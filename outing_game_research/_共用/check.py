#!/usr/bin/env python3
"""「我想要出門」研究交件檢查程式。

用法：python3 -I check.py <研究根目錄> [--now "2026-11-04 21:00"]

檢查四件事：
1. 發現條列與表格資料列都有來源編號（[S1-003]、[判斷]、[查無]、本機已查）。
2. 來源紀錄每列都有網址與讀取時間。
3. 沒有比現在晚的日期（有〔原文未來日期〕標記的行另列，不算錯）。
4. 沒有大陸用語（「」內引文、> 引用行、標〔原文用語〕的行、_原始存檔/ 不掃）。
"""
import re
import sys
import datetime
from pathlib import Path

# 大陸用語 → 台灣用語（共 26 組）
BANNED = {
    "軟件": "軟體", "視頻": "影片", "信息": "資訊", "文件夾": "資料夾",
    "屏幕": "螢幕", "默認": "預設", "網絡": "網路", "質量": "品質",
    "鏈接": "連結", "硬件": "硬體", "打印": "列印", "服務器": "伺服器",
    "數據庫": "資料庫", "互聯網": "網際網路", "短信": "簡訊", "出租車": "計程車",
    "呼吸機": "呼吸器", "制氧機": "製氧機", "吸痰": "抽痰", "反饋": "回饋",
    "醫保": "健保", "殘疾人": "身心障礙者", "U盤": "隨身碟", "博客": "部落格",
    "鼠標": "滑鼠", "帖子": "貼文",
}

CITE = re.compile(r"\[(S\d{1,2}-\d{3}[a-z]?|判斷|查無|本機已查)\]")
SRC_ID = re.compile(r"^S\d{1,2}-\d{3}[a-z]?$")
READ_TIME = re.compile(r"\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}")
URL_LIKE = re.compile(r"(https?://\S+|research/\S+|本機)")
LIST_ITEM = re.compile(r"^\s*(?:(?:[-*]|\d+[.、)])\s+|[・•]\s*)\S")
FUTURE_MARK = "〔原文未來日期〕"
LOCAL_TERM_MARK = "〔原文用語〕"
SKIP_DIRS = {"_原始存檔", "_自測假資料"}
SKIP_TERM_FILES = {"01_幫手共同規則.md", "99_檢查結果.md", "check.py"}

DATE_PATTERNS = [
    # 西元年月日：2026-11-04、2026/11/04、2026.11.04、2026年11月4日
    (re.compile(r"(?<!\d)(20\d{2})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})(?!\d)"), 0),
    # 民國年月日：115年11月5日、115/11/05、115.11.05
    (re.compile(r"(?<!\d)(1[01]\d)\s*[/.年]\s*(\d{1,2})\s*[/.月]\s*(\d{1,2})(?!\d)"), 1911),
]
YEAR_ONLY = re.compile(r"(?<!\d)(20\d{2})\s*年(?!\s*\d)")


def finding_files(root: Path):
    """要檢查「每條發現都有來源編號」的檔案。"""
    for p in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts) or "_共用" in p.relative_to(root).parts:
            continue
        name = p.name
        if name.startswith(("20_", "21_", "30_", "40_")):
            yield p, None
        elif name == "00_總覽.md":
            yield p, ("發現", "把握最低", "最有用")


def strip_urls(line: str) -> str:
    return re.sub(r"https?://\S+", "", line)


def check_citations(root: Path):
    errors = []
    for p, only_sections in finding_files(root):
        lines = p.read_text(encoding="utf-8").splitlines()
        section_ok = only_sections is None
        in_code = False
        for i, line in enumerate(lines, 1):
            if line.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if line.startswith("#"):
                if only_sections is not None:
                    section_ok = any(k in line for k in only_sections)
                continue
            if not section_ok:
                continue
            is_table_row = line.startswith("|") and not re.match(r"^\|[\s:|-]+\|?\s*$", line)
            if is_table_row:
                nxt = lines[i] if i < len(lines) else ""
                if re.match(r"^\|[\s:|-]+\|?\s*$", nxt):  # 表頭列
                    continue
            if (is_table_row or LIST_ITEM.match(line)) and not CITE.search(line):
                errors.append(f"{p.relative_to(root)}:{i}: 缺來源編號：{line.strip()[:60]}")
    return errors


