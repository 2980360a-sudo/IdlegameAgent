/**
 * IdleAgent — Web 控制台 (v0.6.0)
 * 登录/注册 + 仪表盘 + 个人资料
 */
(function () {
    'use strict';

    // ============================================================
    // 全局状态
    // ============================================================
    var AppState = {
        token: localStorage.getItem('idleagent_token') || '',
        user: null,
        currentPage: 'dashboard',
        nextPatrolAt: null
    };

    // ============================================================
    // API 封装（自动携带 Bearer token）
    // ============================================================
    var API = {
        request: function (method, path, body) {
            var headers = { 'Content-Type': 'application/json' };
            if (AppState.token) headers['Authorization'] = 'Bearer ' + AppState.token;
            return fetch('/api' + path, {
                method: method,
                headers: headers,
                body: body ? JSON.stringify(body) : undefined
            }).then(function (res) {
                return res.json().catch(function () { return {}; }).then(function (data) {
                    if (!res.ok) {
                        var err = new Error(data.detail || ('请求失败 (' + res.status + ')'));
                        err.status = res.status;
                        throw err;
                    }
                    return data;
                });
            });
        },
        register: function (p) { return API.request('POST', '/auth/register', p); },
        login: function (p) { return API.request('POST', '/auth/login', p); },
        logout: function () { return API.request('POST', '/auth/logout'); },
        me: function () { return API.request('GET', '/auth/me'); },
        updateMe: function (p) { return API.request('PATCH', '/auth/me', p); },
        getStatus: function () { return API.request('GET', '/status'); },
        getLogs: function (limit) { return API.request('GET', '/logs?limit=' + (limit || 100)); },
        // Melvor 挂机
        melvorModes: function () { return API.request('GET', '/melvor/modes'); },
        melvorConfig: function () { return API.request('GET', '/melvor/config'); },
        melvorLogin: function (p) { return API.request('POST', '/melvor/login', p); },
        melvorAutoLogin: function () { return API.request('POST', '/melvor/auto_login'); },
        melvorAutoResume: function () { return API.request('POST', '/melvor/auto_resume'); },
        melvorCharacters: function () { return API.request('GET', '/melvor/characters'); },
        melvorSelect: function (p) { return API.request('POST', '/melvor/select', p); },
        melvorStart: function (p) { return API.request('POST', '/melvor/start', p); },
        melvorStop: function () { return API.request('POST', '/melvor/stop'); },
        melvorPatrol: function (p) { return API.request('POST', '/melvor/patrol', p); },
        melvorFeedback: function (p) { return API.request('POST', '/melvor/feedback', p); },
        melvorDisconnect: function () { return API.request('POST', '/melvor/disconnect'); },
        melvorStatus: function () { return API.request('GET', '/melvor/status'); },
        melvorEvents: function () { return API.request('GET', '/melvor/events'); },
        melvorDecisions: function () { return API.request('GET', '/melvor/decisions'); },
        melvorGuides: function () { return API.request('GET', '/melvor/guides'); },
        melvorScript: function (p) { return API.request('POST', '/melvor/script', p); },
        getSettings: function () { return API.request('GET', '/settings'); },
        updateSettings: function (p) { return API.request('POST', '/settings', p); }
    };

    // ============================================================
    // 工具函数
    // ============================================================
    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }
    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }
    function show(el) { if (el) el.classList.remove('hidden'); }
    function hide(el) { if (el) el.classList.add('hidden'); }
    function toast(msg, isError) {
        var t = document.createElement('div');
        t.className = 'toast' + (isError ? ' toast-error' : '');
        t.textContent = msg;
        document.body.appendChild(t);
        setTimeout(function () { t.classList.add('toast-out'); }, 2500);
        setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 2900);
    }
    function setAuthError(msg) {
        var el = $('#authError');
        if (!msg) { hide(el); el.textContent = ''; return; }
        el.textContent = msg;
        show(el);
    }

    // ============================================================
    // 认证视图切换
    // ============================================================
    function switchAuthTab(tab) {
        $$('.auth-tab').forEach(function (b) { b.classList.toggle('active', b.dataset.tab === tab); });
        $('#loginForm').classList.toggle('hidden', tab !== 'login');
        $('#registerForm').classList.toggle('hidden', tab !== 'register');
        setAuthError('');
    }

    function showAuth() {
        show($('#authView'));
        hide($('#appView'));
        AppState.user = null;
    }

    function showApp() {
        hide($('#authView'));
        show($('#appView'));
        renderUserChip();
        navigateTo('dashboard');
    }

    function setToken(token) {
        AppState.token = token;
        if (token) localStorage.setItem('idleagent_token', token);
        else localStorage.removeItem('idleagent_token');
    }

    function clearAuth() {
        setToken('');
        AppState.user = null;
    }

    function renderUserChip() {
        var u = AppState.user || {};
        var name = u.display_name || u.username || '用户';
        $('#sidebarName').textContent = name;
        $('#sidebarMail').textContent = u.email || u.username || '';
        $('#sidebarAvatar').textContent = (name.charAt(0) || '?').toUpperCase();
    }

    // ============================================================
    // 表单绑定
    // ============================================================
    function bindAuthForms() {
        $$('.auth-tab').forEach(function (b) {
            b.addEventListener('click', function () { switchAuthTab(b.dataset.tab); });
        });

        $('#loginForm').addEventListener('submit', function (e) {
            e.preventDefault();
            var account = $('#loginAccount').value.trim();
            var password = $('#loginPassword').value;
            if (!account || !password) { setAuthError('请输入用户名和密码'); return; }
            var btn = $('#loginBtn');
            btn.disabled = true; btn.textContent = '登录中...';
            API.login({ login: account, password: password }).then(function (data) {
                setToken(data.token);
                AppState.user = data.user;
                toast('欢迎回来，' + (data.user.display_name || data.user.username));
                showApp();
            }).catch(function (err) {
                setAuthError(err.message);
            }).finally(function () {
                btn.disabled = false; btn.textContent = '登 录';
            });
        });

        $('#registerForm').addEventListener('submit', function (e) {
            e.preventDefault();
            var username = $('#regUsername').value.trim();
            var email = $('#regEmail').value.trim();
            var displayName = $('#regDisplayName').value.trim();
            var password = $('#regPassword').value;
            var password2 = $('#regPassword2').value;
            if (!username || !password) { setAuthError('用户名和密码为必填'); return; }
            if (password.length < 6) { setAuthError('密码至少 6 位'); return; }
            if (password !== password2) { setAuthError('两次输入的密码不一致'); return; }
            var btn = $('#registerBtn');
            btn.disabled = true; btn.textContent = '注册中...';
            API.register({
                username: username, email: email, password: password, display_name: displayName
            }).then(function (data) {
                setToken(data.token);
                AppState.user = data.user;
                toast('注册成功，欢迎 ' + data.user.username);
                showApp();
            }).catch(function (err) {
                setAuthError(err.message);
            }).finally(function () {
                btn.disabled = false; btn.textContent = '注 册';
            });
        });
    }

    function bindShell() {
        $('#logoutBtn').addEventListener('click', function () {
            API.logout().catch(function () {}).finally(function () {
                clearAuth();
                showAuth();
                switchAuthTab('login');
                toast('已退出登录');
            });
        });
        $('#refreshBtn').addEventListener('click', function () {
            if (AppState.currentPage === 'dashboard') loadDashboardData();
        });
        $$('.nav-item[data-page]').forEach(function (link) {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                navigateTo(link.dataset.page);
            });
        });
    }

    // ============================================================
    // 路由
    // ============================================================
    function navigateTo(page) {
        AppState.currentPage = page;
        $$('.nav-item').forEach(function (item) {
            item.classList.toggle('active', item.dataset.page === page);
        });
        var titles = {
            dashboard: ['仪表盘', '实时监控游戏 Agent 运行状态'],
            melvor: ['梅尔沃放置', '登录云账号、选择角色、运行挂机 Agent'],
            logs: ['决策日志', '查看 Agent 的事件与决策记录'],
            settings: ['系统设置', '模型 API 配置与运行参数'],
            profile: ['个人资料', '查看与编辑你的账户信息']
        };
        var t = titles[page] || titles.dashboard;
        $('#pageTitle').textContent = t[0];
        $('#pageSubtitle').textContent = t[1];
        if (page === 'melvor') renderMelvor();
        else if (page === 'logs') renderLogs();
        else if (page === 'settings') renderSettings();
        else if (page === 'profile') renderProfile();
        else renderDashboard();
    }

    // ============================================================
    // 仪表盘
    // ============================================================
    function renderDashboard() {
        $('#contentArea').innerHTML = '' +
            '<div class="dashboard-stats" id="dash-stats">' +
            '  <div class="stat-card"><div class="stat-label">金币</div><div class="stat-value" id="d-gold">-</div></div>' +
            '  <div class="stat-card"><div class="stat-label">屠杀币</div><div class="stat-value" id="d-slayer">-</div></div>' +
            '  <div class="stat-card"><div class="stat-label">总等级</div><div class="stat-value primary" id="d-total">-</div></div>' +
            '  <div class="stat-card"><div class="stat-label">战斗等级</div><div class="stat-value primary" id="d-combat">-</div></div>' +
            '  <div class="stat-card"><div class="stat-label">仓库</div><div class="stat-value" id="d-bank">-</div></div>' +
            '  <div class="stat-card"><div class="stat-label">生命</div><div class="stat-value success" id="d-hp">-</div></div>' +
            '</div>' +
            '<div class="dashboard-row">' +
            '  <div class="panel"><div class="panel-header"><span class="panel-title">Agent 运行状态</span></div>' +
            '    <div class="panel-body" id="dash-agent"><div class="empty">加载中...</div></div></div>' +
            '  <div class="panel"><div class="panel-header"><span class="panel-title">最近决策</span></div>' +
            '    <div class="panel-body"><ul id="dash-decisions" class="log-list"></ul></div></div>' +
            '</div>';
        loadDashboardData();
    }

    function loadDashboardData() {
        API.melvorStatus().then(function (s) {
            var game = s.game || {};
            var raw = game.raw_probe || {};
            $('#d-gold').textContent = fmtCompact(game.gold);
            $('#d-slayer').textContent = fmtCompact(game.slayer_coins);
            $('#d-total').textContent = raw.totalLevel != null ? raw.totalLevel : '-';
            $('#d-combat').textContent = game.combat_level != null ? game.combat_level : '-';
            $('#d-bank').textContent = fmt(game.bank_used) + ' / ' + fmt(game.bank_max);
            var hp = game.hp || 0, maxHp = game.max_hp || 0;
            $('#d-hp').textContent = hp + ' / ' + maxHp;
            // Agent 状态
            var llm = s.llm || {};
            $('#dash-agent').innerHTML = '<ul class="kv-list">' +
                kvRow('会话状态', sessionText(s.session_state)) +
                kvRow('运行模式', s.mode_label || '未启动') +
                kvRow('角色', s.character_label || '未选择') +
                kvRow('巡检间隔', (s.patrol_interval || 0) + ' 秒' + (s.llm_schedules ? ' · LLM 自主排程' : '')) +
                kvRow('LLM', llm.configured ? (llm.model + ' · ' + fmtNum((llm.usage || {}).total_tokens) + ' tokens') : '未配置') +
                '</ul>';
        }).catch(function () {
            $('#dash-agent').innerHTML = '<div class="empty"><div class="empty-icon">🎮</div>尚未连接角色，请到「梅尔沃放置」登录</div>';
        });
        API.melvorDecisions().then(function (d) {
            renderMelvorLogs('#dash-decisions', (d.decisions || []).slice(0, 8), 'decision');
        }).catch(function () {});
    }

    // ============================================================
    // 决策日志（独立页，带级别筛选）
    // ============================================================
    var logsFilter = 'all';

    function renderLogs() {
        $('#contentArea').innerHTML = '' +
            '<div class="logs-filter" id="logs-filter">' +
            '  <span class="filter-chip active" data-f="all">全部</span>' +
            '  <span class="filter-chip" data-f="decision">决策</span>' +
            '  <span class="filter-chip" data-f="action">动作</span>' +
            '  <span class="filter-chip" data-f="warning">警告</span>' +
            '  <span class="filter-chip" data-f="error">错误</span>' +
            '  <span class="filter-chip" data-f="info">信息</span>' +
            '</div>' +
            '<div class="panel"><div class="panel-header"><span class="panel-title">日志时间线</span>' +
            '  <span class="panel-hint" id="logs-hint"></span></div>' +
            '  <div class="panel-body"><ul id="logs-list" class="log-list" style="max-height:none"></ul></div></div>';
        $$('#logs-filter .filter-chip').forEach(function (c) {
            c.addEventListener('click', function () {
                $$('#logs-filter .filter-chip').forEach(function (x) { x.classList.remove('active'); });
                c.classList.add('active');
                logsFilter = c.dataset.f;
                loadLogs();
            });
        });
        loadLogs();
    }

    function loadLogs() {
        API.melvorEvents().then(function (d) {
            var events = (d.events || []).map(function (e) {
                return { t: 'event', time: e.timestamp, level: e.severity || 'info', text: e.event_type, detail: e.details || {} };
            });
            return events;
        }).then(function (events) {
            return API.melvorDecisions().then(function (d) {
                var decisions = (d.decisions || []).map(function (x) {
                    var acts = (x.actions || []).map(function (a) { return a.action_type + '→' + a.target; }).join(', ');
                    return { t: 'decision', time: x.timestamp, level: 'decision', text: x.reason || '决策', detail: acts };
                });
                return events.concat(decisions).sort(function (a, b) { return b.time - a.time; });
            });
        }).then(function (items) {
            var filtered = items.filter(function (it) {
                return logsFilter === 'all' || it.level === logsFilter;
            });
            $('#logs-hint').textContent = filtered.length + ' 条';
            var html = filtered.map(function (it) {
                var time = new Date(it.time * 1000).toLocaleString();
                var detail = (it.detail && typeof it.detail === 'string') ? it.detail : JSON.stringify(it.detail || {});
                return '<li class="log-item ' + it.level + '"><span class="log-time">' + time + ' · ' + it.level + '</span>' +
                    '<div class="log-content"><strong>' + escapeHtml(it.text) + '</strong> ' + escapeHtml(detail) + '</div></li>';
            }).join('');
            $('#logs-list').innerHTML = html || '<li class="empty"><div class="empty-icon">📭</div>暂无日志</li>';
        }).catch(function () {
            $('#logs-list').innerHTML = '<li class="empty">加载失败</li>';
        });
    }

    // ============================================================
    // 系统设置（模型 API 配置）
    // ============================================================
    function renderSettings() {
        $('#contentArea').innerHTML = '' +
            '<div class="panel"><div class="panel-header"><span class="panel-title">模型 API 配置</span>' +
            '  <span class="panel-hint">DeepSeek / OpenAI 兼容接口</span></div>' +
            '  <div class="panel-body">' +
            '    <div class="form-group"><label>API Key</label>' +
            '      <input type="password" class="form-input" id="st-api-key" placeholder="sk-..." autocomplete="off"></div>' +
            '    <div class="form-group"><label>模型</label>' +
            '      <input type="text" class="form-input" id="st-model" placeholder="deepseek-chat"></div>' +
            '    <div class="form-group"><label>接口地址（Base URL）</label>' +
            '      <input type="text" class="form-input" id="st-base-url" placeholder="https://api.deepseek.com"></div>' +
            '    <div class="btn-row"><button class="btn btn-primary" id="st-save-btn">保存配置</button>' +
            '      <button class="btn btn-ghost" id="st-test-btn">测试连接</button></div>' +
            '    <div id="st-hint" class="panel-hint mt"></div>' +
            '  </div>' +
            '</div>' +
            '<div class="panel"><div class="panel-header"><span class="panel-title">说明</span></div>' +
            '  <div class="panel-body" style="font-size:13px;color:var(--text-secondary);line-height:1.8">' +
            '    · API Key 保存后立即生效（当前会话热更新），无需重启后端。<br>' +
            '    · 留空 API Key 并保存可清除已配置的密钥。<br>' +
            '    · 配置优先级：本页设置 &gt; .env 环境变量。<br>' +
            '    · 修改后请在「梅尔沃放置」页观察 token 消耗与决策是否正常。' +
            '  </div>' +
            '</div>';
        loadSettings();
        bindSettings();
    }

    function loadSettings() {
        API.getSettings().then(function (data) {
            var llm = data.llm || {};
            $('#st-model').value = llm.model || '';
            $('#st-base-url').value = llm.base_url || '';
            $('#st-hint').textContent = llm.has_key ? ('当前 Key：' + llm.api_key_masked) : '尚未配置 API Key';
        }).catch(function (err) {
            $('#st-hint').textContent = '加载失败：' + err.message;
        });
    }

    function bindSettings() {
        $('#st-save-btn').addEventListener('click', function () {
            var btn = this; btn.disabled = true; btn.textContent = '保存中...';
            API.updateSettings({
                api_key: $('#st-api-key').value.trim(),
                model: $('#st-model').value.trim(),
                base_url: $('#st-base-url').value.trim()
            }).then(function (data) {
                $('#st-api-key').value = '';
                toast('配置已保存' + (data.llm && data.llm.has_key ? '（Key 已生效）' : '（Key 已清除）'));
                loadSettings();
            }).catch(function (err) { toast(err.message, true); })
              .finally(function () { btn.disabled = false; btn.textContent = '保存配置'; });
        });

        $('#st-test-btn').addEventListener('click', function () {
            var key = $('#st-api-key').value.trim();
            var model = $('#st-model').value.trim();
            var base = $('#st-base-url').value.trim();
            var btn = this; btn.disabled = true; btn.textContent = '测试中...';
            API.updateSettings({ api_key: key || undefined, model: model || undefined, base_url: base || undefined })
              .then(function () { toast('已保存，测试连接需通过实际决策触发（或重启后观察）'); })
              .catch(function (err) { toast(err.message, true); })
              .finally(function () { btn.disabled = false; btn.textContent = '测试连接'; });
        });
    }

    function fmt(v) {
        var n = Number(v);
        return isNaN(n) ? '0' : n.toFixed(0);
    }

    // ============================================================
    // 个人资料
    // ============================================================
    function renderProfile() {
        var u = AppState.user || {};
        var note = (u.profile && u.profile.note) ? u.profile.note : '';
        var created = u.created_at ? new Date(u.created_at * 1000).toLocaleString() : '-';
        $('#contentArea').innerHTML = '' +
            '<div class="profile-grid">' +
            '  <div class="panel">' +
            '    <div class="panel-header"><span class="panel-title">账户信息</span></div>' +
            '    <div class="panel-body profile-card">' +
            '      <div class="profile-avatar">' + escapeHtml((u.display_name || u.username || '?').charAt(0).toUpperCase()) + '</div>' +
            '      <div class="profile-meta">' +
            '        <div class="profile-name">' + escapeHtml(u.display_name || u.username) + '</div>' +
            '        <div class="profile-line">用户名：' + escapeHtml(u.username) + '</div>' +
            '        <div class="profile-line">邮箱：' + escapeHtml(u.email || '未设置') + '</div>' +
            '        <div class="profile-line">注册时间：' + escapeHtml(created) + '</div>' +
            '      </div>' +
            '    </div>' +
            '  </div>' +
            '  <div class="panel">' +
            '    <div class="panel-header"><span class="panel-title">编辑资料</span></div>' +
            '    <div class="panel-body">' +
            '      <form id="profileForm">' +
            '        <div class="form-group"><label>昵称</label><input type="text" class="form-input" id="pfDisplayName" value="' + escapeHtml(u.display_name || '') + '"></div>' +
            '        <div class="form-group"><label>邮箱</label><input type="email" class="form-input" id="pfEmail" value="' + escapeHtml(u.email || '') + '"></div>' +
            '        <div class="form-group"><label>自定义备注</label><textarea class="form-input" id="pfNote" rows="4" placeholder="记录你的游戏目标、偏好等">' + escapeHtml(note) + '</textarea></div>' +
            '        <button type="submit" class="btn btn-primary" id="pfSaveBtn">保存修改</button>' +
            '      </form>' +
            '      <hr class="divider">' +
            '      <h4 class="form-section-title">修改密码</h4>' +
            '      <form id="passwordForm">' +
            '        <div class="form-group"><label>新密码</label><input type="password" class="form-input" id="pfNewPassword" placeholder="至少 6 位" autocomplete="new-password"></div>' +
            '        <div class="form-group"><label>确认新密码</label><input type="password" class="form-input" id="pfNewPassword2" placeholder="再次输入" autocomplete="new-password"></div>' +
            '        <button type="submit" class="btn btn-ghost" id="pfPwdBtn">更新密码</button>' +
            '      </form>' +
            '    </div>' +
            '  </div>' +
            '</div>';
        bindProfileForms();
    }

    function bindProfileForms() {
        $('#profileForm').addEventListener('submit', function (e) {
            e.preventDefault();
            var noteText = $('#pfNote').value.trim();
            var profile = Object.assign({}, (AppState.user.profile || {}));
            profile.note = noteText;
            var btn = $('#pfSaveBtn');
            btn.disabled = true; btn.textContent = '保存中...';
            API.updateMe({
                display_name: $('#pfDisplayName').value.trim(),
                email: $('#pfEmail').value.trim(),
                profile: profile
            }).then(function (data) {
                AppState.user = data.user;
                renderUserChip();
                toast('资料已保存');
                renderProfile();
            }).catch(function (err) {
                toast(err.message, true);
                btn.disabled = false; btn.textContent = '保存修改';
            });
        });

        $('#passwordForm').addEventListener('submit', function (e) {
            e.preventDefault();
            var p1 = $('#pfNewPassword').value;
            var p2 = $('#pfNewPassword2').value;
            if (!p1) { toast('请输入新密码', true); return; }
            if (p1.length < 6) { toast('密码至少 6 位', true); return; }
            if (p1 !== p2) { toast('两次输入的密码不一致', true); return; }
            var btn = $('#pfPwdBtn');
            btn.disabled = true; btn.textContent = '更新中...';
            API.updateMe({ password: p1 }).then(function () {
                $('#pfNewPassword').value = '';
                $('#pfNewPassword2').value = '';
                toast('密码已更新');
                btn.disabled = false; btn.textContent = '更新密码';
            }).catch(function (err) {
                toast(err.message, true);
                btn.disabled = false; btn.textContent = '更新密码';
            });
        });
    }

    // ============================================================
    // 梅尔沃放置
    // ============================================================
    var melvorPollTimer = null;
    var patrolCountdownTimer = null;

    function clearMelvorPoll() {
        if (melvorPollTimer) { clearInterval(melvorPollTimer); melvorPollTimer = null; }
        if (patrolCountdownTimer) { clearInterval(patrolCountdownTimer); patrolCountdownTimer = null; }
    }

    function renderMelvor() {
        clearMelvorPoll();
        $('#contentArea').innerHTML = '' +
            '<div id="mv-running-warning" class="mv-warning hidden">⚠️ Agent 挂机中：浏览器为无头模式，<b>请勿在其它浏览器登录同一账号手动操作</b>，避免存档冲突覆盖。如需手动玩，请先点「■ 停止」。</div>' +
            '<div class="melvor-grid">' +
            '  <div class="melvor-left">' +
            '    <div class="panel"><div class="panel-header"><span class="panel-title">① 连接云账号</span><span class="panel-hint" id="mv-session"></span></div>' +
            '      <div class="panel-body">' +
            '        <div class="form-group"><label>账号</label><input id="mv-account" class="form-input" autocomplete="username"></div>' +
            '        <div class="form-group"><label>密码</label><input id="mv-password" type="password" class="form-input" autocomplete="current-password"></div>' +
            '        <button class="btn btn-primary" id="mv-login-btn">登录并读取角色</button>' +
            '        <div id="mv-characters" class="hidden mt">' +
            '          <div class="form-group"><label>选择角色（存档槽）</label><select id="mv-char-select" class="form-input"></select></div>' +
            '          <button class="btn btn-ghost" id="mv-select-btn">加载该角色</button>' +
            '        </div>' +
            '      </div>' +
            '    </div>' +
            '    <div class="panel"><div class="panel-header"><span class="panel-title">② 运行模式</span></div>' +
            '      <div class="panel-body">' +
            '        <div id="mv-modes" class="mode-list"></div>' +
            '        <div id="mv-script-editor" class="hidden mt">' +
            '          <div class="form-group"><label>脚本（JSON 动作列表，仅「用户脚本」模式）</label>' +
            '            <textarea id="mv-script" class="form-input mono" rows="8" spellcheck="false"></textarea></div>' +
            '          <button class="btn btn-ghost btn-sm" id="mv-script-save">保存脚本</button>' +
            '        </div>' +
            '        <div class="mt btn-row">' +
            '          <button class="btn btn-primary" id="mv-start-btn">▶ 启动</button>' +
            '          <button class="btn btn-ghost" id="mv-stop-btn">■ 停止</button>' +
            '          <button class="btn btn-ghost" id="mv-disconnect-btn">断开</button>' +
            '        </div>' +
            '      </div>' +
            '    </div>' +
            '    <div class="panel"><div class="panel-header"><span class="panel-title">③ 运行监控</span><span class="panel-hint">LLM token · 巡检间隔</span></div>' +
            '      <div class="panel-body">' +
            '        <div class="monitor-row"><span class="monitor-label">🔑 LLM</span><span class="monitor-value" id="mv-llm-state">-</span></div>' +
            '        <div class="monitor-row"><span class="monitor-label">📊 调用次数</span><span class="monitor-value" id="mv-llm-calls">0</span></div>' +
            '        <div class="monitor-row"><span class="monitor-label">📥 Prompt tokens</span><span class="monitor-value" id="mv-llm-prompt">0</span></div>' +
            '        <div class="monitor-row"><span class="monitor-label">📤 Completion tokens</span><span class="monitor-value" id="mv-llm-completion">0</span></div>' +
            '        <div class="monitor-row"><span class="monitor-label">Σ 总 tokens</span><span class="monitor-value" id="mv-llm-total">0</span></div>' +
            '        <div class="monitor-row"><span class="monitor-label">⏱ 下次巡检</span><span class="monitor-value" id="mv-next-patrol">-</span></div>' +
            '        <hr class="divider">' +
            '        <div class="form-group"><label>巡检间隔（秒，默认 3600=1小时，上限 86400=24小时）</label>' +
            '          <div class="patrol-row"><input type="number" id="mv-patrol-interval" class="form-input" min="5" max="86400" step="1">' +
            '          <button class="btn btn-ghost btn-sm" id="mv-patrol-btn">应用</button></div></div>' +
            '        <div class="form-group">' +
            '          <label class="checkbox-row"><input type="checkbox" id="mv-llm-schedules">' +
            '          <span>让 LLM 自主决定下次检查时间（依据动作完成/资源变化估计）</span></label>' +
            '        </div>' +
            '      </div>' +
            '    </div>' +
            '  </div>' +
            '  <div class="melvor-right">' +
            '    <div class="panel"><div class="panel-header"><span class="panel-title">④ 角色数据</span><span class="panel-hint" id="mv-mode-label"></span></div>' +
            '      <div class="panel-body" id="mv-data"><div class="empty">尚未连接角色</div></div>' +
            '    </div>' +
            '    <div class="panel"><div class="panel-header"><span class="panel-title">⑤ 攻略知识库 · 动作目录（RAG 方针）</span></div>' +
            '      <div class="panel-body" id="mv-guides"><div class="empty">加载中...</div></div>' +
            '    </div>' +
            '    <div class="panel"><div class="panel-header"><span class="panel-title">⑥ 账号检查文档</span></div>' +
            '      <div class="panel-body" id="mv-inspection"><div class="empty">首次 LLM 决策后自动生成</div></div>' +
            '    </div>' +
            '    <div class="panel"><div class="panel-header"><span class="panel-title">⑦ 建议对话框</span></div>' +
            '      <div class="panel-body">' +
            '        <textarea id="mv-feedback-input" class="form-input" rows="2" placeholder="对 LLM 的决策提出建议，例如：优先练钓鱼而非星象..."></textarea>' +
            '        <button class="btn btn-primary btn-sm mt" id="mv-feedback-btn">提交建议</button>' +
            '        <ul id="mv-feedback-list" class="log-list mt"></ul>' +
            '      </div>' +
            '    </div>' +
            '    <div class="panel"><div class="panel-header"><span class="panel-title">⑧ 事件与决策日志</span></div>' +
            '      <div class="panel-body log-two-col">' +
            '        <div><h4 class="form-section-title">事件</h4><ul id="mv-events" class="log-list"></ul></div>' +
            '        <div><h4 class="form-section-title">决策</h4><ul id="mv-decisions" class="log-list"></ul></div>' +
            '      </div>' +
            '    </div>' +
            '  </div>' +
            '</div>';

        loadMelvorModes();
        loadMelvorConfig();
        loadMelvorGuides();
        bindMelvor();
        refreshMelvor();
        melvorPollTimer = setInterval(refreshMelvor, 5000);
        patrolCountdownTimer = setInterval(updatePatrolCountdown, 1000);
    }

    function loadMelvorModes() {
        API.melvorModes().then(function (data) {
            var modes = data.modes || [];
            var html = '';
            modes.forEach(function (m) {
                html += '<label class="mode-card"><input type="radio" name="mv-mode" value="' + m.value + '">' +
                    '<div><div class="mode-card-title">' + escapeHtml(m.label) + '</div>' +
                    '<div class="mode-card-desc">' + escapeHtml(m.description) + '</div></div></label>';
            });
            $('#mv-modes').innerHTML = html;
            $$('input[name="mv-mode"]').forEach(function (r) {
                r.addEventListener('change', function () {
                    $('#mv-script-editor').classList.toggle('hidden', r.value !== 'manual');
                    syncModeCardSelected();
                });
            });
        });
    }

    function syncModeCardSelected() {
        $$('.mode-card').forEach(function (card) {
            var r = card.querySelector('input[type="radio"]');
            card.classList.toggle('selected', !!(r && r.checked));
        });
    }

    function loadMelvorConfig() {
        API.melvorConfig().then(function (data) {
            var c = data.config || {};
            if (c.account) $('#mv-account').value = c.account;
            if (c.mode) {
                var r = document.querySelector('input[name="mv-mode"][value="' + c.mode + '"]');
                if (r) { r.checked = true; $('#mv-script-editor').classList.toggle('hidden', c.mode !== 'manual'); }
            }
            syncModeCardSelected();
            var script = c.script || [];
            $('#mv-script').value = script.length ? JSON.stringify(script, null, 2) : defaultManualScript();
            if (c.character_index != null) {
                $('#mv-session').textContent = '已选角色 #' + c.character_index;
            }
            // 已保存云账号密码 → 自动登录并恢复挂机（全自动）
            if (c.has_password && c.account) {
                autoResume();
            }
        }).catch(function () {});
    }

    function autoResume() {
        API.melvorAutoResume().then(function (data) {
            var chars = data.characters || [];
            var sel = $('#mv-char-select');
            sel.innerHTML = chars.map(function (cc, i) { return '<option value="' + i + '">' + escapeHtml(cc.label || ('角色 ' + i)) + '</option>'; }).join('');
            $('#mv-characters').classList.remove('hidden');
            var msgs = [];
            if (data.login) msgs.push('已自动登录');
            if (data.select) msgs.push('已选角色');
            if (data.start) msgs.push('已启动挂机（' + (data.mode || '') + '）');
            toast(msgs.length ? msgs.join(' → ') : '已自动登录（未保存角色/模式，请手动选择）');
            refreshMelvor();
        }).catch(function (err) {
            toast('自动恢复失败：' + err.message, true);
        });
    }

    function loadMelvorGuides() {
        API.melvorGuides().then(function (data) {
            var guides = data.guides || [];
            var catalog = data.catalog;
            var html = '';
            guides.forEach(function (g) {
                html += '<div class="guide-item">' +
                    '<div class="guide-item-title">📖 ' + escapeHtml(g.title) + '</div>' +
                    '<div class="guide-item-meta">' + escapeHtml(g.file) + ' · ' + escapeHtml(g.chars) + ' 字' +
                    (g.source ? ' · ' + escapeHtml(g.source) : '') + '</div></div>';
            });
            if (catalog) {
                var skills = catalog.skills || [];
                html += '<h4 class="form-section-title">动态动作目录（' + skills.length + ' 技能 · ' +
                    catalog.areas + ' 区域 · ' + catalog.dungeons + ' 地牢 · ' +
                    catalog.slayerAreas + ' 屠杀 · ' + catalog.buildings + ' 建筑）</h4>';
                html += '<div class="catalog-chips">';
                skills.forEach(function (s) {
                    html += '<span class="catalog-chip">' + escapeHtml(s.name) + ' ' + (s.lv != null ? s.lv : '') +
                        ' <small>' + s.actions + ' 动作</small></span>';
                });
                html += '</div>';
            } else {
                html += '<h4 class="form-section-title">动态动作目录</h4>' +
                    '<div class="empty">尚未抓取（启动挂机后自动枚举）</div>';
            }
            $('#mv-guides').innerHTML = html;
        }).catch(function () {
            $('#mv-guides').innerHTML = '<div class="empty">加载失败</div>';
        });
    }

    function defaultManualScript() {
        return JSON.stringify([
            { 'action_type': 'operation', 'target': 'resume_astrology', 'reason': '恢复星象研究' },
            { 'action_type': 'operation', 'target': 'township_repair', 'reason': '城镇维护', 'interval': 3600 },
            { 'action_type': 'operation', 'target': 'farming_plant_harvest', 'reason': '农务收获补种', 'interval': 3600 },
            { 'action_type': 'operation', 'target': 'force_save', 'reason': '强制保存', 'interval': 600 }
        ], null, 2);
    }

    function refreshMelvor() {
        if (AppState.currentPage !== 'melvor') { clearMelvorPoll(); return; }
        API.melvorStatus().then(function (s) {
            $('#mv-session').textContent = sessionText(s.session_state);
            $('#mv-mode-label').textContent = (s.mode_label || '') + (s.character_label ? ' · ' + s.character_label : '');
            var warn = $('#mv-running-warning');
            if (warn) warn.classList.toggle('hidden', s.session_state !== 'running');
            renderMelvorData(s.game, s.session_state);
            renderMonitor(s);
        }).catch(function () {});
        API.melvorEvents().then(function (d) { renderMelvorLogs('#mv-events', d.events || [], 'event'); }).catch(function () {});
        API.melvorDecisions().then(function (d) { renderMelvorLogs('#mv-decisions', d.decisions || [], 'decision'); }).catch(function () {});
    }

    function renderMonitor(s) {
        updateSidebarStatus(s.session_state);
        var llm = s.llm || {};
        var u = llm.usage || {};
        var stateEl = $('#mv-llm-state');
        if (stateEl) stateEl.textContent = llm.configured ? ('已配置 · ' + (llm.model || '')) : '未配置';
        if ($('#mv-llm-calls')) $('#mv-llm-calls').textContent = fmtNum(u.calls);
        if ($('#mv-llm-prompt')) $('#mv-llm-prompt').textContent = fmtNum(u.prompt_tokens);
        if ($('#mv-llm-completion')) $('#mv-llm-completion').textContent = fmtNum(u.completion_tokens);
        if ($('#mv-llm-total')) $('#mv-llm-total').textContent = fmtNum(u.total_tokens);
        var intEl = $('#mv-patrol-interval');
        if (intEl && intEl !== document.activeElement) intEl.value = s.patrol_interval != null ? s.patrol_interval : '';
        var cb = $('#mv-llm-schedules');
        if (cb) cb.checked = !!s.llm_schedules;
        // 下次巡检倒计时
        AppState.nextPatrolAt = s.next_patrol_at != null ? Number(s.next_patrol_at) : null;
        updatePatrolCountdown();
        // 检查文档
        var insp = $('#mv-inspection');
        if (insp) {
            var doc = s.inspection_doc || '';
            insp.innerHTML = doc
                ? '<div class="inspection-doc">' + escapeHtml(doc).replace(/\n/g, '<br>') + '</div>'
                : '<div class="empty">首次 LLM 决策后自动生成</div>';
        }
        // 建议列表
        var fbList = $('#mv-feedback-list');
        if (fbList) {
            var fbs = s.user_feedback || [];
            fbList.innerHTML = fbs.length
                ? fbs.slice().reverse().map(function (f) {
                    return '<li class="log-item decision"><span class="log-time">' +
                        new Date(f.time * 1000).toLocaleTimeString() + '</span>' +
                        '<div class="log-content">' + escapeHtml(f.text) + '</div></li>';
                }).join('')
                : '<li class="empty">暂无建议</li>';
        }
    }

    function fmtNum(v) {
        var n = Number(v);
        if (isNaN(n)) return '0';
        if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
        if (n >= 1e4) return (n / 1e3).toFixed(1) + 'K';
        return n.toFixed(0);
    }

    function updatePatrolCountdown() {
        var el = $('#mv-next-patrol');
        if (!el) return;
        var at = AppState.nextPatrolAt;
        if (at == null) {
            el.textContent = '—';
            return;
        }
        var remain = Math.floor(at - Date.now() / 1000);
        if (remain <= 0) {
            el.textContent = '巡检中…';
            return;
        }
        var h = Math.floor(remain / 3600);
        var m = Math.floor((remain % 3600) / 60);
        var s = Math.floor(remain % 60);
        var pad = function (x) { return (x < 10 ? '0' : '') + x; };
        el.textContent = (h > 0 ? h + ':' + pad(m) + ':' : '') + pad(m) + ':' + pad(s);
    }

    function sessionText(s) {
        return { 'idle': '未连接', 'connected': '已连接', 'running': '运行中', 'error': '错误' }[s] || s || '';
    }

    function updateSidebarStatus(s) {
        var dot = $('#sidebarStatusDot');
        var txt = $('#sidebarStatusText');
        if (!dot || !txt) return;
        var cls = (s === 'running') ? 'running' : (s === 'connected') ? 'connected' : (s === 'error') ? 'error' : '';
        dot.className = 'status-dot' + (cls ? ' ' + cls : '');
        txt.textContent = 'Agent ' + (sessionText(s) || '未连接');
    }

    function statCard(label, value) { return '<div class="stat-card small"><div class="stat-label">' + label + '</div><div class="stat-value">' + escapeHtml(value) + '</div></div>'; }
    function panel(title, body) { return '<div class="panel"><div class="panel-header"><span class="panel-title">' + title + '</span></div><div class="panel-body"><ul class="kv-list">' + body + '</ul></div></div>'; }
    function kvRow(k, v) { return '<li><span class="kv-k">' + k + '</span><span class="kv-v">' + escapeHtml(v) + '</span></li>'; }
    function kvProgress(k, v, pct, barCls) {
        var cls = barCls ? ' ' + barCls : '';
        return '<li class="kv-progress"><span class="kv-k">' + k + '</span><span class="kv-v">' + escapeHtml(v) + '</span>' +
            '<div class="progress"><div class="progress-bar' + cls + '" style="width:' + (pct || 0) + '%"></div></div></li>';
    }
    function fmtCompact(v) {
        var n = Number(v);
        if (v == null || isNaN(n)) return '-';
        if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
        if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
        if (n >= 1e4) return (n / 1e3).toFixed(1) + 'K';
        return n.toFixed(0);
    }

    function renderMelvorData(game, sessionState) {
        var el = $('#mv-data');
        if (!game) { el.innerHTML = '<div class="empty"><div class="empty-icon">🎮</div>尚未连接角色</div>'; return; }
        var raw = game.raw_probe || {};
        var hp = game.hp || 0, maxHp = game.max_hp || 0;
        var combat = raw.combat || {};
        var skills = game.skills || {};
        var ts = raw.township || game.township || {};
        var fm = raw.farming || game.farming || {};
        var astro = raw.astrology || game.astrology || {};
        var sess = sessionState || 'idle';
        var hpPct = (maxHp > 0) ? Math.min(100, Math.round(hp / maxHp * 100)) : 0;
        var bankUsed = game.bank_used || 0, bankMax = game.bank_max || 0;
        var bankPct = (bankMax > 0) ? Math.min(100, Math.round(bankUsed / bankMax * 100)) : 0;
        var hpBarCls = hpPct <= 30 ? 'danger' : (hpPct <= 60 ? 'warning' : '');
        var bankBarCls = bankPct >= 90 ? 'warning' : '';

        var html = '';

        // ===== 概览 =====
        html += '<div class="mv-overview">';
        html += '<div class="mv-char"><div class="profile-avatar">' + escapeHtml((raw.characterName || '?').charAt(0).toUpperCase()) + '</div>';
        html += '<div><div class="profile-name">' + escapeHtml(raw.characterName || '未知角色') + ' ' +
            '<span class="status-pill ' + escapeHtml(sess) + '"><span class="status-dot ' + escapeHtml(sess) + '"></span>' + escapeHtml(sessionText(sess)) + '</span></div>';
        html += '<div class="profile-line">总等级 ' + (raw.totalLevel != null ? raw.totalLevel : '-') + ' · 战斗等级 ' + (game.combat_level != null ? game.combat_level : '-') + '</div></div></div>';
        html += '<div class="mv-stat-grid">';
        html += statCard('💰 金币', fmtCompact(game.gold));
        html += statCard('💀 屠杀币', fmtCompact(game.slayer_coins));
        html += statCard('🙏 祈祷点', fmtCompact(combat.prayerPoints));
        html += statCard('📦 仓库', fmt(game.bank_used) + ' / ' + fmt(game.bank_max));
        html += statCard('🧰 物品', fmt(raw.bank ? raw.bank.itemCount : null));
        html += statCard('🎯 当前动作', game.active_action || '空闲');
        html += '</div>';
        html += '<div class="bank-progress"><span class="bank-progress-label">📦 仓库容量 ' + fmt(game.bank_used) + ' / ' + fmt(game.bank_max) + '</span>' +
            '<div class="progress"><div class="progress-bar' + bankBarCls + '" style="width:' + bankPct + '%"></div></div></div>';
        html += '</div>';

        // ===== 战斗 =====
        html += panel('⚔ 战斗',
            kvProgress('生命', hp + ' / ' + maxHp + (combat.active ? '（战斗中）' : ''), hpPct, hpBarCls) +
            kvRow('食物', combat.food ? (combat.food.name + ' × ' + combat.food.qty) : '无') +
            kvRow('自动进食', combat.autoEatTier != null ? ('Tier ' + combat.autoEatTier + (combat.autoEatThreshold != null ? ' · 阈值 ' + combat.autoEatThreshold : '')) : '无') +
            kvRow('屠杀任务', combat.slayerTask ? (combat.slayerTask.monster + '（剩 ' + combat.slayerTask.killsLeft + '）') : '无') +
            kvRow('激活祈祷', (combat.activePrayers && combat.activePrayers.length) ? combat.activePrayers.join('、') : '无') +
            kvRow('装备', (raw.equipment && raw.equipment.length) ? raw.equipment.map(function (e) { return e.item; }).join(' · ') : '无')
        );

        // ===== 技能 =====
        var names = Object.keys(skills).sort(function (a, b) { return (skills[b].level || 0) - (skills[a].level || 0); });
        var skillHtml = '';
        names.forEach(function (k) {
            var sk = skills[k];
            skillHtml += '<div class="skill-card"><div class="skill-card-name">' + escapeHtml(sk.name || k) + '</div>' +
                '<div class="skill-card-lv">' + (sk.level || 0) + '</div>' +
                (sk.mastery != null ? '<div class="skill-card-m">精通 ' + sk.mastery + '%</div>' : '') + '</div>';
        });
        html += '<div class="panel"><div class="panel-header"><span class="panel-title">技能（' + names.length + '）</span></div><div class="panel-body"><div class="skill-grid">' + skillHtml + '</div></div></div>';

        // ===== 城镇 =====
        var tsRes = '';
        if (ts.resources && Object.keys(ts.resources).length) {
            tsRes = Object.keys(ts.resources).slice(0, 8).map(function (k) { return k + ' ' + fmtCompact(ts.resources[k]); }).join(' · ');
        }
        html += panel('🏘 城镇',
            kvRow('等级', ts.level != null ? ts.level : '-') +
            kvRow('健康', ts.health != null ? ts.health + '%' : '-') +
            kvRow('幸福', ts.happiness != null ? ts.happiness + '%' : '-') +
            kvRow('人口', ts.population != null ? fmt(ts.population) : '-') +
            kvRow('仓储', ts.storage != null ? fmtCompact(ts.storage) : '-') +
            kvRow('资源', tsRes || '无')
        );

        // ===== 农务 / 星象 =====
        html += panel('🌾 农务 / ✨ 星象',
            kvRow('农务等级', fm.level != null ? fm.level : '-') +
            kvRow('农务精通池', fm.pool != null ? fmtCompact(fm.pool) : '-') +
            kvRow('星象等级', astro.level != null ? astro.level : '-') +
            kvRow('研究星座', astro.studying || '无') +
            kvRow('星象精通池', astro.pool != null ? fmtCompact(astro.pool) : '-')
        );

        // ===== 召唤 / 灵巧 / 宠物 =====
        var sum = raw.summoning || {};
        var agi = raw.agility || {};
        var pets = raw.pets || {};
        html += panel('🧬 召唤 / 🤸 灵巧 / 🐾 宠物',
            kvRow('召唤印记', sum.marksDiscovered != null ? sum.marksDiscovered : '-') +
            kvRow('灵巧障碍', agi.obstaclesBuilt != null ? agi.obstaclesBuilt : '-') +
            kvRow('当前障碍', agi.activeObstacle || '无') +
            kvRow('宠物', (pets.unlocked != null ? pets.unlocked : '-') + ' / ' + (pets.total != null ? pets.total : '-'))
        );

        // ===== 药水 =====
        var pots = raw.potions || [];
        html += panel('🧪 激活药水', pots.length ? pots.map(function (p) { return p.item + (p.charges != null ? '（' + p.charges + ' 次）' : ''); }).join(' · ') : '无');

        el.innerHTML = html;
    }

    function renderMelvorLogs(sel, items, kind) {
        var el = $(sel);
        if (!el) return;
        if (!items.length) { el.innerHTML = '<li class="empty">暂无</li>'; return; }
        var html = '';
        items.forEach(function (it) {
            var time = new Date(it.timestamp * 1000).toLocaleTimeString();
            if (kind === 'event') {
                html += '<li class="log-item ' + (it.severity || 'info') + '"><span class="log-time">' + time + '</span>' +
                    '<div class="log-content"><strong>' + escapeHtml(it.event_type) + '</strong> ' +
                    escapeHtml(JSON.stringify(it.details || {})) + '</div></li>';
            } else {
                var acts = (it.actions || []).map(function (a) { return a.action_type + '→' + a.target; }).join(', ');
                html += '<li class="log-item decision"><span class="log-time">' + time + ' · ' + escapeHtml(it.mode || '') + '</span>' +
                    '<div class="log-content">' + escapeHtml(it.reason || '') + (acts ? ' <small>[' + escapeHtml(acts) + ']</small>' : '') + '</div></li>';
            }
        });
        el.innerHTML = html;
    }

    function bindMelvor() {
        $('#mv-login-btn').addEventListener('click', function () {
            var account = $('#mv-account').value.trim();
            var password = $('#mv-password').value;
            if (!account || !password) { toast('请输入账号和密码', true); return; }
            var btn = this; btn.disabled = true; btn.textContent = '登录中...';
            API.melvorLogin({ account: account, password: password }).then(function (data) {
                toast('登录成功');
                var chars = data.characters || [];
                var sel = $('#mv-char-select');
                sel.innerHTML = chars.map(function (c, i) { return '<option value="' + i + '">' + escapeHtml(c.label || ('角色 ' + i)) + '</option>'; }).join('');
                $('#mv-characters').classList.remove('hidden');
                refreshMelvor();
            }).catch(function (err) { toast(err.message, true); })
              .finally(function () { btn.disabled = false; btn.textContent = '登录并读取角色'; });
        });

        $('#mv-select-btn').addEventListener('click', function () {
            var index = parseInt($('#mv-char-select').value, 10);
            API.melvorSelect({ index: index }).then(function () { toast('角色已加载'); refreshMelvor(); })
              .catch(function (err) { toast(err.message, true); });
        });

        $('#mv-start-btn').addEventListener('click', function () {
            var mode = (document.querySelector('input[name="mv-mode"]:checked') || {}).value;
            if (!mode) { toast('请选择运行模式', true); return; }
            var payload = { mode: mode };
            if (mode === 'manual') {
                try { payload.script = JSON.parse($('#mv-script').value || '[]'); }
                catch (e) { toast('脚本 JSON 格式错误', true); return; }
            }
            API.melvorStart(payload).then(function () { toast('已启动'); refreshMelvor(); })
              .catch(function (err) { toast(err.message, true); });
        });

        $('#mv-stop-btn').addEventListener('click', function () {
            API.melvorStop().then(function () { toast('已停止'); refreshMelvor(); }).catch(function (err) { toast(err.message, true); });
        });

        $('#mv-disconnect-btn').addEventListener('click', function () {
            API.melvorDisconnect().then(function () { toast('已断开'); refreshMelvor(); }).catch(function (err) { toast(err.message, true); });
        });

        $('#mv-script-save').addEventListener('click', function () {
            var script;
            try { script = JSON.parse($('#mv-script').value || '[]'); }
            catch (e) { toast('脚本 JSON 格式错误', true); return; }
            API.melvorScript({ script: script }).then(function () { toast('脚本已保存'); }).catch(function (err) { toast(err.message, true); });
        });

        $('#mv-patrol-btn').addEventListener('click', function () {
            var v = parseFloat($('#mv-patrol-interval').value);
            if (isNaN(v) || v < 5) { toast('巡检间隔需 ≥ 5 秒', true); return; }
            API.melvorPatrol({ interval: v }).then(function (d) {
                toast('巡检间隔已设为 ' + d.interval + ' 秒');
            }).catch(function (err) { toast(err.message, true); });
        });

        $('#mv-llm-schedules').addEventListener('change', function () {
            var on = this.checked;
            API.melvorPatrol({ llm_schedules: on }).then(function () {
                toast(on ? '已开启：LLM 自主决定下次检查' : '已关闭：使用固定巡检间隔');
            }).catch(function (err) { toast(err.message, true); });
        });

        $('#mv-feedback-btn').addEventListener('click', function () {
            var text = $('#mv-feedback-input').value.trim();
            if (!text) { toast('请输入建议内容', true); return; }
            var btn = this; btn.disabled = true;
            API.melvorFeedback({ text: text }).then(function () {
                $('#mv-feedback-input').value = '';
                toast('建议已提交，将在下次 LLM 决策时参考');
                refreshMelvor();
            }).catch(function (err) { toast(err.message, true); })
              .finally(function () { btn.disabled = false; });
        });
    }

    // ============================================================
    // 初始化
    // ============================================================
    function initApp() {
        bindAuthForms();
        bindShell();

        // 无 token 也尝试 me()：本地版（DISABLE_AUTH）会返回本地用户，云端版会 401 走登录
        API.me().then(function (data) {
            AppState.user = data.user;
            showApp();
        }).catch(function () {
            clearAuth();
            showAuth();
        });
    }

    document.addEventListener('DOMContentLoaded', initApp);
})();
