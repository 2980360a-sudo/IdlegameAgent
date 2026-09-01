/**
 * IdleAgent — Web 控制台主脚本
 * 与后端 FastAPI 通过 REST + WebSocket 实时交互
 * 版本：0.2.1
 */

// ============================================================
// 1. 全局状态与 DOM 引用
// ============================================================

const AppState = {
    currentStatus: null,      // 最新的游戏状态
    logs: [],                 // 日志数组（最多 500 条）
    isRunning: false,         // Agent 运行状态
    ws: null,                 // WebSocket 实例
    reconnectTimer: null,     // 重连定时器
    currentPage: 'dashboard', // 当前页面（dashboard / rules / logs / analytics / settings）
};

// DOM 元素缓存（若页面中不存在对应 ID，则自动忽略）
const DOM = {
    // 仪表盘数值
    gold: document.getElementById('gold-value'),
    wood: document.getElementById('wood-value'),
    stone: document.getElementById('stone-value'),
    hp: document.getElementById('hp-value'),
    maxHp: document.getElementById('max-hp-value'),
    // 状态指示灯
    statusIndicator: document.getElementById('agent-status'),
    // 控制按钮
    startBtn: document.getElementById('btn-start'),
    stopBtn: document.getElementById('btn-stop'),
    pauseBtn: document.getElementById('btn-pause'),
    // 日志表格体
    logBody: document.getElementById('log-table-body'),
    // 规则内容（如果页面存在）
    rulesContent: document.getElementById('rules-content'),
    // 分析图表容器（如果有）
    chartContainer: document.getElementById('chart-container'),
    // 设置表单（如果有）
    settingsForm: document.getElementById('settings-form'),
};

// ============================================================
// 2. API 调用封装
// ============================================================

const API = {
    /**
     * 获取当前游戏状态
     */
    async getStatus() {
        const res = await fetch('/api/status');
        if (!res.ok) throw new Error(`Status API error: ${res.status}`);
        return res.json();
    },

    /**
     * 获取日志列表
     * @param {number} limit 返回条数
     */
    async getLogs(limit = 100) {
        const res = await fetch(`/api/logs?limit=${limit}`);
        if (!res.ok) throw new Error(`Logs API error: ${res.status}`);
        return res.json();
    },

    /**
     * 控制 Agent（start / stop / pause）
     * @param {string} action
     */
    async control(action) {
        const res = await fetch(`/api/control/${action}`, { method: 'POST' });
        if (!res.ok) throw new Error(`Control API error: ${res.status}`);
        return res.json();
    },

    /**
     * 获取规则配置（用于“规则”页面）
     */
    async getRules() {
        const res = await fetch('/api/rules');
        if (!res.ok) throw new Error(`Rules API error: ${res.status}`);
        return res.json();
    },
};

// ============================================================
// 3. 渲染函数（将数据填充到 DOM）
// ============================================================

/**
 * 渲染仪表盘状态
 */
function renderStatus(status) {
    if (!status) return;
    AppState.currentStatus = status;

    // 资源
    const resources = status.resources || {};
    if (DOM.gold) DOM.gold.textContent = (resources.gold || 0).toFixed(0);
    if (DOM.wood) DOM.wood.textContent = (resources.wood || 0).toFixed(0);
    if (DOM.stone) DOM.stone.textContent = (resources.stone || 0).toFixed(0);

    // 战斗
    const combat = status.combat || {};
    if (DOM.hp) DOM.hp.textContent = (combat.hp || 0).toFixed(0);
    if (DOM.maxHp) DOM.maxHp.textContent = (combat.max_hp || 0).toFixed(0);

    // 运行状态
    const running = status.is_running === true;
    AppState.isRunning = running;
    if (DOM.statusIndicator) {
        DOM.statusIndicator.className = running ? 'status-on' : 'status-off';
        DOM.statusIndicator.textContent = running ? '● 运行中' : '● 已停止';
    }
}

/**
 * 渲染日志表格（只显示最近 200 条）
 */
function renderLogs(logs) {
    if (!DOM.logBody) return;
    const recent = logs.slice(-200);
    DOM.logBody.innerHTML = recent.map(log => {
        const time = new Date(log.timestamp * 1000).toLocaleTimeString();
        const levelClass = log.level || 'info';
        return `
            <tr>
                <td>${time}</td>
                <td><span class="log-level ${levelClass}">${levelClass.toUpperCase()}</span></td>
                <td>${log.module || 'system'}</td>
                <td>${escapeHtml(log.message || '')}</td>
            </tr>
        `;
    }).join('');
}

/**
 * 简单的防 XSS 转义（用于日志消息）
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 渲染规则页面（如果元素存在）
 */
async function renderRules() {
    if (!DOM.rulesContent) return;
    try {
        const data = await API.getRules();
        const yamlText = data.rules ? JSON.stringify(data.rules, null, 2) : '（无规则配置）';
        DOM.rulesContent.textContent = yamlText;
    } catch (err) {
        DOM.rulesContent.textContent = '加载规则失败: ' + err.message;
    }
}

// ============================================================
// 4. WebSocket 连接与消息处理
// ============================================================

