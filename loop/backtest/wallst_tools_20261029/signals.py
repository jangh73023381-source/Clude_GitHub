"""월가 시장분석 도구 → 한국장 이용가능일(K) 정렬 신호. 공개 시차를 보수적으로 반영한다.
avail(t) = 그 값을 한국 장중(종가 집행 전)에 실제로 볼 수 있는 첫 한국 날짜.
위험회피(risk-off)=True 면 현금. 백분위는 그 지표 자신의 날짜축에서 확장창(최소 250관측)으로만 계산(룩어헤드 없음)."""
import numpy as np, pandas as pd, os
from pandas.tseries.offsets import BDay
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw')
def y(s, col='close'):
    d = pd.read_csv(f'{R}/y_{s}.csv', dtype={'date': str}); d.index = pd.to_datetime(d.date); return d[col].astype(float)
def f(s):
    d = pd.read_csv(f'{R}/f_{s}.csv', dtype={'date': str}); d.index = pd.to_datetime(d.date); return pd.to_numeric(d.value, errors='coerce').dropna()
def pct(x, minp=250):
    x = x.dropna(); v = x.values; out = np.full(len(v), np.nan)
    for i in range(minp, len(v)): out[i] = (v[:i + 1] <= v[i]).mean() * 100
    return pd.Series(out, x.index)
def chg(x, n): return x - x.shift(n)
def lret(x, n): return np.log(x / x.shift(n))
# 공개 시차 (달력일 기준 이용가능일 계산)
LAG = {
 'yahoo': lambda t: t + pd.Timedelta(days=1),              # 미국 종가 t → 한국 t+1 장전
 'fred':  lambda t: t + BDay(1) + pd.Timedelta(days=1),    # FRED 일별: 다음 미국 영업일 공개 → 한국 그 다음날
 'ofr':   lambda t: t + BDay(2) + pd.Timedelta(days=1),
 'nfci':  lambda t: t + pd.Timedelta(days=6),               # 금요일 기준 → 다음 수요일 08:30 ET 공개
 'stl':   lambda t: t + pd.Timedelta(days=7),               # 금요일 기준 → 다음 목요일 공개
 'h41':   lambda t: t + pd.Timedelta(days=2),               # 수요일 기준 → 목요일 16:30 ET 공개
 'naaim': lambda t: t + pd.Timedelta(days=2),               # 수요일 마감 → 목요일 공개
}
def align(s, lag, kdates):
    """s: 지표일자 index 의 bool/float 시리즈 → 한국 날짜 kdates 에 이용가능한 최신값."""
    s = s.dropna(); a = pd.Series(s.values, index=pd.DatetimeIndex([LAG[lag](t) for t in s.index]))
    a = a[~a.index.duplicated(keep='last')].sort_index()
    return a.reindex(a.index.union(kdates)).ffill().reindex(kdates)

def naaim():
    import openpyxl
    ws = openpyxl.load_workbook(f'{R}/naaim.xlsx', read_only=True).active
    rows = [(r[0], r[1]) for r in ws.iter_rows(values_only=True) if hasattr(r[0], 'year') and r[1] is not None]
    s = pd.Series([float(v) for _, v in rows], pd.DatetimeIndex([d for d, _ in rows])).sort_index(); return s
def cnn():
    d = pd.read_csv(f'{R}/cnn_fg.csv', dtype={'date': str}); d.index = pd.to_datetime(d.date)
    s = d.value.astype(float); s = s[~s.index.duplicated(keep='last')]
    return s.iloc[1:]  # 첫 행 50.0 은 시작 자리값으로 보여 제외
def netliq():
    w = f('WALCL') / 1e3; t = f('WTREGEN') / 1e3; r = f('RRPONTSYD')      # 십억달러
    r = r.reindex(r.index.union(w.index)).ffill().reindex(w.index)
    t = t.reindex(w.index).ffill()
    return w - t - r
def rai():
    """골드만 위험선호지표(RAI) 공개 복제판: 자산별 20일 위험조정 수익(20일 수익 ÷ 일간변동σ60×√20)의 동일가중 평균.
    주식(SPY·EEM) · 신용(HYG/IEF) · 환율(AUDJPY) · 경기(구리/금) · 금리(10년물 상승=위험선호)."""
    parts = {}
    for nm, s in {'SPY': y('SPY'), 'EEM': y('EEM'), 'HYIEF': y('HYG') / y('IEF'), 'AUDJPY': y('AUDJPY_X'), 'CUAU': y('HG_F') / y('GC_F')}.items():
        r = np.log(s / s.shift(1)); parts[nm] = (np.log(s / s.shift(20))) / (r.rolling(60).std() * np.sqrt(20))
    tn = y('TNX'); dr = tn.diff(); parts['UST10'] = (tn - tn.shift(20)) / (dr.rolling(60).std() * np.sqrt(20))
    P = pd.DataFrame(parts).dropna(); return P.mean(1)

