"""
Event study: how did NVDA's price react to Jensen Huang's investigation,
resignation and reinstatement?

Method (short-horizon event study, MacKinlay 1997):
  1. Estimate "normal" returns over a clean pre-event window by OLS on log returns.
  2. Abnormal return over a window = cumulative actual simple return minus
     cumulative model-predicted simple return (dollar-correct; see config.car_simple).
  3. Test the summed log abnormal return against estimation-window residual
     volatility (t-stat) and against the empirical distribution of same-length
     residual sums (fat-tail-robust p-value).

Models (config.MODELS):
  * market_spyx (preferred): NVDA on the S&P 500 *excluding NVDA*. A cap-weighted
    market factor that fits NVDA well but does not mechanically move with NVDA.
  * market_rsp: NVDA on the equal-weight S&P 500 (robustness).
  * industry: market_spyx + equal-weight chip peers. Strips sector news, but the
    peers themselves reacted to the events (rotation on E1/E2, rally on E3), so
    its bias is event-dependent: it inflates E1/E2 and shrinks E3.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests

from config import (BASE, EST_END, EST_LEN, MEGACAPS, MODELS, OUT, PEERS, PREFERRED,
                    car_simple, load_confounders, load_events, load_returns, load_shares)

ret, px = load_returns()
events = load_events()
confounders = load_confounders()
SHARES = load_shares()

est = ret.loc[:EST_END].tail(EST_LEN)
post = ret.loc[ret.index > EST_END]
dates = ret.index
print(f"Estimation window: {est.index[0].date()} -> {est.index[-1].date()} ({len(est)} days)")


def fit(y, xs, sample=est):
    return sm.OLS(sample[y], sm.add_constant(sample[xs])).fit()


def predict(model, xs, frame):
    return model.predict(sm.add_constant(frame[xs], has_constant="add"))


fits, sigma, pred = {}, {}, {}
daily = pd.DataFrame({"raw": post["NVDA"]})
for name, xs in MODELS.items():
    m = fit("NVDA", xs)
    fits[name], sigma[name] = m, np.sqrt(m.mse_resid)
    pred[name] = predict(m, xs, post)
    daily[name] = post["NVDA"] - pred[name]          # log abnormal return
    daily[f"{name}_simple"] = np.expm1(post["NVDA"]) - np.expm1(pred[name])
    print(f"[{name}] alpha={m.params['const']:.5f} "
          + " ".join(f"beta_{x}={m.params[x]:.3f}" for x in xs)
          + f" R2={m.rsquared:.3f} resid sd={sigma[name]:.4f}")
daily.to_csv(OUT / "daily_abnormal_returns.csv")


def window(day, lo, hi):
    i = dates.get_loc(day)
    if i + lo < 0 or i + hi >= len(dates):
        return None                                   # runs past the data
    return dates[i + lo: i + hi + 1]


def base_cap(first_day):
    """Market cap at the close before the window's first day."""
    i = dates.get_loc(first_day)
    return px["NVDA"].loc[dates[i - 1]] * SHARES


def empirical_p(model, car_log, length):
    sums = model.resid.rolling(length).sum().dropna()
    k = (sums.abs() >= abs(car_log)).sum()
    return (k + 1) / (len(sums) + 1)                  # never reports exactly 0


def summarize(w, name, label, event, win_label, with_p=True):
    car_log = daily.loc[w, name].sum()
    car = car_simple(post.loc[w, "NVDA"], pred[name].loc[w])
    raw = np.expm1(post.loc[w, "NVDA"].sum())
    return dict(event=event, label=label, window=win_label, model=name,
                first_day=w[0].date(), last_day=w[-1].date(), days=len(w),
                raw_pct=raw * 100, CAR_pct=car * 100,
                CAR_usd_bn=car * base_cap(w[0]) / 1e9,
                t_stat=car_log / (sigma[name] * np.sqrt(len(w))),
                p_empirical=empirical_p(fits[name], car_log, len(w)) if with_p else np.nan)


rows = []
for _, e in events.iterrows():
    for lo, hi in [(0, 0), (0, 1), (-1, 1)]:
        w = window(e.date, lo, hi)
        if w is None:
            continue
        for name in MODELS:
            rows.append(summarize(w, name, e.label, e.event_id, f"[{lo},{hi}]"))

