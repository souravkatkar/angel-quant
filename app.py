import os
import json
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from google import genai
from google.genai import types

from client.connection import get_session
from client.historical import get_candle_data


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

# ==========================================
# PYDANTIC SCHEMA DEFINITION
# ==========================================
class MetaData(BaseModel):
    symbol: str = Field(description="The ticker symbol, e.g., NIFTY")
    timeframe_analyzed: list[str] = Field(description="List of timeframes analyzed, e.g., ['1D', '15m']")
    generated_at: str = Field(description="Current ISO timestamp")
    data_as_of: str = Field(description="Timestamp of the latest candle provided")
    session: str = Field(description="Trading session type, e.g., Regular")

class Trend(BaseModel):
    primary: str = Field(description="Primary trend direction")
    primary_timeframe: str = Field(description="Timeframe for the primary trend, e.g., 1D")
    secondary: str = Field(description="Secondary trend direction")
    secondary_timeframe: str = Field(description="Timeframe for the secondary trend, e.g., 15m")
    alignment: str = Field(description="How the trends interact")

class MarketContext(BaseModel):
    bias: str = Field(description="Directional bias for the upcoming session: Bullish, Bearish, or Neutral")
    bias_strength: str = Field(description="Strength of the bias: Strong, Moderate, or Weak")
    trend: Trend
    phase: str = Field(description="Current market phase")
    narrative: str = Field(description="Detailed narrative explaining price action")

class KeyLevel(BaseModel):
    price: float = Field(description="Price level")
    type: str = Field(description="Description of the level")
    significance: str = Field(description="Significance: High, Medium, or Low")

class DrawOnLiquidity(BaseModel):
    upside_target: float = Field(description="Next major upside liquidity level")
    downside_target: float = Field(description="Next major downside liquidity level")
    current_draw: str = Field(description="Which direction is price currently being drawn to?")

class KeyLevels(BaseModel):
    resistance: list[KeyLevel]
    support: list[KeyLevel]
    draw_on_liquidity: DrawOnLiquidity

class SignalEntry(BaseModel):
    price: float = Field(description="Exact entry price")
    trigger: str = Field(description="The specific price action trigger")
    entry_type: str = Field(description="Type of order: Limit, Market, Stop-Limit")

class SignalTarget(BaseModel):
    price: float = Field(description="Target price level")
    label: str = Field(description="Target label, e.g., TP1, TP2")
    reward_points: float = Field(description="Points gained if hit")
    rr_ratio: float = Field(description="Risk/Reward ratio for this target")

class RiskManagement(BaseModel):
    stoploss: float = Field(description="Hard stoploss level")
    risk_points: float = Field(description="Total points at risk")
    targets: list[SignalTarget]
    suggested_lot_split: str = Field(description="Suggested partial profit taking strategy")

class TradeSignal(BaseModel):
    id: str = Field(description="Unique signal ID, e.g., SIG-001")
    direction: str = Field(description="Long or Short")
    status: str = Field(description="Pending or Active")
    confidence: str = Field(description="High, Medium, or Low")
    setup_type: str = Field(description="Type of setup")
    entry: SignalEntry
    risk_management: RiskManagement
    rationale: str = Field(description="Detailed reason for taking this trade")
    invalidation: str = Field(description="Specific condition that invalidates the setup")

class TradingReport(BaseModel):
    meta: MetaData
    market_context: MarketContext
    key_levels: KeyLevels
    signals: list[TradeSignal]
    risk_notes: str = Field(description="Overall risk disclaimers and warnings")

ICT_SYSTEM_INSTRUCTION = """
You are an expert quantitative analyst specializing in the ICT (Inner Circle Trader) 2022 Mentorship model. 
Your objective is to analyze price action based strictly on Liquidity, Market Structure Shifts (MSS), Displacement, and Fair Value Gaps (FVG). 
Do not use retail concepts like RSI, MACD, or trendlines.
"""

def generate_ai_analysis(user_prompt: str, max_retries: int = 5, initial_delay: int = 2) -> str:
    """Handles Gemini API calls with exponential backoff for server unavailability."""
    client = genai.Client()
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=ICT_SYSTEM_INSTRUCTION,
                    temperature=0.0, 
                    response_mime_type="application/json",
                    response_schema=TradingReport, 
                )
            )
            # Validate JSON response structure
            json.loads(response.text)
            return response.text

        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                delay = initial_delay * (2 ** attempt)
                print(f"\n[Warning] Server busy (503). Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                print(f"\n[Error] Encountered non-transient error: {e}")
                raise e
                
    raise RuntimeError(f"Failed to get data from Gemini after {max_retries} attempts due to high demand.")

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
        
        # ==========================================
        # PROMPTS & INSTRUCTIONS (ICT SPECIFIC)
        # ==========================================
        user_prompt = f"""
        Analyze the following multi-timeframe candle data for NIFTY 50 using strict ICT 2022 mechanics.

        ### 1-Day Candles (Macro Narrative & Draw on Liquidity)
        {csv_1d}

        ### 15-Minute Candles (Micro Price Action & Entry Models)
        {csv_15m}

        ### RULES FOR ANALYSIS:
        1. **Draw on Liquidity (DOL):** Identify unmitigated Buy-Side Liquidity (BSL) above old daily highs, or Sell-Side Liquidity (SSL) below old daily lows. The DOL must be the most obvious nearest peak or trough.
        2. **Market Structure Shift (MSS):** Look for a 15m candle that sweeps a short-term high/low and then reverses with strong displacement, breaking the opposing fractal structure.
        3. **Displacement & FVG:** The entry signal MUST be based on a return to a Fair Value Gap (a 3-candle imbalance) created during the displacement leg of the MSS.
        4. **Risk/Reward:** Stop losses must be placed strictly behind the swing high/low that created the MSS. Targets must scale out at opposing liquidity pools (BSL/SSL).

        Extract the requested technical parameters based STRICTLY on these ICT rules and output them matching the provided JSON schema.
        """

        print("Sending data to Gemini using 0.0 temperature...")
        analysis_result = generate_ai_analysis(user_prompt)
        print("\nSuccess! Analysis generated.")
        
        return jsonify({"status": "success", "analysis": analysis_result})
    except Exception as e:
        print(f"❌ AI ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)