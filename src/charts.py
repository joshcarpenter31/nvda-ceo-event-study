"""Static PNG charts for the README / LinkedIn post.
Run after event_study.py, robustness.py and synthetic_control.py (run_all.py does this).
All titles and annotations are generated from the output tables."""
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from config import (BASE, MODEL_LABELS, OUT, PEERS, PREFERRED, load_confounders,
                    load_events, load_prices, load_shares)

# Reference palette (light mode): categorical slots 1-3, diverging blue<->red
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA, RED, LIGHTBLUE = "#2a78d6", "#eb6834", "#1baf7a", "#e34948", "#86b6ef"
SHADE = "#f0efec"
SOURCE = "Data: Yahoo Finance adjusted closes. Events: Nvidia board statement and 8-K filings."

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 11, "text.color": INK,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
    "text.parse_math": False,
})

px = load_prices()
events = load_events()
conf = load_confounders()
SHARES = load_shares()
daily = pd.read_csv(OUT / "daily_abnormal_returns.csv", index_col=0, parse_dates=True)
cars = pd.read_csv(OUT / "event_cars.csv")
grid = pd.read_csv(OUT / "robust_spec_grid.csv")
vol = pd.read_csv(OUT / "robust_volatility.csv").set_index("event")

START = "2026-11-02"
EV_SHORT = {"E1": "Probe disclosed", "E2": "Huang resigns", "E3": "Huang reinstated"}
CONF_SHORT = {"2026-11-05": "Chip\nrout", "2026-11-18": "Q3\nearnings", "2026-11-19": "Subpoena\n(rpt.)",
              "2026-11-20": "Selloff +\nSEC rpt."}
conf_days = [pd.Timestamp(d) for d in CONF_SHORT]


def car(event, window="[0,0]", model=PREFERRED, col="CAR_pct"):
    r = cars[(cars.event == event) & (cars.window == window) & (cars.model == model)]
    return float(r[col].iloc[0])


def title(fig, main, sub):
    fig.text(0.015, 0.97, main, fontsize=15, fontweight="bold", va="top")
    fig.text(0.015, 0.905, sub, fontsize=10.5, color=INK2, va="top")


def footer(fig, txt):
    fig.text(0.015, 0.012, txt + "\n" + SOURCE, fontsize=8.3, color=INK2, va="bottom", linespacing=1.4)


def save(fig, name):
    fig.savefig(OUT / name, dpi=200)
    plt.close(fig)


# --- 1. Indexed price path -------------------------------------------------
w = px.loc[START:].copy()
idx = pd.DataFrame({
    "NVDA": w["NVDA"] / w.loc[BASE, "NVDA"] * 100,
    "Chip peers (ex-NVDA)": (w[PEERS] / w.loc[BASE, PEERS]).mean(axis=1) * 100,
    "S&P 500 equal-weight": w["RSP"] / w.loc[BASE, "RSP"] * 100,
})
trough = idx["NVDA"].min()
fig, ax = plt.subplots(figsize=(11, 6.2))
fig.subplots_adjust(left=0.06, right=0.82, top=0.80, bottom=0.14)
for d in conf_days:
    ax.axvspan(d - pd.Timedelta(hours=14), d + pd.Timedelta(hours=14), ymax=0.87, color=SHADE, zorder=0, lw=0)
for (name, s), c in zip(idx.items(), [BLUE, ORANGE, AQUA]):
    ax.plot(s.index, s, color=c, lw=2.2 if name == "NVDA" else 2, label=name, zorder=3)
    ax.scatter(s.index[-1], s.iloc[-1], color=c, s=40, zorder=4, edgecolor=SURFACE, lw=2)
    ax.annotate(f"{name}  {s.iloc[-1]:.0f}", (s.index[-1], s.iloc[-1]), xytext=(10, 0),
                textcoords="offset points", va="center", fontsize=10, color=INK, annotation_clip=False)
