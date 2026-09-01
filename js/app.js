// IdleAgent Dashboard App v0.2.0
const App={
currentPage:'dashboard',games:[{
id:1,name:'Melvor Idle',url:'melvoridle.com',adapter:'melvor',status:'running',uptime:'72h 14m',progress:12.4,lastAction:'训练伐木技能',actionsToday:1247}
,{
id:2,name:'Clicker Heroes',url:'clickerheroes.com',adapter:'clicker',status:'paused',uptime:'0h 0m',progress:3.1,lastAction:'升级英雄',actionsToday:0}
],logs:[{
time:'12:24:18',level:'decision',game:'Melvor Idle',message:'诊断完成：当前瓶颈为<b>钓鱼技能Lv.45</b>，建议优先突破'}
,{
time:'12:24:15',level:'action',game:'Melvor Idle',message:'执行操作：切换到钓鱼训练，预计耗时2小时'}
,{
time:'12:24:12',level:'info',game:'Melvor Idle',message:'状态盘点：技能平均等级38.2，完成度12.4%'}
,{
time:'12:18:05',level:'warning',game:'Melvor Idle',message:'仓库空间紧张：剩余3格，触发自动出售规则'}
,{
time:'12:18:02',level:'action',game:'Melvor Idle',message:'出售普通木材x247，获得金币12,400'}
,{
time:'12:10:00',level:'decision',game:'Melvor Idle',message:'规划更新：短期目标调整为钓鱼Lv.50 → 中期目标解锁深海区域'}
,{
time:'11:45:33',level:'info',game:'Melvor Idle',message:'每小时巡检：角色状态正常，无安全威胁'}
,{
time:'11:30:15',level:'action',game:'Melvor Idle',message:'装备升级：钢钓竿 → 金钓竿，钓鱼效率+15%'}
,{
time:'11:15:00',level:'decision',game:'Melvor Idle',message:'学习社区攻略：发现更优训练路线，更新规划策略'}
,{
time:'10:00:00',level:'info',game:'Melvor Idle',message:'Agent启动：全自动模式，安全约束已激活'}
,{
time:'09:45:22',level:'error',game:'Clicker Heroes',message:'连接超时：无法访问游戏页面，请检查网络'}
,{
time:'09:30:00',level:'info',game:'Clickle Heroes',message:'Agent启动尝试：适配器加载失败，已暂停'}
],rulesFiles:[{
name:'_base.yaml',active:true,content:'# 通用挂机游戏Agent基础规则框架# 所有游戏共享的默认配置，可被具体游戏规则覆盖safety:  hard_constraints:    - type: health_check      condition: hp < threshold      action: pause_all      description: 生命值过低时暂停所有危险操作  soft_constraints:    - type: resource_cap      action: sell_excess      description: 资源达到上限时自动出售低价值物品resources:  keep_always: []  # 永远保留的物品列表  sell_when_excess: []  # 超出阈值时出售  sell_for_investment: true  # 出售换取投资资金priorities:  short_term: []  # 1小时内目标  mid_term: []  # 1天内目标  long_term: []  # 总体目标schedule:  diagnosis_interval: 1h  decision_interval: 10min  emergency_check: 30s'}
,{
name:'melvor_idle.yaml',active:false,content:'# Melvor Idle 专用规则game: Melvor Idleversion: 1.3safety:  hard_constraints:    - condition: hp < 20%      action: stop_combat      description: 角色HP低于20%时停止战斗    - condition: food < 10      action: emergency_fish      description: 食物存量低于10时紧急钓鱼  soft_constraints:    - condition: bank_space < 5      action: pause_gathering      description: 仓库空间不足时暂停采集resources:  keep_always:    - 宝石    - 稀有装备    - 任务物品    - 宠物  sell_when_excess:    - item: 普通木材      threshold: 500    - item: 铜矿石      threshold: 1000    - item: 普通鱼类      threshold: 200  sell_for_investment: truepriorities:  short_term:    - 突破当前技能瓶颈    - 完成进行中的城镇任务  mid_term:    - 解锁下一区域    - 收集关键宠物  long_term:    - 100%完成度equipment:  synthesis_paths:    - name: 龙装备线      stages: [铜装备, 铁装备, 钢装备, 龙装备]      keep_intermediate: trueschedule:  diagnosis_interval: 1h  decision_interval: 10min  emergency_check: 30s'}
,{
name:'clicker_heroes.yaml',active:false,content:'# Clicker Heroes 专用规则game: Clicker Heroesversion: 1.0safety:  hard_constraints:    - condition: auto_save_failed      action: pause_and_alert      description: 自动存档失败时暂停并告警  soft_constraints:    - condition: gold_per_second < 1%_max      action: suggest_ascend      description: 金币获取速度低于历史最高1%时建议转生resources:  keep_always: []  sell_when_excess: []  sell_for_investment: falsepriorities:  short_term:    - 升级最高DPS英雄    - 购买可用升级  mid_term:    - 达到转生阈值    - 解锁新英雄  long_term:    - 最高层数突破schedule:  diagnosis_interval: 30min  decision_interval: 5min  emergency_check: 60s'}
],logFilter:'全部',ruleTab:'编辑',settings:{
model:'DeepSeek-V3',apiKey:'sk-******************************',temperature:0.3,diagnosisInterval:'1h',decisionInterval:'10min',emergencyCheck:'30s',notifyDeath:true,notifyDaily:true,notifyStrategy:false,notifyError:true}
,init(){
this.bindEvents();
this.renderPage();
this.startLiveSimulation()}
,bindEvents(){
document.querySelectorAll('.nav-item').forEach(el=>{
el.addEventListener('click',e=>{
e.preventDefault();
this.switchPage(el.dataset.page)}
)}
);
document.getElementById('addGameBtn').addEventListener('click',()=>this.showModal());
document.getElementById('cancelAddGame').addEventListener('click',()=>this.hideModal());
document.querySelector('.modal-close').addEventListener('click',()=>this.hideModal());
document.querySelector('.modal-backdrop').addEventListener('click',()=>this.hideModal());
document.getElementById('confirmAddGame').addEventListener('click',()=>this.addGame());
document.getElementById('refreshBtn').addEventListener('click',()=>this.refreshData())}
,switchPage(page){
this.currentPage=page;
document.querySelectorAll('.nav-item').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
const titles={
dashboard:'仪表盘',games:'游戏管理',rules:'规则配置',logs:'决策日志',analytics:'数据分析',settings:'系统设置'}
;
const subtitles={
dashboard:'实时监控所有游戏Agent的运行状态',games:'管理已接入的挂机游戏',rules:'配置各游戏的决策规则',logs:'查看Agent的完整决策与执行记录',analytics:'分析Agent运行效率与策略效果',settings:'系统参数与全局配置'}
;
document.querySelector('.page-title').textContent=titles[page];
document.querySelector('.page-subtitle').textContent=subtitles[page];
this.renderPage()}
,renderPage(){
const content=
document.getElementById('contentArea');
content.innerHTML='';
switch(
this.currentPage){
case'dashboard':
this.renderDashboard(content);
break;
case'games':
this.renderGames(content);
break;
case'rules':
this.renderRules(content);
break;
case'logs':
this.renderLogs(content);
break;
case'analytics':
this.renderAnalytics(content);
break;
case'settings':
this.renderSettings(content);
break}
}
,renderDashboard(container){
const runningGames=
this.games.filter(g=>g.status==='running').length;
const totalActions=
this.games.reduce((sum,g)=>sum+g.actionsToday,0);
const avgProgress=(
this.games.reduce((sum,g)=>sum+g.progress,0)/
this.games.length).toFixed(1);
container.innerHTML=`<div class=dashboard-grid><div class=stat-card><div class=stat-label>运行中游戏</div><div class='stat-value success' id=statRunning>${
runningGames}
<span style='font-size:14px;
color:var(--text-muted);
font-weight:400;
'> / ${
this.games.length}
</span></div><div class=stat-change>+1 较昨日</div></div><div class=stat-card><div class=stat-label>今日操作数</div><div class='stat-value primary' id=statActions>${
totalActions.toLocaleString()}
</div><div class=stat-change>+342 较昨日</div></div><div class=stat-card><div class=stat-label>平均完成度</div><div class='stat-value warning' id=statProgress>${
avgProgress}
%</div><div class=stat-change>+0.8% 较昨日</div></div><div class=stat-card><div class=stat-label>运行时长</div><div class=stat-value id=statUptime>72h</div><div class=stat-change>连续运行无中断</div></div></div><div class=dashboard-row><div class=panel><div class=panel-header><span class=panel-title>游戏实例</span><span style='font-size:12px;
color:var(--text-muted)'>${
this.games.length}
 个游戏</span></div><div class=panel-body><div class=game-list>${
this.games.map(g=>`<div class='game-item ${
g.status==='running'?'active':''}
' data-game-id=${
g.id}
><div class=game-icon style='background:linear-gradient(135deg,#00d4aa20,#0ea5e920)'>${
g.name.charAt(0)}
</div><div class=game-info><div class=game-name>${
g.name}
</div><div class=game-meta>${
g.adapter}
 · 完成度 ${
g.progress.toFixed(1)}
% · ${
g.lastAction}
</div></div><div class='game-status ${
g.status}
'>${
g.status==='running'?'运行中':g.status==='paused'?'已暂停':'异常'}
</div></div>`).join('')}
</div></div></div><div class=panel><div class=panel-header><span class=panel-title>最近决策</span><a href=# class='btn btn-sm btn-ghost' data-page=logs onclick='
App.switchPage(&quot;
logs&quot;
);
return false;
'>查看全部</a></div><div class=panel-body><div class=log-list>${
this.logs.slice(0,6).map(l=>`<div class='log-item ${
l.level}
'><div class=log-time>${
l.time}
</div><div class=log-content>[${
l.game}
] ${
l.message}
</div></div>`).join('')}
</div></div></div></div>`;
container.querySelectorAll('.game-item').forEach(el=>{
el.addEventListener('click',()=>{
const id=parseInt(el.dataset.gameId);
const game=
this.games.find(g=>g.id===id);
if(game){
this.switchPage('games');
setTimeout(()=>this.showGameDetail(game),100)}
}
)}
)}
,renderGames(container){
container.innerHTML=`<div class=games-grid>${
this.games.map(g=>`<div class=game-card data-game-id=${
g.id}
><div class=game-card-header><div class=game-icon style='width:48px;
height:48px;
font-size:22px;
background:linear-gradient(135deg,#00d4aa20,#0ea5e920)'>${
g.name.charAt(0)}
</div><div style='flex:1'><div style='font-size:16px;
font-weight:600'>${
g.name}
</div><div style='font-size:12px;
color:var(--text-muted);
margin-top:2px'>${
g.url}
</div></div><div class='game-status ${
g.status}
' style='padding:4px 12px'>${
g.status==='running'?'运行中':g.status==='paused'?'已暂停':'异常'}
</div></div><div class=game-card-body><div class=game-stats><div class=game-stat><div class='game-stat-value ${
g.status==='running'?'success':'muted'}
' id=progress-${
g.id}
>${
g.progress.toFixed(1)}
%</div><div class=game-stat-label>完成度</div></div><div class=game-stat><div class=game-stat-value id=uptime-${
g.id}
>${
g.uptime}
</div><div class=game-stat-label>运行时长</div></div><div class=game-stat><div class=game-stat-value id=actions-${
g.id}
>${
g.actionsToday.toLocaleString()}
</div><div class=game-stat-label>今日操作</div></div></div><div style='margin-top:12px;
font-size:12px;
color:var(--text-muted)'>适配器: <span style='color:var(--text-secondary)'>${
g.adapter}
</span></div><div style='margin-top:4px;
font-size:12px;
color:var(--text-muted)'>最近操作: <span style='color:var(--text-secondary)'>${
g.lastAction}
</span></div></div><div class=game-card-footer><button class='btn btn-sm btn-ghost btn-view-logs' data-game='${
g.name}
'>查看日志</button><button class='btn btn-sm btn-ghost btn-edit-rules' data-game='${
g.name}
'>编辑规则</button><button class='btn btn-sm ${
g.status==='running'?'btn-danger':'btn-primary'}
 btn-toggle-status' data-game-id=${