function initWebSocket() {
    // 如果已有连接，先关闭
    if (AppState.ws) {
        AppState.ws.close();
        AppState.ws = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    AppState.ws = new WebSocket(wsUrl);

    AppState.ws.onopen = () => {
        console.log('[WS] 已连接到 IdleAgent 后端');
        // 清除重连定时器
        if (AppState.reconnectTimer) {
            clearTimeout(AppState.reconnectTimer);
            AppState.reconnectTimer = null;
        }
        // 每 30 秒发送一次 ping 保持连接（可选）
        if (window._wsPingInterval) clearInterval(window._wsPingInterval);
        window._wsPingInterval = setInterval(() => {
            if (AppState.ws && AppState.ws.readyState === WebSocket.OPEN) {
                AppState.ws.send('ping');
            }
        }, 30000);
    };

    AppState.ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            // 根据消息类型处理
            if (data.type === 'state_update') {
                renderStatus(data.payload);
            } else if (data.type === 'log') {
                // 追加日志并自动截断
                AppState.logs.push(data.payload);
                if (AppState.logs.length > 500) {
                    AppState.logs = AppState.logs.slice(-500);
                }
                // 如果当前在日志页面，重新渲染
                if (AppState.currentPage === 'logs' || AppState.currentPage === 'dashboard') {
                    renderLogs(AppState.logs);
                }
            }
        } catch (e) {
            console.warn('[WS] 消息解析失败:', e);
        }
    };

    AppState.ws.onerror = (err) => {
        console.error('[WS] 错误:', err);
    };

    AppState.ws.onclose = () => {
        console.warn('[WS] 断开连接，3 秒后重连...');
        if (AppState.reconnectTimer) clearTimeout(AppState.reconnectTimer);
        AppState.reconnectTimer = setTimeout(() => {
            initWebSocket();
        }, 3000);
    };
}

// ============================================================
// 5. 控制按钮绑定
// ============================================================

function setupControls() {
    const showMessage = (msg) => alert(msg);

    if (DOM.startBtn) {
        DOM.startBtn.addEventListener('click', async () => {
            try {
                const result = await API.control('start');
                showMessage(result.message || 'Agent 已启动');
                // 刷新状态
                const status = await API.getStatus();
                renderStatus(status);
            } catch (err) {
                showMessage('启动失败: ' + err.message);
            }
        });
    }

    if (DOM.stopBtn) {
        DOM.stopBtn.addEventListener('click', async () => {
            try {
                const result = await API.control('stop');
                showMessage(result.message || 'Agent 已停止');
                const status = await API.getStatus();
                renderStatus(status);
            } catch (err) {
                showMessage('停止失败: ' + err.message);
            }
        });
    }

    if (DOM.pauseBtn) {
        DOM.pauseBtn.addEventListener('click', async () => {
            try {
                const result = await API.control('pause');
                showMessage(result.message || 'Agent 已暂停');
                const status = await API.getStatus();
                renderStatus(status);
            } catch (err) {
                showMessage('暂停失败: ' + err.message);
            }
        });
    }
}

// ============================================================
// 6. 页面切换（如果您的 HTML 有多页面导航）
// ============================================================

function navigateTo(page) {
    AppState.currentPage = page;
    // 隐藏所有页面（假设每个页面容器有 id="page-xxx"）
    const pages = ['dashboard', 'rules', 'logs', 'analytics', 'settings'];
    pages.forEach(p => {
        const el = document.getElementById(`page-${p}`);
        if (el) el.style.display = (p === page) ? 'block' : 'none';
    });

    // 根据页面加载相应数据
    if (page === 'rules') {
        renderRules();
    } else if (page === 'logs') {
        renderLogs(AppState.logs);
    } else if (page === 'dashboard') {
        // 确保仪表盘显示最新状态
        if (AppState.currentStatus) renderStatus(AppState.currentStatus);
    }
    // 其他页面可自行扩展
}

// ============================================================
// 7. 初始化数据加载
// ============================================================

async function loadInitialData() {
    try {
        // 并行获取状态和日志
        const [status, logData] = await Promise.all([
            API.getStatus(),
            API.getLogs(100)
        ]);
        renderStatus(status);
        AppState.logs = logData.logs || [];
        renderLogs(AppState.logs);
    } catch (err) {
        console.error('加载初始数据失败:', err);
        // 显示错误提示（可选）
        const msgEl = document.getElementById('error-message');
        if (msgEl) msgEl.textContent = '⚠️ 无法连接后端，请确保服务已启动。';
    }
}

// ============================================================
// 8. 主初始化入口
// ============================================================

async function initApp() {
    // 1. 加载初始数据
    await loadInitialData();

    // 2. 建立 WebSocket 连接
    initWebSocket();

    // 3. 绑定控制按钮
    setupControls();

    // 4. 设置页面切换（如果存在导航菜单）
    const navLinks = document.querySelectorAll('[data-page]');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = link.getAttribute('data-page');
            if (page) navigateTo(page);
        });
    });

    // 默认显示 dashboard（如果有多页面）
    navigateTo('dashboard');

    // 5. 可选：设置一个备用的轮询，当 WebSocket 断开时仍能刷新状态
    // 但为了减少请求，仅在 WS 未连接时轮询
    setInterval(async () => {
        if (AppState.ws && AppState.ws.readyState === WebSocket.OPEN) {
            return; // WS 正常，不轮询
        }
        try {
            const status = await API.getStatus();
            renderStatus(status);
        } catch (e) {
            // 忽略
        }
    }, 15000); // 15 秒一次备用轮询
}

// 页面加载完成后启动
document.addEventListener('DOMContentLoaded', initApp);
