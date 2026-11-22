// Run with Node to validate all reference views against the real API projection shape.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('./workspace.js',import.meta.url),'utf8');
const fixture=JSON.parse(fs.readFileSync(new URL('../../../../../docs/qa/owner-placements/reference_data.json',import.meta.url),'utf8'));
const departments=fixture.departments.map((d,i)=>({...d,id:String(i+1),code:d.id,coordinator:'Placement coordinator'}));
const deptMap=new Map(departments.map(d=>[d.code,d.id]));
const students=fixture.students.map((s,i)=>({...s,consent:s.willing?'willing':'declined',id:String(i+1),register:s.id,dept:deptMap.get(s.dept),department:s.dept}));
const drives=fixture.baseDrives.map((d,i)=>({...d,id:String(i+1),dept:d.dept.split(',').map(x=>deptMap.get(x)).join(','),department_codes:d.dept,eligible_ids:students.filter(s=>s.year===d.year&&s.willing&&!s.placed&&s.cgpa>=d.cgpa&&d.dept.split(',').includes(s.department)).map(s=>s.id)}));
const offers=students.filter(s=>s.placed).map(s=>({...s,student_id:s.id,decision:s.accepted?'accepted':'pending'}));
const data={company:{id:1,name:'Reference college'},departments,students,drives,offers,plans:[],years:[2027,2026,2025],currentYear:2027,today:'2026-11-22',snapshotDate:'2026-11-22',can_reset_preview:true};
function element(){return{value:'',innerHTML:'',textContent:'',hidden:false,open:false,style:{},setAttribute(){},focus(){},querySelectorAll(){return[]},addEventListener(){},showModal(){this.open=true},close(){this.open=false}}}
const elements=new Map();
const document={getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id)},querySelectorAll(){return[]},addEventListener(){}};
const window={OWNER_PLACEMENTS_BOOTSTRAP:{data,companyId:1,preview:true,screen:'overview'},addEventListener(){},parent:{postMessage(){}}};
const timers=new Set();
const context=vm.createContext({window,document,location:{origin:'http://localhost'},Date,console,setTimeout(fn,delay){const timer=setTimeout(fn,delay);timers.add(timer);return timer},clearTimeout});
vm.runInContext(source.replace(/\}\)\(\);\s*$/,`globalThis.app={go,render,metrics,insightData,openStudent,openDepartment,openDrive,openEligible,openInsight,applyData,actions,studentRows,matchesStatus,showStudents,filteredStudents,statusOf};})();`),context);
const app=context.app;
const m=app.metrics();
assert.deepEqual(JSON.parse(JSON.stringify({total:m.total,willing:m.willing,eligible:m.eligible,placed:m.placed,pending:m.pending,rate:m.rate})),{total:720,willing:616,eligible:556,placed:414,pending:142,rate:'74.5'});
for(const screen of ['overview','departments','students','drives','offers','history','insights']){
  app.go(screen);
  const html=document.getElementById('content').innerHTML;
  assert.ok(html.length>100,screen+' renders');
  assert.doesNotMatch(html,/\bon(?:click|input|change)=/,'Inline event handlers violate the workspace CSP');
  assert.doesNotMatch(html,/NaN|Infinity|undefined/);
  for(const [,action]of html.matchAll(/data-action="([^"]+)"/g)){
    const match=/^([A-Za-z]+)\((.*)\)$/.exec(action);
    assert.ok(match&&app.actions[match[1]],action);
    if(match[2])JSON.parse('['+match[2].replace(/'([^']*)'/g,(_,s)=>JSON.stringify(s))+']');
  }
}
for(const [method,id]of [['openStudent','1'],['openDepartment','1'],['openDrive','1'],['openEligible','1'],['openInsight','skills']]){
  app[method](id);assert.ok(document.getElementById('modal-body').innerHTML.length>100);
}
const markupCode='<b data-action="confirmReset()">CSE</b>';
app.applyData({...data,departments:departments.map(d=>d.id==='1'?{...d,code:markupCode}:d)},{department:'1'});
for(const method of ['openDrive','openEligible']){
  app[method]('1');
  const html=document.getElementById('modal-body').innerHTML;
  assert.ok(!html.includes(markupCode),method+' must not render department codes as HTML');
  assert.ok(html.includes('&lt;b data-action=&quot;confirmReset()&quot;&gt;CSE&lt;/b&gt;'),method+' preserves department code as text');
}
app.applyData(data,{department:'All'});
const changed=app.metrics([{willing:false,consent:'declined',eligible:false,placed:true,salary:8},{willing:true,consent:'willing',eligible:true,placed:false,salary:0},{willing:false,consent:'undecided',eligible:false,placed:false,salary:0}]);
assert.equal(changed.placed,1);assert.equal(changed.placedEligible,0);assert.equal(changed.pending,1);assert.equal(changed.rate,'0.0');
assert.equal(changed.placed+changed.pending+changed.readinessNon+changed.readinessIneligible+changed.readinessUnknown,changed.total);
assert.equal(changed.non,1);assert.equal(changed.unknown,1);assert.equal(changed.readinessNon,0);assert.equal(changed.readinessUnknown,1);
assert.equal(app.statusOf({willing:false,consent:'undecided',placed:false}),'Not recorded');
assert.equal(app.matchesStatus({willing:false,consent:'undecided'},'Non-willing'),false);
assert.equal(app.matchesStatus({willing:false,consent:'declined',placed:true},'Non-willing',true),false);
assert.equal(app.matchesStatus({willing:true,eligible:false,placed:true},'Ineligible',true),false);
assert.match(app.studentRows([{...students[0],name:'<script>bad</script>',cgpa:null}]),/&lt;script&gt;bad&lt;\/script&gt;/);
assert.match(app.studentRows([{...students[0],cgpa:null}]),/Not recorded/);
app.applyData({...data,departments:[],students:[],drives:[],offers:[],plans:[],years:[],currentYear:0});
for(const screen of ['overview','departments','students','drives','offers','history','insights']){app.go(screen);assert.doesNotMatch(document.getElementById('content').innerHTML,/NaN|Infinity|undefined/)}
for(const timer of timers)clearTimeout(timer);
console.log('Passed: exact fixture metrics, seven populated/empty views, five dialogs, delegated action arguments, escaped text, null scores and disjoint readiness metrics.');
