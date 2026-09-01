/**
 * IdleAgent — Web 控制台主脚本（修复语法错误版）
 * 所有函数均已测试，无语法错误
 */

console.log('[IdleAgent] 脚本开始加载...');

// ============================================================
// 1. 全局状态
// ============================================================
var AppState = {
    currentStatus: null,
    logs: [],
    isRunning: false,
    ws: null,
    reconnectTimer: null,
    currentPage: 'dashboard'
};

// ============================================================
// 2. DOM 引用（安全获取）
// ============================================================
var DOM = {
    gold: document.getElementById('gold-value'),
    wood: document.getElementById('wood-value'),
    stone: document.getElementById('stone-value'),
    hp: document.getElementById('hp-value'),
    maxHp: document.getElementById('max-hp-value'),
    statusIndicator: document.getElementById('agent-status'),
    startBtn: document.getElementById('btn-start'),
    stopBtn: document.getElementById('btn-stop'),
    pauseBtn: document.getElementById('btn-pause'),
    logBody: document.getElementById('log-table-body'),
    rulesContent: document.getElementById('rules-content')
};

console.log('[IdleAgent] DOM 元素检查:', {
    gold: !!DOM.gold,
    wood: !!DOM.wood,
    stone: !!DOM.stone,
    hp: !!DOM.hp,
    maxHp: !!DOM.maxHp,
    statusIndicator: !!DOM.statusIndicator,
    startBtn: !!DOM.startBtn,
    stopBtn: !!DOM.stopBtn,
    pauseBtn: !!DOM.pauseBtn,
    logBody: !!DOM.logBody
});

// ============================================================
// 3. API 调用（使用传统函数避免箭头语法问题）
// ============================================================
var API = {
    getStatus: function() {
        return fetch('/api/status').then(function(res) {
            if (!res.ok) throw new Error('Status API error: ' + res.status);
            return res.json();
        });
    },
    getLogs: function(limit) {
        limit = limit || 100;
        return fetch('/api/logs?limit=' + limit).then(function(res) {
            if (!res.ok) throw new Error('Logs API error: ' + res.status);
            return res.json();
        });
    },
    control: function(action) {
        return fetch('/api/control/' + action, { method: 'POST' }).then(function(res) {
            if (!res.ok) throw new Error('Control API error: ' + res.status);
            return res.json();
        });
    },
    getRules: function() {
        return fetch('/api/rules').then(function(res) {
            if (!res.ok) throw new Error('Rules API error: ' + res.status);
            return res.json();
        });
    }
};

// ============================================================
// 4. 渲染函数（安全更新 DOM）
// ============================================================
function renderStatus(status) {
    if (!status) return;
    AppState.currentStatus = status;

    var resources = status.resources || {};
    if (DOM.gold) DOM.gold.textContent = (resources.gold || 0).toFixed(0);
    if (DOM.wood) DOM.wood.textContent = (resources.wood || 0).toFixed(0);
    if (DOM.stone) DOM.stone.textContent = (resources.stone || 0).toFixed(0);

    var combat = status.combat || {};
    if (DOM.hp) DOM.hp.textContent = (combat.hp || 0).toFixed(0);
    if (DOM.maxHp) DOM.maxHp.textContent = (combat.max_hp || 0).toFixed(0);

    var running = status.is_running === true;
    AppState.isRunning = running;
    if (DOM.statusIndicator) {
        DOM.statusIndicator.className = running ? 'status-on' : 'status-off';
        DOM.statusIndicator.textContent = running ? '● 运行中' : '● 已停止';
    }
}

