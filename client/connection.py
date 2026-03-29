"""
client/connection.py

Handles authentication and token management for the Angel One SmartAPI.
Reads credentials from .env and exposes:
  - get_session()   → returns auth_token, refresh_token, feed_token
  - get_headers()   → returns pre-built request headers for secure endpoints
"""

import os
import json
import pyotp
import http.client
from dotenv import load_dotenv

load_dotenv()

# ── Credentials from .env ────────────────────────────────────────────────────
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_PIN    = os.getenv("MPIN")
TOTP_SECRET   = os.getenv("TOTP_SECRET")
API_KEY       = os.getenv("API_KEY")
LOCAL_IP      = os.getenv("CLIENT_LOCAL_IP", "127.0.0.1")
PUBLIC_IP     = os.getenv("CLIENT_PUBLIC_IP", "127.0.0.1")
MAC_ADDRESS   = os.getenv("MAC_ADDRESS", "00:00:00:00:00:00")

BASE_HOST     = "apiconnect.angelone.in"


# ── Internal helpers ─────────────────────────────────────────────────────────

def _common_headers(auth_token: str | None = None) -> dict:
    """
    Headers shared by every Angel One API call.
    Pass auth_token for endpoints that require Bearer authentication.
    """
    headers = {
        "Content-Type":      "application/json",
        "Accept":            "application/json",
        "X-UserType":        "USER",
        "X-SourceID":        "WEB",
        "X-ClientLocalIP":   LOCAL_IP,
        "X-ClientPublicIP":  PUBLIC_IP,
        "X-MACAddress":      MAC_ADDRESS,
        "X-PrivateKey":      API_KEY,
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return headers


def _post(path: str, payload: dict, auth_token: str | None = None) -> dict:
    """Generic HTTPS POST helper. Returns parsed JSON response."""
    conn = http.client.HTTPSConnection(BASE_HOST)
    conn.request(
        "POST",
        path,
        body=json.dumps(payload),
        headers=_common_headers(auth_token),
    )
    res  = conn.getresponse()
    data = json.loads(res.read().decode("utf-8"))
    conn.close()
    return data


# ── Public API ───────────────────────────────────────────────────────────────

def get_session() -> dict:
    """
    Authenticates with Angel One and returns a session dict:
        {
            "auth_token":    str,
            "refresh_token": str,
            "feed_token":    str,
        }

    Raises RuntimeError if authentication fails.
    """
    totp_code = pyotp.TOTP(TOTP_SECRET).now()

    payload = {
        "clientcode": CLIENT_ID,
        "password":   CLIENT_PIN,
        "totp":       totp_code,
    }

    response = _post(
        "/rest/auth/angelbroking/user/v1/loginByPassword",
        payload,
    )

    if not response.get("status"):
        raise RuntimeError(
            f"Login failed → {response.get('message', 'Unknown error')} "
            f"(code: {response.get('errorcode', 'N/A')})"
        )

    data = response["data"]
    return {
        "auth_token":    data["jwtToken"],
        "refresh_token": data["refreshToken"],
        "feed_token":    data["feedToken"],
    }


def refresh_session(auth_token: str, refresh_token: str) -> dict:
    """
    Generates a new JWT using an existing refresh token.
    Returns the same session dict shape as get_session().

    Raises RuntimeError if the refresh fails.
    """
    payload  = {"refreshToken": refresh_token}
    response = _post(
        "/rest/auth/angelbroking/jwt/v1/generateTokens",
        payload,
        auth_token=auth_token,
    )

    if not response.get("status"):
        raise RuntimeError(
            f"Token refresh failed → {response.get('message', 'Unknown error')}"
        )

    data = response["data"]
    return {
        "auth_token":    data["jwtToken"],
        "refresh_token": data["refreshToken"],
        "feed_token":    data["feedToken"],
    }


def get_headers(auth_token: str) -> dict:
    """
    Returns a ready-to-use headers dict for secure Angel One endpoints.
    Pass the auth_token returned by get_session() or refresh_session().
    """
    return _common_headers(auth_token)