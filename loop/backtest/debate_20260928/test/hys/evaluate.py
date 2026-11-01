# -*- coding: utf-8 -*-
"""HYS 판정 ①~⑤ + fold + 대조군(교체율 매칭 무작위 유지 200회) + b* 역산."""
import pickle, json, numpy as np, pandas as pd
from common import *
import hys

T = pickle.load(open('/home/claude/w/test/hys/tracks.pkl', 'rb'))
LV, lvp = T['LV']
rep_lv, _ = hys.turnover(lvp)
res = {}


def pair(H, m):
    j = H[['i', 'date', m]].merge(LV[['i', m]], on='i', suffixes=('', '_lv')).dropna(subset=[m, m + '_lv'])
    return j


def ci_mean(d, I):
    bs = d[I].mean(1); return np.quantile(bs, [.05, .95])


def evalK(K):
    H, hp = T[K]
    rep_h, ret_h = hys.turnover(hp)
    common_days = sorted(set(rep_h) & set(rep_lv))
    rlv = np.mean([rep_lv[i] for i in common_days]); rh = np.mean([rep_h[i] for i in common_days])
    r = {'K': K, 'rep_lv': rlv, 'rep_hys': rh, 'rep_cut': 1 - rh / rlv}
    for m in ('OO', 'OOx', 'L1', 'A'):
        j = pair(H, m); d = (j[m] - j[m + '_lv']).values; n = len(d)
        I = sbb_idx(n)
        lo, hi = ci_mean(d, I)
        x, y = j[m].values, j[m + '_lv'].values
        dsh = sharpe(x[I]) - sharpe(y[I])
        ph, pl = prof(x), prof(y)
        f3 = folds(d, 3); rr = r5(d)
        r[m] = dict(n=n, cagr=ph['cagr'], mdd=ph['mdd'], sh=ph['sharpe'], dcagr=ph['cagr'] - pl['cagr'],
                    dmdd=ph['mdd'] - pl['mdd'], dsh=ph['sharpe'] - pl['sharpe'], dmean=d.mean(), ci=[lo, hi],
                    dsh_ci=list(np.quantile(dsh, [.05, .95])), f3=f3, t=tstat(d), med=rr['median'], drop3=rr['drop3'])
    # 폴백
    r['fb_rate'] = H['fb'].mean(); r['fb_days'] = int(H['fb'].sum())
    if r['fb_days']:
        fbj = pair(H[H.fb], 'OO'); r['fb_oo_diff'] = float((fbj['OO'] - fbj['OO_lv']).mean())
    r['tv1'] = H['tv1'].mean(); r['tv5'] = H['tv5'].mean()
    # b* = -(OO 일별 차 평균) / (일 교체 감소 건수 × 1/5)  [%, 왕복 스프레드 손익분기]
    dred = rlv - rh
    r['bstar'] = -r['OO']['dmean'] / (dred / 5) if dred > 0 else np.nan
    # 이상치 민감도 (441640 20240405 −20.56%): D ∈ [20240402,20240405] 행 제거
    j = pair(H, 'OO'); msk = ~j['date'].between('20240402', '20240405')
    d = (j['OO'] - j['OO_lv'])[msk].values
    r['anom_dmean'] = d.mean(); r['anom_ci'] = list(ci_mean(d, sbb_idx(len(d))))
    # 판정
    oo, ox = r['OO'], r['OOx']
    r['c1'] = oo['ci'][0] > -0.010
    r['c2'] = oo['dsh_ci'][0] > -0.05
    r['c3'] = oo['dmdd'] > -1.0
    r['c4'] = r['rep_cut'] >= 0.25
    r['c5'] = ox['ci'][0] > -0.010
    r['cfold'] = min(oo['f3']) >= -0.02
    return r, H, hp, ret_h


if __name__ == '__main__':
    out = {}
    for K in (8, 6, 10):
        r, H, hp, ret_h = evalK(K)
        out[K] = r
        if K == 8:
            H8, ret8 = H, ret_h
    # 대조군: 교체율 매칭 무작위 유지 200회 (K=8 기본만)
    rng = np.random.default_rng(SEED)
    hd = pair(H8, 'OO'); hmean = (hd['OO'] - hd['OO_lv']).mean()
    null = []; nrep = []
    for b in range(200):
        R, rp = hys.track('RND', retain=ret8, rng=rng)
        j = pair(R, 'OO'); null.append((j['OO'] - j['OO_lv']).mean())
        rr, _ = hys.turnover(rp); nrep.append(np.mean(list(rr.values())))
    null = np.array(null)
    out['ctrl'] = dict(hys_dmean=hmean, null_mean=null.mean(), null_median=float(np.median(null)),
                       null_q05=float(np.quantile(null, .05)), null_q95=float(np.quantile(null, .95)),
                       pct_rank=float((null < hmean).mean()), null_rep=float(np.mean(nrep)),
                       pass_=bool(hmean > np.median(null)))
    json.dump(out, open('/home/claude/w/test/hys/hys_out.json', 'w'), indent=1, default=float)
    for K in (8, 6, 10):
        r = out[K]
        print(f"=== K_out={K} 풀40 · 교체 LV {r['rep_lv']:.3f}→{r['rep_hys']:.3f}/일 ({r['rep_cut']:.1%} 감소) · 폴백 {r['fb_days']}일 · b* {r['bstar']:.4f}%")
        for m in ('OO', 'OOx', 'L1', 'A'):
            x = r[m]
            print(f"  {m:3s} CAGR {x['cagr']:+.1f}(Δ{x['dcagr']:+.1f}) MDD {x['mdd']:.1f}(Δ{x['dmdd']:+.1f}) Sh {x['sh']:.2f}(Δ{x['dsh']:+.3f} CI[{x['dsh_ci'][0]:+.3f},{x['dsh_ci'][1]:+.3f}]) Δ일 {x['dmean']:+.4f} CI[{x['ci'][0]:+.4f},{x['ci'][1]:+.4f}] fold {['%+.4f'%f for f in x['f3']]} 중앙 {x['med']:+.4f} 상위3제거 {x['drop3']:+.4f}")
        print('  판정', {k: r[k] for k in ('c1','c2','c3','c4','c5','cfold')}, 'tv<1억', round(r['tv1'],4), 'tv<5억', round(r['tv5'],4), '이상치제거 Δ', round(r['anom_dmean'],4), r['anom_ci'])
    print('대조군', out['ctrl'])
    print('LV tv', LV['tv1'].mean(), LV['tv5'].mean())
