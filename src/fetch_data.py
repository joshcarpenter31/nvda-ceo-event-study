"""Download daily adjusted closes for NVDA, benchmarks and peers into data/.

Only complete sessions are kept: the cutoff is computed in New York time, so a
session that is still trading (or not yet settled) is never saved. This
overwrites the frozen dataset in data/, so run_all.py only calls it with --fetch.
"""
import json

import pandas as pd
import yfinance as yf

from config import DATA, DATA_START, TARGET, TICKERS


def last_complete_session_end():
    """yfinance's `end` is exclusive and interpreted in New York time. Include
    today only once the US close (16:00 ET, plus a buffer) has passed."""
    now = pd.Timestamp.now(tz="America/New_York")
    include_today = now.hour >= 17
    return (now.normalize() + pd.Timedelta(days=1 if include_today else 0)).strftime("%Y-%m-%d")


def main():
    end = last_complete_session_end()
    raw = yf.download(TICKERS, start=DATA_START, end=end, auto_adjust=True, progress=False)
    close, volume = raw["Close"], raw["Volume"]

    missing = close.columns[close.isna().any()].tolist()
    if missing or set(close.columns) != set(TICKERS):
        raise RuntimeError(f"Incomplete download (missing/NaN: {missing}); data/ left unchanged")

    close.to_csv(DATA / "close.csv")
    volume.to_csv(DATA / "volume.csv")
    # Intraday range for the target (used by the hero chart)
    ohlc = pd.DataFrame({f: raw[f][TARGET] for f in ["Open", "High", "Low", "Close"]})
    ohlc.to_csv(DATA / "nvda_ohlc.csv")
    shares = yf.Ticker(TARGET).fast_info.get("shares")
    meta = {
        "nvda_shares_outstanding": int(shares),
        "shares_source": "yfinance Ticker('NVDA').fast_info['shares']",
        "fetched_at_utc": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M"),
        "last_trading_day": close.index[-1].strftime("%Y-%m-%d"),
    }
    (DATA / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"Saved {len(close)} sessions through {meta['last_trading_day']}; shares {shares:,}")


if __name__ == "__main__":
    main()
