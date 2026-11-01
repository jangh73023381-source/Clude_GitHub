"""Kronos (shiyu-coder/Kronos, AAAI 2026) 제로샷 캔들 예측 → 한국 개별주 횡단면 선정 검정.
모델 코드는 검토 후 사용(신경망 정의만, 파일·네트워크 호출 없음). 가중치는 safetensors 를 직접 로드(믹스인 미사용).
표본일마다 20일 평균 거래대금 상위 U 종목(유동 조건 충족, 직전 LB일 결측 없음)의 OHLCV 를 넣어 다음 H일을 예측,
예측 수익(H일 뒤 예측 종가/현재 종가−1) 상위 10% 의 실제 수익 − 같은 U 종목 평균, 그리고 IC.
python3 kronos_bt.py <model:small|mini> <step> <U> [start_idx]"""
import sys, os, json, time, pickle, numpy as np, pandas as pd, torch
sys.path.insert(0, '/tmp/claude-0/ext/shiyu-coder_Kronos')
from model.kronos import KronosTokenizer, Kronos, KronosPredictor
from safetensors.torch import load_file
import glob
torch.set_num_threads(2); torch.manual_seed(0); np.random.seed(0)
MODEL, STEP, U = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
W = '/tmp/claude-0/kronos_w'


def build(cls, rep):
    d = glob.glob(f'{W}/models--NeoQuasar--{rep}/snapshots/*')[0]
    cfg = json.load(open(f'{d}/config.json')); m = cls(**cfg)
    m.load_state_dict(load_file(f'{d}/model.safetensors')); return m.eval()


tok = build(KronosTokenizer, 'Kronos-Tokenizer-2k' if MODEL == 'mini' else 'Kronos-Tokenizer-base')
mdl = build(Kronos, 'Kronos-mini' if MODEL == 'mini' else 'Kronos-small')
P = KronosPredictor(mdl, tok, device='cpu', max_context=512)
Z = np.load('/tmp/claude-0/vcpkr/dense.npz'); dates = Z['dates'].astype(int)
O, H, L, C, V = (Z[k].astype(float) for k in 'OHLCV'); T, N = C.shape
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
LB, HZ = 200, 5
idx = pd.to_datetime(dates.astype(str))
bdays = pd.bdate_range(idx[-1], periods=40)[1:]
start = int(sys.argv[4]) if len(sys.argv) > 4 else LB + 20
outp = f'/tmp/claude-0/vcpkr/kronos_{MODEL}_{STEP}_{U}.pkl'
res = pickle.load(open(outp, 'rb')) if os.path.exists(outp) else {}
for t in range(start, T - HZ, STEP):
    if t in res: continue
    t0 = time.time()
    win = slice(t - LB + 1, t + 1)
    ok = LIQ[t] & np.isfinite(C[win]).all(0) & np.isfinite(O[win]).all(0) & (V[win] > 0).all(0) & np.isfinite(C[t + HZ])
    cand = np.where(ok)[0]
    if len(cand) < 50: continue
    sel = cand[np.argsort(-val20[t, cand])[:U]]
    dfs, xs, ys = [], [], []
    yts = pd.Series(list(idx[t + 1:t + 1 + HZ]) if t + HZ < T else list(bdays[:HZ]))
    xts = pd.Series(idx[win])
    for j in sel:
        dfs.append(pd.DataFrame(dict(open=O[win, j], high=H[win, j], low=L[win, j], close=C[win, j], volume=V[win, j])))
        xs.append(xts); ys.append(yts)
    with torch.no_grad():
        pr = P.predict_batch(dfs, xs, ys, pred_len=HZ, T=1.0, top_p=0.9, sample_count=4, verbose=False)
    pc = np.array([p['close'].values for p in pr])                     # (U, HZ)
    res[t] = dict(sel=sel, pred1=pc[:, 0] / C[t, sel] - 1, pred5=pc[:, -1] / C[t, sel] - 1,
                  r1=C[t + 1, sel] / C[t, sel] - 1, r5=C[t + HZ, sel] / C[t, sel] - 1)
    pickle.dump(res, open(outp, 'wb'))
    print(dates[t], len(sel), f'{time.time()-t0:.0f}s', flush=True)
print('DONE')
