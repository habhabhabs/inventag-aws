#!/usr/bin/env python3
"""Convert zh-Hans docs pages to zh-Hant for Taiwan readers.

Steps for each page:
  1. OpenCC `s2twp` (Simplified to Traditional, Taiwan standard, with phrases).
  2. A Taiwan term glossary (GLOSSARY below) fixes terms that s2twp leaves in
     Mainland form, for example 賬戶 -> 帳戶, 許可權 -> 權限, 模板 -> 範本.
  3. Table "column" and "row" words are swapped to the Taiwan words
     (column = 欄, row = 列) by a few conservative rules (see fix_columns).

These parts are never changed, they are copied from the zh-Hans file:
  fenced code blocks, inline code, link and image targets, bare URLs,
  heading anchors ({#slug} and {/* #slug */}), import/export lines,
  JSX attributes href/src/to/icon, and front matter keys.
After converting, the script checks that those parts are identical in the
output and refuses to write a file when they are not.

Usage (run from website/, needs `pip install opencc-python-reimplemented`):
  python3 scripts/zh-hant-convert.py --all                 convert every page
  python3 scripts/zh-hant-convert.py --all --folders guides templates examples
  python3 scripts/zh-hant-convert.py translations/zh-Hant/docs/guides/run-a-scan.md
  python3 scripts/zh-hant-convert.py --check --all         write nothing; exit 1
                                                           if any page is out of date
The source of translations/zh-Hant/docs/X is translations/zh-Hans/docs/X.
The conversion is idempotent: running it twice gives the same file.
"""
import argparse
import os
import re
import sys

try:
    import opencc
except ImportError:
    sys.exit('Install OpenCC first: pip install opencc-python-reimplemented')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
HANS = os.path.join(ROOT, 'translations', 'zh-Hans', 'docs')
HANT = os.path.join(ROOT, 'translations', 'zh-Hant', 'docs')

# Applied in order, after s2twp. Longer terms come first.
GLOSSARY = [
    ('釋出說明', '發行說明'), ('釋出', '發佈'),
    ('訪問金鑰', '存取金鑰'), ('訪問', '存取'),
    ('配置檔案', '設定檔'), ('配置', '設定'),
    ('許可權', '權限'), ('許可證', '授權'),
    ('賬', '帳'),
    ('對映', '對應'),
    ('模板', '範本'),
    ('示例', '範例'),
    ('當前', '目前'),
    ('導航', '導覽'),
    ('選項卡', '分頁'),
    ('關鍵詞', '關鍵字'),
    ('可複用', '可重複使用'),
    ('只讀', '唯讀'),
    ('代入', '擔任'),
    ('版式', '版面配置'),
    ('並行', '平行'),
    ('儲存桶', '儲存貯體'),
    ('選中', '選取'),
    ('響應', '回應'),
    ('令牌', '權杖'),
    ('登錄', '登入'),
    ('構建', '建置'),
    ('倉庫', '儲存庫'),
    ('退出碼', '結束代碼'),
    ('拉取請求', '提取要求'),
    ('反饋', '回饋'),
]

# Mainland 行 (row) = Taiwan 列, and Mainland 列 (column) = Taiwan 欄.
# s2twp does not know which one is meant (it even turns some line counts such as
# 一行 into 一列), so both are decided on the zh-Hans text BEFORE s2twp runs and
# carried through it as private-use marker characters.
COL, LINE, ROW = '\ue002', '\ue003', '\ue004'
ROW_RULES = [  # zh-Hans patterns where 行 means a table row; group 1 or 2 is kept
    (re.compile(r'表头行'), '表头' + ROW),
    (re.compile(r'前( ?)(几|\d+)( ?)行'), r'前\1\2\3' + ROW),
    (re.compile(r'行数'), ROW + '数'),
    (re.compile(r'(最多|共|最少|上限为?) ?(\d+) 行'), r'\1 \2 ' + ROW),
    (re.compile(r'(每个[^，。；：\n|`]{0,10}?一)行(?!命令|摘要|日志|代码|文本)'), r'\1' + ROW),
    (re.compile(r'行顺序'), ROW + '顺序'),
    (re.compile(r'(^|。)行按'), r'\1' + ROW + '按'),
    (re.compile(r'([二三四五六七八九两\d]+)行(?=存储|数据|资源)'), r'\1' + ROW),
]
# Any other 行 after a number word is a text line ("打印一行 OK"): keep it as 行.
LINE_RULE = re.compile(r'(?:(?<=[一二两三四五六七八九十\d几每多])|(?<=[一二两三四五六七八九十\d几每多] ))行(?![为业动])')
# Column: 列 -> 欄, except where it is part of 列表/列出/排列/列在/列为/列入/列举/系列/序列/并列.
COLUMN = re.compile(r'(?<![排序系并陈])列(?![表出在为入举印车])')

