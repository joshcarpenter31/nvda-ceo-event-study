"""LinkedIn hero image (4:5 portrait, dark): output/hero_linkedin.png

Top: Nvidia's market value each day with the intraday range, annotated with the
events. Bottom: each day's abnormal return against a normal-day noise band.
Run after event_study.py (run_all.py does this)."""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import BASE, DATA, OUT, PREFERRED, load_events, load_shares

# Reference palette, dark mode
BG, INK, INK2, MUTED, GRID = "#1a1a19", "#f0efec", "#c3c2b7", "#7d7c74", "#383835"
BLUE, AQUA, RED = "#3987e5", "#199e70", "#e66767"
BLUE_LIGHT = "#1c5cab"

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "font.family": "DejaVu Sans", "text.color": INK, "axes.edgecolor": GRID,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
    "text.parse_math": False,
})

SHARES = load_shares()
events = load_events()
ohlc = pd.read_csv(DATA / "nvda_ohlc.csv", index_col=0, parse_dates=True)
cars = pd.read_csv(OUT / "event_cars.csv")

end = events.date.max()
w = ohlc.loc[BASE:end] * SHARES / 1e12            # market value, $ trillions
days = list(w.index)
x = np.arange(len(days))
pos = {d: i for i, d in enumerate(days)}
D = lambda s: pos[pd.Timestamp(s)]

e3 = events.event_id.iloc[-1]
ar_usd = cars[(cars.event == e3) & (cars.window == "[0,0]") & (cars.model == PREFERRED)].CAR_usd_bn.iloc[0]
jump_usd = (w.Close.iloc[-1] - w.Close.iloc[-2]) * 1000
low_day = w.Close.idxmin()
drop_usd = (w.Close.loc[BASE] - w.Close.min())

fig = plt.figure(figsize=(8, 10), dpi=150)
fig.text(0.06, 0.955, f"The ${round(ar_usd, -2):,.0f} billion comeback", fontsize=30, fontweight="bold", va="top")
fig.text(0.06, 0.895, "Nvidia's market value as Jensen Huang was investigated,\nresigned and reinstated, November 2026",
         fontsize=13, color=INK2, va="top", linespacing=1.35)

# --- Top panel: market value ---------------------------------------------------
ax = fig.add_axes([0.11, 0.40, 0.83, 0.43])
wick_c = [RED if d == pd.Timestamp("2026-11-12") else MUTED for d in days]
ax.vlines(x, w.Low, w.High, color=wick_c, lw=[3.5 if c == RED else 2.2 for c in wick_c], zorder=2)  # intraday range
ax.fill_between(x[:-1], w.Close.iloc[:-1], 2.6, color=BLUE, alpha=0.10, lw=0, zorder=1)
ax.plot(x[:-1], w.Close.iloc[:-1], color=BLUE, lw=3, zorder=3, solid_capstyle="round")
ax.plot(x[-2:], w.Close.iloc[-2:], color=AQUA, lw=4, zorder=4, solid_capstyle="round")
ax.scatter(x, w.Close, s=34, color=[BLUE] * (len(x) - 1) + [AQUA], zorder=5, edgecolor=BG, lw=1.5)
ax.set_ylim(2.6, 4.9)
ax.set_xlim(-0.6, len(x) - 0.3)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:.1f}T"))
ax.tick_params(axis="y", labelsize=10.5, length=0)
ax.set_xticks(x, [""] * len(x))
ax.tick_params(axis="x", length=0, labelbottom=False)


def note(i, y, text, xy_off, ha="center", va="bottom", color=INK, size=11.5, weight="normal", line=True):
    ax.annotate(text, (i, y), xytext=xy_off, textcoords="offset points", ha=ha, va=va, fontsize=size,
                color=color, fontweight=weight, linespacing=1.25, zorder=6,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=1, shrinkA=2, shrinkB=4) if line else None)


note(D("2026-11-09"), w.High.loc["2026-11-09"], "Board discloses\ninvestigation", (10, 30), ha="left")
i12 = D("2026-11-12")
o12 = ohlc.loc["2026-11-12"]
prev = ohlc.Close.shift(1).loc["2026-11-12"]
note(i12, w.Low.loc["2026-11-12"],
     f"Huang resigns\nOpens {o12.Open / prev - 1:+.0%}, closes {o12.Close / prev - 1:+.0%}".replace("-", "−"),
     (0, -36), va="top", color=RED, weight="bold")