ax.axhline(100, color=INK2, lw=0.8)
top = max(idx.max().max() + 8, 120)
ax.set_ylim(idx.min().min() - 5, top)
for _, e in events.iterrows():
    ax.axvline(e.date, color=INK2, lw=1, ls=(0, (3, 3)), zorder=1)
    ax.text(e.date, top - 1, " " + EV_SHORT[e.event_id], fontsize=9, color=INK2, va="top")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.set_ylabel(f"Index ({pd.Timestamp(BASE):%b} {pd.Timestamp(BASE).day} close = 100)")
ax.legend(loc="upper right", bbox_to_anchor=(1.0, 0.93), frameon=False, fontsize=9.5)
title(fig, f"Nvidia lost {100 - trough:.0f}% in two weeks, then got most of it back in one day",
      f"Price indexed to the last close before the investigation was disclosed ({pd.Timestamp(BASE):%b} "
      f"{pd.Timestamp(BASE).day}, 2026). Shaded days carried other news.")
footer(fig, "Chip peers = equal-weight AMD, AVGO, TSM, MU, INTC. Shaded: Nov 5 sector rout; Nov 18-20 earnings, "
            "regulatory reports and a sector selloff.")
save(fig, "01_price_path.png")

# --- 2. Daily abnormal returns (preferred model) ----------------------------
a_pct = daily.loc[START:, f"{PREFERRED}_simple"] * 100
pos = {d: i for i, d in enumerate(a_pct.index)}
sd_pct = vol["sd_const"].iloc[0]
fig, ax = plt.subplots(figsize=(11, 6.2))
fig.subplots_adjust(left=0.07, right=0.97, top=0.80, bottom=0.15)
ymax = a_pct.max() + 9
for d, lab in CONF_SHORT.items():
    i = pos[pd.Timestamp(d)]
    ax.axvspan(i - 0.5, i + 0.5, ymax=0.87, color=SHADE, zorder=0, lw=0)
    ax.text(i, ymax - 5.5, lab, fontsize=7.8, color=INK2, ha="center", va="top", linespacing=1.1)
ax.bar(range(len(a_pct)), a_pct, width=0.62, color=[BLUE if v >= 0 else RED for v in a_pct], zorder=3)
ax.axhline(0, color=INK2, lw=0.8, zorder=4)
for i, v in enumerate(a_pct):
    if abs(v) > 4:
        ax.text(i, v + (0.8 if v > 0 else -0.8), f"{v:+.1f}%", ha="center", va="bottom" if v > 0 else "top",
                fontsize=9.5, color=INK, zorder=5, bbox=dict(boxstyle="square,pad=0.1", fc=SURFACE, ec="none"))
ax.set_ylim(a_pct.min() - 4, ymax)
for _, e in events.iterrows():
    i = pos[e.date]
    ax.axvline(i - 0.45, color=INK2, lw=1, ls=(0, (3, 3)), zorder=1)
    last = e.event_id == events.event_id.iloc[-1]
    ax.text(i - 0.45 + (-0.1 if last else 0.1), ymax - 0.5, EV_SHORT[e.event_id], fontsize=9,
            color=INK2, ha="right" if last else "left", va="top")
ax.set_xticks(range(len(a_pct)), [f"{d:%b} {d.day}" for d in a_pct.index], fontsize=8.5)
ax.set_xlim(-0.7, len(a_pct) - 0.3)
ax.set_ylabel("Abnormal return, % (beyond what the market predicts)")
title(fig, "Nothing else came close to the day Huang came back",
      "Nvidia's daily abnormal return vs. a market model using the S&P 500 excluding Nvidia")
footer(fig, f"{MODEL_LABELS[PREFERRED]}, estimated Oct 2025 - Oct 2026. Typical daily abnormal move: "
            f"+/-{sd_pct:.1f}%. Shaded days carried other news.")
save(fig, "02_abnormal_returns.png")

