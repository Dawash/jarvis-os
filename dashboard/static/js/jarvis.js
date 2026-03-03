/* ═══════════════════════════════════════════════════════════════
   JARVIS-OS Main Controller — Boot, WebSocket, Global Events
   ═══════════════════════════════════════════════════════════════ */

// ── Boot Sequence ───────────────────────────────────────────────
(function boot() {
    const bootLog = document.getElementById('boot-log');
    const progressBar = document.getElementById('boot-progress-bar');
    const bootScreen = document.getElementById('boot-screen');
    const desktopEnv = document.getElementById('desktop-env');

    const bootSteps = [
        { msg: 'Loading kernel modules...', delay: 300 },
        { msg: 'Initializing system control <span class="ok">[OK]</span>', delay: 400 },
        { msg: 'Starting memory subsystem <span class="ok">[OK]</span>', delay: 300 },
        { msg: 'Loading LLM providers <span class="ok">[OK]</span>', delay: 500 },
        { msg: 'Initializing agent framework <span class="ok">[OK]</span>', delay: 400 },
        { msg: 'Starting voice engine <span class="ok">[OK]</span>', delay: 350 },
        { msg: 'Loading plugin system <span class="ok">[OK]</span>', delay: 300 },
        { msg: 'Connecting to dashboard <span class="ok">[OK]</span>', delay: 350 },
        { msg: 'Establishing WebSocket link <span class="ok">[OK]</span>', delay: 400 },
        { msg: 'Running self-diagnostics <span class="ok">[PASS]</span>', delay: 500 },
        { msg: 'All subsystems operational', delay: 300 },
        { msg: '<span style="color:var(--primary);font-weight:bold">JARVIS-OS is ONLINE</span>', delay: 200 },
    ];

    let step = 0;
    function nextStep() {
        if (step >= bootSteps.length) {
            progressBar.style.width = '100%';
            setTimeout(() => {
                bootScreen.classList.add('fade-out');
                setTimeout(() => {
                    bootScreen.style.display = 'none';
                    desktopEnv.style.display = 'block';
                    initDesktop();
                }, 800);
            }, 500);
            return;
        }

        const s = bootSteps[step];
        const line = document.createElement('div');
        line.className = 'boot-line';
        line.innerHTML = s.msg;
        bootLog.appendChild(line);
        bootLog.scrollTop = bootLog.scrollHeight;

        progressBar.style.width = `${((step + 1) / bootSteps.length) * 100}%`;
        step++;
        setTimeout(nextStep, s.delay);
    }

    nextStep();
})();

// ── Desktop Initialization ──────────────────────────────────────
function initDesktop() {
    wm.init();

    // Start clock
    updateClock();
    setInterval(updateClock, 1000);

    // Start system stats polling
    updateSystemStats();
    setInterval(updateSystemStats, 3000);

    // Connect WebSocket
    connectWebSocket();

    // Setup global keyboard shortcuts
    setupShortcuts();

    // Setup notification panel
    document.getElementById('btn-notifications').addEventListener('click', toggleNotifications);

    // Setup drag-and-drop on desktop
    setupDesktopDrop();

    // Check if API keys are set — show setup wizard if not
    checkFirstBoot();
}

// ── First-Boot Setup Wizard (in-dashboard) ──────────────────────
async function checkFirstBoot() {
    try {
        const res = await fetch('/api/setup/status');
        const status = await res.json();
        if (!status.any_configured) {
            openSetupWizard();
        } else {
            // Keys are good — open assistant
            openAssistant();
        }
    } catch (e) {
        // Server might not be fully up yet, just open assistant
        openAssistant();
    }
}