function renderLogs(logs) {
    if (!DOM.logBody) return;
    var recent = logs.slice(-200);
    var html = '';
    for (var i = 0; i < recent.length; i++) {
        var log = recent[i];
        var time = new Date(log.timestamp * 1000).toLocaleTimeString();
        var levelClass = log.level || 'info';
        var levelText = levelClass.toUpperCase();
        var module = log.module || 'system';
        var message = escapeHtml(log.message || '');
        html += '<tr><td>' + time + '</td><td><span class="log-level ' + levelClass + '">' + levelText + '</span></td><td>' + module + '</td><td>' + message + '</td></tr>';
    }
    DOM.logBody.innerHTML = html;
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderRules() {
    if (!DOM.rulesContent) return;
    API.getRules().then(function(data) {
        var text = data.rules ? JSON.stringify(data.rules, null, 2) : '（无规则配置）';
        DOM.rulesContent.textContent = text;
    }).catch(function(err) {
        DOM.rulesContent.textContent = '加载规则失败: ' + err.message;
    });
}

// ============================================================
// 5. WebSocket
// ============================================================
function initWebSocket() {
    if (AppState.ws) {
        AppState.ws.close();
        AppState.ws = null;
    }
    var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var wsUrl = protocol + '//' + window.location.host + '/ws';
    AppState.ws = new WebSocket(wsUrl);

    AppState.ws.onopen = function() {
        console.log('[WS] 已连接');
        if (AppState.reconnectTimer) {
            clearTimeout(AppState.reconnectTimer);
            AppState.reconnectTimer = null;
        }
        if (window._wsPingInterval) clearInterval(window._wsPingInterval);
        window._wsPingInterval = setInterval(function() {
            if (AppState.ws && AppState.ws.readyState === WebSocket.OPEN) {
                AppState.ws.send('ping');
            }
        }, 30000);
    };

    AppState.ws.onmessage = function(event) {
        try {
            var data = JSON.parse(event.data);
            if (data.type === 'state_update') {
                renderStatus(data.payload);
            } else if (data.type === 'log') {
                AppState.logs.push(data.payload);
                if (AppState.logs.length > 500) AppState.logs = AppState.logs.slice(-500);
                if (AppState.currentPage === 'logs' || AppState.currentPage === 'dashboard') {
                    renderLogs(AppState.logs);
                }
            }
        } catch (e) {
            console.warn('[WS] 解析失败:', e);
        }
    };

    AppState.ws.onerror = function(err) {
        console.error('[WS] 错误:', err);
    };

    AppState.ws.onclose = function() {
        console.warn('[WS] 断开，3秒后重连...');
        if (AppState.reconnectTimer) clearTimeout(AppState.reconnectTimer);
        AppState.reconnectTimer = setTimeout(initWebSocket, 3000);
    };
}

// ============================================================
// 6. 控制按钮绑定
// ============================================================
function setupControls() {
    function showMessage(msg) {
        alert(msg);
    }

    if (DOM.startBtn) {
        DOM.startBtn.addEventListener('click', function() {
            API.control('start').then(function(result) {
                showMessage(result.message || 'Agent 已启动');
                return API.getStatus();
            }).then(function(status) {
                renderStatus(status);
            }).catch(function(err) {
                showMessage('启动失败: ' + err.message);
            });
        });
    }

    if (DOM.stopBtn) {
        DOM.stopBtn.addEventListener('click', function() {
            API.control('stop').then(function(result) {
                showMessage(result.message || 'Agent 已停止');
                return API.getStatus();
            }).then(function(status) {
                renderStatus(status);
            }).catch(function(err) {
                showMessage('停止失败: ' + err.message);
            });
        });
    }

    if (DOM.pauseBtn) {
        DOM.pauseBtn.addEventListener('click', function() {
            API.control('pause').then(function(result) {
                showMessage(result.message || 'Agent 已暂停');
                return API.getStatus();
            }).then(function(status) {
                renderStatus(status);
            }).catch(function(err) {
                showMessage('暂停失败: ' + err.message);
            });
        });
    }
}

// ============================================================
// 7. 页面导航
// ============================================================
function navigateTo(page) {
    AppState.currentPage = page;
    var pages = ['dashboard', 'rules', 'logs', 'analytics', 'settings'];
    for (var i = 0; i < pages.length; i++) {
        var el = document.getElementById('page-' + pages[i]);
        if (el) el.style.display = (pages[i] === page) ? 'block' : 'none';
    }
    if (page === 'rules') renderRules();
    else if (page === 'logs') renderLogs(AppState.logs);
    else if (page === 'dashboard' && AppState.currentStatus) renderStatus(AppState.currentStatus);
}

// ============================================================
// 8. 数据加载
// ============================================================
function loadInitialData() {
    Promise.all([
        API.getStatus(),
        API.getLogs(100)
    ]).then(function(results) {
        var status = results[0];
        var logData = results[1];
        renderStatus(status);
        AppState.logs = logData.logs || [];
        renderLogs(AppState.logs);
        console.log('[IdleAgent] 初始数据加载成功');
    }).catch(function(err) {
        console.error('加载初始数据失败:', err);
        var msgEl = document.getElementById('error-message');
        if (msgEl) msgEl.textContent = '⚠️ 无法连接后端，请确保服务已启动。';
    });
}

// ============================================================
// 9. 初始化
// ============================================================
function initApp() {
    console.log('[IdleAgent] 开始初始化...');
    loadInitialData();
    initWebSocket();
    setupControls();

    // 导航菜单绑定
    var navLinks = document.querySelectorAll('[data-page]');
    for (var i = 0; i < navLinks.length; i++) {
        (function(link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                var page = link.getAttribute('data-page');
                if (page) navigateTo(page);
            });
        })(navLinks[i]);
    }

    navigateTo('dashboard');

    // 备用轮询
    setInterval(function() {
        if (AppState.ws && AppState.ws.readyState === WebSocket.OPEN) return;
        API.getStatus().then(function(status) {
            renderStatus(status);
        }).catch(function(e) { /* 忽略 */ });
    }, 15000);

    console.log('[IdleAgent] 初始化完成');
}

// 页面加载完成后启动
document.addEventListener('DOMContentLoaded', initApp);
