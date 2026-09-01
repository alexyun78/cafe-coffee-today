# -*- coding: utf-8 -*-
"""원두 카드를 A4 세로 인쇄용 시트로 만든다.

static/beans/index.json 하나만 읽어서 자르기 좋은 격자 HTML 을 뽑는다.
브라우저에서 열고 Ctrl+P → 대상 A4, 배율 100%, 여백 없음 으로 인쇄하면 된다.

    python scripts/build_bean_print.py                 # 기본 3열 x 4행 (12장/쪽)
    python scripts/build_bean_print.py --cols 4 --rows 5
    python scripts/build_bean_print.py --out build/cards.html --no-cut-lines

카드 크기는 A4(210x297mm)에서 여백과 간격을 뺀 값으로 자동 계산된다.
기본값 3x4 는 한 장이 약 62 x 68mm 로, 명함(90x50mm)보다 조금 크다.
"""
import argparse
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
DEFAULT_IN = os.path.join(ROOT, 'static', 'beans', 'index.json')
DEFAULT_OUT = os.path.join(ROOT, 'static', 'beans', 'print.html')

A4_W, A4_H = 210.0, 297.0

# 카드에 넣을 항목과 라벨 — 값이 없으면 그 줄은 빠진다.
SPEC_FIELDS = [
    ('farm', '농장'),
    ('variety', '품종'),
    ('process', '가공'),
    ('altitude', '고도'),
    ('region', '지역'),
]


def esc(s):
    return html.escape(str(s if s is not None else ''), quote=True)


def spec_limit(card_h):
    """카드 높이에 맞춰 넣을 수 있는 정보 줄 수."""
    if card_h >= 62:
        return 5
    if card_h >= 52:
        return 4
    return 3


def card_html(bean, limit, show_en, show_line):
    specs = []
    for key, label in SPEC_FIELDS:
        value = bean.get(key)
        if value:
            specs.append((label, value))
    specs = specs[:limit]

    notes = bean.get('cup_notes') or []
    if not isinstance(notes, list):
        notes = [notes]

    rows = ''.join(
        '<div class="spec"><span class="k">%s</span><span class="v">%s</span></div>' % (esc(k), esc(v))
        for k, v in specs
    )
    en = ''
    if show_en and bean.get('name_en'):
        en = '<div class="en">%s</div>' % esc(bean['name_en'])

    note_block = ''
    if notes:
        note_block = (
            '<div class="notes"><span class="nk">컵노트</span>'
            '<span class="nv">%s</span></div>' % esc(', '.join(notes))
        )

    line = ''
    if show_line and bean.get('one_liner'):
        line = '<p class="line">%s</p>' % esc(bean['one_liner'])

    return (
        '<article class="card">'
        '<div class="top">'
        '<div class="country">%s</div>'
        '<div class="name">%s</div>'
        '%s'
        '</div>'
        '<div class="mid">%s%s</div>'
        '<div class="bot">%s<div class="brand">92<span>°C</span> ROASTERY</div></div>'
        '</article>'
    ) % (esc(bean.get('country') or 'GREEN BEAN'), esc(bean.get('name_ko')), en, rows, line, note_block)


def build(items, cols, rows, margin, gap, cut_lines, show_en, one_liner):
    card_w = (A4_W - 2 * margin - (cols - 1) * gap) / cols
    card_h = (A4_H - 2 * margin - (rows - 1) * gap) / rows
    limit = spec_limit(card_h)

    # 기본 치수(3열 4행, 62.7 x 68.0mm)를 1.0 으로 두고 글자 크기를 비례 조정한다.
    scale = min(card_w / 62.7, card_h / 68.0)
    scale = max(0.62, min(1.15, scale))

    per_page = cols * rows
    pages = [items[i:i + per_page] for i in range(0, len(items), per_page)] or [[]]

    # 한 줄 소개는 카드가 충분히 클 때만 넣는다 (작은 격자에서는 넘친다).
    show_line = one_liner and card_h >= 62

    body = []
    for page in pages:
        body.append('<section class="sheet">%s</section>' %
                    ''.join(card_html(b, limit, show_en, show_line) for b in page))

    css = CSS % {
        'margin': margin,
        'gap': gap,
        'cols': cols,
        'card_w': round(card_w, 2),
        'card_h': round(card_h, 2),
        'border': '0.2mm dashed #b9b0a4' if cut_lines else '0.2mm solid transparent',
        'f_country': round(5.2 * scale, 2),
        'f_name': round(8.6 * scale, 2),
        'f_en': round(5.4 * scale, 2),
        'f_spec': round(6.0 * scale, 2),
        'f_note': round(6.4 * scale, 2),
        'f_brand': round(4.8 * scale, 2),
        'f_line': round(6.1 * scale, 2),
        'pad': round(3.6 * scale, 2),
    }
    return HTML % {'css': css, 'body': ''.join(body), 'count': len(items),
                   'pages': len(pages)}, card_w, card_h, len(pages)


