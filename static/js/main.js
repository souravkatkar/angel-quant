/**
 * Formats a Date object into the string format required by the datetime-local input.
 */
function formatDateTimeLocal(date) {
    const pad = (num) => num.toString().padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/**
 * Sends a log message to the server to be stored in the centralized app logs.
 */
async function logToServer(level, message, exception = null) {
    // Console reflection
    const consoleFunc = console[level.toLowerCase()] || console.log;
    if (exception) {
        consoleFunc(`[Client ${level}] ${message}`, exception);
    } else {
        consoleFunc(`[Client ${level}] ${message}`);
    }

    try {
        await fetch('/api/logs/client', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                level: level,
                message: message,
                exception: exception ? (exception.stack || String(exception)) : null
            })
        });
    } catch (err) {
        console.error("Failed to send client log to server:", err);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    try {
        const startDateInput = document.getElementById('startDate');
        const endDateInput = document.getElementById('endDate');

        const now = new Date();
        endDateInput.value = formatDateTimeLocal(now);

        const startOfDay = new Date();
        startOfDay.setHours(0, 0, 0, 0);
        startDateInput.value = formatDateTimeLocal(startOfDay);
        // Setup Theme Toggle
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            if (document.documentElement.getAttribute('data-theme') === 'dark') {
                themeToggle.textContent = '☀️';
            } else {
                themeToggle.textContent = '🌙';
            }

            themeToggle.addEventListener('click', () => {
                const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
                if (isDark) {
                    document.documentElement.removeAttribute('data-theme');
                    localStorage.setItem('theme', 'light');
                    themeToggle.textContent = '🌙';
                    logToServer('INFO', 'User toggled theme to light');
                } else {
                    document.documentElement.setAttribute('data-theme', 'dark');
                    localStorage.setItem('theme', 'dark');
                    themeToggle.textContent = '☀️';
                    logToServer('INFO', 'User toggled theme to dark');
                }
            });
        }
        
        // Setup Sidebar switching logic
        const tabLive = document.getElementById('tab-live');
        const tabAi = document.getElementById('tab-ai');
        const tabChart = document.getElementById('tab-chart');
        const tabBacktest = document.getElementById('tab-backtest');
        
        const contentLive = document.getElementById('content-live');
        const contentAi = document.getElementById('content-ai');

        const allTabs = [tabLive, tabAi, tabChart, tabBacktest].filter(Boolean);

        function setActiveTab(activeTab) {
            allTabs.forEach(tab => tab.classList.remove('active'));
            activeTab.classList.add('active');
        }

        if (tabLive && tabAi) {
            tabLive.addEventListener('click', () => {
                setActiveTab(tabLive);
                contentLive.style.display = 'block';
                contentAi.style.display = 'none';
                logToServer('INFO', 'User switched to CSV Candle Data section');
            });
            
            tabAi.addEventListener('click', () => {
                setActiveTab(tabAi);
                contentLive.style.display = 'none';
                contentAi.style.display = 'block';
                logToServer('INFO', 'User switched to AI Market Analysis section');
            });
            
            if(tabChart) {
                tabChart.addEventListener('click', () => {
                    alert("Chart Window is coming soon!");
                    logToServer('INFO', 'User clicked placeholder Chart Window section');
                });
            }
            
            if(tabBacktest) {
                tabBacktest.addEventListener('click', () => {
                    alert("Backtesting is coming soon!");
                    logToServer('INFO', 'User clicked placeholder Backtesting section');
                });
            }
        }

        logToServer('INFO', 'Main application dashboard loaded successfully');
    } catch (e) {
        console.error("Error setting dates:", e);
        logToServer('ERROR', 'Error initializing application dates/theme', e);
    }
});

document.getElementById('aiAnalyzeBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('aiAnalyzeBtn');
    const output = document.getElementById('aiOutput');
    const symbol = document.getElementById('aiSymbol').value;

    btn.disabled = true;
    btn.textContent = 'Analyzing...';
    output.value = `Analyzing live market data for ${symbol}...\nPlease wait.`;

    logToServer('INFO', `User clicked Get Live Market Analysis for symbol: ${symbol}`);

    try {
        logToServer('INFO', 'Sending AI analysis request to /api/analyze');
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: symbol })
        });
        
        if (!response.ok) {
            let errorMsg = `HTTP ${response.status}`;
            try {
                const errJson = await response.json();
                if (errJson.message) errorMsg = errJson.message;
            } catch (e) {}
            throw new Error(errorMsg);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        output.value = ""; // Clear the "Please wait" text
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split("\n\n");
            
            for (const line of lines) {
                if (line.trim().startsWith("data: ")) {
                    let data;
                    try {
                        data = JSON.parse(line.trim().substring(6));
                        if (data.error) {
                            throw new Error(data.error);
                        }
                        if (data.text) {
                            output.value += data.text;
                            output.scrollTop = output.scrollHeight; // Auto-scroll
                        }
                    } catch (e) {
                        // Throw if it's our own error thrown above
                        if (e.message === data?.error || line.includes('"error"')) throw e;
                        console.warn("Partial chunk ignored", e);
                    }
                }
            }
        }
        logToServer('INFO', `AI Analysis streaming successfully completed for ${symbol}`);
    } catch (error) {
        output.value = 'Error generating analysis:\n\n' + error.message;
        if (!error.message.startsWith("Received unexpected format") && !error.message.startsWith("Failed to fetch") && !error.message.includes("failed:")) {
            logToServer('ERROR', `Error generating analysis: ${error.message}`, error);
        }
    } finally {
        btn.disabled = false;
        btn.textContent = 'Get Live Market Analysis';
    }
});

