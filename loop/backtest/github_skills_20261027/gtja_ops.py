"""GTJA191 계산용 연산자 — Vibe-Trading base.py 의 '정의'를 읽고 직접 구현(저장소 코드는 실행하지 않음).
+ 알파 파일 안전 로더: AST 화이트리스트 검사 후, 검사된 함수 정의만 제한된 이름공간에서 정의한다."""
import ast, numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv


def _f(df):
    return df.astype(float)


def rank(df):
    return df.rank(axis=1, method='average', pct=True, na_option='keep')


def scale(df, a=1.0):
    df = _f(df); s = df.abs().sum(axis=1, skipna=True); s = s.where(s > 0)
    return df.mul(a).div(s, axis=0)


def ts_rank(df, n):
    arr = df.to_numpy(dtype=np.float64); T, C = arr.shape; out = np.full((T, C), np.nan)
    if T >= n:
        for c0 in range(0, C, 300):
            w = swv(arr[:, c0:c0 + 300], n, axis=0); last = w[..., -1:]
            bad = np.isnan(w).any(-1)
            less = (w < last).sum(-1); eq = (w == last).sum(-1)
            pct = (less + 0.5 * (eq + 1)) / n; pct[bad] = np.nan
            out[n - 1:, c0:c0 + 300] = pct
    return pd.DataFrame(out, index=df.index, columns=df.columns)


def _roll(df, n):
    return df.rolling(window=n, min_periods=n)


def ts_corr(x, y, n):
    return _roll(_f(x), n).corr(_f(y)).replace([np.inf, -np.inf], np.nan)


def ts_cov(x, y, n):
    return _roll(_f(x), n).cov(_f(y)).replace([np.inf, -np.inf], np.nan)


def ts_mean(df, n): return _roll(df, n).mean()
def ts_std(df, n): return _roll(df, n).std(ddof=1)
def ts_max(df, n): return _roll(df, n).max()
def ts_min(df, n): return _roll(df, n).min()


def _argx(df, n, fn, fill):
    arr = df.to_numpy(dtype=np.float64); T, C = arr.shape; out = np.full((T, C), np.nan)
    if T >= n:
        for c0 in range(0, C, 300):
            w = swv(arr[:, c0:c0 + 300], n, axis=0); bad = np.isnan(w).any(-1)
            r = fn(np.where(np.isnan(w), fill, w), -1).astype(float); r[bad] = np.nan   # 0 기준(창 시작부터)
            out[n - 1:, c0:c0 + 300] = r
    return pd.DataFrame(out, index=df.index, columns=df.columns)


def ts_argmax(df, n):
    # 원 구현(bottleneck)은 같은 값이면 '가장 최근' 위치를 고른다 → 창을 뒤집어 argmax 후 환산
    return _argx(df, n, lambda w, ax: (n - 1) - np.argmax(w[..., ::-1], ax), -np.inf)


def ts_argmin(df, n):
    return _argx(df, n, lambda w, ax: (n - 1) - np.argmin(w[..., ::-1], ax), np.inf)


def delta(df, d):
    assert d >= 1
    return df - df.shift(d)


def decay_linear(df, n):
    w8 = np.arange(1, n + 1, dtype=float); w8 /= w8.sum()
    arr = df.to_numpy(dtype=np.float64); T, C = arr.shape; out = np.full((T, C), np.nan)
    if T >= n:
        for c0 in range(0, C, 300):
            w = swv(arr[:, c0:c0 + 300], n, axis=0); bad = np.isnan(w).any(-1)
            r = np.einsum('ijk,k->ij', np.where(bad[..., None], 0.0, w), w8); r[bad] = np.nan
            out[n - 1:, c0:c0 + 300] = r
    return pd.DataFrame(out, index=df.index, columns=df.columns)


def signed_power(df, p):
    a = df.to_numpy(dtype=np.float64, na_value=np.nan)
    return pd.DataFrame(np.sign(a) * np.power(np.abs(a), p), index=df.index, columns=df.columns)


def observed_over(*inputs):
    present = None
    for frame, n in inputs:
        seen = frame.notna().astype(float).rolling(n, min_periods=n).min().eq(1.0)
        present = seen if present is None else present & seen
    return present


def safe_div(a, b, eps=1e-12):
    a = _f(a); b = _f(b); bb = b.to_numpy(dtype=np.float64, na_value=np.nan)
    den = pd.DataFrame(bb + eps * np.sign(bb), index=b.index, columns=b.columns)
    return a.div(den).replace([np.inf, -np.inf], np.nan)


def vwap(panel, market=None):
    return panel['vwap']   # 패널에 (O+H+L+C)/4 를 넣어 둔다 = 저장소의 equity_kr 정의


OPS = dict(rank=rank, scale=scale, ts_rank=ts_rank, ts_corr=ts_corr, ts_cov=ts_cov, ts_mean=ts_mean, ts_std=ts_std,
           ts_max=ts_max, ts_min=ts_min, ts_argmax=ts_argmax, ts_argmin=ts_argmin, delta=delta, decay_linear=decay_linear,
           signed_power=signed_power, observed_over=observed_over, safe_div=safe_div, vwap=vwap)

# ---------- 안전 로더 ----------
BAD_NAMES = {'open', 'exec', 'eval', 'compile', '__import__', 'globals', 'locals', 'vars', 'getattr', 'setattr',
             'delattr', 'input', 'breakpoint', 'help', 'memoryview', 'os', 'sys', 'subprocess', 'importlib', 'builtins'}
OK_IMPORTS = {'__future__', 'numpy', 'pandas', 'src.factors.base'}
SAFE_BUILTINS = dict(range=range, len=len, min=min, max=max, abs=abs, float=float, int=int, sum=sum, zip=zip,
                     enumerate=enumerate, list=list, dict=dict, tuple=tuple, isinstance=isinstance, ValueError=ValueError,
                     KeyError=KeyError, bool=bool, round=round, sorted=sorted, any=any, all=all, str=str, set=set,
                     map=map, reversed=reversed, Exception=Exception, ZeroDivisionError=ZeroDivisionError,
                     __build_class__=None)


def load_compute(path):
    src = open(path, encoding='utf-8').read(); tree = ast.parse(src)
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
            if any(m not in OK_IMPORTS for m in mods):
                raise PermissionError(f'금지 import {mods}')
            continue                                    # import 는 실행하지 않고 이름공간을 직접 준비
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.FunctionDef)):
            body.append(node); continue
        raise PermissionError(f'허용 안 된 최상위 구문 {type(node).__name__}')
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id in BAD_NAMES:
            raise PermissionError(f'금지 이름 {n.id}')
        if isinstance(n, ast.Attribute) and n.attr.startswith('_'):
            raise PermissionError(f'금지 속성 {n.attr}')
        if isinstance(n, (ast.Global, ast.Nonlocal, ast.ClassDef, ast.Lambda)) and isinstance(n, ast.ClassDef):
            raise PermissionError('class 금지')
    mod = ast.Module(body=body, type_ignores=[])
    ns = dict(OPS); ns.update(np=np, pd=pd, __builtins__=SAFE_BUILTINS, annotations=None)
    exec(compile(mod, path, 'exec'), ns)              # 검사된 정의(메타 dict·함수)만 실행
    return ns['compute']
