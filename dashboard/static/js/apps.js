/* ═══════════════════════════════════════════════════════════════
   JARVIS-OS Built-in Applications
   ═══════════════════════════════════════════════════════════════ */

/* ── JARVIS Assistant (main AI chat) ─────────────────────────── */
function openAssistant() {
    if (wm.isOpen('assistant')) { wm.focusWindow('assistant'); return; }
    wm.createWindow({
        id: 'assistant',
        title: 'JARVIS ASSISTANT',
        icon: '&#9883;',
        width: 900,
        height: 600,
        appType: 'assistant',
        content: `
            <div class="assistant-body">
                <div class="assistant-chat" id="assistant-chat">
                    <div class="message system">
                        <div class="message-header">
                            <span class="message-sender system">SYSTEM</span>
                        </div>
                        <div class="message-content">
                            JARVIS-OS online. All subsystems operational. How can I assist you?
                        </div>
                    </div>
                </div>
                <div class="typing-indicator" id="typing-indicator">
                    <div class="typing-dots"><span></span><span></span><span></span></div>
                    <span>JARVIS is thinking...</span>
                </div>
                <div class="assistant-input-area">
                    <div class="assistant-input-row">
                        <label class="assistant-upload-btn" title="Upload files">
                            <input type="file" id="assistant-file-input" multiple hidden onchange="handleFileUpload(this)">
                            &#128206;
                        </label>
                        <input type="text" class="assistant-input" id="assistant-input"
                               placeholder="Ask JARVIS anything..."
                               autocomplete="off" spellcheck="false">
                        <button class="sysbar-btn sysbar-icon-btn" id="assistant-mic" onclick="toggleAssistantVoice()" title="Voice input" style="font-size:18px;padding:8px">&#127908;</button>
                        <button class="assistant-send" id="assistant-send" onclick="sendAssistantMessage()">&#9654;</button>
                    </div>
                    <div id="assistant-attachments" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px"></div>
                </div>
            </div>
        `,
        onReady: () => {
            const input = document.getElementById('assistant-input');
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendAssistantMessage();
                }
            });
            input.focus();
        }
    });
}

function addChatMessage(role, content, extra = '') {
    const chat = document.getElementById('assistant-chat');
    if (!chat) return;

    const time = new Date().toLocaleTimeString();
    const senderMap = { user: 'YOU', jarvis: 'JARVIS', system: 'SYSTEM', agent: 'AGENT' };

    const msg = document.createElement('div');
    msg.className = `message ${role}`;
    msg.innerHTML = `
        <div class="message-header">
            <span class="message-sender ${role}">${senderMap[role] || role.toUpperCase()}</span>
            <span class="message-time">${time}</span>
        </div>
        <div class="message-content">${escapeHTML(content)}${extra}</div>
    `;
    chat.appendChild(msg);
    chat.scrollTop = chat.scrollHeight;
}

function showTyping(show) {
    const el = document.getElementById('typing-indicator');
    if (el) el.classList.toggle('active', show);
}

function sendAssistantMessage() {
    const input = document.getElementById('assistant-input');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    addChatMessage('user', text);
    input.value = '';
    showTyping(true);

    // Send to backend via WebSocket
    if (window.jarvisWS && window.jarvisWS.readyState === WebSocket.OPEN) {
        window.jarvisWS.send(JSON.stringify({
            type: 'command',
            command: text,
            source: 'assistant',
        }));
    } else {
        // Fallback to HTTP
        fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: text, source: 'assistant' }),
        })
        .then(r => r.json())
        .then(data => {
            showTyping(false);
            addChatMessage('jarvis', data.result || data.error || 'No response');
        })
        .catch(err => {
            showTyping(false);
            addChatMessage('system', `Error: ${err.message}`);
        });
    }
}

function handleFileUpload(input) {
    const files = Array.from(input.files);
    const container = document.getElementById('assistant-attachments');
    if (!container) return;

    files.forEach(file => {
        const tag = document.createElement('div');
        tag.style.cssText = 'padding:4px 10px;background:var(--bg-card);border:1px solid var(--border);border-radius:4px;font-family:var(--font-mono);font-size:11px;color:var(--text-secondary);display:flex;align-items:center;gap:6px';
        tag.innerHTML = `&#128196; ${file.name} <span style="cursor:pointer;color:var(--danger)" onclick="this.parentElement.remove()">&#10005;</span>`;
        container.appendChild(tag);
    });
}

