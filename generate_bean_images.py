import json
import os
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent
JSON_PATH = BASE_DIR / "coffee_beans.json"
OUTPUT_DIR = BASE_DIR / "bean_images"

IMG_SIZE = 500
MARGIN = 24
BG_COLOR = (255, 248, 240)
ACCENT_COLOR = (230, 126, 34)
TITLE_COLOR = (40, 30, 20)
TEXT_COLOR = (80, 60, 40)
NOTE_BG = (255, 236, 217)

FONT_REGULAR: str | None = None
FONT_BOLD: str | None = None

_FONT_CANDIDATES = {
    True: [
        "C:/Windows/Fonts/malgunbd.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.otc",
    ],
    False: [
        "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otc",
    ],
}


def _find_font(bold: bool) -> str:
    for p in _FONT_CANDIDATES[bold]:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "한글 TrueType 폰트를 찾을 수 없습니다. (Windows: malgun.ttf, "
        "Linux: apt install fonts-nanum 또는 fonts-noto-cjk)"
    )


def _ensure_fonts() -> None:
    global FONT_REGULAR, FONT_BOLD
    if FONT_REGULAR is None:
        FONT_REGULAR = _find_font(False)
    if FONT_BOLD is None:
        FONT_BOLD = _find_font(True)


def safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "", name).replace(" ", "_")


def wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= max_w:
            cur += ch
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def fit_font(text: str, font_path: str, max_w: int, max_h: int, max_size: int,
             draw: ImageDraw.ImageDraw, min_size: int = 14, line_gap: float = 1.15) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(font_path, size)
        lines = wrap(text, font, max_w, draw)
        line_h = int(size * line_gap)
        total_h = line_h * len(lines)
        if total_h <= max_h:
            return font, lines, line_h
    font = ImageFont.truetype(font_path, min_size)
    lines = wrap(text, font, max_w, draw)
    return font, lines, int(min_size * line_gap)


