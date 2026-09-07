#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A4 인쇄용 커피 메뉴판 생성.

단일 소스: content/menu/filter-menu.json
산출물  : static/menu/filter-menu.html  (A4 세로 2장, 브라우저에서 인쇄)

    python scripts/build_menu.py

인쇄 설정: 용지 A4, 배율 100%, 여백 없음, 배경 그래픽 켜기.
메뉴를 고칠 때는 JSON 만 고치고 다시 실행하면 된다.
(구글 시트로 편집하려면 scripts/menu_sheet.py push / pull 사용)
"""
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "content" / "menu" / "filter-menu.json"
OUT = ROOT / "static" / "menu" / "filter-menu.html"

CSS = """
  :root{
    --ink:#111;
    --sub:#6b6b6b;
    --gold:#F5A623;
    --gold-d:#D98200;
    --paper:#fff;
  }
  *{box-sizing:border-box;}
  html,body{
    margin:0;padding:0;background:#8d8d8d;
    font-family:"Noto Sans KR","Pretendard","Malgun Gothic",sans-serif;
    color:var(--ink);
    -webkit-print-color-adjust:exact;print-color-adjust:exact;
  }
  .page{
    width:210mm;height:297mm;background:var(--paper);
    margin:8mm auto;padding:11mm 12mm 9mm;
    display:flex;flex-direction:column;
    box-shadow:0 3px 18px rgba(0,0,0,.35);
    position:relative;overflow:hidden;
  }
  .site{position:absolute;top:6mm;right:12mm;font-size:8pt;color:#4a7fd4;letter-spacing:.2px;}
  .head{text-align:center;padding-top:2mm;}
  .head h1{
    font-family:"Oswald","Noto Sans KR",sans-serif;
    font-weight:700;font-size:37pt;line-height:1;margin:0;letter-spacing:-.5px;
  }
  .head h1 .ko{font-family:"Noto Sans KR",sans-serif;font-weight:900;font-size:27pt;}
  .head .tag{margin:2.5mm 0 0;font-size:10.5pt;font-weight:400;color:#333;}
  .head .tag b{font-weight:900;color:var(--ink);}
  .rule{height:2.6pt;background:var(--gold);margin-top:4mm;border-radius:1pt;}

  .sect{display:flex;align-items:baseline;gap:4mm;margin:5mm 0 2.5mm;}
  .sect h2{
    font-family:"Oswald","Noto Sans KR",sans-serif;
    font-size:16.5pt;font-weight:700;margin:0;letter-spacing:.3px;white-space:nowrap;
  }
  .sect .sub{font-size:9pt;color:#888;font-weight:500;white-space:nowrap;}
  .sect .price{
    margin-left:auto;font-size:10pt;font-weight:700;color:var(--gold-d);
    letter-spacing:.2px;text-align:right;white-space:nowrap;
  }
  .sect .price .unit{font-size:8.5pt;color:#999;font-weight:500;}

  .grid{display:grid;grid-template-columns:1fr 1fr;column-gap:8mm;}
  .grid.one{grid-template-columns:1fr;}
  .item{
    border-top:.7pt solid #dcdcdc;
    padding:2.2mm 0 2.1mm;
    break-inside:avoid;page-break-inside:avoid;
  }
  .item.top{border-top:1.4pt solid var(--ink);}
  .item .nm{
    font-size:11pt;font-weight:700;line-height:1.25;
    display:flex;align-items:baseline;gap:2mm;
  }
  .item .nm .txt{flex:1;}
  .item .nm .won{
    font-family:"Oswald",sans-serif;font-size:10pt;font-weight:600;
    color:var(--gold-d);white-space:nowrap;
  }
  .item .notes{font-size:8.7pt;color:var(--sub);margin-top:1mm;line-height:1.3;letter-spacing:-.1px;}
  .proc{
    display:inline-block;font-size:7.4pt;font-weight:700;color:#fff;background:#3a3a3a;
    padding:.4mm 1.6mm;border-radius:1pt;margin-right:1.8mm;
    vertical-align:1px;letter-spacing:-.1px;line-height:1.35;
  }
  .proc.ana{background:var(--gold-d);}
  .proc.decaf{background:#5b7a3f;}

  .page.big .item{padding:3.1mm 0 2.9mm;}
  .page.big .item .nm{font-size:12.4pt;}
  .page.big .item .notes{font-size:9.3pt;margin-top:1.3mm;}

  /* 항목 수와 무관하게 남는 세로 공간을 행에 고르게 나눠 페이지를 채운다 */
  .page.fill .grid{flex:1;grid-auto-rows:1fr;align-content:stretch;}
  .page.fill .item{display:flex;flex-direction:column;justify-content:center;}
  .page.fill .item .nm{font-size:11.6pt;}
  .page.fill .item .notes{font-size:9pt;}

  .spacer{flex:1;}
  .note{
    border:.7pt solid #e2e2e2;border-left:3pt solid var(--gold);
    padding:2.8mm 3.5mm;font-size:8.5pt;color:#555;line-height:1.55;margin-top:5mm;
  }
  .note b{color:var(--ink);}

  .foot{
    display:flex;align-items:center;gap:5mm;
    border-top:1.4pt solid var(--ink);padding-top:3mm;margin-top:4mm;
  }
  .foot .logo{width:20mm;flex:0 0 auto;text-align:center;}
  .foot .logo img{width:16mm;display:block;margin:0 auto .8mm;}
  .foot .logo .han{font-size:7pt;color:#777;letter-spacing:.3px;}
  .foot .msg{font-size:8.8pt;color:#444;line-height:1.55;}
  .foot .msg b{color:var(--ink);font-weight:700;}
  .foot .pg{margin-left:auto;font-family:"Oswald",sans-serif;font-size:9pt;color:#b5b5b5;white-space:nowrap;}

  @page{size:A4 portrait;margin:0;}
  @media print{
    html,body{background:#fff;}
    .page{margin:0;box-shadow:none;page-break-after:always;}
    .page:last-child{page-break-after:auto;}
  }
"""


def esc(s):
    return html.escape(s or "", quote=False)


def render_item(it, is_top):
    cls = "item top" if is_top else "item"
    won = ""
    if it.get("price"):
        won = '<span class="won">%s</span>' % esc(it["price"])
    proc = ""
    if it.get("process"):
        tag = it.get("tag", "")
        proc = '<span class="proc%s">%s</span>' % (
            (" " + tag) if tag else "", esc(it["process"])
        )
    return (
        '    <div class="%s">\n'
        '      <div class="nm"><span class="txt">%s</span>%s</div>\n'
        '      <div class="notes">%s%s</div>\n'
        "    </div>\n"
    ) % (cls, esc(it["name"]), won, proc, esc(it.get("notes", "")))


def order_for_grid(items, cols):
    """세로로 읽히게: 좌측 절반을 먼저 채우도록 row-major 그리드용으로 재배열."""
    if cols < 2:
        return [(it, i == 0) for i, it in enumerate(items)]
    half = (len(items) + 1) // 2
    left, right = items[:half], items[half:]
    out = []
    for i in range(half):
        out.append((left[i], i == 0))
        if i < len(right):
            out.append((right[i], i == 0))
    return out


def render_page(page, brand, page_no, page_total):
    cols = page.get("columns", 1)
    parts = []
    cls = ""
    if page.get("big_items"):
        cls += " big"
    if page.get("fill"):
        cls += " fill"
    parts.append('<section class="page%s">\n' % cls)
    parts.append('  <div class="site">%s</div>\n' % esc(brand["site"]))
    parts.append('  <div class="head">\n')
    parts.append(
        '    <h1>%s<span class="ko">%s</span></h1>\n'
        % (esc(page["title_en"]), esc(page["title_ko"]))
    )
    tag = esc(brand["tagline"])
    if "," in tag:
        left, _, right = tag.partition(",")
        tag = "%s, <b>%s</b>" % (left, right.strip())
    parts.append('    <p class="tag">%s</p>\n' % tag)
    parts.append("  </div>\n  <div class=\"rule\"></div>\n")

    for sec in page["sections"]:
        parts.append('\n  <div class="sect">\n')
        parts.append("    <h2>%s</h2>\n" % esc(sec["heading"]))
        if sec.get("sub"):
            parts.append('    <div class="sub">%s</div>\n' % esc(sec["sub"]))
        if sec.get("price_note"):
            parts.append(
                '    <div class="price">%s <span class="unit">원</span></div>\n'
                % esc(sec["price_note"])
            )
        parts.append("  </div>\n")
        parts.append('  <div class="grid%s">\n' % ("" if cols >= 2 else " one"))
        for it, is_top in order_for_grid(sec["items"], cols):
            parts.append(render_item(it, is_top))
        parts.append("  </div>\n")

    if page.get("note"):
        parts.append('\n  <div class="note">%s</div>\n' % page["note"])

    if not page.get("fill"):
        parts.append('\n  <div class="spacer"></div>\n')
    parts.append('  <div class="foot">\n')
    parts.append('    <div class="logo">\n')
    parts.append('      <img src="../img/logo-92black.png" alt="92도씨 로스터리">\n')
    parts.append('      <div class="han">%s</div>\n' % esc(brand["handle"]))
    parts.append("    </div>\n")
    parts.append('    <div class="msg">%s</div>\n' % page["footer"])
    parts.append('    <div class="pg">%d / %d</div>\n' % (page_no, page_total))
    parts.append("  </div>\n</section>\n")
    return "".join(parts)


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    brand = data["brand"]
    pages = data["pages"]
    body = "\n".join(
        render_page(p, brand, i + 1, len(pages)) for i, p in enumerate(pages)
    )
    doc = (
        '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        "<title>92도씨 커피 메뉴 (A4 %d장)</title>\n"
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900'
        '&family=Oswald:wght@500;600;700&display=swap" rel="stylesheet">\n'
        "<style>%s</style>\n</head>\n<body>\n\n%s\n</body>\n</html>\n"
    ) % (len(pages), CSS, body)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    total = sum(len(s["items"]) for p in pages for s in p["sections"])
    print("[OK] %s — %d쪽, %d종" % (OUT.relative_to(ROOT), len(pages), total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