/* ── Terminal ────────────────────────────────────────────────── */
function openTerminal() {
    const id = wm.isOpen('terminal') ? `terminal_${Date.now()}` : 'terminal';
    if (id === 'terminal' && wm.isOpen('terminal')) { wm.focusWindow('terminal'); return; }

    wm.createWindow({
        id,
        title: 'TERMINAL',
        icon: '&#9000;',
        width: 800,
        height: 500,
        appType: 'terminal',
        content: `
            <div class="terminal-body" id="${id}-terminal" onclick="document.getElementById('${id}-term-input').focus()">
                <div class="terminal-line"><span class="terminal-prompt">JARVIS-OS</span> <span style="color:var(--text-dim)">v1.0 — Type commands below</span></div>
                <div class="terminal-line">&nbsp;</div>
                <div id="${id}-term-output"></div>
                <div class="terminal-input-line">
                    <span class="terminal-prompt">$ </span>
                    <input type="text" class="terminal-input" id="${id}-term-input" autocomplete="off" spellcheck="false">
                </div>
            </div>
        `,
        onReady: () => {
            const input = document.getElementById(`${id}-term-input`);
            const output = document.getElementById(`${id}-term-output`);
            const history = [];
            let histIdx = -1;

            input.addEventListener('keydown', async (e) => {
                if (e.key === 'Enter') {
                    const cmd = input.value.trim();
                    if (!cmd) return;
                    history.unshift(cmd);
                    histIdx = -1;

                    // Show command
                    const cmdLine = document.createElement('div');
                    cmdLine.className = 'terminal-line';
                    cmdLine.innerHTML = `<span class="terminal-prompt">$ </span>${escapeHTML(cmd)}`;
                    output.appendChild(cmdLine);

                    input.value = '';

                    // Execute
                    try {
                        const res = await fetch('/api/execute', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ command: cmd }),
                        });
                        const data = await res.json();
                        const resultLine = document.createElement('div');
                        resultLine.className = 'terminal-line';
                        if (data.stderr) {
                            resultLine.innerHTML = `<span class="terminal-error">${escapeHTML(data.stderr)}</span>`;
                        }
                        if (data.stdout) {
                            resultLine.innerHTML += `<span class="terminal-output">${escapeHTML(data.stdout)}</span>`;
                        }
                        if (data.error) {
                            resultLine.innerHTML = `<span class="terminal-error">${escapeHTML(data.error)}</span>`;
                        }
                        output.appendChild(resultLine);
                    } catch (err) {
                        const errLine = document.createElement('div');
                        errLine.className = 'terminal-line';
                        errLine.innerHTML = `<span class="terminal-error">Error: ${escapeHTML(err.message)}</span>`;
                        output.appendChild(errLine);
                    }

                    // Scroll to bottom
                    const term = document.getElementById(`${id}-terminal`);
                    term.scrollTop = term.scrollHeight;
                } else if (e.key === 'ArrowUp') {
                    if (histIdx < history.length - 1) {
                        histIdx++;
                        input.value = history[histIdx];
                    }
                    e.preventDefault();
                } else if (e.key === 'ArrowDown') {
                    if (histIdx > 0) {
                        histIdx--;
                        input.value = history[histIdx];
                    } else {
                        histIdx = -1;
                        input.value = '';
                    }
                    e.preventDefault();
                }
            });

            input.focus();
        }
    });
}

/* ── File Browser ────────────────────────────────────────────── */
function openFiles(startPath) {
    if (wm.isOpen('files')) { wm.focusWindow('files'); return; }

    // Use home dir as default — works on Windows, Linux, Mac
    const defaultPath = startPath || '.';

    wm.createWindow({
        id: 'files',
        title: 'FILE BROWSER',
        icon: '&#128193;',
        width: 850,
        height: 550,
        appType: 'files',
        content: `
            <div class="file-browser">
                <div class="file-toolbar">
                    <button class="sysbar-btn" id="files-back" onclick="filesNavigate('..')">&#9664; Back</button>
                    <button class="sysbar-btn" onclick="filesNavigate('.')">&#127968; Home</button>
                    <input type="text" class="file-path-bar" id="files-path" value="${defaultPath}"
                           onkeydown="if(event.key==='Enter')filesNavigate(this.value)">
                    <button class="sysbar-btn" onclick="filesRefresh()">&#8635;</button>
                </div>
                <div class="file-list" id="files-list">
                    <div style="padding:20px;text-align:center;color:var(--text-dim);font-family:var(--font-mono)">Loading...</div>
                </div>
            </div>
        `,
        onReady: () => {
            filesNavigate(defaultPath);
        }
    });
}

async function filesNavigate(path) {
    const pathBar = document.getElementById('files-path');
    const list = document.getElementById('files-list');
    if (!list) return;

    try {
        const res = await fetch(`/api/files/list?path=${encodeURIComponent(path)}`);
        const data = await res.json();

        if (data.error) {
            list.innerHTML = `<div style="padding:20px;color:var(--danger);font-family:var(--font-mono)">${escapeHTML(data.error)}</div>`;
            return;
        }

        if (pathBar && data.current_path) pathBar.value = data.current_path;

        list.innerHTML = '';
        if (data.items) {
            data.items.forEach(item => {
                const el = document.createElement('div');
                el.className = 'file-item';
                const icon = item.is_dir ? '&#128193;' : getFileIcon(item.extension);
                const size = item.is_dir ? '--' : formatSize(item.size);
                const modified = item.modified ? new Date(item.modified).toLocaleDateString() : '';
                el.innerHTML = `
                    <span class="file-item-icon">${icon}</span>
                    <span class="file-item-name">${escapeHTML(item.name)}</span>
                    <span class="file-item-size">${size}</span>
                    <span class="file-item-date">${modified}</span>
                `;
                if (item.is_dir) {
                    el.ondblclick = () => filesNavigate(item.path);
                }
                list.appendChild(el);
            });
        }
    } catch (err) {
        list.innerHTML = `<div style="padding:20px;color:var(--danger);font-family:var(--font-mono)">Error: ${escapeHTML(err.message)}</div>`;
    }
}