def fit_chips(notes: list[str], font_path: str, max_w: int, max_h: int, max_size: int,
              draw: ImageDraw.ImageDraw, min_size: int = 14) -> tuple[ImageFont.FreeTypeFont, list[list[tuple[str, float]]], int, int, int]:
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(font_path, size)
        pad_x = max(10, size // 2)
        chip_h = size + 14
        gap = 8
        rows: list[list[tuple[str, float]]] = [[]]
        row_w = 0.0
        for n in notes:
            w = draw.textlength(n, font=font) + pad_x * 2
            if rows[-1] and row_w + gap + w > max_w:
                rows.append([])
                row_w = 0.0
            if rows[-1]:
                row_w += gap
            rows[-1].append((n, w))
            row_w += w
        total_h = len(rows) * chip_h + (len(rows) - 1) * gap
        if total_h <= max_h and all(row_w_ok(r, max_w, gap) for r in rows):
            return font, rows, chip_h, gap, pad_x
    font = ImageFont.truetype(font_path, min_size)
    return fit_chips_fallback(notes, font, max_w, draw, min_size)


def row_w_ok(row: list[tuple[str, float]], max_w: int, gap: int) -> bool:
    total = sum(w for _, w in row) + gap * (len(row) - 1)
    return total <= max_w


def fit_chips_fallback(notes, font, max_w, draw, size):
    pad_x, chip_h, gap = 10, size + 14, 8
    rows, row_w = [[]], 0.0
    for n in notes:
        w = draw.textlength(n, font=font) + pad_x * 2
        if rows[-1] and row_w + gap + w > max_w:
            rows.append([])
            row_w = 0.0
        if rows[-1]:
            row_w += gap
        rows[-1].append((n, w))
        row_w += w
    return font, rows, chip_h, gap, pad_x


def draw_card(country: str, bean: str, notes: list[str]) -> Image.Image:
    _ensure_fonts()
    img = Image.new("RGB", (IMG_SIZE, IMG_SIZE), BG_COLOR)
    draw = ImageDraw.Draw(img)

    inner_w = IMG_SIZE - MARGIN * 2

    header_h = 90
    draw.rectangle([(0, 0), (IMG_SIZE, header_h)], fill=ACCENT_COLOR)
    country_font, country_lines, country_lh = fit_font(
        country, FONT_BOLD, inner_w, header_h - 20, 52, draw, min_size=28
    )
    ch_total = country_lh * len(country_lines)
    cy = (header_h - ch_total) // 2
    for line in country_lines:
        lw = draw.textlength(line, font=country_font)
        draw.text(((IMG_SIZE - lw) // 2, cy), line, font=country_font, fill="white")
        cy += country_lh

    label_font = ImageFont.truetype(FONT_BOLD, 18)
    label_h = 26

    bottom_margin = MARGIN
    notes_block_max_h = 170
    notes_font, note_rows, chip_h, chip_gap, pad_x = fit_chips(
        notes, FONT_REGULAR, inner_w, notes_block_max_h, 26, draw, min_size=14
    )
    notes_h = len(note_rows) * chip_h + (len(note_rows) - 1) * chip_gap

    notes_top = IMG_SIZE - bottom_margin - notes_h
    label_y = notes_top - label_h - 4
    divider_y = label_y - 14

    bean_area_top = header_h + MARGIN
    bean_area_h = divider_y - bean_area_top - 10
    bean_font, bean_lines, bean_lh = fit_font(
        bean, FONT_BOLD, inner_w, bean_area_h, 40, draw, min_size=20, line_gap=1.25
    )
    bh_total = bean_lh * len(bean_lines)
    by = bean_area_top + (bean_area_h - bh_total) // 2
    for line in bean_lines:
        lw = draw.textlength(line, font=bean_font)
        draw.text(((IMG_SIZE - lw) // 2, by), line, font=bean_font, fill=TITLE_COLOR)
        by += bean_lh

    draw.line([(MARGIN, divider_y), (IMG_SIZE - MARGIN, divider_y)], fill=ACCENT_COLOR, width=2)

    draw.text((MARGIN, label_y), "CUP NOTES", font=label_font, fill=ACCENT_COLOR)

    y = notes_top
    for row in note_rows:
        row_total = sum(w for _, w in row) + chip_gap * (len(row) - 1)
        x = (IMG_SIZE - row_total) // 2
        for text, w in row:
            draw.rounded_rectangle(
                [(x, y), (x + w, y + chip_h)],
                radius=chip_h // 2, fill=NOTE_BG, outline=ACCENT_COLOR, width=1,
            )
            tw = draw.textlength(text, font=notes_font)
            ty = y + (chip_h - notes_font.size) // 2 - 2
            draw.text((x + (w - tw) // 2, ty), text, font=notes_font, fill=TEXT_COLOR)
            x += w + chip_gap
        y += chip_h + chip_gap

    return img


def render_card_for_coffee(item: dict) -> Image.Image:
    """DB 아이템(한글 키 또는 영문 키)에서 카드 이미지를 만든다.

    헤더(주황 띠)는 원두 이름의 첫 단어(국가/구분), 그 외는 본문 큰 글씨.
    공백이 없으면 로스터리를 헤더로 폴백한다. 컵노트는 콤마로 분리해 칩으로.
    """
    name = (item.get("커피") or item.get("name") or "").strip()
    notes_raw = (item.get("컵노트") or item.get("cup_notes") or "").strip()
    notes = [n.strip() for n in notes_raw.split(",") if n.strip()]
    parts = name.split(maxsplit=1)
    if len(parts) == 2:
        country, bean = parts[0], parts[1]
    else:
        country = (item.get("로스터리") or item.get("roastery") or "92도씨 로스터리").strip()
        bean = name or "이름 없음"
    return draw_card(country, bean, notes)


def main() -> None:
    with open(JSON_PATH, encoding="utf-8") as f:
        beans = json.load(f)
    OUTPUT_DIR.mkdir(exist_ok=True)

    for idx, item in enumerate(beans, 1):
        country, bean, notes = item["나라"], item["원두"], item["컵노트"]
        img = draw_card(country, bean, notes)
        base = f"{idx:02d}_{safe_filename(country)}_{safe_filename(bean)}"
        img.save(OUTPUT_DIR / f"{base}.png", "PNG")
        img.convert("RGB").save(OUTPUT_DIR / f"{base}.jpg", "JPEG", quality=92)
        print(f"saved: {base}")

    print(f"\ndone: {len(beans) * 2} files -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