# --- 3. Dollar value of each event ------------------------------------------
ev_ids = list(events.event_id)
fig, ax = plt.subplots(figsize=(11, 6.2))
fig.subplots_adjust(left=0.08, right=0.97, top=0.80, bottom=0.17)
lo_all, hi_all = [], []
for i, ev in enumerate(ev_ids):
    v = car(ev, col="CAR_usd_bn")
    lo, hi = grid[f"{ev}_usd_bn"].min(), grid[f"{ev}_usd_bn"].max()
    lo_all.append(lo); hi_all.append(hi)
    ax.bar(i, v, width=0.5, color=BLUE if v >= 0 else RED, zorder=3)
    ax.errorbar(i, (lo + hi) / 2, yerr=(hi - lo) / 2, color=INK2, capsize=6, lw=1.2, zorder=4)
    edge = hi if v > 0 else lo
    ax.text(i, edge + (30 if v > 0 else -30), f"{'+' if v > 0 else '-'}${abs(round(v, -1)):,.0f}B\n"
            f"({car(ev):+.1f}%)", ha="center", va="bottom" if v > 0 else "top", fontsize=12, fontweight="bold")
ax.axhline(0, color=INK2, lw=0.8)
ax.set_xticks(range(len(ev_ids)), [f"{EV_SHORT[e]}\n{events.set_index('event_id').loc[e, 'date']:%b} "
                                   f"{events.set_index('event_id').loc[e, 'date'].day}" for e in ev_ids],
              fontsize=11, color=INK)
ax.tick_params(axis="x", length=0)
ax.set_ylim(min(lo_all) - 260, max(hi_all) + 230)
ax.set_ylabel("Abnormal change in market value, $ billions")
e3 = ev_ids[-1]
title(fig, f"The comeback added about ${round(car(e3, col='CAR_usd_bn'), -1):,.0f}B beyond the market's move",
      f"Event-day abnormal change in Nvidia's market value. Bars: preferred model; whiskers: range across "
      f"{len(grid)} specifications.")
footer(fig, f"Abnormal simple return x prior-day market cap ({SHARES / 1e9:.2f}B shares). The reinstatement also "
            "carried the board's statement that U.S. government input left it\nconfident there was no "
            "national-security risk; the two cannot be separated.")
save(fig, "03_dollar_impact.png")

# --- 4. Spillovers on reinstatement day ---------------------------------------
sp = pd.read_csv(OUT / "peer_spillovers.csv")
s3 = sp[sp.event == e3].set_index("ticker").sort_values("AR_pct")
fig, ax = plt.subplots(figsize=(11, 6.2))
fig.subplots_adjust(left=0.10, right=0.97, top=0.80, bottom=0.19)
ax.grid(axis="y", visible=False)
ax.grid(axis="x", visible=True)
ax.barh(s3.index, s3.AR_pct, height=0.6, color=[BLUE if s else LIGHTBLUE for s in s3.significant_bh], zorder=3)
xr = s3.AR_pct.abs().max()
for i, (tk, r) in enumerate(s3.iterrows()):
    off = xr * 0.03
    ax.text(r.AR_pct + (off if r.AR_pct >= 0 else -off), i, f"{r.AR_pct:+.1f}%  (t={r.t_stat:.1f})",
            va="center", ha="left" if r.AR_pct >= 0 else "right", fontsize=9.5)
ax.axvline(0, color=INK2, lw=0.8)
ax.set_xlim(-xr * 1.6, xr * 1.6)
ax.set_xlabel(f"Abnormal return on {pd.Timestamp(events.date.iloc[-1]):%b} {events.date.iloc[-1].day}, % "
              "(market model vs S&P 500 ex-NVDA)")
ax.tick_params(axis="y", length=0, labelcolor=INK)
n_sig = int(s3.significant_bh.sum())
sig_names = ", ".join(s3.index[s3.significant_bh])
ax.legend(handles=[Patch(color=BLUE, label="Significant after multiple-testing correction"),
                   Patch(color=LIGHTBLUE, label="Not significant")], frameon=False, fontsize=9.5, loc="lower right")
