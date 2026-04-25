# angel-quant
Historical data analysis and backtesting framework built on Angel One SmartAPI.

---

**⚠️ Note:** This is a personal project built for educational purposes and individual experimentation. It is not affiliated with or endorsed by Angel One. Use any financial data or trading strategies at your own risk.

## Features
- **Web-Based UI:** Easy-to-use interface for selecting indices (NIFTY, BANK NIFTY), time intervals, and date ranges.
- **SmartAPI Integration:** Automated login, TOTP generation, JWT token caching, and background session refreshing.
- **Historical Data:** Fetch OHLC data via Angel One's Historical API.
- **Data Export:** View data in a responsive HTML table and copy it instantly as a CSV for further analysis in Excel or Python.

## Prerequisites
- Python 3.8+
- Angel One API credentials (Client ID, MPIN, API Key, TOTP Secret)

## Installation

1. Navigate to the project directory:
   ```bash
   cd angel-quant
   ```

2. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory and add your Angel One credentials:
   ```env
   CLIENT_ID=your_client_id
   MPIN=your_mpin
   TOTP_SECRET=your_totp_secret
   API_KEY=your_api_key
   CLIENT_LOCAL_IP=127.0.0.1
   CLIENT_PUBLIC_IP=127.0.0.1
   MAC_ADDRESS=00:00:00:00:00:00
   ```

## Usage

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. Open your web browser and navigate to `http://127.0.0.1:5000/`.

3. Select your desired Index, Interval, and Date Range, then click **Fetch Data**.