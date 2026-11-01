# -*- coding: utf-8 -*-
"""VMX 성과 검정 (선행 점검 P1~P3 통과 후 실행). r3_mom.md §2 사전등록 그대로."""
from vmx_lib import *
import warnings; warnings.filterwarnings('ignore')
SEED = 20260929
S = sleeve('exit')
r_all = S.r
EV = S.index[S.index >= EVAL0]
r = r_all.loc[EV].values
dts = np.array([int(dates[i + 1]) for i in EV])      # 실현일


def w_for(sig, K=5):
    return weights(sig, K)


def eval_pair(w_all, rr=r, idx=EV):
    w = w_all.loc[idx].values
    w = np.where(np.isfinite(w), w, 1.0)   # σ̂ 미정의(L252 초기 2일) → 스케일 없음(w=1)
    v = w * rr
    c = np.nanmean(w) * rr
    return v, c, w


def line(nm, x):
    s = stats(x)
    return f"{nm:34s} CAGR {s['cagr']:+6.1f}  MDD {s['mdd']:6.1f}  Sh {s['sh']:.3f}"


res = {}
print(f"평가 창: 선정일 {dates[EV[0]]} ~ {dates[EV[-1]]} ({len(EV)}일), 슬리브 시작 {dates[SLEEVE_START]}")
print(line('슬리브(스케일 전, mom150 탈락청산 RuleH)', r))
print('\n=== 본판·R1 인접값 ===')
for nm, L, K in [('본판 L126 K5', 126, 5), ('R1 L63 K5', 63, 5), ('R1 L252 K5', 252, 5), ('R1 L126 K1', 126, 1)]:
    w = w_for(sig_hat(r_all, L), K)
    v, c, we = eval_pair(w)
    lo, hi, _ = boot_diff(v, c, 'sharpe', seed=SEED)
    clo, chi, _ = boot_diff(v, c, 'cagr', seed=SEED)
    sv, sc = stats(v), stats(c)
    res[nm] = dict(v=v, c=c, w=we, dsh=sv['sh'] - sc['sh'], lo=lo, hi=hi, sv=sv, sc=sc, clo=clo, chi=chi)
    print(line(nm, v) + f" | ①상수(평균w {we.mean():.3f}) CAGR {sc['cagr']:+.1f} MDD {sc['mdd']:.1f} Sh {sc['sh']:.3f}"
          f" | ΔSh {sv['sh']-sc['sh']:+.3f} 90%CI [{lo:+.3f},{hi:+.3f}] | ΔCAGR {sv['cagr']-sc['cagr']:+.2f} CI[{clo:+.2f},{chi:+.2f}] "
          f"ΔMDD {sv['mdd']-sc['mdd']:+.1f} | 일t {tstat(v-c):+.2f} | 통과(a) {lo>0}")

m = res['본판 L126 K5']; v, c, w = m['v'], m['c'], m['w']
imp = m['dsh']
print('\n=== 대조군 (본판 L126 K5 기준, 평균 노출 매칭) ===')
# ② KODEX200 σ̂ 판
Mr = bench_by_i(S.index)
w2 = w_for(sig_hat(Mr, 126), 5).loc[EV].values
w2 = w2 * (w.mean() / w2.mean())
v2 = w2 * r; imp2 = sharpe(v2) - sharpe(c)
lo2, hi2, _ = boot_diff(v, v2, 'sharpe', seed=SEED)
print(f"② KODEX200 σ̂ 판: Sh {sharpe(v2):.3f} (최대 w {w2.max():.2f}) 개선 {imp2:+.3f} = 본판 개선의 {imp2/imp if imp else np.nan:.2f}배 "
      f"→ (b) 재분류 {imp2 >= 0.8*imp if imp>0 else 'n/a'} | 본판−② ΔSh 90%CI [{lo2:+.3f},{hi2:+.3f}]")
# ③ MA60 게이트 (평균 노출 매칭)
cb = pd.Series(C[:, bi]); ma = cb.rolling(60).mean()
below = (cb < ma).values[EV].astype(float)
g = 1 - (1 - w.mean()) / below.mean()
if g >= 0:
    w3 = np.where(below == 1, g, 1.0); gdesc = f"MA60 아래 노출 {g:.3f}, 위 1.0"
