"""第七輪生活事件第三批檢查程式。

用法：
  python3 -I check_batch3.py <events.json>          檢查一個檔
  python3 -I check_batch3.py --selftest              用故意寫錯的假事件自測
  python3 -I check_batch3.py --selftest <events.json> 先自測再檢查

錯誤（ERROR）一定要改到 0；警告（WARN）要人工看過，在對照表寫明處理。
相似度用字元二元組（bigram）的 Jaccard 係數，跟遊戲現有 31 則（只有第一段前段）與第六輪草稿 92 則（text）比。
字數計算：佔位字（{name} 等）一律當 2 個字算。
"""
import json, re, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
REF = HERE / '_ref'

ALLOWED_FIELDS = ['id', 'layer', 'need', 'not', 'months', 'signal', 'text', 'text2', 'life', 'means',
                  'tags', 'src', 'freq_basis', 'sensitive', 'clinical_check', 'grp', 'status']
REQUIRED = ['id', 'layer', 'text', 'life', 'means', 'tags', 'src', 'freq_basis', 'sensitive',
            'clinical_check', 'grp', 'status']
FORBIDDEN_FIELDS = ['eff', 'set', 'opts', 'w', 'mutex', 'weight']
TOKENS = set('''@work @live @spouse @child @alone @kids @partner @say @nosay
in_hospital in_icu in_rcc in_rcw in_nh home_vent o2_home
trach ett bedbound weak_cough dementia dysphagia stroke_hx copd heart_dz terminal
foreign_cg hire_cg ltc respite daycare care_bed aids home_team suction_home hospice major_ill disab_card dnr ad_signed hcpa
quit_job fam_split card_debt bank_loan rev_mortgage'''.split())
PLACEHOLDERS = {'{name}', '{ta}', '{me}', '{oth}', '{cause}', '{age}', '{cg}'}
BANNED = ['應該', '記得要', '提醒', '建議', '其實這是', '正確', '錯誤', '其實']
GAME_TEXT = ['text', 'text2', 'life']
NUM_PAT = re.compile(r'[0-9０-９]|[一二三四五六七八九十百千萬兩]+\s*(元|塊|天|日|週|周|個月|年|%|％|成|小時|分鐘|公斤|床)')
NATION = re.compile(r'印尼|越南|菲律賓|泰國|印傭|菲傭|越傭')
ROLE = re.compile(r'媳婦|女婿|公公|婆婆')
MOBILE = re.compile(r'走路|走到|走去|走進|走出|散步|搬|煮|下廚|打電話|下樓|上樓|爬樓梯|騎車|開車')
MEANS_BAD = '你那時候看到的是'


def plen(s):
    return len(re.sub(r'\{[a-z]+\}', 'XX', s))


