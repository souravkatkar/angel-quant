import os
import json
import time
import uuid
import logging
import io
import hashlib
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, g, has_request_context, send_file
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException

from google import genai
from google.genai import types

from client.connection import get_session
from client.historical import get_candle_data


load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Global Cache for AI Analysis ──────────────────────────────────────────────────
ANALYSIS_CACHE = {}

# ── Centralized Logging Setup ──────────────────────────────────────────────────
class RequestFilter(logging.Filter):
    """Filters log records to dynamically inject Flask client IP and request ID."""
    
    def is_valid_ip(self, ip_str):
        if not ip_str:
            return False
        if "://" in ip_str:
            return False
        # Catch common domain formats
        if re.search(r'[a-zA-Z-]+\.[a-zA-Z]{2,}', ip_str):
            return False
        return True

    def filter(self, record):
        if has_request_context():
            ip_candidate = None
            headers_to_check = ['X-Real-IP', 'CF-Connecting-IP', 'X-Forwarded-For']
            
            for header in headers_to_check:
                val = request.headers.get(header)
                if val:
                    first_ip = val.split(',')[0].strip()
                    if self.is_valid_ip(first_ip):
                        ip_candidate = first_ip
                        break
                        
            if not ip_candidate and self.is_valid_ip(request.remote_addr):
                ip_candidate = request.remote_addr
                
            record.ip = ip_candidate or 'UNKNOWN'
            record.request_id = getattr(g, 'request_id', '-')
        else:
            record.ip = 'SYSTEM'
            record.request_id = '-'
        return True

class JsonFormatter(logging.Formatter):
    """Custom formatter to structure logs as JSON Lines (JSONL)."""
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "ip": getattr(record, 'ip', 'SYSTEM'),
            "request_id": getattr(record, 'request_id', '-'),
            "module": record.name,
            "message": record.getMessage()
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        elif getattr(record, 'client_exception', None):
            log_entry["exception"] = record.client_exception
        return json.dumps(log_entry)

# Create parent logger for angel_quant application
logger = logging.getLogger("angel_quant")
logger.setLevel(logging.INFO)
logger.propagate = False  # Avoid duplicating output to standard root logger

request_filter = RequestFilter()

# Console handler (stdout) for readability during development
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] [%(ip)s] [%(request_id)s] %(name)s: %(message)s',
    "%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(console_formatter)
console_handler.addFilter(request_filter)
logger.addHandler(console_handler)

# File handler writing JSON lines for parser robustness
log_file_path = os.path.join(BASE_DIR, 'app.log.jsonl')
file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
file_handler.setFormatter(JsonFormatter())
file_handler.addFilter(request_filter)
logger.addHandler(file_handler)

app_logger = logging.getLogger("angel_quant.app")
client_logger = logging.getLogger("angel_quant.client")

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)

@app.before_request
def generate_request_id():
    """Flask request interceptor to trace requests using request IDs."""
    g.request_id = str(uuid.uuid4())[:8]

@app.errorhandler(Exception)
def handle_exception(e):
    """Ensure all unhandled application crashes return JSON instead of a Flask HTML 500 page."""
    if isinstance(e, HTTPException):
        # Suppress logging 404/405 errors (typically caused by malicious bot scanners)
        if getattr(e, 'code', None) not in [404, 405]:
            app_logger.warning(f"HTTP Exception {e.code}: {getattr(e, 'description', str(e))}")
        return jsonify({"status": "error", "message": getattr(e, 'description', str(e))}), getattr(e, 'code', 500)
        
    url = request.url if has_request_context() else "Unknown URL"
    app_logger.error(f"UNHANDLED SERVER ERROR on {url}: {str(e)}", exc_info=True)
    return jsonify({"status": "error", "message": f"Internal Server Error (500). {str(e)}"}), 500

app_logger.info("Initializing application...")

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

@app.route('/favicon.ico')
def favicon():
    """Handle automatic browser requests for favicon to prevent 404 logs."""
    return '', 204

@app.route('/')
def index():
    """Renders the main UI."""
    return render_template('index.html')


@app.route('/log')
def log_dashboard():
    """Renders the log viewer dashboard."""
    return render_template('log.html')


