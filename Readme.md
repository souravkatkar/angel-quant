# angel-quant

![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![Flask](https://img.shields.io/badge/Flask-Web%20Framework-lightgrey.svg)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg)
![Status](https://img.shields.io/badge/Status-Active-success.svg)

Originally engineered as a personal utility for extracting market data, this application has evolved into a comprehensive trading dashboard featuring integrated AI intelligence. It is specifically built to supply clean OHLC data and technical analysis to traders, AI models, and algorithmic tools for analyzing trends and generating trade signals.

---

**⚠️ Note:** This is a personal project built for educational purposes and individual experimentation. It is not affiliated with or endorsed by Angel One. Use any financial data or trading strategies at your own risk.

## Live Demo
The platform is currently hosted online via the Oracle Cloud Free Tier, making market data instantly accessible from any device or location.
🌐 **[Live Instance](http://80.225.238.68/)**

## Features
- **Modern Web Interface:** Fully responsive, modern dual-tab UI (CSV Candle Data and AI Market Intelligence) using Tailwind CSS and DaisyUI, featuring a Dark/Light mode toggle and a high-performance CSS-only animated mesh gradient background.
- **SmartAPI Integration:** Automated login, TOTP generation, JWT token caching, and background session refreshing.
- **Live Data Retrieval:** Fetch precise recent OHLC data via Angel One's API for indices like NIFTY and BANK NIFTY across customizable timeframes.
- **Data Export & Visualization:** View data in an elegant, zebra-striped HTML table and instantly copy it as a CSV for AI ingestion, Excel, or Python workflows.
- 🚀 **AI Market Intelligence:** Integrated with Google's Gemini API to provide live, multi-timeframe technical analysis. Automatically evaluates the last 4 weeks of Daily data (macro trend) alongside 1 week of 15-minute data (micro price action) to deliver instant support/resistance levels and a directional bias.
- **Systematic Logging & Monitoring:** Built-in application logging with a dedicated `/log` route for tracking errors, monitoring application health, and filtering logs by specific IP addresses.

## Prerequisites
- Python 3.8+
- Angel One API credentials (Client ID, MPIN, API Key, TOTP Secret)
- Google Gemini API Key

## Project Structure
```text
angel-quant/
├── app.py                  # Main Flask application and API routing
├── client/                 # Angel One SmartAPI backend logic & caching
├── static/js/main.js       # Client-side UI logic and theme management
└── templates/
    ├── index.html          # Frontend dashboard interface
    └── log.html            # System logging and error monitoring interface
```

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
   GEMINI_API_KEY=your_gemini_api_key
   CLIENT_LOCAL_IP=127.0.0.1
   CLIENT_PUBLIC_IP=127.0.0.1
   MAC_ADDRESS=00:00:00:00:00:00
   ```

## Local Development

1. Start the Flask development server:
   ```bash
   python app.py
   ```

2. Open your web browser and navigate to `http://127.0.0.1:5000/`.

3. Select your desired Index, Interval, and Date Range, then click **Fetch Data**.

## Cloud Deployment & CI/CD
This project is production-ready and is deployed for 24/7 access using the following stack and automation:
- **CI/CD Pipeline (GitHub Actions):** Deployments are fully automated. Pushing code to the `main` branch triggers a GitHub Action that securely connects to the cloud instance, pulls the latest updates, installs new dependencies, and safely restarts the application.
- **Gunicorn:** Acts as the robust WSGI HTTP backend server (`gunicorn --workers 3 --bind 127.0.0.1:5000 app:app`).
- **Nginx:** Configured as a reverse proxy to securely route public web traffic (Port 80/443) to the internal Gunicorn service.
- **Systemd:** Used to daemonize the application, ensuring it runs continuously in the background and restarts automatically on server reboots.