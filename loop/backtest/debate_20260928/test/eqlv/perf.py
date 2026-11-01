# -*- coding: utf-8 -*-
"""EQLV 성과 검정 (Q1·Q2 통과 후). r3_mom.md §3 명세 그대로."""
import sys, json; sys.path.insert(0, '/home/claude/w/test')
from common import *
cls = pd.read_csv('/home/claude/w/debate/prereg_mom_classes.csv', dtype={'code': str})
cmap = dict(zip(cls.code, cls.cls))
isEq = np.array([cmap.get(c) == '주식' for c in codes])
S20 = E.vol(20)

def pick_pool(sel, n_pool=30, start=20):
    out = {}
    for i in range(start, E.T - 3):
        pl = E.pool(i, n=n_pool)
        if len(pl) < 5: continue
        pk = sel(i, pl)
        if pk is None or len(pk) < 5 or np.isnan(E.fA[i, pk]).any(): continue
        out[i] = np.asarray(pk)
    return out

def mk_eqlv(lab):
    def s(i, pl, n=5):
        v = S20[i, pl]; m = ~np.isnan(v)
        if m.sum() < n: return pl[:n]
        o = pl[m][np.argsort(v[m], kind='stable')]
        eq = [x for x in o if lab[x]]
        if len(eq) >= n: return np.array(eq[:n])
        return np.array(eq + [x for x in o if not lab[x]][:n - len(eq)])
    return s

# 기준
PK = {'LV': pick_pool(E.sel_lv), 'MOM': pick_pool(E.sel_mom), 'EQLV': pick_pool(mk_eqlv(isEq)),
      'EQLV_p20': pick_pool(mk_eqlv(isEq), 20), 'EQLV_p40': pick_pool(mk_eqlv(isEq), 40)}
# CRLV (보고용): σ20 / 그날 eligible 유니버스 자산군 중앙값
clsarr = np.array([cmap.get(c, '') for c in codes])
def sel_crlv(i, pl, n=5):
    v = S20[i]; ok = E.elig & ~np.isnan(v)
    med = {k: np.median(v[ok & (clsarr == k)]) for k in ('주식', '채권혼합', '원자재') if (ok & (clsarr == k)).any()}
    r = np.array([v[x] / med.get(clsarr[x], np.nan) for x in pl])
    m = ~np.isnan(r)
    if m.sum() < n: return pl[:n]
    return pl[m][np.argsort(r[m], kind='stable')][:n]
PK['CRLV'] = pick_pool(sel_crlv)
# β 진단 (보고용): pool30 → β60(KODEX200) 하위5
Rb = E.R[:, E.bi]
Rd = pd.DataFrame(E.R); cov = Rd.rolling(60, min_periods=60).cov(pd.Series(Rb)).values
varb = pd.Series(Rb).rolling(60, min_periods=60).var().values
BETA = cov / varb[:, None]
def sel_beta(i, pl, n=5):
    b = BETA[i, pl]; m = ~np.isnan(b)
    if m.sum() < n: return pl[:n]
    return pl[m][np.argsort(b[m], kind='stable')][:n]
PK['BETA'] = pick_pool(sel_beta)

ov_ce, _ = overlap(PK['CRLV'], PK['EQLV'])
print(f'CRLV∩EQLV 겹침 {ov_ce:.3f}/5  (≥4.0 이면 CRLV=EQLV 로 기록·계산 생략)')
DF = {k: rets(v) for k, v in PK.items()}
# 공통 날짜
common = set(DF['LV'].i) & set(DF['MOM'].i)
for k in DF: common &= set(DF[k].i)
common = sorted(common)
print('공통 표본일', len(common), {k: len(v) for k, v in DF.items()})
D = {k: v.set_index('i').loc[common] for k, v in DF.items()}
n = len(common); IDX = sbb_idx(n)
MET = ('OO', 'OOx', 'L1', 'A')