@app.route('/api/logs/download')
def download_logs():
    """Allows downloading the logs in a formatted human-readable text format."""
    if not os.path.exists(log_file_path):
        app_logger.warning("Download logs failed: log file not found.")
        return jsonify({"status": "error", "message": "Log file not found"}), 404
        
    try:
        log_format = request.args.get('fmt', 'txt').lower()
        
        if log_format == 'json':
            logs = []
            with open(log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            logs.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            
            json_content = json.dumps(logs, indent=2)
            buffer = io.BytesIO(json_content.encode('utf-8'))
            response = send_file(
                buffer,
                as_attachment=True,
                download_name="app_logs.json",
                mimetype="application/json"
            )
        else:
            formatted_logs = []
            with open(log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        timestamp = entry.get("timestamp", "-")
                        level = entry.get("level", "INFO")
                        ip = entry.get("ip", "-")
                        req_id = entry.get("request_id", "-")
                        module = entry.get("module", "-")
                        message = entry.get("message", "")
                        
                        # Formatted text line
                        log_line = f"[{timestamp}] [{level}] [{ip}] [{req_id}] {module}: {message}"
                        
                        # Handle tracebacks elegantly
                        if "exception" in entry and entry["exception"]:
                            log_line += f"\n  Exception details:\n"
                            indented_exc = "\n".join(f"    {l}" for l in entry["exception"].splitlines())
                            log_line += indented_exc + "\n"
                            
                        formatted_logs.append(log_line)
                    except Exception:
                        formatted_logs.append(line)
                        
            text_content = "\n".join(formatted_logs)
            buffer = io.BytesIO(text_content.encode('utf-8'))
            
            response = send_file(
                buffer,
                as_attachment=True,
                download_name="app_logs.txt",
                mimetype="text/plain"
            )
            
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        app_logger.error(f"Failed to generate formatted log download: {str(e)}")
        return jsonify({"status": "error", "message": f"Could not generate log file: {str(e)}"}), 500


@app.route('/api/logs/client', methods=['POST'])
def client_log():
    """Receives JSON log telemetry from frontend client and routes to application logger."""
    try:
        data = request.json or {}
        level = data.get('level', 'INFO').upper()
        message = data.get('message', '')
        exception = data.get('exception')
        
        extra = {}
        if exception:
            extra['client_exception'] = exception
            
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        log_level = level_map.get(level, logging.INFO)
        client_logger.log(log_level, message, extra=extra)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        app_logger.error(f"Failed to log client event: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/api/logs')
def api_logs():
    """Returns application logs with optional IP, Level, and Request ID filtering."""
    ip_filter = request.args.get('ip', '').strip()
    level_filter = request.args.get('level', '').strip()
    request_id_filter = request.args.get('request_id', '').strip()
    
    logs = []
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            app_logger.error(f"Failed to read log file: {str(e)}")
            return jsonify({"status": "error", "message": "Could not read logs"}), 500
            
    # Apply filtering
    filtered_logs = []
    for entry in logs:
        if ip_filter and entry.get('ip') != ip_filter:
            continue
        if level_filter:
            if level_filter == 'ERROR':
                if entry.get('level') not in ('ERROR', 'CRITICAL'):
                    continue
            elif entry.get('level') != level_filter:
                continue
        if request_id_filter and entry.get('request_id') != request_id_filter:
            continue
        filtered_logs.append(entry)
        
    # Show newest logs first (reverse order)
    filtered_logs.reverse()
    
    # Return last 1000 logs to prevent rendering overload
    return jsonify(filtered_logs[:1000])


@app.route('/api/data', methods=['POST'])
def fetch_data():
    """API Endpoint to fetch data based on UI form submission."""
    app_logger.info("🚀 NEW FETCH REQUEST TRIGGERED")
    try:
        data = request.json
        app_logger.info(f"📦 Received Payload: {data}")
        
        ui_symbol = data.get('symbol')
        ui_interval = data.get('interval')
        start_date = data.get('start_date') # Expected from UI: "YYYY-MM-DDTHH:MM"
        end_date = data.get('end_date')     # Expected from UI: "YYYY-MM-DDTHH:MM"

        if not all([ui_symbol, ui_interval, start_date, end_date]):
            app_logger.warning("Validation failed: Missing required fields.")
            return jsonify({"status": "error", "message": "All fields are required"}), 400

        # Map inputs to Angel One API expectations
        token = SYMBOL_MAP.get(ui_symbol, "99926000")
        api_interval = INTERVAL_MAP.get(ui_interval, "FIVE_MINUTE")
        
        # Convert HTML5 datetime-local (T) to AngelOne format (Space)
        start_date_formatted = start_date.replace("T", " ")
        end_date_formatted = end_date.replace("T", " ")

        app_logger.info("🔑 Checking Angel One Authentication...")
        session = get_session()
        auth_token = session['auth_token']

        app_logger.info(f"📈 Fetching from Angel One: {token} | {api_interval} | {start_date_formatted} to {end_date_formatted}")
        df = get_candle_data(auth_token, token, api_interval, start_date_formatted, end_date_formatted)

        if df.empty:
            app_logger.warning("Angel One API returned NO DATA for this time range.")
            return jsonify({"status": "error", "message": "Angel One returned empty data. Check if the market was open during this date range."}), 400

        # Remove the volume column as requested
        if 'volume' in df.columns:
            df.drop(columns=['volume'], inplace=True)

        app_logger.info(f"✅ SUCCESS: Fetched {len(df)} candle rows.")
        return jsonify({"status": "success", "csv": df.to_csv()})

    except Exception as e:
        app_logger.error(f"BACKEND ERROR: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/analyze', methods=['POST'])
def analyze_market():
    """API Endpoint to fetch historical data and analyze it using Gemini."""
    app_logger.info("🤖 NEW AI ANALYSIS REQUEST TRIGGERED")
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
        
        app_logger.info("🔑 Checking Angel One Authentication...")
        session = get_session()
        auth_token = session['auth_token']
        
        app_logger.info(f"📈 Fetching 15-min data ({one_week_str} to {now_str})...")
        df_15m = get_candle_data(auth_token, token, "FIFTEEN_MINUTE", one_week_str, now_str)
        
        app_logger.info(f"📈 Fetching 1-day data ({four_weeks_str} to {now_str})...")
        df_1d = get_candle_data(auth_token, token, "ONE_DAY", four_weeks_str, now_str)
        
        csv_15m = df_15m.to_csv(index=False) if not df_15m.empty else "No 15m data available."
        csv_1d = df_1d.to_csv(index=False) if not df_1d.empty else "No 1d data available."
        
        # Check cache before proceeding
        data_hash = hashlib.md5((csv_1d + csv_15m).encode('utf-8')).hexdigest()
        if ui_symbol in ANALYSIS_CACHE and ANALYSIS_CACHE[ui_symbol]['hash'] == data_hash:
            app_logger.info("Market data unchanged. Returning cached AI analysis.")
            def cached_stream():
                yield f"data: {json.dumps({'text': ANALYSIS_CACHE[ui_symbol]['response']})}\n\n"
            return app.response_class(cached_stream(), mimetype='text/event-stream')
        
        if "GEMINI_API_KEY" not in os.environ:
            raise ValueError("GEMINI_API_KEY not found in environment.")
            
        app_logger.info("🧠 Sending data to Gemini...")
        
        user_prompt = f"""
        Analyze the following historical price data for {ui_symbol} and provide a brief, actionable market summary.
        Identify the current trend, key support/resistance levels, and a short-term bias. 
        Keep the response concise (under 150 words) to ensure fast processing.

        ### 1-Day Candles (Macro)
        {csv_1d}

        ### 15-Minute Candles (Micro)
        {csv_15m}
        """

        app_logger.info("Sending text generation streaming request to Gemini...")
        client = genai.Client()
        
        def stream_generator():
            models_to_try = ['gemini-2.5-flash']
            max_retries = 3
            last_error = None
            
            for model in models_to_try:
                for attempt in range(max_retries):
                    try:
                        app_logger.info(f"Trying model {model} (Attempt {attempt + 1}/{max_retries})...")
                        response_stream = client.models.generate_content_stream(
                            model=model,
                            contents=user_prompt,
                        )
                        
                        full_response = ""
                        # Yield the stream as Server-Sent Events (SSE)
                        for chunk in response_stream:
                            if chunk.text:
                                full_response += chunk.text
                                yield f"data: {json.dumps({'text': chunk.text})}\n\n"
                                
                        # Save to cache after successful streaming
                        ANALYSIS_CACHE[ui_symbol] = {'hash': data_hash, 'response': full_response}
                        app_logger.info("Success! Analysis stream completed and cached.")
                        return # Exit the generator on success
                        
                    except Exception as e:
                        last_error = e
                        error_msg = str(e)
                        if "503 UNAVAILABLE" in error_msg or "high demand" in error_msg.lower() or "429" in error_msg:
                            backoff = 2 ** attempt
                            app_logger.warning(f"Model {model} overloaded/rate-limited. Retrying in {backoff}s...")
                            time.sleep(backoff)
                        else:
                            # Re-raise or yield error if it's unrelated
                            app_logger.error(f"Unrelated API Error: {error_msg}")
                            yield f"data: {json.dumps({'error': error_msg})}\n\n"
                            return
                
            # If we exhaust all models and retries
            app_logger.error("All retries and model fallbacks failed.")
            user_friendly_msg = "The AI model is currently experiencing high demand. Please try again in a few moments."
            yield f"data: {json.dumps({'error': user_friendly_msg})}\n\n"

        return app.response_class(stream_generator(), mimetype='text/event-stream')

    except Exception as e:
        error_msg = str(e)
        app_logger.error(f"AI ERROR: {error_msg}", exc_info=True)
        return jsonify({"status": "error", "message": error_msg}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)