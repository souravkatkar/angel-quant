"""
client/historical.py

Fetches historical candle data from Angel One SmartAPI.
Returns a pandas DataFrame indexed by timestamp.

Usage:
    from client.historical import get_candle_data
"""

import json
import logging
import pandas as pd
import requests
from datetime import datetime
from client.connection import get_headers

logger = logging.getLogger("angel_quant.client.historical")

BASE_HOST       = "apiconnect.angelone.in"
HISTORICAL_PATH = "/rest/secure/angelbroking/historical/v1/getCandleData"

# ── Valid constants ───────────────────────────────────────────────────────────

VALID_EXCHANGES = {"NSE", "NFO", "BSE", "BFO", "MCX"}

VALID_INTERVALS = {
    "ONE_MINUTE", "THREE_MINUTE", "FIVE_MINUTE", "TEN_MINUTE",
    "FIFTEEN_MINUTE", "THIRTY_MINUTE", "ONE_HOUR", "ONE_DAY"
}

MAX_DAYS = {
    "ONE_MINUTE":     30,
    "THREE_MINUTE":   60,
    "FIVE_MINUTE":    100,
    "TEN_MINUTE":     100,
    "FIFTEEN_MINUTE": 200,
    "THIRTY_MINUTE":  200,
    "ONE_HOUR":       400,
    "ONE_DAY":        2000,
}


# ── Main function ─────────────────────────────────────────────────────────────

def get_candle_data(
    auth_token: str,
    symbol_token: str,
    interval: str,
    from_date: str,
    to_date: str,
    exchange: str = "NSE",
) -> pd.DataFrame:
    """
    Fetches historical OHLCV candle data from Angel One.

    Args:
        auth_token:   JWT token from get_session()
        symbol_token: Instrument token e.g. "2885" for RELIANCE
        interval:     One of VALID_INTERVALS e.g. "ONE_DAY", "ONE_HOUR"
        from_date:    "YYYY-MM-DD HH:MM"  e.g. "2024-01-01 09:15"
        to_date:      "YYYY-MM-DD HH:MM"  e.g. "2024-01-31 15:30"
        exchange:     One of VALID_EXCHANGES, default "NSE"

    Returns:
        pd.DataFrame with columns: open, high, low, close, volume
        Index: timestamp (datetime, Asia/Kolkata timezone)
        Empty DataFrame if no data returned.

    Raises:
        ValueError:   for invalid inputs or exceeded date range
        RuntimeError: if the API returns an error response
    """

    # ── Validate inputs ───────────────────────────────────────────────────────
    exchange = exchange.upper()
    interval = interval.upper()

    if exchange not in VALID_EXCHANGES:
        raise ValueError(f"Invalid exchange '{exchange}'. Choose from: {VALID_EXCHANGES}")

    if interval not in VALID_INTERVALS:
        raise ValueError(f"Invalid interval '{interval}'. Choose from: {VALID_INTERVALS}")

    fmt = "%Y-%m-%d %H:%M"
    try:
        from_dt = datetime.strptime(from_date, fmt)
        to_dt   = datetime.strptime(to_date, fmt)
    except ValueError:
        raise ValueError(f"Dates must be 'YYYY-MM-DD HH:MM'. Got: '{from_date}', '{to_date}'")

    if from_dt >= to_dt:
        raise ValueError("from_date must be earlier than to_date")

    days_requested = (to_dt - from_dt).days
    if days_requested > MAX_DAYS[interval]:
        raise ValueError(
            f"Requested {days_requested} days but max allowed for "
            f"{interval} is {MAX_DAYS[interval]} days."
        )

    # ── API call ──────────────────────────────────────────────────────────────
    payload = {
        "exchange":    exchange,
        "symboltoken": symbol_token,
        "interval":    interval,
        "fromdate":    from_date,
        "todate":      to_date,
    }

    url = f"https://{BASE_HOST}{HISTORICAL_PATH}"
    try:
        res = requests.post(url, json=payload, headers=get_headers(auth_token), timeout=30)
        res.raise_for_status()
        response = res.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Historical API request failed: {e}")

    if not response.get("status"):
        raise RuntimeError(
            f"Historical API error → {response.get('message', 'Unknown error')} "
            f"(code: {response.get('errorcode', 'N/A')})"
        )

    # ── Parse into DataFrame ──────────────────────────────────────────────────
    raw = response.get("data", [])

    if not raw:
        logger.warning(f"No candles returned for token {symbol_token} ({interval}). "
                       f"Check token, exchange, or date range.")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])

    # Clean up timestamp — Angel One returns ISO 8601 with IST offset
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    df.set_index("timestamp", inplace=True)

    # Correct dtypes
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
    df["volume"] = df["volume"].astype(int)

    logger.info(f"✓ Fetched {len(df)} candles | Token: {symbol_token} | "
                f"Interval: {interval} | {from_date} → {to_date}")

    return df