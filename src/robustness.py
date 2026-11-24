"""
Robustness checks for the event study (preferred model unless noted).

1. Volatility-robust inference. A constant-volatility t-stat overstates
   significance when the stock is in a turbulent regime. Each event-day abnormal
   return is re-standardized by a GARCH(1,1) conditional volatility (Student-t
   innovations), fit on the estimation window and filtered forward with fixed
   parameters, so sigma_t uses only information up to t-1.
   Because the episode's own shocks raise sigma_t for later events, we also
   report z using the GARCH sigma frozen at the pre-episode level (BASE). The
   two readings bracket the answer; for E2 they disagree.
2. Specification grid. Event-day abnormal returns across estimation windows
   (120 / 250 / 500 days) x market benchmarks (S&P 500 ex-NVDA, equal-weight
   S&P 500, SPY, QQQ) x with/without the chip-peer factor = 24 specifications.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from arch import arch_model
from scipy import stats

from config import (BASE, EST_END, EST_LEN, MODELS, OUT, PREFERRED, car_simple,
                    load_events, load_returns, load_shares)

ret, px = load_returns()
events = load_events()
SHARES = load_shares()
EVENT_ID = dict(zip(events.date, events.event_id))


def fit_model(xs, est_len, est_end=EST_END):
    est = ret.loc[:est_end].tail(est_len)
    m = sm.OLS(est["NVDA"], sm.add_constant(est[xs])).fit()
    full = ret.loc[est.index[0]:]
    predicted = m.predict(sm.add_constant(full[xs], has_constant="add"))
    return m, full["NVDA"] - predicted, predicted


# --- 1. Volatility-robust inference -----------------------------------------
xs = MODELS[PREFERRED]
m, ar, predicted = fit_model(xs, EST_LEN)
est_idx = ar.loc[:EST_END].index
gfit = arch_model(ar.loc[est_idx] * 100, mean="Zero", vol="GARCH", p=1, q=1, dist="t").fit(disp="off")
cond_sd = arch_model(ar * 100, mean="Zero", vol="GARCH", p=1, q=1, dist="t").fix(gfit.params) \
    .conditional_volatility / 100
nu = gfit.params["nu"]
t_scale = np.sqrt((nu - 2) / nu)   # standardized Student-t -> scipy's t


def p_garch(z):
    return 2 * stats.t.sf(abs(z) / t_scale, nu)


const_sd = np.sqrt(m.mse_resid)
sd_pre = cond_sd.loc[BASE]   # conditional sigma just before the episode
# sd_pre is the forecast for BASE itself; the forecast for the next day is close.
rows = []
for _, e in events.iterrows():
    a = ar.loc[e.date]
    z_g, z_pre = a / cond_sd.loc[e.date], a / sd_pre
    rows.append(dict(event=e.event_id, label=e.label,
                     AR_pct=car_simple([ret.loc[e.date, "NVDA"]], [predicted.loc[e.date]]) * 100,
                     sd_const=const_sd * 100, t_const=a / const_sd,
                     sd_garch=cond_sd.loc[e.date] * 100, z_garch=z_g, p_garch=p_garch(z_g),
                     sd_garch_pre=sd_pre * 100, z_garch_pre=z_pre, p_garch_pre=p_garch(z_pre)))
vol = pd.DataFrame(rows)
vol.to_csv(OUT / "robust_volatility.csv", index=False)
cond_sd.loc["2026-10-01":].mul(100).round(3).rename("garch_sd_pct").to_csv(OUT / "garch_conditional_sd.csv")
pd.set_option("display.width", 220)
print("GARCH(1,1)-t params:", gfit.params.round(4).to_dict(),
      f"persistence={gfit.params['alpha[1]'] + gfit.params['beta[1]']:.3f}")
print("\nVolatility-robust inference (preferred model):\n", vol.round(3).to_string(index=False))

# --- 2. Specification grid --------------------------------------------------
grid = []
for est_len in [120, 250, 500]:
    for bench in ["SPYX", "RSP", "SPY", "QQQ"]:
        for industry in [False, True]:
            xs_ = [bench] + (["CHIPS"] if industry else [])
            mm, a, pr = fit_model(xs_, est_len)
            sd = np.sqrt(mm.mse_resid)
            r = dict(est_len=est_len, benchmark=bench, chip_factor=industry, R2=mm.rsquared)
            for d, key in EVENT_ID.items():
                r[f"{key}_AR"] = car_simple([ret.loc[d, "NVDA"]], [pr.loc[d]]) * 100
                r[f"{key}_t"] = a.loc[d] / sd
                prev_close = px["NVDA"].loc[ret.index[ret.index.get_loc(d) - 1]]
                r[f"{key}_usd_bn"] = r[f"{key}_AR"] / 100 * prev_close * SHARES / 1e9
            grid.append(r)
grid = pd.DataFrame(grid)
grid.to_csv(OUT / "robust_spec_grid.csv", index=False)
show = [c for c in grid.columns if not c.endswith("usd_bn")]
print(f"\nSpecification grid ({len(grid)} specs, event-day abnormal returns %):\n",
      grid[show].round(2).to_string(index=False))
for k in EVENT_ID.values():
    print(f"{k}: AR {grid[f'{k}_AR'].min():.1f}% to {grid[f'{k}_AR'].max():.1f}%  "
          f"(${grid[f'{k}_usd_bn'].min():,.0f}B to ${grid[f'{k}_usd_bn'].max():,.0f}B), "
          f"t {grid[f'{k}_t'].min():.2f} to {grid[f'{k}_t'].max():.2f}, "
          f"|t|>1.96 in {(grid[f'{k}_t'].abs() > 1.96).sum()}/{len(grid)}")
