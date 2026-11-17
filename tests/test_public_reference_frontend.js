/* Offline state/render contract checks; no browser, network or model calls. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const elements = new Map();
function element(key) {
  if (!elements.has(key)) elements.set(key, {
    innerHTML: '', textContent: '', value: '', disabled: false, listeners: {},
    options: [{value:'4096',disabled:false},{value:'8192',disabled:false}],
    addEventListener(type, fn) { this.listeners[type] = fn; },
    querySelector(selector) { return element(selector); },
    querySelectorAll(selector) { return selector === '.summary-row strong' ? [0,1,2,3,4].map((n) => element('summary-'+n)) : []; },
  });
  return elements.get(key);
}
const publicBank = JSON.parse(fs.readFileSync(path.join(root, 'data/annotation/reference-squad2-20261025.json'), 'utf8'));
publicBank.articles = publicBank.articles.slice(0,1);
publicBank.id = 'public-test';
publicBank.formal_eligible = false;
const recentBank = {id:'recent-test',schema_version:'reading-bank-v2',bank_version:'recent-test',formal_eligible:false,
  articles:[{id:'recent-a',language:'zh',source_cluster_id:'recent-a',questions:[{id:'q01',prompt:'fixture'}]}]};
const requests = [];
const sandbox = {
  document: {querySelector: element,querySelectorAll:()=>[],addEventListener:()=>{},hidden:false},
  window: {addEventListener:()=>{},scrollY:0},
  sessionStorage: {getItem:()=>null},location:{hash:'#test'},
  setTimeout:()=>1,clearTimeout:()=>{},URL,
  fetch: async (url, options = {}) => {
    requests.push({url,options});
    const payload = url === '/api/v2/banks/public-test' ? {bank:publicBank} :
      url === '/api/v2/banks/recent-test' ? {bank:recentBank} :
      url === '/api/v2/runs' && options.method === 'POST' ? {id:'offline-test-run'} : null;
    assert.notEqual(payload,null,'Unexpected mock URL; real network is prohibited');
    return {ok:true,status:200,json:async()=>JSON.parse(JSON.stringify(payload))};
  },
};
const source = fs.readFileSync(path.join(root, 'frontend/app.js'), 'utf8');
const bootstrap = '  readRoute(); loadData();';
assert.equal(source.split(bootstrap).length,2,'Expected one app bootstrap');
vm.runInNewContext(source.replace(bootstrap,
  '  globalThis.__offline = {state,loadBank,v2CanLaunch,constrainV2Context,v2ContextExplanation,renderV2Experiment,renderV2Run,renderV2Result,launchV2Run};'), sandbox);
const api = sandbox.__offline, state = api.state;

async function main() {
  let checks = 0;
  state.route = 'offline-test';
  state.bankId = 'public-test';
  await api.loadBank('public-test');
  assert.equal(state.v2Config.strict_time,false);
  assert.equal(state.v2DraftAccepted,false);
  checks++;

  state.models = [{id:'baseline',name:'Baseline',model:'baseline',available:true,native_context_tokens:8192},
    {id:'yi4k',name:'Yi 4K',model:'yi',available:true,native_context_tokens:4096}];
  state.v2Models = new Set(['baseline']);
  state.v2Config.num_ctx = 8192;
  element('#main').listeners.change({target:{dataset:{v2Model:'yi4k'},checked:true}});
  assert.equal(state.v2Config.num_ctx,4096);
  assert.equal(element('#v2-num-ctx').value,'4096');
  assert.equal(element('#v2-num-ctx').options.find((o)=>o.value==='8192').disabled,true);
  assert.match(element('#v2-context-note').textContent,/4096|4,096/);
  checks++;

  state.bankId = 'recent-test';
  await api.loadBank('recent-test');
  assert.equal(state.v2Config.strict_time,true);
  state.bankId = 'public-test';
  await api.loadBank('public-test');
  assert.equal(state.v2Config.strict_time,false);
  checks++;

  state.v2DraftAccepted = true;
  assert.equal(api.v2CanLaunch(),true);
  state.bankLoading = true;
  assert.equal(api.v2CanLaunch(),false);
  state.bankLoading = false;
  state.bankId = 'other-loading-bank';
  assert.equal(api.v2CanLaunch(),false);
  state.bankId = 'public-test';
  checks++;

  state.banks = [publicBank,recentBank];
  const setup = api.renderV2Experiment();
  assert.match(setup,/公开历史参考/);
  assert.match(setup,/源标题簇/);
  assert.match(setup,/原始公开参考答案/);
  assert.match(setup,/仅按原始答案 span 映射/);
  assert.doesNotMatch(setup,/AI 草稿参考答案/);
  checks++;

  const article = publicBank.articles[0], question = article.questions[0];
  const result = {model_id:'yi4k',article_id:article.id,question_id:question.id,kind:question.kind,language:'en',
    response:{answer:question.answers[0],unit:'',evidence_ids:[article.paragraphs[0].id],confidence:1,abstain:false},
    metrics:{answer_correct:1,evidence_exact:1,evidence_f1:1,joint_success:1,short_token_f1:1},latency_s:1};
  state.run = {id:'offline-run',protocol:'reading-experiment-v2',status:'completed',created_at:'2026-10-24T12:00:00Z',
    config:{allow_draft:true,model_ids:['yi4k'],bank_id:'public-test',mode:'with_context',num_ctx:4096,max_tokens:512,temperature:0},
    progress:{done:1,total:1},snapshots:{bank:publicBank,models:state.models},results:[result],
    evaluation:{formal:false,summaries:{yi4k:{en:{planned_questions:1,answerable_questions:1,unanswerable_questions:0,
      primary_metrics:{short_em:1,short_token_f1:1,evidence_exact_answerable:1,evidence_f1_answerable:1},by_question_kind:{short:{planned_questions:1,articles:1}}}}}}};
  const completed = api.renderV2Run();
  assert.match(completed,/公开历史参考成绩，本项目未独立复核/);
  assert.match(completed,/代理证据 EM/);
  assert.match(completed,/原始公开参考答案 · 项目未复核/);
  assert.match(completed,/仅按原始答案 span 映射/);
  assert.doesNotMatch(completed,/AI 草稿成绩|AI 草稿参考答案/);
  checks++;

  await api.launchV2Run();
  const submitted = JSON.parse(requests.findLast((r)=>r.url==='/api/v2/runs').options.body);
  assert.equal(submitted.num_ctx,4096);
  assert.equal(submitted.strict_time,false);
  assert.equal(submitted.allow_draft,true);
  checks++;
  console.log(JSON.stringify({offline_checks:checks,network_calls:0,model_calls:0,status:'passed'}));
}
main().catch((error)=>{ console.error(error);process.exitCode=1; });