# Whole episode, and a split into event days vs. all other days
episode = dates[(dates > BASE) & (dates <= events.date.max())]
event_days = pd.DatetimeIndex(events.date)
other_days = episode.difference(event_days)
for name in MODELS:
    rows.append(summarize(episode, name, "Full episode", "EPISODE", f"{len(episode)} days"))
    rows.append(summarize(other_days, name, "Episode, non-event days", "OTHER_DAYS",
                          f"{len(other_days)} days", with_p=False))

tbl = pd.DataFrame(rows)
tbl.to_csv(OUT / "event_cars.csv", index=False)
pd.set_option("display.width", 220)
cols = ["event", "window", "model", "raw_pct", "CAR_pct", "CAR_usd_bn", "t_stat", "p_empirical"]
print("\n", tbl[cols].round(3).to_string(index=False))

# Confounded days inside the episode
conf = daily.loc[daily.index.isin(confounders.date), ["raw", f"{PREFERRED}_simple"]] * 100
conf["note"] = confounders.set_index("date").reindex(conf.index)["label"].values
print("\nConfounded days (preferred-model abnormal return, %):\n", conf.round(2).to_string())

# --- Spillovers: peers' abnormal returns on event days -----------------------
spill = []
for t in PEERS + MEGACAPS:
    m = fit(t, ["SPYX"])
    s = np.sqrt(m.mse_resid)
    p_ = predict(m, ["SPYX"], post)
    for _, e in events.iterrows():
        a_log = post.loc[e.date, t] - p_.loc[e.date]
        tt = a_log / s
        spill.append(dict(ticker=t, event=e.event_id,
                          AR_pct=(np.expm1(post.loc[e.date, t]) - np.expm1(p_.loc[e.date])) * 100,
                          t_stat=tt, p=2 * stats.t.sf(abs(tt), m.df_resid)))
spill = pd.DataFrame(spill)
# 30 simultaneous tests: control the false discovery rate (Benjamini-Hochberg)
spill["p_bh"] = multipletests(spill["p"], method="fdr_bh")[1]
spill["significant_bh"] = spill["p_bh"] < 0.05
spill.to_csv(OUT / "peer_spillovers.csv", index=False)
print("\nPeer abnormal returns on event days (market model vs S&P 500 ex-NVDA):\n",
      spill.pivot(index="ticker", columns="event", values=["AR_pct", "t_stat", "p_bh"]).round(2).to_string())

# --- Interpretation 1: the "Huang trade" (suppliers minus competitors) ---------
# Primary grouping is fixed by a rule, not by looking at the results:
#   suppliers   = sell components into Nvidia's products (TSMC foundry, Micron HBM)
#   competitors = sell AI accelerators that compete with Nvidia GPUs
#                 (AMD Instinct, Broadcom custom ASICs, Intel Gaudi)
# An earlier draft grouped Intel as a "partner" after seeing the event-day moves;
# that grouping and one that drops Intel are kept as sensitivity checks.
GROUPINGS = {
    "rule_based": (["TSM", "MU"], ["AMD", "AVGO", "INTC"]),
    "intel_excluded": (["TSM", "MU"], ["AMD", "AVGO"]),
    "post_hoc_intel_as_partner": (["TSM", "MU", "INTC"], ["AMD", "AVGO"]),
}
sp_rows = []
for gname, (sup, riv) in GROUPINGS.items():
    spread = ret[sup].mean(axis=1) - ret[riv].mean(axis=1)
    m_sp = sm.OLS(spread.loc[est.index], sm.add_constant(est["SPYX"])).fit()
    sd_sp = np.sqrt(m_sp.mse_resid)
    sp_pred = predict(m_sp, ["SPYX"], post)
    for _, e in events.iterrows():
        a_ = spread.loc[e.date] - sp_pred.loc[e.date]
        k = (m_sp.resid.abs() >= abs(a_)).sum()
        sp_rows.append(dict(grouping=gname, suppliers="+".join(sup), competitors="+".join(riv),
                            event=e.event_id, label=e.label, spread_AR_pct=a_ * 100, t_stat=a_ / sd_sp,
                            p_empirical=(k + 1) / (len(m_sp.resid) + 1),
                            suppliers_raw_pct=np.expm1(ret.loc[e.date, sup]).mean() * 100,
                            competitors_raw_pct=np.expm1(ret.loc[e.date, riv]).mean() * 100))
