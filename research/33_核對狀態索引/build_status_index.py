"""依序合併各處核對結果，產出每筆來源的核對狀態。
順序：28_本機補核_第二批 → 26_本機補核 → 23_原頁核對 → 各輪來源表「已開原頁」標記；都沒有＝未核。
若較前面的來源只寫「打不開」、後面有實際結果，採用後面的結果（判斷），並在 依據 欄註明。
用法：python3 -I build_status_index.py <research 資料夾路徑>
"""
import csv, re, sys, pathlib

R = pathlib.Path(sys.argv[1])
OUT = R / '33_核對狀態索引'
ID = re.compile(r'\b([A-Z][0-9]{3})\b')

def norm(raw):
    r = raw.strip()
    if r.startswith('相符'): return '原頁相符'
    if r.startswith('部分相符'): return '原頁部分相符'
    if r.startswith('不符'): return '原頁不符'
    if r.startswith('網址錯'): return '網址錯'
    if r.startswith('打不開'): return '打不開'
    if r.startswith('已核（他處）'): return '原頁相符'
    return None

def rows(path):
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('|') and not line.startswith('|---'):
            yield [c.strip() for c in line.strip().strip('|').split('|')]

def set_to_folder(s):
    if s.startswith('23_18'): return '18'
    if s.startswith('23_19'): return '19'
    if s.startswith('23_20'): return '20'
    if s.startswith('25'): return '25'
    if s.startswith('27'): return '27'
    return s

# 每筆來源依資料夾區分（同字首不同資料夾理論上不重複，仍保留資料夾欄）
PREFIX_FOLDER = {'L':'18','F':'19','E':'20','B':'24','G':'25','U':'25','A':'25','T':'25','J':'27甲','Q':'27乙','W':'27丙','D':'27丁'}
records = {}  # id -> list of (priority, layer, raw, normalized, file)

def add(i, layer, pri, raw, f):
    n = norm(raw)
    if n: records.setdefault(i, []).append((pri, layer, raw, n, f))

# 28
for f in sorted((R/'28_本機補核_第二批').glob('B*_核對表.md')):
    for c in rows(f):
        if len(c) > 4 and ID.fullmatch(c[0]):
            add(c[0], '28_本機補核_第二批', 1, c[4], f.name)
# 26（編號欄可能含多個編號）
for c in rows(R/'26_本機補核'/'核對表.md'):
    if len(c) > 3 and c[0] != '來源編號':
        for i in set(ID.findall(c[0])):
            add(i, '26_本機補核', 2, c[3], '核對表.md')
# 23
for name in ('18_核對表.md','19_核對表.md','20_核對表.md'):
    for c in rows(R/'23_原頁核對'/name):
        if len(c) > 2 and ID.fullmatch(c[0]):
            add(c[0], '23_原頁核對', 3, c[2], name)

# 各輪來源表：所有編號＋是否自行開原頁
SRC_TABLES = ['18_法規與金額查證/10_來源紀錄.md','19_外國制度與台灣缺口/10_來源紀錄.md','20_生活事件素材/10_來源紀錄.md',
              '24_生活事件卡片/10_來源紀錄.md','25_外國對照_德英澳/10_來源紀錄.md',
              '27_第五輪/甲_急診與加護/10_來源紀錄.md','27_第五輪/乙_錢/10_來源紀錄.md',
              '27_第五輪/丙_走了以後與呼吸器門檻/10_來源紀錄.md','27_第五輪/丁_外籍看護與生活事件補缺/10_來源紀錄.md']
meta = {}
for t in SRC_TABLES:
    p = R/t
    for c in rows(p):
        if len(c) >= 7 and ID.fullmatch(c[0]):
            i = c[0]
            meta.setdefault(i, {'表': t, '網址': c[2], '原文或摘要': c[5]})
            if '已開原頁' in c[5]:
                add(i, '自行開原頁（' + t.split('/')[0] + '）', 4, '相符', t)

out = []
for i in sorted(set(meta) | set(records), key=lambda x: (x[0], int(x[1:]))):
    recs = sorted(records.get(i, []))
    chosen, note = None, ''
    for r in recs:
        if chosen is None:
            chosen = r
        elif chosen[3] == '打不開' and r[3] != '打不開':
            note = f'{chosen[1]} 打不開，改採 {r[1]}（判斷）'
            chosen = r; break
        else:
            break
    status = chosen[3] if chosen else '未核'
    layer = chosen[1] if chosen else '—'
    raw = chosen[2] if chosen else ''
    m = meta.get(i, {})
    out.append({'來源編號': i, '所屬資料夾': PREFIX_FOLDER.get(i[0], '?'), '核對狀態': status, '依據層': layer,
                '原始結果文字': raw[:60], '依據檔': chosen[4] if chosen else '', '備註': note,
                '網址': m.get('網址', ''), '來源表': m.get('表', '（不在各輪來源表）')})

with open(OUT/'核對狀態索引.csv', 'w', encoding='utf-8-sig', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)

from collections import Counter
cnt = Counter((o['所屬資料夾'], o['核對狀態']) for o in out)
folders = sorted({o['所屬資料夾'] for o in out})
states = ['原頁相符','原頁部分相符','原頁不符','網址錯','打不開','未核']
print('| 資料夾 | ' + ' | '.join(states) + ' | 合計 |')
print('|---' * (len(states)+2) + '|')
for f in folders:
    v = [cnt[(f,s)] for s in states]
    print(f'| {f} | ' + ' | '.join(map(str,v)) + f' | {sum(v)} |')
v = [sum(cnt[(f,s)] for f in folders) for s in states]
print('| 合計 | ' + ' | '.join(map(str,v)) + f' | {sum(v)} |')
print('改採後層結果:', sum(1 for o in out if o['備註']))