PH = '{}'
PROTECT = [
    re.compile(r'`[^`\n]+`'),                                  # inline code
    re.compile(r'\]\([^)\n]*\)'),                              # link/image targets
    re.compile(r'\{(?:#|/\* #)[\w-]+(?: \*/)?\}'),             # heading anchors
    re.compile(r'https?://[^\s)>"\']+'),                       # bare URLs
    re.compile(r'\b(?:href|src|to|icon)=(?:"[^"\n]*"|\{[^}\n]*\})'),
    re.compile(r'require\([^)\n]*\)'),
]
FENCE = re.compile(r'^(```|~~~)')
cc = opencc.OpenCC('s2twp')


def mark(s):
    for rx, rep in ROW_RULES:
        s = rx.sub(rep, s)
    s = LINE_RULE.sub(LINE, s)
    return COLUMN.sub(COL, s)


def convert_text(s):
    saved = []

    def stash(m):
        saved.append(m.group(0))
        return PH.format(len(saved) - 1)

    for rx in PROTECT:
        s = rx.sub(stash, s)
    s = cc.convert(mark(s))
    for a, b in GLOSSARY:
        s = s.replace(a, b)
    s = s.replace(COL, '欄').replace(ROW, '列').replace(LINE, '行')
    return re.sub('(\\d+)', lambda m: saved[int(m.group(1))], s)


def convert_file(src):
    out, fence, i = [], None, 0
    lines = src.split('\n')
    in_fm = lines[0] == '---'
    for n, line in enumerate(lines):
        if in_fm:
            if n > 0 and line == '---':
                in_fm = False
                out.append(line)
            elif ':' in line and n > 0:
                k, v = line.split(':', 1)
                out.append(k + ':' + convert_text(v))
            else:
                out.append(line)
            continue
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)
            out.append(line)
        elif fence is not None:
            if line.startswith(fence):
                fence = None
            out.append(line)
        elif re.match(r'^(import|export) ', line):
            out.append(line)
        else:
            out.append(convert_text(line))
    return '\n'.join(out)


def invariants(src, dst):
    """Parts that must be identical to the zh-Hans file."""
    def parts(t):
        fences = re.findall(r'^(```[\s\S]*?^```)', t, flags=re.M)
        body = re.sub(r'^```[\s\S]*?^```', '', t, flags=re.M)
        return (fences,
                re.findall(r'`[^`\n]+`', body),
                re.findall(r'\]\([^)\n]*\)', body),
                re.findall(r'\{(?:#|/\* #)[\w-]+(?: \*/)?\}', body),
                [l.split(':', 1)[0] for l in t.split('\n---\n')[0].split('\n')],
                [l for l in t.split('\n') if re.match(r'^(import|export) ', l)])
    return parts(src) == parts(dst)


def pages(folders):
    for dp, _, fs in os.walk(HANS):
        for f in sorted(fs):
            if f.endswith(('.md', '.mdx')):
                rel = os.path.relpath(os.path.join(dp, f), HANS)
                if not folders or rel.split(os.sep)[0] in folders:
                    yield rel


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='*', help='zh-Hant (or zh-Hans) page paths')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--folders', nargs='*', default=[], help='only these top-level docs folders')
    ap.add_argument('--check', action='store_true', help='write nothing; exit 1 if a page would change')
    a = ap.parse_args()
    rels = list(pages(a.folders)) if a.all else []
    for f in a.files:
        f = os.path.abspath(f)
        base = HANT if f.startswith(HANT) else HANS
        rels.append(os.path.relpath(f, base))
    if not rels:
        ap.error('give page paths or --all')
    stale = 0
    for rel in rels:
        src = open(os.path.join(HANS, rel), encoding='utf8').read()
        dst = convert_file(src)
        if not invariants(src, dst):
            sys.exit(f'{rel}: protected content changed, not written')
        path = os.path.join(HANT, rel)
        cur = open(path, encoding='utf8').read() if os.path.exists(path) else None
        if cur != dst:
            stale += 1
            print(('would change ' if a.check else 'wrote ') + rel)
            if not a.check:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, 'w', encoding='utf8').write(dst)
    print(f'{stale} of {len(rels)} page(s) {"out of date" if a.check else "updated"}')
    sys.exit(1 if a.check and stale else 0)


if __name__ == '__main__':
    main()