def bigrams(s):
    s = re.sub(r'\{[a-z]+\}', '', s)
    s = re.sub(r'[\s，。、「」：；！？…—（）()·,.!?]', '', s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def jac(a, b):
    A, B = bigrams(a), bigrams(b)
    return len(A & B) / len(A | B) if A and B else 0.0


def load_ref():
    ref = []
    for line in (REF / 'existing31.tsv').read_text(encoding='utf-8').splitlines():
        i, lay, cond, txt = line.split('\t')
        ref.append(('現有', i, txt))
    for e in json.loads((REF / 'drafts92.json').read_text(encoding='utf-8')):
        ref.append(('草稿', e['id'], e['text']))
    return ref


def check(events, label):
    errs, warns, rows = [], [], []
    ref = load_ref()
    ref_ids = {r[1] for r in ref}
    seen = set()
    signals = {}
    if not isinstance(events, list):
        return ['頂層不是 JSON 陣列'], [], []
    for n, e in enumerate(events):
        eid = e.get('id', f'(第{n}則沒有 id)')
        E = lambda m: errs.append(f'{eid}: {m}')
        W = lambda m: warns.append(f'{eid}: {m}')
        for k in e:
            if k in FORBIDDEN_FIELDS:
                E(f'用了禁止欄位 {k}')
            elif k not in ALLOWED_FIELDS:
                E(f'用了清單外欄位 {k}')
        for k in REQUIRED:
            if k not in e:
                E(f'缺必填欄位 {k}')
        if not re.fullmatch(r'E_[a-z0-9_]+', str(eid)):
            E('id 格式不符（E_ 開頭、英文小寫與底線）')
        if eid in seen:
            E('id 在本批重複')
        if eid in ref_ids:
            E('id 撞到現有或草稿')
        seen.add(eid)
        lay = e.get('layer', [])
        if not (isinstance(lay, list) and lay and all(x in (1, 2, 3, 4, 5) for x in lay)):
            E('layer 要是 1～5 的非空陣列')
        for key in ('need', 'not'):
            v = e.get(key, [])
            if not isinstance(v, list):
                E(f'{key} 不是陣列')
                continue
            for t in v:
                if t not in TOKENS:
                    E(f'{key} 用了清單外記號 {t}')
        if set(e.get('need', [])) & set(e.get('not', [])):
            E('need 與 not 有相同記號')
        if 'months' in e and not (isinstance(e['months'], list) and e['months'] and all(isinstance(m, int) and 1 <= m <= 12 for m in e['months'])):
            E('months 要是 1～12 的非空陣列（沒有就不寫）')
        if e.get('grp') != 3:
            E('grp 不是 3')
        if e.get('status') != 'draft':
            E('status 不是 draft')
        for b in ('sensitive', 'clinical_check'):
            if b in e and not isinstance(e[b], bool):
                E(f'{b} 不是 true/false')
        if 'text2' in e and not e['text2']:
            E('text2 是空字串（沒有就不要寫這個欄位）')
        if 'signal' in e:
            signals.setdefault(e['signal'], []).append(eid)
        means = e.get('means', '')
        if means.startswith(MEANS_BAD):
            E('means 以「你那時候看到的是」開頭')
        allg = ''
        for f in GAME_TEXT:
            s = e.get(f, '')
            if not isinstance(s, str):
                E(f'{f} 不是字串')
                continue
            allg += s
            for b in BANNED:
                if b in s:
                    E(f'{f} 有禁字「{b}」')
            if NUM_PAT.search(s):
                E(f'{f} 有數字（金額、天數、比例等）：{NUM_PAT.search(s).group(0)}')
            if NATION.search(s):
                E(f'{f} 寫了國籍：{NATION.search(s).group(0)}')
            if ROLE.search(s):
                E(f'{f} 用了玩家不會有的親屬稱呼：{ROLE.search(s).group(0)}')
            for ph in re.findall(r'\{[^}]*\}', s):
                if ph not in PLACEHOLDERS:
                    E(f'{f} 用了清單外佔位字 {ph}')
        for ph in re.findall(r'\{[^}]*\}', means):
            if ph not in PLACEHOLDERS:
                E(f'means 用了清單外佔位字 {ph}')
        if plen(e.get('text', '')) > 80:
            E(f'text 超過 80 字（{plen(e["text"])}）')
        if 'text2' in e and plen(e['text2']) > 80:
            E(f'text2 超過 80 字（{plen(e["text2"])}）')
        if plen(e.get('life', '')) > 30:
            E(f'life 超過 30 字（{plen(e["life"])}）')
        need = set(e.get('need', []))
        if '孩子' in allg and '@kids' not in need:
            E('遊戲文字有「孩子」但 need 沒有 @kids')
        if '伴侶' in allg and '@partner' not in need:
            E('遊戲文字有「伴侶」但 need 沒有 @partner')
        if '{oth}' in allg and '@alone' not in set(e.get('not', [])):
            W('用了 {oth} 但 not 沒有 @alone（她沒有其他成年家人時會印成「親戚」，請確認句子仍通順）')
        if '{cg}' in allg and not ({'foreign_cg', 'hire_cg'} & need):
            W('用了 {cg} 但 need 沒有 foreign_cg 或 hire_cg')
        if ({4, 5} & set(lay)) and MOBILE.search(allg):
            W(f'呼吸器長照或安寧段落出現行動相關字「{MOBILE.search(allg).group(0)}」，確認主詞不是她')
        if '廚房' in allg or '灶' in allg:
            W('出現廚房，確認沒有預設誰管廚房')
        for kw in ('回診單', '紅紙', '群組'):
            if kw in allg:
                W(f'用了已經用很多次的物件「{kw}」')
        best = max(((jac(e.get('text', ''), r[2]), r) for r in ref), key=lambda x: x[0])
        if best[0] >= 0.30:
            W(f'text 與{best[1][0]} {best[1][1]} 相似度 {best[0]:.2f}，確認不重複')
        rows.append((eid, round(best[0], 2), best[1][0] + ' ' + best[1][1]))
    for sg, ids in signals.items():
        if len(ids) > 3:
            errs.append(f'signal「{sg}」在本批出現 {len(ids)} 則（上限 3）：{"、".join(ids)}')
    print(f'== {label}：{len(events)} 則，ERROR {len(errs)}，WARN {len(warns)}')
    for m in errs:
        print('ERROR', m)
    for m in warns:
        print('WARN ', m)
    return errs, warns, rows


FAKE = [{
    'id': 'E_bags',
    'layer': [6],
    'need': ['drives_car', '@kids'],
    'text': '你建議{name}其實可以去看看，花了3000元，媳婦也來了，孩子在旁邊哭，{dog}也叫了很久很久很久很久很久很久很久很久很久很久很久很久很久很久很久很久很久很久很久很久，直到天亮才停下來。',
    'life': '{name}每天走路去市場買菜，煮一大鍋湯給全家人吃，從年輕煮到老，一年到頭都沒停過。',
    'means': '你那時候看到的是一次普通的回診。',
    'tags': ['測試'], 'src': '—', 'freq_basis': '—', 'sensitive': 'no', 'clinical_check': False,
    'grp': 2, 'status': 'final', 'weight': 3,
}]

if __name__ == '__main__':
    args = sys.argv[1:]
    if '--selftest' in args:
        args.remove('--selftest')
        errs, warns, _ = check(FAKE, '自測（故意寫錯的假事件）')
        must = ['禁字「建議」', '禁字「其實」', '清單外記號 drives_car', '禁止欄位 weight', '撞到現有',
                'layer', '數字', '媳婦', '清單外佔位字 {dog}', 'text 超過 80', 'life 超過 30',
                '你那時候看到的是', 'grp', 'status', 'sensitive']
        missed = [m for m in must if not any(m in x for x in errs)]
        print('自測結果：', '全部抓到' if not missed else f'漏抓 {missed}')
        if missed:
            sys.exit(2)
    for p in args:
        ev = json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
        errs, warns, rows = check(ev, p)
        print('\n相似度（每則 text 最像的現有或草稿）：')
        for r in sorted(rows, key=lambda x: -x[1]):
            print(f'  {r[0]}\t{r[1]}\t{r[2]}')
        if errs:
            sys.exit(1)
