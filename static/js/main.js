/**
 * Formats a Date object into the string format required by the datetime-local input.
 */
function formatDateTimeLocal(date) {
    const pad = (num) => num.toString().padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
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
            } else {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
                themeToggle.textContent = '☀️';
            }
        });

        console.log("✓ main.js loaded successfully and dates populated.");
    } catch (e) {
        console.error("Error setting dates:", e);
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

    try {
        const maxDaysMap = { "1m": 30, "3m": 60, "5m": 100, "10m": 100, "15m": 200, "30m": 200, "1h": 400, "1d": 2000 };
        const start = new Date(payload.start_date);
        const end = new Date(payload.end_date);
        const diffDays = (end - start) / (1000 * 60 * 60 * 24);
        const maxDays = maxDaysMap[payload.interval];
        
        if (end < start) throw new Error("End Date cannot be before Start Date.");
        if (diffDays > maxDays) throw new Error(`Maximum allowed duration for this interval is ${maxDays} days. You selected ${Math.ceil(diffDays)} days.`);

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
        } else {
            throw new Error(result.message || `Server returned HTTP ${response.status}`);
        }
    } catch (error) {
        console.error("Fetch Error:", error);
        errorMsg.textContent = "Error: " + error.message;
        errorMsg.style.display = 'block';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Fetch Data';
    }
});

document.getElementById('copyBtn').addEventListener('click', async () => {
    const csvText = document.getElementById('csvOutput').value;
    const copyBtn = document.getElementById('copyBtn');
    
    await navigator.clipboard.writeText(csvText);
    const originalText = copyBtn.textContent;
    copyBtn.textContent = 'Copied!';
    setTimeout(() => { copyBtn.textContent = originalText; }, 2000);
});