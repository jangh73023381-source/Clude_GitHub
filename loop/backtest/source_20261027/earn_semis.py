"""반도체 대형주 실적 발표일 이벤트 — 2026-10-28 사용자 질문("하이닉스 실적 좋을 걸 알았는데 왜 반도체를 못 맞췄나").
날짜: DART '연결재무제표기준영업(잠정)실적(공정공시)' 접수일(정정 제외). 하이닉스 35회, 삼성전자 70회(잠정+확정), 2018~2026-10.
가격: ETF 7년 패널(2019-04~2026-09). D0 = 발표일(장전 08시 전후 발표 → D0 시가부터 반영).
창: [D-1 종가→D0 종가] 발표일 보유 · [D-6→D-1] 사전 상승 · [D0→D+5] 사후.
비교: 반도체 ETF(091160 KODEX 반도체) − KODEX200, 그리고 같은 창 길이의 '평범한 날' 분포(이벤트일 ±10일 제외) 대비 순열 p.
사전 기대 대리지표(D-1까지 알 수 있는 것): 직전 20거래일 증권사 목표가 상향−하향(네이버 리포트, 해당 기업) · 반도체 ETF 20일 모멘텀."""
import json, glob, numpy as np, pandas as pd
p = pd.read_csv('/mnt/user-data/uploads/loop/backtest/panel_ohlc_long.csv', dtype={'code': str})
px = p.pivot(index='date', columns='code', values='close'); d = px.index.values.astype(int)
semi, k200 = px['091160'].values.astype(float), px['069500'].values.astype(float)
E = {'SK하이닉스': '20180125 20180424 20180726 20181025 20190124 20190425 20190725 20191024 20200131 20200423 20200723 20201104 20210129 20210428 20210727 20211026 20220427 20220727 20221026 20230201 20230426 20230726 20231026 20240125 20240425 20240725 20241024 20250123 20250424 20250724 20251029 20260128 20260423 20260729 20261028',
     '삼성전자': '20180109 20180131 20180406 20180426 20180706 20180731 20181005 20181031 20190108 20190131 20190405 20190430 20190705 20190731 20191008 20191031 20200108 20200130 20200407 20200429 20200707 20200730 20201008 20210108 20210128 20210407 20210429 20210707 20210729 20211008 20211028 20220107 20220127 20220407 20220428 20220707 20220728 20221007 20221027 20230106 20230131 20230407 20230427 20230707 20230727 20231011 20231031 20240109 20240131 20240405 20240430 20240705 20240731 20241008 20241031 20250108 20250131 20250408 20250430 20250708 20250731 20251014 20251030 20260108 20260129 20260407 20260430 20260707 20260730 20261008'}
# 리포트 목표가 수정(기업별, PIT)
rows = [json.loads(l) for fn in glob.glob('/tmp/claude-0/naver_rs/detail*.jsonl') for l in open(fn)]
rp = pd.DataFrame(rows).drop_duplicates('researchId')
rp['goal'] = pd.to_numeric(rp.goalPrice.astype(str).str.replace(',', ''), errors='coerce'); rp['dt'] = rp.writeDate.str.replace('-', '').astype(int)
rp = rp.sort_values(['itemCode', 'brokerName', 'dt']); rp['prev'] = rp.groupby(['itemCode', 'brokerName']).goal.shift()
rp['rev'] = np.sign(rp.goal / rp.prev - 1).where(rp.prev > 0)
CODE = {'SK하이닉스': '000660', '삼성전자': '005930'}
rng = np.random.default_rng(1)
def ret(a, i, j): return (a[j] / a[i] - 1) * 100 if 0 <= i < len(a) and 0 <= j < len(a) else np.nan
WIN = {'발표일 보유(D-1종가→D0종가)': (-1, 0), '사전 5일(D-6→D-1)': (-6, -1), '사후 5일(D0→D+5)': (0, 5), '발표일+익일(D-1→D+1)': (-1, 1)}
out = []; detail = []
for corp, s in E.items():
    t0s = [int(np.searchsorted(d, int(x))) for x in s.split() if d[0] <= int(x) <= d[-1]]
    t0s = [t for t in t0s if t < len(d) and d[t] == int(s.split()[[int(np.searchsorted(d, int(x))) for x in s.split()].index(t)]) or True]
    t0s = [int(np.searchsorted(d, int(x))) for x in s.split() if d[0] <= int(x) <= d[-2]]
    mask = np.ones(len(d), bool)
    for t in t0s: mask[max(t - 10, 0):t + 11] = False
    for wn, (a, b) in WIN.items():
        se = np.array([ret(semi, t + a, t + b) for t in t0s]); kk = np.array([ret(k200, t + a, t + b) for t in t0s]); sp = se - kk
        base = np.array([ret(semi, t + a, t + b) - ret(k200, t + a, t + b) for t in np.where(mask)[0] if 10 < t < len(d) - 10])
        sims = np.array([rng.choice(base, len(sp)).mean() for _ in range(5000)])
        out.append(dict(기업=corp, 창=wn, 횟수=len(sp), 반도체=np.nanmean(se), KODEX200=np.nanmean(kk), 반도체_초과=np.nanmean(sp), 초과_중앙=np.nanmedian(sp),
                        초과_양수비율=(sp > 0).mean() * 100, 평범한날_초과=base.mean(), p=(sims >= np.nanmean(sp)).mean()))
    for t in t0s:
        tt = d[t]; pre = rp[(rp.itemCode == CODE[corp]) & (rp.dt < tt) & (rp.dt >= d[max(t - 20, 0)])]
        detail.append(dict(기업=corp, 날짜=tt, 상향=int((pre.rev > 0).sum()), 하향=int((pre.rev < 0).sum()), 반도체20일=ret(semi, t - 21, t - 1),
                           발표일_초과=ret(semi, t - 1, t) - ret(k200, t - 1, t), 발표일_반도체=ret(semi, t - 1, t), 사후5_초과=ret(semi, t, t + 5) - ret(k200, t, t + 5)))
o = pd.DataFrame(out); dt = pd.DataFrame(detail)
pd.set_option('display.width', 260); pd.set_option('display.max_columns', 20)
print('가격 기간', d[0], '~', d[-1]); print(o.round(3).to_string(index=False))
dt['기대'] = np.where(dt.상향 + dt.하향 == 0, '리포트없음', np.where(dt.상향 > dt.하향, '상향우세', '하향·동률'))
print('\n사전 기대(직전 20일 목표가 상향 vs 하향)별 발표일 반도체 초과(%p):')
print(dt.groupby(['기업', '기대']).agg(횟수=('발표일_초과', 'size'), 발표일_초과=('발표일_초과', 'mean'), 양수비율=('발표일_초과', lambda x: (x > 0).mean() * 100),
                                     사후5_초과=('사후5_초과', 'mean')).round(2).to_string())
print('\n반도체 20일 모멘텀 부호별:'); dt['모멘텀'] = np.where(dt.반도체20일 > 0, '+', '−')
print(dt.groupby(['기업', '모멘텀']).agg(횟수=('발표일_초과', 'size'), 발표일_초과=('발표일_초과', 'mean'), 양수비율=('발표일_초과', lambda x: (x > 0).mean() * 100)).round(2).to_string())
print('\n하이닉스 최근 8회:'); print(dt[dt.기업 == 'SK하이닉스'].tail(8).round(2).to_string(index=False))
o.to_csv('earn_semis.csv', index=False); dt.to_csv('earn_semis_detail.csv', index=False)