function openSetupWizard() {
    wm.createWindow({
        id: 'setup-wizard',
        title: 'FIRST LAUNCH SETUP',
        icon: '&#9881;',
        width: 600,
        height: 520,
        resizable: false,
        content: `
            <div style="padding:30px;height:100%;display:flex;flex-direction:column;align-items:center;text-align:center">
                <div class="arc-reactor" style="width:60px;height:60px;margin-bottom:20px"></div>
                <div style="font-family:var(--font-display);font-size:18px;letter-spacing:4px;color:var(--primary);margin-bottom:8px">WELCOME TO JARVIS-OS</div>
                <div style="font-family:var(--font-mono);font-size:12px;color:var(--text-dim);margin-bottom:30px">Configure your AI provider to get started</div>

                <div style="width:100%;text-align:left">
                    <div style="margin-bottom:20px">
                        <label style="font-family:var(--font-display);font-size:10px;letter-spacing:2px;color:var(--primary);text-transform:uppercase;display:block;margin-bottom:8px">LLM Provider</label>
                        <select id="setup-provider" style="width:100%;padding:10px;background:var(--bg-card);border:1px solid var(--border);color:var(--text-primary);border-radius:8px;font-family:var(--font-mono);font-size:14px" onchange="onSetupProviderChange()">
                            <option value="openai">OpenAI (GPT-4o)</option>
                            <option value="anthropic">Anthropic (Claude)</option>
                        </select>
                    </div>

                    <div style="margin-bottom:24px">
                        <label style="font-family:var(--font-display);font-size:10px;letter-spacing:2px;color:var(--primary);text-transform:uppercase;display:block;margin-bottom:8px">API Key</label>
                        <input type="password" id="setup-apikey" placeholder="sk-..." style="width:100%;padding:10px;background:var(--bg-card);border:1px solid var(--border);color:var(--text-primary);border-radius:8px;font-family:var(--font-mono);font-size:14px">
                        <div id="setup-hint" style="font-family:var(--font-mono);font-size:10px;color:var(--text-dim);margin-top:6px">
                            Get your key from <span style="color:var(--primary)">platform.openai.com/api-keys</span>
                        </div>
                    </div>

                    <div id="setup-error" style="display:none;padding:10px;border:1px solid var(--danger);border-radius:6px;color:var(--danger);font-family:var(--font-mono);font-size:12px;margin-bottom:16px;text-align:center"></div>
                    <div id="setup-success" style="display:none;padding:10px;border:1px solid var(--success);border-radius:6px;color:var(--success);font-family:var(--font-mono);font-size:12px;margin-bottom:16px;text-align:center"></div>

                    <button onclick="submitSetupWizard()" style="width:100%;padding:12px;border:none;background:linear-gradient(135deg,var(--primary),var(--secondary));color:white;font-family:var(--font-display);font-size:12px;letter-spacing:3px;border-radius:8px;cursor:pointer;transition:all 0.2s" onmouseover="this.style.boxShadow='0 0 25px var(--primary-dim)'" onmouseout="this.style.boxShadow='none'">
                        ACTIVATE JARVIS
                    </button>

                    <div style="font-family:var(--font-mono);font-size:10px;color:var(--text-dim);margin-top:16px;text-align:center">
                        You can add more providers later in Settings
                    </div>
                </div>
            </div>
        `,
    });
}

function onSetupProviderChange() {
    const provider = document.getElementById('setup-provider').value;
    const hint = document.getElementById('setup-hint');
    if (provider === 'openai') {
        hint.innerHTML = 'Get your key from <span style="color:var(--primary)">platform.openai.com/api-keys</span>';
    } else {
        hint.innerHTML = 'Get your key from <span style="color:var(--primary)">console.anthropic.com/settings/keys</span>';
    }
}