title(fig, f"Chip stocks soared too, but only {sig_names} beat what the market predicts" if n_sig
      else "After adjusting for market beta, no peer clearly outperformed",
      "Peers' abnormal returns on reinstatement day. Chip stocks rose a lot, but mostly in line with their high "
      "market betas.")
footer(fig, "Significance: two-sided tests, Benjamini-Hochberg false-discovery-rate correction across all 30 "
            "peer x event tests (q < 0.05).\nThe S&P 500 ex-NVDA itself rose ~3% that day, partly on the same "
            "news, so these are conservative.")
save(fig, "04_spillovers.png")

# --- 5. Synthetic tracking portfolio ------------------------------------------
sc = pd.read_csv(OUT / "synthetic_control_path.csv", index_col=0, parse_dates=True)
pl = pd.read_csv(OUT / "synthetic_control_placebos.csv", index_col=0, parse_dates=True)
pl = pd.concat([pd.DataFrame(0.0, index=[pd.Timestamp(BASE)], columns=pl.columns), pl])
wts = pd.read_csv(OUT / "synthetic_control_weights.csv", index_col=0)["weight"]
summ = pd.read_csv(OUT / "synthetic_control_summary.csv", index_col=0, parse_dates=True)
n_first = int((summ.daily_rank == 1).sum())
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 6.2), gridspec_kw={"width_ratios": [1.15, 1]})
fig.subplots_adjust(left=0.07, right=0.97, top=0.78, bottom=0.17, wspace=0.28)
ax1.plot(sc.index, sc["synthetic"], color=INK2, lw=2, ls=(0, (4, 3)), label="Synthetic NVDA")
ax1.plot(sc.index, sc["actual"], color=BLUE, lw=2.2, label="Actual NVDA")
ax1.fill_between(sc.index, sc["actual"], sc["synthetic"], color=RED, alpha=0.12, lw=0)
for col in ["synthetic", "actual"]:
    ax1.annotate(f"{sc[col].iloc[-1]:.0f}", (sc.index[-1], sc[col].iloc[-1]), xytext=(6, 0),
                 textcoords="offset points", va="center", fontsize=10, color=INK, annotation_clip=False)
ax1.set_title(f"Actual vs. synthetic ({pd.Timestamp(BASE):%b} {pd.Timestamp(BASE).day} = 100)",
              fontsize=11, color=INK, loc="left")
ax1.legend(frameon=False, fontsize=9.5, loc="lower left")
ax2.fill_between(sc.index, -2 * sc.band_1sd_pct, 2 * sc.band_1sd_pct, color=SHADE, lw=0, zorder=0)
for t in pl.columns.drop("NVDA"):
    ax2.plot(pl.index, pl[t], color="#c3c2b7", lw=1.2, zorder=1)
ax2.plot(pl.index, pl["NVDA"], color=BLUE, lw=2.4, zorder=3)
ax2.axhline(0, color=INK2, lw=0.8)
tday = pl["NVDA"].idxmin()
ax2.annotate(f"NVDA {pl['NVDA'].min():+.0f}%", (tday, pl["NVDA"].min()), xytext=(-8, -4),
             textcoords="offset points", ha="right", va="top", fontsize=10, color=INK)
ax2.annotate(f"{pl['NVDA'].iloc[-1]:+.0f}%", (pl.index[-1], pl["NVDA"].iloc[-1]), xytext=(6, 0),
             textcoords="offset points", va="center", fontsize=10, color=INK, annotation_clip=False)
ax2.set_title("Gap vs. synthetic, %: NVDA, 10 placebos, +/-2 SD band", fontsize=11, color=INK, loc="left")
for a_ in (ax1, ax2):
    a_.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    a_.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    a_.tick_params(axis="x", labelsize=9)
