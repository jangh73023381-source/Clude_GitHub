# -*- coding: utf-8 -*-
"""공개 채널용 요약 카드 이미지(PNG) — 2026-10-28 사용자 지시: "텔레그램에는 요약 정리 그림만 올려줘".

  python3 references/scripts/public_card.py --date 20261028   # fable/공개/요약카드_YYYY-MM-DD.png

- 입력은 public_post.py 와 같다: watch_plan_<T>.json + lv_oos_tracker.csv + mid_momentum_shadow.csv. **선정 재계산 없음.**
- 공개본 원칙 그대로: 트랙 D 보유·평가손익·내부 용어·회사 결재를 넣지 않는다. **면책 고지는 그림 하단에 반드시 넣는다.**
- 조회·게시 전용. 주문 기능 없음.
"""
import csv, json, os, sys
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import public_post as pp  # noqa: E402

FR = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
FB = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
R = fm.FontProperties(fname=FR) if os.path.exists(FR) else None
B = fm.FontProperties(fname=FB) if os.path.exists(FB) else R

BG, FG, MUTED, LINE = '#f6f7f5', '#17201b', '#5d6a62', '#dfe4e0'
ACC, WARN, WARNBG, OKBG, MID = '#1f6f54', '#b3402a', '#fbe9e4', '#e4f2ea', '#b07a1e'
SPC = '#3b5ba5'  # S&P500 선(2026-10-28 추가)


def series():
    """누적 지수(시작=100) — public_post.perf() 와 같은 구간·같은 가정."""
    rows = [r for r in csv.DictReader(open(os.path.join(pp.LOOP, 'references', 'lv_oos_tracker.csv'), encoding='utf-8'))
            if r.get('lv_ret') not in ('', None)]
    mm = {r['date']: float(r['mom150_ret']) for r in csv.DictReader(
        open(os.path.join(pp.LOOP, 'references', 'mid_momentum_shadow.csv'), encoding='utf-8'))
        if r.get('status') == 'scored' and r.get('mom150_ret') not in ('', None)}
    lv, bm, mid = [100.0], [100.0], [100.0]
    for r in rows:
        lv.append(lv[-1] * (1 + float(r['lv_ret']) / 100))
        bm.append(bm[-1] * (1 + float(r['bench_ret']) / 100))
        mid.append(mid[-1] * (1 + mm.get(r['date'], 0.0) / 100))
    sp = sp500_line(rows)
    return rows[0]['date'], rows[-1]['date'], lv, mid, bm, sp


SP_CACHE = os.path.join(pp.LOOP, 'backtest', '_sp500_close_cache.csv')


def _sp500_closes():
    """S&P500(^GSPC) 일별 종가 {YYYYMMDD: close} — Yahoo chart API(User-Agent 필수) 조회 후 캐시에 멱등 보충.
    조회 실패 시 캐시만 쓴다. 2026-10-28 사용자 지시("성과공개 그래프에 S&P500 도 포함")."""
    import urllib.request
    from datetime import timezone, timedelta
    cache = {}
    if os.path.exists(SP_CACHE):
        cache = {r['date']: float(r['close']) for r in csv.DictReader(open(SP_CACHE, encoding='utf-8'))}
    try:
        u = 'https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=1y&interval=1d'
        j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=15))
        res = j['chart']['result'][0]
        off = res['meta'].get('gmtoffset', 0)
        now_ny = datetime.now(timezone.utc) + timedelta(seconds=off)
        for ts, c in zip(res['timestamp'], res['indicators']['quote'][0]['close']):
            d = (datetime.fromtimestamp(ts, timezone.utc) + timedelta(seconds=off))
            # 미확정 봉 유입 금지 — 미국 장 마감(16:00 현지) 전의 당일 봉은 쓰지 않는다
            if c is None or (d.date() == now_ny.date() and now_ny.hour < 16):
                continue
            cache[d.strftime('%Y%m%d')] = round(float(c), 2)
        with open(SP_CACHE, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f); w.writerow(['date', 'close'])
            for k in sorted(cache):
                w.writerow([k, cache[k]])
    except Exception as e:  # noqa: BLE001
        print(f'  [S&P500] 조회 실패 — 캐시 사용: {type(e).__name__}')
    return cache


