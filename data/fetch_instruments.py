"""
data/fetch_instruments.py

Downloads Angel One scrip master ONLY if not already present.
To force a refresh, pass force=True or delete instruments.json manually.

Usage:
    python data/fetch_instruments.py           # skips if already exists
    python data/fetch_instruments.py --force   # forces re-download
"""

import requests
import os
import argparse

INSTRUMENTS_URL = (
    "https://margincalculator.angelone.in"
    "/OpenAPI_File/files/OpenAPIScripMaster.json"
)
DEFAULT_SAVE_PATH = os.path.join(os.path.dirname(__file__), "instruments.json")


def fetch_and_save_instruments(save_path=DEFAULT_SAVE_PATH, force=False):
    # ── Skip if already exists ───────────────────────────────────────────────
    if os.path.exists(save_path) and not force:
        size_mb = os.path.getsize(save_path) / 1024 / 1024
        print(f"✓ instruments.json already exists ({size_mb:.1f} MB). Skipping download.")
        print(f"  To refresh, run with --force or call fetch_and_save_instruments(force=True)")
        return save_path

    # ── Download ─────────────────────────────────────────────────────────────
    print("Fetching instruments... (streaming)")
    with requests.get(INSTRUMENTS_URL, stream=True, timeout=120) as response:
        response.raise_for_status()

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        total = 0
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                total += len(chunk)
                print(f"  Downloaded {total / 1024 / 1024:.1f} MB...", end="\r")

    print(f"\n✓ Saved to {os.path.abspath(save_path)}")
    return save_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force re-download even if file exists")
    args = parser.parse_args()

    fetch_and_save_instruments(force=args.force)