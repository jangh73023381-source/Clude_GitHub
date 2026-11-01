# -*- coding: utf-8 -*-
"""공개용 웹 아카이브 페이지 생성 (2026-10-21 사용자 요청 — 텔레그램 + 웹 아카이브).

  python3 references/scripts/public_site.py [--date YYYYMMDD]
  → fable/공개/site.html (Claude Artifact 로 게시하는 원본, 같은 URL 에 매일 재게시)

입력은 public_post.py 와 같다(watch_plan_<T>.json · lv_oos_tracker.csv · 공개브리핑_*.md 목록). 선정 재계산 없음.
"""
import argparse, csv, glob, html, json, os
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
LOOP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PUB = os.path.abspath(os.path.join(LOOP, '..', 'fable', '공개'))
import importlib.util as _u
_s = _u.spec_from_file_location('pp', os.path.join(os.path.dirname(__file__), 'public_post.py'))
pp = _u.module_from_spec(_s); _s.loader.exec_module(pp)
E = html.escape


def series():
    rows = [r for r in csv.DictReader(open(os.path.join(LOOP, 'references', 'lv_oos_tracker.csv'), encoding='utf-8'))
            if r.get('lv_ret') not in ('', None)]
    mid = {r['date']: float(r['mom150_ret']) for r in csv.DictReader(open(os.path.join(LOOP, 'references', 'mid_momentum_shadow.csv'), encoding='utf-8'))
           if r.get('status') == 'scored' and r.get('mom150_ret') not in ('', None)}
    a = b = m = 100.0; out = [(rows[0]['date'], 100.0, 100.0, 100.0)]
    for r in rows:
        a *= 1 + float(r['lv_ret']) / 100; b *= 1 + float(r['bench_ret']) / 100; m *= 1 + mid.get(r['date'], 0.0) / 100
        out.append((r['date'], a, b, m))
    return out


