/* Offline user-flow contracts. Mock responses never call a real model. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/app.js'), 'utf8');
const bootstrap = '  readRoute(); loadData();';
assert.equal(source.split(bootstrap).length,2);
const copy = (value) => JSON.parse(JSON.stringify(value));
const runId = 'run-123456abcdef';
const questions = [
  {id:'q01',prompt:'正文明确给出的名称是什么？',kind:'short',dimension:'D1',answers:['标准'],evidence_sets:[['p01']]},
  {id:'q02',prompt:'哪一项符合原文？',kind:'choice',dimension:'D2',options:{A:'是',B:'否'},answer:'A',evidence_sets:[['p01']]},
  {id:'q03',prompt:'原文未提供什么？',kind:'unanswerable',dimension:'D6'},
];
const article = {id:'demo-article',title:'正文 <img src=x onerror=alert(1)>',language:'zh',published_at:'2026-10-10',source_url:'https://example.org/article',
  scope:'full',paragraphs:[{id:'p01',text:'必须完整保留的第一段。'},{id:'p02',text:'必须完整保留的最后一段。'}],questions};
const presets = ['zh','en'].flatMap((language) => [1,3].map((n) => ({id:`${language}-${n===1?'quick':'reading'}`,label:`${language} ${n}题`,
  language,question_count:n,bank_id:'draft-bank',article:{...article,language},questions:questions.slice(0,n),formal:false})));
const status = {version:'test-demo-v1',ready:true,status:'ready',problems:[],deployment:{label:'测试平台',hostname:'test-host',model_connection_note:'平台后端所在主机的模型服务'},
  models:[{id:'baseline',name:'可用模型',model:'baseline:7b',available:true,base_url:'http://127.0.0.1:11435',
    compatible_preset_ids:presets.map((p)=>p.id),demo_context_tokens:8192,compatibility:Object.fromEntries(presets.map((p)=>[p.id,{allowed:true,num_ctx:8192}]))},
    {id:'offline',name:'离线模型',model:'offline',available:false,compatible_preset_ids:presets.map((p)=>p.id)},
    {id:'incompatible',name:'超预算模型',model:'too-small',available:true,compatible_preset_ids:[]}],
  presets,default_model_id:'baseline',default_preset_id:'zh-quick',active_run:null,recent_runs:[],model_calls:0};

function runFixture(state='running') {
  const results = state === 'completed' ? [{model_id:'baseline',article_id:article.id,question_id:'q01',kind:'short',language:'zh',
    response:{answer:'标准',unit:'',evidence_ids:['p01'],confidence:.9,abstain:false},
    metrics:{answer_correct:1,evidence_exact:1,evidence_f1:1,short_token_f1:1,joint_success:1},latency_s:2.1,raw_response:'{"answer":"标准"}'}] : [];
  return {id:runId,protocol:'reading-experiment-v2',status:state,created_at:'2026-10-26T00:00:00Z',
    config:{model_ids:['baseline'],allow_draft:true,bank_id:'draft-bank',mode:'with_context'},
    progress:{done:results.length,total:1},snapshots:{bank:{articles:[article]},models:[status.models[0]]},results};
}

function harness({stored=new Map(),origin='http://localhost:8877',token='',run=runFixture(),postFailure=false}={}) {
  const elements = new Map(), requests = [], timers = new Map(); let nextTimer=0, failed=false;
  function element(key) {
    if (!elements.has(key)) elements.set(key,{innerHTML:'',textContent:'',value:'',disabled:false,listeners:{},
      addEventListener(kind,fn){this.listeners[kind]=fn;},querySelector:element,querySelectorAll:()=>[],focus:()=>{}});
    return elements.get(key);
  }
  const control = {run,status:copy(status),deferred:null,failGet:false,failStatus:false,missingGet:false};
  const sandbox = {
    document:{querySelector:element,querySelectorAll:()=>[],getElementById:element,addEventListener:()=>{},hidden:false},
    window:{addEventListener:()=>{},scrollY:0,scrollTo:()=>{}},
    location:{hash:'',origin},crypto:{randomUUID:()=> 'test-request-12345678'},URL,
    sessionStorage:{getItem:()=>token},localStorage:{getItem:(key)=>stored.get(key)||null,setItem:(key,value)=>stored.set(key,value)},
    setTimeout:(fn)=>{timers.set(++nextTimer,fn);return nextTimer;},clearTimeout:(id)=>timers.delete(id),
    fetch:async(url,options={})=>{
      requests.push({url,options});
      if (url==='/api/demo/status') {
        if (control.failStatus) throw new Error('network lost');
        return {ok:true,json:async()=>copy(control.status)};
      }
      if (url==='/api/demo/runs' && options.method==='POST') {
        if (postFailure && !failed) { failed=true; throw new Error('network lost'); }
        return {ok:true,json:async()=>({id:runId,run:copy(control.run),reused:failed})};
      }
      if (url===`/api/v2/runs/${runId}`) {
        if (control.deferred) return control.deferred;
        if (control.failGet) throw new Error('network lost');
        if (control.missingGet) return {ok:false,status:400,json:async()=>({error:'记录不存在'})};
        return {ok:true,json:async()=>copy(control.run)};
      }
      if (url===`/api/runs/${runId}/cancel` && options.method==='POST') {
        control.run={...control.run,status:'cancelled'};
        return {ok:true,json:async()=>copy(control.run)};
      }
      throw new Error('Unexpected URL: '+url);
    },
  };
  vm.runInNewContext(source.replace(bootstrap,
    '  globalThis.__test = {state,demo,readRoute,loadDemoStatus,loadDemoRun,launchDemo,cancelDemo,demoCanLaunch,demoCompatible,renderDemo,renderDemoProgress,chooseDemoPreset,restoreDemo,rememberDemo,stopDemoPolling};'),sandbox);
  const api=sandbox.__test;
  api.state.route='demo';api.state.loaded=true;
  return {api,sandbox,requests,elements,element,stored,control,timers};
}
const settle = async()=>{ for(let i=0;i<12;i++) await Promise.resolve(); };
const launches=(h)=>h.requests.filter((r)=>r.url==='/api/demo/runs');

async function main() {
  let checks=0;
  const h=harness({token:'fixture-token'}), {api}=h;
  api.readRoute(); await settle();
  assert.equal(api.state.route,'demo'); assert.equal(api.demo.presetId,'zh-quick'); assert.equal(api.demo.modelId,'baseline');
  assert.equal(launches(h).length,0); assert.equal(api.demoCanLaunch(),true); checks++;

  const html=api.renderDemo();
  assert.match(html,/必须完整保留的第一段/); assert.match(html,/必须完整保留的最后一段/);
  assert.match(html,/&lt;img src=x onerror=alert\(1\)&gt;/); assert.doesNotMatch(html,/<img src=x/);
  assert.match(html,/未完成人审/); assert.match(html,/平台后端所在主机/);
  assert.equal(api.demoCompatible(api.demo.data.models[1]),false); assert.equal(api.demoCompatible(api.demo.data.models[2]),false); checks++;

  api.demo.language='en'; api.demo.count=3; api.chooseDemoPreset();
  assert.equal(api.demo.presetId,'en-reading'); assert.match(api.renderDemo(),/3<\/strong> 次模型调用/);
  assert.equal(launches(h).length,0); checks++;

  await Promise.all([api.launchDemo(),api.launchDemo()]); await settle();
  assert.equal(launches(h).length,1); const sent=JSON.parse(launches(h)[0].options.body);
  assert.equal(sent.model_id,'baseline'); assert.equal(sent.preset_id,'en-reading'); assert.equal(sent.allow_draft,true);
  assert.equal(sent.client_request_id,'test-request-12345678'); assert.equal(launches(h)[0].options.headers.Authorization,'Bearer fixture-token');
  assert.equal(api.demo.runId,runId); assert.equal(api.demoCanLaunch(),false); checks++;

  const g=harness({postFailure:true});await g.api.loadDemoStatus();
  await g.api.launchDemo(); assert.equal(g.api.demo.pending,true);
  const original=JSON.parse(launches(g)[0].options.body);
  await g.api.launchDemo(); await settle();
  assert.equal(launches(g).length,2);assert.equal(JSON.parse(launches(g)[1].options.body).client_request_id,original.client_request_id);
  assert.equal(g.api.demo.pending,false);assert.equal(g.api.demo.runId,runId);checks++;

  const restored=harness({stored:h.stored,run:runFixture('completed')});await restored.api.loadDemoStatus();await settle();
  assert.equal(restored.api.demo.runId,runId);assert.equal(restored.api.demo.run.status,'completed');assert.equal(launches(restored).length,0);
  const isolated=harness({stored:h.stored,origin:'http://localhost:8787'});isolated.api.restoreDemo();
  assert.equal(isolated.api.demo.runId,'');checks++;

  restored.control.failGet=true;await restored.api.loadDemoRun(runId);
  assert.equal(restored.api.demo.run.results.length,1);assert.match(restored.api.demo.runError,/无法连接/);
  assert.match(restored.api.renderDemoProgress(),/保留上次读取到的真实记录/);
  assert.equal(launches(restored).length,0);
  restored.control.failGet=false;await restored.api.loadDemoRun(runId);
  assert.equal(restored.api.demo.runError,'');assert.equal(launches(restored).length,0);checks++;

  h.control.run=runFixture('running');await api.loadDemoRun(runId);
  await api.cancelDemo();assert.equal(api.demo.run.status,'cancelled');
  assert.equal(h.requests.filter((r)=>r.url.endsWith('/cancel')).length,1);assert.equal(launches(h).length,1);checks++;

  const stale=harness();await stale.api.loadDemoStatus();
  stale.api.demo.runId=runId; let resolve;
  stale.control.deferred=new Promise((r)=>{resolve=r;});
  const inFlight=stale.api.loadDemoRun(runId);
  stale.sandbox.location.hash='#overview';stale.api.readRoute();
  resolve({ok:true,json:async()=>runFixture('completed')});await inFlight;
  assert.equal(stale.api.demo.run,null);assert.equal(launches(stale).length,0);checks++;

  const failed=runFixture('completed');failed.results[0].error='bad JSON <script>alert(1)</script>';
  failed.results[0].raw_response='<script>alert(2)</script>';
  restored.api.demo.run=failed;
  const errors=restored.api.renderDemoProgress();
  assert.match(errors,/1<\/strong>调用 \/ 格式错误/);assert.match(errors,/bad JSON &lt;script&gt;/);
  assert.match(errors,/&lt;script&gt;alert\(2\)&lt;\/script&gt;/);assert.doesNotMatch(errors,/<script>/);checks++;

  const unavailable=harness();await unavailable.api.loadDemoStatus();
  unavailable.control.failStatus=true;await unavailable.api.loadDemoStatus();
  assert.equal(unavailable.api.demo.connected,false);assert.equal(unavailable.api.demoCanLaunch(),false);
  assert.match(unavailable.api.renderDemo(),/上次检查结果已保留/);assert.equal(launches(unavailable).length,0);checks++;

  const unrelated=harness();unrelated.control.status.active_run={id:runId,status:'running'};
  unrelated.control.status.ready=false;unrelated.control.status.status='busy';
  await unrelated.api.loadDemoStatus();await settle();
  assert.equal(unrelated.api.demo.runId,'');assert.equal(unrelated.api.demoCanLaunch(),false);
  assert.equal(unrelated.requests.filter((r)=>r.url.startsWith('/api/v2/runs/')).length,0);checks++;

  const vanished=harness({stored:h.stored});vanished.control.missingGet=true;
  await vanished.api.loadDemoStatus();await settle();
  assert.equal(vanished.api.demo.runId,'');assert.equal(vanished.api.demoCanLaunch(),true);
  assert.match(vanished.api.demo.error,/没有找到可恢复/);assert.equal(launches(vanished).length,0);checks++;

  const pending=harness({postFailure:true,run:runFixture('completed')});await pending.api.loadDemoStatus();
  pending.api.demo.runId=runId;pending.api.demo.run=runFixture('completed');
  await pending.api.launchDemo();const key=JSON.parse(launches(pending)[0].options.body).client_request_id;
  pending.control.status.active_run={id:'run-aaaaaabbbbbb',status:'running'};
  await pending.api.loadDemoStatus();await settle();
  assert.equal(pending.api.demoCanLaunch(),true);await pending.api.launchDemo();
  assert.equal(JSON.parse(launches(pending)[1].options.body).client_request_id,key);checks++;

  console.log(JSON.stringify({offline_checks:checks,status:'passed',network_calls:0,model_calls:0}));
}
main().catch((error)=>{console.error(error);process.exitCode=1;});