def sp500_line(rows):
    """단기·KODEX200 선과 같은 점(시작 + 채점일별)에 S&P500 누적 지수를 맞춘다.
    한국 채점일 d 의 값 = d 이전(미만) 마지막 미국 종가 — 한국 d 개장 전에 끝난 미국장까지 반영. 달러 지수 기준(환율 미반영)."""
    try:
        px = _sp500_closes()
        if not px:
            return None
        import ensure_data
        last = str(ensure_data.panel_last_date(ensure_data.newest_panel()))
        pts = [rows[0]['date']] + [r['date'] for r in rows[1:]] + [last]
        ks = sorted(px)

        def at(d):
            c = [k for k in ks if k < d]
            return px[c[-1]] if c else None
        v = [at(d) for d in pts]
        if None in v:
            return None
        return [x / v[0] * 100 for x in v]
    except Exception as e:  # noqa: BLE001
        print(f'  [S&P500] 계산 실패: {type(e).__name__}: {e}')
        return None


def t(ax, x, y, s, size=11, bold=False, color=FG, ha='left', va='top'):
    ax.text(x, y, s, fontproperties=B if bold else R, fontsize=size, color=color, ha=ha, va=va,
            transform=ax.transAxes)


def build_card(T, out=None):
    wp = json.load(open(os.path.join(pp.LOOP, '장중알림', 'plans', f'watch_plan_{T}.json'), encoding='utf-8'))
    p = pp.perf()
    d = datetime.strptime(T, '%Y%m%d'); wd = '월화수목금토일'[d.weekday()]
    fig = plt.figure(figsize=(9, 12.6), dpi=130, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis('off'); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    L = 0.05
    t(ax, L, 0.975, f"데일리 ETF 브리핑  {d.month}/{d.day}({wd})", 22, True)
    t(ax, L, 0.938, "장전 요약 · 전일 종가 기준 · 자체 규칙 참고 정보", 11, color=MUTED)

    # 모드 띠
    cons = wp['mode'] == '보수'
    ax.add_patch(plt.Rectangle((L, 0.862), 0.90, 0.058, transform=ax.transAxes,
                               facecolor=WARNBG if cons else OKBG, edgecolor='none'))
    ax.add_patch(plt.Rectangle((L, 0.862), 0.008, 0.058, transform=ax.transAxes,
                               facecolor=WARN if cons else ACC, edgecolor='none'))
    if cons:
        t(ax, L + 0.025, 0.910, "보수 모드 — 경고 신호 발동", 13, True, WARN)
        t(ax, L + 0.025, 0.884, "매수상단 전일종가 +0.3% · 금액 평소의 2/3 · 14:30까지 미체결이면 매수하지 않음", 10.5)
    else:
        t(ax, L + 0.025, 0.910, "표준 모드", 13, True, ACC)
        t(ax, L + 0.025, 0.884, "매수상단 전일종가 +0.6% · 미체결 시 종가 무렵 담기 가능", 10.5)

    # 단기 표
    t(ax, L, 0.840, "단기 ETF 5종", 14, True); t(ax, L + 0.19, 0.836, "저변동 정렬 · 하루 보유 후 교체", 10, color=MUTED)
    cols = [("종목", L, 'left'), ("구분", 0.50, 'center'), ("전일종가", 0.60, 'right'), ("매수상단", 0.705, 'right'),
            ("지정가", 0.79, 'right'), ("손절", 0.87, 'right'), ("목표", 0.95, 'right')]
    y = 0.800
    for name, x, ha in cols:
        t(ax, x, y, name, 9.5, True, MUTED, ha=ha)
    ax.plot([L, 0.95], [y - 0.022, y - 0.022], color=LINE, lw=1, transform=ax.transAxes)
    y -= 0.032
    for s in wp['short']:
        nm = s['name'] if len(s['name']) <= 22 else s['name'][:21] + '…'
        t(ax, L, y, nm, 10.5, True); t(ax, L, y - 0.019, s['code'], 8.5, color=MUTED)
        new = s['status'] != '유지'
        t(ax, 0.50, y, s['status'], 10, new, ACC if new else MUTED, ha='center')
        vals = [(f"{s['prev_close']:,.0f}", FG, False), (f"{s['upper']:,}", FG, True), (f"{s['limit']:,}", FG, False),
                (f"{s['stop']:,}", WARN, False), (f"{s['target']:,}", ACC, False)]
        for (v, c, b), x in zip(vals, (0.60, 0.705, 0.79, 0.87, 0.95)):
            t(ax, x, y, v, 10.5, b, c, ha='right')
        y -= 0.047
        ax.plot([L, 0.95], [y + 0.008, y + 0.008], color=LINE, lw=0.6, transform=ax.transAxes)
    sells = wp.get('short_sells') or []
    t(ax, L, y - 0.002, "오늘 종가 교체(제외): " + (", ".join(x['name'] for x in sells) if sells else "없음")
      + "  ·  매수상단 위로 시작하면 쫓지 않음", 9.5, color=MUTED)

    # 중기
    y -= 0.040
    t(ax, L, y, "중기 ETF 5종", 14, True)
    b = wp['mid_band']
    t(ax, L + 0.19, y - 0.004, f"150일 모멘텀 · 종가 무렵 당일 등락 {b[0]:+.1f}%~{b[1]:+.1f}%일 때만", 10, color=MUTED)
    y -= 0.036
    mids = wp['mid']
    for i, m in enumerate(mids):
        cx = L + (i % 2) * 0.45; cy = y - (i // 2) * 0.028
        t(ax, cx, cy, f"· {m['name']}", 10.5); 
    y -= ((len(mids) + 1) // 2) * 0.028
    ms = wp.get('mid_sells') or []
    if ms:
        t(ax, L, y, "추천 제외(종가 청산): " + ", ".join(x['name'] for x in ms), 9.5, color=MUTED)
        y -= 0.026

    # 성과 차트
    y -= 0.016
    t(ax, L, y, "성과 공개", 14, True)
    t(ax, L + 0.15, y - 0.004, f"누적 {p['n']}거래일 · 무비용 가정 · 손실일 포함", 10, color=MUTED)
    y -= 0.036
    s0, s1, lv, mid, bm, sp = series()
    kp = [("단기 5종", p['lv'], ACC), ("중기 5종", p['mid'], MID), ("KODEX200", p['bm'], MUTED),
          ("S&P500(달러)", (sp[-1] - 100) if sp else None, SPC)]
    for i, (nm, v, c) in enumerate(kp):
        if v is None:
            continue
        x = L + i * 0.225
        t(ax, x, y, nm, 10, color=MUTED)
        t(ax, x, y - 0.020, f"{v:+.2f}%", 17, True, c)
    top = y - 0.065
    cax = fig.add_axes([L + 0.04, 0.125, 0.86, max(0.10, top - 0.125)], facecolor=BG)
    xs = range(len(lv))
    cax.plot(xs, bm, color=MUTED, lw=1.4, ls='--', label='KODEX200')
    if sp and len(sp) == len(lv):
        cax.plot(xs, sp, color=SPC, lw=1.4, ls=':', label='S&P500')
    cax.plot(xs, mid, color=MID, lw=1.8, label='중기 5종'); cax.plot(xs, lv, color=ACC, lw=2.4, label='단기 5종')
    lg = cax.legend(loc='lower left', bbox_to_anchor=(0, 1.0), ncol=4, frameon=False, prop=R, fontsize=9, borderaxespad=0.2)
    [tx.set_fontsize(9) for tx in lg.get_texts()]
    cax.axhline(100, color=LINE, lw=1)
    for sp in cax.spines.values():
        sp.set_visible(False)
    cax.tick_params(colors=MUTED, labelsize=8.5, length=0)
    cax.set_xticks([0, len(lv) - 1]); cax.set_xticklabels([f"{s0[4:6]}/{s0[6:]}", f"{s1[4:6]}/{s1[6:]}"], fontproperties=R)
    cax.grid(axis='y', color=LINE, lw=0.6)
    for lab in cax.get_yticklabels():
        lab.set_fontproperties(R)
    t(ax, L, 0.082, "시작일=100 누적 지수 · S&P500 은 달러 지수(환율 미반영, 한국 채점일 직전 미국 종가 기준)", 8.5, color=MUTED)
    t(ax, L, 0.064, "중기는 5종을 매일 그대로 보유 가정(종가 진입 밴드 미반영) · 스프레드·슬리피지 미반영", 8.5, color=MUTED)

    # 면책 — 반드시 포함
    t(ax, L, 0.045, "※ 개인이 자체 규칙으로 만든 참고 정보이며 투자 권유·자문이 아닙니다. 과거 성과와 백테스트는 미래 수익을 보장하지 않습니다.", 8.5, color=MUTED)
    t(ax, L, 0.027, "   매매 판단과 손익의 책임은 투자자 본인에게 있습니다. 유료 서비스·1:1 상담·리딩을 하지 않습니다.", 8.5, color=MUTED)
    out = out or os.path.join(pp.PUB, f"요약카드_{T[:4]}-{T[4:6]}-{T[6:]}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, facecolor=BG); plt.close(fig)
    return out


if __name__ == '__main__':
    T = sys.argv[sys.argv.index('--date') + 1] if '--date' in sys.argv else datetime.now(pp.KST).strftime('%Y%m%d')
    print(build_card(T, os.path.join('/tmp/mr', 'card_test.png') if '--preview' in sys.argv else None))