else:
    k = w.mean() / (1 - below).mean(); w3 = np.where(below == 1, 0.0, k); gdesc = f"MA60 아래 0, 위 {k:.3f}"
v3 = w3 * r
lo3, hi3, _ = boot_diff(v, v3, 'sharpe', seed=SEED)
print(f"③ MA60 게이트({gdesc}, 평균 {w3.mean():.3f}): {line('', v3)} | 본판−③ ΔSh {sharpe(v)-sharpe(v3):+.3f} 90%CI [{lo3:+.3f},{hi3:+.3f}] → (c) 기각 {lo3<=0}")
# ④ 무관 계열
sig126 = sig_hat(r_all, 126)
sig_lag = sig126.shift(250)
w4a_all = w_for(sig_lag, 5)
gi = codes.index('411060')
G = pd.Series(FWD[S.index, gi], index=S.index)
w4b_all = w_for(sig_hat(G, 126), 5)
d4 = {}
for nm4, wa in [('④-1 σ̂ 250일 시차', w4a_all), ('④-2 ACE KRX금현물 σ̂', w4b_all)]:
    wa_ev = wa.loc[EV].values
    defined = np.isfinite(wa_ev)
    # (가) 전체 창: 미정의일 w=1, 평균 노출 매칭
    wf = np.where(defined, wa_ev, 1.0); wf = wf * (w.mean() / wf.mean())
    impf = sharpe(wf * r) - sharpe(c)
    # (나) 정의 구간 한정: 본판·①도 같은 구간으로 재계산
    rs, ws, wd = r[defined], w[defined], wa_ev[defined]
    wd = wd * (ws.mean() / wd.mean())
    cs = ws.mean() * rs
    imp_main_s = sharpe(ws * rs) - sharpe(cs); imps = sharpe(wd * rs) - sharpe(cs)
    ratio_f = impf / imp if imp > 0 else np.nan
    ratio_s = imps / imp_main_s if imp_main_s > 0 else np.nan
    d4[nm4] = (ratio_f, ratio_s)
    print(f"{nm4}: 전체창(미정의 {int((~defined).sum())}일 w=1) 개선 {impf:+.3f} = 본판의 {ratio_f:.2f}배 | 정의구간 {defined.sum()}일({dates[EV[defined][0]]}~) "
          f"본판 개선 {imp_main_s:+.3f}, 대조 개선 {imps:+.3f} = {ratio_s:.2f}배 → (d') 기각 {(ratio_f>=0.5) or (ratio_s>=0.5)}")
# ⑤ w 20일 블록 셔플 200회
rng = np.random.default_rng(SEED)
nb = int(np.ceil(len(w) / 20)); blocks = [w[j*20:(j+1)*20] for j in range(nb)]
sh_null = []
for _ in range(200):
    ws_ = np.concatenate([blocks[j] for j in rng.permutation(nb)])
    sh_null.append(sharpe(ws_ * r) - sharpe(c))
sh_null = np.array(sh_null)
kk = (sh_null >= imp).sum()
p5 = (1 + kk) / 201
print(f"⑤ w 블록셔플 200회: 귀무 ΔSh 평균 {sh_null.mean():+.3f} (5–95% {np.quantile(sh_null,.05):+.3f}~{np.quantile(sh_null,.95):+.3f}), "
      f"실측 {imp:+.3f}, ≥실측 {kk}회, p={(kk)/200:.3f} (보수 (1+k)/201={p5:.3f}) → 기각 {p5>=0.05}")

print('\n=== 기각 조건 (d)(e)(f) ===')
dd = v - c
tot = dd.sum()
ev_dates = [20200319, 20240805, 20260626, 20260713]
rows = []
for e in ev_dates:
    pos = np.searchsorted(dts, e)
    if pos >= len(dts) or dts[0] > e:
        rows.append((e, None, None)); continue
    after = dd[pos + 1:pos + 21] if dts[pos] == e else dd[pos:pos + 20]
    incl = dd[pos:pos + 20]
    rows.append((e, after.sum(), incl.sum()))
for e, a, b in rows:
    if a is None:
        print(f"  {e}: 평가 창 밖(워밍업)")
    else:
        print(f"  {e}: 이후 20거래일 누적 차(VMX−①) {100*a:+.2f}%p (폭락일 포함 20일 {100*b:+.2f}%p), 전체 누적 차 대비 {a/tot if tot else np.nan:+.2f} / {b/tot if tot else np.nan:+.2f}")
