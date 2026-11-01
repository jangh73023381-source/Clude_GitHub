"""Rule BRD 와 같은 정의의 시장 폭(b200) 7년 재구성 — krx_full 조밀 배열(P_close·P_value, 비수정 종가)."""
import numpy as np, pandas as pd
K = '../krx_full/'
d = np.load(K + 'dates.npy').astype(str); C = np.load(K + 'P_close.npy', mmap_mode='r'); V = np.load(K + 'P_value.npy', mmap_mode='r')
i0 = np.searchsorted(d, '20171101'); d = d[i0:]; C = np.array(C[i0:], float); V = np.array(V[i0:], float)
C[C <= 0] = np.nan
val20 = pd.DataFrame(V).rolling(20, min_periods=20).mean().values
ma = pd.DataFrame(C).rolling(200, min_periods=200).mean().values
ok = (C >= 1000) & (val20 >= 1e9) & np.isfinite(ma)
b = np.where(ok.sum(1) > 0, (ok & (C > ma)).sum(1) / np.maximum(ok.sum(1), 1) * 100, np.nan)
pd.DataFrame({'date': d, 'n': ok.sum(1), 'b200': b}).to_csv('breadth_b200.csv', index=False)
print(d[0], d[-1], np.round(b[-5:], 2))