async function submitSetupWizard() {
    const provider = document.getElementById('setup-provider').value;
    const apiKey = document.getElementById('setup-apikey').value.trim();
    const errEl = document.getElementById('setup-error');
    const successEl = document.getElementById('setup-success');

    errEl.style.display = 'none';
    successEl.style.display = 'none';

    if (!apiKey) {
        errEl.textContent = 'Please enter an API key';
        errEl.style.display = 'block';
        return;
    }

    if (provider === 'openai' && !apiKey.startsWith('sk-')) {
        errEl.textContent = 'OpenAI keys typically start with sk-';
        errEl.style.display = 'block';
        return;
    }

    try {
        const res = await fetch('/api/setup/apikey', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, api_key: apiKey }),
        });
        const data = await res.json();

        if (data.status === 'success') {
            successEl.textContent = 'API key saved! JARVIS is now active.';
            successEl.style.display = 'block';
            setTimeout(() => {
                wm.closeWindow('setup-wizard');
                openAssistant();
                addNotification('API key configured. JARVIS is ready.', 'success');
            }, 1500);
        } else {
            errEl.textContent = data.message || 'Failed to save key';
            errEl.style.display = 'block';
        }
    } catch (e) {
        errEl.textContent = 'Connection error: ' + e.message;
        errEl.style.display = 'block';
    }
}