inw = [x for x in rows if x[1] is not None]
all_neg = all(x[1] < 0 for x in inw) or all(x[2] < 0 for x in inw)
one50 = tot > 0 and any(max(x[1], x[2]) / tot >= 0.5 for x in inw)
print(f"  전체 일별 차 합 {100*tot:+.2f}%p | (d) 전부 음수 {all_neg} · 한 사건 ≥50% {one50} → (d) 문언상 발동 {all_neg or one50} (전체 개선 ≤0 이면 50% 조건은 정의상 비적용 — 해석 기록)")
f3 = [(sharpe(a) - sharpe(b)) for a, b in zip(np.array_split(v, 3), np.array_split(c, 3))]
print(f"  (e) fold Sharpe 차(VMX−①): {['%+.3f' % x for x in f3]} ({[str(dts[j*len(dts)//3]) for j in range(3)]}) → 기각 {min(f3)<=0}")
rr5 = r5(dd)
flip = np.sign(rr5['drop3']) != np.sign(dd.mean())
top5 = np.argsort(-dd)[:5]
vm = v.copy(); vm[top5] = c[top5]
mdd_v, mdd_c, mdd_vm = stats(v)['mdd'], stats(c)['mdd'], stats(vm)['mdd']
print(f"  (f) 일별 차 평균 {100*dd.mean():+.5f}%p, 상위3일 제거 {100*rr5['drop3']:+.5f}%p, 중앙값 {100*rr5['median']:+.5f} → 부호반전 {flip} | "
      f"MDD 본판 {mdd_v:.1f} ① {mdd_c:.1f}, 최선5일 ①대체 후 {mdd_vm:.1f} → MDD 우위 소멸 {mdd_vm <= mdd_c}")

print('\n=== Deflated Sharpe (본판) ===')
for ne in (100, 850):
    p, sr0 = dsr(v, ne)
    print(f"  N_eff={ne}: DSR={p:.3f} (기대 최대 SR0 연 {sr0:.2f}, 본판 Sh {sharpe(v):.2f})")

print('\n=== 보조 보고 (판정 제외) ===')
# CB 밴드 틀
Sb = sleeve('band'); rb_all = Sb.r; rb = rb_all.loc[EV].values
wb = w_for(sig_hat(rb_all, 126), 5).loc[EV].values
vb, cbb = wb * rb, wb.mean() * rb
lob, hib, _ = boot_diff(vb, cbb, 'sharpe', seed=SEED)
print(line('CB밴드 슬리브(원)', rb))
print(line('CB밴드 + VMX', vb) + f" | ① Sh {sharpe(cbb):.3f} ΔSh {sharpe(vb)-sharpe(cbb):+.3f} CI[{lob:+.3f},{hib:+.3f}] 평균w {wb.mean():.3f} 확장발동 {Sb.attrs if hasattr(Sb,'attrs') else ''}")
# 20일 트랜치(mid.py) 오버레이
tr = mid.tranche(mid.base_sel)
tr = tr[tr.date.astype(int) >= int(dates[EVAL0 + 1])].reset_index(drop=True)
x = pd.Series(tr.port.values / 100)
st = x.shift(1).rolling(126, min_periods=126).std()
wt = weights(st, 5).values
ok = np.isfinite(wt)
vt, ct = wt[ok] * x.values[ok], np.nanmean(wt[ok]) * x.values[ok]
lot, hit, _ = boot_diff(vt, ct, 'sharpe', seed=SEED)
print(line('20일 트랜치 원', x.values[ok]) + f" | +VMX Sh {sharpe(vt):.3f} ① {sharpe(ct):.3f} ΔSh {sharpe(vt)-sharpe(ct):+.3f} CI[{lot:+.3f},{hit:+.3f}]")

print('\n=== 패널 이상치 민감도 (441640 20240405 −20.56%) ===')
hit_ = [i for i in EV if int(dates[i + 1]) == 20240405]
i0 = hit_[0]
held = codes.index('441640') in set(targets(MOM[150], i0, )[i0].tolist()) if False else codes.index('441640') in set(top_k(MOM[150], i0).tolist())
print(f"  20240404 선정 목표에 441640 포함: {held}. 불포함이면 슬리브·VMX 수익에 영향 없음. σ̂ 경로(과거 수익)도 영향 없음.")