CSS = """
@page { size: A4 portrait; margin: %(margin)smm; }

* { box-sizing: border-box; }

html, body {
    margin: 0;
    padding: 0;
    background: #f4f1ec;
    font-family: 'Pretendard', 'Malgun Gothic', '맑은 고딕', 'Apple SD Gothic Neo', sans-serif;
    color: #241c16;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}

.sheet {
    width: %(card_w)smm;
    width: auto;
    display: grid;
    grid-template-columns: repeat(%(cols)s, %(card_w)smm);
    gap: %(gap)smm;
    justify-content: center;
    align-content: start;
    break-after: page;
    page-break-after: always;
}
.sheet:last-child { break-after: auto; page-break-after: auto; }

.card {
    width: %(card_w)smm;
    height: %(card_h)smm;
    padding: %(pad)smm;
    border: %(border)s;
    border-radius: 1.6mm;
    background: #fff;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    break-inside: avoid;
    page-break-inside: avoid;
}

.country {
    font-size: %(f_country)spt;
    letter-spacing: 0.09em;
    color: #a8622b;
    font-weight: 700;
    margin-bottom: 0.6mm;
}

.name {
    font-size: %(f_name)spt;
    font-weight: 700;
    line-height: 1.28;
    letter-spacing: -0.01em;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.en {
    margin-top: 0.6mm;
    font-size: %(f_en)spt;
    line-height: 1.25;
    color: #9a9086;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.mid {
    flex: 1;
    margin-top: 1.8mm;
    padding-top: 1.6mm;
    border-top: 0.18mm solid #e4ded5;
    display: flex;
    flex-direction: column;
    gap: 0.5mm;
    overflow: hidden;
}

.spec { display: flex; gap: 1.4mm; font-size: %(f_spec)spt; line-height: 1.3; }
.spec .k { flex: none; width: 8mm; color: #a89e93; }
.spec .v {
    flex: 1;
    color: #3b322a;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.line {
    margin: 1.8mm 0 0;
    padding-top: 1.6mm;
    border-top: 0.18mm solid #f0ebe3;
    font-size: %(f_line)spt;
    line-height: 1.4;
    color: #6b6055;
    display: -webkit-box;
    -webkit-line-clamp: 4;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.bot { margin-top: 1.4mm; }

.notes {
    padding: 1.2mm 1.4mm;
    border-radius: 1mm;
    background: #f6f1e9;
    font-size: %(f_note)spt;
    line-height: 1.32;
}
.notes .nk { color: #a8622b; font-weight: 700; margin-right: 1.2mm; }
.notes .nv {
    color: #2c241d;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.brand {
    margin-top: 1.2mm;
    font-size: %(f_brand)spt;
    letter-spacing: 0.14em;
    color: #b3a99d;
    text-align: right;
}
.brand span { color: #c2793c; }

@media screen {
    body { padding: 10mm 0; }
    .sheet {
        width: 210mm;
        min-height: 297mm;
        margin: 0 auto 10mm;
        padding: %(margin)smm;
        background: #fff;
        box-shadow: 0 2px 14px rgba(0, 0, 0, 0.14);
    }
}
@media print {
    body { background: #fff; padding: 0; }
    .sheet { box-shadow: none; margin: 0; padding: 0; }
}
"""

HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>원두 카드 인쇄 — 92°C ROASTERY</title>
<style>%(css)s</style>
</head>
<body>
%(body)s
<!-- 원두 %(count)s종 / %(pages)s쪽 -->
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description='원두 카드 A4 인쇄 시트 생성')
    ap.add_argument('--cols', type=int, default=3, help='가로 장수 (기본 3)')
    ap.add_argument('--rows', type=int, default=4, help='세로 장수 (기본 4)')
    ap.add_argument('--margin', type=float, default=8.0, help='용지 여백 mm (기본 8)')
    ap.add_argument('--gap', type=float, default=3.0, help='카드 간격 mm (기본 3)')
    ap.add_argument('--input', default=DEFAULT_IN, help='원두 index.json 경로')
    ap.add_argument('--out', default=DEFAULT_OUT, help='출력 HTML 경로')
    ap.add_argument('--no-cut-lines', action='store_true', help='자르는 선 숨김')
    ap.add_argument('--no-en', action='store_true', help='영문명 숨김')
    ap.add_argument('--no-one-liner', action='store_true', help='한 줄 소개 숨김')
    args = ap.parse_args()

    if not 1 <= args.cols <= 6 or not 1 <= args.rows <= 8:
        raise SystemExit('cols 는 1~6, rows 는 1~8 범위로 지정하세요.')

    with open(args.input, encoding='utf-8') as f:
        items = json.load(f).get('items', [])
    if not items:
        raise SystemExit('원두가 없습니다: %s' % args.input)

    doc, card_w, card_h, pages = build(
        items, args.cols, args.rows, args.margin, args.gap,
        not args.no_cut_lines, not args.no_en, not args.no_one_liner,
    )

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(doc)

    print('원두 %d종 → %s' % (len(items), os.path.relpath(args.out, ROOT).replace(os.sep, '/')))
    print('카드 %.1f x %.1fmm, %d열 %d행, %d장/쪽, 총 %d쪽'
          % (card_w, card_h, args.cols, args.rows, args.cols * args.rows, pages))
    print('브라우저에서 열고 인쇄 → 용지 A4, 배율 100%, 여백 없음')


if __name__ == '__main__':
    main()