g.id}
>${
g.status==='running'?'停止':'启动'}
</button></div></div>`).join('')}
</div>`;
container.querySelectorAll('.btn-view-logs').forEach(btn=>{
btn.addEventListener('click',e=>{
e.stopPropagation();
this.viewGameLogs(btn.dataset.game)}
)}
);
container.querySelectorAll('.btn-edit-rules').forEach(btn=>{
btn.addEventListener('click',e=>{
e.stopPropagation();
this.editGameRules(btn.dataset.game)}
)}
);
container.querySelectorAll('.btn-toggle-status').forEach(btn=>{
btn.addEventListener('click',e=>{
e.stopPropagation();
this.toggleGameStatus(parseInt(btn.dataset.gameId))}
)}
)}
,renderRules(container){
const activeFile=
this.rulesFiles.find(f=>f.active);
const yamlContent=activeFile?activeFile.content:'';
let editorContent='';
if(
this.ruleTab==='编辑'){
editorContent=`<textarea class=code-editor spellcheck=false id=ruleEditor>${
yamlContent}
</textarea>`}
else 
if(
this.ruleTab==='预览'){
editorContent=`<div class=code-editor style='white-space:pre-wrap;
overflow:auto'>${
this.highlightYaml(yamlContent)}
</div>`}
else{
editorContent=`<div class=code-editor style='white-space:pre-wrap;
overflow:auto;
color:var(--text-muted)'># 修改历史（模拟数据）2026-09-01 12:00  创建初始规则文件2026-09-01 10:30  调整分块策略参数2026-09-01 09:15  添加安全约束规则</div>`}
container.innerHTML=`<div class=rules-editor><div class=rules-sidebar><div class=rules-sidebar-header>规则文件</div><div class=rules-file-list>${
this.rulesFiles.map((f,i)=>`<div class='rules-file-item ${
f.active?'active':''}
' data-index=${
i}
>${
f.name}
</div>`).join('')}
</div></div><div class=rules-editor-main><div class=rules-editor-header><div class=rules-editor-tabs><div class='editor-tab ${
this.ruleTab==='编辑'?'active':''}
' data-tab=编辑>编辑</div><div class='editor-tab ${
this.ruleTab==='预览'?'active':''}
' data-tab=预览>预览</div><div class='editor-tab ${
this.ruleTab==='历史'?'active':''}
' data-tab=历史>历史</div></div><div style='display:flex;
gap:8px'><button class='btn btn-sm btn-ghost' id=btnResetRules>重置</button><button class='btn btn-sm btn-primary' id=btnSaveRules>保存</button></div></div>${
editorContent}
</div></div>`;
container.querySelectorAll('.rules-file-item').forEach(el=>{
el.addEventListener('click',()=>{
const idx=parseInt(el.dataset.index);
this.rulesFiles.forEach((f,i)=>f.active=i===idx);
this.renderRules(container)}
)}
);
container.querySelectorAll('.editor-tab').forEach(el=>{
el.addEventListener('click',()=>{
this.ruleTab=el.dataset.tab;
this.renderRules(container)}
)}
);
const saveBtn=
document.getElementById('btnSaveRules');
if(saveBtn)saveBtn.addEventListener('click',()=>this.saveRules());
const resetBtn=
document.getElementById('btnResetRules');
if(resetBtn)resetBtn.addEventListener('click',()=>this.resetRules())}
,renderLogs(container){
const filteredLogs=
this.logFilter==='全部'?
this.logs:
this.logs.filter(l=>{
const map={
'决策':'decision','执行':'action','信息':'info','警告':'warning','错误':'error'}
;
return l.level===map[
this.logFilter]}
);
const filters=['全部','决策','执行','信息','警告','错误'];
container.innerHTML=`<div class=logs-filter>${
filters.map(f=>`<div class='filter-chip ${
this.logFilter===f?'active':''}
' data-filter='${
f}
'>${
f}
</div>`).join('')}
</div><table class=logs-table><thead><tr><th>时间</th><th>级别</th><th>游戏</th><th>内容</th></tr></thead><tbody>${
filteredLogs.map(l=>`<tr><td style='font-family:var(--font-mono);
font-size:12px;
color:var(--text-muted)'>${
l.time}
</td><td><span class='log-level-badge level-${
l.level}
'>${
l.level}
</span></td><td>${
l.game}
</td><td>${
l.message}
</td></tr>`).join('')}
</tbody></table>`;
container.querySelectorAll('.filter-chip').forEach(el=>{
el.addEventListener('click',()=>{
this.logFilter=el.dataset.filter;
this.renderLogs(container)}
)}
)}
,renderAnalytics(container){
container.innerHTML=`<div class=dashboard-grid><div class=stat-card><div class=stat-label>决策准确率</div><div class='stat-value success'>94.2%</div><div class=stat-change>基于过去1000次决策</div></div><div class=stat-card><div class=stat-label>平均响应时间</div><div class='stat-value primary'>1.8s</div><div class=stat-change>从诊断到执行</div></div><div class=stat-card><div class=stat-label>策略迭代次数</div><div class='stat-value warning'>23</div><div class=stat-change>通过学习社区攻略</div></div><div class=stat-card><div class=stat-label>人工干预次数</div><div class=stat-value>0</div><div class=stat-change>72小时内零干预</div></div></div><div class=dashboard-row><div class=panel><div class=panel-header><span class=panel-title>完成度趋势</span></div><div class=panel-body><div class=chart-placeholder>图表区域 - 将接入 Chart.js 实时数据</div></div></div><div class=panel><div class=panel-header><span class=panel-title>决策分布</span></div><div class=panel-body><div class=chart-placeholder>图表区域 - 将接入 Chart.js 实时数据</div></div></div></div><div class=panel style='margin-top:16px'><div class=panel-header><span class=panel-title>策略效果对比</span></div><div class=panel-body><div class=chart-placeholder style='height:240px'>图表区域 - 将接入 Chart.js 实时数据</div></div></div>`}
,renderSettings(container){
container.innerHTML=`<div style='max-width:640px'><div class=panel style='margin-bottom:16px'><div class=panel-header><span class=panel-title>LLM配置</span></div><div class=panel-body style='display:flex;
flex-direction:column;
gap:16px'><div class=form-group><label>默认模型</label><select class=form-select id=settingModel><option ${
this.settings.model==='DeepSeek-V3'?'selected':''}
>DeepSeek-V3</option><option ${
this.settings.model==='DeepSeek-R1'?'selected':''}
>DeepSeek-R1</option><option ${
this.settings.model==='GPT-4o'?'selected':''}
>GPT-4o</option><option ${
this.settings.model==='Claude 3.5 Sonnet'?'selected':''}
>Claude 3.5 Sonnet</option></select></div><div class=form-group><label>API Key</label><input type=password class=form-input id=settingApiKey value='${
this.settings.apiKey}
' placeholder='输入你的API Key'></div><div class=form-group><label>温度参数</label><input type=range class=form-input id=settingTemp min=0 max=1 step=0.1 value='${
this.settings.temperature}
' style='padding:0'><div style='display:flex;
justify-content:space-between;
font-size:12px;
color:var(--text-muted);
margin-top:4px'><span>精确</span><span id=tempValue>${
this.settings.temperature}
</span><span>创意</span></div></div></div></div><div class=panel style='margin-bottom:16px'><div class=panel-header><span class=panel-title>全局调度</span></div><div class=panel-body style='display:flex;
flex-direction:column;
gap:16px'><div class=form-group><label>诊断间隔</label><select class=form-select id=settingDiag><option ${
this.settings.diagnosisInterval==='30min'?'selected':''}
>30分钟</option><option ${
this.settings.diagnosisInterval==='1h'?'selected':''}
>1小时</option><option ${
this.settings.diagnosisInterval==='2h'?'selected':''}
>2小时</option><option ${
this.settings.diagnosisInterval==='6h'?'selected':''}
>6小时</option></select></div><div class=form-group><label>决策间隔</label><select class=form-select id=settingDecision><option ${
this.settings.decisionInterval==='5min'?'selected':''}
>5分钟</option><option ${
this.settings.decisionInterval==='10min'?'selected':''}
>10分钟</option><option ${
this.settings.decisionInterval==='30min'?'selected':''}
>30分钟</option><option ${
this.settings.decisionInterval==='1h'?'selected':''}
>1小时</option></select></div><div class=form-group><label>紧急检查间隔</label><select class=form-select id=settingEmergency><option ${
this.settings.emergencyCheck==='10s'?'selected':''}
>10秒</option><option ${
this.settings.emergencyCheck==='30s'?'selected':''}
>30秒</option><option ${
this.settings.emergencyCheck==='1min'?'selected':''}
>1分钟</option><option ${
this.settings.emergencyCheck==='5min'?'selected':''}
>5分钟</option></select></div></div></div><div class=panel><div class=panel-header><span class=panel-title>通知设置</span></div><div class=panel-body style='display:flex;
flex-direction:column;
gap:12px'><label class=radio-label style='color:var(--text-secondary)'><input type=checkbox id=notifyDeath ${
this.settings.notifyDeath?'checked':''}
> 角色死亡时立即通知</label><label class=radio-label style='color:var(--text-secondary)'><input type=checkbox id=notifyDaily ${
this.settings.notifyDaily?'checked':''}
> 每日运行报告</label><label class=radio-label style='color:var(--text-secondary)'><input type=checkbox id=notifyStrategy ${
this.settings.notifyStrategy?'checked':''}
> 策略自动更新时通知</label><label class=radio-label style='color:var(--text-secondary)'><input type=checkbox id=notifyError ${
this.settings.notifyError?'checked':''}
> 异常状态时通知</label></div></div><div style='margin-top:20px;
display:flex;
gap:10px;
justify-content:flex-end'><button class='btn btn-ghost' id=btnResetSettings>恢复默认</button><button class='btn btn-primary' id=btnSaveSettings>保存设置</button></div></div>`;
const tempSlider=
document.getElementById('settingTemp');
if(tempSlider){
tempSlider.addEventListener('input',()=>{
document.getElementById('tempValue').textContent=tempSlider.value}
)}
document.getElementById('btnSaveSettings').addEventListener('click',()=>this.saveSettings());
document.getElementById('btnResetSettings').addEventListener('click',()=>this.resetSettings())}
,showModal(){
document.getElementById('addGameModal').classList.add('show')}
,hideModal(){
document.getElementById('addGameModal').classList.remove('show')}
,addGame(){
const nameInput=
document.querySelector('#addGameModal input[type=text]');
const urlInput=
document.querySelectorAll('#addGameModal input[type=text]')[1];
const adapterSelect=
document.querySelector('#addGameModal select');
const name=nameInput?nameInput.value:'';
const url=urlInput?urlInput.value:'';
const adapter=adapterSelect?adapterSelect.value:'custom';
if(!name||!url){
this.showToast('请填写游戏名称和URL','error');
return}
const newGame={
id:
this.games.length+1,name,url,adapter,status:'paused',uptime:'0h 0m',progress:0,lastAction:'等待启动',actionsToday:0}
;
this.games.push(newGame);
this.hideModal();
if(nameInput)nameInput.value='';
if(urlInput)urlInput.value='';
this.renderPage();
this.updateBadge();
this.showToast(`游戏「${
name}
」添加成功`,'success')}
,updateBadge(){
const gameBadge=
document.querySelector('.nav-item[data-page=games] .badge');
if(gameBadge)gameBadge.textContent=
this.games.length}
,refreshData(){
const btn=
document.getElementById('refreshBtn');
btn.textContent='刷新中...';
setTimeout(()=>{
const runningGame=
this.games.find(g=>g.status==='running');
if(runningGame){
runningGame.actionsToday+=Math.floor(Math.random()*15)+5;
runningGame.progress=Math.min(100,runningGame.progress+0.02);
runningGame.lastAction=['训练技能','出售资源','装备升级','切换区域','学习攻略'][Math.floor(Math.random()*5)];
const now=new Date();
const h=String(now.getHours()).padStart(2,'0');
const m=String(now.getMinutes()).padStart(2,'0');
const s=String(now.getSeconds()).padStart(2,'0');
this.logs.unshift({
time:`${
h}
:${
m}
:${
s}
`,level:'action',game:runningGame.name,message:`${
runningGame.lastAction}
 - 完成度 ${
runningGame.progress.toFixed(1)}
%`}
)}
btn.textContent='刷新';
this.renderPage();
this.showToast('数据已刷新','success')}
,800)}
,toggleGameStatus(gameId){
const game=
this.games.find(g=>g.id===gameId);
if(!game)return;
game.status=game.status==='running'?'paused':'running';
if(game.status==='running'){
game.lastAction='Agent已启动';
const now=new Date();
const h=String(now.getHours()).padStart(2,'0');
const m=String(now.getMinutes()).padStart(2,'0');
const s=String(now.getSeconds()).padStart(2,'0');
this.logs.unshift({
time:`${
h}
:${
m}
:${
s}
`,level:'info',game:game.name,message:'Agent启动：全自动模式，安全约束已激活'}
)}
else{
game.lastAction='Agent已停止';
const now=new Date();
const h=String(now.getHours()).padStart(2,'0');
const m=String(now.getMinutes()).padStart(2,'0');
const s=String(now.getSeconds()).padStart(2,'0');
this.logs.unshift({
time:`${
h}
:${
m}
:${
s}
`,level:'warning',game:game.name,message:'Agent已手动停止'}
)}
this.renderPage();
this.showToast(`「${
game.name}
」已${
game.status==='running'?'启动':'停止'}
`,game.status==='running'?'success':'warning')}
,viewGameLogs(gameName){
this.logFilter='全部';
this.switchPage('logs');
setTimeout(()=>{
this.logFilter='全部';
const logContainer=
document.getElementById('contentArea');
if(logContainer)
this.renderLogs(logContainer);
this.showToast(`已筛选「${
gameName}
」的日志`,'info')}
,100)}
,editGameRules(gameName){
const ruleMap={
'Melvor Idle':'melvor_idle.yaml','Clicker Heroes':'clicker_heroes.yaml'}
;
const targetFile=ruleMap[gameName]||'_base.yaml';
this.rulesFiles.forEach(f=>f.active=f.name===targetFile);
this.ruleTab='编辑';
this.switchPage('rules');
this.showToast(`已加载「${
gameName}
」的规则配置`,'info')}
,saveRules(){
const editor=
document.getElementById('ruleEditor');
if(!editor)return;
const activeFile=
this.rulesFiles.find(f=>f.active);
if(activeFile){
activeFile.content=editor.value;
this.showToast(`规则文件「${
activeFile.name}
」已保存`,'success')}
}
,resetRules(){
const activeFile=
this.rulesFiles.find(f=>f.active);
if(!activeFile)return;
if(confirm(`确定要重置「${
activeFile.name}
」到默认内容吗？`)){
const defaults={
'_base.yaml':'# 通用挂机游戏Agent基础规则框架# 所有游戏共享的默认配置，可被具体游戏规则覆盖safety:  hard_constraints:    - type: health_check      condition: hp < threshold      action: pause_all      description: 生命值过低时暂停所有危险操作  soft_constraints:    - type: resource_cap      action: sell_excess      description: 资源达到上限时自动出售低价值物品resources:  keep_always: []  # 永远保留的物品列表  sell_when_excess: []  # 超出阈值时出售  sell_for_investment: true  # 出售换取投资资金priorities:  short_term: []  # 1小时内目标  mid_term: []  # 1天内目标  long_term: []  # 总体目标schedule:  diagnosis_interval: 1h  decision_interval: 10min  emergency_check: 30s','melvor_idle.yaml':'# Melvor Idle 专用规则game: Melvor Idleversion: 1.3safety:  hard_constraints:    - condition: hp < 20%      action: stop_combat      description: 角色HP低于20%时停止战斗    - condition: food < 10      action: emergency_fish      description: 食物存量低于10时紧急钓鱼  soft_constraints:    - condition: bank_space < 5      action: pause_gathering      description: 仓库空间不足时暂停采集resources:  keep_always:    - 宝石    - 稀有装备    - 任务物品    - 宠物  sell_when_excess:    - item: 普通木材      threshold: 500    - item: 铜矿石      threshold: 1000    - item: 普通鱼类      threshold: 200  sell_for_investment: truepriorities:  short_term:    - 突破当前技能瓶颈    - 完成进行中的城镇任务  mid_term:    - 解锁下一区域    - 收集关键宠物  long_term:    - 100%完成度equipment:  synthesis_paths:    - name: 龙装备线      stages: [铜装备, 铁装备, 钢装备, 龙装备]      keep_intermediate: trueschedule:  diagnosis_interval: 1h  decision_interval: 10min  emergency_check: 30s','clicker_heroes.yaml':'# Clicker Heroes 专用规则game: Clicker Heroesversion: 1.0safety:  hard_constraints:    - condition: auto_save_failed      action: pause_and_alert      description: 自动存档失败时暂停并告警  soft_constraints:    - condition: gold_per_second < 1%_max      action: suggest_ascend      description: 金币获取速度低于历史最高1%时建议转生resources:  keep_always: []  sell_when_excess: []  sell_for_investment: falsepriorities:  short_term:    - 升级最高DPS英雄    - 购买可用升级  mid_term:    - 达到转生阈值    - 解锁新英雄  long_term:    - 最高层数突破schedule:  diagnosis_interval: 30min  decision_interval: 5min  emergency_check: 60s'}
;
activeFile.content=defaults[activeFile.name]||activeFile.content;
this.renderPage();
this.showToast(`「${
activeFile.name}
」已重置`,'success')}
}
,saveSettings(){
this.settings.model=
document.getElementById('settingModel').value;
this.settings.apiKey=
document.getElementById('settingApiKey').value;
this.settings.temperature=parseFloat(
document.getElementById('settingTemp').value);
this.settings.diagnosisInterval=
document.getElementById('settingDiag').value;
this.settings.decisionInterval=
document.getElementById('settingDecision').value;
this.settings.emergencyCheck=
document.getElementById('settingEmergency').value;
this.settings.notifyDeath=
document.getElementById('notifyDeath').checked;
this.settings.notifyDaily=
document.getElementById('notifyDaily').checked;
this.settings.notifyStrategy=
document.getElementById('notifyStrategy').checked;
this.settings.notifyError=
document.getElementById('notifyError').checked;
this.showToast('设置已保存','success')}
,resetSettings(){
if(!confirm('确定要恢复所有默认设置吗？'))return;
this.settings={
model:'DeepSeek-V3',apiKey:'sk-******************************',temperature:0.3,diagnosisInterval:'1h',decisionInterval:'10min',emergencyCheck:'30s',notifyDeath:true,notifyDaily:true,notifyStrategy:false,notifyError:true}
;
this.renderPage();
this.showToast('已恢复默认设置','success')}
,showGameDetail(game){
const detail=
document.createElement('div');
detail.className='modal show';
detail.innerHTML=`<div class=modal-backdrop></div><div class=modal-content style='max-width:560px'><div class=modal-header><h3>${
game.name}
 - 详情</h3><button class=modal-close>&times;
</button></div><div class=modal-body><div style='display:grid;
grid-template-columns:1fr 1fr;
gap:16px;
margin-bottom:16px'><div class=stat-card><div class=stat-label>状态</div><div class='stat-value ${
game.status==='running'?'success':'warning'}
'>${
game.status==='running'?'运行中':'已暂停'}
</div></div><div class=stat-card><div class=stat-label>完成度</div><div class='stat-value primary'>${
game.progress.toFixed(1)}
%</div></div><div class=stat-card><div class=stat-label>今日操作</div><div class=stat-value>${
game.actionsToday.toLocaleString()}
</div></div><div class=stat-card><div class=stat-label>运行时长</div><div class=stat-value>${
game.uptime}
</div></div></div><div style='font-size:13px;
color:var(--text-secondary);
line-height:1.8'><p><strong>适配器:</strong> ${
game.adapter}
</p><p><strong>游戏URL:</strong> ${
game.url}
</p><p><strong>最近操作:</strong> ${
game.lastAction}
</p><p><strong>游戏ID:</strong> #${
game.id}
</p></div></div><div class=modal-footer><button class='btn btn-ghost btn-edit-rules' data-game='${
game.name}
'>编辑规则</button><button class='btn btn-primary btn-toggle-status' data-game-id=${
game.id}
>${
game.status==='running'?'停止':'启动'}
</button></div></div>`;
document.body.appendChild(detail);
detail.querySelector('.modal-close').addEventListener('click',()=>detail.remove());
detail.querySelector('.modal-backdrop').addEventListener('click',()=>detail.remove());
const editBtn=detail.querySelector('.btn-edit-rules');
if(editBtn)editBtn.addEventListener('click',()=>{
detail.remove();
this.editGameRules(game.name)}
);
const toggleBtn=detail.querySelector('.btn-toggle-status');
if(toggleBtn)toggleBtn.addEventListener('click',()=>{
detail.remove();
this.toggleGameStatus(game.id)}
)}
,highlightYaml(content){
return content.replace(/(#.*$)/gm,'<span class=yaml-comment>$1</span>').replace(/(^[a-zA-Z_][a-zA-Z0-9_]*)(?=:)/gm,'<span class=yaml-key>$1</span>').replace(/: ([^#][^$]*)/gm,': <span class=yaml-string>$1</span>')}
,showToast(message,type='info'){
const toast=
document.createElement('div');
const colors={
info:'#0ea5e9',success:'#00d4aa',warning:'#f59e0b',error:'#ef4444'}
;
toast.style.cssText=`position:fixed;
bottom:24px;
right:24px;
padding:12px 20px;
border-radius:10px;
background:var(--bg-card);
border:1px solid ${
colors[type]}
;
color:var(--text-primary);
font-size:13px;
font-weight:500;
z-index:1000;
box-shadow:var(--shadow-lg);
animation:slideIn .3s ease-out`;
toast.textContent=message;
document.body.appendChild(toast);
setTimeout(()=>{
toast.style.animation='slideOut .3s ease-in';
setTimeout(()=>toast.remove(),300)}
,3000)}
,startLiveSimulation(){
setInterval(()=>{
const runningGame=
this.games.find(g=>g.status==='running');
if(!runningGame)return;
runningGame.actionsToday+=Math.floor(Math.random()*3);
runningGame.progress=Math.min(100,parseFloat((runningGame.progress+0.001).toFixed(3)));
const statActions=
document.getElementById('statActions');
if(statActions)statActions.textContent=
this.games.reduce((sum,g)=>sum+g.actionsToday,0).toLocaleString();
const statProgress=
document.getElementById('statProgress');
if(statProgress){
const avg=(
this.games.reduce((sum,g)=>sum+g.progress,0)/
this.games.length).toFixed(1);
statProgress.textContent=avg+'%'}
const progressEl=
document.getElementById(`progress-${
runningGame.id}
`);
if(progressEl)progressEl.textContent=runningGame.progress.toFixed(1)+'%';
const actionsEl=
document.getElementById(`actions-${
runningGame.id}
`);
if(actionsEl)actionsEl.textContent=runningGame.actionsToday.toLocaleString()}
,5000)}
}
;
document.addEventListener('DOMContentLoaded',()=>App.init());