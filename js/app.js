/**
 * IdleAgent — Web 控制台主脚本 (适配动态内容版)
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
// 2. DOM 引用（初始为空，渲染后更新）
// ============================================================
var DOM = {};

// ============================================================
// 3. 渲染仪表盘内容
// ============================================================
function renderDashboard() {
    var contentArea = document.getElementById('contentArea');
    if (!contentArea) return;
    contentArea.innerHTML = `
        <div class="dashboard-stats">
            <div class="stat-card">
                <div class="stat-label">💰 金币</div>
                <div class="stat-value" id="gold-value">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🪵 木头</div>
                <div class="stat-value" id="wood-value">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🪨 石头</div>
                <div class="stat-value" id="stone-value">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">❤️ 生命值</div>
                <div class="stat-value" id="hp-value">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">❤️ 最大生命</div>
                <div class="stat-value" id="max-hp-value">0</div>
            </div>
        </div>
        <div class="logs-section">
            <h3>决策日志</h3>
            <table>
                <thead><tr><th>时间</th><th>级别</th><th>模块</th><th>消息</th></tr></thead>
                <tbody id="log-table-body"></tbody>
            </table>
        </div>
    `;
    // 更新 DOM 引用
    DOM.gold = document.getElementById('gold-value');
    DOM.wood = document.getElementById('wood-value');
    DOM.stone = document.getElementById('stone-value');
    DOM.hp = document.getElementById('hp-value');
    DOM.maxHp = document.getElementById('max-hp-value');
    DOM.logBody = document.getElementById('log-table-body');
    DOM.statusIndicator = document.querySelector('.agent-status .status-dot');
    DOM.startBtn = document.getElementById('startBtn');   // 如果有这些按钮，需在 HTML 中添加对应 id
    DOM.stopBtn = document.getElementById('stopBtn');
    DOM.pauseBtn = document.getElementById('pauseBtn');
    DOM.rulesContent = document.getElementById('rules-content'); // 可能在其他页面
    console.log('[IdleAgent] 仪表盘渲染完成，DOM 已更新');
}

// ============================================================
// 4. API 调用
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
// 5. 渲染函数（安全更新 DOM）
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
        DOM.statusIndicator.className = 'status-dot ' + (running ? 'running' : 'stopped');
        // 同时更新侧边栏文本（可选）
        var statusSpan = document.querySelector('.agent-status span');
        if (statusSpan) statusSpan.textContent = running ? 'Agent运行中' : 'Agent已停止';
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

// ============================================================
// 6. WebSocket（同前，略）
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
            var trimmed = event.data.trim();
            if (trimmed.startsWith('{') || trimmed.startsWith('[') || trimmed.startsWith('"')) {
                var data = JSON.parse(trimmed);
                if (data.type === 'state_update') {
                    renderStatus(data.payload);
                } else if (data.type === 'log') {
                    AppState.logs.push(data.payload);
                    if (AppState.logs.length > 500) AppState.logs = AppState.logs.slice(-500);
                    if (AppState.currentPage === 'logs' || AppState.currentPage === 'dashboard') {
                        renderLogs(AppState.logs);
                    }
                }
            } else {
                console.log('[WS] 收到文本:', trimmed);
            }
        } catch (e) {
            console.warn('[WS] 解析失败:', e, '原始数据:', event.data);
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
// 7. 控制按钮（需在 HTML 中添加 id）
// ============================================================
function setupControls() {
    function showMessage(msg) { alert(msg); }

    // 检查是否有这些按钮（需在 HTML 中添加 id）
    var startBtn = document.getElementById('startBtn');
    var stopBtn = document.getElementById('stopBtn');
    var pauseBtn = document.getElementById('pauseBtn');

    if (startBtn) {
        startBtn.addEventListener('click', function() {
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

    if (stopBtn) {
        stopBtn.addEventListener('click', function() {
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

    if (pauseBtn) {
        pauseBtn.addEventListener('click', function() {
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

    // 刷新按钮
    var refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            API.getStatus().then(function(status) {
                renderStatus(status);
            }).catch(function(err) {
                console.error('刷新失败:', err);
            });
        });
    }
}

// ============================================================
// 8. 页面导航（适配你的侧边栏）
// ============================================================
function navigateTo(page) {
    AppState.currentPage = page;
    // 更新导航高亮
    var navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(function(item) {
        item.classList.remove('active');
        if (item.getAttribute('data-page') === page) {
            item.classList.add('active');
        }
    });
    // 页面标题更新
    var titleMap = {
        'dashboard': '仪表盘',
        'games': '游戏管理',
        'rules': '规则配置',
        'logs': '决策日志',
        'analytics': '数据分析',
        'settings': '系统设置'
    };
    var pageTitle = document.querySelector('.page-title');
    var pageSubtitle = document.querySelector('.page-subtitle');
    if (pageTitle) pageTitle.textContent = titleMap[page] || page;
    if (pageSubtitle) {
        var subMap = {
            'dashboard': '实时监控所有游戏Agent的运行状态',
            'games': '管理已添加的游戏和适配器',
            'rules': '查看和编辑YAML规则配置',
            'logs': '查看Agent的决策日志和历史记录',
            'analytics': '数据分析和图表展示',
            'settings': '系统设置和账号管理'
        };
        pageSubtitle.textContent = subMap[page] || '';
    }

    // 根据页面渲染内容（目前只有仪表盘实现）
    if (page === 'dashboard') {
        renderDashboard();
        // 重新加载数据
        API.getStatus().then(function(status) {
            renderStatus(status);
        }).catch(function(err) {
            console.error('加载状态失败:', err);
        });
        API.getLogs(100).then(function(logData) {
            AppState.logs = logData.logs || [];
            renderLogs(AppState.logs);
        }).catch(function(err) {
            console.error('加载日志失败:', err);
        });
    } else {
        // 其他页面暂时显示占位信息
        var contentArea = document.getElementById('contentArea');
        if (contentArea) {
            contentArea.innerHTML = '<div class="placeholder"><h2>' + (titleMap[page] || page) + '</h2><p>该页面正在开发中...</p></div>';
        }
    }
}

// ============================================================
// 9. 数据加载（初始调用）
// ============================================================
function loadInitialData() {
    // 先渲染仪表盘
    renderDashboard();
    // 加载数据
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
// 10. 初始化
// ============================================================
function initApp() {
    console.log('[IdleAgent] 开始初始化...');
    loadInitialData();
    initWebSocket();
    setupControls();

    // 导航菜单绑定
    var navLinks = document.querySelectorAll('.nav-item[data-page]');
    navLinks.forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            var page = link.getAttribute('data-page');
            if (page) navigateTo(page);
        });
    });

    // 模态框逻辑（简单示例）
    var addGameBtn = document.getElementById('addGameBtn');
    var modal = document.getElementById('addGameModal');
    var closeModal = function() {
        if (modal) modal.style.display = 'none';
    };
    if (addGameBtn && modal) {
        addGameBtn.addEventListener('click', function() {
            modal.style.display = 'block';
        });
        modal.querySelector('.modal-close').addEventListener('click', closeModal);
        modal.querySelector('.modal-backdrop').addEventListener('click', closeModal);
        document.getElementById('cancelAddGame').addEventListener('click', closeModal);
        document.getElementById('confirmAddGame').addEventListener('click', function() {
            alert('游戏添加功能开发中');
            closeModal();
        });
    }

    console.log('[IdleAgent] 初始化完成');
}

// 页面加载完成后启动
document.addEventListener('DOMContentLoaded', initApp);
