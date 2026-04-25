import os
from flask import Flask, render_template, request, jsonify
from client.connection import get_session
from client.historical import get_candle_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)

print("Initializing application...")

# ── UI to API Mappings ────────────────────────────────────────────────────────
INTERVAL_MAP = {
    "1m": "ONE_MINUTE",
    "3m": "THREE_MINUTE",
    "5m": "FIVE_MINUTE",
    "10m": "TEN_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "30m": "THIRTY_MINUTE",
    "1h": "ONE_HOUR",
    "1d": "ONE_DAY"
}

SYMBOL_MAP = {
    "NIFTY": "99926000",
    "BANK NIFTY": "99926009"
}


@app.route('/')
def index():
    """Renders the main UI."""
    return render_template('index.html')


@app.route('/api/data', methods=['POST'])
def fetch_data():
    """API Endpoint to fetch data based on UI form submission."""
    print("\n" + "="*50)
    print("🚀 NEW FETCH REQUEST TRIGGERED")
    try:
        data = request.json
        print(f"📦 Received Payload: {data}")
        
        ui_symbol = data.get('symbol')
        ui_interval = data.get('interval')
        start_date = data.get('start_date') # Expected from UI: "YYYY-MM-DDTHH:MM"
        end_date = data.get('end_date')     # Expected from UI: "YYYY-MM-DDTHH:MM"

        if not all([ui_symbol, ui_interval, start_date, end_date]):
            return jsonify({"status": "error", "message": "All fields are required"}), 400

        # Map inputs to Angel One API expectations
        token = SYMBOL_MAP.get(ui_symbol, "99926000")
        api_interval = INTERVAL_MAP.get(ui_interval, "FIVE_MINUTE")
        
        # Convert HTML5 datetime-local (T) to AngelOne format (Space)
        start_date_formatted = start_date.replace("T", " ")
        end_date_formatted = end_date.replace("T", " ")

        print("🔑 Checking Angel One Authentication...")
        session = get_session()
        auth_token = session['auth_token']

        print(f"📈 Fetching from Angel One: {token} | {api_interval} | {start_date_formatted} to {end_date_formatted}")
        df = get_candle_data(auth_token, token, api_interval, start_date_formatted, end_date_formatted)

        if df.empty:
            print("⚠️ WARNING: Angel One API returned NO DATA for this time range.")
            return jsonify({"status": "error", "message": "Angel One returned empty data. Check if the market was open during this date range."}), 400

        # Remove the volume column as requested
        if 'volume' in df.columns:
            df.drop(columns=['volume'], inplace=True)

        print(f"✅ SUCCESS: Fetched {len(df)} candle rows.")
        print("="*50 + "\n")
        
        return jsonify({"status": "success", "csv": df.to_csv()})

    except Exception as e:
        print(f"❌ BACKEND ERROR: {str(e)}")
        print("="*50 + "\n")
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)