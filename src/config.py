"""Single source of truth for paths, tickers, dates and shared helpers."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "output"
OUT.mkdir(exist_ok=True)

# --- Universe ---------------------------------------------------------------
TARGET = "NVDA"
BENCHMARKS = ["SPY", "RSP", "QQQ"]          # RSP = equal-weight S&P 500
SECTOR_ETF = ["SMH"]
PEERS = ["AMD", "AVGO", "TSM", "MU", "INTC"]  # chip peers (NVDA excluded)
MEGACAPS = ["MSFT", "GOOGL", "META", "AMZN", "AAPL"]
TICKERS = [TARGET] + BENCHMARKS + SECTOR_ETF + PEERS + MEGACAPS
DATA_START = "2024-06-01"

# --- Study design -----------------------------------------------------------
EST_END = "2026-10-23"   # estimation window ends before Megaspeed reports / midterms
EST_LEN = 250            # ~1 trading year
BASE = "2026-11-06"      # last close before the investigation was disclosed
SYNTH_PRE_START = "2026-04-01"

# NVDA weight in the S&P 500 on EST_END, used to strip NVDA out of SPY.
# Source: WhichIndex S&P 500 weights as of 23 Oct 2026 (https://whichindex.com/indexes/sp-500/).
# Rolled forward/back with relative prices; matches published weights within ~0.1pp
# (SPY holdings 8.50% on Oct 2 vs 8.45% implied; Vanguard 7.58% on Oct 31 vs 7.59%).
NVDA_SPX_WEIGHT_ANCHOR = 0.0777

PREFERRED = "market_spyx"   # key into MODELS below


def load_shares():
    meta = json.loads((DATA / "meta.json").read_text())
    return float(meta["nvda_shares_outstanding"])


def load_events():
    ev = pd.read_csv(DATA / "events.csv", parse_dates=["date"])
    return ev


def load_confounders():
    return pd.read_csv(DATA / "confounders.csv", parse_dates=["date"])


def load_prices():
    px = pd.read_csv(DATA / "close.csv", index_col=0, parse_dates=True).sort_index()
    if px.isna().any().any():
        bad = px.columns[px.isna().any()].tolist()
        raise ValueError(f"Missing prices for {bad}; re-run fetch_data.py")
    return px


def nvda_spx_weight(px):
    """Daily NVDA weight in the S&P 500, anchored on EST_END and drifted with prices."""
    rel = (px[TARGET] / px.loc[EST_END, TARGET]) / (px["SPY"] / px.loc[EST_END, "SPY"])
    w0 = NVDA_SPX_WEIGHT_ANCHOR
    return w0 * rel / (1 - w0 + w0 * rel)


def load_returns():
    """Daily log returns plus constructed factors:
    SPYX  = S&P 500 excluding NVDA (cap-weighted, NVDA removed using prior-day weight)
    CHIPS = equal-weight chip-peer basket (NVDA excluded)
    """
    px = load_prices()
    simple = px.pct_change()
    w_prev = nvda_spx_weight(px).shift(1)
    spyx_simple = (simple["SPY"] - w_prev * simple[TARGET]) / (1 - w_prev)
    ret = np.log1p(simple)
    ret["SPYX"] = np.log1p(spyx_simple)
    ret["CHIPS"] = ret[PEERS].mean(axis=1, skipna=False)
    return ret.dropna(how="any"), px


# Normal-return models: name -> regressors
MODELS = {
    "market_spyx": ["SPYX"],            # preferred: cap-weighted market without NVDA
    "market_rsp": ["RSP"],              # equal-weight market
    "industry": ["SPYX", "CHIPS"],      # + chip peers (peers react to NVDA news; see README)
}
MODEL_LABELS = {
    "market_spyx": "Market model (S&P 500 ex-NVDA)",
    "market_rsp": "Market model (equal-weight S&P 500)",
    "industry": "Industry model (+ chip peers)",
}


def car_simple(actual_log, predicted_log):
    """Abnormal return as a simple-return difference over a window:
    (cumulative actual simple return) - (cumulative predicted simple return).
    This is the dollar-correct measure: times the starting market cap it gives the
    gap between actual and counterfactual market value."""
    return np.expm1(np.sum(actual_log)) - np.expm1(np.sum(predicted_log))
