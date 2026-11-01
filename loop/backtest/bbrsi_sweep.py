# -*- coding: utf-8 -*-
"""구간별 예측력 스윕 — RSI 십분위 / %B 십분위 / 밴드폭 오분위.

유니버스 등가중 평균 대비(=선정 우위)와 KODEX200 대비를 함께 본다.
표준오차는 일자 클러스터.
"""
import sys, os, math
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bbrsi_engine import build_cache, get, is_excluded, is_cashlike, BENCH
from fib_engine import date_clustered_t, jackknife_low

MINP = 10000


def build_obs(cache, name, dates, hold=1, warm=140):
    obs = []
    be = cache[BENCH]
    for i in range(warm, len(dates) - hold):
        d = dates[i]; dn = dates[i + hold]
        bi = be['idx'].get(d); bj = be['idx'].get(dn)
        if bi is None or bj is None:
            continue
        bench = (be['px'][bj] / be['px'][bi]) ** (1.0 / hold) - 1.0
        for code, e in cache.items():
            nm = name[code]
            if is_excluded(nm) or is_cashlike(nm):
                continue
            ii = e['idx'].get(d); jj = e['idx'].get(dn)
            if ii is None or jj is None:
                continue
            p = e['px'][ii]
            if p < MINP:
                continue
            r = (e['px'][jj] / p) ** (1.0 / hold) - 1.0
            obs.append((d, code, {
                'rsi9': e['rsi9'][ii], 'rsi14': e['rsi14'][ii], 'rsi25': e['rsi25'][ii],
                'pctb2.0': e['pctb2.0'][ii], 'pctb1.5': e['pctb1.5'][ii],
                'bwpct': e['bwpct'][ii], 'mom20': e['mom20'][ii],
            }, r - bench))
    return obs


def report(obs, keyfn, labels, title, baseline):
    by = defaultdict(lambda: defaultdict(list))
    for d, code, f, ex in obs:
        lab = keyfn(f)
        if lab is None:
            continue
        by[lab][d].append(ex)
    print(f'\n=== {title} ===')
    print(f'{"구간":<20}{"관측":>8}{"일수":>6}{"vsKODEX%":>10}{"vs유니버스%":>12}'
          f'{"t(유니)":>8}{"잭나이프%":>10}{"승률%":>7}')
    for lab in labels:
        if lab not in by:
            continue
        dd = by[lab]
        da = {d: sum(v) / len(v) for d, v in dd.items()}
        rel = [da[d] - baseline[d] for d in da if d in baseline]
        n = sum(len(v) for v in dd.values())
        ma, _, _ = date_clustered_t(list(da.values()))
        mr, tr, nd = date_clustered_t(rel)
        jk = jackknife_low(rel)
        win = sum(1 for d, v in dd.items() for x in v if x - baseline.get(d, 0) > 0)
        print(f'{lab:<20}{n:>8}{nd:>6}{ma*100:>10.4f}{mr*100:>12.4f}{(tr or 0):>8.2f}'
              f'{(jk*100 if jk is not None else 0):>10.4f}{win/n*100:>7.1f}')


def main():
    cache, name, dates = build_cache()
    print(f'유니버스 {len(cache)}종 · 거래일 {len(dates)} ({dates[0]}~{dates[-1]})')
    for hold in (1, 3):
        obs = build_obs(cache, name, dates, hold)
        base = defaultdict(list)
        for d, code, f, ex in obs:
            base[d].append(ex)
        baseline = {d: sum(v) / len(v) for d, v in base.items()}
        mb, tb, ndb = date_clustered_t(list(baseline.values()))
        print(f'\n\n######## 보유 {hold}일(1일환산) · 관측 {len(obs):,} ########')
        print(f'유니버스 등가중 기준선: vs KODEX200 {mb*100:+.4f}%/일 (t={tb:.2f}, {ndb}일)')

        # RSI 십분위
        for n in (9, 14, 25):
            edges = list(range(0, 101, 10))
            labels = [f'RSI{n} {edges[i]}~{edges[i+1]}' for i in range(10)]

            def kf(f, _n=n, _e=edges):
                v = f[f'rsi{_n}']
                if v is None:
                    return None
                for i in range(10):
                    if _e[i] <= v < _e[i + 1] or (i == 9 and v >= 100):
                        return f'RSI{_n} {_e[i]}~{_e[i+1]}'
                return None
            report(obs, kf, labels, f'h={hold} RSI({n}) 십분위', baseline)

        # %B 십분위 (하단 이탈/상단 이탈 별도)
        labels = ['%B <0 (하단이탈)'] + [f'%B {i/10:.1f}~{(i+1)/10:.1f}' for i in range(10)] \
                 + ['%B >1 (상단이탈)']

        def kf2(f):
            v = f['pctb2.0']
            if v is None:
                return None
            if v < 0:
                return '%B <0 (하단이탈)'
            if v > 1:
                return '%B >1 (상단이탈)'
            i = min(int(v * 10), 9)
            return f'%B {i/10:.1f}~{(i+1)/10:.1f}'
        report(obs, kf2, labels, f'h={hold} 볼린저 %B (20,2.0) 구간', baseline)

        # 밴드폭 백분위 오분위
        labels = [f'밴드폭 {i*20}~{(i+1)*20}%' for i in range(5)]

        def kf3(f):
            v = f['bwpct']
            if v is None:
                return None
            i = min(int(v * 5), 4)
            return f'밴드폭 {i*20}~{(i+1)*20}%'
        report(obs, kf3, labels, f'h={hold} 밴드폭 백분위(0=최협착) 오분위', baseline)

        # 고전 조합: 과매도 + 하단 / 과매수 + 상단
        labels = ['RSI<30 & %B<0.1', 'RSI<30', '%B<0.1',
                  'RSI>70 & %B>0.9', 'RSI>70', '%B>0.9',
                  '스퀴즈(bw<20%) & %B>0.8', '스퀴즈(bw<20%) & %B<0.2']

        def kf4(f):
            r = f['rsi14']; b = f['pctb2.0']; w = f['bwpct']
            if r is None or b is None:
                return None
            if r < 30 and b < 0.1:
                return 'RSI<30 & %B<0.1'
            if r > 70 and b > 0.9:
                return 'RSI>70 & %B>0.9'
            if w is not None and w < 0.2 and b > 0.8:
                return '스퀴즈(bw<20%) & %B>0.8'
            if w is not None and w < 0.2 and b < 0.2:
                return '스퀴즈(bw<20%) & %B<0.2'
            if r < 30:
                return 'RSI<30'
            if r > 70:
                return 'RSI>70'
            if b < 0.1:
                return '%B<0.1'
            if b > 0.9:
                return '%B>0.9'
            return None
        report(obs, kf4, labels, f'h={hold} 고전 시그널 조합 (상호배타)', baseline)


if __name__ == '__main__':
    main()