function filesRefresh() {
    const pathBar = document.getElementById('files-path');
    if (pathBar) filesNavigate(pathBar.value);
}

/* ── System Monitor ──────────────────────────────────────────── */
function openMonitor() {
    if (wm.isOpen('monitor')) { wm.focusWindow('monitor'); return; }

    wm.createWindow({
        id: 'monitor',
        title: 'SYSTEM MONITOR',
        icon: '&#128200;',
        width: 900,
        height: 600,
        appType: 'monitor',
        content: `
            <div class="monitor-grid" id="monitor-grid">
                <div class="monitor-card">
                    <div class="monitor-card-title">CPU Usage</div>
                    <div class="monitor-big-value" id="mon-cpu">0%</div>
                    <div class="monitor-sub" id="mon-cpu-info">Loading...</div>
                    <div class="monitor-bar-large"><div class="monitor-bar-fill" id="mon-cpu-bar" style="width:0%"></div></div>
                </div>
                <div class="monitor-card">
                    <div class="monitor-card-title">Memory</div>
                    <div class="monitor-big-value" id="mon-mem">0%</div>
                    <div class="monitor-sub" id="mon-mem-info">Loading...</div>
                    <div class="monitor-bar-large"><div class="monitor-bar-fill" id="mon-mem-bar" style="width:0%"></div></div>
                </div>
                <div class="monitor-card">
                    <div class="monitor-card-title">Disk</div>
                    <div class="monitor-big-value" id="mon-disk">0%</div>
                    <div class="monitor-sub" id="mon-disk-info">Loading...</div>
                    <div class="monitor-bar-large"><div class="monitor-bar-fill" id="mon-disk-bar" style="width:0%"></div></div>
                </div>
                <div class="monitor-card">
                    <div class="monitor-card-title">Network</div>
                    <div class="monitor-big-value" id="mon-net">0 KB/s</div>
                    <div class="monitor-sub" id="mon-net-info">Loading...</div>
                </div>
                <div class="monitor-card" style="grid-column: 1 / -1">
                    <div class="monitor-card-title">Top Processes</div>
                    <table class="process-table" id="mon-processes">
                        <thead><tr><th>PID</th><th>Name</th><th>CPU %</th><th>MEM %</th><th>Status</th></tr></thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        `,
        onReady: () => {
            refreshMonitor();
            window._monitorInterval = setInterval(refreshMonitor, 3000);
        },
        onClose: () => {
            if (window._monitorInterval) clearInterval(window._monitorInterval);
        }
    });
}

async function refreshMonitor() {
    try {
        const res = await fetch('/api/system/stats');
        const stats = await res.json();

        setText('mon-cpu', stats.cpu?.usage_percent + '%');
        setText('mon-cpu-info', `${stats.cpu?.cores_logical} cores @ ${Math.round(stats.cpu?.freq_mhz || 0)} MHz`);
        setBar('mon-cpu-bar', stats.cpu?.usage_percent);

        setText('mon-mem', stats.memory?.percent + '%');
        setText('mon-mem-info', `${stats.memory?.used_gb} / ${stats.memory?.total_gb} GB`);
        setBar('mon-mem-bar', stats.memory?.percent);

        setText('mon-disk', stats.disk?.percent + '%');
        setText('mon-disk-info', `${stats.disk?.used_gb} / ${stats.disk?.total_gb} GB`);
        setBar('mon-disk-bar', stats.disk?.percent);

        setText('mon-net', formatSize(stats.network?.bytes_recv || 0));
        setText('mon-net-info', `Sent: ${formatSize(stats.network?.bytes_sent || 0)}`);

        // Processes
        const procRes = await fetch('/api/system/processes?limit=10');
        const procs = await procRes.json();
        const tbody = document.querySelector('#mon-processes tbody');
        if (tbody && procs.length) {
            tbody.innerHTML = procs.map(p => `
                <tr>
                    <td>${p.pid}</td>
                    <td>${escapeHTML(p.name || '')}</td>
                    <td>${(p.cpu_percent || 0).toFixed(1)}</td>
                    <td>${(p.memory_percent || 0).toFixed(1)}</td>
                    <td>${p.status || ''}</td>
                </tr>
            `).join('');
        }
    } catch (err) {
        console.error('Monitor refresh error:', err);
    }
}