def check_source_logs(root: Path):
    errors, count, ids = [], 0, set()
    for p in sorted(root.rglob("10_來源紀錄.md")):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        header = None
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if "編號" in cells[0]:
                header = cells
                continue
            if not cells or not SRC_ID.match(cells[0]):
                continue
            count += 1
            ids.add(cells[0])
            rel = f"{p.relative_to(root)}:{i} {cells[0]}"
            url_col = header.index("網址") if header and "網址" in header else 2
            time_col = next((k for k, h in enumerate(header or []) if "時間" in h or "讀取" in h), 3)
            url = cells[url_col] if len(cells) > url_col else ""
            when = cells[time_col] if len(cells) > time_col else ""
            if not URL_LIKE.search(url):
                errors.append(f"{rel}: 缺網址（網址欄：「{url[:40]}」）")
            if not READ_TIME.search(when):
                errors.append(f"{rel}: 缺讀取時間或格式不符（時間欄：「{when[:40]}」）")
    return errors, count, ids


def check_cited_ids_exist(root: Path, ids: set):
    missing = {}
    for p in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        for m in re.finditer(r"\[(S\d{1,2}-\d{3}[a-z]?)\]", p.read_text(encoding="utf-8")):
            if m.group(1) not in ids:
                missing.setdefault(m.group(1), set()).add(str(p.relative_to(root)))
    return [f"{k}: 被引用但來源紀錄裡沒有（{', '.join(sorted(v))}）" for k, v in sorted(missing.items())]


def check_dates(root: Path, now: datetime.datetime):
    errors, marked = [], []
    for p in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts) or p.name == "99_檢查結果.md":
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            text = strip_urls(line)
            hits = []
            for pat, offset in DATE_PATTERNS:
                for m in pat.finditer(text):
                    y, mo, d = int(m.group(1)) + offset, int(m.group(2)), int(m.group(3))
                    try:
                        dt = datetime.datetime(y, mo, d)
                    except ValueError:
                        continue
                    if dt.date() > now.date():
                        hits.append(m.group(0))
                    elif dt.date() == now.date():
                        # 同一天時，比對時分
                        t = re.search(re.escape(m.group(0)) + r"\s+(\d{1,2}):(\d{2})", text)
                        if t and (int(t.group(1)), int(t.group(2))) > (now.hour, now.minute):
                            hits.append(m.group(0) + " " + t.group(1) + ":" + t.group(2))
            for m in YEAR_ONLY.finditer(text):
                if int(m.group(1)) > now.year:
                    hits.append(m.group(0))
            if hits:
                msg = f"{p.relative_to(root)}:{i}: {'、'.join(hits)}｜{line.strip()[:50]}"
                (marked if FUTURE_MARK in line else errors).append(msg)
    return errors, marked


def check_terms(root: Path):
    errors = []
    for p in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts) or p.name in SKIP_TERM_FILES:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(">") or LOCAL_TERM_MARK in line:
                continue
            text = re.sub(r"「[^」]*」", "", strip_urls(line))
            text = re.sub(r"『[^』]*』", "", text)
            for bad, good in BANNED.items():
                if bad in text:
                    errors.append(f"{p.relative_to(root)}:{i}: 「{bad}」→「{good}」｜{line.strip()[:50]}")
    return errors


def main():
    root = Path(sys.argv[1]).resolve()
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).replace(tzinfo=None)
    if "--now" in sys.argv:
        now = datetime.datetime.strptime(sys.argv[sys.argv.index("--now") + 1], "%Y-%m-%d %H:%M")
    print(f"檢查根目錄：{root}")
    print(f"現在時間（台灣）：{now:%Y-%m-%d %H:%M}")
    print(f"大陸用語清單（{len(BANNED)} 組）：" + "、".join(f"{k}→{v}" for k, v in BANNED.items()))
    cite = check_citations(root)
    logs, n, ids = check_source_logs(root)
    missing = check_cited_ids_exist(root, ids)
    dates, marked = check_dates(root, now)
    terms = check_terms(root)
    sections = [
        ("一、發現條列缺來源編號", cite),
        (f"二、來源紀錄缺網址或讀取時間（共掃 {n} 列）", logs),
        ("二之一、被引用但來源紀錄沒有的編號", missing),
        ("三、比現在晚的日期（未標記）", dates),
        ("三之一、比現在晚的日期（已標〔原文未來日期〕，供人工確認）", marked),
        ("四、大陸用語", terms),
    ]
    total = 0
    for title, items in sections:
        print(f"\n## {title}：{len(items)} 筆")
        for x in items:
            print(f"- {x}")
        if not title.startswith("三之一"):
            total += len(items)
    print(f"\n合計待修：{total} 筆")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