def c1(name, m):
    """C1: LV–MOM 혼합, 전체기간 변동성 일치로 w 1회 결정(지표별)."""
    a, l, mo = D[name][m].values, D['LV'][m].values, D['MOM'][m].values
    target = np.nanstd(a, ddof=1); ws = np.linspace(0, 1, 1001)
    sds = [np.nanstd(w * l + (1 - w) * mo, ddof=1) for w in ws]
    w = ws[int(np.argmin(np.abs(np.array(sds) - target)))]
    return w, w * l + (1 - w) * mo

res = {}
def block(name):
    out = {}
    for m in MET:
        a = D[name][m].values; w, cc = c1(name, m); lv = D['LV'][m].values
        pa, pc, pl_ = prof(a), prof(cc), prof(lv)
        dC = ci_shdiff(a, cc, IDX); dL = ci_shdiff(a, lv, IDX)
        d = a - cc; ok = ~np.isnan(d); s = np.sort(d[ok])[::-1]
        fo = []
        for f in range(3):
            sl = slice(f * n // 3, (f + 1) * n // 3)
            fo.append((sh(a[sl]), sh(cc[sl])))
        out[m] = dict(cagr=pa['cagr'], mdd=pa['mdd'], sh=pa['sharpe'], w=w, c1_cagr=pc['cagr'], c1_mdd=pc['mdd'], c1_sh=pc['sharpe'],
                      dC=dC, lv_cagr=pl_['cagr'], lv_mdd=pl_['mdd'], lv_sh=pl_['sharpe'], dL=dL,
                      dmean=d[ok].mean(), drop3=(s.sum() - s[:3].sum()) / (len(s) - 3), med=np.median(d[ok]), folds=fo)
    return out
for name in ('EQLV', 'EQLV_p20', 'EQLV_p40', 'BETA') + (() if ov_ce >= 4.0 else ('CRLV',)):
    res[name] = block(name)
    for m in MET:
        r = res[name][m]
        print(f"[{name} {m}] CAGR{r['cagr']:+.1f} MDD{r['mdd']:.1f} Sh{r['sh']:.2f} | C1(w={r['w']:.3f}) CAGR{r['c1_cagr']:+.1f} MDD{r['c1_mdd']:.1f} Sh{r['c1_sh']:.2f} "
              f"ΔSh vs C1 {r['dC'][0]:+.3f} CI[{r['dC'][1]:+.3f},{r['dC'][2]:+.3f}] | LV Sh{r['lv_sh']:.2f} MDD{r['lv_mdd']:.1f} ΔSh vs LV {r['dL'][0]:+.3f} CI[{r['dL'][1]:+.3f},{r['dL'][2]:+.3f}] "
              f"| Δ일{r['dmean']:+.4f} 상위3제거{r['drop3']:+.4f} 중앙{r['med']:+.4f} folds(EQ,C1)={[(round(x,2),round(y,2)) for x,y in r['folds']]}")
# 기준 보고
for k in ('LV', 'MOM'):
    for m in MET:
        p = prof(D[k][m].values); print(f'{k} {m} CAGR{p["cagr"]:+.1f} MDD{p["mdd"]:.1f} Sh{p["sharpe"]:.2f}')
# DSR
for N in (100, 850):
    print(f'DSR EQLV OO N={N}: {deflated_sr(D["EQLV"]["OO"].values, N):.3f} · LV OO: {deflated_sr(D["LV"]["OO"].values, N):.3f}')
# 이상치 민감도: 441640 20240405 영향 D 행 제외
bad = [dates.index(x) for x in ('20240402', '20240403', '20240404', '20240405')]
keep = np.array([i not in bad for i in common])
a = D['EQLV']['OO'].values; w, cc = c1('EQLV', 'OO')
print(f'이상치 민감도: EQLV−C1 OO ΔSh 전체 {sh(a)-sh(cc):+.3f} / 20240402~05 선정일 제외 {sh(a[keep])-sh(cc[keep]):+.3f}')
pickle_out = {k: {int(i): v.tolist() for i, v in PK[k].items()} for k in ('EQLV',)}
import pickle; pickle.dump(dict(res=res, common=common), open('/home/claude/w/test/eqlv/perf_res.pkl', 'wb'))
