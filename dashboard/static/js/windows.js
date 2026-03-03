/* ═══════════════════════════════════════════════════════════════
   JARVIS-OS Window Manager — Handles OS window lifecycle
   ═══════════════════════════════════════════════════════════════ */

class WindowManager {
    constructor() {
        this.windows = new Map();
        this.container = null;
        this.zIndexCounter = 100;
        this.activeWindowId = null;
    }

    init() {
        this.container = document.getElementById('windows-container');
    }

    createWindow(opts) {
        const id = opts.id || `win_${Date.now()}`;
        if (this.windows.has(id)) {
            this.focusWindow(id);
            return this.windows.get(id);
        }

        const defaults = {
            title: 'Window',
            icon: '&#9744;',
            width: 800,
            height: 500,
            x: 100 + (this.windows.size * 30),
            y: 50 + (this.windows.size * 30),
            resizable: true,
            content: '',
            onClose: null,
            onReady: null,
        };

        const config = { ...defaults, ...opts, id };

        // Center if not specified
        const area = document.getElementById('desktop-area');
        if (!opts.x) config.x = Math.max(50, (area.offsetWidth - config.width) / 2);
        if (!opts.y) config.y = Math.max(20, (area.offsetHeight - config.height) / 3);

        // Create DOM
        const win = document.createElement('div');
        win.className = 'os-window focused';
        win.id = id;
        win.style.cssText = `
            left: ${config.x}px;
            top: ${config.y}px;
            width: ${config.width}px;
            height: ${config.height}px;
            z-index: ${++this.zIndexCounter};
        `;

        win.innerHTML = `
            <div class="window-titlebar" data-win-id="${id}">
                <div class="window-title-left">
                    <span class="window-icon">${config.icon}</span>
                    <span class="window-title">${config.title}</span>
                </div>
                <div class="window-controls">
                    <button class="win-btn minimize" data-action="minimize" title="Minimize"></button>
                    <button class="win-btn maximize" data-action="maximize" title="Maximize"></button>
                    <button class="win-btn close" data-action="close" title="Close"></button>
                </div>
            </div>
            <div class="window-body" id="${id}-body">${config.content}</div>
            ${config.resizable ? '<div class="window-resize"></div>' : ''}
        `;

        this.container.appendChild(win);

        // Store
        const winData = {
            id,
            element: win,
            config,
            minimized: false,
            maximized: false,
            prevBounds: null,
        };
        this.windows.set(id, winData);

        // Setup interactions
        this._setupDrag(win, id);
        if (config.resizable) this._setupResize(win, id);
        this._setupControls(win, id, config);
        this._setupFocus(win, id);

        // Mark dock item
        const dockItem = document.getElementById(`dock-${config.appType || ''}`);
        if (dockItem) dockItem.classList.add('has-window');

        // Focus
        this.focusWindow(id);

        // Callback
        if (config.onReady) config.onReady(win, id);

        return winData;
    }

    _setupDrag(win, id) {
        const titlebar = win.querySelector('.window-titlebar');
        let isDragging = false;
        let startX, startY, origX, origY;

        titlebar.addEventListener('mousedown', (e) => {
            if (e.target.closest('.window-controls')) return;
            const winData = this.windows.get(id);
            if (winData.maximized) return;

            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            origX = win.offsetLeft;
            origY = win.offsetTop;
            win.style.transition = 'none';
            this.focusWindow(id);
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            win.style.left = `${origX + dx}px`;
            win.style.top = `${Math.max(0, origY + dy)}px`;
        });

        document.addEventListener('mouseup', () => {
            isDragging = false;
            win.style.transition = '';
        });
    }

    _setupResize(win, id) {
        const handle = win.querySelector('.window-resize');
        let isResizing = false;
        let startX, startY, startW, startH;

        handle.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;
            startY = e.clientY;
            startW = win.offsetWidth;
            startH = win.offsetHeight;
            win.style.transition = 'none';
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            win.style.width = `${Math.max(400, startW + dx)}px`;
            win.style.height = `${Math.max(300, startH + dy)}px`;
        });

        document.addEventListener('mouseup', () => {
            isResizing = false;
            win.style.transition = '';
        });
    }

    _setupControls(win, id, config) {
        win.querySelector('[data-action="close"]').addEventListener('click', () => {
            this.closeWindow(id);
            if (config.onClose) config.onClose();
        });

        win.querySelector('[data-action="minimize"]').addEventListener('click', () => {
            this.minimizeWindow(id);
        });

        win.querySelector('[data-action="maximize"]').addEventListener('click', () => {
            this.toggleMaximize(id);
        });

        // Double-click titlebar to maximize
        win.querySelector('.window-titlebar').addEventListener('dblclick', (e) => {
            if (e.target.closest('.window-controls')) return;
            this.toggleMaximize(id);
        });
    }

    _setupFocus(win, id) {
        win.addEventListener('mousedown', () => {
            this.focusWindow(id);
        });
    }

    focusWindow(id) {
        if (this.activeWindowId) {
            const prev = this.windows.get(this.activeWindowId);
            if (prev) prev.element.classList.remove('focused');
        }
        const winData = this.windows.get(id);
        if (!winData) return;
        winData.element.style.zIndex = ++this.zIndexCounter;
        winData.element.classList.add('focused');
        winData.element.classList.remove('minimized');
        winData.minimized = false;
        this.activeWindowId = id;
    }

    minimizeWindow(id) {
        const winData = this.windows.get(id);
        if (!winData) return;
        winData.element.classList.add('minimized');
        winData.minimized = true;
        if (this.activeWindowId === id) this.activeWindowId = null;
    }

    toggleMaximize(id) {
        const winData = this.windows.get(id);
        if (!winData) return;
        if (winData.maximized) {
            // Restore
            winData.element.classList.remove('maximized');
            if (winData.prevBounds) {
                winData.element.style.left = winData.prevBounds.left;
                winData.element.style.top = winData.prevBounds.top;
                winData.element.style.width = winData.prevBounds.width;
                winData.element.style.height = winData.prevBounds.height;
            }
            winData.maximized = false;
        } else {
            // Maximize
            winData.prevBounds = {
                left: winData.element.style.left,
                top: winData.element.style.top,
                width: winData.element.style.width,
                height: winData.element.style.height,
            };
            winData.element.classList.add('maximized');
            winData.maximized = true;
        }
    }

    closeWindow(id) {
        const winData = this.windows.get(id);
        if (!winData) return;
        winData.element.style.transition = 'all 0.2s ease';
        winData.element.style.opacity = '0';
        winData.element.style.transform = 'scale(0.9)';
        setTimeout(() => {
            winData.element.remove();
            this.windows.delete(id);
            if (this.activeWindowId === id) this.activeWindowId = null;
            // Unmark dock
            const dockItem = document.getElementById(`dock-${winData.config.appType || ''}`);
            if (dockItem) dockItem.classList.remove('has-window');
        }, 200);
    }

    getWindowBody(id) {
        return document.getElementById(`${id}-body`);
    }

    isOpen(id) {
        return this.windows.has(id);
    }
}

// Global singleton
window.wm = new WindowManager();
