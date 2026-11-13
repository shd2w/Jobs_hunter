"""Experiment 3: simulate the closure guard (doc 09 B6) and the drift detector (B12).
Synthetic boards: Poisson hiring, exponential job lifetimes, scans every 3 h. NOT real data;
it tests whether the *rules* behave sensibly, not how real boards behave."""
import random, statistics as st

def make_board(rng, lam, mean_life, days, freeze_day=None, freeze_frac=0.6):
    jobs = []                        # [start_day, end_day]
    t = -mean_life * 3               # warm-up so day 0 is steady
    while t < days:
        t += rng.expovariate(lam)
        life = rng.expovariate(1 / mean_life)
        jobs.append([t, t + life])
    if freeze_day is not None:       # hiring freeze: 60% of open jobs vanish and hiring drops 60 %
        for j in jobs:
            if j[0] <= freeze_day < j[1] and rng.random() < freeze_frac: j[1] = freeze_day
        jobs = [j for j in jobs if not (j[0] > freeze_day and rng.random() < freeze_frac)]
    return jobs

def run_policy(jobs, days, policy, thr=0.5, k=3, tol=1.15):
    """returns (flag_rate_before_event, stuck_days_after, stale_open_at_end)"""
    open_ids, miss, complete_counts, flagged_buf = set(), {}, [], []
    scans = int(days * 8); flagged_total = 0; flagged_hist = []
    for s in range(scans):
        t = s / 8
        seen = {i for i, j in enumerate(jobs) if j[0] <= t < j[1]}
        n = len(seen); med = st.median(complete_counts[-7:]) if len(complete_counts) >= 5 else None
        guarded = med is not None and med >= 4 and (n < thr * med or (n == 0 and med > 0))
        if policy == "v2" and guarded:
            flagged_buf.append(n)
            if len(flagged_buf) >= k and max(flagged_buf[-k:]) <= tol * max(min(flagged_buf[-k:]), 1):
                guarded = False; flagged_buf = []          # re-baseline: stable new level confirmed
        elif not guarded: flagged_buf = []
        flagged_hist.append(guarded)
        if guarded: continue                                # partial run: no lifecycle change, not in baseline
        complete_counts.append(n)
        for i in seen: open_ids.add(i); miss[i] = 0
        for i in list(open_ids):
            if i not in seen:
                miss[i] = miss.get(i, 0) + 1
                if miss[i] >= 2: open_ids.discard(i)
    end_t = scans / 8
    truly_open = {i for i, j in enumerate(jobs) if j[0] <= end_t < j[1]}
    stale = len(open_ids - truly_open)
    return flagged_hist, stale

def experiment_guard(seeds=200):
    print("== guard: hiring freeze at day 30 (60 % of jobs vanish, hiring -60 %), 60-day run ==")
    print(f"{'board size':>10} {'policy':>6} {'normal-ops flag %':>18} {'runs flagged after freeze (of 240)':>36} {'stale-open jobs at day 60 (mean)':>34}")
    for lam, life, label in ((0.5, 10, "~5"), (2, 10, "~20"), (20, 10, "~200")):
        for pol in ("v1", "v2"):
            fl_norm, fl_after, stale = [], [], []
            for sd in range(seeds):
                rng = random.Random(sd)
                jobs = make_board(rng, lam, life, 60, freeze_day=30)
                hist, stl = run_policy(jobs, 60, pol)
                fl_norm.append(sum(hist[:240]) / 240); fl_after.append(sum(hist[240:])); stale.append(stl)
            print(f"{label:>10} {pol:>6} {100*st.mean(fl_norm):>17.2f}% {st.mean(fl_after):>36.1f} {st.mean(stale):>34.2f}")

def drift(series, floor):
    out = []
    for i in range(14, len(series)):
        w = series[i-14:i]; med = st.median(w); mad = st.median([abs(x - med) for x in w])
        d = max(mad, floor(med))
        z = 0.6745 * (series[i] - med) / d if d > 0 else (0 if series[i] == med else float("inf"))
        out.append(abs(z))
    return out

def experiment_drift(seeds=300):
    print("\n== drift detector on SMALL stable boards (|z|>3.5 = warn) ==")
    for name, fl in (("naive (MAD only)", lambda m: 0), ("floored max(MAD,5%*med,1)", lambda m: max(0.05 * m, 1))):
        fa = tot = det = trials = 0
        for sd in range(seeds):
            rng = random.Random(sd)
            jobs = make_board(rng, 0.4, 14, 90)
            counts = [sum(1 for j in jobs if j[0] <= s/8 < j[1]) for s in range(0, 90*8, 8)]   # one sample per day
            z = drift(counts, fl); fa += sum(1 for x in z if x > 3.5); tot += len(z)
            c2 = counts[:60] + [max(0, int(c * 0.5)) for c in counts[60:]]                        # inject 50 % volume drop at day 60
            z2 = drift(c2, fl); trials += 1; det += any(x > 3.5 for x in z2[60-14:60-14+5])      # detected within 5 days
        print(f"{name:28} false-alarm rate {100*fa/tot:5.2f}% of days | detects injected 50% drop within 5 days: {100*det/trials:5.1f}%")

if __name__ == "__main__":
    experiment_guard(); experiment_drift()
