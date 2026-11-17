/* Native, dependency-free research UI. All scores and answers come from the API. */
(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const main = $('#main');
  const icons = {
    demo: '<path d="m9 6 10 6-10 6V6Z"/><path d="M4 3v18"/>',
    overview: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    library: '<path d="M4 4h7v16H4zM14 4h6v16h-6zM4 8h7M14 8h6"/>',
    workspace: '<path d="M4 4h16v16H4zM4 9h16M10 9v11M7 6.5h1M12 6.5h5"/>',
    experiment: '<path d="M9 3h6M10 3v6L4 19c-.5 1 .1 2 1.2 2h13.6c1.1 0 1.7-1 1.2-2L14 9V3M7 15h10"/>',
    v2experiment: '<path d="M9 3h6M10 3v6L4 19c-.5 1 .1 2 1.2 2h13.6c1.1 0 1.7-1 1.2-2L14 9V3M7 15h10"/>',
    models: '<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 9h6v6H9zM9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    methodology: '<path d="M5 3h11l3 3v15H5zM16 3v4h3M8 11h8M8 15h8M8 18h5"/>',
    arrow: '<path d="M4 12h15M13 6l6 6-6 6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
    play: '<path d="m8 5 11 7-11 7V5Z"/>',
    download: '<path d="M12 3v12M7 10l5 5 5-5M5 16v5h14v-5"/>',
    refresh: '<path d="M20 7v5h-5M4 17v-5h5M20 12a8 8 0 0 0-14-5M4 12a8 8 0 0 0 14 5"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  };
  const svg = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.methodology}</svg>`;
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeURL = (value) => { try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) ? u.href : ''; } catch { return ''; } };
  const extLink = (url, label) => safeURL(url) ? `<a href="${esc(safeURL(url))}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>` : esc(label);
  const pct = (n) => n === null || n === undefined || !Number.isFinite(Number(n)) ? '—' : `${(Number(n) * 100).toFixed(1)}%`;
  const decimal = (n, digits = 2) => n === null || n === undefined || !Number.isFinite(Number(n)) ? '—' : Number(n).toFixed(digits);
  const date = (value, time = false) => { const d = new Date(value); if (!value || Number.isNaN(d.getTime())) return '日期未声明'; return d.toLocaleString('zh-CN', {timeZone:'Asia/Shanghai', year:'numeric', month:'2-digit', day:'2-digit', ...(time ? {hour:'2-digit', minute:'2-digit', hour12:false} : {})}); };
  const number = (n) => Number(n || 0).toLocaleString('zh-CN');
  const textLength = (article) => Array.from(article.text || '').length;
  const articleDateMetadata = (a) => `<span>网页发布于 ${date(a.source_page_published_at || a.published_at)}</span>${a.promulgated_at ? `<span>原公布日 ${date(a.promulgated_at)}</span>` : ''}${a.first_published_at ? `<span>已知首发日 ${date(a.first_published_at)}</span>` : ''}<span>时间门槛日期 ${date(a.temporal_date || a.published_at)}</span>`;
  const questionText = (q) => q.prompt || q.question || '';
  const reference = (q) => q.reference_answer || q.answers?.join(' / ') || q.answer || (q.type === 'unanswerable' ? '应拒答：文章未提供答案' : '');
  const evidence = (q) => Array.isArray(q.evidence) ? q.evidence.join('\n') : String(q.evidence || '');
  const typeNames = {fact:'事实提取',factual:'事实提取',literal:'事实提取',extraction:'信息提取',inference:'推理理解',multi_hop:'跨段推理',integration:'信息整合',synthesis:'信息整合',summary:'概括归纳',summarization:'概括归纳',numeric:'数值理解',numerical:'数值推理',unanswerable:'不可回答',critical:'批判理解',causal:'因果理解',comparison:'对比理解',temporal:'时序理解',vocabulary:'语境词义'};
  const typeLabel = (type) => typeNames[type] || type || '未分类';
  const statusNames = {queued:'排队中',running:'运行中',completed:'已完成',failed:'运行失败',cancelled:'已取消',interrupted:'已中断'};
  const isActive = (run) => ['queued', 'running'].includes(run?.status);
  const statusBadge = (status) => `<span class="badge ${status === 'completed' ? 'badge-success' : ['running','queued'].includes(status) ? 'badge-running' : ['failed','interrupted'].includes(status) ? 'badge-danger' : 'badge-neutral'}"><span class="badge-dot"></span>${esc(statusNames[status] || status || '未知')}</span>`;
  const modelBadge = (m) => `<span class="badge ${m.available ? 'badge-success' : 'badge-neutral'}"><span class="badge-dot"></span>${m.available ? '可调用' : '未连接'}</span>`;
  const state = {health:null, models:[], articles:[], runs:[], methodology:'', workspace:null, candidateLanguage:'all', candidateProvider:'all', selectedCandidate:'', candidateDetail:null, candidateLoading:false, candidateError:'', loaded:false, errors:[], route:'overview', routeId:'', search:'', selectedArticle:'', selectedModels:new Set(), selectedArticles:new Set(), config:{mode:'with_context',strict_time:true,question_limit:4,temperature:0,max_tokens:512}, run:null, resultModel:'all', resultView:'all', busy:false, runLoading:false, runError:'', openDetails:new Set()};
  Object.assign(state, {banks:[],bank:null,bankId:'',bankLoading:false,bankError:'',v2Article:'',v2Models:new Set(),v2Articles:new Set(),v2DraftAccepted:false,resultLanguage:'all',v2Config:{mode:'with_context',strict_time:true,strict_budget:false,question_limit:16,temperature:0,max_tokens:512,num_ctx:8192,bootstrap_repetitions:200}});
  const demo = {data:null,connected:false,loading:false,error:'',modelId:'',presetId:'',language:'zh',count:1,starting:false,requestId:'',pending:false,run:null,runId:'',runError:'',runLoading:false,lastRead:null};
  let demoPollTimer = null;
  let demoPollGeneration = 0;
  let demoStatusGeneration = 0;
  const isPublicReference = (value) => value?.annotation_origin === 'external_public_benchmark';
  const isEvidenceProxy = (value) => value?.evidence_gold_status === 'unreviewed_proxy';
  function v2NativeContextLimit() {
    const limits = state.models.filter((m) => state.v2Models.has(m.id)).map((m) => Number(m.native_context_tokens)).filter((n) => Number.isInteger(n) && n > 0);
    return limits.length ? Math.min(...limits) : null;
  }
  function constrainV2Context() {
    const limit = v2NativeContextLimit();
    if (limit !== null && state.v2Config.num_ctx > limit && limit >= 4096) state.v2Config.num_ctx = 4096;
  }
  function v2ContextExplanation() {
    const limit = v2NativeContextLimit();
    return `${limit === null ? '所选模型未全部登记原生上下文上限；以服务端预算核验为准。' : `所选已登记模型的最小原生上限为 ${number(limit)} Tokens。`}${limit === 4096 ? '已按原生上限使用 4096 窗口。' : ''}当前实验窗口 ${number(state.v2Config.num_ctx)}；超出预算会拒绝运行，不截断正文。`;
  }
  let candidateGeneration = 0;
  let bankGeneration = 0;
  const annotationLabels = {candidate:'已下载候选',ai_checked:'AI 初审',human_reviewed:'人工复核',frozen:'冻结入库'};
  let pollTimer = null;
  let pollGeneration = 0;
  let initializedSelection = false;
  let toastTimer;
  function token() { try { return sessionStorage.getItem('reading-bench-token') || ''; } catch { return ''; } }
  async function api(path, options = {}) {
    const headers = {...(options.body ? {'Content-Type':'application/json'} : {}), ...(token() ? {Authorization:`Bearer ${token()}`} : {}), ...options.headers};
    let response;
    try { response = await fetch(path, {...options, headers, cache:'no-store'}); } catch { throw new Error('无法连接平台服务。请检查服务是否启动以及服务器连接。'); }
    if (!response.ok) {
      let message = `请求失败（HTTP ${response.status}）`;
      try { const payload = await response.json(); message = payload.error || payload.detail || message; } catch { /* Non-JSON error page. */ }
      if (response.status === 401) message += '。请在右上角填写正确的访问令牌。';
      const error = new Error(message); error.status = response.status; throw error;
    }
    return options.blob ? response.blob() : response.json();
  }
  function toast(message, error = false) {
    const region = $('#toast-region');
    region.innerHTML = `<div class="toast ${error ? 'error' : ''}" role="${error ? 'alert' : 'status'}">${esc(message)}</div>`;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { region.innerHTML = ''; }, error ? 9000 : 4500);
  }
  function empty(title, description, action = '', icon = 'library') { return `<div class="empty-state"><div class="empty-symbol">${svg(icon)}</div><h3>${esc(title)}</h3><p>${esc(description)}</p>${action}</div>`; }
  function heading(eyebrow, title, subtitle, actions = '') { return `<div class="page-heading"><div><span class="eyebrow">${esc(eyebrow)}</span><h1>${esc(title)}</h1>${subtitle ? `<p>${esc(subtitle)}</p>` : ''}</div>${actions}</div>`; }
  function stat(label, value, note, icon, unit = '') { return `<div class="stat-card"><div class="stat-label">${esc(label)}${svg(icon)}</div><div class="stat-value">${esc(value)}${unit ? `<small>${esc(unit)}</small>` : ''}</div><div class="stat-note">${esc(note)}</div></div>`; }
  function globalErrors() { return state.errors.length ? `<div class="notice error global-error" role="alert">${state.errors.map(esc).join('<br>')}<div class="read-more"><button type="button" class="button button-small button-secondary" data-action="reload">重新连接</button></div></div>` : ''; }
  async function loadData() {
    state.errors = [];
    const paths = ['/api/health','/api/models','/api/articles','/api/runs','/api/methodology','/api/corpus-workspace','/api/v2/banks'];
    const results = await Promise.allSettled(paths.map((p) => api(p)));
    const labels = ['平台状态','模型列表','文章题库','实验记录','方法文档','题库建设'];
    results.forEach((result, i) => {
      if (result.status === 'rejected') { if (i === 6) { state.bankError = result.reason.message; return; } state.errors.push(`${labels[i]}：${result.reason.message}`); if (!i) state.health = null; return; }
      const data = result.value;
      if (i === 0) state.health = data;
      if (i === 1) state.models = data.models || [];
      if (i === 2) state.articles = data.articles || [];
      if (i === 3) state.runs = data.runs || [];
      if (i === 4) state.methodology = data.markdown || '';
      if (i === 5) state.workspace = data;
      if (i === 6) { state.banks = data.banks || []; state.bankError = ''; if (!state.bankId) state.bankId = state.banks[0]?.id || ''; }
    });
    if (!initializedSelection && state.models.length) {
      const available = state.models.filter((m) => m.available).sort((a,b) => Number(b.provider === 'ollama') - Number(a.provider === 'ollama'));
      state.selectedModels = new Set(available.slice(0,2).map((m) => m.id));
      const defaultV2 = available.find((m) => m.id === 'qwen25-7b') || available.find((m) => !m.native_context_tokens || m.native_context_tokens >= 8192) || available[0];
      state.v2Models = new Set(defaultV2 ? [defaultV2.id] : []);
      initializedSelection = true;
    }
    if (!state.selectedArticle && state.articles.length) state.selectedArticle = state.articles[0].id;
    if (!state.selectedArticles.size && state.articles.length) state.selectedArticles.add(state.articles[0].id);
    state.loaded = true;
    updateConnection(); render();
    if (state.route === 'run' && state.routeId) loadRun(state.routeId);
    if (state.route === 'workspace') selectWorkspaceCandidate();
    if (state.route === 'v2experiment' && state.bankId) loadBank(state.bankId);
    if (state.route === 'demo' && !demo.data && !demo.loading) loadDemoStatus();
  }
  function updateConnection() {
    const el = $('#connection');
    const online = !!state.health && ['ok','healthy','ready'].includes(state.health.status || 'ok');
    el.className = `connection ${online ? 'online' : 'offline'}`;
    el.innerHTML = `<i></i>${online ? '服务已连接' : '服务未连接'}`;
    el.title = online ? `平台版本 ${state.health.version || '未声明'}` : '请启动服务或配置访问令牌';
    $('#token-button').textContent = token() ? '令牌已设置' : '访问令牌';
  }
  function readRoute() {
    const parts = location.hash.slice(1).split(':');
    state.route = ['demo','overview','library','workspace','experiment','v2experiment','run','models','methodology'].includes(parts[0]) ? parts[0] : 'demo';
    state.routeId = parts.slice(1).join(':');
    if (state.route === 'library' && state.routeId) state.selectedArticle = state.routeId;
    if (state.route === 'workspace' && state.routeId) state.selectedCandidate = state.routeId;
    stopPolling();
    stopDemoPolling();
    if (state.route !== 'run') { state.run = null; state.runError = ''; }
    render();
    if (state.route === 'run' && state.routeId && state.loaded) { state.run = null; state.runLoading = true; state.runError = ''; render(); loadRun(state.routeId); }
    if (state.route === 'workspace' && state.loaded) selectWorkspaceCandidate();
    if (state.route === 'v2experiment' && state.loaded && state.bankId && state.bank?.id !== state.bankId) loadBank(state.bankId);
    if (state.route === 'demo') { if (!demo.data && !demo.loading) loadDemoStatus(); else if (demo.runId) loadDemoRun(demo.runId); }
  }
  function renderNavigation() {
    const items = [['demo','现场演示'],['overview','概览'],['library','演示题库'],['workspace','题库建设'],['v2experiment','新版实验（开发）'],['experiment','历史实验 v1'],['models','模型管理'],['methodology','评价方法']];
    const active = state.route === 'run' ? (state.run?.protocol === 'reading-experiment-v2' ? 'v2experiment' : 'experiment') : state.route;
    $('#navigation').innerHTML = items.map(([key,label]) => `<a class="nav-item ${active === key ? 'active' : ''}" href="#${key}" ${active === key ? 'aria-current="page"' : ''}>${svg(key)}<span>${label}</span></a>`).join('');
    $('#page-label').textContent = state.route === 'run' ? '实验详情' : items.find(([key]) => key === active)?.[1] || '概览';
    document.title = `${$('#page-label').textContent} · 阅见 Reading Bench`;
  }
  function render() {
    renderNavigation();
    if (!state.loaded && state.route !== 'demo') return;
    const views = {demo:renderDemo,overview:renderOverview,library:renderLibrary,workspace:renderWorkspace,experiment:renderExperiment,v2experiment:renderV2Experiment,run:renderRun,models:renderModels,methodology:renderMethodology};
    main.innerHTML = (state.route === 'demo' ? '' : globalErrors()) + views[state.route]();
  }
  function demoStorageKey() { return `reading-bench-live-demo:${location.origin}`; }
  function rememberDemo() {
    try { localStorage.setItem(demoStorageKey(),JSON.stringify({run_id:demo.runId,client_request_id:demo.pending ? demo.requestId : '',model_id:demo.modelId,preset_id:demo.presetId})); }
    catch { /* Reading results remains possible when storage is unavailable. */ }
  }
  function restoreDemo() {
    try {
      const saved = JSON.parse(localStorage.getItem(demoStorageKey()) || 'null');
      if (!saved || typeof saved !== 'object') return;
      if (/^run-[a-f0-9]{12}$/.test(saved.run_id || '')) demo.runId = saved.run_id;
      if (/^[A-Za-z0-9_-]{8,100}$/.test(saved.client_request_id || '')) { demo.requestId = saved.client_request_id; demo.pending = true; }
      if (typeof saved.model_id === 'string') demo.modelId = saved.model_id;
      if (typeof saved.preset_id === 'string') demo.presetId = saved.preset_id;
    } catch { /* An absent or invalid saved selection does not block startup. */ }
  }
  const selectedDemoPreset = () => demo.data?.presets?.find((p) => p.id === demo.presetId);
  const selectedDemoModel = () => demo.data?.models?.find((m) => m.id === demo.modelId);
  function demoCompatible(model, preset = selectedDemoPreset()) {
    return !!model?.available && !!preset && (model.compatible_preset_ids || []).includes(preset.id);
  }
  function demoSelectionLocked() { return demo.starting || demo.pending || demo.runLoading || !!demo.runId && !demo.run || isActive(demo.run); }
  function chooseDemoPreset() {
    const presets = demo.data?.presets || [];
    const selected = presets.find((p) => p.language === demo.language && Number(p.question_count) === demo.count);
    demo.presetId = selected?.id || '';
    if (!demoCompatible(selectedDemoModel(),selected)) {
      demo.modelId = demo.data?.models?.find((m) => m.id === demo.data.default_model_id && demoCompatible(m,selected))?.id || demo.data?.models?.find((m) => demoCompatible(m,selected))?.id || '';
    }
  }
  function stopDemoPolling() { clearTimeout(demoPollTimer); demoPollTimer = null; demoPollGeneration++; }
  function renderDemoPreservingFocus() {
    if (state.route !== 'demo') return;
    const activeId = document.activeElement?.id;
    const scroll = window.scrollY;
    render();
    if (activeId) document.getElementById(activeId)?.focus({preventScroll:true});
    window.scrollTo({top:scroll,behavior:'instant'});
  }
  async function loadDemoStatus() {
    const generation = ++demoStatusGeneration;
    demo.loading = true; demo.error = ''; renderDemoPreservingFocus();
    try {
      const data = await api('/api/demo/status');
      if (generation !== demoStatusGeneration) return;
      demo.data = data; demo.connected = true;
      state.health = {status:'ok'}; updateConnection();
      if (!demo.presetId) { restoreDemo(); if (!demo.presetId) demo.presetId = data.default_preset_id || data.presets?.[0]?.id || ''; }
      const preset = selectedDemoPreset();
      if (preset) { demo.language = preset.language; demo.count = Number(preset.question_count); }
      else { demo.presetId = ''; chooseDemoPreset(); }
      if (!demo.modelId) demo.modelId = data.default_model_id || '';
      if (!demoSelectionLocked() && !demoCompatible(selectedDemoModel())) chooseDemoPreset();
      if (!demo.runId && !demo.pending && data.active_run?.live_demo?.version === data.version) demo.runId = data.active_run.id;
      rememberDemo();
    } catch (error) { if (generation === demoStatusGeneration) { demo.error = error.message; demo.connected = false; } }
    finally {
      if (generation === demoStatusGeneration) {
        demo.loading = false; renderDemoPreservingFocus();
        if (state.route === 'demo' && demo.runId) { stopDemoPolling(); loadDemoRun(demo.runId); }
      }
    }
  }
  async function loadDemoRun(id) {
    const generation = demoPollGeneration;
    demo.runLoading = !demo.run;
    try {
      const payload = await api(`/api/v2/runs/${encodeURIComponent(id)}`);
      if (state.route !== 'demo' || demo.runId !== id || generation !== demoPollGeneration) return;
      demo.run = payload.run || payload; demo.runError = ''; demo.runLoading = false; demo.lastRead = new Date().toISOString();
      rememberDemo(); renderDemoPreservingFocus();
      if (isActive(demo.run)) demoPollTimer = setTimeout(() => loadDemoRun(id),1500);
    } catch (error) {
      if (state.route !== 'demo' || demo.runId !== id || generation !== demoPollGeneration) return;
      if (error.status === 404 || error.status === 400 && /记录不存在|此运行不是新版实验/.test(error.message)) { demo.runId = ''; demo.run = null; demo.error = `当前平台没有找到可恢复的新版实验 ${id}，可重新选择并运行。`; rememberDemo(); }
      demo.runLoading = false; demo.runError = error.message; renderDemoPreservingFocus();
      // Leave the last real response visible. Reconnection only reads this run.
    }
  }
  function demoCanLaunch() {
    return !!demo.data && demo.connected && !demo.loading && !demo.starting && !isActive(demo.run) && !demo.runLoading && (!demo.runId || !!demo.run) && demoCompatible(selectedDemoModel()) && (demo.pending || !demo.data.active_run || demo.data.active_run.id === demo.run?.id && !isActive(demo.run));
  }
  async function launchDemo() {
    if (!demoCanLaunch()) return;
    if (!demo.pending) {
      demo.requestId = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `demo-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,12)}`;
      demo.pending = true; rememberDemo();
    }
    demo.starting = true; demo.error = ''; renderDemoPreservingFocus();
    try {
      const result = await api('/api/demo/runs',{method:'POST',body:JSON.stringify({model_id:demo.modelId,preset_id:demo.presetId,allow_draft:true,client_request_id:demo.requestId})});
      const run = result.run || result;
      const id = run.id || result.run_id || result.id;
      if (!/^run-[a-f0-9]{12}$/.test(id || '')) throw new Error('服务器未返回有效实验编号，请重新确认本次提交。');
      demo.runId = id; demo.run = run.id ? run : null; demo.pending = false; demo.requestId = ''; demo.runError = ''; demo.lastRead = null;
      rememberDemo(); stopDemoPolling();
      if (state.route === 'demo') loadDemoRun(id);
      toast(result.reused ? '已恢复同一次提交，不会重复调用。' : '已创建真实实验，正在等待模型回答。');
    } catch (error) {
      if (error.status && error.status < 500) { demo.pending = false; demo.requestId = ''; rememberDemo(); }
      demo.error = error.message + (demo.pending ? ' 本次提交编号已保留；重新确认会使用同一编号，避免重复创建。' : '');
      if (error.status === 409) await loadDemoStatus();
    } finally { demo.starting = false; renderDemoPreservingFocus(); }
  }
  async function cancelDemo() {
    if (!demo.runId || !isActive(demo.run) || demo.starting) return;
    demo.starting = true; renderDemoPreservingFocus();
    try {
      await api(`/api/runs/${encodeURIComponent(demo.runId)}/cancel`,{method:'POST',body:'{}'});
      toast('已请求取消。当前模型请求结束后停止后续题目。'); stopDemoPolling(); await loadDemoRun(demo.runId);
    } catch (error) { demo.runError = error.message; }
    finally { demo.starting = false; renderDemoPreservingFocus(); }
  }
  function renderDemoQuestions(preset) {
    return (preset.questions || []).map((q,i) => `<li><div class="demo-question-heading"><span>${String(i+1).padStart(2,'0')}</span><span class="badge">${esc(kindLabels[q.kind] || q.kind)}</span></div><p>${esc(q.prompt)}</p>${q.options ? `<dl class="v2-options">${Object.entries(q.options).map(([key,value]) => `<dt>${esc(key)}</dt><dd>${esc(value)}</dd>`).join('')}</dl>` : ''}</li>`).join('');
  }
  function renderDemoProgress() {
    const run = demo.run;
    if (!run) return `<section class="demo-live-panel panel" aria-label="现场运行记录"><div class="demo-awaiting"><span class="demo-outline-play">${svg('play')}</span><h2>${demo.runId ? '正在恢复这次运行' : '等待你的第一场现场运行'}</h2><p>${demo.runId ? '只读取已经保存的实验，不会重新调用模型。' : '点击“开始现场运行”，模型回答与逐题评分会在这里依次出现。'}</p>${demo.runError ? `<div class="notice error" role="alert">${esc(demo.runError)}<button class="button button-small button-secondary" data-action="demo-reconnect" type="button">恢复读取</button></div>` : ''}</div></section>`;
    const results = run.results || [], done = Number(run.progress?.done || 0), total = Number(run.progress?.total || 0);
    const errors = results.filter((r) => r.error || r.metrics?.error).length;
    const modelName = run.snapshots?.models?.[0]?.name || run.config?.model_ids?.[0] || '未声明模型';
    const articleTitle = run.snapshots?.bank?.articles?.[0]?.title || '固定材料';
    const elapsed = results.reduce((sum,r) => sum + (Number.isFinite(Number(r.latency_s)) ? Number(r.latency_s) : 0),0);
    const active = isActive(run);
    const waiting = active && done === 0;
    return `<section class="demo-live-panel" aria-label="现场运行记录"><div class="demo-run-heading"><div><span class="eyebrow">LIVE RECORD · 本次真实记录</span><h2>${active ? '模型正在阅读' : run.status === 'completed' ? '本次运行已结束' : statusNames[run.status] || '运行记录'}</h2><p>${esc(modelName)} · ${esc(articleTitle)}</p></div>${statusBadge(run.status)}</div>
      <div class="demo-run-strip"><span><strong>${done}<small> / ${total}</small></strong>已记录回答</span><span><strong>${errors}</strong>调用 / 格式错误</span><span><strong>${decimal(elapsed,1)}<small> 秒</small></strong>已记录请求耗时</span></div>
      <div class="progress-track demo-progress" role="progressbar" aria-label="已记录调用进度" aria-valuemin="0" aria-valuemax="${Math.max(1,total)}" aria-valuenow="${Math.min(done,total)}"><div class="progress-fill" style="width:${total ? Math.min(100,done / total * 100) : 0}%"></div></div>
      <p class="demo-live-note" role="status">${demo.runError ? '连接中断，以下保留上次读取到的真实记录。' : waiting ? '首个响应尚未返回，模型可能正在加载或推理；进度只在记录实际响应后更新。' : active ? '后台继续逐题运行，回答返回后自动更新。刷新页面可恢复同一次运行。' : done < total ? '运行未完成，未执行题不会显示为成功。可进入完整报告查看与续跑。' : errors ? '调用已记录完毕，错误与原始响应均保留；完成不代表所有题都答对。' : '已保存全部回答、评分与原始响应。少量演示题不能代表模型总体能力。'}</p>
      ${demo.runError ? `<div class="notice error" role="alert">${esc(demo.runError)}<div class="read-more"><button type="button" class="button button-small button-secondary" data-action="demo-reconnect">恢复读取，不重复运行</button></div></div>` : ''}${run.error ? `<div class="notice error" role="alert">${esc(run.error)}</div>` : ''}
      <div class="demo-run-actions actions">${active ? `<button class="button button-danger button-small" type="button" data-action="demo-cancel" ${demo.starting ? 'disabled' : ''}>停止后续题目</button>` : ''}<a class="button button-secondary button-small" href="#run:${esc(run.id)}">完整报告 ${svg('arrow')}</a><button class="button button-quiet button-small" type="button" data-demo-export="json">${svg('download')}JSON</button><button class="button button-quiet button-small" type="button" data-demo-export="csv">CSV</button></div>
      <p class="demo-record-meta"><span class="mono">${esc(run.id)}</span><span>创建于 ${date(run.created_at,true)}</span><span>${demo.lastRead ? '最近读取 '+date(demo.lastRead,true) : '等待读取'}</span></p>
      ${results.length ? `<div class="demo-result-list">${results.map((r,index) => renderV2ResultForRun(run,r,index)).join('')}</div>` : `<div class="demo-answer-wait"><span class="spinner"></span><span>${active ? '等待第一条真实回答…' : '本次尚无已记录回答。'}</span></div>`}</section>`;
  }
  function renderDemo() {
    const data = demo.data, preset = selectedDemoPreset(), model = selectedDemoModel();
    const locked = demoSelectionLocked();
    const readyModels = (data?.models || []).filter((m) => m.available).length;
    const compatibility = model?.compatibility?.[preset?.id];
    return `<div class="demo-page"><section class="demo-hero"><div><span class="eyebrow">READING BENCH / LIVE SESSION</span><h1>让模型，<br>现场读一篇。</h1><p>给出文章，等待真实回答，再核对答案与依据。</p></div><ol class="demo-journey" aria-label="演示流程"><li><span>01</span><div><strong>选择材料与模型</strong><small>中英文 · 单题或三题</small></div></li><li><span>02</span><div><strong>发起真实推理</strong><small>现场生成 · 后台保存</small></div></li><li><span>03</span><div><strong>回到证据核验</strong><small>逐题评分 · 原始记录</small></div></li></ol></section>
      <div class="demo-connection-strip"><div><span class="demo-connection-dot ${demo.connected ? 'online' : ''}"></span><strong>${demo.connected ? esc(data?.deployment?.label || '平台已连接') : demo.loading ? '正在检查平台连接' : '平台连接待检查'}</strong><span>${demo.connected ? `${readyModels} 个模型可连接` : data ? '上次检查结果已保留，请重新连接' : '检查不触发模型推理'}</span></div><button class="button button-quiet button-small" type="button" data-action="demo-refresh" ${demo.loading || demo.starting ? 'disabled' : ''}>${demo.loading ? '<span class="spinner"></span>' : svg('refresh')}检查连接</button></div>
      ${demo.error ? `<div class="notice error demo-error" role="alert">${esc(demo.error)}</div>` : ''}
      ${!data ? `<section class="panel demo-unavailable">${demo.loading ? '<div class="loading-screen"><span class="spinner"></span><p>正在检查模型连接与可运行材料…</p></div>' : empty('尚未连接演示服务','请确认平台已启动。服务器部署请保持连接隧道，本地部署请确认模型服务已运行。','<button class="button button-secondary" type="button" data-action="demo-refresh">重新检查连接</button>','models')}</section>` : `<div class="demo-workbench"><aside class="demo-controls panel"><div class="demo-panel-heading"><span class="eyebrow">01 / 准备运行</span><h2>这一场，怎么读？</h2></div>
      <fieldset class="demo-choice-group" ${locked ? 'disabled' : ''}><legend>阅读语言</legend><div class="segment"><button type="button" data-demo-language="zh" aria-pressed="${demo.language === 'zh'}">中文<span>Chinese</span></button><button type="button" data-demo-language="en" aria-pressed="${demo.language === 'en'}">英文<span>English</span></button></div></fieldset>
      <fieldset class="demo-choice-group" ${locked ? 'disabled' : ''}><legend>本次题量</legend><div class="segment"><button type="button" data-demo-count="1" aria-pressed="${demo.count === 1}">单题快跑<span>验证完整流程</span></button><button type="button" data-demo-count="3" aria-pressed="${demo.count === 3}">三题阅读<span>答案、证据与拒答</span></button></div></fieldset>
      <label class="field demo-model-field" for="demo-model">调用哪个模型<select id="demo-model" ${locked ? 'disabled' : ''}>${(data.models || []).length ? (data.models || []).map((m) => `<option value="${esc(m.id)}" ${m.id === demo.modelId ? 'selected' : ''} ${!demoCompatible(m,preset) ? 'disabled' : ''}>${esc(m.name)}${!m.available ? ' · 未连接' : !demoCompatible(m,preset) ? ' · 此材料暂不兼容' : ''}</option>`).join('') : '<option value="">暂无模型连接</option>'}</select></label>
      ${model ? `<div class="demo-model-note"><strong>${esc(model.model)}</strong><span>${esc(data.deployment?.model_connection_note || '推理由当前平台后端调用已配置的模型服务。')}</span></div>` : '<p class="demo-model-note">暂无兼容的可用模型，请检查连接或前往模型管理。</p>'}
      ${(data.problems || []).length ? `<div class="notice demo-problems">${data.problems.map(esc).join('<br>')}${data.active_run?.id && data.active_run.id !== demo.runId ? `<br><a href="#run:${esc(data.active_run.id)}">查看正在运行的实验</a>` : ''}</div>` : ''}
      <div class="demo-launch-box"><span class="demo-call-count"><strong>${preset?.question_count || 0}</strong> 次模型调用 · 完整文章</span><button class="button button-primary demo-launch" type="button" data-action="demo-launch" ${demoCanLaunch() ? '' : 'disabled'}>${demo.starting ? '<span class="spinner"></span>正在提交' : svg('play')+(demo.pending ? '重新确认本次提交' : '开始现场运行')}</button><p>本次使用未完成人审的开发题稿。点击后生成新回答，结果仅作演示与诊断。</p></div>
      <details class="demo-settings raw-details" data-detail="demo-settings" ${state.openDetails.has('demo-settings') ? 'open' : ''}><summary>查看连接与运行条件</summary><dl><dt>平台主机</dt><dd>${esc(data.deployment?.hostname || '当前平台')}</dd><dt>模型服务</dt><dd class="mono">${esc(model?.base_url || '—')}</dd><dt>上下文窗口</dt><dd>${number(compatibility?.num_ctx || model?.demo_context_tokens)} Tokens</dd><dt>生成设置</dt><dd>Temperature 0 · 输出 512 Tokens</dd><dt>材料版本</dt><dd class="mono">${esc(preset?.bank_id || '—')}</dd></dl><p>模型服务地址相对于平台后端所在主机；浏览器无需直接连接推理端口。首题可能包含模型加载时间。</p></details>
      <a class="demo-advanced-link" href="#v2experiment">多模型比较与自选题库 ${svg('arrow')}</a></aside><div class="demo-reading-column">${preset ? `<section class="panel demo-material"><div class="demo-material-heading"><div><span class="eyebrow">02 / 本次材料</span><h2>${esc(preset.label)}</h2></div><span class="badge badge-gold">开发题稿 · 未人审</span></div><details class="demo-source" data-detail="demo-source" ${state.openDetails.has('demo-source') ? 'open' : ''}><summary><span>阅读完整文章</span><span>${preset.article?.paragraphs?.length || 0} 段 ${svg('arrow')}</span></summary>${preset.article ? renderV2Article(preset.article,'demo-source') : ''}</details><ol class="demo-questions">${renderDemoQuestions(preset)}</ol></section>` : '<div class="notice error">未找到该语言与题量的演示材料，请检查题库连接。</div>'}${renderDemoProgress()}</div></div>`}
      ${(data?.recent_runs || []).length ? `<section class="demo-recent"><div class="section-heading"><h2>最近的现场记录</h2><span class="muted small">已保存的真实运行</span></div><div class="demo-recent-list">${data.recent_runs.slice(0,4).map((r) => `<a href="#run:${esc(r.id)}"><span class="mono">${esc(r.id)}</span>${statusBadge(r.status)}<small>${date(r.created_at,true)}</small>${svg('arrow')}</a>`).join('')}</div></section>` : ''}<p class="demo-bottom-note">演示题不构成正式基准。中文与英文分别评价；每次运行的答案、段落证据、错误和版本信息都会保留。</p></div>`;
  }
  function runRows(runs, compact = false) {
    if (!runs.length) return empty('第一场实验，从这里开始', '选择文章与模型，现场观察模型回答和评分。每一次调用都会保存原始记录。', '<a class="button button-secondary button-small" href="#experiment">创建测评实验</a>', 'experiment');
    return `<div class="table-wrap"><table class="data-table"><thead><tr><th>实验 / 时间</th><th>状态</th><th>模型</th>${compact ? '' : '<th>实验设置</th>'}<th class="numeric">进度</th><th></th></tr></thead><tbody>${runs.map((r) => {
      const config = r.config || {}; const sourceBank = r.snapshots?.bank || state.banks.find((b) => b.id === config.bank_id); const names = (r.summary || []).map((s) => s.model_name); const modelNames = names.length ? names : (config.model_ids || []).map((id) => state.models.find((m) => m.id === id)?.name || id);
      return `<tr><td><a class="run-title" href="#run:${esc(r.id)}">${esc(r.id)}</a><small>${r.protocol === 'reading-experiment-v2' ? 'v2 · ' + (isPublicReference(sourceBank) ? '公开历史参考' : config.allow_draft ? '开发诊断' : '冻结题库') : 'v1 · 历史评分'} · ${date(r.created_at,true)}</small></td><td>${statusBadge(r.status)}</td><td>${esc(modelNames.slice(0,2).join(' · ') || '—')}${modelNames.length > 2 ? `<small>共 ${modelNames.length} 个模型</small>` : ''}</td>${compact ? '' : `<td>${config.mode === 'no_context' ? '无文章对照' : '提供文章'}<small>${config.strict_time ? '开启时间门槛' : '关闭时间门槛'}</small></td>`}<td class="numeric">${number(r.progress?.done)} <span class="muted">/ ${number(r.progress?.total)}</span></td><td><a class="text-link" href="#run:${esc(r.id)}" aria-label="查看实验 ${esc(r.id)}">${svg('arrow')}</a></td></tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function renderOverview() {
    const totalQuestions = state.articles.reduce((n,a) => n + (a.questions?.length || 0),0);
    const done = state.runs.filter((r) => r.status === 'completed').length;
    const typeCounts = {};
    state.articles.forEach((a) => a.questions?.forEach((q) => { typeCounts[q.type] = (typeCounts[q.type] || 0) + 1; }));
    const newest = [...state.articles].sort((a,b) => String(b.published_at).localeCompare(String(a.published_at))).slice(0,3);
    return `${heading('READING INTELLIGENCE LAB','阅读，理解，然后验证。','用近期文章，衡量模型的理解能力与证据意识。')}
      <section class="hero"><div><span class="eyebrow">从真实文本，得到真实结果</span><h1>把“读懂”变成<br>可验证的证据。</h1><p>向模型提供文章，检查事实、推理与拒答表现。每个分数都能回到原始回答、标准答案和文章证据。</p><a class="button button-primary" href="#v2experiment">${svg('play')}进入新版开发实验 ${svg('arrow')}</a></div><div class="hero-diagram"><span class="diagram-label">时间隔离的实验设计</span><div class="timeline"><span class="timeline-point"></span><span class="timeline-event"><strong>模型发布</strong>锁定版本与日期</span><span class="timeline-line"></span><span class="timeline-event"><strong>文章发布</strong>选择更新的文本</span><span class="timeline-line"></span><span class="timeline-event"><strong>现场测评</strong>保存逐题证据</span></div><p>发布日可作为训练完成的保守上界；<br>通过日期门槛仍不等于完全排除数据污染。</p></div></section>
      <div class="stat-grid">${stat('演示文章',number(state.articles.length),'示例标注仍需独立人工复核','library','篇')}${stat('演示问题',number(totalQuestions),'含参考答案与原文证据','methodology','题')}${stat('已连接模型',number(state.models.filter((m) => m.available).length),`共配置 ${state.models.length} 个模型`,'models','个')}${stat('已完成实验',number(done),`共保存 ${state.runs.length} 次实验记录`,'experiment','次')}</div>
      <div class="notice corpus-progress"><div><strong>双语题库建设：${number(state.workspace?.counts?.downloaded)} 篇真实正文已下载</strong><p>目标 120 篇，中英文各 60 篇；20 篇开发集、100 篇正式测试集。当前人工复核 ${number(state.workspace?.counts?.states?.human_reviewed)} 篇，冻结 ${number(state.workspace?.counts?.states?.frozen)} 篇。</p></div><a class="button button-small button-secondary" href="#workspace">查看题库建设 ${svg('arrow')}</a></div>
      <div class="two-column"><section><div class="section-heading"><h2>最近的实验</h2><a class="text-link" href="#experiment">查看全部 ${svg('arrow')}</a></div><div class="panel" style="padding:8px 10px">${runRows(state.runs.slice(0,5),true)}</div></section><section><div class="section-heading"><h2>题库来源</h2><span class="muted">按网页发布日期</span></div><div class="panel">${newest.length ? newest.map((a) => `<div class="source-row"><a href="#library:${esc(a.id)}">${esc(a.title)}</a><div class="meta"><span>${esc(a.source_name || '未声明来源')}</span><span>${date(a.published_at)}</span><span>${a.questions?.length || 0} 题</span></div></div>`).join('') : empty('还没有文章','导入包含标准答案和证据的文章，建立可核查的题库。','','library')}</div></section></div>
      ${Object.keys(typeCounts).length ? `<div class="section-heading" style="margin-top:29px;margin-bottom:0"><h2>问题能力覆盖</h2><span class="muted">题库实际分布</span></div><div class="coverage">${Object.entries(typeCounts).map(([type,n]) => `<div class="coverage-item"><span>${esc(typeLabel(type))}</span><strong>${n}<span class="small muted"> 题</span></strong></div>`).join('')}</div>` : ''}`;
  }
  function renderLibrary() {
    const query = state.search.trim().toLowerCase();
    const articles = state.articles.filter((a) => `${a.title} ${a.source_name} ${a.text}`.toLowerCase().includes(query));
    const article = articles.find((a) => a.id === state.selectedArticle) || articles[0];
    return `${heading('DEMO CORPUS & EVIDENCE','演示题库','当前示例用于验证平台流程；正式测评题库需完成独立人工复核。','<button class="button button-secondary" type="button" data-action="import">'+svg('plus')+'导入题库 JSON</button>')}
      <input type="file" id="import-file" class="file-input" accept=".json,application/json" aria-label="选择题库 JSON 文件">
      <div class="library-toolbar"><label class="search-box">${svg('search')}<span class="sr-only">搜索文章、来源或正文</span><input id="article-search" type="search" placeholder="搜索文章、来源或正文…" value="${esc(state.search)}"></label><span class="muted small">${articles.length} 篇文章 · ${articles.reduce((n,a) => n + (a.questions?.length || 0),0)} 道问题</span></div>
      ${!state.articles.length ? `<div class="panel">${empty('题库等待第一篇文章','导入文章正文、日期、来源链接、问题、答案与证据。只有真实题库会进入测评。')}</div>` : `<div class="library-layout"><div class="article-list">${articles.length ? articles.map((a,i) => `<button type="button" class="article-list-button ${article?.id === a.id ? 'active' : ''}" data-article="${esc(a.id)}" aria-pressed="${article?.id === a.id}"><span class="article-number">DOCUMENT ${String(i+1).padStart(2,'0')}</span><h3>${esc(a.title)}</h3><div class="meta"><span>${esc(a.source_name || '未声明来源')}</span><span>${date(a.published_at)}</span></div><div class="meta" style="margin-top:9px"><span>${number(textLength(a))} 字符</span><span>${a.questions?.length || 0} 道问题</span><span>${esc(({zh:'中文',en:'英语'})[a.language] || a.language || '未声明语言')}</span></div></button>`).join('') : empty('没有匹配的文章','试试其他关键词。')}</div>${article ? renderArticle(article) : ''}</div>`}`;
  }
  function renderArticle(a) {
    const paragraphs = (a.text || '').split(/\n\s*\n|\n/).filter((p) => p.trim());
    return `<article class="panel article-preview"><span class="eyebrow">原文与标注</span><h2>${esc(a.title)}</h2><div class="article-meta"><span>${esc(a.source_name || '未声明来源')}</span>${articleDateMetadata(a)}<span>${number(textLength(a))} 字符</span>${a.source_url ? extLink(a.source_url,'查看原始来源 ↗') : ''}</div><div class="article-body">${paragraphs.map((p,i) => `<div class="article-paragraph"><span class="paragraph-number" aria-hidden="true">${String(i+1).padStart(2,'0')}</span><p>${esc(p)}</p></div>`).join('')}</div><div class="footer-hint">${a.scope ? `文本范围：${esc(({excerpt:'节选',full:'全文'})[a.scope] || a.scope)} · ` : ''}${a.license ? `许可声明：${esc(a.license)}` : '许可未声明'}${a.sha256 ? `<br><span class="mono">SHA-256 ${esc(a.sha256)}</span>` : ''}</div><section class="question-section"><div class="section-heading"><h3>阅读问题与标准答案</h3><span class="muted small">${a.questions?.length || 0} 题</span></div>${(a.questions || []).map((q,i) => `<details class="question-card" ${i === 0 ? 'open' : ''}><summary><span class="badge ${q.type === 'unanswerable' ? 'badge-gold' : ''}">${esc(typeLabel(q.type))}</span><span>${esc(questionText(q))}</span></summary><div class="question-answer"><div class="answer-block"><span class="answer-label">标准答案</span><span>${esc(reference(q))}</span></div><div class="answer-block"><span class="answer-label">文章证据</span><blockquote class="evidence-text">${esc(evidence(q) || (q.type === 'unanswerable' ? '文章中没有足以回答该问题的证据。' : '未记录证据'))}</blockquote></div>${q.answers?.length > 1 ? `<div class="answer-block muted">接受的答案表达：${esc(q.answers.join(' / '))}</div>` : ''}<div class="answer-block muted">${q.reviewed ? '已做来源核对' : '待来源核对'}${q.review_note ? ` · ${esc(q.review_note)}` : ''}</div></div></details>`).join('')}</section></article>`;
  }
  function filteredCandidates() {
    return (state.workspace?.articles || []).filter((a) => (state.candidateLanguage === 'all' || a.language === state.candidateLanguage) && (state.candidateProvider === 'all' || a.provider === state.candidateProvider));
  }
  function selectWorkspaceCandidate() {
    const articles = filteredCandidates();
    if (!articles.some((a) => a.id === state.selectedCandidate)) state.selectedCandidate = articles[0]?.id || '';
    if (state.selectedCandidate && state.candidateDetail?.id !== state.selectedCandidate) loadCandidate(state.selectedCandidate);
    else render();
  }
  async function loadCandidate(identity) {
    const generation = ++candidateGeneration;
    state.candidateLoading = true; state.candidateError = ''; render();
    try {
      const data = await api(`/api/corpus-workspace/articles/${encodeURIComponent(identity)}`);
      if (generation !== candidateGeneration || state.selectedCandidate !== identity) return;
      state.candidateDetail = data;
    } catch (error) { if (generation === candidateGeneration) state.candidateError = error.message; }
    finally { if (generation === candidateGeneration) { state.candidateLoading = false; if (state.route === 'workspace') render(); } }
  }
  function renderWorkspace() {
    const data = state.workspace;
    const counts = data?.counts || {};
    const articles = filteredCandidates();
    const providers = [...new Map((data?.articles || []).map((a) => [a.provider,a.source_name])).entries()];
    const stages = [['candidate','正文、日期与许可待审'],['ai_checked','辅助检查完成，人工仍需复核'],['human_reviewed','有独立人工审题记录'],['frozen','锁定正文、题目与划分版本']];
    return `${heading('BILINGUAL BENCHMARK WORKSPACE','题库建设','中英文各半、分别报告。先建立可审查的真实文章池，再锁定题目与标准答案。','<button class="button button-secondary" type="button" data-action="refresh-workspace">'+svg('refresh')+'刷新采集进度</button>')}
      <section class="panel benchmark-target"><div><span class="eyebrow">正式设计目标</span><h2>120 篇文章 · 中文 60 / 英文 60</h2><p>开发集 20 篇（各 10） · 正式测试集 100 篇（各 50）<br>每篇计划 8 题：6 道可回答题、2 道信息不足题；目标 960 题，尚未完成标注。</p></div><div class="target-count"><strong>${number(counts.downloaded)}</strong><span>已下载并核对 hash 的正文候选</span><small>中文 ${number(counts.language?.zh)} / 英文 ${number(counts.language?.en)} · 候选题目 ${number(counts.questions)} 道</small></div></section>
      <div class="stat-grid workspace-stages">${stages.map(([key,note]) => stat(annotationLabels[key],number(counts.states?.[key]),note,'workspace','篇')).join('')}</div>
      <div class="notice">${esc(data?.notice || '候选正文尚未采集完成。')}<br><strong>当前可运行正式候选 ${number(counts.runnable)} 篇。</strong>候选不会自动进入测评实验；正文、题目和证据审定后才可冻结入库。</div>
      ${(data?.warnings || []).length ? `<div class="notice error workspace-warning">${data.warnings.map(esc).join('<br>')}</div>` : ''}
      <div class="workspace-toolbar"><label class="field">阅读语言<select id="candidate-language"><option value="all" ${state.candidateLanguage === 'all' ? 'selected' : ''}>中文与英文</option><option value="zh" ${state.candidateLanguage === 'zh' ? 'selected' : ''}>中文</option><option value="en" ${state.candidateLanguage === 'en' ? 'selected' : ''}>英文</option></select></label><label class="field">来源机构<select id="candidate-provider"><option value="all">全部来源</option>${providers.map(([key,label]) => `<option value="${esc(key)}" ${state.candidateProvider === key ? 'selected' : ''}>${esc(label || key)}</option>`).join('')}</select></label><span class="muted small">筛选结果 ${number(articles.length)} 篇 · 来源 / 领域 / 体裁仍需人工审定</span></div>
      ${articles.length ? `<div class="library-layout workspace-library"><div class="article-list">${articles.map((a) => `<button type="button" class="article-list-button ${a.id === state.selectedCandidate ? 'active' : ''}" data-candidate="${esc(a.id)}" aria-pressed="${a.id === state.selectedCandidate}"><span class="article-number">${esc(annotationLabels[a.annotation_status] || '待审候选')} · ${esc(a.language === 'zh' ? '中文' : '英文')}</span><h3>${esc(a.title)}</h3><div class="meta"><span>${esc(a.source_name)}</span><span>${date(a.published_at)}</span></div><div class="meta" style="margin-top:9px"><span>${a.language === 'en' ? `${number(a.word_count)} 单词` : `${number(a.han_count)} 汉字`}</span><span>${a.hash_verified ? '正文 hash 已核对' : '正文待检查'}</span></div></button>`).join('')}</div><div>${state.candidateLoading ? '<div class="panel loading-screen"><span class="spinner"></span><span>正在读取已下载正文…</span></div>' : state.candidateError ? `<div class="panel">${empty('正文读取失败',state.candidateError)}</div>` : state.candidateDetail?.id === state.selectedCandidate ? renderCandidate(state.candidateDetail) : '<div class="panel">选择一篇候选文章查看。</div>'}</div></div>` : `<div class="panel">${empty('当前筛选下没有正文候选','采集完成后刷新，或选择其他语言与来源。')}</div>`}
      <p class="footer-hint">${(data?.pools || []).map((p) => `${esc(p.name)}：${p.status === 'collecting' ? '仍在采集中' : '采集清单已保存'}`).join(' · ')}</p>`;
  }
  function renderCandidate(a) {
    return `<article class="panel article-preview candidate-preview"><span class="badge badge-neutral">${esc(annotationLabels[a.annotation_status] || '待审候选')} · 不能直接运行正式测评</span><h2>${esc(a.title)}</h2><div class="article-meta"><span>${esc(a.source_name)}</span><span>${esc(a.language === 'zh' ? '中文' : '英文')}</span><span>官网发布日期 ${date(a.published_at)}</span>${a.first_published_at ? `<span>官网明确首发 ${date(a.first_published_at)}</span>` : '<span>更早首发 / 转载仍待核查</span>'}${extLink(a.source_url,'核对原始来源 ↗')}</div><div class="candidate-provenance"><details><summary>日期证据与采集信息</summary><dl class="model-info"><dt>日期字段</dt><dd>${esc(a.date_evidence?.field || a.date_evidence?.kind || '未声明')}</dd><dt>原始值</dt><dd>${esc(a.date_evidence?.value || '未声明')}</dd><dt>日期说明</dt><dd>${esc(a.date_review_note)}</dd><dt>采集时间</dt><dd>${date(a.downloaded_at,true)}</dd><dt>正文范围</dt><dd>机构正文选择器抽取，尚需清理图注和相关内容</dd><dt>抽取规则</dt><dd>${esc(a.extraction_selector)}</dd><dt>领域建议</dt><dd>${esc(a.domain_provisional)}</dd><dt>体裁建议</dt><dd>${esc(a.genre_provisional)}</dd><dt>正文 hash</dt><dd class="mono">${esc(a.sha256)}</dd><dt>原始快照 hash</dt><dd class="mono">${esc(a.raw_sha256)}</dd></dl></details></div><div class="article-body">${(a.paragraphs || []).map((p) => `<div class="article-paragraph"><span class="paragraph-number" aria-hidden="true">${esc(p.id)}</span><p>${esc(p.text)}</p></div>`).join('')}</div><p class="footer-hint">${esc(a.paragraph_note)}</p><div class="notice candidate-rights"><strong>许可状态：待逐篇复核</strong><br>${esc(a.rights || '来源尚未声明许可；不能视为可公开分发。')}</div><p class="footer-hint">${esc(a.review_note)}<br>当前问题数：${number(a.questions_count)}。下载正文不等于已编题，也不等于已完成独立人工审题。</p></article>`;
  }
  function selectedQuestionCount() {
    const available = state.articles.filter((a) => state.selectedArticles.has(a.id)).reduce((n,a) => n + (a.questions?.length || 0),0);
    return Math.min(available, Math.max(0, Number(state.config.question_limit) || 0));
  }
  function temporalWarning() {
    if (!state.config.strict_time) return '时间门槛已关闭。这次实验可用于连通性检查，不能作为时间隔离实验报告。';
    const selected = state.models.filter((m) => state.selectedModels.has(m.id));
    const unverified = selected.filter((m) => !m.temporal_verified);
    if (unverified.length) return `${unverified.map((m) => m.name).join('、')} 的日期或版本门槛未通过。请在模型管理中核查；服务器将拒绝不符合门槛的严格实验。`;
    const dates = state.articles.filter((a) => state.selectedArticles.has(a.id)).map((a) => new Date(a.temporal_date || a.published_at).getTime());
    const invalid = selected.filter((m) => dates.some((d) => !Number.isFinite(d) || new Date(m.release_date).getTime() >= d));
    if (invalid.length) return `${invalid.map((m) => m.name).join('、')} 的发布日期不早于全部所选文章。请更换模型或文章。`;
    return '时间门槛会核对固定的模型版本和发布日期。通过门槛不等于证明完全没有训练数据污染。';
  }
  function renderExperiment() {
    const count = selectedQuestionCount(); const models = state.selectedModels.size; const calls = count * models;
    return `${heading('EXPERIMENT DESIGN','测评实验','先锁定模型与题库，再运行一场可复现的比较。')}
      <div class="experiment-grid"><div class="panel setup-panel"><section class="setup-section"><div class="step-heading"><span class="step-number">01</span><div><h3>选择参与的模型</h3><p>同一题目分别提交给每个模型，独立保存回答。</p></div></div>${state.models.length ? `<div class="option-grid">${state.models.map((m) => `<label class="model-option"><input type="checkbox" data-model-choice="${esc(m.id)}" ${state.selectedModels.has(m.id) ? 'checked' : ''} ${!m.available ? 'disabled' : ''}><span class="option-content"><span class="option-title">${esc(m.name)}</span><span class="option-meta" style="display:block">${esc(m.model)}<br>发布日 ${date(m.release_date)}</span>${modelBadge(m)}</span></label>`).join('')}</div><p class="footer-hint"><a href="#models">管理模型与连接配置 →</a></p>` : empty('还没有配置模型','添加服务器上的 Ollama 或 OpenAI 兼容模型后即可开始。','<a class="button button-secondary button-small" href="#models">添加模型</a>','models')}</section>
      <section class="setup-section"><div class="step-heading"><span class="step-number">02</span><div><h3>选择阅读材料</h3><p>标准答案只用于评分，调用模型时不会发送答案。</p></div></div>${state.articles.length ? `<div class="article-options">${state.articles.map((a) => `<label class="article-option"><input type="checkbox" data-article-choice="${esc(a.id)}" ${state.selectedArticles.has(a.id) ? 'checked' : ''}><span class="option-content"><span class="option-title">${esc(a.title)}</span><span class="option-meta" style="display:block">${esc(a.source_name)} · 网页 ${date(a.published_at)} · 门槛 ${date(a.temporal_date || a.published_at)}</span></span><span class="article-count">${a.questions?.length || 0} 题</span></label>`).join('')}</div>` : empty('题库尚未准备好','先导入文章与经过复核的问题。','<a class="button button-secondary button-small" href="#library">查看题库</a>')}</section>
      <section class="setup-section"><div class="step-heading"><span class="step-number">03</span><div><h3>设置实验条件</h3><p>可用无上下文组检查模型是否已经知道答案。</p></div></div><div class="segment" aria-label="实验模式"><button type="button" data-mode="with_context" aria-pressed="${state.config.mode === 'with_context'}">提供文章<span>阅读理解测评</span></button><button type="button" data-mode="no_context" aria-pressed="${state.config.mode === 'no_context'}">无上下文对照<span>只提供问题</span></button></div><p class="mode-description">${state.config.mode === 'with_context' ? '模型将收到文章与问题，并需返回回答、原文证据、置信度和拒答标记。' : '模型只收到问题。这是污染检查的辅助信号；无上下文答对也可能来自一般知识或推理，不能单独证明训练污染。'}</p><div class="toggle-row"><div class="toggle-copy"><strong>启用严格时间门槛</strong><p>固定模型版本，并要求模型发布日早于每篇文章。</p></div><label class="switch"><input type="checkbox" id="strict-time" ${state.config.strict_time ? 'checked' : ''} aria-label="启用严格时间门槛"><span class="switch-track" aria-hidden="true"></span></label></div><div class="field-grid"><label class="field">每模型总题目上限<input id="question-limit" data-config="question_limit" type="number" min="1" max="200" step="1" value="${esc(state.config.question_limit)}"><small>按文章选择顺序取题，演示建议 4 题</small></label><label class="field">Temperature<input data-config="temperature" type="number" min="0" max="1" step="0.1" value="${esc(state.config.temperature)}"><small>0 便于比较与复现</small></label><label class="field">最大输出 Token<input data-config="max_tokens" type="number" min="64" max="2048" step="64" value="${esc(state.config.max_tokens)}"><small>建议 512，证据过长可能截断</small></label></div></section></div>
      <aside class="panel launch-panel"><span class="eyebrow">实验预览</span><h2>准备好，开始阅读。</h2><div class="launch-summary"><div class="summary-row"><span>参与模型</span><strong>${models} 个</strong></div><div class="summary-row"><span>阅读材料</span><strong>${state.selectedArticles.size} 篇</strong></div><div class="summary-row"><span>每个模型的问题</span><strong>${count} 题</strong></div><div class="summary-row"><span>实验模式</span><strong>${state.config.mode === 'no_context' ? '无上下文对照' : '提供文章'}</strong></div><div class="summary-row total"><span>真实模型调用</span><strong>${calls}<span class="small muted"> 次</span></strong></div></div><button class="button button-primary" type="button" data-action="launch" ${state.busy || !calls ? 'disabled' : ''}>${state.busy ? '<span class="spinner"></span>正在创建…' : `${svg('play')}开始测评 ${svg('arrow')}`}</button><div class="notice">${esc(temporalWarning())}</div><p class="launch-footnote">耗时取决于模型规模与服务器性能。运行期间可查看逐题回答，也可随时请求取消后续调用。</p></aside></div>
      <section class="history-section"><div class="section-heading"><h2>实验记录</h2><button class="button button-small button-quiet" type="button" data-action="refresh-runs">${svg('refresh')}刷新记录</button></div><div class="panel" style="padding:8px 10px">${runRows(state.runs)}</div></section>`;
  }
  function updateLaunchPreview() {
    const panel = $('.launch-panel');
    if (!panel) return;
    const count = selectedQuestionCount(), calls = count * state.selectedModels.size;
    const values = panel.querySelectorAll('.summary-row strong');
    if (values.length >= 5) { values[0].textContent = `${state.selectedModels.size} 个`; values[1].textContent = `${state.selectedArticles.size} 篇`; values[2].textContent = `${count} 题`; values[3].textContent = state.config.mode === 'no_context' ? '无上下文对照' : '提供文章'; values[4].innerHTML = `${calls}<span class="small muted"> 次</span>`; }
    $('[data-action="launch"]',panel).disabled = state.busy || !calls;
    $('.notice',panel).textContent = temporalWarning();
  }
  async function launchRun() {
    if (state.busy) return;
    if (!state.selectedModels.size || !selectedQuestionCount()) { toast('请至少选择一个模型和一篇有题目的文章。',true); return; }
    if (!Number.isInteger(Number(state.config.question_limit)) || state.config.question_limit < 1 || state.config.question_limit > 200) { toast('每模型总题目上限必须是 1–200 的整数。',true); return; }
    if (!Number.isInteger(Number(state.config.max_tokens)) || state.config.max_tokens < 64 || state.config.max_tokens > 2048 || !Number.isFinite(state.config.temperature) || state.config.temperature < 0 || state.config.temperature > 1) { toast('输出 Token 须为 64–2048 的整数，Temperature 须在 0–1 之间。',true); return; }
    state.busy = true; render();
    try {
      const data = await api('/api/runs',{method:'POST',body:JSON.stringify({...state.config,model_ids:[...state.selectedModels],article_ids:[...state.selectedArticles]})});
      if (!data.id) throw new Error('服务器没有返回实验编号。');
      location.hash = `run:${data.id}`;
      toast('实验已创建。正在等待真实模型回答。');
    } catch (error) { toast(error.message,true); }
    finally { state.busy = false; if (state.route === 'experiment') render(); }
  }
  async function loadBank(id) {
    const generation = ++bankGeneration;
    state.bankLoading = true; state.bankError = '';
    if (state.route === 'v2experiment') render();
    try {
      const payload = await api(`/api/v2/banks/${encodeURIComponent(id)}`);
      if (generation !== bankGeneration || id !== state.bankId) return;
      const bank = payload.bank || payload;
      const changed = state.bank?.id !== id;
      state.bank = {...bank,id};
      if (changed) { state.v2Articles = new Set((bank.articles || []).map((a) => a.id)); state.v2Article = bank.articles?.[0]?.id || ''; state.v2DraftAccepted = false; state.v2Config.strict_budget = !!bank.formal_eligible; state.v2Config.strict_time = !isPublicReference(bank); }
      constrainV2Context();
    } catch (error) { if (generation === bankGeneration) { state.bank = null; state.bankError = error.message; } }
    finally { if (generation === bankGeneration) { state.bankLoading = false; if (state.route === 'v2experiment') render(); } }
  }
  const kindLabels = {choice:'选择题',short:'短答案',numeric:'数值题',unanswerable:'信息不足题'};
  const dimensionLabels = {D1:'事实定位',D2:'语义与条件',D3:'跨句整合',D4:'数量与时间',D5:'主旨与结构',D6:'信息边界'};
  function v2Reference(q) {
    if (q.kind === 'choice') return `${q.correct_option || '—'}${q.options?.[q.correct_option] ? ' · ' + q.options[q.correct_option] : ''}`;
    if (q.kind === 'numeric') return `${q.value ?? '—'} ${q.unit || ''}`;
    if (q.kind === 'unanswerable') return `应拒答：${q.missing_information || '文章缺少所需信息。'}`;
    return q.answers?.join(' / ') || '未提供参考答案';
  }
  function v2QuestionCount() {
    const available = (state.bank?.articles || []).filter((a) => state.v2Articles.has(a.id)).reduce((n,a) => n + (a.questions?.length ?? a.question_count ?? 0),0);
    return Math.min(available, Math.max(0, Number(state.v2Config.question_limit) || 0));
  }
  function v2CanLaunch() {
    const nativeLimit = v2NativeContextLimit();
    return !state.busy && !state.bankLoading && !!state.bank && state.bank.id === state.bankId && state.v2Models.size > 0 && v2QuestionCount() > 0 && [4096,8192].includes(state.v2Config.num_ctx) && (nativeLimit === null || state.v2Config.num_ctx <= nativeLimit) && (state.bank.formal_eligible || state.v2DraftAccepted);
  }
  function v2TemporalWarning() {
    if (isPublicReference(state.bank)) return state.v2Config.strict_time ? '公开旧题早于被测历史模型，严格时间门槛通常会拒绝；请关闭时间门槛，仅作公开参考。' : '公开历史参考：时间隔离不适用，可能已被模型训练见过；不纳入近期隐藏测试或无污染结论。';
    if (!state.v2Config.strict_time) return '时间门槛关闭，仅适合明确标记的开发诊断。';
    const selected = state.models.filter((m) => state.v2Models.has(m.id));
    const unchecked = selected.filter((m) => !m.temporal_verified);
    if (unchecked.length) return `${unchecked.map((m) => m.name).join('、')} 的版本或日期尚未通过门槛，后端会拒绝不合格的严格运行。`;
    return '固定模型版本，并核对模型发布早于文章。日期门槛通过仍不能证明完全没有训练污染。';
  }
  function renderV2Experiment() {
    const bank = state.bank, articles = bank?.articles || [];
    const count = v2QuestionCount(), calls = count * state.v2Models.size;
    const formal = !!bank?.formal_eligible, publicReference = isPublicReference(bank);
    const article = articles.find((a) => a.id === state.v2Article) || articles[0];
    return `${heading('READING EXPERIMENT V2','新版实验（开发）','用实际模型回答验证答案、证据和信息边界；中英文分别报告。','<button type="button" class="button button-secondary" data-action="refresh-banks">'+svg('refresh')+'刷新题库与模型</button>')}
      <div class="notice v2-status-notice"><strong>${publicReference ? '公开历史参考，可能已被模型训练见过' : formal ? '当前题库已通过冻结契约检查' : '当前是开发诊断，不能作为正式排名'}</strong><br>${publicReference ? '答案来自原始公开标注，本项目尚未独立人工复核；证据由答案 span 机械映射，仅作辅助，不是人审支持链。' : 'AI 初审和评分器检查不能代替独立人工审题。现有 v1 历史记录仍保留原评分方式。'}</div>
      ${state.bankError ? `<div class="notice error" role="alert">题库读取失败：${esc(state.bankError)}</div>` : ''}
      <div class="experiment-grid v2-experiment"><div class="panel setup-panel"><section class="setup-section"><div class="step-heading"><span class="step-number">01</span><div><h3>选择题库与文章</h3><p>模型调用不发送参考答案；实验保存使用时的正文与金标快照。</p></div></div><label class="field">版本化题库<select id="v2-bank" ${state.bankLoading ? 'disabled' : ''}>${state.banks.length ? state.banks.map((b) => `<option value="${esc(b.id)}" ${state.bankId === b.id ? 'selected' : ''}>${esc(b.id)} · ${esc(b.bank_version || '')}${isPublicReference(b) ? ' · 公开历史参考' : b.formal_eligible ? ' · 已冻结' : ' · 开发草稿'}</option>`).join('') : '<option value="">尚无新版题库</option>'}</select></label>
      ${state.bankLoading ? '<div class="v2-loading"><span class="spinner"></span>正在读取正文与标注…</div>' : bank ? `<div class="v2-bank-meta"><span class="mono">${esc(bank.bank_version)}</span><span>${articles.length} ${publicReference ? '参考篇章' : '篇'} · 中文 ${articles.filter((a) => a.language === 'zh').length} / 英文 ${articles.filter((a) => a.language === 'en').length}${publicReference ? ' · 源标题簇 '+new Set(articles.map((a) => a.source_cluster_id)).size : ''}</span></div><p class="footer-hint">${esc(bank.note || bank.notice || '')}</p><div class="article-options">${articles.map((a) => `<label class="article-option"><input type="checkbox" data-v2-article="${esc(a.id)}" ${state.v2Articles.has(a.id) ? 'checked' : ''}><span class="option-content"><span class="option-title">${esc(a.title)}</span><span class="option-meta" style="display:block">${a.language === 'zh' ? '中文' : '英文'} · ${esc(a.split || '未划分')} · ${esc(isPublicReference(a) ? '原始公开标注 · 项目未复核' : annotationLabels[a.annotation_state] || a.annotation_state || '待审')} · 项目人审 ${number(a.human_review_count)} 人</span></span><span class="article-count">${a.questions?.length ?? a.question_count ?? 0} 题</span></label>`).join('')}</div>${!formal ? `<label class="v2-draft-consent"><input id="v2-allow-draft" type="checkbox" ${state.v2DraftAccepted ? 'checked' : ''}><span>${publicReference ? '允许运行公开历史参考。原题可能已训练见过，本项目未复核；span 代理证据仅辅助，不作为正式金标或排名。' : '允许运行 AI 草稿。结果仅用于开发诊断，不能视作人工审定的正式金标或模型排名。'}</span></label>` : ''}` : empty('还没有新版题库','完成版本化的正文、题目和段落证据标注后，再运行实验。')}
      </section><section class="setup-section"><div class="step-heading"><span class="step-number">02</span><div><h3>选择模型</h3><p>使用服务器真实接口；未连接的模型不可选择。</p></div></div>${state.models.length ? `<div class="option-grid">${state.models.map((m) => `<label class="model-option"><input type="checkbox" data-v2-model="${esc(m.id)}" ${state.v2Models.has(m.id) ? 'checked' : ''} ${!m.available ? 'disabled' : ''}><span class="option-content"><span class="option-title">${esc(m.name)}</span><span class="option-meta" style="display:block">${esc(m.model)} · ${date(m.release_date)} · 原生上下文 ${m.native_context_tokens ? number(m.native_context_tokens)+' Tokens' : '未登记'}</span>${modelBadge(m)}</span></label>`).join('')}</div>` : empty('需要连接模型','在模型管理配置真实推理服务。','<a class="button button-small button-secondary" href="#models">模型管理</a>','models')}
      </section><section class="setup-section"><div class="step-heading"><span class="step-number">03</span><div><h3>设置运行条件</h3><p>问题上限针对每个模型；失败和未完成问题保留在计划分母。</p></div></div><div class="segment"><button type="button" data-v2-mode="with_context" aria-pressed="${state.v2Config.mode === 'with_context'}">提供文章<span>答案与证据</span></button><button type="button" data-v2-mode="no_context" aria-pressed="${state.v2Config.mode === 'no_context'}">无文章对照<span>答案诊断</span></button></div><p class="mode-description">${state.v2Config.mode === 'no_context' ? '无文章对照允许利用已知知识作答；证据成绩不用于与阅读组比较。答对本身不能证明训练污染。' : '提交完整选定文本与问题；模型返回答案、段落 ID、置信度、拒答标记。'}</p><div class="field-grid"><label class="field">每模型题目上限<input type="number" id="v2-question-limit" data-v2-config="question_limit" min="1" max="5000" step="1" value="${esc(state.v2Config.question_limit)}"><small>按题库原始顺序取题，支持未来完整 800 题测试</small></label><label class="field">Temperature<input type="number" data-v2-config="temperature" min="0" max="1" step="0.1" value="${esc(state.v2Config.temperature)}"><small>默认 0，减少随机波动</small></label><label class="field">最大输出 Token<input type="number" data-v2-config="max_tokens" min="64" max="2048" step="64" value="${esc(state.v2Config.max_tokens)}"><small>默认 512；保持比较条件一致</small></label><label class="field">实验上下文窗口<select id="v2-num-ctx" data-v2-config="num_ctx">${[4096,8192].map((n) => `<option value="${n}" ${state.v2Config.num_ctx === n ? 'selected' : ''} ${v2NativeContextLimit() !== null && n > v2NativeContextLimit() ? 'disabled' : ''}>${number(n)} Tokens</option>`).join('')}</select><small id="v2-context-note">${esc(v2ContextExplanation())}</small></label></div><div class="toggle-row"><div class="toggle-copy"><strong>严格时间门槛</strong><p>校验固定模型版本和文章日期。</p></div><label class="switch"><input id="v2-strict-time" type="checkbox" ${state.v2Config.strict_time ? 'checked' : ''} aria-label="新版严格时间门槛"><span class="switch-track"></span></label></div><div class="toggle-row"><div class="toggle-copy"><strong>精确输入预算</strong><p>要求使用匹配 tokenizer 与原生模板，不能用估算代替；正式运行需开启。</p></div><label class="switch"><input id="v2-strict-budget" type="checkbox" ${state.v2Config.strict_budget ? 'checked' : ''} ${formal ? 'disabled' : ''} aria-label="要求精确输入预算"><span class="switch-track"></span></label></div></section></div>
      <aside class="panel launch-panel v2-launch-panel"><span class="eyebrow">真实运行预览</span><h2>${publicReference ? '检验公开参考任务。' : formal ? '使用冻结题库。' : '先验证开发流程。'}</h2><div class="launch-summary"><div class="summary-row"><span>参与模型</span><strong>${state.v2Models.size} 个</strong></div><div class="summary-row"><span>文章</span><strong>${state.v2Articles.size} 篇</strong></div><div class="summary-row"><span>每模型题目</span><strong>${count} 题</strong></div><div class="summary-row"><span>评分身份</span><strong>${publicReference ? '公开历史参考' : formal ? '冻结契约' : 'AI 草稿诊断'}</strong></div><div class="summary-row total"><span>真实请求</span><strong>${calls}<span class="small muted"> 次</span></strong></div></div><button class="button button-primary" data-action="launch-v2" type="button" ${v2CanLaunch() ? '' : 'disabled'}>${state.busy ? '<span class="spinner"></span>正在创建…' : svg('play')+'运行新版实验'}</button><div class="notice v2-temporal">${esc(v2TemporalWarning())}</div><p class="launch-footnote">${!formal && !state.v2DraftAccepted ? (publicReference ? '勾选公开参考说明后才能运行。' : '勾选草稿诊断说明后才能运行。') : '保存逐题日志，可取消后续调用；续跑只提交未完成题。'} 不自动下载模型或启动实验。</p></aside></div>
      ${article ? `<section class="panel v2-material-panel"><div class="panel-header"><div><h2>${publicReference ? '公开篇章与原始参考标注' : '开发材料与参考标注'}</h2><p>参考答案只在界面和评分端显示。</p></div></div><label class="field">查看文章<select id="v2-preview-article">${articles.map((a) => `<option value="${esc(a.id)}" ${article.id === a.id ? 'selected' : ''}>${esc(a.title)}</option>`).join('')}</select></label>${renderV2Article(article,'v2-preview',true)}</section>` : ''}
      <section class="history-section"><div class="section-heading"><h2>新版实验记录</h2><button type="button" class="button button-small button-quiet" data-action="refresh-runs">${svg('refresh')}刷新记录</button></div><div class="panel" style="padding:8px 10px">${runRows(state.runs.filter((r) => r.protocol === 'reading-experiment-v2'))}</div></section>`;
  }
  function renderV2Article(a, prefix, includeQuestions = false) {
    return `<div class="v2-article"><h3>${esc(a.title)}</h3><div class="article-meta"><span>${a.language === 'zh' ? '中文' : '英文'}</span><span>${isPublicReference(a) ? '数据文件版本日' : '发布日期'} ${date(a.published_at)}</span><span>${esc(a.synthetic ? '合成改文诊断' : isPublicReference(a) ? '完整原始参考篇章' : ({excerpt:'节选',full:'全文'})[a.scope] || a.scope || '未声明文本范围')}</span>${a.source_url ? extLink(a.source_url,'来源 ↗') : ''}</div><div class="article-body">${(a.paragraphs || []).map((p) => `<div class="article-paragraph v2-paragraph" id="${esc(prefix+'-'+p.id)}"><span class="paragraph-number">${esc(p.id)}</span><p>${esc(p.text)}</p></div>`).join('')}</div><p class="footer-hint">${esc(a.scope_note || '')}${a.presented_text_sha256 ? '<br>呈现文本 SHA-256 <span class="mono">'+esc(a.presented_text_sha256)+'</span>' : ''}</p>${includeQuestions ? `<div class="question-section"><h3>${isPublicReference(a) ? '题目与原始公开参考答案' : '题目与草稿参考答案'} · ${a.questions?.length || 0} 题</h3>${(a.questions || []).map((q) => `<details class="question-card"><summary><span class="badge">${esc(kindLabels[q.kind] || q.kind)}</span><span>${esc(q.prompt)}</span></summary><div class="question-answer"><div class="meta"><span>${esc(dimensionLabels[q.dimension] || q.dimension)}</span><span class="mono">${esc(q.id)}</span><span>人审 ${q.human_reviews?.length || 0} 条</span></div>${q.options ? `<dl class="v2-options">${Object.entries(q.options).map(([k,v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>` : ''}<div class="answer-block"><span class="answer-label">${isPublicReference(q) ? '原始公开参考答案 · 项目未复核' : '参考答案'}</span><span>${esc(v2Reference(q))}</span></div>${renderV2EvidenceAlternatives(q.evidence_sets || [],prefix,isEvidenceProxy(q) ? '答案 span 映射代理（点击定位）' : '参考证据（点击定位）',isEvidenceProxy(q))}<p class="footer-hint">${esc(q.rubric_note || '')}${q.kind === 'numeric' ? ' · 绝对容差 '+esc(q.absolute_tolerance || '0')+'；单位必须匹配' : ''}</p></div></details>`).join('')}</div>` : ''}</div>`;
  }
  function renderV2Evidence(ids, prefix, label) {
    const unique = Array.isArray(ids) ? [...new Set(ids)] : [];
    return `<div class="v2-evidence"><span class="answer-label">${esc(label)}</span><div class="v2-evidence-buttons">${unique.length ? unique.map((id) => `<button type="button" class="v2-evidence-link" data-v2-evidence="${esc(prefix+'-'+id)}">${esc(id)}</button>`).join('') : '<span class="muted small">无段落证据</span>'}</div></div>`;
  }
  function renderV2EvidenceAlternatives(sets, prefix, label, proxy = false) {
    if (proxy) return `<div class="v2-evidence-alternatives"><p class="muted small">仅按原始答案 span 映射的段落代理，未完成人审支持链核验；只作辅助诊断。</p>${Array.isArray(sets) && sets.length ? sets.map((ids,i) => renderV2Evidence(ids,prefix,sets.length > 1 ? `${label} · 第 ${i+1} 组` : label)).join('') : renderV2Evidence([],prefix,label)}</div>`;
    if (!Array.isArray(sets) || sets.length < 2) return renderV2Evidence(sets?.[0] || [],prefix,label);
    return `<div class="v2-evidence-alternatives"><p class="muted small">任一组完整支持链均可；同一组内须包含全部段落。</p>${sets.map((ids,i) => renderV2Evidence(ids,prefix,`${label} · 第 ${i+1} 组`)).join('')}</div>`;
  }
  function updateV2Preview() {
    const panel = $('.v2-launch-panel');
    if (!panel) return;
    const count = v2QuestionCount(), calls = count * state.v2Models.size;
    const values = panel.querySelectorAll('.summary-row strong');
    if (values.length >= 5) { values[0].textContent = `${state.v2Models.size} 个`; values[1].textContent = `${state.v2Articles.size} 篇`; values[2].textContent = `${count} 题`; values[4].innerHTML = `${calls}<span class="small muted"> 次</span>`; }
    $('[data-action="launch-v2"]',panel).disabled = !v2CanLaunch();
    $('.v2-temporal',panel).textContent = v2TemporalWarning();
    const contextSelect = $('#v2-num-ctx'), contextNote = $('#v2-context-note');
    if (contextSelect) {
      const nativeLimit = v2NativeContextLimit();
      for (const option of contextSelect.options) option.disabled = nativeLimit !== null && Number(option.value) > nativeLimit;
      contextSelect.value = String(state.v2Config.num_ctx);
    }
    if (contextNote) contextNote.textContent = v2ContextExplanation();
  }
  async function launchV2Run() {
    if (!v2CanLaunch()) return;
    const c = state.v2Config;
    if (![4096,8192].includes(c.num_ctx)) { toast('请选择 4096 或 8192 的实验上下文窗口。',true); return; }
    if (!Number.isInteger(c.question_limit) || c.question_limit < 1 || c.question_limit > 5000 || state.v2Models.size > 8) { toast('题目上限须为 1–5000 的整数，模型须为 1–8 个。',true); return; }
    if (!Number.isInteger(c.max_tokens) || c.max_tokens < 64 || c.max_tokens > 2048 || !Number.isFinite(c.temperature) || c.temperature < 0 || c.temperature > 1) { toast('输出 Token 须为 64–2048 的整数，Temperature 须在 0–1 之间。',true); return; }
    state.busy = true; render();
    try {
      const payload = {...c,strict_budget:state.bank.formal_eligible ? true : c.strict_budget,bank_id:state.bankId,model_ids:[...state.v2Models],article_ids:[...state.v2Articles],allow_draft:!state.bank.formal_eligible};
      const data = await api('/api/v2/runs',{method:'POST',body:JSON.stringify(payload)});
      if (!data.id) throw new Error('服务器未返回新版实验编号。');
      location.hash = `run:${data.id}`; toast('新版实验已创建，等待真实模型回答。');
    } catch (error) { toast(error.message,true); }
    finally { state.busy = false; if (state.route === 'v2experiment') render(); }
  }
  function stopPolling() { clearTimeout(pollTimer); pollTimer = null; pollGeneration++; }
  async function loadRun(id, polling = false) {
    const generation = pollGeneration;
    try {
      const run = await api(`/api/runs/${encodeURIComponent(id)}`);
      if (state.route !== 'run' || state.routeId !== id || generation !== pollGeneration) return;
      state.run = run; state.runLoading = false; state.runError = '';
      const index = state.runs.findIndex((r) => r.id === run.id);
      const snapshot = {...run}; delete snapshot.results;
      if (index >= 0) state.runs[index] = snapshot; else state.runs.unshift(snapshot);
      renderRunPreservingFocus();
      if (isActive(run)) pollTimer = setTimeout(() => loadRun(id,true),1500);
    } catch (error) {
      if (state.route !== 'run' || state.routeId !== id || generation !== pollGeneration) return;
      state.runLoading = false; state.runError = error.message;
      renderRunPreservingFocus();
      // A failed poll remains visible and can be retried explicitly.
    }
  }
  function renderRunPreservingFocus() {
    const activeId = document.activeElement?.id;
    const scroll = window.scrollY;
    renderNavigation();
    main.innerHTML = globalErrors() + renderRun();
    if (activeId) { const input = document.getElementById(activeId); if (input) input.focus({preventScroll:true}); }
    window.scrollTo({top:scroll,behavior:'instant'});
  }
  function mean(values) { const nums = values.filter((v) => v !== null && v !== undefined && Number.isFinite(Number(v))).map(Number); return nums.length ? nums.reduce((a,b) => a+b,0) / nums.length : null; }
  function renderRun() {
    if (!state.run) return `${heading('EXPERIMENT RECORD','实验详情',state.routeId)}${state.runError ? `<div class="notice error" role="alert">${esc(state.runError)}<div class="read-more"><button class="button button-secondary button-small" type="button" data-action="retry-run">重新读取实验</button></div></div>` : '<div class="loading-screen"><span class="spinner"></span><p>正在读取实验记录…</p></div>'}`;
    if (state.run.protocol === 'reading-experiment-v2') return renderV2Run();
    const run = state.run, config = run.config || {}, summary = run.summary || [], results = run.results || [];
    const done = Number(run.progress?.done || 0), total = Number(run.progress?.total || 0);
    const successes = summary.reduce((n,s) => n + Number(s.successful || 0),0);
    const errors = summary.reduce((n,s) => n + Number(s.errors || 0),0);
    const filtered = results.filter((r) => (state.resultModel === 'all' || r.model_id === state.resultModel) && (state.resultView === 'all' || (state.resultView === 'errors' ? !!r.error : !r.error && Number(r.metrics?.em) < 1)));
    const modelNames = (config.model_ids || []).map((id) => run.snapshots?.models?.find((m) => m.id === id)?.name || state.models.find((m) => m.id === id)?.name || id);
    const articleNames = (config.article_ids || []).map((id) => run.snapshots?.articles?.find((a) => a.id === id)?.title || state.articles.find((a) => a.id === id)?.title || id);
    return `<div class="page-heading run-header"><div><span class="eyebrow">EXPERIMENT RECORD</span><h1>每一道题，都有迹可循。</h1><div class="run-meta"><span class="mono">${esc(run.id)}</span><span>${date(run.created_at,true)}</span>${statusBadge(run.status)}</div><div class="run-meta"><span>${config.mode === 'no_context' ? '无上下文对照' : '提供文章'}</span><span>${config.strict_time ? '时间门槛已开启' : '时间门槛已关闭'}</span><span>Temperature ${esc(config.temperature ?? '—')}</span><span>Max Tokens ${esc(config.max_tokens ?? '—')}</span></div></div><div class="actions">${isActive(run) ? '<button class="button button-danger" type="button" data-action="cancel-run">取消后续调用</button>' : ''}<button class="button button-secondary button-small" type="button" data-export="json">${svg('download')}JSON</button><button class="button button-secondary button-small" type="button" data-export="csv">${svg('download')}CSV</button></div></div>
      ${state.runError ? `<div class="notice error" role="alert">${esc(state.runError)}<div class="read-more"><button class="button button-secondary button-small" type="button" data-action="retry-run">恢复读取</button></div></div>` : ''}${run.error ? `<div class="notice error run-error" role="alert">${esc(run.error)}</div>` : ''}
      <div class="progress-block"><div class="progress-top"><strong>${isActive(run) ? '正在调用模型并逐题评分' : statusNames[run.status] || '实验记录'}</strong><span>${done} / ${total} 次调用已记录</span></div><div class="progress-track" role="progressbar" aria-label="实验进度" aria-valuemin="0" aria-valuemax="${Math.max(1,total)}" aria-valuenow="${done}"><div class="progress-fill" style="width:${total ? Math.min(100,done / total * 100) : 0}%"></div></div></div>
      <div class="run-score-grid">${stat('已成功回答',number(successes),`${errors} 次调用错误`,'experiment','次')}${stat('平均答案 F1',pct(mean(summary.map((s) => s.f1))),'各模型均值；调用失败计 0 分','methodology')}${stat('平均证据 F1',pct(mean(summary.map((s) => s.evidence_f1))),'提供文章且有金标证据的已执行题','library')}${stat('平均响应时间',decimal(mean(summary.map((s) => s.mean_latency_s)),1),'各模型成功调用的平均单题耗时','clock','秒')}</div>
      <section class="panel"><div class="panel-header"><div><h2>模型表现对比</h2><p>答案 EM/F1 包含调用失败题（计 0 分）；尚未执行题不在分母。</p></div><span class="badge">${summary.length} 个模型</span></div>${summary.length ? renderSummary(summary) : empty('等待第一条模型回答','模型响应到达后，评分与逐题记录会自动出现。','','experiment')}<p class="metric-table-note">EM、F1、证据 F1 与拒答准确率越高越好；Brier 越低越好。证据 F1 仅统计提供文章且有金标证据的已执行题；拒答准确率仅统计有效响应，Brier 还要求有效置信度；响应时间仅统计成功调用。评测期间显示当前已执行题目的统计。</p></section>
      ${summary.some((s) => s.f1 !== null && s.f1 !== undefined) ? `<section class="panel chart-panel"><div class="panel-header"><div><h3>答案与证据，一起看</h3><p>统一 0–100% 尺度</p></div></div><div class="score-chart">${summary.map((s) => `<div class="score-chart-model"><h3>${esc(s.model_name || s.model_id)}</h3>${[['精确匹配',s.em],['答案 F1',s.f1],['证据 F1',s.evidence_f1]].map(([label,value]) => `<div class="chart-row"><span>${label}</span><div class="chart-track"><div class="chart-bar" style="width:${Number.isFinite(Number(value)) && value !== null ? Math.max(0,Math.min(100,Number(value) * 100)) : 0}%"></div></div><strong>${pct(value)}</strong></div>`).join('')}</div>`).join('')}</div></section>` : ''}
      <div class="result-toolbar"><h2>逐题阅读记录 <span class="muted small">${filtered.length} / ${results.length}</span></h2><div class="result-filters"><label class="sr-only" for="result-model">按模型筛选</label><select id="result-model"><option value="all">全部模型</option>${(config.model_ids || []).map((id) => `<option value="${esc(id)}" ${state.resultModel === id ? 'selected' : ''}>${esc(state.models.find((m) => m.id === id)?.name || id)}</option>`).join('')}</select><label class="sr-only" for="result-view">按结果筛选</label><select id="result-view"><option value="all" ${state.resultView === 'all' ? 'selected' : ''}>全部回答</option><option value="incorrect" ${state.resultView === 'incorrect' ? 'selected' : ''}>未精确匹配</option><option value="errors" ${state.resultView === 'errors' ? 'selected' : ''}>调用错误</option></select></div></div>
      ${filtered.length ? filtered.map(renderResult).join('') : `<div class="panel">${empty(results.length ? '没有符合筛选条件的记录' : '模型正在阅读',results.length ? '选择其他筛选条件查看回答。' : '成功回答和真实错误都会在这里显示。','','experiment')}</div>`}
      <details class="raw-details" data-detail="run-config" ${state.openDetails.has('run-config') ? 'open' : ''}><summary>实验材料与完整配置</summary><pre>${esc(JSON.stringify({models:modelNames,articles:articleNames,config},null,2))}</pre></details>`;
  }
  const v2MetricDefinitions = [
    ['choice_accuracy','选择题 ACC','choice'],['short_em','短答 EM','short'],['short_token_f1','短答 F1','short'],['numeric_strict_accuracy','数值严格 ACC','numeric'],
    ['evidence_exact_answerable','证据 EM','answerable'],['evidence_f1_answerable','证据 F1','answerable'],['correct_refusal_rate','正确拒答 ↑','unanswerable'],
    ['unanswerable_substantive_rate','缺信息误答 ↓','unanswerable'],['false_refusal_rate','可答题误拒 ↓','answerable']
  ];
  function v2MetricDenominator(summary, kind) {
    if (kind === 'answerable') return summary.answerable_questions;
    if (kind === 'unanswerable') return summary.unanswerable_questions;
    return summary.by_question_kind?.[kind]?.planned_questions;
  }
  function v2MetricCell(summary, key, kind, noContext) {
    if (noContext && key.startsWith('evidence_')) return '<td class="numeric muted">不适用</td>';
    const raw = summary.primary_metrics?.[key];
    const value = typeof raw === 'object' && raw !== null ? raw.value : raw;
    const n = typeof raw === 'object' && raw !== null && raw.n !== undefined ? raw.n : v2MetricDenominator(summary,kind);
    return `<td class="numeric">${pct(value)}<small>计划 N ${n === undefined ? '—' : number(n)}</small></td>`;
  }
  function renderV2LanguageSummary(run, language) {
    const evaluation = run.evaluation || {}, summaries = evaluation.summaries || {};
    const ids = run.config?.model_ids || Object.keys(summaries);
    const noContext = run.config?.mode === 'no_context';
    const publicReference = isPublicReference(run.snapshots?.bank);
    const label = language === 'zh' ? '中文' : '英文';
    const activeModels = ids.filter((id) => summaries[id]?.[language]?.planned_questions);
    return `<section class="panel v2-language-panel"><div class="panel-header"><div><span class="eyebrow">${language === 'zh' ? 'CHINESE' : 'ENGLISH'} · 分语言报告</span><h2>${label}阅读表现</h2><p>各题型使用自己的计划分母；没有适用题显示“—”。</p></div></div>${activeModels.length ? `<div class="table-wrap"><table class="data-table v2-metric-table"><thead><tr><th>模型 / 完成情况</th>${v2MetricDefinitions.map(([,title]) => `<th class="numeric">${esc(publicReference ? title.replace('证据','代理证据') : title)}</th>`).join('')}</tr></thead><tbody>${activeModels.map((id) => {
      const summary = summaries[id][language];
      const recorded = (run.results || []).filter((r) => r.model_id === id && r.language === language);
      const errors = recorded.filter((r) => r.error || r.metrics?.error).length;
      const name = run.snapshots?.models?.find((m) => m.id === id)?.name || state.models.find((m) => m.id === id)?.name || id;
      return `<tr><td><strong>${esc(name)}</strong><small>已记录 ${recorded.length} / ${number(summary.planned_questions)} 题</small><small>调用 / 格式错误 ${errors} · 尚未记录 ${Math.max(0,Number(summary.planned_questions) - recorded.length)}</small></td>${v2MetricDefinitions.map(([key,,kind]) => v2MetricCell(summary,key,kind,noContext)).join('')}</tr>`;
    }).join('')}</tbody></table></div><p class="metric-table-note">短答 F1：中文按字符、英文按词进行本项目规范化。${publicReference ? '本公开参考集的代理证据 EM/F1 由答案 span 机械映射，仅作辅助；不是人审完整支持链，也不能与近期集的证据分数直接比较。' : '证据 EM 要求恰好覆盖一套参考支持链，多引和漏引均失败。'}调用、格式失败与未完成题计零；错误拒答低也可能源于失败，应结合完成率和答案成绩。</p><details class="raw-details" data-detail="v2-kinds-${language}" ${state.openDetails.has('v2-kinds-'+language) ? 'open' : ''}><summary>查看题型、辅助指标与文章数</summary><div class="table-wrap"><table class="data-table"><thead><tr><th>模型</th><th>题型</th><th class="numeric">计划题 / 文章</th><th class="numeric">失败 / 未完成</th><th class="numeric">有效输出率</th><th class="numeric">严格答案正确率</th></tr></thead><tbody>${activeModels.flatMap((id) => Object.entries(summaries[id][language].by_question_kind || {}).filter(([,s]) => s.planned_questions).map(([kind,s]) => `<tr><td>${esc(run.snapshots?.models?.find((m) => m.id === id)?.name || id)}</td><td>${esc(kindLabels[kind] || kind)}</td><td class="numeric">${number(s.planned_questions)} / ${number(s.articles)}</td><td class="numeric">${number(s.errors)}</td><td class="numeric">${pct(s.valid_output_rate)}</td><td class="numeric">${pct(s.strict_answer_accuracy)}</td></tr>`)).join('')}</tbody></table></div><p class="metric-table-note">联合成功率、六维宏平均 U、Brier 和覆盖率属于补充观测，不组成公认的阅读总分。</p><pre>${esc(JSON.stringify(Object.fromEntries(activeModels.map((id) => [id,{articles:summaries[id][language].articles,supplemental_metrics:summaries[id][language].supplemental_metrics,brier_answer:summaries[id][language].brier_answer,brier_effective_n:summaries[id][language].brier_effective_n,valid_output_rate:summaries[id][language].valid_output_rate}])),null,2))}</pre></details>` : empty(`没有${label}计分材料`,'本次计划中没有此语言的问题，不能据此报告其阅读能力。','','methodology')}</section>`;
  }
  function renderV2Run() {
    const run = state.run, config = run.config || {}, results = run.results || [], bank = run.snapshots?.bank || {};
    const done = Number(run.progress?.done || 0), total = Number(run.progress?.total || 0);
    const draft = config.allow_draft !== false || run.evaluation?.formal === false;
    const publicReference = isPublicReference(bank);
    const errors = results.filter((r) => r.error || r.metrics?.error).length;
    const filtered = results.filter((r) => (state.resultModel === 'all' || r.model_id === state.resultModel) && (state.resultLanguage === 'all' || r.language === state.resultLanguage) && (state.resultView === 'all' || (state.resultView === 'errors' ? !!(r.error || r.metrics?.error) : !r.error && !r.metrics?.error && Number(r.metrics?.answer_correct) < 1)));
    const canResume = !isActive(run) && done < total;
    const noContext = config.mode === 'no_context';
    return `<div class="page-heading run-header"><div><span class="eyebrow">READING EXPERIMENT V2 · ${publicReference ? '公开历史参考' : draft ? '开发诊断' : '冻结题库实验'}</span><h1>回答、证据，各自验证。</h1><div class="run-meta"><span class="mono">${esc(run.id)}</span><span>${date(run.created_at,true)}</span>${statusBadge(run.status)}</div><div class="run-meta"><span>${noContext ? '无文章对照' : '提供文章'}</span><span>题库 ${esc(config.bank_id || bank.id || bank.bank_version || '—')}</span><span>Temperature ${esc(config.temperature ?? '—')}</span><span>输出 ${esc(config.max_tokens ?? '—')} Tokens</span><span>上下文 ${esc(config.num_ctx ?? '未记录')} Tokens</span></div></div><div class="actions">${isActive(run) ? '<button type="button" class="button button-danger" data-action="cancel-run">取消后续调用</button>' : canResume ? '<button type="button" class="button button-primary" data-action="resume-v2" '+(state.busy ? 'disabled' : '')+'>'+svg('play')+'续跑未完成题</button>' : ''}<button type="button" class="button button-secondary button-small" data-export="json">${svg('download')}JSON</button><button type="button" class="button button-secondary button-small" data-export="csv">${svg('download')}CSV</button></div></div>
      <div class="notice v2-status-notice"><strong>${publicReference ? '公开历史参考成绩，本项目未独立复核' : draft ? 'AI 草稿成绩，仅用于开发诊断' : '冻结题库成绩，须保留实际审题与版本证据'}</strong><br>${publicReference ? '原题可能已被模型训练见过，不能代表近期隐藏集表现；答案来自原始公开标注，证据仅是 span 派生代理辅助项，非人审支持链。本平台规范化评分不等于原数据集官方成绩。' : draft ? '这些参考答案没有完成独立人工审题。页面上的分数是此次真实回答的诊断结果，不能解释为正式模型排名。' : '根据当前冻结题库计分；中文与英文分别解释，未纳入自行设定的统一阅读总分。'}${noContext ? '<br>无文章组仅提供答案诊断；不评价证据，不与有文章组的联合指标作能力排名。' : ''}</div>
      ${state.runError ? `<div class="notice error" role="alert">${esc(state.runError)}<div class="read-more"><button type="button" class="button button-small button-secondary" data-action="retry-run">恢复读取</button></div></div>` : ''}${run.error ? `<div class="notice error" role="alert">${esc(run.error)}</div>` : ''}
      <div class="progress-block"><div class="progress-top"><strong>${isActive(run) ? '正在真实调用并逐题评分' : statusNames[run.status] || '实验记录'}</strong><span>${done} / ${total} 次计划调用已记录</span></div><div class="progress-track" role="progressbar" aria-label="新版实验进度" aria-valuemin="0" aria-valuemax="${Math.max(1,total)}" aria-valuenow="${Math.min(done,total)}"><div class="progress-fill" style="width:${total ? Math.min(100,done / total * 100) : 0}%"></div></div></div>
      <div class="run-score-grid">${stat('已记录响应',number(results.length),'实际响应或明确错误记录','experiment','次')}${stat('调用 / 格式错误',number(errors),'计零并保留，不通过重试删除','methodology','次')}${stat('尚未完成',number(Math.max(0,total-done)),'仍保留在计划分母；支持续跑','clock','次')}${stat(publicReference ? '固定参考篇章' : '固定文章',number(bank.articles?.length || 0),'正文、题目与段落 ID 留在快照','library','篇')}</div>
      <div class="notice v2-progress-note">${isActive(run) || done < total ? '实验尚未完整完成，以下分数是暂时诊断；未完成题已按零计入计划分母。' : '以下指标基于完整计划分母，已评分失败仍保留。'} 续跑只提交未完成题，已记录失败不会自动重试。</div>
      ${renderV2LanguageSummary(run,'zh')}${renderV2LanguageSummary(run,'en')}
      <details class="raw-details v2-statistics" data-detail="v2-statistics" ${state.openDetails.has('v2-statistics') ? 'open' : ''}><summary>查看置信区间与模型差值</summary><p class="metric-table-note">按文章簇重采样；开发小样本不能支撑正式比较。若单语言只有一篇文章，重采样无法估计文章间差异。</p><pre>${esc(JSON.stringify(run.evaluation?.statistics || {note:'统计结果尚未生成'},null,2))}</pre></details>
      <div class="result-toolbar"><h2>逐题记录 <span class="muted small">${filtered.length} / ${results.length}</span></h2><div class="result-filters"><label class="sr-only" for="result-model">按模型筛选</label><select id="result-model"><option value="all">全部模型</option>${(config.model_ids || []).map((id) => `<option value="${esc(id)}" ${state.resultModel === id ? 'selected' : ''}>${esc(run.snapshots?.models?.find((m) => m.id === id)?.name || id)}</option>`).join('')}</select><label class="sr-only" for="result-language">按语言筛选</label><select id="result-language"><option value="all" ${state.resultLanguage === 'all' ? 'selected' : ''}>中英文</option><option value="zh" ${state.resultLanguage === 'zh' ? 'selected' : ''}>中文</option><option value="en" ${state.resultLanguage === 'en' ? 'selected' : ''}>英文</option></select><label class="sr-only" for="result-view">按评分筛选</label><select id="result-view"><option value="all" ${state.resultView === 'all' ? 'selected' : ''}>全部响应</option><option value="incorrect" ${state.resultView === 'incorrect' ? 'selected' : ''}>答案未正确</option><option value="errors" ${state.resultView === 'errors' ? 'selected' : ''}>调用 / 格式错误</option></select></div></div>
      ${filtered.length ? filtered.map(renderV2Result).join('') : `<div class="panel">${empty(results.length ? '没有匹配的逐题记录' : '等待模型响应',results.length ? '调整筛选条件查看。' : '真实响应与错误会保存在这里。','','experiment')}</div>`}
      <details class="raw-details" data-detail="v2-run-config" ${state.openDetails.has('v2-run-config') ? 'open' : ''}><summary>查看预算核验、评分版本与固定快照</summary><p class="metric-table-note">精确预算保存 tokenizer、原生模板与完整渲染提示；草稿允许保守估算时应标明方法。全文输入超预算会明确报错，不静默截断。</p><pre>${esc(JSON.stringify({protocol:run.protocol,grader_version:run.evaluation?.grader_version,config,snapshots:run.snapshots,budget:run.budget ?? run.budget_validation ?? run.input_budget ?? null},null,2))}</pre></details>`;
  }
  function renderV2Result(r, index) { return renderV2ResultForRun(state.run,r,index); }
  function renderV2ResultForRun(runRecord, r, index) {
    const article = runRecord?.snapshots?.bank?.articles?.find((a) => a.id === r.article_id);
    const q = article?.questions?.find((question) => question.id === r.question_id) || {};
    const response = r.response || r, metrics = r.metrics || {};
    const id = `v2-result-${r.model_id}-${r.article_id}-${r.question_id}-${index}`;
    const prefix = id+'-paragraph';
    const error = r.error || metrics.error;
    const predictedIds = response.evidence_ids || r.evidence_ids || r.evidence || [];
    const answer = response.answer ?? r.answer;
    const noContext = runRecord?.config?.mode === 'no_context';
    const publicReference = isPublicReference(runRecord?.snapshots?.bank);
    const evidenceProxy = (r.kind || q.kind) !== 'unanswerable' && (isEvidenceProxy(q) || isEvidenceProxy(article));
    return `<article class="result-card"><div class="result-card-header"><div><h3>${esc(r.question || q.prompt || r.question_id)}</h3><div class="result-meta"><span class="badge">${esc(kindLabels[r.kind || q.kind] || r.kind || q.kind || '')}</span><span>${esc(dimensionLabels[r.dimension || q.dimension] || '')}</span><span>${esc(runRecord?.snapshots?.models?.find((m) => m.id === r.model_id)?.name || r.model_id)}</span><span>${esc(article?.title || r.article_id)}</span><span class="mono">${esc(r.question_id)}</span></div></div>${error ? '<span class="badge badge-danger">调用 / 格式错误</span>' : `<div class="result-score"><span>答案<strong>${metrics.answer_correct ? '正确' : '未正确'}</strong></span>${!noContext && (r.kind || q.kind) !== 'unanswerable' ? `<span>${evidenceProxy ? '代理证据 EM' : '证据 EM'}<strong>${pct(metrics.evidence_exact)}</strong></span><span>${evidenceProxy ? '代理证据 F1' : '证据 F1'}<strong>${pct(metrics.evidence_f1)}</strong></span>` : ''}</div>`}</div><div class="result-content">${error ? `<div class="notice error" role="alert">${esc(error)}</div>` : `<div class="answer-comparison"><div><span class="answer-label">模型回答${response.abstain ? ' · 拒答' : ''}</span><div class="answer-copy">${esc(answer || (response.abstain ? '模型选择拒答。' : '空答案'))}${response.unit ? ' '+esc(response.unit) : ''}</div>${!noContext ? renderV2Evidence(predictedIds,prefix,'模型段落证据（点击定位）') : ''}</div><div><span class="answer-label">${publicReference ? '原始公开参考答案 · 项目未复核' : runRecord?.config?.allow_draft ? 'AI 草稿参考答案' : '参考答案'}</span><div class="answer-copy">${esc(v2Reference(q))}</div>${!noContext ? renderV2EvidenceAlternatives(q.evidence_sets || [],prefix,evidenceProxy ? '答案 span 映射代理（点击定位）' : '参考支持链（点击定位）',evidenceProxy) : ''}${q.options ? `<dl class="v2-options">${Object.entries(q.options).map(([k,v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>` : ''}</div></div><div class="confidence-row"><span>置信度 ${pct(response.confidence ?? r.confidence)}</span><span>耗时 ${decimal(r.latency_s,2)} 秒</span><span>短答 F1 ${pct(metrics.short_token_f1)}</span><span>${evidenceProxy ? '联合成功（含代理证据，仅辅助）' : '联合成功'} ${noContext || (r.kind || q.kind) === 'unanswerable' ? '不适用' : pct(metrics.joint_success)}</span></div>`}
      ${article ? `<details class="raw-details v2-response-article" data-detail="${esc(id+'-article')}" ${state.openDetails.has(id+'-article') ? 'open' : ''}><summary>查看本次使用的完整文章 · 段落 ID 可定位</summary>${renderV2Article(article,prefix)}</details>` : '<p class="footer-hint">本次记录没有文章快照，无法定位段落。</p>'}<details class="raw-details" data-detail="${esc(id)}" ${state.openDetails.has(id) ? 'open' : ''}><summary>查看原始响应、预算与完整评分</summary><pre>${esc(typeof r.raw_response === 'string' ? r.raw_response : JSON.stringify(r.raw_response ?? null,null,2))}</pre><pre>${esc(JSON.stringify(r,null,2))}</pre></details></div></article>`;
  }
  async function resumeV2Run() {
    if (state.busy || !state.run || isActive(state.run)) return;
    state.busy = true; renderRunPreservingFocus();
    try { await api(`/api/v2/runs/${encodeURIComponent(state.run.id)}/resume`,{method:'POST',body:'{}'}); toast('已提交续跑，只处理未完成题。'); stopPolling(); await loadRun(state.run.id); }
    catch (error) { toast(error.message,true); }
    finally { state.busy = false; if (state.route === 'run') renderRunPreservingFocus(); }
  }
  function renderSummary(summary) {
    return `<div class="table-wrap"><table class="data-table"><thead><tr><th>模型</th><th class="numeric">成功 / 错误</th><th class="numeric">EM</th><th class="numeric">答案 F1</th><th class="numeric">证据 F1</th><th class="numeric">拒答准确率</th><th class="numeric">Brier</th><th class="numeric">平均 / P95 秒</th><th class="numeric">输入 / 输出 Tokens</th></tr></thead><tbody>${summary.map((s) => `<tr><td><strong class="break-all">${esc(s.model_name || s.model_id)}</strong><small>已记录 ${number(s.n)} 题</small></td><td class="numeric">${number(s.successful)} / <span class="${s.errors ? 'badge-danger' : 'muted'}">${number(s.errors)}</span></td><td class="numeric">${pct(s.em)}</td><td class="numeric metric-main">${pct(s.f1)}</td><td class="numeric">${pct(s.evidence_f1)}${s.evidence_n !== undefined ? `<small>计分 N ${number(s.evidence_n)}</small>` : ""}</td><td class="numeric">${pct(s.abstention_accuracy)}<small>有效响应 N ${number(s.successful)}</small></td><td class="numeric">${decimal(s.brier,3)}${s.brier_n !== undefined ? `<small>有效 N ${number(s.brier_n)}</small>` : ""}</td><td class="numeric">${decimal(s.mean_latency_s,1)} / ${decimal(s.p95_latency_s,1)}<small>成功请求 N ${number(s.successful)}</small></td><td class="numeric">${number(s.input_tokens)} / ${number(s.output_tokens)}</td></tr>`).join('')}</tbody></table></div>${summary.some((s) => Object.keys(s.by_type || {}).length) ? `<details class="raw-details" data-detail="type-scores" ${state.openDetails.has('type-scores') ? 'open' : ''}><summary>查看按阅读能力分组的表现</summary><div class="table-wrap"><table class="data-table"><thead><tr><th>模型</th><th>问题类型</th><th class="numeric">已评分题数</th><th class="numeric">EM</th><th class="numeric">答案 F1</th></tr></thead><tbody>${summary.flatMap((s) => Object.entries(s.by_type || {}).map(([type,v]) => `<tr><td>${esc(s.model_name || s.model_id)}</td><td>${esc(typeLabel(type))}</td><td class="numeric">${number(v.n)}</td><td class="numeric">${pct(v.em)}</td><td class="numeric">${pct(v.f1)}</td></tr>`)).join('')}</tbody></table></div></details>` : ''}`;
  }
  function renderResult(r, index) {
    const article = state.run?.snapshots?.articles?.find((a) => a.id === r.article_id) || state.articles.find((a) => a.id === r.article_id);
    const question = article?.questions?.find((q) => q.id === r.question_id);
    const id = `result-${r.model_id}-${r.article_id}-${r.question_id}-${index}`;
    const predictionEvidence = Array.isArray(r.evidence) ? r.evidence.join('\n') : r.evidence;
    const historicalEvidence = r.gold_evidence ?? r.reference_evidence;
    const refEvidence = historicalEvidence !== undefined ? (Array.isArray(historicalEvidence) ? historicalEvidence.join('\n') : String(historicalEvidence)) : (question ? evidence(question) : '');
    return `<article class="result-card"><div class="result-card-header"><div><h3>${esc(question ? questionText(question) : r.prompt || r.question_id)}</h3><div class="result-meta"><span class="badge ${r.type === 'unanswerable' ? 'badge-gold' : ''}">${esc(typeLabel(r.type))}</span><span>${esc(r.model_name || r.model_id)}</span><a href="#library:${esc(r.article_id)}">${esc(r.article_title || article?.title || r.article_id)}</a><span class="mono">${esc(r.question_id)}</span></div></div>${r.error ? '<span class="badge badge-danger">调用错误</span>' : `<div class="result-score"><span>EM<strong>${pct(r.metrics?.em)}</strong></span><span>F1<strong>${pct(r.metrics?.f1)}</strong></span><span>证据<strong>${pct(r.metrics?.evidence_f1)}</strong></span></div>`}</div><div class="result-content">${r.error ? `<div class="notice error" role="alert">${esc(r.error)}</div>` : `<div class="answer-comparison"><div><span class="answer-label">模型回答${r.abstain ? ' · 已拒答' : ''}</span><div class="answer-copy">${esc(r.answer || (r.abstain ? '模型未给出答案，选择拒答。' : '模型返回空答案。'))}</div><blockquote class="evidence-text">${esc(predictionEvidence || '未提供原文证据')}</blockquote></div><div><span class="answer-label">标准答案</span><div class="answer-copy">${esc(r.reference_answer || (question ? reference(question) : '未记录'))}</div><blockquote class="evidence-text">${esc(refEvidence || (r.type === 'unanswerable' ? '原文无法回答。' : '未记录证据'))}</blockquote></div></div><div class="confidence-row"><span>置信度 ${pct(r.confidence)}</span><span>拒答判断 ${r.metrics?.abstention_correct === null || r.metrics?.abstention_correct === undefined ? '—' : r.metrics.abstention_correct ? '正确' : '错误'}</span><span>Brier ${decimal(r.metrics?.brier,3)}</span><span>耗时 ${decimal(r.latency_s,2)} 秒</span><span>Tokens ${number(r.input_tokens)} 入 / ${number(r.output_tokens)} 出</span></div>`}<details class="raw-details" data-detail="${esc(id)}" ${state.openDetails.has(id) ? 'open' : ''}><summary>查看原始响应与完整调用记录</summary><span class="answer-label" style="margin-top:12px">原始模型响应</span><pre>${esc(typeof r.raw_response === 'string' ? r.raw_response : JSON.stringify(r.raw_response ?? null,null,2))}</pre><span class="answer-label" style="margin-top:12px">完整评分记录</span><pre>${esc(JSON.stringify(r,null,2))}</pre></details></div></article>`;
  }
  async function cancelRun() {
    if (!state.run || !isActive(state.run)) return;
    const button = $('[data-action="cancel-run"]'); if (button) button.disabled = true;
    try { await api(`/api/runs/${encodeURIComponent(state.run.id)}/cancel`,{method:'POST',body:'{}'}); toast('已提交取消请求。正在执行的调用结束后停止后续调用。'); stopPolling(); await loadRun(state.run.id); }
    catch (error) { toast(error.message,true); if (button) button.disabled = false; }
  }
  async function exportRun(format, runRecord = state.run) {
    if (!runRecord) return;
    const button = $(`[data-export="${format}"], [data-demo-export="${format}"]`); if (button) button.disabled = true;
    try { const base = runRecord.protocol === 'reading-experiment-v2' ? '/api/v2/runs' : '/api/runs'; const blob = await api(`${base}/${encodeURIComponent(runRecord.id)}/export?format=${format}`,{blob:true}); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${runRecord.id}.${format}`; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url),1000); toast(`${format.toUpperCase()} 实验记录已导出。`); }
    catch (error) { toast(error.message,true); }
    finally { if (button) button.disabled = false; }
  }
  function renderModels() {
    return `${heading('MODEL REGISTRY','模型管理','连接真实推理服务，记录可核查的版本、日期与连接状态。','<button class="button button-secondary" type="button" data-action="refresh-models">'+svg('refresh')+'检查连接</button>')}
      <div class="notice" style="margin-bottom:21px"><strong>日期声明需要证据，版本需要固定。</strong>模型发布日应早于题库文章；Ollama digest 与预期 digest 匹配后才通过版本门槛。API 模型还需要提供可固定的版本声明。通过门槛仍不保证完全没有数据污染。</div>
      ${state.models.length ? `<div class="model-list">${state.models.map((m) => `<article class="model-card"><div class="model-card-top"><div><h3>${esc(m.name)}</h3><div class="provider">${m.provider === 'ollama' ? 'OLLAMA · 本地推理' : 'OPENAI 兼容接口'}</div></div>${modelBadge(m)}</div><dl class="model-info"><dt>模型标识</dt><dd class="mono">${esc(m.model)}</dd><dt>服务地址</dt><dd class="mono">${esc(m.base_url)}</dd><dt>登记原生上下文</dt><dd>${m.native_context_tokens ? number(m.native_context_tokens)+' Tokens' : '未登记'}</dd><dt>发布日期</dt><dd>${date(m.release_date)} ${m.release_source ? extLink(m.release_source,'核查来源 ↗') : '<span class="muted">来源未声明</span>'}</dd><dt>当前 Digest</dt><dd class="mono">${esc(m.digest || '尚未获取 / 未声明')}</dd><dt>预期版本</dt><dd class="mono">${esc(m.expected_digest || '尚未固定')}</dd><dt>门槛状态</dt><dd><span class="badge ${m.temporal_verified ? 'badge-success' : 'badge-gold'}">${m.temporal_verified ? '版本与日期门槛通过' : '版本或日期待核查'}</span></dd></dl>${m.status && !['ok','ready','available','connected'].includes(m.status) ? `<div class="notice ${!m.available ? 'error' : ''}">${esc(typeof m.status === 'string' ? m.status : JSON.stringify(m.status))}</div>` : ''}</article>`).join('')}</div>` : `<div class="panel" style="margin-bottom:23px">${empty('连接你的第一个模型','配置服务器上已部署的模型。平台不会使用虚构回答。','','models')}</div>`}
      <section class="panel"><div class="panel-header"><div><span class="eyebrow">添加模型连接</span><h2>让模型加入实验</h2><p>这里只保存服务配置。API 密钥由服务器环境变量提供。</p></div>${svg('plus')}</div><form id="model-form" class="model-form"><div class="field-grid"><label class="field">显示名称<input name="name" required maxlength="100" placeholder="如：Qwen 2.5 7B"></label><label class="field">推理接口<select name="provider" id="model-provider"><option value="ollama">Ollama</option><option value="openai">OpenAI 兼容接口</option></select></label><label class="field">服务地址<input name="base_url" type="url" required placeholder="http://127.0.0.1:11434"><small>填写平台服务器能访问的地址</small></label><label class="field">模型名称 / 固定版本<input name="model" required placeholder="如：qwen2.5:7b"><small>须与服务已部署的模型标识一致</small></label><label class="field">模型发布日期<input name="release_date" type="date" required><small>用模型正式发布日作为训练完成的保守上界</small></label><label class="field">发布日期证据链接<input name="release_source" type="url" required placeholder="https://…"><small>官方模型卡或公告</small></label><label class="field" style="grid-column:1 / -1">预期 Digest / 不可变版本声明<input name="expected_digest" placeholder="Ollama SHA-256 digest，或供应方不可变模型版本"><small>可在检查连接后复制当前 digest，核对可信来源并固定。只有声明日期不足以通过严格实验。</small></label></div><div class="actions"><button class="button button-primary" type="submit" ${state.busy ? 'disabled' : ''}>${svg('plus')}保存并检查模型</button></div></form></section>`;
  }
  async function addModel(form) {
    if (state.busy || !form.reportValidity()) return;
    const values = Object.fromEntries(new FormData(form).entries());
    state.busy = true; const button = $('button[type="submit"]',form); button.disabled = true;
    try { await api('/api/models',{method:'POST',body:JSON.stringify(values)}); const data = await api('/api/models'); state.models = data.models || []; state.busy = false; render(); toast('模型配置已保存，连接状态已更新。'); }
    catch (error) { state.busy = false; button.disabled = false; toast(error.message,true); }
  }
  function inlineMarkdown(text) {
    let safe = esc(text);
    safe = safe.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_,label,url) => safeURL(url.replace(/&amp;/g,'&')) ? `<a href="${esc(safeURL(url.replace(/&amp;/g,'&')))}" target="_blank" rel="noopener noreferrer">${label}</a>` : label);
    return safe.replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  }
  function markdown(text) {
    const lines = text.replace(/\r/g,'').split('\n'); let html = '', list = '', code = false, codeLines = [], table = [];
    const closeList = () => { if (list) { html += `</${list}>`; list = ''; } };
    const closeTable = () => { if (!table.length) return; const rows = table.filter((l) => !/^\s*\|?[\s:|-]+\|?\s*$/.test(l)); html += '<div class="table-wrap"><table>' + rows.map((l,i) => `<tr>${l.replace(/^\||\|$/g,'').split('|').map((cell) => `<${i === 0 ? 'th' : 'td'}>${inlineMarkdown(cell.trim())}</${i === 0 ? 'th' : 'td'}>`).join('')}</tr>`).join('') + '</table></div>'; table = []; };
    for (const line of lines) {
      if (/^```/.test(line)) { closeList(); closeTable(); if (code) { html += `<pre><code>${esc(codeLines.join('\n'))}</code></pre>`; codeLines = []; } code = !code; continue; }
      if (code) { codeLines.push(line); continue; }
      if (/^\s*\|/.test(line)) { closeList(); table.push(line.trim()); continue; } else closeTable();
      if (!line.trim()) { closeList(); continue; }
      const h = /^(#{1,3})\s+(.+)$/.exec(line); if (h) { closeList(); html += `<h${h[1].length}>${inlineMarkdown(h[2])}</h${h[1].length}>`; continue; }
      const li = /^\s*(?:[-*]\s+|\d+\.\s+)(.+)$/.exec(line); if (li) { const next = /^\s*\d+\./.test(line) ? 'ol' : 'ul'; if (list !== next) { closeList(); html += `<${next}>`; list = next; } html += `<li>${inlineMarkdown(li[1])}</li>`; continue; }
      closeList(); if (/^>\s?/.test(line)) html += `<blockquote>${inlineMarkdown(line.replace(/^>\s?/,''))}</blockquote>`; else if (!/^---+$/.test(line.trim())) html += `<p>${inlineMarkdown(line)}</p>`;
    }
    closeList(); closeTable(); if (codeLines.length) html += `<pre><code>${esc(codeLines.join('\n'))}</code></pre>`; return html;
  }
  function renderMethodology() {
    const dimensions = [['D1','事实定位','准确找出实体、事件与明确事实，核对答案对应的上下文。'],['D2','语义与条件理解','理解指代、否定、比较、条件和词义。相同词语的顺序或关系变化，答案也应随之改变。'],['D3','跨句与跨段推理','必须结合至少两处有效依据；答案若可直接复制一句话，不能当作跨句推理题。'],['D4','数量与时间推理','根据文章中的数据或时间进行计算、比较与排序。仅找到一个数字属于事实定位。'],['D5','主旨、结构与论证','概括核心观点，区分主张与依据，理解段落关系和论证结构。'],['D6','信息边界识别','识别接近答案却仍缺关键条件的问题，并正确拒答。文本已反驳错误前提时应作有依据的回答。']];
    const cards = [['EXACT MATCH','精确匹配 EM','旧 v1 已实现。适合确定性短答案；同义表达可能被判错。不能单独代表阅读能力。'],['ANSWER F1','答案 F1','旧 v1 已实现。词元重合无法判断关系、否定与语义是否正确。例如“甲高于乙”和“乙高于甲”可能获得相同词元 F1。'],['EVIDENCE F1','证据 F1','旧 v1 已实现。当前检查原文引用和词元重合，尚不能验证完整支持链；不能替代 v2 的证据完整性。'],['ABSTENTION','拒答与错误拒答','旧 v1 会记录拒答正确性。v2 分开报告不可回答题正确拒答、可回答题错误拒答和覆盖率，避免全拒答取得高分。'],['CALIBRATION','Brier 分数','旧 v1 已实现。置信度表示答案正确概率，对答案正确性校准；不与阅读得分加权混成总分。'],['EFFICIENCY','耗时与用量','旧 v1 已实现。保存耗时与 token，报告均值、P95 和失败率。硬件、负载及语言会影响这些辅助指标。']];
    return `${heading('MEASUREMENT & LIMITS','评价方法','先定义“读懂”的可核验标准，再比较模型。')}<p class="method-intro">正式设计采用六个能力维度；中文与英文各 60 篇，并分别报告成绩。当前 ${number(state.articles.length)} 篇示例用于演示流程，AI 整理与静态检查不能代替独立人工审题。</p><section class="panel joint-metric"><span class="eyebrow">v2 标准任务指标 · 真实运行</span><h2>先判断答案，再核对依据。</h2><p>学术界没有统一的阅读能力总分。新版按任务分别报告选择题准确率、短答 EM / token F1、数值严格正确率和证据集合 EM / F1；中文与英文分开报告。失败与未完成题保留在计划分母中。</p><p>信息不足题分别评价正确拒答与误答，可回答题另报误拒。答案正确且完整证据正确的联合成功 J = A × E，以及 D1—D5 五维宏平均 U 都是本项目补充指标，不能称作公认学术总分；D6 信息边界单独报告。</p><div class="notice">新版开发实验已接入版本化题库、真实调用和评分，支持段落定位、取消、续跑及结果导出。AI 草稿只能用于开发诊断；正式运行须有独立双人审题和冻结版本。历史 v1 实验保持原评分版本。</div></section><div class="section-heading"><h2>六个能力维度</h2><span class="muted small">题目按实际所需能力标注，不能只改类型名称</span></div><div class="metric-grid">${dimensions.map(([code,title,description]) => `<article class="metric-card"><div class="metric-code">${code}</div><h3>${title}</h3><p>${description}</p></article>`).join('')}</div><div class="section-heading"><h2>现有指标与辅助观测</h2><span class="muted small">不混入阅读能力总分</span></div><div class="metric-grid">${cards.map(([code,title,description]) => `<article class="metric-card"><div class="metric-code">${code}</div><h3>${title}</h3><p>${description}</p></article>`).join('')}</div><div class="notice" style="margin-bottom:24px"><strong>时间隔离是风险控制，不是无污染证明。</strong>模型发布日早于文章、固定 digest、使用无上下文对照，能减少已见过答案的风险。近期文章也可能讨论旧知识；还需核查首发与转载、近似重复和实体记忆。无上下文答对不能单独证明训练污染。</div><section class="panel"><div class="markdown">${state.methodology ? markdown(state.methodology) : '<p>服务端方法文档暂未提供。请检查 /api/methodology。</p>'}</div></section>`;
  }
  async function importFile(file) {
    if (!file) return;
    try {
      if (file.size > 20 * 1024 * 1024) throw new Error('题库 JSON 超过 20 MB，请拆分后导入。');
      const data = JSON.parse(await file.text());
      const articles = Array.isArray(data) ? data : data.articles || [data.article || data];
      if (!articles.length || !articles.every((a) => a && typeof a === 'object' && a.title && a.text && Array.isArray(a.questions))) throw new Error('请导入完整文章对象或 { articles: [...] }，须包含 title、text 与 questions。');
      let imported = 0;
      for (const article of articles) { await api('/api/articles',{method:'POST',body:JSON.stringify({article})}); imported++; }
      const updated = await api('/api/articles'); state.articles = updated.articles || []; state.selectedArticle = articles[0].id || state.articles[0]?.id; render(); toast(`已导入 ${imported} 篇文章。请检查答案与证据标注。`);
    } catch (error) { toast(`导入失败：${error.message}`,true); }
  }
  main.addEventListener('click', async (event) => {
    const demoLanguage = event.target.closest('[data-demo-language]');
    if (demoLanguage) { if (!demoSelectionLocked() && ['zh','en'].includes(demoLanguage.dataset.demoLanguage)) { demo.language = demoLanguage.dataset.demoLanguage; chooseDemoPreset(); rememberDemo(); render(); } return; }
    const demoCount = event.target.closest('[data-demo-count]');
    if (demoCount) { if (!demoSelectionLocked() && [1,3].includes(Number(demoCount.dataset.demoCount))) { demo.count = Number(demoCount.dataset.demoCount); chooseDemoPreset(); rememberDemo(); render(); } return; }
    const demoExport = event.target.closest('[data-demo-export]');
    if (demoExport) { exportRun(demoExport.dataset.demoExport,demo.run); return; }
    const evidenceButton = event.target.closest('[data-v2-evidence]');
    if (evidenceButton) {
      const paragraph = document.getElementById(evidenceButton.dataset.v2Evidence);
      if (!paragraph) { toast('此段落 ID 不在本次文章中；证据引用无效。',true); return; }
      const details = paragraph.closest('details'); if (details) details.open = true;
      document.querySelectorAll('.v2-paragraph.evidence-highlight').forEach((el) => el.classList.remove('evidence-highlight'));
      paragraph.classList.add('evidence-highlight'); paragraph.scrollIntoView({block:'center',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
      return;
    }
    const v2Mode = event.target.closest('[data-v2-mode]');
    if (v2Mode) { state.v2Config.mode = v2Mode.dataset.v2Mode; render(); return; }
    const candidateButton = event.target.closest('[data-candidate]');
    if (candidateButton) { state.selectedCandidate = candidateButton.dataset.candidate; loadCandidate(state.selectedCandidate); return; }
    const articleButton = event.target.closest('[data-article]');
    if (articleButton) { state.selectedArticle = articleButton.dataset.article; render(); return; }
    const modeButton = event.target.closest('[data-mode]');
    if (modeButton) { state.config.mode = modeButton.dataset.mode; render(); return; }
    const exportButton = event.target.closest('[data-export]');
    if (exportButton) { exportRun(exportButton.dataset.export); return; }
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (!action) return;
    if (action === 'demo-refresh') { if (!demo.loading && !demo.starting) loadDemoStatus(); return; }
    if (action === 'demo-launch') { launchDemo(); return; }
    if (action === 'demo-cancel') { cancelDemo(); return; }
    if (action === 'demo-reconnect') { if (demo.runId) { stopDemoPolling(); loadDemoRun(demo.runId); } return; }
    if (action === 'launch') launchRun();
    if (action === 'launch-v2') launchV2Run();
    if (action === 'resume-v2') resumeV2Run();
    if (action === 'cancel-run') cancelRun();
    if (action === 'reload') loadData();
    if (action === 'refresh-banks') {
      const button = event.target.closest('button'); button.disabled = true;
      try { const values = await Promise.all([api('/api/v2/banks'),api('/api/models')]); state.banks = values[0].banks || []; state.models = values[1].models || []; if (!state.banks.some((b) => b.id === state.bankId)) state.bankId = state.banks[0]?.id || ''; if (state.bankId) await loadBank(state.bankId); else render(); toast('已刷新真实题库与模型。'); }
      catch (error) { toast(error.message,true); button.disabled = false; }
    }
    if (action === 'refresh-workspace') { try { state.workspace = await api('/api/corpus-workspace'); state.candidateDetail = null; selectWorkspaceCandidate(); toast('已更新真实采集与审定数量。'); } catch (error) { toast(error.message,true); } }
    if (action === 'retry-run') { stopPolling(); loadRun(state.routeId); }
    if (action === 'import') $('#import-file').click();
    if (action === 'refresh-runs') { try { const data = await api('/api/runs'); state.runs = data.runs || []; render(); toast('实验记录已更新。'); } catch (error) { toast(error.message,true); } }
    if (action === 'refresh-models') { const button = event.target.closest('button'); button.disabled = true; try { const data = await api('/api/models'); state.models = data.models || []; render(); toast('模型连接状态已更新。'); } catch (error) { toast(error.message,true); button.disabled = false; } }
  });
  main.addEventListener('input', (event) => {
    const el = event.target;
    if (el.id === 'article-search') { const start = el.selectionStart; state.search = el.value; render(); const input = $('#article-search'); input.focus({preventScroll:true}); input.setSelectionRange(start,start); }
    if (el.dataset.config) { state.config[el.dataset.config] = Number(el.value); updateLaunchPreview(); }
    if (el.dataset.v2Config) { state.v2Config[el.dataset.v2Config] = Number(el.value); updateV2Preview(); }
  });
  main.addEventListener('change', (event) => {
    const el = event.target;
    if (el.id === 'demo-model') { if (!demoSelectionLocked() && demoCompatible(demo.data?.models?.find((m) => m.id === el.value))) { demo.modelId = el.value; rememberDemo(); render(); } return; }
    if (el.dataset.v2Model) { if (el.checked) state.v2Models.add(el.dataset.v2Model); else state.v2Models.delete(el.dataset.v2Model); constrainV2Context(); updateV2Preview(); }
    if (el.dataset.v2Article) { if (el.checked) state.v2Articles.add(el.dataset.v2Article); else state.v2Articles.delete(el.dataset.v2Article); updateV2Preview(); }
    if (el.id === 'v2-bank') { state.bankId = el.value; loadBank(el.value); }
    if (el.id === 'v2-num-ctx') { state.v2Config.num_ctx = Number(el.value); updateV2Preview(); }
    if (el.id === 'v2-preview-article') { state.v2Article = el.value; render(); }
    if (el.id === 'v2-allow-draft') { state.v2DraftAccepted = el.checked; updateV2Preview(); }
    if (el.id === 'v2-strict-time') { state.v2Config.strict_time = el.checked; updateV2Preview(); }
    if (el.id === 'v2-strict-budget') { state.v2Config.strict_budget = el.checked; updateV2Preview(); }
    if (el.dataset.modelChoice) { if (el.checked) state.selectedModels.add(el.dataset.modelChoice); else state.selectedModels.delete(el.dataset.modelChoice); updateLaunchPreview(); }
    if (el.dataset.articleChoice) { if (el.checked) state.selectedArticles.add(el.dataset.articleChoice); else state.selectedArticles.delete(el.dataset.articleChoice); updateLaunchPreview(); }
    if (el.id === 'strict-time') { state.config.strict_time = el.checked; updateLaunchPreview(); }
    if (el.id === 'result-model') { state.resultModel = el.value; renderRunPreservingFocus(); }
    if (el.id === 'result-view') { state.resultView = el.value; renderRunPreservingFocus(); }
    if (el.id === 'result-language') { state.resultLanguage = el.value; renderRunPreservingFocus(); }
    if (el.id === 'candidate-language') { state.candidateLanguage = el.value; selectWorkspaceCandidate(); }
    if (el.id === 'candidate-provider') { state.candidateProvider = el.value; selectWorkspaceCandidate(); }
    if (el.id === 'import-file') importFile(el.files[0]);
  });
  main.addEventListener('submit', (event) => { if (event.target.id === 'model-form') { event.preventDefault(); addModel(event.target); } });
  main.addEventListener('toggle', (event) => { const key = event.target.dataset?.detail; if (key) { if (event.target.open) state.openDetails.add(key); else state.openDetails.delete(key); } },true);
  $('.skip-link').addEventListener('click', (event) => { event.preventDefault(); main.focus(); main.scrollIntoView({block:'start'}); });
  $('#token-button').addEventListener('click', () => { $('#token-input').value = token(); $('#token-dialog').showModal(); });
  document.querySelectorAll('[data-close-dialog]').forEach((button) => button.addEventListener('click', () => $('#token-dialog').close()));
  $('#token-form').addEventListener('submit', (event) => { event.preventDefault(); try { const value = $('#token-input').value.trim(); if (value) sessionStorage.setItem('reading-bench-token',value); else sessionStorage.removeItem('reading-bench-token'); } catch { toast('浏览器禁止会话存储，无法保存令牌。',true); return; } $('#token-dialog').close(); stopPolling(); loadData(); });
  window.addEventListener('hashchange',readRoute);
  document.addEventListener('visibilitychange', () => { if (!document.hidden && state.route === 'run' && isActive(state.run) && !pollTimer) loadRun(state.routeId); if (!document.hidden && state.route === 'demo' && demo.runId && !demoPollTimer) loadDemoRun(demo.runId); });
  readRoute(); loadData();
})();
