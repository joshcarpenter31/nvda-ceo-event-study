"""LinkedIn hero image (4:5 portrait, dark): output/hero_linkedin.png

Top: Nvidia's market value each day with the intraday range, annotated with the
events. Bottom: implied share of Huang's exit already priced in.
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
odds = pd.read_csv(OUT / "implied_exit_odds.csv", index_col=0, parse_dates=True)

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

# --- Bottom panel: implied exit odds ---------------------------------------------
bx = fig.add_axes([0.11, 0.135, 0.83, 0.185], sharex=ax)
bx.text(-0.6, 121, "How sure the market was that he was gone", fontsize=12.5, fontweight="bold", va="bottom")
bx.text(-0.6, 108, "Share of his exit already priced into the stock", fontsize=10, color=INK2, va="bottom")
for d, r in odds.iterrows():
    i = pos[d]
    if r.implied_exit_odds_pct > 100:
        bx.bar(i, 100, width=0.62, color=GRID, zorder=2)
        bx.text(i, 50, "other\nnews", ha="center", va="center", fontsize=8, color=INK2, rotation=90, linespacing=1.0)
    else:
        bx.bar(i, r.implied_exit_odds_pct, width=0.62, color=BLUE, zorder=2)
for d in ["2026-11-09", "2026-11-12", "2026-11-18"]:
    v = odds.loc[d, "implied_exit_odds_pct"]
    bx.text(pos[pd.Timestamp(d)], v + 4, f"{v:.0f}%", ha="center", va="bottom", fontsize=11.5, fontweight="bold")
bx.text(len(x) - 1, 6, "He's\nback", ha="center", va="bottom", fontsize=10, color=AQUA, fontweight="bold", linespacing=1.1)
bx.set_ylim(0, 100)
bx.set_yticks([0, 50, 100], ["0%", "50%", "100%"])
bx.tick_params(axis="y", labelsize=9.5, length=0)
bx.set_xticks(x, [f"{d:%b}\n{d.day}" if i in (0, len(x) - 1) else f"{d.day}" for i, d in enumerate(days)],
              fontsize=9.5)
bx.tick_params(axis="x", length=0, colors=INK2)
bx.spines["bottom"].set_color(GRID)

fig.text(0.06, 0.055, "Market value = closing price × shares outstanding; gray bars show each day's trading range. "
         "Exit odds: cumulative\nmove beyond the S&P 500 ex-Nvidia, as a share of the comeback-day jump "
         "(a rough guide; Nov 20 had other news).", fontsize=8, color=MUTED, va="bottom", linespacing=1.4)
fig.text(0.06, 0.025, "Full analysis: github.com/joshcarpenter31/nvda-ceo-event-study", fontsize=9.5,
         color=INK2, va="bottom")
fig.savefig(OUT / "hero_linkedin.png", dpi=150)
print("Saved", OUT / "hero_linkedin.png")
