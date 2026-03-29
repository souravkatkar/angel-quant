"""
client/instruments.py

Loads the Angel One scrip master into a DataFrame.
Run data/fetch_instruments.py first if instruments.json doesn't exist.

Usage:
    from client.instruments import load_instruments, get_symbol_token

    df = load_instruments()
    token = get_symbol_token(df, "RELIANCE", exchange="NSE")
    token = get_symbol_token(df, "NIFTY", exchange="NSE", instrument_type="AMXIDX")
"""

import os
import json
import pandas as pd

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "../data/instruments.json")


def load_instruments(path=DEFAULT_PATH) -> pd.DataFrame:
    """
    Loads instruments.json from disk.
    If missing, automatically downloads it once — subsequent calls use the cache.
    """
    abs_path = os.path.abspath(path)

    if not os.path.exists(abs_path):
        print("instruments.json not found. Fetching for the first time...")
        from data.fetch_instruments import fetch_and_save_instruments
        fetch_and_save_instruments(save_path=abs_path)

    with open(abs_path, "r") as f:
        instruments = json.load(f)

    df = pd.DataFrame(instruments)
    print(f"✓ Loaded {df.shape[0]:,} instruments ({df.shape[1]} columns)")
    return df


def get_symbol_token(
    df: pd.DataFrame,
    symbol: str,
    exchange: str = "NSE",
    instrument_type: str = None,
) -> str:
    """
    Looks up the symboltoken for a given symbol, exchange, and optionally instrument type.

    Args:
        df:              Instruments DataFrame from load_instruments()
        symbol:          Trading symbol e.g. "RELIANCE", "NIFTY"
        exchange:        Exchange segment e.g. "NSE", "NFO", "BSE", "BFO", "MCX"
        instrument_type: Optional filter e.g. "EQ", "AMXIDX", "OPTIDX", "FUTIDX"
                         Pass None to skip this filter (default)

    Returns:
        Token string e.g. "2885"

    Raises:
        ValueError: if no match found, with helpful suggestions
    """
    mask = (
        (df["symbol"] == symbol.upper()) &
        (df["exch_seg"] == exchange.upper())
    )

    if instrument_type:
        mask &= (df["instrumenttype"] == instrument_type.upper())

    result = df[mask]

    # ── No match — give a helpful error ──────────────────────────────────────
    if result.empty:
        # Check if symbol exists at all (ignoring exchange/type filters)
        all_matches = df[df["symbol"] == symbol.upper()]

        if all_matches.empty:
            raise ValueError(f"Symbol '{symbol}' not found in instruments. Check the symbol name.")

        # Symbol exists but filters didn't match — show what's available
        available = all_matches[["symbol", "exch_seg", "instrumenttype", "token"]].to_string(index=False)
        raise ValueError(
            f"Symbol '{symbol}' not found with exchange='{exchange}'"
            + (f", instrument_type='{instrument_type}'" if instrument_type else "")
            + f"\n\nAvailable options for '{symbol}':\n{available}"
        )

    # ── Multiple matches — warn and return first ──────────────────────────────
    if len(result) > 1:
        print(f"⚠ Multiple matches found for '{symbol}' on {exchange}"
              + (f" ({instrument_type})" if instrument_type else "")
              + f". Returning first. Use instrument_type to narrow down.")
        print(result[["symbol", "exch_seg", "instrumenttype", "token"]].to_string(index=False))

    return result.iloc[0]["token"]