// ── WebSocket Connection ────────────────────────────────────────
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws`;

    const ws = new WebSocket(wsUrl);
    window.jarvisWS = ws;

    ws.onopen = () => {
        console.log('WebSocket connected');
        document.getElementById('global-status-dot').style.background = 'var(--success)';
        document.getElementById('global-status').textContent = 'ONLINE';
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWSMessage(data);
        } catch (e) {
            console.error('WS parse error:', e);
        }
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected — reconnecting in 3s');
        document.getElementById('global-status-dot').style.background = 'var(--danger)';
        document.getElementById('global-status').textContent = 'RECONNECTING';
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
        console.error('WS error:', err);
    };
}

// ── Agentic Task Tracker State ──────────────────────────────────
window._activeTaskId = null;

function handleWSMessage(data) {
    switch (data.type) {
        case 'command_accepted':
            showTyping(false);
            showPlanningIndicator();
            break;

        case 'command_result':
            showTyping(false);
            removePlanningIndicator();
            if (window._activeTaskId) {
                finalizeTaskProgress(data.status === 'completed' ? 'completed' : 'error');
            }
            if (data.result && data.result !== '[CLEAR]') {
                addChatMessage('jarvis', data.result);
            }
            if (data.result === '[CLEAR]') {
                const chat = document.getElementById('assistant-chat');
                if (chat) chat.innerHTML = '';
            }
            if (data.error) {
                addChatMessage('system', `Error: ${data.error}`);
            }
            window._activeTaskId = null;
            break;

        case 'kernel_event':
            handleKernelEvent(data.event);
            break;

        case 'agent_cancelled':
            finalizeTaskProgress('cancelled');
            window._activeTaskId = null;
            addNotification('Agent cancelled', 'warning');
            break;

        case 'voice_transcript':
            document.getElementById('voice-transcript').textContent = data.text;
            break;

        case 'voice_command':
            closeVoiceOverlay();
            addChatMessage('user', `[Voice] ${data.command}`);
            if (window.jarvisWS && window.jarvisWS.readyState === WebSocket.OPEN) {
                window.jarvisWS.send(JSON.stringify({
                    type: 'command',
                    command: data.command,
                    source: 'voice',
                }));
            }
            break;

        case 'system_stats':
            updateStatsDisplay(data.stats);
            break;

        case 'speak':
            if ('speechSynthesis' in window) {
                const utter = new SpeechSynthesisUtterance(data.text);
                utter.rate = 1.0;
                utter.pitch = 0.9;
                speechSynthesis.speak(utter);
            }
            break;

        case 'notification':
            addNotification(data.message, data.level || 'info');
            break;
    }
}

function handleKernelEvent(event) {
    if (!event) return;

    switch (event.type) {
        case 'agent.planning':
            removePlanningIndicator();
            showPlanningIndicator(event.data.message || 'Creating execution plan...');
            break;

        case 'agent.plan_ready':
            removePlanningIndicator();
            window._activeTaskId = event.data.agent_id;
            showTaskProgress(event.data.agent_id, event.data.plan, event.data.task);
            break;

        case 'agent.spawned':
            addNotification(`Agent spawned: ${event.data.name}`, 'info');
            if (!window._activeTaskId) window._activeTaskId = event.data.agent_id;
            break;

        case 'agent.step':
            updateTaskStep(event.data);
            break;

        case 'agent.completed':
            if (event.data.agent_id === window._activeTaskId) {
                finalizeTaskProgress(event.data.status === 'completed' ? 'completed' : 'error');
            }
            break;

        case 'system.boot':
            addNotification('System boot complete', 'success');
            break;
    }
}

// ── Planning Indicator ─────────────────────────────────────────
function showPlanningIndicator(message) {
    const chat = document.getElementById('assistant-chat');
    if (!chat) return;
    removePlanningIndicator();
    const el = document.createElement('div');
    el.id = 'planning-indicator';
    el.className = 'planning-indicator';
    el.innerHTML = `
        <div class="planning-spinner"></div>
        <div class="planning-text">${escapeHTML(message || 'Analyzing task and creating plan...')}</div>
    `;
    chat.appendChild(el);
    chat.scrollTop = chat.scrollHeight;
}

function removePlanningIndicator() {
    const el = document.getElementById('planning-indicator');
    if (el) el.remove();
}

// ── Task Progress Tracker ──────────────────────────────────────
function showTaskProgress(agentId, plan, task) {
    const chat = document.getElementById('assistant-chat');
    if (!chat) return;

    const steps = plan?.steps || [];
    const containerId = `task-progress-${agentId}`;
    const existing = document.getElementById(containerId);
    if (existing) existing.remove();

    let stepsHtml = '';
    steps.forEach((step, i) => {
        if (step.tool === 'direct_response') return;
        stepsHtml += `
            <div class="task-step-item" id="step-${agentId}-${step.id || i}">
                <div class="task-step-icon pending" id="step-icon-${agentId}-${step.id || i}">${i + 1}</div>
                <div class="task-step-content">
                    <div class="task-step-desc">${escapeHTML(step.description)}</div>
                    ${step.tool && step.tool !== 'autonomous' ? `<span class="task-step-tool">${escapeHTML(step.tool)}</span>` : ''}
                </div>
            </div>
        `;
    });

    const el = document.createElement('div');
    el.id = containerId;
    el.className = 'task-progress-container';
    el.innerHTML = `
        <div class="task-progress-header">
            <div class="task-progress-title">Task Execution</div>
            <div class="task-progress-status">
                <span id="task-status-text-${agentId}">Running</span>
                <button class="task-cancel-btn" onclick="cancelActiveTask('${agentId}')">Cancel</button>
            </div>
        </div>
        <div class="task-progress-bar-wrapper">
            <div class="task-progress-bar">
                <div class="task-progress-fill indeterminate" id="task-progress-fill-${agentId}" style="width:0%"></div>
            </div>
        </div>
        ${steps.length > 0 ? `
            <div class="task-steps-toggle" onclick="toggleTaskSteps('${agentId}')">&#9654; ${steps.length} planned steps</div>
            <div class="task-steps-list" id="task-steps-${agentId}" style="display:none">${stepsHtml}</div>
        ` : ''}
    `;
    chat.appendChild(el);
    chat.scrollTop = chat.scrollHeight;
}

function toggleTaskSteps(agentId) {
    const list = document.getElementById(`task-steps-${agentId}`);
    if (!list) return;
    const isHidden = list.style.display === 'none';
    list.style.display = isHidden ? 'block' : 'none';
    const toggle = list.previousElementSibling;
    if (toggle) toggle.innerHTML = toggle.innerHTML.replace(isHidden ? '&#9654;' : '&#9660;', isHidden ? '&#9660;' : '&#9654;');
}

function updateTaskStep(data) {
    const agentId = data.agent_id;
    const step = data.step;
    const planProgress = data.plan_progress;
    if (!step) return;

    const chat = document.getElementById('assistant-chat');
    const container = document.getElementById(`task-progress-${agentId}`);

    if (planProgress && container) {
        const fill = document.getElementById(`task-progress-fill-${agentId}`);
        if (fill) { fill.classList.remove('indeterminate'); fill.style.width = `${planProgress.percent}%`; }
        const statusText = document.getElementById(`task-status-text-${agentId}`);
        if (statusText) statusText.textContent = `Step ${data.total_steps || step.step}`;
    }

    // Auto-expand steps list
    if (container) {
        const stepsList = document.getElementById(`task-steps-${agentId}`);
        if (stepsList && stepsList.style.display === 'none') {
            stepsList.style.display = 'block';
            const toggle = stepsList.previousElementSibling;
            if (toggle) toggle.innerHTML = toggle.innerHTML.replace('&#9654;', '&#9660;');
        }
    }

    // Show actions in chat
    if (step.actions && step.actions.length > 0) {
        step.actions.forEach(a => {
            const resultShort = typeof a.result === 'string' ? a.result.substring(0, 300) : '';
            let actionHtml = `<div class="agent-step">
                <div class="step-header">
                    <span class="step-number">STEP ${step.step}</span>
                    <span class="step-tool">${escapeHTML(a.tool)}</span>
                    <span class="step-tool" style="background:${a.status === 'error' ? 'rgba(255,59,48,0.2);color:var(--danger)' : 'rgba(48,209,88,0.2);color:var(--success)'}">${a.status || 'done'}</span>
                </div>
                ${resultShort ? `<div class="step-content">${escapeHTML(resultShort)}</div>` : ''}
            </div>`;
            if (step.thought) {
                addChatMessage('agent', step.thought, actionHtml);
                step.thought = '';
            } else {
                addChatMessage('agent', `Executing ${a.tool}...`, actionHtml);
            }
        });
    } else if (step.thought) {
        addChatMessage('agent', step.thought);
    }

    if (chat) chat.scrollTop = chat.scrollHeight;
}

function finalizeTaskProgress(status) {
    const agentId = window._activeTaskId;
    if (!agentId) return;
    const container = document.getElementById(`task-progress-${agentId}`);
    if (!container) return;

    const fill = document.getElementById(`task-progress-fill-${agentId}`);
    const statusText = document.getElementById(`task-status-text-${agentId}`);
    const cancelBtn = container.querySelector('.task-cancel-btn');

    if (fill) {
        fill.classList.remove('indeterminate');
        if (status === 'completed') { fill.style.width = '100%'; fill.style.background = 'linear-gradient(90deg, var(--success), var(--accent))'; }
        else { fill.style.background = 'var(--danger)'; }
    }
    if (statusText) {
        const labels = { completed: 'Completed', error: 'Failed', cancelled: 'Cancelled' };
        statusText.textContent = labels[status] || status;
        statusText.style.color = status === 'completed' ? 'var(--success)' : 'var(--danger)';
    }
    if (cancelBtn) cancelBtn.remove();
}

function cancelActiveTask(agentId) {
    if (window.jarvisWS && window.jarvisWS.readyState === WebSocket.OPEN) {
        window.jarvisWS.send(JSON.stringify({ type: 'cancel_agent', agent_id: agentId }));
    }
}

// ── Clock ───────────────────────────────────────────────────────
function updateClock() {
    const now = new Date();
    const time = now.toLocaleTimeString('en-US', { hour12: false });
    const date = now.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' });

    setText('sysbar-time', time);
    setText('sysbar-date', date);

    // Uptime
    const uptimeEl = document.getElementById('dock-uptime-val');
    if (uptimeEl && window._bootTime) {
        const secs = Math.floor((Date.now() - window._bootTime) / 1000);
        const h = Math.floor(secs / 3600);
        const m = Math.floor((secs % 3600) / 60);
        const s = secs % 60;
        uptimeEl.textContent = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    }
}
window._bootTime = Date.now();

// ── System Stats ────────────────────────────────────────────────
async function updateSystemStats() {
    try {
        const res = await fetch('/api/system/stats');
        const stats = await res.json();
        updateStatsDisplay(stats);
    } catch (e) {
        // Silent fail — stats will refresh next cycle
    }
}

function updateStatsDisplay(stats) {
    if (!stats) return;
    setText('top-cpu', (stats.cpu?.usage_percent || 0) + '%');
    setText('top-mem', (stats.memory?.percent || 0) + '%');

    // Sidebar metrics if assistant is open
    setText('cpu-val', (stats.cpu?.usage_percent || 0) + '%');
    setText('mem-val', (stats.memory?.percent || 0) + '%');
    setText('disk-val', (stats.disk?.percent || 0) + '%');
    setBar('cpu-bar', stats.cpu?.usage_percent);
    setBar('mem-bar', stats.memory?.percent);
    setBar('disk-bar', stats.disk?.percent);
}

// ── Notifications ───────────────────────────────────────────────
let notifications = [];

function addNotification(message, level = 'info') {
    const notif = {
        id: Date.now(),
        message,
        level,
        time: new Date().toLocaleTimeString(),
    };
    notifications.unshift(notif);
    if (notifications.length > 50) notifications.pop();

    // Update badge
    const badge = document.getElementById('notif-badge');
    if (badge) {
        badge.style.display = 'block';
        badge.textContent = Math.min(notifications.length, 99);
    }

    // Update panel
    renderNotifications();
}

function renderNotifications() {
    const list = document.getElementById('notif-list');
    if (!list) return;
    list.innerHTML = notifications.slice(0, 30).map(n => `
        <div class="notif-item">
            <div class="notif-item-title" style="color:var(--${n.level === 'error' ? 'danger' : n.level === 'warning' ? 'warning' : n.level === 'success' ? 'success' : 'primary'})">${escapeHTML(n.message)}</div>
            <div class="notif-item-time">${n.time}</div>
        </div>
    `).join('');
}

function toggleNotifications() {
    const panel = document.getElementById('notification-panel');
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
        const badge = document.getElementById('notif-badge');
        if (badge) badge.style.display = 'none';
    }
}

function clearNotifications() {
    notifications = [];
    renderNotifications();
    const badge = document.getElementById('notif-badge');
    if (badge) badge.style.display = 'none';
}

// ── Voice Control ───────────────────────────────────────────────
let isVoiceActive = false;
let recognition = null;

function toggleVoice() {
    if (isVoiceActive) {
        closeVoiceOverlay();
    } else {
        openVoiceOverlay();
    }
}

function openVoiceOverlay() {
    const overlay = document.getElementById('voice-overlay');
    overlay.classList.add('active');
    isVoiceActive = true;

    // Use Web Speech API for browser-based STT
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
            let transcript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                transcript += event.results[i][0].transcript;
            }
            document.getElementById('voice-transcript').textContent = transcript;
            document.getElementById('voice-status-text').textContent = 'Listening...';

            if (event.results[event.results.length - 1].isFinal) {
                closeVoiceOverlay();
                // Send as command
                if (transcript.trim()) {
                    if (!wm.isOpen('assistant')) openAssistant();
                    setTimeout(() => {
                        addChatMessage('user', `[Voice] ${transcript}`);
                        showTyping(true);
                        if (window.jarvisWS && window.jarvisWS.readyState === WebSocket.OPEN) {
                            window.jarvisWS.send(JSON.stringify({
                                type: 'command',
                                command: transcript,
                                source: 'voice',
                            }));
                        }
                    }, 300);
                }
            }
        };

        recognition.onerror = (e) => {
            document.getElementById('voice-status-text').textContent = `Error: ${e.error}`;
            setTimeout(closeVoiceOverlay, 2000);
        };

        recognition.onend = () => {
            if (isVoiceActive) {
                document.getElementById('voice-status-text').textContent = 'Processing...';
            }
        };

        recognition.start();
        document.getElementById('voice-status-text').textContent = 'Listening...';
    } else {
        document.getElementById('voice-status-text').textContent = 'Speech recognition not supported in this browser';
    }
}

function closeVoiceOverlay() {
    const overlay = document.getElementById('voice-overlay');
    overlay.classList.remove('active');
    isVoiceActive = false;
    if (recognition) {
        recognition.stop();
        recognition = null;
    }
    document.getElementById('voice-transcript').textContent = '';
}

function toggleAssistantVoice() {
    toggleVoice();
}

// ── Keyboard Shortcuts ──────────────────────────────────────────
function setupShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+Space — toggle voice
        if (e.ctrlKey && e.code === 'Space') {
            e.preventDefault();
            toggleVoice();
        }
        // Ctrl+T — new terminal
        if (e.ctrlKey && e.key === 't' && !e.target.matches('input, textarea')) {
            e.preventDefault();
            openTerminal();
        }
        // Ctrl+E — file browser
        if (e.ctrlKey && e.key === 'e' && !e.target.matches('input, textarea')) {
            e.preventDefault();
            openFiles();
        }
        // Escape — close voice overlay
        if (e.key === 'Escape') {
            if (isVoiceActive) closeVoiceOverlay();
            const notifPanel = document.getElementById('notification-panel');
            if (notifPanel.classList.contains('open')) notifPanel.classList.remove('open');
        }
        // Ctrl+J — focus JARVIS assistant
        if (e.ctrlKey && e.key === 'j') {
            e.preventDefault();
            openAssistant();
            setTimeout(() => {
                const input = document.getElementById('assistant-input');
                if (input) input.focus();
            }, 100);
        }
    });
}

// ── Desktop Drag & Drop ─────────────────────────────────────────
function setupDesktopDrop() {
    const desktop = document.getElementById('desktop-area');

    desktop.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
    });

    desktop.addEventListener('drop', async (e) => {
        e.preventDefault();
        const files = Array.from(e.dataTransfer.files);
        const text = e.dataTransfer.getData('text');

        if (files.length > 0) {
            // Files dropped on desktop
            if (!wm.isOpen('assistant')) openAssistant();
            setTimeout(() => {
                const fileNames = files.map(f => f.name).join(', ');
                addChatMessage('system', `Files dropped: ${fileNames}`);
                addChatMessage('user', `I've dropped these files: ${fileNames}. Please analyze them.`);
                showTyping(true);

                // Upload files
                const formData = new FormData();
                files.forEach(f => formData.append('files', f));
                fetch('/api/upload', { method: 'POST', body: formData })
                    .then(r => r.json())
                    .then(data => {
                        if (window.jarvisWS && window.jarvisWS.readyState === WebSocket.OPEN) {
                            window.jarvisWS.send(JSON.stringify({
                                type: 'command',
                                command: `Analyze the uploaded files: ${data.files?.map(f => f.path).join(', ')}`,
                                source: 'upload',
                            }));
                        }
                    });
            }, 300);
        } else if (text) {
            // Link or text dropped
            if (!wm.isOpen('assistant')) openAssistant();
            setTimeout(() => {
                addChatMessage('user', `Process this: ${text}`);
                showTyping(true);
                if (window.jarvisWS && window.jarvisWS.readyState === WebSocket.OPEN) {
                    window.jarvisWS.send(JSON.stringify({
                        type: 'command',
                        command: `Process this link/text: ${text}`,
                        source: 'drop',
                    }));
                }
            }, 300);
        }
    });
}

// ── Quick Commands ──────────────────────────────────────────────
function sendQuickCommand(cmd) {
    if (!wm.isOpen('assistant')) openAssistant();
    setTimeout(() => {
        addChatMessage('user', cmd);
        showTyping(true);
        if (window.jarvisWS && window.jarvisWS.readyState === WebSocket.OPEN) {
            window.jarvisWS.send(JSON.stringify({
                type: 'command',
                command: cmd,
                source: 'quick',
            }));
        } else {
            fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: cmd, source: 'quick' }),
            })
            .then(r => r.json())
            .then(data => {
                showTyping(false);
                addChatMessage('jarvis', data.result || data.error || 'No response');
            });
        }
    }, 200);
}
