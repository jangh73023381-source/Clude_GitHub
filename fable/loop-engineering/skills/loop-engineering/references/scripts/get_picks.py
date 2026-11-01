#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
get_picks.py — 최신(또는 지정) 데일리브리핑 docx에서 단기 추천 ETF 상위 5종을 추출한다.

대상(보유 ETF) = 가장 최근 아침 브리핑의 단기 추천 ETF 상위 5종.
단기 ETF 표는 헤더에 '순위'와 '매수상단'(매수상단가)을 포함하는 표로 식별한다.

사용:
  python3 get_picks.py                       # 작업 폴더 최신 데일리브리핑_*.docx 자동 선택
  python3 get_picks.py --file <경로>          # 특정 파일 지정
  python3 get_picks.py --dir <폴더> --csv out.csv

출력: 화면 표 + (옵션) CSV(code,name,prev_close) — rank_etf.py의 --picks 입력에 사용.
"""
import argparse, glob, os, re, sys
from docx import Document

def find_latest(d):
    files = sorted(glob.glob(os.path.join(d, "데일리브리핑_*.docx")), key=os.path.getmtime)
    if not files:
        sys.exit(f"데일리브리핑_*.docx 파일을 찾지 못함: {d}")
    return files[-1]

def extract(path):
    doc = Document(path)
    for t in doc.tables:
        hdr = [c.text.strip() for c in t.rows[0].cells]
        if "순위" in hdr and any("매수상단" in h for h in hdr):
            picks = []
            for r in t.rows[1:6]:
                c = [x.text.strip() for x in r.cells]
                code = re.sub(r"\D", "", c[2])[:6].zfill(6)
                prev = re.sub(r"[^\d]", "", c[3])
                picks.append({"rank": c[0], "name": c[1], "code": code, "prev_close": prev})
            return picks
    sys.exit("단기 추천 ETF 표(헤더에 '순위'·'매수상단')를 찾지 못함.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--csv")
    a = ap.parse_args()
    path = a.file or find_latest(a.dir)
    picks = extract(path)
    print(f"소스: {os.path.basename(path)}")
    print("대상(단기 추천 ETF 상위 5종):")
    for p in picks:
        print(f"  {p['rank']}위 {p['name']} ({p['code']}) 전일종가 {int(p['prev_close']):,}")
    print("picks 인자:", ",".join(p["code"] for p in picks))
    if a.csv:
        import csv
        with open(a.csv, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f); w.writerow(["code", "name", "prev_close"])
            for p in picks: w.writerow([p["code"], p["name"], p["prev_close"]])
        print("CSV 저장:", a.csv)

if __name__ == "__main__":
    main()
