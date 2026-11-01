import csv, json, statistics, random
from datetime import date, timedelta

SECTORS = ['반도체','자동차','이차전지','바이오헬스','화장품']
TICKER_OF = {'반도체':'반도체','자동차':'자동차','이차전지':'이차전지','바이오헬스':'바이오헬스','화장품':'화장품'}

# ---- load trade data ----
exp = {s: {} for s in SECTORS}
with open('sector_trade_monthly.csv', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        s = row['sector']
        if s in exp:
            exp[s][row['yyyymm']] = int(row['expDlr'])

def ym_add(ym, k):
    y = int(ym[:4]); m = int(ym[4:6])
    idx = y*12 + (m-1) + k
    y2 = idx // 12
    m2 = idx % 12 + 1
    return f"{y2}{m2:02d}"

months_all = sorted(exp['반도체'].keys())

# YoY growth
yoy = {s: {} for s in SECTORS}
for s in SECTORS:
    for m in months_all:
        prev = ym_add(m, -12)
        if prev in exp[s] and exp[s][prev] != 0:
            yoy[s][m] = exp[s][m] / exp[s][prev] - 1.0

# 3m trailing avg yoy (of prior 3 months, excluding current) for acceleration signal
accel = {s: {} for s in SECTORS}
for s in SECTORS:
    for m in months_all:
        prevs = [ym_add(m, -k) for k in (1,2,3)]
        vals = [yoy[s][p] for p in prevs if p in yoy[s]]
        if len(vals) == 3 and m in yoy[s]:
            accel[s][m] = yoy[s][m] - sum(vals)/3

# ---- load prices ----
prices = json.load(open('sector_etf_prices.json', encoding='utf-8'))
trading_days = sorted(prices['KODEX200'].keys())  # YYYYMMDD strings

def first_trading_day_on_or_after(yyyymmdd):
    for d in trading_days:
        if d >= yyyymmdd:
            return d
    return None

def entry_date_for_month(m):
    # signal for month m available ~15th of m+1; use 16th to be safe
    nxt = ym_add(m, 1)
    target = f"{nxt}16"
    return first_trading_day_on_or_after(target)

# ---- build signal/return panel ----
records = []  # each: {month, sector, yoy, accel, fwd_ret, kospi_ret, entry, exit}
valid_months = [m for m in months_all if m >= '201901' and m <= '202606']
for m in valid_months:
    ed = entry_date_for_month(m)
    xd = entry_date_for_month(ym_add(m,1))
    if ed is None or xd is None or ed not in trading_days or xd not in trading_days:
        continue
    if ed >= xd:
        continue
    kospi_ret = prices['KODEX200'][xd] / prices['KODEX200'][ed] - 1.0
    row = {'month': m, 'entry': ed, 'exit': xd, 'kospi_ret': kospi_ret, 'sectors': {}}
    ok = True
    for s in SECTORS:
        if m not in yoy[s] or ed not in prices[s] or xd not in prices[s]:
            ok = False
            break
        fwd = prices[s][xd] / prices[s][ed] - 1.0
        row['sectors'][s] = {'yoy': yoy[s][m], 'accel': accel[s].get(m), 'fwd_ret': fwd}
    if ok:
        records.append(row)

print(f"usable months: {len(records)}  ({records[0]['month']} ~ {records[-1]['month']})")

def tstat(xs):
    n = len(xs)
    if n < 2:
        return float('nan')
    m = statistics.mean(xs)
    sd = statistics.stdev(xs)
    if sd == 0:
        return float('nan')
    return m / sd * (n ** 0.5)

def run_strategy(signal_key, label):
    print(f"\n===== signal: {label} ({signal_key}) =====")
    top1_excess_kospi = []
    top1_excess_ew = []
    top2_excess_kospi = []
    bottom1_excess_kospi = []
    ic_list = []  # spearman-ish: rank corr between signal and fwd_ret within month
    usable = [r for r in records if all(r['sectors'][s].get(signal_key) is not None for s in SECTORS)]
    for r in usable:
        secs = r['sectors']
        ranked = sorted(SECTORS, key=lambda s: secs[s][signal_key], reverse=True)
        ew_ret = sum(secs[s]['fwd_ret'] for s in SECTORS) / len(SECTORS)
        top1 = ranked[0]
        bottom1 = ranked[-1]
        top2 = ranked[:2]
        top1_excess_kospi.append(secs[top1]['fwd_ret'] - r['kospi_ret'])
        top1_excess_ew.append(secs[top1]['fwd_ret'] - ew_ret)
        top2_ret = sum(secs[s]['fwd_ret'] for s in top2) / 2
        top2_excess_kospi.append(top2_ret - r['kospi_ret'])
        bottom1_excess_kospi.append(secs[bottom1]['fwd_ret'] - r['kospi_ret'])
        # rank IC (Spearman) within the 5-sector cross-section this month
        sig_rank = {s: i for i, s in enumerate(sorted(SECTORS, key=lambda s: secs[s][signal_key]))}
        ret_rank = {s: i for i, s in enumerate(sorted(SECTORS, key=lambda s: secs[s]['fwd_ret']))}
        n = len(SECTORS)
        d2 = sum((sig_rank[s]-ret_rank[s])**2 for s in SECTORS)
        spearman = 1 - 6*d2/(n*(n**2-1))
        ic_list.append(spearman)

    n = len(usable)
    print(f"n months={n}")
    print(f"Top1 vs KODEX200: mean={statistics.mean(top1_excess_kospi)*100:.3f}%p t={tstat(top1_excess_kospi):.2f} win={sum(1 for x in top1_excess_kospi if x>0)/n*100:.1f}%")
    print(f"Top1 vs EqualWeight5: mean={statistics.mean(top1_excess_ew)*100:.3f}%p t={tstat(top1_excess_ew):.2f} win={sum(1 for x in top1_excess_ew if x>0)/n*100:.1f}%")
    print(f"Top2 vs KODEX200: mean={statistics.mean(top2_excess_kospi)*100:.3f}%p t={tstat(top2_excess_kospi):.2f}")
    print(f"Bottom1 vs KODEX200 (placebo, should be worse if signal works): mean={statistics.mean(bottom1_excess_kospi)*100:.3f}%p t={tstat(bottom1_excess_kospi):.2f}")
    print(f"Mean rank-IC (Spearman, signal vs fwd_ret, 5-sector cross-section): {statistics.mean(ic_list):.3f}  (t={tstat(ic_list):.2f})")

    # train/test split
    half = n // 2
    train = top1_excess_kospi[:half]
    test = top1_excess_kospi[half:]
    print(f"train(n={len(train)}) mean={statistics.mean(train)*100:.3f}%p t={tstat(train):.2f} | test(n={len(test)}) mean={statistics.mean(test)*100:.3f}%p t={tstat(test):.2f}")

    # leave-one-sector-out jackknife on top1-vs-kospi mean
    print("jackknife (leave-one-sector-out, recompute top1 among remaining 4):")
    for excl in SECTORS:
        remain = [s for s in SECTORS if s != excl]
        vals = []
        for r in usable:
            secs = r['sectors']
            ranked = sorted(remain, key=lambda s: secs[s][signal_key], reverse=True)
            top1 = ranked[0]
            vals.append(secs[top1]['fwd_ret'] - r['kospi_ret'])
        print(f"  exclude {excl}: mean={statistics.mean(vals)*100:.3f}%p t={tstat(vals):.2f}")

    # placebo shuffle test: shuffle signal across sectors within each month, rerun top1 500 times
    random.seed(42)
    placebo_means = []
    for _ in range(500):
        vals = []
        for r in usable:
            secs = r['sectors']
            sig_vals = [secs[s][signal_key] for s in SECTORS]
            random.shuffle(sig_vals)
            shuffled = dict(zip(SECTORS, sig_vals))
            top1 = max(SECTORS, key=lambda s: shuffled[s])
            vals.append(secs[top1]['fwd_ret'] - r['kospi_ret'])
        placebo_means.append(statistics.mean(vals))
    obs = statistics.mean(top1_excess_kospi)
    p = sum(1 for x in placebo_means if x >= obs) / len(placebo_means)
    print(f"placebo shuffle (500x): mean={statistics.mean(placebo_means)*100:.3f}%p sd={statistics.stdev(placebo_means)*100:.3f}%p  observed={obs*100:.3f}%p  p={p:.3f}")

    # cumulative return top1 vs kospi vs equal-weight-5
    cum_top1, cum_kospi, cum_ew = 1.0, 1.0, 1.0
    for r in usable:
        secs = r['sectors']
        ranked = sorted(SECTORS, key=lambda s: secs[s][signal_key], reverse=True)
        top1 = ranked[0]
        ew_ret = sum(secs[s]['fwd_ret'] for s in SECTORS) / len(SECTORS)
        cum_top1 *= (1 + secs[top1]['fwd_ret'])
        cum_kospi *= (1 + r['kospi_ret'])
        cum_ew *= (1 + ew_ret)
    print(f"cumulative return over {n} months: Top1={((cum_top1-1)*100):.1f}%  KODEX200={((cum_kospi-1)*100):.1f}%  EqualWeight5={((cum_ew-1)*100):.1f}%")
    return usable, top1_excess_kospi

u1, e1 = run_strategy('yoy', 'raw YoY level')
u2, e2 = run_strategy('accel', 'YoY acceleration (vs 3m trailing avg)')

# dump per-month detail for report
with open('backtest_detail.csv', 'w', encoding='utf-8', newline='') as f:
    w = csv.writer(f)
    w.writerow(['month','entry','exit','kospi_ret'] + [f'{s}_yoy' for s in SECTORS] + [f'{s}_fwdret' for s in SECTORS])
    for r in records:
        w.writerow([r['month'], r['entry'], r['exit'], r['kospi_ret']] +
                    [r['sectors'][s]['yoy'] for s in SECTORS] +
                    [r['sectors'][s]['fwd_ret'] for s in SECTORS])
print("\nsaved backtest_detail.csv")