document.getElementById('fetchForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = document.getElementById('submitBtn');
    const errorMsg = document.getElementById('errorMsg');
    const outputSection = document.getElementById('outputSection');
    const csvOutput = document.getElementById('csvOutput');
    const tableContainer = document.getElementById('tableContainer');
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Fetching...';
    errorMsg.style.display = 'none';
    outputSection.style.display = 'none';
    csvOutput.value = '';
    tableContainer.innerHTML = '';

    const payload = {
        symbol: document.getElementById('symbol').value,
        interval: document.getElementById('interval').value,
        start_date: document.getElementById('startDate').value,
        end_date: document.getElementById('endDate').value
    };

    logToServer('INFO', `User submitted Fetch Data form: symbol=${payload.symbol}, interval=${payload.interval}, start=${payload.start_date}, end=${payload.end_date}`);

    try {
        const maxDaysMap = { "1m": 30, "3m": 60, "5m": 100, "10m": 100, "15m": 200, "30m": 200, "1h": 400, "1d": 2000 };
        const start = new Date(payload.start_date);
        const end = new Date(payload.end_date);
        const diffDays = (end - start) / (1000 * 60 * 60 * 24);
        const maxDays = maxDaysMap[payload.interval];
        
        if (end < start) {
            const validationErr = new Error("End Date cannot be before Start Date.");
            logToServer('WARNING', `Client-side validation failed: ${validationErr.message}`);
            throw validationErr;
        }
        if (diffDays > maxDays) {
            const validationErr = new Error(`Maximum allowed duration for this interval is ${maxDays} days. You selected ${Math.ceil(diffDays)} days.`);
            logToServer('WARNING', `Client-side validation failed: ${validationErr.message}`);
            throw validationErr;
        }

        logToServer('INFO', 'Sending historical data request to /api/data');
        const response = await fetch('/api/data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok && result.status === 'success') {
            csvOutput.value = result.csv;
            
            // Parse CSV and generate HTML table
            const rows = result.csv.trim().split(/\r?\n/);
            if (rows.length > 0) {
                let tableHtml = '<table class="data-table"><thead><tr>';
                const headers = rows[0].split(',');
                headers.forEach(header => { tableHtml += `<th>${header}</th>`; });
                tableHtml += '</tr></thead><tbody>';
                for (let i = 1; i < rows.length; i++) {
                    if (!rows[i]) continue;
                    const cols = rows[i].split(',');
                    tableHtml += '<tr>';
                    cols.forEach(col => { tableHtml += `<td>${col}</td>`; });
                    tableHtml += '</tr>';
                }
                tableHtml += '</tbody></table>';
                tableContainer.innerHTML = tableHtml;
            }

            outputSection.style.display = 'block';
            logToServer('INFO', `Historical data response successfully received and parsed (${rows.length > 1 ? rows.length - 1 : 0} rows)`);
        } else {
            const serverErr = new Error(result.message || `Server returned HTTP ${response.status}`);
            logToServer('ERROR', `Historical data fetch API failed: ${serverErr.message}`);
            throw serverErr;
        }
    } catch (error) {
        console.error("Fetch Error:", error);
        errorMsg.textContent = "Error: " + error.message;
        errorMsg.style.display = 'block';
        if (!error.message.includes("End Date cannot be before") && !error.message.includes("Maximum allowed duration") && !error.message.includes("API failed")) {
            logToServer('ERROR', `Error fetching historical data: ${error.message}`, error);
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Fetch Data';
    }
});

document.getElementById('copyBtn').addEventListener('click', async () => {
    const csvText = document.getElementById('csvOutput').value;
    const copyBtn = document.getElementById('copyBtn');
    
    logToServer('INFO', `User clicked Copy CSV (length: ${csvText.length} characters)`);

    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(csvText);
        } else {
            // Fallback for non-HTTPS (HTTP) connections
            const textArea = document.createElement("textarea");
            textArea.value = csvText;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            textArea.remove();
        }
        const originalText = copyBtn.textContent;
        copyBtn.textContent = 'Copied!';
        logToServer('INFO', 'CSV copied to clipboard successfully');
        setTimeout(() => { copyBtn.textContent = originalText; }, 2000);
    } catch (err) {
        console.error("Copy failed:", err);
        logToServer('WARNING', `Copying to clipboard failed: ${err.message}`, err);
        alert("Unable to copy to clipboard. Your browser might block this action on HTTP.");
    }
});