/* ── Agent Hub ───────────────────────────────────────────────── */
function openAgentHub() {
    if (wm.isOpen('agents')) { wm.focusWindow('agents'); return; }

    wm.createWindow({
        id: 'agents',
        title: 'AGENT HUB',
        icon: '&#129302;',
        width: 800,
        height: 500,
        appType: 'agents',
        content: `
            <div class="agent-hub">
                <div class="agent-hub-header">
                    <div>
                        <span style="font-family:var(--font-display);font-size:14px;letter-spacing:2px;color:var(--primary)">AGENTS</span>
                        <span style="font-family:var(--font-mono);font-size:11px;color:var(--text-dim);margin-left:12px" id="agent-count">0 active</span>
                    </div>
                    <button class="btn-spawn" onclick="spawnAgentDialog()">+ SPAWN AGENT</button>
                </div>
                <div id="agent-hub-list">
                    <div style="text-align:center;padding:40px;color:var(--text-dim);font-family:var(--font-mono)">No agents running</div>
                </div>
            </div>
        `,
        onReady: () => {
            refreshAgents();
            window._agentInterval = setInterval(refreshAgents, 2000);
        },
        onClose: () => {
            if (window._agentInterval) clearInterval(window._agentInterval);
        }
    });
}

async function refreshAgents() {
    try {
        const res = await fetch('/api/agents');
        const agents = await res.json();
        const list = document.getElementById('agent-hub-list');
        const count = document.getElementById('agent-count');
        if (!list) return;

        const active = agents.filter(a => a.status === 'running').length;
        if (count) count.textContent = `${active} active / ${agents.length} total`;

        if (agents.length === 0) {
            list.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-dim);font-family:var(--font-mono)">No agents</div>';
            return;
        }

        list.innerHTML = agents.map(a => `
            <div class="agent-card">
                <div class="agent-avatar" style="border-color:${a.status === 'running' ? 'var(--success)' : a.status === 'failed' ? 'var(--danger)' : 'var(--primary)'}">
                    &#129302;
                </div>
                <div class="agent-info">
                    <div class="agent-card-name">${escapeHTML(a.name)}</div>
                    <div class="agent-card-task">${escapeHTML(a.task || 'No task')}</div>
                </div>
                <span class="agent-card-status ${a.status}">${a.status}</span>
            </div>
        `).join('');
    } catch (err) {
        console.error('Agent refresh error:', err);
    }
}

function spawnAgentDialog() {
    const task = prompt('Enter task for the new agent:');
    if (!task) return;
    fetch('/api/agents/spawn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, type: 'general' }),
    }).then(() => refreshAgents());
}

/* ── Memory Viewer ───────────────────────────────────────────── */
function openMemory() {
    if (wm.isOpen('memory')) { wm.focusWindow('memory'); return; }

    wm.createWindow({
        id: 'memory',
        title: 'MEMORY BANK',
        icon: '&#129504;',
        width: 700,
        height: 500,
        content: `
            <div style="padding:16px;height:100%;overflow-y:auto">
                <div style="margin-bottom:16px;display:flex;gap:8px">
                    <button class="quick-btn" onclick="loadMemory('conversations')">Conversations</button>
                    <button class="quick-btn" onclick="loadMemory('facts')">Facts</button>
                    <button class="quick-btn" onclick="loadMemory('tasks')">Tasks</button>
                </div>
                <div id="memory-content" style="font-family:var(--font-mono);font-size:12px;color:var(--text-secondary)">
                    Select a memory category above
                </div>
            </div>
        `,
        onReady: () => { loadMemory('conversations'); }
    });
}

