#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rule USX 검정용 미국 테마 지수 일별 종가 수집 (조회 전용).
선정 시각 T 06:00 KST 에 확보 가능한 것은 '미국 날짜 = D' 세션이다(05:00 KST 마감).
"""
import os, sys, time
import yfinance as yf
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'us_theme_close.csv')
TICK = {
    'SOX': 'SOXX', 'BIO': 'IBB', 'SOLAR': 'TAN', 'DEF': 'ITA', 'BATT': 'LIT',
    'ROBO': 'BOTZ', 'GOLD': 'GLD', 'SPY': 'SPY', 'QQQ': 'QQQ', 'CHINA': 'FXI',
    'NUKE': 'URA', 'BANK': 'KBE', 'AUTO': 'CARZ', 'COS': 'XLP', 'CONS': 'PAVE',
}
rows = []
for th, tk in TICK.items():
    for attempt in range(3):
        try:
            df = yf.Ticker(tk).history(start='2019-03-01', end='2026-08-21', auto_adjust=False)
            if len(df) > 100:
                break
        except Exception as e:
            print('  retry', tk, e)
        time.sleep(2)
    if df is None or len(df) < 100:
        print('  [실패]', th, tk); continue
    for dt, cl in df['Close'].items():
        if pd.isna(cl):
            continue
        rows.append((th, tk, dt.strftime('%Y%m%d'), float(cl)))
    print('  [OK]', th, tk, len(df), df.index[0].date(), df.index[-1].date())
    time.sleep(1)

import csv
with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['theme', 'ticker', 'date', 'close']); w.writerows(rows)
print('rows', len(rows), '->', OUT)
