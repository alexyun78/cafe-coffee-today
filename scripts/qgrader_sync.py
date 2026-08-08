#!/usr/bin/env python3
"""Q 그레이더 학습플랜(md) → D1 seed SQL 생성기.

  python scripts/qgrader_sync.py                 # scripts/qgrader_seed.sql 생성
  python scripts/qgrader_sync.py --print         # 파싱 결과만 확인

커리큘럼 계열 테이블(qg_curriculum·qg_roadmap·qg_targets·qg_routine_items·qg_reference)만
지우고 다시 채운다. 사용자가 쌓는 qg_logs·qg_routine_checks·qg_settings 는 건드리지 않는다.
루틴 항목 id 는 label 해시라서 md 를 고쳐도 같은 항목이면 체크 이력이 유지된다.

적용:
  cd worker && node_modules/.bin/wrangler d1 execute cafe-coffee --remote \
      --file ../scripts/qgrader_seed.sql
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD_PATH = os.path.join(ROOT, "content", "qgrader", "study-plan.md")
OUT_PATH = os.path.join(ROOT, "scripts", "qgrader_seed.sql")
SOURCE_LABEL = "content/qgrader/study-plan.md"


# ---------------- markdown 유틸 ----------------

def split_sections(md: str) -> list[tuple[str, str]]:
    """(heading, body) 목록. heading 은 '## …' / '### …' 원문."""
    out, cur, buf = [], None, []
    for line in md.splitlines():
        if line.startswith("## "):
            if cur is not None:
                out.append((cur, "\n".join(buf)))
            cur, buf = line.strip(), []
        else:
            buf.append(line)
    if cur is not None:
        out.append((cur, "\n".join(buf)))
    return out


def find_section(sections, *keywords):
    for head, body in sections:
        if all(k in head for k in keywords):
            return head, body
    return None, ""


def parse_tables(body: str) -> list[list[dict]]:
    """body 안의 마크다운 표들을 순서대로 [ {헤더: 값}, ... ] 로."""
    tables, rows, header = [], [], None
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s[1:-1].split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                continue                       # 구분선
            if header is None:
                header = cells
            else:
                rows.append(dict(zip(header, cells)))
        else:
            if header is not None and rows:
                tables.append(rows)
            header, rows = None, []
    if header is not None and rows:
        tables.append(rows)
    return tables


def parse_bullets(body: str) -> list[str]:
    return [re.sub(r"^[-*]\s+", "", l.strip())
            for l in body.splitlines()
            if re.match(r"^[-*]\s+", l.strip())]


def strip_md(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", s)
    return s.strip()


# ---------------- 도메인 파싱 ----------------

MONTH_RE = re.compile(r"(\d{1,2})월")


def roadmap_rows(sections, base_year: int):
    _, body = find_section(sections, "6개월 로드맵")
    tables = parse_tables(body)
    if not tables:
        return []
    out, year, prev_m = [], base_year, 0
    for i, r in enumerate(tables[0]):
        period = r.get("기간", "")
        m = MONTH_RE.search(period)
        if not m:
            continue
        mm = int(m.group(1))
        if prev_m and mm < prev_m:
            year += 1
        prev_m = mm
        label = re.search(r"\((M\d)\)", period)
        out.append({
            "month": "%04d-%02d" % (year, mm),
            "label": label.group(1) if label else "",
            "period": period,
            "theme": r.get("테마", ""),
            "activities": r.get("핵심 활동", ""),
            "goal": r.get("월말 목표", ""),
            "sort_order": i,
        })
    return out


TARGET_PATTERNS = [
    ("aroma",   re.compile(r"아로마\s*(\d+)\s*/\s*36"),            lambda v: float(v)),
    ("acid",    re.compile(r"유기산\s*(\d+)\s*%"),                 lambda v: float(v)),
    ("tri",     re.compile(r"삼각\s*(\d+)\s*%"),                   lambda v: round(6 * float(v) / 100, 1)),
    ("defect",  re.compile(r"결함\s*분류\s*정확도\s*(\d+)\s*%"),    lambda v: float(v)),
    ("written", re.compile(r"모의\s*필기\s*(\d+)\s*점"),            lambda v: float(v)),
]


def target_rows(roadmap):
    out = []
    for r in roadmap:
        for metric, pat, conv in TARGET_PATTERNS:
            m = pat.search(r["goal"])
            if m:
                out.append({"metric": metric, "month": r["month"],
                            "value": conv(m.group(1)), "note": r["goal"]})
    return out


CADENCE_RE = re.compile(r"^\*\*(.+?)\*\*\s*[—-]\s*(.+)$")


def routine_rows(sections):
    _, body = find_section(sections, "훈련 루틴")
    out, order = [], 0
    for b in parse_bullets(body):
        m = CADENCE_RE.match(b)
        if not m:
            continue
        head, rest = m.group(1).strip(), m.group(2).strip()
        name, _, detail = rest.partition(":")
        name, detail = name.strip(), detail.strip()
        daily = head.startswith("매일")
        times = 1
        wm = re.search(r"주\s*(\d+)\s*회", head)
        if wm:
            times = int(wm.group(1))
        for n in range(times):
            label = name if times == 1 else "%s %d회차" % (name, n + 1)
            if daily:
                label = "%s (%s)" % (name, head.replace("매일 ", "").strip())
            out.append({
                "id": int(hashlib.sha1(label.encode("utf-8")).hexdigest()[:7], 16),
                "label": label,
                "cadence": "daily" if daily else "weekly",
                "detail": detail,
                "sort_order": order,
            })
            order += 1
    return out


def reference_rows(sections):
    out = []

    def add(section, rows):
        for i, r in enumerate(rows):
            out.append({"section": section, "sort_order": i, "data": r})

    _, exam = find_section(sections, "한눈에 보기")
    tbls = parse_tables(exam)
    if tbls:
        add("exam", tbls[0])
    if len(tbls) > 1:                       # ### 실기 8개 평가 컴포넌트 (같은 ## 블록 안)
        add("components", tbls[1])

    _, mat = find_section(sections, "준비물")
    if parse_tables(mat):
        add("materials", parse_tables(mat)[0])

    _, acid = find_section(sections, "유기산")
    at = parse_tables(acid)
    if at:
        add("acids", at[0])
    if len(at) > 1:
        add("dilution", at[1])

    _, todo = find_section(sections, "바로 할 일")
    add("todo", [{"task": strip_md(re.sub(r"^\[[ x]\]\s*", "", b))} for b in parse_bullets(todo)])

    _, links = find_section(sections, "참고 자료")
    rows = []
    for b in parse_bullets(links):
        m = re.match(r"^(.+?):\s*(https?://\S+)$", b.strip())
        rows.append({"label": m.group(1).strip(), "url": m.group(2)} if m
                    else {"label": strip_md(b), "url": ""})
    add("links", rows)
    return out


# ---------------- SQL 출력 ----------------

def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def build_sql(md: str, data: dict) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    version = hashlib.sha1(md.encode("utf-8")).hexdigest()[:12]
    L = ["-- 자동 생성: scripts/qgrader_sync.py — 직접 수정하지 말 것",
         "-- 원본: %s (version %s)" % (SOURCE_LABEL, version),
         "",
         "DELETE FROM qg_roadmap;",
         "DELETE FROM qg_targets;",
         "DELETE FROM qg_routine_items;",
         "DELETE FROM qg_reference;",
         ""]

    title = md.splitlines()[0].lstrip("# ").strip()
    L.append("INSERT OR REPLACE INTO qg_curriculum (version, source, title, body_md, created_at) "
             "VALUES (%s, %s, %s, %s, %s);" % (q(version), q(SOURCE_LABEL), q(title), q(md), q(now)))
    L.append("")

    for r in data["roadmap"]:
        L.append("INSERT INTO qg_roadmap (month,label,period,theme,activities,goal,sort_order) VALUES (%s);"
                 % ",".join(q(r[k]) for k in
                            ("month", "label", "period", "theme", "activities", "goal", "sort_order")))
    L.append("")
    for r in data["targets"]:
        L.append("INSERT INTO qg_targets (metric,month,value,note) VALUES (%s);"
                 % ",".join(q(r[k]) for k in ("metric", "month", "value", "note")))
    L.append("")
    for r in data["routine"]:
        L.append("INSERT INTO qg_routine_items (id,label,cadence,detail,sort_order,active) VALUES (%s,1);"
                 % ",".join(q(r[k]) for k in ("id", "label", "cadence", "detail", "sort_order")))
    L.append("")
    for r in data["reference"]:
        L.append("INSERT INTO qg_reference (section,sort_order,data) VALUES (%s,%s,%s);"
                 % (q(r["section"]), q(r["sort_order"]),
                    q(json.dumps(r["data"], ensure_ascii=False))))
    L.append("")
    # 시험일 기본값 — 이미 있으면 사용자가 바꾼 값 유지
    L.append("INSERT OR IGNORE INTO qg_settings (key,value,updated_at) VALUES ('exam_date','2027-02-01',%s);" % q(now))
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", dest="dump")
    a = ap.parse_args()

    md = open(MD_PATH, encoding="utf-8").read()
    sections = split_sections(md)
    base_year = int(re.search(r"(\d{4})년", md).group(1))

    roadmap = roadmap_rows(sections, base_year)
    data = {
        "roadmap": roadmap,
        "targets": target_rows(roadmap),
        "routine": routine_rows(sections),
        "reference": reference_rows(sections),
    }

    if a.dump:
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return

    sql = build_sql(md, data)
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(sql)
    print("생성: %s" % OUT_PATH)
    print("  로드맵 %d · 목표 %d · 루틴 %d · 참고 %d행"
          % (len(data["roadmap"]), len(data["targets"]),
             len(data["routine"]), len(data["reference"])))
    secs = {}
    for r in data["reference"]:
        secs[r["section"]] = secs.get(r["section"], 0) + 1
    print("  참고 섹션:", ", ".join("%s=%d" % kv for kv in secs.items()))


if __name__ == "__main__":
    main()
