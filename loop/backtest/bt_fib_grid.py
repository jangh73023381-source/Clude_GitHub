# -*- coding: utf-8 -*-
"""6단계 — 되돌림 타깃 정밀 그리드(0.0~1.0) + 과최적화 점검용 요약.

'최적 피보나치 지점'이 존재하는지, 아니면 되돌림이 얕을수록 좋은 단조 관계인지
확인한다. 단조 관계면 피보나치 특유의 지점(0.618 등)은 의미가 없다는 뜻이다.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fib_engine import load
from bt_fib_tracks import run, summarize, pick_fib_target, pick_mom20, show


def main():
    P = load()
    out = {}
    rows = [summarize(*run(P, pick_mom20, 'BASE mom20+RuleH'))]
    for L in (20, 60):
        for t10 in range(0, 11):
            tgt = t10 / 10.0
            r = summarize(*run(
                P, lambda p, i, u, _L=L, _t=tgt: pick_fib_target(p, i, u, _L, _t),
                f'L{L} 타깃 retr={tgt:.1f}'))
            rows.append(r)
    show(rows)
    for r in rows:
        out[r['label']] = r
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'fib_grid_results.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
