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
        melvorDisconnect: function () { return API.request('POST', '/melvor/disconnect'); },
        melvorStatus: function () { return API.request('GET', '/melvor/status'); },
        melvorEvents: function () { return API.request('GET', '/melvor/events'); },
        melvorDecisions: function () { return API.request('GET', '/melvor/decisions'); },
        melvorGuides: function () { return API.request('GET', '/melvor/guides'); },
        melvorScript: function (p) { return API.request('POST', '/melvor/script', p); }
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
            profile: ['个人资料', '查看与编辑你的账户信息']
        };
        var t = titles[page] || titles.dashboard;
        $('#pageTitle').textContent = t[0];
        $('#pageSubtitle').textContent = t[1];
        if (page === 'melvor') renderMelvor();
        else if (page === 'profile') renderProfile();
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
    // 梅尔沃放置
    // ============================================================
    var melvorPollTimer = null;

    function clearMelvorPoll() {
        if (melvorPollTimer) { clearInterval(melvorPollTimer); melvorPollTimer = null; }
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
            '  </div>' +
            '  <div class="melvor-right">' +
            '    <div class="panel"><div class="panel-header"><span class="panel-title">③ 角色数据</span><span class="panel-hint" id="mv-mode-label"></span></div>' +
            '      <div class="panel-body" id="mv-data"><div class="empty">尚未连接角色</div></div>' +
            '    </div>' +
            '    <div class="panel"><div class="panel-header"><span class="panel-title">⑤ 攻略知识库 · 动作目录（RAG 方针）</span></div>' +
            '      <div class="panel-body" id="mv-guides"><div class="empty">加载中...</div></div>' +
            '    </div>' +
            '    <div class="panel"><div class="panel-header"><span class="panel-title">④ 事件与决策日志</span></div>' +
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
                });
            });
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
            renderMelvorData(s.game);
        }).catch(function () {});
        API.melvorEvents().then(function (d) { renderMelvorLogs('#mv-events', d.events || [], 'event'); }).catch(function () {});
        API.melvorDecisions().then(function (d) { renderMelvorLogs('#mv-decisions', d.decisions || [], 'decision'); }).catch(function () {});
    }

    function sessionText(s) {
        return { 'idle': '未连接', 'connected': '已连接', 'running': '运行中', 'error': '错误' }[s] || s || '';
    }

    function statCard(label, value) { return '<div class="stat-card small"><div class="stat-label">' + label + '</div><div class="stat-value">' + escapeHtml(value) + '</div></div>'; }
    function panel(title, body) { return '<div class="panel"><div class="panel-header"><span class="panel-title">' + title + '</span></div><div class="panel-body"><ul class="kv-list">' + body + '</ul></div></div>'; }
    function kvRow(k, v) { return '<li><span class="kv-k">' + k + '</span><span class="kv-v">' + escapeHtml(v) + '</span></li>'; }
    function fmtCompact(v) {
        var n = Number(v);
        if (v == null || isNaN(n)) return '-';
        if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
        if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
        if (n >= 1e4) return (n / 1e3).toFixed(1) + 'K';
        return n.toFixed(0);
    }

    function renderMelvorData(game) {
        var el = $('#mv-data');
        if (!game) { el.innerHTML = '<div class="empty">尚未连接角色</div>'; return; }
        var raw = game.raw_probe || {};
        var hp = game.hp || 0, maxHp = game.max_hp || 0;
        var combat = raw.combat || {};
        var skills = game.skills || {};
        var ts = raw.township || game.township || {};
        var fm = raw.farming || game.farming || {};
        var astro = raw.astrology || game.astrology || {};

        var html = '';

        // ===== 概览 =====
        html += '<div class="mv-overview">';
        html += '<div class="mv-char"><div class="profile-avatar">' + escapeHtml((raw.characterName || '?').charAt(0).toUpperCase()) + '</div>';
        html += '<div><div class="profile-name">' + escapeHtml(raw.characterName || '未知角色') + '</div>';
        html += '<div class="profile-line">总等级 ' + (raw.totalLevel != null ? raw.totalLevel : '-') + ' · 战斗等级 ' + (game.combat_level != null ? game.combat_level : '-') + '</div></div></div>';
        html += '<div class="mv-stat-grid">';
        html += statCard('💰 金币', fmtCompact(game.gold));
        html += statCard('💀 屠杀币', fmtCompact(game.slayer_coins));
        html += statCard('🙏 祈祷点', fmtCompact(combat.prayerPoints));
        html += statCard('📦 仓库', fmt(game.bank_used) + ' / ' + fmt(game.bank_max));
        html += statCard('🧰 物品', fmt(raw.bank ? raw.bank.itemCount : null));
        html += statCard('🎯 当前动作', game.active_action || '空闲');
        html += '</div></div>';

        // ===== 战斗 =====
        html += panel('⚔ 战斗',
            kvRow('生命', hp + ' / ' + maxHp + (combat.active ? '（战斗中）' : '')) +
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