mix = ", ".join(f"{k.replace('SPYX', 'S&P ex-NVDA')} {v:.0%}" for k, v in wts.items() if v >= 0.05)
final_sd = sc.gap_pct.iloc[-1] / sc.band_1sd_pct.iloc[-1]
title(fig, f"The real Nvidia fell {abs(pl['NVDA'].min()):.0f}% behind a stand-in built from its peers",
      f"NVDA's gap was the most extreme of 11 stocks on {n_first} of {len(summ)} days. The final "
      f"{sc.gap_pct.iloc[-1]:.0f}% gap is {abs(final_sd):.1f} SD of normal drift.")
footer(fig, f"Synthetic NVDA = fixed mix fit on Apr-Oct 2026 daily returns: {mix}. Placebos re-run the "
            "procedure on each donor. Band = 2 SD of\npre-period cumulative tracking gaps. The window "
            "includes Q3 earnings (Nov 18) and other news.")
save(fig, "05_synthetic_control.png")

# --- 6. Specification curve for the reinstatement day ------------------------
g3 = grid.sort_values(f"{e3}_AR").reset_index(drop=True)
names = {"SPYX": "S&P ex-NVDA", "RSP": "Equal-wt S&P", "SPY": "SPY", "QQQ": "QQQ"}
cmap = {"SPYX": BLUE, "RSP": ORANGE, "SPY": AQUA, "QQQ": "#eda100"}
fig, ax = plt.subplots(figsize=(11, 6.2))
fig.subplots_adjust(left=0.07, right=0.97, top=0.80, bottom=0.24)
for i, r in g3.iterrows():
    ax.scatter(i, r[f"{e3}_AR"], s=70, color=cmap[r.benchmark], zorder=3, edgecolor=SURFACE, lw=2,
               marker="D" if r.chip_factor else "o")
ax.set_ylim(0, g3[f"{e3}_AR"].max() + 5)
ax.set_xticks(range(len(g3)), [f"{r.est_len}d" for r in g3.itertuples()], fontsize=8)
ax.set_xlabel("Estimation window (each point = one specification, sorted by estimate)")
ax.set_ylabel(f"Abnormal return on {events.date.iloc[-1]:%b} {events.date.iloc[-1].day}, %")
handles = [Line2D([], [], marker="o", ls="", color=c, markersize=8, label=names[b]) for b, c in cmap.items()]
handles += [Line2D([], [], marker="o", ls="", color=INK2, markersize=8, label="Market only"),
            Line2D([], [], marker="D", ls="", color=INK2, markersize=8, label="+ chip-peer factor")]
ax.legend(handles=handles, frameon=False, fontsize=9.5, loc="lower right", ncol=3, title="Benchmark",
          title_fontsize=9.5)
title(fig, f"{len(g3)} ways to measure the comeback. None comes in below {np.floor(g3[f'{e3}_AR'].min()):.0f}%.",
      f"Each is significant at |t| > {np.floor(g3[f'{e3}_t'].min()):.0f}. The preferred specification "
      f"(S&P 500 ex-NVDA, 250 days) gives {car(e3):.1f}%.")
footer(fig, "SPY and QQQ include NVDA itself, so on a +31% NVDA day they mechanically rise with it. "
            "Differences also reflect each benchmark's fit and beta.")
save(fig, "06_spec_curve.png")


# --- 7. The "Huang trade": suppliers minus rivals -------------------------------
st = pd.read_csv(OUT / "supplier_rival_spread.csv")
fig, ax = plt.subplots(figsize=(11, 6.2))
fig.subplots_adjust(left=0.08, right=0.97, top=0.80, bottom=0.19)
for i, r in st.iterrows():
    v = r.spread_AR_pct
    ax.bar(i, v, width=0.5, color=BLUE if v >= 0 else RED, zorder=3)
    ax.text(i, v + (0.5 if v > 0 else -0.5), f"{v:+.1f} pts\n(t = {r.t_stat:.1f})", ha="center",
            va="bottom" if v > 0 else "top", fontsize=11.5, fontweight="bold")
