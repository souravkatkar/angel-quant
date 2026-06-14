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
        
        // Setup Tab switching logic
        const tabLive = document.getElementById('tab-live');
        const tabAi = document.getElementById('tab-ai');
        const contentLive = document.getElementById('content-live');
        const contentAi = document.getElementById('content-ai');

        if (tabLive && tabAi) {
            tabLive.addEventListener('click', () => {
                tabLive.classList.add('active');
                tabAi.classList.remove('active');
                contentLive.style.display = 'block';
                contentAi.style.display = 'none';
                logToServer('INFO', 'User switched to Live Market Data tab');
            });
            
            tabAi.addEventListener('click', () => {
                tabAi.classList.add('active');
                tabLive.classList.remove('active');
                contentLive.style.display = 'none';
                contentAi.style.display = 'block';
                logToServer('INFO', 'User switched to AI Market Analysis tab');
            });
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
        
        const responseText = await response.text();
        let result;
        try {
            result = JSON.parse(responseText);
        } catch (e) {
            const parseErr = new Error(`Received unexpected format (HTTP ${response.status}). Raw response:\n\n${responseText}`);
            logToServer('ERROR', 'Failed to parse AI Analysis JSON response from server', parseErr);
            throw parseErr;
        }
        
        if (response.ok && result.status === 'success') {
            try {
                output.value = JSON.stringify(JSON.parse(result.analysis), null, 2);
                logToServer('INFO', `AI Analysis response successfully received and parsed as JSON for ${symbol}`);
            } catch (parseError) {
                output.value = result.analysis;
                logToServer('INFO', `AI Analysis response successfully received and loaded as plain text for ${symbol}`);
            }
        } else {
            const apiErr = new Error(result.message || 'Failed to fetch analysis');
            logToServer('ERROR', `AI Analysis failed: ${apiErr.message}`, apiErr);
            throw apiErr;
        }
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