def build(kdates, thr=80):
    """thr: 상단 문턱 백분위(하단은 100-thr). R1 격자에서 바꾼다."""
    lo = 100 - thr; S = {}; G = {}
    vix = y('VIX'); v3 = y('VIX3M')
    S['VIX 수준 상위'] = align(pct(vix) >= thr, 'yahoo', kdates); G['VIX 수준 상위'] = '1 변동성'
    S['VIX/VIX3M ≥ 1(역전)'] = align((vix / v3).dropna() >= {80: 1.0, 70: .95, 75: .975, 85: 1.025, 90: 1.05}[thr], 'yahoo', kdates); G['VIX/VIX3M ≥ 1(역전)'] = '1 변동성'
    S['SKEW 상위'] = align(pct(y('SKEW')) >= thr, 'yahoo', kdates); G['SKEW 상위'] = '1 변동성'
    S['Baa-10년 스프레드 상위'] = align(pct(f('BAA10Y')) >= thr, 'fred', kdates); G['Baa-10년 스프레드 상위'] = '2 신용'
    S['HYG/IEF 20일 하위'] = align(pct(lret(y('HYG') / y('IEF'), 20)) <= lo, 'yahoo', kdates); G['HYG/IEF 20일 하위'] = '2 신용'
    S['10년물 20일 상승 상위'] = align(pct(chg(y('TNX'), 20)) >= thr, 'yahoo', kdates); G['10년물 20일 상승 상위'] = '3 금리'
    S['장단기(10-2) 역전'] = align(f('T10Y2Y') < {80: 0, 70: .5, 75: .25, 85: -.25, 90: -.5}[thr], 'fred', kdates); G['장단기(10-2) 역전'] = '3 금리'
    S['달러지수 20일 상승 상위'] = align(pct(lret(y('DX-Y.NYB'), 20)) >= thr, 'yahoo', kdates); G['달러지수 20일 상승 상위'] = '4 달러'
    S['원/달러 20일 상승 상위'] = align(pct(lret(y('KRW_X'), 20)) >= thr, 'yahoo', kdates); G['원/달러 20일 상승 상위'] = '4 달러'
    nl = netliq()
    S['순유동성 4주 변화 하위'] = align(pct(chg(nl, 4), 100) <= lo, 'h41', kdates); G['순유동성 4주 변화 하위'] = '5 유동성'
    S['순유동성 13주 변화 하위'] = align(pct(chg(nl, 13), 100) <= lo, 'h41', kdates); G['순유동성 13주 변화 하위'] = '5 유동성'
    c = cnn(); g = {80: 80, 70: 70, 75: 75, 85: 85, 90: 90}[thr]
    S['CNN 극단탐욕(역발상)'] = align(c >= g, 'yahoo', kdates); G['CNN 극단탐욕(역발상)'] = '6 심리'
    S['CNN 극단공포(추세)'] = align(c <= 100 - g, 'yahoo', kdates); G['CNN 극단공포(추세)'] = '6 심리'
    S['NAAIM 과열 상위(역발상)'] = align(pct(naaim(), 100) >= thr, 'naaim', kdates); G['NAAIM 과열 상위(역발상)'] = '6 심리'
    S['OFR 스트레스 상위'] = align(pct(pd.read_csv(f'{R}/ofr_fsi.csv', dtype={'date': str}).set_index('date').value.pipe(lambda s: s.set_axis(pd.to_datetime(s.index)))) >= thr, 'ofr', kdates); G['OFR 스트레스 상위'] = '7 스트레스지수'
    S['시카고연준 NFCI 상위'] = align(pct(f('NFCI'), 100) >= thr, 'nfci', kdates); G['시카고연준 NFCI 상위'] = '7 스트레스지수'
    S['세인트루이스 STLFSI 상위'] = align(pct(f('STLFSI4'), 100) >= thr, 'stl', kdates); G['세인트루이스 STLFSI 상위'] = '7 스트레스지수'
    r = rai()
    S['골드만RAI 복제 하위(추세)'] = align(pct(r) <= lo, 'yahoo', kdates); G['골드만RAI 복제 하위(추세)'] = '8 골드만 RAI'
    S['골드만RAI 복제 상위(역발상)'] = align(pct(r) >= thr, 'yahoo', kdates); G['골드만RAI 복제 상위(역발상)'] = '8 골드만 RAI'
    kc = y('KC_F')
    S['[대조] 커피 20일 상승 상위'] = align(pct(lret(kc, 20)) >= thr, 'yahoo', kdates); G['[대조] 커피 20일 상승 상위'] = '대조'
    S['[대조] 커피 수준 상위'] = align(pct(kc) >= thr, 'yahoo', kdates); G['[대조] 커피 수준 상위'] = '대조'
    return S, G