sp_tbl = pd.DataFrame(sp_rows)
sp_tbl.to_csv(OUT / "supplier_rival_spread.csv", index=False)
print("\nSupplier-minus-competitor abnormal spread on event days:\n",
      sp_tbl.pivot(index="grouping", columns="event", values=["spread_AR_pct", "t_stat"]).round(2).to_string())

# --- Rebound check: how much of the comeback day is a bounce from Nov 20? -------
# Nov 20 was a large negative abnormal day attributed to other news. Some of the
# next day's jump could be that overshoot reversing. Measure NVDA's typical
# next-day abnormal return after big down days over all pre-event history.
pre_all = ret.loc[:EST_END]
m_all = fit("NVDA", MODELS[PREFERRED], pre_all)
res_all = pre_all["NVDA"] - predict(m_all, MODELS[PREFERRED], pre_all)
nxt = pd.DataFrame({"ar": res_all, "next": res_all.shift(-1)}).dropna()
ar1 = sm.OLS(nxt["next"], sm.add_constant(nxt["ar"])).fit(cov_type="HC1")
prev_day = dates[dates.get_loc(events.date.iloc[-1]) - 1]
prev_ar = daily.loc[prev_day, PREFERRED]
reb = [dict(method="AR(1) on abnormal returns", n=len(nxt),
            expected_rebound_pct=(ar1.params["const"] + ar1.params["ar"] * prev_ar) * 100,
            detail=f"rho={ar1.params['ar']:.3f} (t={ar1.tvalues['ar']:.2f})")]
for thr in [-0.04, -0.05, -0.06]:
    big = nxt[nxt["ar"] <= thr]
    reb.append(dict(method=f"Mean next-day AR after AR <= {thr:.0%}", n=len(big),
                    expected_rebound_pct=big["next"].mean() * 100,
                    detail=f"max next-day AR {big['next'].max() * 100:+.1f}%"))
reb = pd.DataFrame(reb)
e3_ar = tbl[(tbl.event == events.event_id.iloc[-1]) &
                    (tbl.window == "[0,0]") & (tbl.model == PREFERRED)]
e3_pct, e3_usd = float(e3_ar.CAR_pct.iloc[0]), float(e3_ar.CAR_usd_bn.iloc[0])
reb["comeback_net_of_rebound_pct"] = e3_pct - reb["expected_rebound_pct"]
reb["comeback_net_of_rebound_usd_bn"] = reb["comeback_net_of_rebound_pct"] / e3_pct * e3_usd
reb.to_csv(OUT / "rebound_check.csv", index=False)
print(f"\nRebound check (prior day {prev_day.date()} abnormal {daily.loc[prev_day, PREFERRED + '_simple']:+.1%}; "
      f"largest pre-event abnormal day {res_all.max():+.1%}):\n", reb.round(2).to_string(index=False))

# --- Interpretation 2: implied odds of Huang's exit ----------------------------
# Back-of-envelope: treat the reinstatement-day abnormal return as the full value
# of having Huang vs. not. Losing him entirely is then a drop of
# 1 - 1/(1 + AR_reinstatement). The cumulative abnormal return since disclosure,
# divided by that, is the share of his exit the market had priced in.
# The 95% band reflects only day-to-day noise in the cumulative abnormal return
# (residual sd x sqrt(days)); it ignores error in the denominator, so it is a
# lower bound on the true uncertainty. Days with other news are flagged.
ar_e3 = daily.loc[events.date.iloc[-1], f"{PREFERRED}_simple"]
full_loss = 1 - 1 / (1 + ar_e3)
cum_ar = (1 + daily.loc[episode, f"{PREFERRED}_simple"]).cumprod() - 1
odds = pd.DataFrame({"cum_AR_pct": cum_ar * 100, "implied_exit_odds_pct": -cum_ar / full_loss * 100})
odds = odds.loc[odds.index < events.date.iloc[-1]]
n_days = np.arange(1, len(odds) + 1)
odds["band_95_pts"] = 1.96 * sigma[PREFERRED] * np.sqrt(n_days) / full_loss * 100
odds["other_news"] = odds.index.isin(confounders.date)
odds.to_csv(OUT / "implied_exit_odds.csv")
print(f"\nImplied full value of Huang: +{ar_e3:.1%} with vs. without (= {full_loss:.1%} of with-Huang value)")
print(odds.round(1).to_string())