def chart(s):
    W, H, L, R, T, B = 640, 240, 44, 12, 14, 28
    vals = [v for _, a, b, m in s for v in (a, b, m)]
    lo, hi = min(vals) - 2, max(vals) + 2
    x = lambda i: L + (W - L - R) * i / (len(s) - 1)
    y = lambda v: T + (H - T - B) * (hi - v) / (hi - lo)
    grid = ''.join(f'<line x1="{L}" x2="{W-R}" y1="{y(g):.1f}" y2="{y(g):.1f}" class="g"/><text x="{L-6}" y="{y(g)+4:.1f}" class="ax" text-anchor="end">{g:.0f}</text>'
                   for g in range(int(lo // 5 * 5 + 5), int(hi) + 1, 5))
    pa = ' '.join(f'{x(i):.1f},{y(r[1]):.1f}' for i, r in enumerate(s))
    pb = ' '.join(f'{x(i):.1f},{y(r[2]):.1f}' for i, r in enumerate(s))
    pm = ' '.join(f'{x(i):.1f},{y(r[3]):.1f}' for i, r in enumerate(s))
    d0, d1 = s[0][0], s[-1][0]
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="누적 성과 차트">{grid}'
            f'<line x1="{L}" x2="{W-R}" y1="{y(100):.1f}" y2="{y(100):.1f}" class="base"/>'
            f'<polyline points="{pb}" class="lb"/><polyline points="{pm}" class="lm"/><polyline points="{pa}" class="la"/>'
            f'<circle cx="{x(len(s)-1):.1f}" cy="{y(s[-1][1]):.1f}" r="4" class="da"/>'
            f'<text x="{L}" y="{H-8}" class="ax">{d0[4:6]}/{d0[6:]}</text>'
            f'<text x="{W-R}" y="{H-8}" class="ax" text-anchor="end">{d1[4:6]}/{d1[6:]}</text></svg>')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--date', default=datetime.now(KST).strftime('%Y%m%d'))
    T = ap.parse_args().date
    wp = json.load(open(os.path.join(LOOP, '장중알림', 'plans', f'watch_plan_{T}.json'), encoding='utf-8'))
    p = pp.perf(); s = series()
    d = datetime.strptime(T, '%Y%m%d'); wd = '월화수목금토일'[d.weekday()]
    cons = wp['mode'] == '보수'
    rows = ''.join(
        f'<tr><td><b>{E(x["name"])}</b><span class="code">{x["code"]}</span></td><td><span class="pill {"new" if x["status"]=="신규" else "keep"}">{E(x["status"])}</span></td>'
        f'<td>{x["prev_close"]:,.0f}</td><td class="hi">{x["upper"]:,}</td><td>{x["limit"]:,}</td><td class="neg">{x["stop"]:,}</td><td class="pos">{x["target"]:,}</td></tr>'
        for x in wp['short'])
    sells = ', '.join(E(x['name']) for x in wp.get('short_sells', [])) or '없음'
    mids = ''.join(f'<li>{E(m["name"])} <span class="code">{m["code"]}</span></li>' for m in wp['mid'])
    days = sorted((os.path.basename(f)[6:16] for f in glob.glob(os.path.join(PUB, '공개브리핑_*.md'))), reverse=True)
    arch = ''.join(f'<details{" open" if i==0 else ""}><summary>{dd}</summary><pre>{E(open(os.path.join(PUB, f"공개브리핑_{dd}.md"), encoding="utf-8").read())}</pre></details>'
                   for i, dd in enumerate(days[:60]))
    diff = p['lv'] - p['bm']
    page = f'''<title>데일리 ETF 브리핑</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;600;700&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
/* 레이아웃: 단일 칼럼 장전 메모 — 모드 띠 → 오늘의 가격표 → 성과 → 아카이브 */
:root{{--bg:#f6f7f5;--panel:#ffffff;--fg:#17201b;--muted:#5d6a62;--line:#dfe4e0;--accent:#1f6f54;--warn:#b3402a;--warnbg:#fbe9e4;--okbg:#e4f2ea;--mid:#b07a1e;
--sans:"IBM Plex Sans KR",system-ui,sans-serif;--mono:"IBM Plex Mono",ui-monospace,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#111613;--panel:#182019;--fg:#e6ece8;--muted:#9aa8a0;--line:#2b352f;--accent:#5fc49b;--warn:#ff8a70;--warnbg:#3a1f19;--okbg:#17301f;--mid:#e0b25a;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#111613;--panel:#182019;--fg:#e6ece8;--muted:#9aa8a0;--line:#2b352f;--accent:#5fc49b;--warn:#ff8a70;--warnbg:#3a1f19;--okbg:#17301f;--mid:#e0b25a;color-scheme:dark}}
body{{background:var(--bg);color:var(--fg);font:15px/1.6 var(--sans)}}
.wrap{{max-width:860px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:28px 48px;display:flex;flex-direction:column;gap:22px}}
h1{{font-size:1.7rem;margin:0;text-wrap:balance}} h2{{font-size:1.1rem;margin:0 0 10px}}
.sub{{color:var(--muted);font-size:.9rem}}
.mode{{padding:12px 16px;border-radius:10px;background:{"var(--warnbg)" if cons else "var(--okbg)"};border-left:4px solid {"var(--warn)" if cons else "var(--accent)"}}}
.mode b{{color:{"var(--warn)" if cons else "var(--accent)"}}}
section{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}}
.tbl{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:.92rem}}
th,td{{padding:8px 6px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}} th:first-child,td:first-child{{text-align:left}}
th{{color:var(--muted);font-weight:600;font-size:.8rem;letter-spacing:.02em}}
.code{{font-family:var(--mono);color:var(--muted);font-size:.8rem;margin-left:6px}}
.pill{{font-size:.75rem;padding:2px 8px;border-radius:99px;border:1px solid var(--line)}} .pill.new{{color:var(--accent);border-color:var(--accent)}}
.hi{{font-weight:700}} .neg{{color:var(--warn)}} .pos{{color:var(--accent)}}
ul{{margin:0;padding-left:18px}} .note{{color:var(--muted);font-size:.85rem;margin-top:8px}}
.kpi{{display:flex;gap:28px;flex-wrap:wrap;margin-bottom:8px}} .kpi div{{min-width:0}} .kpi b{{font-size:1.4rem;display:block;font-variant-numeric:tabular-nums}}
svg{{width:100%;height:auto}} .g{{stroke:var(--line)}} .base{{stroke:var(--muted);stroke-dasharray:3 3}} .ax{{fill:var(--muted);font-size:11px}}
.la{{fill:none;stroke:var(--accent);stroke-width:2.4}} .lb{{fill:none;stroke:var(--muted);stroke-width:1.6;stroke-dasharray:5 3}} .da{{fill:var(--accent)}} .lm{{fill:none;stroke:var(--mid);stroke-width:2}}
.leg span{{margin-right:14px;font-size:.85rem}} .sw{{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:6px}}
details{{border-top:1px solid var(--line);padding:8px 0}} summary{{cursor:pointer;font-weight:600}} pre{{white-space:pre-wrap;font:13px/1.55 var(--sans);margin:8px 0 0}}
.disc{{font-size:.82rem;color:var(--muted)}}
</style>
<div class="wrap">
<header><h1>데일리 ETF 브리핑</h1><div class="sub">{d.month}월 {d.day}일({wd}) 장전 · 전일 종가 기준 · 매일 아침 갱신</div></header>
<div class="mode"><b>{"보수 모드" if cons else "표준 모드"}</b> — {"급락·금리 경고 신호 발동. 매수상단 전일종가 +0.3%, 금액 평소의 2/3, 14:30까지 지정가 미체결이면 매수하지 않습니다." if cons else "매수상단 전일종가 +0.6%. 14:30까지 미체결이면 종가 무렵 시장가로 담습니다."}</div>
<section><h2>단기 ETF 5종 <span class="sub">저변동 정렬 규칙 · 하루 보유 후 교체</span></h2>
<div class="tbl"><table><thead><tr><th>종목</th><th>구분</th><th>전일종가</th><th>매수상단</th><th>지정가(-1%)</th><th>손절(2ATR)</th><th>목표(+3%)</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="note">오늘 종가에 교체되는 종목: {sells}. 매수상단 위로 시작하면 쫓지 않습니다.</div></section>
<section><h2>중기 ETF 5종 <span class="sub">150일 모멘텀 · 종가 무렵 당일 등락 {wp["mid_band"][0]:+.1f}%~{wp["mid_band"][1]:+.1f}%일 때만</span></h2><ul>{mids}</ul></section>
<section><h2>성과 공개 <span class="sub">누적 {p["n"]}거래일 · 무비용 가정 · 손실일 포함</span></h2>
<div class="kpi"><div><span class="sub">단기 5종</span><b>{p["lv"]:+.2f}%</b></div><div><span class="sub">중기 5종</span><b>{(p["mid"] if p.get("mid") is not None else 0):+.2f}%</b></div><div><span class="sub">KODEX200 같은 기간</span><b>{p["bm"]:+.2f}%</b></div><div><span class="sub">직전 거래일 단기 / 중기</span><b>{p["last_lv"]:+.2f}% / {(p["last_mid"] if p.get("last_mid") is not None else 0):+.2f}%</b></div></div>
<div class="leg"><span><i class="sw" style="background:var(--accent)"></i>단기 5종</span><span><i class="sw" style="background:var(--mid)"></i>중기 5종</span><span><i class="sw" style="background:var(--muted)"></i>KODEX200</span></div>
{chart(s)}<div class="note">시작일을 100으로 놓은 누적 지수입니다. 중기는 5종을 매일 그대로 보유했다고 가정한 값(종가 진입 밴드 미반영)이며, 호가 스프레드·슬리피지는 반영하지 않았습니다.</div></section>
<section><h2>지난 브리핑</h2>{arch}</section>
<p class="disc">{E(pp.DISCLAIMER)}</p>
</div>'''
    out = os.path.join(PUB, 'site.html'); open(out, 'w', encoding='utf-8').write(page); print(out)


if __name__ == '__main__':
    main()