async function loadMemory(category) {
    const container = document.getElementById('memory-content');
    if (!container) return;
    try {
        const res = await fetch(`/api/memory/${category}`);
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
            container.innerHTML = data.slice(-50).reverse().map(item => `
                <div style="padding:10px;border:1px solid var(--border);border-radius:6px;margin-bottom:8px;background:var(--bg-card)">
                    <div style="color:var(--text-primary);margin-bottom:4px">${escapeHTML(item.content || item.fact || item.task || JSON.stringify(item))}</div>
                    <div style="font-size:10px;color:var(--text-dim)">${item.timestamp || ''}</div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-dim)">No entries</div>';
        }
    } catch (err) {
        container.innerHTML = `<div style="color:var(--danger)">${err.message}</div>`;
    }
}

/* ── Plugins ─────────────────────────────────────────────────── */
function openPlugins() {
    if (wm.isOpen('plugins')) { wm.focusWindow('plugins'); return; }

    wm.createWindow({
        id: 'plugins',
        title: 'PLUGINS',
        icon: '&#128268;',
        width: 700,
        height: 500,
        content: `
            <div style="padding:16px;height:100%;overflow-y:auto">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                    <span style="font-family:var(--font-display);font-size:14px;letter-spacing:2px;color:var(--primary)">INSTALLED PLUGINS</span>
                    <button class="btn-spawn" onclick="installPluginDialog()" style="margin-right:8px">Install from Git</button>
                    <button class="btn-spawn" onclick="discoverPlugins()">Scan for Plugins</button>
                </div>
                <div id="plugins-list">
                    <div style="text-align:center;padding:40px;color:var(--text-dim);font-family:var(--font-mono)">Loading...</div>
                </div>
            </div>
        `,
        onReady: () => { loadPlugins(); }
    });
}

async function loadPlugins() {
    try {
        const res = await fetch('/api/plugins');
        const plugins = await res.json();
        const list = document.getElementById('plugins-list');
        if (!list) return;
        if (plugins.length === 0) {
            list.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-dim);font-family:var(--font-mono)">No plugins installed.</div>';
            return;
        }
        list.innerHTML = plugins.map(p => `
            <div class="agent-card">
                <div class="agent-avatar">&#128268;</div>
                <div class="agent-info">
                    <div class="agent-card-name">${escapeHTML(p.name)} <span style="font-size:10px;color:var(--text-dim)">v${p.version || '?'}</span></div>
                    <div class="agent-card-task">${escapeHTML(p.description || '')}</div>
                    ${p.tools && p.tools.length ? `<div style="margin-top:4px;font-size:10px;color:var(--primary)">${p.tools.join(', ')}</div>` : ''}
                </div>
                <span class="agent-card-status ${p.enabled ? 'running' : 'completed'}">${p.enabled ? 'ACTIVE' : 'DISABLED'}</span>
            </div>
        `).join('');
    } catch (err) {
        const list = document.getElementById('plugins-list');
        if (list) list.innerHTML = `<div style="color:var(--danger)">${err.message}</div>`;
    }
}

async function discoverPlugins() {
    try {
        await fetch('/api/plugins/discover', { method: 'POST' });
        loadPlugins();
        addNotification('Plugins rescanned', 'success');
    } catch (err) { console.error(err); }
}

function installPluginDialog() {
    const url = prompt('Git URL for plugin repository:');
    if (!url) return;
    fetch('/api/plugins/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
    }).then(r => r.json()).then(data => {
        if (data.status === 'success') {
            addNotification(`Installed: ${data.installed.join(', ')}`, 'success');
            loadPlugins();
        } else {
            addNotification(`Install failed: ${data.message}`, 'error');
        }
    });
}

/* ── Settings ────────────────────────────────────────────────── */
function openSettings() {
    if (wm.isOpen('settings')) { wm.focusWindow('settings'); return; }

    wm.createWindow({
        id: 'settings',
        title: 'SETTINGS',
        icon: '&#9881;',
        width: 650,
        height: 600,
        content: `
            <div style="padding:20px;height:100%;overflow-y:auto">
                <div class="sidebar-section" style="margin-bottom:16px">
                    <div class="section-title">API Keys</div>

                    <div style="margin-bottom:14px">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                            <label style="font-family:var(--font-mono);font-size:11px;color:var(--text-dim)">OpenAI API Key</label>
                            <span id="set-openai-status" style="font-family:var(--font-mono);font-size:10px;padding:2px 8px;border-radius:4px;background:var(--bg-card)">--</span>
                        </div>
                        <div style="display:flex;gap:8px">
                            <input type="password" id="set-openai-key" placeholder="sk-..." style="flex:1;padding:8px;background:var(--bg-card);border:1px solid var(--border);color:var(--text-primary);border-radius:6px;font-family:var(--font-mono);font-size:12px">
                            <button class="quick-btn" onclick="saveSettingsKey('openai')" style="white-space:nowrap;padding:8px 14px">Save</button>
                        </div>
                        <div id="set-openai-msg" style="font-family:var(--font-mono);font-size:10px;margin-top:4px;min-height:14px"></div>
                    </div>

                    <div style="margin-bottom:6px">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                            <label style="font-family:var(--font-mono);font-size:11px;color:var(--text-dim)">Anthropic API Key</label>
                            <span id="set-anthropic-status" style="font-family:var(--font-mono);font-size:10px;padding:2px 8px;border-radius:4px;background:var(--bg-card)">--</span>
                        </div>
                        <div style="display:flex;gap:8px">
                            <input type="password" id="set-anthropic-key" placeholder="sk-ant-..." style="flex:1;padding:8px;background:var(--bg-card);border:1px solid var(--border);color:var(--text-primary);border-radius:6px;font-family:var(--font-mono);font-size:12px">
                            <button class="quick-btn" onclick="saveSettingsKey('anthropic')" style="white-space:nowrap;padding:8px 14px">Save</button>
                        </div>
                        <div id="set-anthropic-msg" style="font-family:var(--font-mono);font-size:10px;margin-top:4px;min-height:14px"></div>
                    </div>
                </div>

                <div class="sidebar-section" style="margin-bottom:16px">
                    <div class="section-title">LLM Provider</div>
                    <select id="set-provider" style="width:100%;padding:8px;background:var(--bg-card);border:1px solid var(--border);color:var(--text-primary);border-radius:6px;font-family:var(--font-mono)">
                        <option value="openai">OpenAI (GPT-4o)</option>
                        <option value="anthropic">Anthropic (Claude)</option>
                    </select>
                </div>
                <div class="sidebar-section" style="margin-bottom:16px">
                    <div class="section-title">Voice Settings</div>
                    <div style="margin-bottom:10px">
                        <label style="font-family:var(--font-mono);font-size:11px;color:var(--text-dim)">Wake Word</label>
                        <input type="text" value="jarvis" style="width:100%;padding:8px;background:var(--bg-card);border:1px solid var(--border);color:var(--text-primary);border-radius:6px;font-family:var(--font-mono);margin-top:4px">
                    </div>
                    <div>
                        <label style="font-family:var(--font-mono);font-size:11px;color:var(--text-dim)">Speech Rate</label>
                        <input type="range" min="100" max="300" value="180" style="width:100%;margin-top:4px">
                    </div>
                </div>
                <div class="sidebar-section" style="margin-bottom:16px">
                    <div class="section-title">Agent Configuration</div>
                    <div>
                        <label style="font-family:var(--font-mono);font-size:11px;color:var(--text-dim)">Max Concurrent Agents</label>
                        <input type="number" value="10" min="1" max="50" style="width:100%;padding:8px;background:var(--bg-card);border:1px solid var(--border);color:var(--text-primary);border-radius:6px;font-family:var(--font-mono);margin-top:4px">
                    </div>
                </div>
                <div class="sidebar-section">
                    <div class="section-title">System</div>
                    <button class="quick-btn" style="width:100%;margin-bottom:8px" onclick="if(confirm('Restart JARVIS-OS?')) fetch('/api/system/restart',{method:'POST'})">Restart JARVIS-OS</button>
                    <button class="quick-btn" style="width:100%;color:var(--danger);border-color:rgba(255,59,48,0.3)" onclick="if(confirm('Shutdown JARVIS-OS?')) fetch('/api/system/shutdown',{method:'POST'})">Shutdown</button>
                </div>
            </div>
        `,
        onReady: () => { loadSettingsKeys(); }
    });
}

async function loadSettingsKeys() {
    try {
        const res = await fetch('/api/setup/keys');
        const data = await res.json();

        const oaiStatus = document.getElementById('set-openai-status');
        const antStatus = document.getElementById('set-anthropic-status');

        if (oaiStatus) {
            if (data.openai?.active) {
                oaiStatus.textContent = 'Active (' + data.openai.masked + ')';
                oaiStatus.style.color = 'var(--success)';
                oaiStatus.style.borderColor = 'var(--success)';
            } else {
                oaiStatus.textContent = 'Not configured';
                oaiStatus.style.color = 'var(--text-dim)';
            }
        }
        if (antStatus) {
            if (data.anthropic?.active) {
                antStatus.textContent = 'Active (' + data.anthropic.masked + ')';
                antStatus.style.color = 'var(--success)';
                antStatus.style.borderColor = 'var(--success)';
            } else {
                antStatus.textContent = 'Not configured';
                antStatus.style.color = 'var(--text-dim)';
            }
        }
    } catch (e) {
        console.error('Failed to load key status:', e);
    }
}

async function saveSettingsKey(provider) {
    const input = document.getElementById(`set-${provider}-key`);
    const msgEl = document.getElementById(`set-${provider}-msg`);
    if (!input || !msgEl) return;

    const apiKey = input.value.trim();
    if (!apiKey) {
        msgEl.textContent = 'Please enter an API key';
        msgEl.style.color = 'var(--danger)';
        return;
    }

    msgEl.textContent = 'Saving...';
    msgEl.style.color = 'var(--text-dim)';

    try {
        const res = await fetch('/api/setup/apikey', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, api_key: apiKey }),
        });
        const data = await res.json();

        if (data.status === 'success') {
            msgEl.textContent = data.message;
            msgEl.style.color = 'var(--success)';
            input.value = '';
            addNotification(`${provider.charAt(0).toUpperCase() + provider.slice(1)} API key saved`, 'success');
            loadSettingsKeys();
        } else {
            msgEl.textContent = data.message || 'Failed to save key';
            msgEl.style.color = 'var(--danger)';
        }
    } catch (e) {
        msgEl.textContent = 'Connection error: ' + e.message;
        msgEl.style.color = 'var(--danger)';
    }
}

/* ── Browser ─────────────────────────────────────────────────── */
function openBrowser() {
    if (wm.isOpen('browser')) { wm.focusWindow('browser'); return; }

    wm.createWindow({
        id: 'browser',
        title: 'BROWSER',
        icon: '&#127760;',
        width: 1000,
        height: 600,
        content: `
            <div style="display:flex;flex-direction:column;height:100%">
                <div class="file-toolbar">
                    <button class="sysbar-btn" onclick="browserNavigate(-1)">&#9664;</button>
                    <button class="sysbar-btn" onclick="browserNavigate(1)">&#9654;</button>
                    <input type="text" class="file-path-bar" id="browser-url" value="https://www.google.com"
                           placeholder="Enter URL..." onkeydown="if(event.key==='Enter')browserGo()">
                    <button class="sysbar-btn" onclick="browserGo()">Go</button>
                </div>
                <iframe id="browser-frame" style="flex:1;border:none;background:#fff" sandbox="allow-same-origin allow-scripts allow-forms"></iframe>
            </div>
        `,
        onReady: () => { browserGo(); }
    });
}

function browserGo() {
    const url = document.getElementById('browser-url')?.value;
    const frame = document.getElementById('browser-frame');
    if (url && frame) frame.src = url;
}

/* ── Goals ───────────────────────────────────────────────────── */
function openGoals() {
    if (wm.isOpen('goals')) { wm.focusWindow('goals'); return; }
    wm.createWindow({
        id: 'goals',
        title: 'GOALS',
        icon: '&#127919;',
        width: 750,
        height: 550,
        content: `
            <div style="padding:16px;height:100%;overflow-y:auto">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                    <span style="font-family:var(--font-display);font-size:14px;letter-spacing:2px;color:var(--primary)">ACTIVE GOALS</span>
                    <div style="display:flex;gap:8px">
                        <button class="btn-spawn" onclick="getBriefing()">Briefing</button>
                        <button class="btn-spawn" onclick="createGoalDialog()">+ New Goal</button>
                    </div>
                </div>
                <div id="goals-briefing" style="display:none;padding:12px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card);margin-bottom:16px;font-family:var(--font-mono);font-size:12px;color:var(--text-secondary);white-space:pre-wrap"></div>
                <div id="goals-list">
                    <div style="text-align:center;padding:40px;color:var(--text-dim);font-family:var(--font-mono)">Loading...</div>
                </div>
            </div>
        `,
        onReady: () => { loadGoals(); }
    });
}

async function loadGoals() {
    try {
        const res = await fetch('/api/goals');
        const goals = await res.json();
        const list = document.getElementById('goals-list');
        if (!list) return;
        if (!goals.length) {
            list.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-dim);font-family:var(--font-mono)">No goals yet. Create one to get started!</div>';
            return;
        }
        list.innerHTML = goals.map(g => `
            <div class="agent-card" style="flex-direction:column;align-items:stretch">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div class="agent-card-name">${escapeHTML(g.title)}</div>
                    <span class="agent-card-status ${g.status === 'active' ? 'running' : 'completed'}">${g.status} — ${g.progress}%</span>
                </div>
                ${g.description ? `<div style="font-family:var(--font-mono);font-size:11px;color:var(--text-secondary);margin-top:4px">${escapeHTML(g.description)}</div>` : ''}
                <div style="margin-top:8px;height:4px;background:rgba(0,212,255,0.1);border-radius:2px;overflow:hidden">
                    <div style="height:100%;width:${g.progress}%;background:linear-gradient(90deg,var(--primary),var(--accent));border-radius:2px;transition:width 0.3s"></div>
                </div>
                ${g.milestones && g.milestones.length ? `<div style="margin-top:8px;font-family:var(--font-mono);font-size:11px">${g.milestones.map(m =>
                    `<div style="padding:3px 0;color:${m.completed ? 'var(--success)' : 'var(--text-dim)'}">${m.completed ? '&#10003;' : '&#9675;'} ${escapeHTML(m.title)}</div>`
                ).join('')}</div>` : ''}
            </div>
        `).join('');
    } catch (err) {
        const list = document.getElementById('goals-list');
        if (list) list.innerHTML = `<div style="color:var(--danger)">${err.message}</div>`;
    }
}

async function getBriefing() {
    try {
        const res = await fetch('/api/goals/briefing');
        const data = await res.json();
        const el = document.getElementById('goals-briefing');
        if (el) { el.textContent = data.briefing; el.style.display = 'block'; }
    } catch (err) { console.error(err); }
}

function createGoalDialog() {
    const title = prompt('Goal title:');
    if (!title) return;
    const desc = prompt('Description (optional):') || '';
    const msInput = prompt('Milestones (comma-separated, optional):') || '';
    const milestones = msInput ? msInput.split(',').map(s => s.trim()).filter(Boolean) : [];
    fetch('/api/goals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description: desc, milestones }),
    }).then(() => loadGoals());
}

/* ── Reminders ──────────────────────────────────────────────── */
function openReminders() {
    if (wm.isOpen('reminders')) { wm.focusWindow('reminders'); return; }
    wm.createWindow({
        id: 'reminders',
        title: 'REMINDERS',
        icon: '&#9200;',
        width: 650,
        height: 500,
        content: `
            <div style="padding:16px;height:100%;overflow-y:auto">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                    <span style="font-family:var(--font-display);font-size:14px;letter-spacing:2px;color:var(--primary)">REMINDERS</span>
                    <button class="btn-spawn" onclick="createReminderDialog()">+ Set Reminder</button>
                </div>
                <div id="reminders-list">
                    <div style="text-align:center;padding:40px;color:var(--text-dim);font-family:var(--font-mono)">Loading...</div>
                </div>
            </div>
        `,
        onReady: () => { loadReminders(); }
    });
}

async function loadReminders() {
    try {
        // Use the command API to list reminders
        const res = await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: 'list my reminders', source: 'reminders_app' }),
        });
        // Also try direct plugin execution if API exists
        const listEl = document.getElementById('reminders-list');
        if (listEl) {
            listEl.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-dim);font-family:var(--font-mono)">Ask JARVIS to set reminders. They\'ll appear here and trigger as notifications.</div>';
        }
    } catch (err) {
        console.error(err);
    }
}

function createReminderDialog() {
    const msg = prompt('What to remind about?');
    if (!msg) return;
    const time = prompt('When? (e.g., "in 30 minutes", "3pm", "tomorrow")');
    if (!time) return;
    if (window.jarvisWS && window.jarvisWS.readyState === WebSocket.OPEN) {
        window.jarvisWS.send(JSON.stringify({
            type: 'command', command: `remind me to ${msg} ${time}`, source: 'assistant',
        }));
        addNotification(`Reminder set: ${msg}`, 'success');
    }
}

/* ── Contacts ───────────────────────────────────────────────── */
function openContacts() {
    if (wm.isOpen('contacts')) { wm.focusWindow('contacts'); return; }
    wm.createWindow({
        id: 'contacts',
        title: 'CONTACTS',
        icon: '&#128101;',
        width: 700,
        height: 500,
        content: `
            <div style="padding:16px;height:100%;overflow-y:auto">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                    <span style="font-family:var(--font-display);font-size:14px;letter-spacing:2px;color:var(--primary)">CONTACTS</span>
                    <button class="btn-spawn" onclick="addContactDialog()">+ Add Contact</button>
                </div>
                <div style="margin-bottom:12px">
                    <input type="text" id="contact-search" placeholder="Search contacts..."
                        style="width:100%;padding:8px 12px;background:var(--bg-card);border:1px solid var(--border);border-radius:6px;color:var(--text-primary);font-family:var(--font-mono);font-size:12px;outline:none"
                        oninput="searchContacts(this.value)">
                </div>
                <div id="contacts-list">
                    <div style="text-align:center;padding:40px;color:var(--text-dim);font-family:var(--font-mono)">No contacts yet</div>
                </div>
            </div>
        `,
        onReady: () => { searchContacts(''); }
    });
}

async function searchContacts(query) {
    try {
        const url = query ? `/api/command` : `/api/command`;
        // Use command API for search
        const listEl = document.getElementById('contacts-list');
        if (!listEl) return;
        // Direct approach — talk to JARVIS to manage contacts
        listEl.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-dim);font-family:var(--font-mono)">Ask JARVIS to add or search contacts. Example: "Add John as a colleague"</div>';
    } catch (err) { console.error(err); }
}

function addContactDialog() {
    const name = prompt('Contact name:');
    if (!name) return;
    const rel = prompt('Relationship (friend, colleague, family):') || '';
    const notes = prompt('Notes (optional):') || '';
    if (window.jarvisWS && window.jarvisWS.readyState === WebSocket.OPEN) {
        window.jarvisWS.send(JSON.stringify({
            type: 'command',
            command: `add contact ${name}${rel ? ', ' + rel : ''}${notes ? '. Notes: ' + notes : ''}`,
            source: 'assistant',
        }));
        addNotification(`Contact added: ${name}`, 'success');
    }
}

/* ── App Launcher ────────────────────────────────────────────── */
function openApp(appName) {
    switch (appName) {
        case 'assistant': openAssistant(); break;
        case 'terminal': openTerminal(); break;
        case 'files': openFiles(); break;
        case 'monitor': openMonitor(); break;
        case 'agents': openAgentHub(); break;
        case 'memory': openMemory(); break;
        case 'goals': openGoals(); break;
        case 'reminders': openReminders(); break;
        case 'contacts': openContacts(); break;
        case 'plugins': openPlugins(); break;
        case 'settings': openSettings(); break;
        case 'browser': openBrowser(); break;
        default:
            addNotification(`Unknown app: ${appName}`, 'warning');
    }
}

/* ── Helpers ──────────────────────────────────────────────────── */
function escapeHTML(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function setBar(id, percent) {
    const el = document.getElementById(id);
    if (el) el.style.width = `${Math.min(100, percent || 0)}%`;
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

function getFileIcon(ext) {
    const icons = {
        '.py': '&#128013;', '.js': '&#9997;', '.html': '&#127760;', '.css': '&#127912;',
        '.json': '&#128196;', '.md': '&#128214;', '.txt': '&#128196;', '.pdf': '&#128213;',
        '.png': '&#127912;', '.jpg': '&#127912;', '.gif': '&#127912;', '.svg': '&#127912;',
        '.zip': '&#128230;', '.tar': '&#128230;', '.gz': '&#128230;',
        '.sh': '&#9000;', '.bash': '&#9000;',
        '.mp3': '&#127925;', '.wav': '&#127925;', '.mp4': '&#127916;',
    };
    return icons[ext] || '&#128196;';
}
