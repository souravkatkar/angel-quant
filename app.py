import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from client.connection import get_session
from client.historical import get_candle_data
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

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

@app.route('/api/analyze', methods=['POST'])
def analyze_market():
    """API Endpoint to fetch historical data and analyze it using Gemini."""
    print("\n" + "="*50)
    print("🤖 NEW AI ANALYSIS REQUEST TRIGGERED")
    try:
        data = request.json
        ui_symbol = data.get('symbol', 'NIFTY')
        token = SYMBOL_MAP.get(ui_symbol, "99926000")
        
        # Calculate dynamic dates
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        four_weeks_ago = now - timedelta(days=28)
        
        now_str = now.strftime("%Y-%m-%d %H:%M")
        one_week_str = one_week_ago.strftime("%Y-%m-%d 09:15")
        four_weeks_str = four_weeks_ago.strftime("%Y-%m-%d 09:15")
        
        session = get_session()
        auth_token = session['auth_token']
        
        print(f"📈 Fetching 15-min data ({one_week_str} to {now_str})...")
        df_15m = get_candle_data(auth_token, token, "FIFTEEN_MINUTE", one_week_str, now_str)
        
        print(f"📈 Fetching 1-day data ({four_weeks_str} to {now_str})...")
        df_1d = get_candle_data(auth_token, token, "ONE_DAY", four_weeks_str, now_str)
        
        csv_15m = df_15m.to_csv(index=False) if not df_15m.empty else "No 15m data available."
        csv_1d = df_1d.to_csv(index=False) if not df_1d.empty else "No 1d data available."
        
        if "GEMINI_API_KEY" not in os.environ:
            raise ValueError("GEMINI_API_KEY not found in environment.")
            
        print("🧠 Sending data to Gemini...")
        client = genai.Client()
        
        user_prompt = f"""
        Analyze the following multi-timeframe candle data for {ui_symbol}. 
        Identify the macro trend from the Daily data, and look for immediate momentum or entry signals in the 15-minute data.

        ### 1-Day Candles (Macro Trend)
        {csv_1d}

        ### 15-Minute Candles (Micro Price Action)
        {csv_15m}

        Please provide:
        1. A brief summary of the multi-timeframe alignment.
        2. Key support and resistance levels based on this data.
        3. A directional bias for the upcoming session.
        """
                
        response = client.models.generate_content(
            model='gemini-3.5-flash', # Update this to 'gemini-2.5-flash' or 'gemini-1.5-flash' if 3.5 throws a model not found error
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are an expert algorithmic trading assistant. Provide concise, data-driven technical analysis without financial disclaimers.",
                temperature=0.1, 
            )
        )
        
        return jsonify({"status": "success", "analysis": response.text})
    except Exception as e:
        print(f"❌ AI ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)