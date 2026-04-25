"""
client/connection.py

Handles authentication and token management for the Angel One SmartAPI.
Reads credentials from .env and exposes:
  - get_session()   → returns auth_token, refresh_token, feed_token
  - get_headers()   → returns pre-built request headers for secure endpoints
"""

import os
import json
import time
import pyotp
import requests
import jwt
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
SESSION_FILE  = os.path.join(os.path.dirname(__file__), "../.session.json")

# Make sure to add `requests` and `PyJWT` to your requirements.txt
# pip install requests pyjwt


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


def _post(path: str, payload: dict, auth_token: str | None = None, timeout: int = 10) -> dict:
    """Generic HTTPS POST helper using requests. Returns parsed JSON response."""
    url = f"https://{BASE_HOST}{path}"
    try:
        response = requests.post(url, json=payload, headers=_common_headers(auth_token), timeout=timeout)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API request to {path} failed: {e}")


def _save_session_to_disk(session: dict):
    """Saves the session dictionary to the session file."""
    with open(SESSION_FILE, "w") as f:
        json.dump(session, f)


def _load_session_from_disk() -> dict | None:
    """Loads the session dictionary from the session file, if it exists."""
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def _is_token_expired(token: str) -> bool:
    """Checks if a JWT token is expired, with a 10-second leeway."""
    try:
        decoded_token = jwt.decode(token, options={"verify_signature": False}, leeway=10)
        return decoded_token["exp"] < time.time()
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return True


# ── Public API ───────────────────────────────────────────────────────────────

def _perform_login() -> dict:
    """
    Performs a full login with client ID, PIN, and TOTP.
    This should only be called when no valid session or refresh token exists.
    """
    print("Performing full login with TOTP...")
    totp_code = pyotp.TOTP(TOTP_SECRET).now()
    payload = {
        "clientcode": CLIENT_ID,
        "password":   CLIENT_PIN,
        "totp":       totp_code,
    }
    response = _post("/rest/auth/angelbroking/user/v1/loginByPassword", payload)

    if not response.get("status"):
        raise RuntimeError(
            f"Login failed → {response.get('message', 'Unknown error')} "
            f"(code: {response.get('errorcode', 'N/A')})"
        )
    
    data = response["data"]
    session = {
        "auth_token":    data["jwtToken"],
        "refresh_token": data["refreshToken"],
        "feed_token":    data["feedToken"],
    }
    _save_session_to_disk(session)
    print("✓ Login successful. Session saved to disk.")
    return session


def refresh_session(auth_token: str, refresh_token: str) -> dict:
    """
    Generates a new JWT using an existing refresh token.
    """
    print("Auth token expired. Attempting to refresh session...")
    payload  = {"refreshToken": refresh_token}
    response = _post(
        "/rest/auth/angelbroking/jwt/v1/generateTokens",
        payload,
        auth_token=auth_token, # The expired token is needed for this endpoint
    )

    if not response.get("status"):
        raise RuntimeError(
            f"Token refresh failed → {response.get('message', 'Unknown error')}"
        )

    data = response["data"]
    session = {
        "auth_token":    data["jwtToken"],
        "refresh_token": data["refreshToken"],
        "feed_token":    data["feedToken"],
    }
    _save_session_to_disk(session)
    print("✓ Session refreshed successfully. New tokens saved.")
    return session


def get_session() -> dict:
    """
    The main entry point for getting a valid session.
    1. Tries to load a session from the local cache (`.session.json`).
    2. If the auth_token is expired, it tries to refresh it.
    3. If refreshing fails or no session exists, it performs a full login.
    """
    session = _load_session_from_disk()

    if session and not _is_token_expired(session.get("auth_token", "")):
        print("✓ Using cached session.")
        return session

    if session and session.get("refresh_token"):
        try:
            return refresh_session(session["auth_token"], session["refresh_token"])
        except RuntimeError as e:
            print(f"Refresh failed: {e}. Proceeding to full login.")

    return _perform_login()


def get_headers(auth_token: str) -> dict:
    """
    Returns a ready-to-use headers dict for secure Angel One endpoints.
    Pass the auth_token returned by get_session() or refresh_session().
    """
    return _common_headers(auth_token)