note(D("2026-11-18"), w.High.loc["2026-11-18"], "Chair: he's\nnot coming back", (0, 30))
il = pos[low_day]
note(il, w.Close.min(), f"${w.Close.min():.1f}T\n−${drop_usd:.1f}T since Nov {pd.Timestamp(BASE).day}",
     (-14, -18), ha="right", va="top", color=INK2)
note(len(x) - 1, w.High.iloc[-1], f"Reinstated\n+${round(jump_usd, -1):,.0f}B in one day", (-6, 26),
     ha="right", color=AQUA, size=14.5, weight="bold")

# --- Bottom panel: daily move beyond the market vs. normal noise ---------------
daily = pd.read_csv(OUT / "daily_abnormal_returns.csv", index_col=0, parse_dates=True)
vol = pd.read_csv(OUT / "robust_volatility.csv")
reb = pd.read_csv(OUT / "rebound_check.csv")
noise = 2 * vol.sd_const.iloc[0]                       # +/- 2 SD of a normal day, %
ar_pct = daily.loc[days, f"{PREFERRED}_simple"] * 100
bx = fig.add_axes([0.11, 0.135, 0.83, 0.185], sharex=ax)
bx.text(-0.6, 41, "The resignation barely beat the noise. The comeback blew past it.", fontsize=12,
        fontweight="bold", va="bottom")
bx.text(-0.6, 34, "Each day's move beyond what the market explains", fontsize=10, color=INK2, va="bottom")
bx.axhspan(-noise, noise, color=GRID, alpha=0.9, lw=0, zorder=0)
bx.text(0.15, noise + 0.6, f"normal day: \u00b1{noise:.0f}%", fontsize=8.5, color=INK2, va="bottom")
ev_days = set(events.date)
for d, v in ar_pct.items():
    i = pos[d]
    if d == days[-1]:
        c = AQUA
    elif d in ev_days:
        c = RED
    else:
        c = MUTED
    bx.bar(i, v, width=0.62, color=c, zorder=2)
for d in events.date:
    v = ar_pct.loc[d]
    bx.text(pos[d], v + (1 if v > 0 else -1), f"{v:+.1f}%".replace("-", "\u2212"), ha="center",
            va="bottom" if v > 0 else "top", fontsize=11, fontweight="bold",
            color=AQUA if d == days[-1] else INK)
bx.axhline(0, color=INK2, lw=0.8, zorder=1)
bx.set_ylim(-14, 32)
bx.set_yticks([-10, 0, 10, 20, 30], ["\u221210%", "0%", "+10%", "+20%", "+30%"])
bx.tick_params(axis="y", labelsize=9.5, length=0)
bx.set_xticks(x, [f"{d:%b}\n{d.day}" if i in (0, len(x) - 1) else f"{d.day}" for i, d in enumerate(days)],
              fontsize=9.5)
bx.tick_params(axis="x", length=0, colors=INK2)
bx.spines["bottom"].set_visible(False)

lo_usd, hi_usd = reb.comeback_net_of_rebound_usd_bn.min(), reb.comeback_net_of_rebound_usd_bn.max()
fig.text(0.06, 0.055, f"Market value = closing price \u00d7 shares outstanding; gray lines show each day's trading range. "
         f"Moves are relative to the\nS&P 500 ex-Nvidia. Allowing for a typical rebound after Nov 20, the comeback is "
         f"still ${round(lo_usd, -1):,.0f}B to ${round(hi_usd, -1):,.0f}B. Built with AI assistance.",
         fontsize=8, color=MUTED, va="bottom", linespacing=1.4)
fig.text(0.06, 0.025, "Full analysis: github.com/joshcarpenter31/nvda-ceo-event-study", fontsize=9.5,
         color=INK2, va="bottom")
fig.savefig(OUT / "hero_linkedin.png", dpi=150)
print("Saved", OUT / "hero_linkedin.png")
