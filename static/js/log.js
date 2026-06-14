/**
 * helper to escape HTML and prevent injection
 */
function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * Main module for logs dashboard
 */
document.addEventListener('DOMContentLoaded', () => {
    const filterForm = document.getElementById('filterForm');
    const filterIp = document.getElementById('filterIp');
    const filterRequestId = document.getElementById('filterRequestId');
    const filterErrorsOnly = document.getElementById('filterErrorsOnly');
    
    const logsTableBody = document.getElementById('logsTableBody');
    const logCountVal = document.getElementById('logCountVal');
    
    const traceSection = document.getElementById('traceSection');
    const tracedIdVal = document.getElementById('tracedIdVal');
    const timelineContainer = document.getElementById('timelineContainer');
    
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    const closeTraceBtn = document.getElementById('closeTraceBtn');
    const themeToggle = document.getElementById('themeToggle');

    // Theme logic
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

    /**
     * Fetch logs from backend
     */
    async function loadLogs() {
        logsTableBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-8 text-neutral-content">
                    <span class="loading loading-spinner loading-md"></span> Loading logs...
                </td>
            </tr>
        `;

        const ip = filterIp.value.trim();
        const requestId = filterRequestId.value.trim();
        const errorsOnly = filterErrorsOnly.checked;

        const params = new URLSearchParams();
        if (ip) params.append('ip', ip);
        if (requestId) params.append('request_id', requestId);
        if (errorsOnly) params.append('level', 'ERROR');

        try {
            const response = await fetch(`/api/logs?${params.toString()}`);
            if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
            
            const logs = await response.json();
            renderLogsTable(logs);
            
            // If request ID is specified, also build & display the chronological trace timeline
            if (requestId && logs.length > 0) {
                showTrace(requestId, logs);
            } else {
                hideTrace();
            }
        } catch (error) {
            console.error("Failed to load logs:", error);
            logsTableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center py-8 text-error font-bold">
                        Failed to fetch logs: ${error.message}
                    </td>
                </tr>
            `;
            logCountVal.textContent = "Error";
        }
    }

    /**
     * Renders logs in the table
     */
    function renderLogsTable(logs) {
        logCountVal.textContent = `Showing ${logs.length} entries`;
        if (logs.length === 0) {
            logsTableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center py-8 text-neutral-content">
                        No logs match the current filters.
                    </td>
                </tr>
            `;
            return;
        }

        logsTableBody.innerHTML = '';
        logs.forEach(log => {
            const tr = document.createElement('tr');
            
            // Level badge class selection
            let badgeClass = 'badge-info';
            if (log.level === 'WARNING') {
                badgeClass = 'badge-warning';
            } else if (log.level === 'ERROR' || log.level === 'CRITICAL') {
                badgeClass = 'badge-error';
            }
            
            // Make Request ID clickable to trace
            const reqIdHtml = log.request_id !== '-' ? 
                `<button type="button" class="btn btn-xs btn-outline btn-primary font-mono trace-link" data-reqid="${log.request_id}">${log.request_id}</button>` : 
                `<span class="text-neutral-content">-</span>`;

            // Setup exception details if present
            let messageHtml = escapeHtml(log.message);
            if (log.exception) {
                messageHtml = `
                    <details class="collapse bg-base-200/30 border border-base-300 rounded-lg">
                        <summary class="collapse-title text-sm font-semibold py-2 px-3 min-h-0 flex items-start gap-2 flex-wrap">
                            <span class="mt-0.5">❌</span>
                            <span class="break-words whitespace-normal flex-1 min-w-0">${escapeHtml(log.message)}</span>
                            <span class="badge badge-sm badge-outline text-[10px] text-neutral-content/70 whitespace-nowrap ml-auto self-center">(Click to view traceback)</span>
                        </summary>
                        <div class="collapse-content px-3 py-1 mt-1">
                            <pre class="text-xs text-error p-3 rounded bg-black/60 overflow-x-auto select-text font-mono max-h-40">${escapeHtml(log.exception)}</pre>
                        </div>
                    </details>
                `;
            }

            tr.innerHTML = `
                <td class="font-semibold text-neutral-content whitespace-nowrap">${log.timestamp}</td>
                <td><span class="badge ${badgeClass} text-white uppercase text-[10px] font-bold px-2.5 py-1 select-none">${log.level}</span></td>
                <td class="font-mono font-medium">${escapeHtml(log.ip)}</td>
                <td class="text-center">${reqIdHtml}</td>
                <td class="font-bold text-neutral-content/80 text-xs">${escapeHtml(log.module)}</td>
                <td class="break-words">${messageHtml}</td>
            `;

            logsTableBody.appendChild(tr);
        });

        // Add trace triggers
        document.querySelectorAll('.trace-link').forEach(btn => {
            btn.addEventListener('click', () => {
                const reqId = btn.getAttribute('data-reqid');
                triggerTraceFlow(reqId);
            });
        });
    }

    /**
     * Start tracing for a specific request ID
     */
    async function triggerTraceFlow(reqId) {
        // Clear IP filter and check errors filter to ensure we see all steps for this request ID
        filterIp.value = '';
        filterErrorsOnly.checked = false;
        filterRequestId.value = reqId;
        
        // Load logs with this request ID
        await loadLogs();
    }

    /**
     * Renders visual chronological timeline of exact steps
     */
    function showTrace(requestId, logs) {
        tracedIdVal.textContent = `Request ID: ${requestId}`;
        traceSection.classList.remove('hidden');
        timelineContainer.innerHTML = '';

        // Timeline needs chronological order (oldest first)
        const sortedLogs = [...logs].reverse();

        sortedLogs.forEach((log, index) => {
            const li = document.createElement('li');
            li.className = 'w-full mb-3';

            let lineClass = 'bg-primary';
            let dotColor = 'text-primary';
            let cardBg = 'bg-base-200/40';
            
            if (log.level === 'WARNING') {
                dotColor = 'text-warning';
                lineClass = 'bg-warning';
                cardBg = 'bg-warning/5 border border-warning/20';
            } else if (log.level === 'ERROR' || log.level === 'CRITICAL') {
                dotColor = 'text-error';
                lineClass = 'bg-error';
                cardBg = 'bg-error/5 border border-error/20';
            }

            const hrStart = index > 0 ? `<hr class="${lineClass}" />` : '';
            const hrEnd = index < sortedLogs.length - 1 ? `<hr class="${lineClass}" />` : '';

            let excHtml = '';
            if (log.exception) {
                excHtml = `
                    <details class="collapse bg-black/40 rounded-lg mt-2">
                        <summary class="collapse-title text-xs text-error font-semibold py-1 px-3 min-h-0">
                            🔍 View Traceback Details
                        </summary>
                        <div class="collapse-content px-3 py-1">
                            <pre class="text-xs text-error p-3 overflow-x-auto select-text font-mono max-h-48">${escapeHtml(log.exception)}</pre>
                        </div>
                    </details>
                `;
            }

            li.innerHTML = `
                ${hrStart}
                <div class="timeline-middle">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5 ${dotColor}">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd" />
                    </svg>
                </div>
                <div class="timeline-end timeline-box rounded-xl p-4 w-full ${cardBg}">
                    <div class="flex justify-between items-center mb-1">
                        <span class="text-xs font-semibold text-neutral-content/60 font-mono">${log.timestamp}</span>
                        <span class="text-xs font-bold text-neutral-content/85">${escapeHtml(log.module)}</span>
                    </div>
                    <div class="text-sm font-semibold leading-relaxed mt-1 text-neutral-content">${escapeHtml(log.message)}</div>
                    ${excHtml}
                </div>
                ${hrEnd}
            `;

            timelineContainer.appendChild(li);
        });

        // Scroll to trace view
        traceSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function hideTrace() {
        traceSection.classList.add('hidden');
        timelineContainer.innerHTML = '';
    }

    // Event Listeners
    filterForm.addEventListener('submit', (e) => {
        e.preventDefault();
        loadLogs();
    });

    clearFiltersBtn.addEventListener('click', () => {
        filterIp.value = '';
        filterRequestId.value = '';
        filterErrorsOnly.checked = false;
        loadLogs();
    });

    refreshBtn.addEventListener('click', () => {
        loadLogs();
    });

    closeTraceBtn.addEventListener('click', () => {
        filterRequestId.value = '';
        loadLogs();
    });

    // Simplify download to standard browser-driven HTTP request with a cache buster
    const downloadLogsTxtBtn = document.getElementById('downloadLogsTxtBtn');
    if (downloadLogsTxtBtn) {
        downloadLogsTxtBtn.addEventListener('click', () => {
            downloadLogsTxtBtn.href = '/api/logs/download?fmt=txt&t=' + Date.now();
        });
    }

    const downloadLogsJsonBtn = document.getElementById('downloadLogsJsonBtn');
    if (downloadLogsJsonBtn) {
        downloadLogsJsonBtn.addEventListener('click', () => {
            downloadLogsJsonBtn.href = '/api/logs/download?fmt=json&t=' + Date.now();
        });
    }

    // Initial load
    loadLogs();
});
