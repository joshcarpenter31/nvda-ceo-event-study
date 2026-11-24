"""
Synthetic tracking portfolio: what would NVDA have done over the episode if it
had moved like a fixed mix of comparable stocks?

Weights are non-negative, sum to one, and minimise daily-return tracking error
over a pre-period (a returns-based variant of synthetic control; the classic
Abadie-Diamond-Hainmueller method matches *levels* of an outcome). After BASE
the weights are frozen; actual minus synthetic is the estimated gap.

Caveats built into the outputs:
  * Pre-period noise band: the SD of same-length cumulative tracking gaps in
    the fit window, so a post-period gap can be read against normal drift.
  * Placebos: the same procedure treats each donor as if it were NVDA. With 10
    donors the smallest attainable permutation p-value is 1/11 = 0.09.
  * Donor contamination: some donors (TSM, AVGO) reacted to the NVDA news. The
    fit is re-run on non-chip donors and without TSM to check this matters.

Donors exclude ETFs that hold NVDA (SPY, QQQ, SMH); the S&P 500 ex-NVDA is used.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from config import BASE, EST_END, MEGACAPS, OUT, PEERS, SYNTH_PRE_START, load_events, load_returns

ret, _ = load_returns()
events = load_events()
assert pd.Timestamp(BASE) in ret.index, "BASE must be a trading day"
DONORS = ["SPYX"] + PEERS + MEGACAPS
END = events.date.max()
post_idx = ret.index[(ret.index > BASE) & (ret.index <= END)]


def fit_weights(y, X):
    k = X.shape[1]
    res = minimize(lambda w: np.sum((y - X @ w) ** 2), np.full(k, 1 / k), method="SLSQP",
                   bounds=[(0, 1)] * k, constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
                   options={"ftol": 1e-12, "maxiter": 1000})
    assert res.success, res.message
    return res.x


def synth(target, donors):
    pre = ret.loc[SYNTH_PRE_START:EST_END]
    w = pd.Series(fit_weights(pre[target].values, pre[donors].values), index=donors)
    pre_gap = pre[target] - pre[donors] @ w
    post = ret.loc[post_idx]
    gap = (post[target] - post[donors] @ w).cumsum()           # cumulative log gap
    return w, gap, pre_gap


w, gap, pre_gap = synth("NVDA", DONORS)
rmse = np.sqrt(np.mean(pre_gap ** 2))
# Noise band: SD of h-day cumulative tracking gaps in the pre-period
band = {h: pre_gap.rolling(h).sum().std() for h in range(1, len(post_idx) + 1)}

weights = w[w > 0.005].sort_values(ascending=False)
weights.rename("weight").to_csv(OUT / "synthetic_control_weights.csv")
print("Synthetic NVDA weights:\n", weights.round(3).to_string())
print(f"Pre-period daily tracking RMSE: {rmse * 100:.2f}%")

post = ret.loc[post_idx]
path = pd.DataFrame({
    "actual": np.exp(post["NVDA"].cumsum()) * 100,
    "synthetic": np.exp((post[DONORS] @ w).cumsum()) * 100,
    "gap_pct": np.expm1(gap) * 100,
    "band_1sd_pct": [np.expm1(band[i + 1]) * 100 for i in range(len(post_idx))],
})
path = pd.concat([pd.DataFrame({"actual": [100.0], "synthetic": [100.0], "gap_pct": [0.0],
                                "band_1sd_pct": [0.0]}, index=[pd.Timestamp(BASE)]), path])
path.to_csv(OUT / "synthetic_control_path.csv")
pd.set_option("display.width", 200)
print("\n", path.round(2).to_string())

# --- Placebos -----------------------------------------------------------------
placebo = {t: synth(t, [d for d in DONORS if d != t]) for t in DONORS if t != "SPYX"}
gaps = pd.DataFrame({t: np.expm1(g) * 100 for t, (_, g, _) in placebo.items()})
gaps["NVDA"] = np.expm1(gap) * 100
gaps.to_csv(OUT / "synthetic_control_placebos.csv")

rank = gaps.apply(lambda r: int((r.drop("NVDA").abs() >= abs(r["NVDA"])).sum()) + 1, axis=1)
print("\nNVDA's rank by |gap| each day (1 = most extreme of 11):\n", rank.to_string())


def rmspe_ratio(g, pre):
    daily = g.diff().fillna(g.iloc[0])
    return np.sqrt(np.mean(daily ** 2)) / np.sqrt(np.mean(pre ** 2))


ratios = {t: rmspe_ratio(g, p) for t, (_, g, p) in placebo.items()}
ratios["NVDA"] = rmspe_ratio(gap, pre_gap)
ratio_rank = sum(v >= ratios["NVDA"] for k, v in ratios.items() if k != "NVDA") + 1
print(f"Post/pre RMSPE ratio: NVDA {ratios['NVDA']:.2f}; placebos "
      f"{min(v for k, v in ratios.items() if k != 'NVDA'):.2f}-{max(v for k, v in ratios.items() if k != 'NVDA'):.2f}; "
      f"rank {ratio_rank}/{len(ratios)} (permutation p = {ratio_rank / len(ratios):.2f}, minimum attainable 0.09)")

# --- Donor-pool sensitivity --------------------------------------------------
variants = {
    "All donors": DONORS,
    "Excluding TSM": [d for d in DONORS if d != "TSM"],
    "Non-chip donors only": ["SPYX"] + MEGACAPS,
}
sens = []
for name, pool in variants.items():
    _, g, p = synth("NVDA", pool)
    sens.append(dict(donor_pool=name, pre_rmse_pct=np.sqrt(np.mean(p ** 2)) * 100,
                     trough_gap_pct=np.expm1(g.min()) * 100, trough_date=g.idxmin().date(),
                     final_gap_pct=np.expm1(g.iloc[-1]) * 100))
sens = pd.DataFrame(sens)
sens.to_csv(OUT / "synthetic_control_sensitivity.csv", index=False)
summary = pd.DataFrame({
    "daily_rank": rank, "rmspe_ratio_nvda": ratios["NVDA"], "rmspe_rank": ratio_rank,
    "pre_rmse_pct": rmse * 100})
summary.to_csv(OUT / "synthetic_control_summary.csv")
print("\nDonor-pool sensitivity:\n", sens.round(2).to_string(index=False))
final = path.iloc[-1]
print(f"\nFinal gap {final.gap_pct:.1f}% vs 1-SD pre-period band +/-{final.band_1sd_pct:.1f}% "
      f"({final.gap_pct / final.band_1sd_pct:.1f} SD)")
