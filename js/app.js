/**
 * IdleAgent — Web 控制台 (v0.5.0)
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
        currentPage: 'dashboard'
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
        getLogs: function (limit) { return API.request('GET', '/logs?limit=' + (limit || 100)); }
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
            profile: ['个人资料', '查看与编辑你的账户信息']
        };
        var t = titles[page] || titles.dashboard;
        $('#pageTitle').textContent = t[0];
        $('#pageSubtitle').textContent = t[1];
        if (page === 'profile') renderProfile();
        else renderDashboard();
    }

    // ============================================================
    // 仪表盘
    // ============================================================
    function renderDashboard() {
        $('#contentArea').innerHTML = '' +
            '<div class="dashboard-stats">' +
            '  <div class="stat-card"><div class="stat-label">💰 金币</div><div class="stat-value" id="v-gold">-</div></div>' +
            '  <div class="stat-card"><div class="stat-label">🪵 木头</div><div class="stat-value" id="v-wood">-</div></div>' +
            '  <div class="stat-card"><div class="stat-label">🪨 石头</div><div class="stat-value" id="v-stone">-</div></div>' +
            '  <div class="stat-card"><div class="stat-label">❤️ 生命值</div><div class="stat-value" id="v-hp">-</div></div>' +
            '  <div class="stat-card"><div class="stat-label">❤️ 最大生命</div><div class="stat-value" id="v-maxhp">-</div></div>' +
            '</div>' +
            '<div class="panel">' +
            '  <div class="panel-header"><span class="panel-title">决策日志</span>' +
            '    <span class="panel-hint" id="statusHint"></span></div>' +
            '  <div class="panel-body">' +
            '    <table class="logs-table">' +
            '      <thead><tr><th>时间</th><th>级别</th><th>模块</th><th>消息</th></tr></thead>' +
            '      <tbody id="logBody"></tbody>' +
            '    </table>' +
            '  </div>' +
            '</div>';
        loadDashboardData();
    }

    function loadDashboardData() {
        API.getStatus().then(function (status) {
            var r = status.resources || {};
            $('#v-gold').textContent = fmt(r.gold);
            $('#v-wood').textContent = fmt(r.wood);
            $('#v-stone').textContent = fmt(r.stone);
            var c = status.combat || {};
            $('#v-hp').textContent = fmt(c.hp);
            $('#v-maxhp').textContent = fmt(c.max_hp);
            $('#statusHint').textContent = (status.is_running ? '运行中' : '已停止') +
                (status.source ? ' · ' + (status.source === 'real' ? '真实数据' : '模拟数据') : '');
        }).catch(function () {});
        API.getLogs(100).then(function (data) {
            var logs = data.logs || [];
            var html = '';
            for (var i = 0; i < logs.length; i++) {
                var log = logs[i];
                var time = new Date(log.timestamp * 1000).toLocaleTimeString();
                var level = log.level || 'info';
                html += '<tr><td>' + time + '</td><td><span class="log-level ' + level + '">' +
                    level.toUpperCase() + '</span></td><td>' + escapeHtml(log.module || '') +
                    '</td><td>' + escapeHtml(log.message || '') + '</td></tr>';
            }
            $('#logBody').innerHTML = html || '<tr><td colspan="4" class="empty">暂无日志</td></tr>';
        }).catch(function () {});
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
    // 初始化
    // ============================================================
    function initApp() {
        bindAuthForms();
        bindShell();

        if (AppState.token) {
            API.me().then(function (data) {
                AppState.user = data.user;
                showApp();
            }).catch(function () {
                clearAuth();
                showAuth();
            });
        } else {
            showAuth();
        }
    }

    document.addEventListener('DOMContentLoaded', initApp);
})();
