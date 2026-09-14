"""위키 마크다운에서 매뉴얼 검색 목록(search-index.json)을 만든다.

사용: python build_index.py <위키 폴더> <출력 json>

- 페이지를 제목(##) 단위 절로 나누고, 문단·목록·표 한 줄을 검색 단위로 저장한다.
- 절마다 GitHub 가 붙이는 제목 앵커를 계산해 검색 결과에서 그 부분으로 바로 이동한다.
"""
import html
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

SKIP = {"_Sidebar", "_Footer", "Home", "Goo"}
NAV = ("← 이전", "다음 퀵 가이드", "**다음 →**")


def slug_base(text):
    """GitHub 제목 앵커: 소문자 → 글자·숫자·밑줄·하이픈·공백만 남김 → 공백을 하이픈으로."""
    kept = [ch for ch in text.lower()
            if unicodedata.category(ch)[0] in "LM" or unicodedata.category(ch) in ("Nd", "Pc") or ch in "- "]
    return "".join(kept).replace(" ", "-")


def inline(s):
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"<img[^>]*>", "", s)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("**", "").replace("__", "").replace("`", "")
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def flatten_html_tables(md):
    """사진|설명 HTML 표는 칸 내용만 꺼내 일반 줄로 만든다."""
    def cells(m):
        parts = re.findall(r"<td[^>]*>(.*?)</td>", m.group(0), flags=re.S)
        return "\n\n".join(p.strip() for p in parts) + "\n"
    return re.sub(r"<table>.*?</table>", cells, md, flags=re.S)


def build(wiki_dir):
    names = sorted(os.path.splitext(f)[0] for f in os.listdir(wiki_dir)
                   if f.endswith(".md") and os.path.splitext(f)[0] not in SKIP)
    # 입구 페이지를 맨 앞에
    names.sort(key=lambda n: (0 if n == "DIYversity-메뉴얼" else 1, n))
    pages, sections, items = [], [], []
    for name in names:
        md = open(os.path.join(wiki_dir, name + ".md"), encoding="utf-8").read()
        md = flatten_html_tables(md)
        lines = md.split("\n")
        title = next((inline(l[2:]) for l in lines if l.startswith("# ")), name)
        pi = len(pages)
        pages.append({"p": name, "t": title})
        sections.append([pi, "", ""])
        si, used, sec_count = len(sections) - 1, {}, {}
        in_code = False
        for i, raw in enumerate(lines):
            line = raw.rstrip()
            if line.startswith("```"):
                in_code = not in_code
                continue
            if in_code or not line.strip():
                continue
            m = re.match(r"^(#{1,6})\s+(.*)$", line)
            if m:
                text = inline(m.group(2))
                base = slug_base(text)
                n = used.get(base, 0)
                used[base] = n + 1
                anchor = base if n == 0 else f"{base}-{n}"
                if len(m.group(1)) == 1:
                    continue
                sections.append([pi, text, anchor])
                si = len(sections) - 1
                continue
            if re.match(r"^\s*\|?\s*:?-{3,}", line) or re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
                continue
            if any(k in line for k in NAV):
                continue
            if line.lstrip().startswith("|"):
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                if re.match(r"^\s*\|?\s*:?-{3,}", nxt):
                    continue                                   # 표 머리칸
                cells = [inline(c) for c in line.strip().strip("|").split("|")]
                text = " — ".join(c for c in cells if c)
            else:
                line = re.sub(r"^\s*(>\s*)+", "", line)
                line = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", line)
                text = inline(line)
            if len(text) < 2:
                continue
            items.append([si, text])
            sec_count[si] = sec_count.get(si, 0) + 1
        # 본문 없는 절도 제목으로 찾히게
        for s in range(pi and next(k for k, sec in enumerate(sections) if sec[0] == pi), len(sections)):
            if sections[s][0] == pi and sections[s][1] and not sec_count.get(s):
                items.append([s, sections[s][1]])
    kst = timezone(timedelta(hours=9))
    return {"built": datetime.now(kst).strftime("%Y-%m-%d %H:%M"),
            "pages": pages, "sections": sections, "items": items}


if __name__ == "__main__":
    wiki, out = sys.argv[1], sys.argv[2]
    data = build(wiki)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"페이지 {len(data['pages'])} · 절 {len(data['sections'])} · 검색 단위 {len(data['items'])} → {out}")