ax.axhline(0, color=INK2, lw=0.8)
ax.set_xticks(range(len(st)), [f"{EV_SHORT[e]}\n{events.set_index('event_id').loc[e, 'date']:%b} "
                               f"{events.set_index('event_id').loc[e, 'date'].day}" for e in st.event],
              fontsize=11, color=INK)
ax.tick_params(axis="x", length=0)
lim = st.spread_AR_pct.abs().max() + 4
ax.set_ylim(-lim, lim)
ax.set_ylabel("Suppliers minus rivals, abnormal return (pts)")
title(fig, "Wall Street traded Huang's fate as suppliers vs. rivals",
      "Nvidia's partners (TSMC, Micron, Intel) minus its AI-chip rivals (AMD, Broadcom), beyond the market's move")
footer(fig, "Spread of equal-weight baskets, market model vs S&P 500 ex-NVDA, estimated Oct 2025 - Oct 2026. "
            "\nThe resignation and comeback spreads beat every day of the prior year; Nov 9's is matched by one. "
            "AMD also had an analyst upgrade on Nov 9.")
save(fig, "07_huang_trade.png")

# --- 8. Implied odds of a permanent exit --------------------------------------
od = pd.read_csv(OUT / "implied_exit_odds.csv", index_col=0, parse_dates=True)
clean = od[od.implied_exit_odds_pct <= 100]
over = od[od.implied_exit_odds_pct > 100]
fig, ax = plt.subplots(figsize=(11, 6.2))
fig.subplots_adjust(left=0.08, right=0.95, top=0.80, bottom=0.17)
ax.axhline(100, color=INK2, lw=0.8, ls=(0, (3, 3)))
ax.text(od.index[0], 101.5, "Fully priced: Huang gone for good", fontsize=9, color=INK2, va="bottom")
for d in od.index[od.other_news]:
    ax.axvspan(d - pd.Timedelta(hours=14), d + pd.Timedelta(hours=14), ymax=0.87, color=SHADE, zorder=0, lw=0)
ax.plot(clean.index, clean.implied_exit_odds_pct, color=BLUE, lw=2.4, marker="o", markersize=7,
        markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
ax.set_ylim(0, 125)
labels = [("2026-11-09", "Probe\ndisclosed", (-14, 0), "right", "center"),
          ("2026-11-12", "Huang\nresigns", (0, 14), "center", "bottom"),
          ("2026-11-18", "Chair: he's\nnot coming back", (0, -40), "center", "top")]
for d, lab, off, ha, va in labels:
    d = pd.Timestamp(d)
    v = od.loc[d, "implied_exit_odds_pct"]
    ax.annotate(f"{v:.0f}%", (d, v), xytext=(0, -14), textcoords="offset points", ha="center",
                va="top", fontsize=11, fontweight="bold", color=INK)
    ax.annotate(lab, (d, v), xytext=off, textcoords="offset points", ha=ha, va=va, fontsize=9, color=INK2)
if len(over):
    d = over.index[0]
    ax.annotate(f"Nov {d.day}: {over.iloc[0].implied_exit_odds_pct:.0f}%, more than\nlosing Huang could explain",
                xy=(d, 112), xytext=(-10, 0), textcoords="offset points", ha="right", va="center",
                fontsize=9.5, color=INK, arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1))
    ax.annotate("", xy=(d, 116), xytext=(d, 104), arrowprops=dict(arrowstyle="-|>", color=RED, lw=2))
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.set_ylabel("Share of Huang's exit priced in")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.set_xlim(od.index[0] - pd.Timedelta(days=2), od.index[-1] + pd.Timedelta(days=1))
title(fig, "The market had priced in most of Huang's exit before he resigned",
      "Cumulative abnormal loss since the probe, as a share of what losing Huang for good was worth "
      "(valued by the comeback-day jump)")
footer(fig, "Back-of-envelope: assumes every abnormal move in the window is about Huang and the comeback "
            "jump is his full value (it also carried\ngovernment reassurance). Shaded days carried other news, "
            "so readings there are less reliable.")
save(fig, "08_implied_odds.png")

print("Saved charts to", OUT)
