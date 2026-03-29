"""
main.py  –  Entry point / quick smoke-test for the Angel One connection.
"""

from client import get_session, refresh_session

def main():
    print("Connecting to Angel One SmartAPI …")

    # ── Step 1: Login ────────────────────────────────────────────────────────
    session = get_session()
    print("✓ Logged in successfully")
    print(f"  auth_token    : {session['auth_token'][:30]}…")
    print(f"  refresh_token : {session['refresh_token'][:30]}…")
    print(f"  feed_token    : {session['feed_token'][:20]}…")

    # ── Step 2: Refresh (optional – demonstrates token refresh flow) ─────────
    new_session = refresh_session(
        auth_token=session["auth_token"],
        refresh_token=session["refresh_token"],
    )
    print("\n✓ Token refreshed successfully")
    print(f"  new auth_token: {new_session['auth_token'][:30]}…")

    # ── Use new_session['auth_token'] in all subsequent API calls ────────────


if __name__ == "__main__":
    main()