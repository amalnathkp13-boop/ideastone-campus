/** Student Learning Studio, adapted from the supplied reference. */
(() => {

'use strict';
const media={"campus": "/ideastone_erp/static/src/learning_studio/media/e517374ee3292c58.jpg", "cover0": "/ideastone_erp/static/src/learning_studio/media/dbe83949289d5717.webp", "cover1": "/ideastone_erp/static/src/learning_studio/media/4a0c60a8f0d1bfdd.webp", "cover2": "/ideastone_erp/static/src/learning_studio/media/61b39c912a3f9891.webp", "cover3": "/ideastone_erp/static/src/learning_studio/media/ca29b18117b6db6e.webp", "lesson0": "/ideastone_erp/static/src/learning_studio/media/9b60fa2ce0088edc.mp4", "lesson1": "/ideastone_erp/static/src/learning_studio/media/532c911a8b402bbe.mp4", "lesson2": "/ideastone_erp/static/src/learning_studio/media/50dbc4045127cfe0.mp4", "lesson3": "/ideastone_erp/static/src/learning_studio/media/274c34ec9ec05f6c.mp4"};
const courses = [
  {
    id: 'ds', code: 'CS201', title: 'Data Structures & Algorithms', short: 'Data structures', mentor: 'Meera Raman', unit: ['Trees and search', 'Traversal and analysis'],
    intro: 'Use order and structure to find information efficiently.', reading: 'Ordering a binary search tree', video: 'Searching for a key', lesson: 'Traversing a binary tree',
    first: ['A binary search tree stores a key at each node. Every key in its left subtree is smaller, and every key in its right subtree is larger. Our example uses distinct keys.', 'Insert 8, then 4, then 12. The first key becomes the root. Compare each later key with 8 to decide which side to use. Try inserting 6. It belongs to the right of 4.'],
    transcript: ['Start at 8 and look for 6.', '6 is smaller than 8, so visit its left child, 4.', '6 is larger than 4, so visit its right child, 6. The search succeeds.'],
    body: ['A traversal is an order for visiting every node exactly once. In-order traversal visits the left subtree, the current node, and then the right subtree. In a binary search tree, this produces sorted keys.', 'Start with the root 8. Follow left children until you reach 2. Visit 2, return to 4, then visit 6. Only after the whole left subtree is finished do you visit 8. Repeat the same rule on the right.', 'Pre-order visits the current node first. Post-order visits it last. The tree stays the same. The position of the visit changes the sequence.'],
    example: 'In-order     2, 4, 6, 8, 10, 12, 14\nPre-order    8, 4, 2, 6, 12, 10, 14\nPost-order   2, 6, 4, 10, 14, 12, 8',
    practice: ['Which key follows 6 in the in-order example?', ['4','8','12'],1,'The left subtree is finished after 6, so the traversal returns to the root, 8.'],
    quiz: [['What does in-order traversal return for a binary search tree with distinct keys?',['Keys in insertion order','Keys in ascending order','Only leaf keys'],1,'The left subtree, node, right subtree order yields ascending keys.'],['A search takes one branch at each node. What bounds the comparisons?',['Tree height plus one','Number of leaves only','Always exactly two'],0,'A root-to-leaf search can visit one node per level.'],['Which traversal visits both children before their parent?',['Pre-order','In-order','Post-order'],2,'Post-order processes both subtrees before the current node.']],
    task: 'Tree traversal lab', brief: 'Build the tree produced by inserting 10, 5, 15, 2, 7 and 12. Give its in-order and pre-order traversals, then explain how you would search for 7.', rubric: ['Correct tree structure','Two labelled traversal sequences','A step-by-step search trace']
  },
  {
    id:'db',code:'CS202',title:'Database Management Systems',short:'Database systems',mentor:'Arun Menon',unit:['Relational modelling','Queries and integrity'],
    intro:'Connect records through keys and turn related tables into useful answers.',reading:'Keys and relationships',video:'Joining two tables',lesson:'Writing an inner join',
    first:['A relation stores one kind of fact per row. A primary key uniquely identifies that row. A foreign key refers to a key in another table.', 'Keep a course title in the course catalogue. An enrolment row only needs the learner ID and course code. Updating the course title now requires a change in one place.'],
    transcript:['A learner with ID 17 has an enrolment for CS202.','Find CS202 in the course catalogue.','Return the learner ID together with the matching course title.'],
    body:['An inner join pairs rows that satisfy its join condition. Write down the two tables and identify the matching keys before choosing the columns to return.', 'For an enrolment list, compare enrolment.course_code with course.code. A course with no enrolments has no matching pair and is absent from this result.', 'If you need every course, including empty ones, start with course and use a left join to enrolment. Missing matches produce null enrolment fields.'],
    example:'SELECT e.learner_id, c.title\nFROM enrolment AS e\nJOIN course AS c\n  ON c.code = e.course_code;',
    practice:['What happens to a course without a matching enrolment in an inner join?',['It is omitted','It appears twice','Its title changes'],0,'An inner join only returns matching pairs.'],
    quiz:[['What identifies a row uniquely?',['A primary key','Any description','A column alias'],0,'A primary key enforces row identity.'],['Which join retains every row from the left table?',['Inner join','Left join','Cross join only'],1,'Unmatched left rows are retained with nulls on the right.'],['Why store a title in the course table?',['To remove the course key','To hide titles','To avoid repeated updates'],2,'One authoritative title avoids inconsistent copies.']],
    task:'Enrolment query lab',brief:'Design a course table and an enrolment table. Identify their keys. Write a query that lists every course and its learner count, including courses with zero learners.',rubric:['Keys are identified','Empty courses are preserved','Count excludes null enrolments']
  },
  {
    id:'dl',code:'EC203',title:'Digital Logic Design',short:'Digital logic',mentor:'Priya Nair',unit:['Logic gates','Circuit reasoning'],
    intro:'Translate binary inputs into predictable circuit behaviour.',reading:'Signals and truth tables',video:'Following a NAND gate',lesson:'Building a truth table',
    first:['A digital circuit models a signal as one of two values, 0 or 1. A truth table lists the output for each possible combination of inputs.','With two independent binary inputs, there are four possible input pairs. List them systematically as 00, 01, 10 and 11.'],
    transcript:['Both inputs are high: A equals 1 and B equals 1.','The AND gate therefore outputs 1.','An inverter changes that output to 0. This is NAND.'],
    body:['Break a circuit into named intermediate signals. Evaluate one gate at a time for each row. This makes it easier to find a mistaken inversion or swapped input.', 'To evaluate NAND, first write a column for A AND B. Then invert each entry to obtain the output column.', 'Check the 11 row separately. It is the only input pair that makes the AND gate high, so it is the only pair that makes NAND low.'],
    example:'A   B   AND   NAND\n0   0    0      1\n0   1    0      1\n1   0    0      1\n1   1    1      0',
    practice:['What is NAND(0, 1)?',['0','1','Undefined'],1,'AND produces 0 and the inversion produces 1.'],
    quiz:[['How many rows cover three binary inputs?',['3','6','8'],2,'There are two choices for each of three inputs.'],['Which gate inverts its input?',['NOT','OR','AND'],0,'NOT maps 0 to 1 and 1 to 0.'],['When is a two-input AND high?',['If either input is high','When both are high','When both are low'],1,'Both conditions must hold.']],
    task:'Logic verification lab',brief:'Construct a truth table for NOT(A OR B). Include the intermediate OR column. Compare your outputs with a NAND table and identify one input pair where they differ.',rubric:['All four input pairs','Correct intermediate outputs','A justified comparison']
  },
  {
    id:'net',code:'OE204',title:'Computer Networks',short:'Computer networks',mentor:'Kiran Rao',unit:['Packets and frames','Routing decisions'],
    intro:'Follow a message as it travels between local and remote networks.',reading:'Packets, frames and addresses',video:'Following a packet',lesson:'Choosing a next hop',
    first:['A packet carries network-layer addresses. A link-layer frame carries a packet across a single link. The frame changes as the packet moves between links.','When a destination is on the local network, the sender can deliver a frame directly. A remote destination requires a router.'],
    transcript:['The destination lies outside the local subnet.','The routing table selects the default gateway.','The sender addresses the frame to the gateway.'],
    body:['Routers choose a next hop by matching the destination against their routing table. If several entries match, the most specific prefix wins.', 'A route for 10.1.0.0/16 is more specific than 10.0.0.0/8. A packet for 10.1.2.3 uses the /16 route if both are available.', 'A default route matches all destinations and is used when no more specific route matches.'],
    example:'Destination     Next hop\n10.1.0.0/16     Router B\n10.0.0.0/8      Router A\n0.0.0.0/0       Gateway',
    practice:['Where is a packet for 10.1.4.8 sent in the example?',['Router A','Router B','Gateway'],1,'The /16 prefix is the most specific matching entry.'],
    quiz:[['Which address helps choose a network route?',['Destination IP','Font name','Frame colour'],0,'Routers match the destination IP prefix.'],['Which prefix is more specific?',['/0','/8','/24'],2,'More fixed prefix bits make a route more specific.'],['What carries a packet over one link?',['A directory','A frame','A hostname'],1,'A link-layer frame encloses the packet.']],
    task:'Route selection lab',brief:'Use the example table to choose routes for 10.1.2.3, 10.4.0.5 and 192.0.2.8. Justify each choice using prefix length.',rubric:['Three correct next hops','Prefix lengths identified','Default route explained']
  }
];
const activityTypes = ['Reading','Recording','Reading','Practice','Quiz','Assignment'];
function activities(c) { return [c.reading,c.video,c.lesson,'Practice checkpoint','Unit self-assessment',c.task]; }

const $ = sel => document.querySelector(sel);
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const paths = {
  grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  book:'M12 6C9 4 5 4 2 5v14c3-1 7-1 10 1 3-2 7-2 10-1V5c-3-1-7-1-10 1z M12 6v14',
  cal:'M4 5h16v15H4z M8 3v4 M16 3v4 M4 10h16 M8 14h2 M14 14h2',
  grades:'M4 20V9 M10 20V4 M16 20v-8 M3 20h18', chat:'M4 4h16v12H9l-5 4z M8 8h8 M8 12h5',
  down:'M12 3v12 M7 10l5 5 5-5 M4 16v4h16v-4', files:'M3 7h7l2 2h9v11H3z M4 7V4h7l2 3',
  compass:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z M16 8l-2 6-6 2 2-6z',
  wifi:'M2 8q10-8 20 0 M5 12q7-6 14 0 M8.5 16q3.5-3 7 0 M12 20h.01', offline:'M3 3l18 18 M4 9q3-2 5-2 M12 5q6 0 10 3 M6 13q3-2 5-2 M9 17q3-2 6 0 M12 20h.01',
  chev:'M9 5l7 7-7 7',back:'M15 5l-7 7 7 7',bell:'M5 16h14l-2-3V9a5 5 0 0 0-10 0v4z M10 19q2 3 4 0',
  search:'M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0z M14.5 14.5l6 6',menu:'M3 6h18 M3 12h18 M3 18h18', close:'M5 5l14 14 M19 5L5 19',
  play:'M7 4l13 8-13 8z',star:'m12 3 2.8 5.8 6.5.9-4.7 4.6 1.1 6.5-5.7-3-5.8 3 1.1-6.5-4.7-4.6 6.5-.9z',
  pen:'M4 20l4-1 12-12-3-3L5 16z M14 7l3 3',check:'M4 12l5 5L20 6',clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z M12 7v6l4 2',
  note:'M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8 M8 16h6',screen:'M3 4h18v13H3z M8 21h8 M12 17v4',
  pin:'M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0z M14 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0z',
  user:'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0z M4 21v-2a8 7 0 0 1 16 0v2',
  checkbook:'M5 5h6l2-2h6v17H5z M8 13l2 2 5-5',cloud:'M5 18a5 5 0 0 1 0-10 7 7 0 0 1 13 1 4.5 4.5 0 0 1 0 9z',
  key:'M11 10a4 4 0 1 1-8 0 4 4 0 0 1 8 0z M11 10h10v3h-3v2h-3v-5',cap:'m2 9 10-5 10 5-10 5z M6 12v5q6 4 12 0v-5 M22 9v7',info:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z M12 11v6 M12 7v.1',
  sparkle:'M12 2l1.6 6.4L20 10l-6.4 1.6L12 18l-1.6-6.4L4 10l6.4-1.6z M19 17l.7 2.3L22 20l-2.3.7L19 23l-.7-2.3L16 20l2.3-.7z',
  arrow:'M4 12h16 M14 6l6 6-6 6',target:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z M17 12a5 5 0 1 1-10 0 5 5 0 0 1 10 0z M10 12h4',trophy:'M7 4h10v7a5 5 0 0 1-10 0z M7 6H4v3a4 4 0 0 0 4 4 M17 6h3v3a4 4 0 0 1-4 4 M12 16v4 M8 21h8',trend:'M3 17l7-7 4 4 7-8 M15 6h6v6',bolt:'M13 2L4 13h7l-1 9 10-12h-7z',
  list:'M8 6h13 M8 12h13 M8 18h13 M3 6h.1 M3 12h.1 M3 18h.1',video:'M3 6h12v12H3z M15 10l6-3v10l-6-3',flag:'M4 21V4q4-3 8 0t8 0v10q-4 3-8 0t-8 0'
};
function icon(n){return '<svg class="ic" aria-hidden="true" viewBox="0 0 24 24"><path d="'+(paths[n]||paths.book)+'"/></svg>'}
const btn=(label,act,ic='',cls='btn')=>'<button type="button" class="'+cls+'" data-act="'+act+'">'+(ic?icon(ic):'')+label+'</button>';
const link=(label,url,cls='textbtn',ic='')=>'<a class="'+cls+'" href="#'+url+'">'+(ic?icon(ic):'')+label+'</a>';
const prog=n=>'<progress value="'+n+'" max="100" aria-label="Course completion '+n+' percent"></progress>';
const tag=(s,t='')=>'<span class="tag '+t+'">'+esc(s)+'</span>';
const getCourse=id=>courses.find(c=>c.id===id);
const art=c=>media['cover'+courses.indexOf(c)];
const icons=['book','play','book','pen','checkbook','note'];
function dayKey(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
const today=()=>dayKey(new Date());
const dateOf=s=>new Date(s+'T12:00:00');
const human=(d,opts={day:'numeric',month:'short'})=>dateOf(d).toLocaleDateString('en-IN',opts);
function offset(n){const d=dateOf(state.anchor);d.setDate(d.getDate()+n);return dayKey(d)}
const bootstrap=window.LEARNING_STUDIO_BOOTSTRAP;
const offlineMode=window.LEARNING_STUDIO_OFFLINE===true;
if(!bootstrap&&!offlineMode){document.getElementById('student_main').innerHTML='<section class="panel"><h1>Open LMS through your student portal</h1><p>Please sign in to load your learning workspace.</p></section>';return;}
const storageKey='vcet.learning.studio.offline.v1';
const fresh=()=>({name:'Learner',anchor:today(),enrolled:[],done:{},last:['ds',0],stars:[],answers:{},notes:{},drafts:{},submissions:{},attempts:{},testAttempts:{},posts:[],bookings:{},noticed:false,files:[],saved:[]});
let restoreIssue='',state=fresh(),revision=bootstrap?.revision||0;
try{
  if(offlineMode){
    const stored=JSON.parse(localStorage.getItem(storageKey)||'null'),portable=JSON.parse($('#portable-state').textContent);
    const source=portable&&(!stored||portable.exported>(stored.updated||0))?portable:stored;
    if(source&&Array.isArray(source.enrolled)&&source.done)state=Object.assign(state,source);
  }else state=Object.assign(state,bootstrap.state);
}catch{restoreIssue='The learning record could not be opened. Reload this page to try again.'}
let saveTimer,saveBusy=false,dirty=false,conflicted=false,changeVersion=0,pendingMessage='';
let parentNavigationReady=window.parent===window;
const saveWaiters=[];
function reportDirty(){if(!offlineMode&&window.parent!==window)window.parent.postMessage({type:'campus-lms-dirty',dirty},location.origin)}
function saveProblem(message,conflict=false){
  conflicted=conflict;
  const banner=$('#save-status');banner.hidden=false;
  banner.querySelector('span').textContent=message;
  banner.querySelector('[data-act="retry-save"]').hidden=conflict;
  banner.querySelector('[data-act="reload-state"]').hidden=!conflict;
}
async function persist(){
  clearTimeout(saveTimer);
  if(saveBusy||!dirty||conflicted||offlineMode)return;
  saveBusy=true;
  const version=changeVersion, snapshot=JSON.stringify(state);
  try{
    const response=await fetch('/my/campus/student/lms/state',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({csrf_token:bootstrap.csrfToken,state:snapshot,revision:String(revision)})});
    const data=await response.json().catch(()=>({}));
    if(response.status===409){saveProblem('This workspace changed in another tab. Download your current copy if needed, then reload the saved record.',true);return;}
    if(!response.ok||!data.state||typeof data.revision!=='number')throw new Error(data.error||'Your changes have not been saved. Check your connection and retry.');
    revision=data.revision;
    if(changeVersion===version){state=Object.assign(fresh(),data.state);dirty=false;reportDirty();}
    $('#save-status').hidden=true;
    if(pendingMessage&&!dirty){toast(pendingMessage);pendingMessage='';}
  }catch(error){saveProblem(error.message||'Your changes have not been saved. Check your connection and retry.');return;}
  finally{saveBusy=false;saveWaiters.splice(0).forEach(resolve=>resolve());}
  if(dirty&&!conflicted)persist();
}
let route=[],courseFilter='all',courseQuery='',sort='default',discussionCourse='ds',testFilter='all',activeTest=null,calendarDay=today(),monthStart=calendarDay.slice(0,7)+'-01',toastTimer, activeAttempt=null;
const enrolled=()=>courses.filter(c=>state.enrolled.includes(c.id));
const done=(c,i)=>(state.done[c.id]||[]).includes(i);
const pct=c=>Math.round((state.done[c.id]||[]).length/6*100);
const next=c=>{const idx=activities(c).findIndex((_,i)=>!done(c,i));return idx<0?0:idx};
function save(immediate=false){
  state.updated=Date.now();
  if(offlineMode){try{localStorage.setItem(storageKey,JSON.stringify(state));return true}catch{toast('Browser storage is full. Download a workspace copy to keep your changes.',true);return false}}
  changeVersion++;dirty=true;reportDirty();clearTimeout(saveTimer);
  if(immediate)persist();else saveTimer=setTimeout(persist,700);
  return true;
}
function complete(c,i){const items=state.done[c.id]||=[];if(!items.includes(i))items.push(i)}
function toast(msg,error=false){clearTimeout(toastTimer);$('#toast').className='toast'+(error?' error':'');$('#toast').textContent=msg;toastTimer=setTimeout(()=>$('#toast').textContent='',4800)}
const sectors=[['Workspace',[['dashboard','grid','Dashboard'],['courses','book','My courses'],['calendar','cal','Calendar'],['grades','grades','Grades'],['tests','checkbook','Tests']]],['Learning tools',[['discussions','chat','Discussions'],['offline','down','Offline library'],['files','files','Private files'],['explore','compass','Interest zone']]]];
const sectionNames=Object.fromEntries(sectors.flatMap(g=>g[1].map(x=>[x[0],x[2]])));
const initials=()=>state.name.trim().split(/\s+/).slice(0,2).map(x=>x.charAt(0).toUpperCase()).join('');
function shell(section){
  const group=['course','lesson'].includes(section)?'courses':section;
  $('#nav').innerHTML=sectors.flatMap(([,items])=>items).map(([id,ic,label])=>'<a class="lms-section-link '+(group===id?'active':'')+'" '+(group===id?'aria-current="page"':'')+' href="#'+id+'">'+icon(ic)+label+'</a>').join('');
  $('#avatar').textContent=initials();$('#unread').hidden=!!state.noticed;
  $('#network').innerHTML=icon(navigator.onLine?'wifi':'offline')+'<span>'+(navigator.onLine?'Online':'Offline')+'</span>';
}
function top(title,description,action=''){return '<div class="topline"><div><h1>'+esc(title)+'</h1><p>'+esc(description)+'</p></div>'+action+'</div>'}
function sectionHead(title,action=''){return '<div class="secthead"><h2>'+esc(title)+'</h2>'+action+'</div>'}
const metric=(ic,label,n,sub)=>'<div class="metric"><div class="inline"><span class="metric-icon">'+icon(ic)+'</span><span>'+esc(label)+'</span></div><b>'+n+'</b><small>'+esc(sub)+'</small></div>';
const empty=s=>'<p class="empty">'+esc(s)+'</p>';
// Course illustrations are intentionally muted, self-contained SVG art to match Grades and Tests.
function courseArt(c){
  const kind=({ds:'indigo',db:'teal',dl:'amber',net:'blue'})[c.id]||'indigo';
  const subject=({ds:'ALGORITHMS',db:'DATABASES',dl:'DIGITAL SYSTEMS',net:'NETWORKS'})[c.id]||'LEARNING';
  const art={
    ds:`<svg class="course-art-svg" viewBox="0 0 520 180" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <circle cx="421" cy="34" r="116" fill="#d5d9ff" opacity=".55"/><circle cx="300" cy="162" r="104" fill="#fff" opacity=".42"/>
      <path d="M325 66L391 30L455 66L389 102Z" fill="#fff" fill-opacity=".85" stroke="#9999e9" stroke-width="2"/>
      <path d="M325 66v57l64 35v-56z" fill="#c2c5f7" fill-opacity=".72" stroke="#9999e9" stroke-width="2"/>
      <path d="M389 102v56l66-35V66z" fill="#a9b0ee" fill-opacity=".5" stroke="#9999e9" stroke-width="2"/>
      <path d="M347 58l65 35m-24-54v54m45-25l-63 35" stroke="#ffffff" stroke-width="2" opacity=".68"/>
      <circle cx="301" cy="53" r="9" fill="#fff" stroke="#9897e6" stroke-width="2"/><circle cx="465" cy="141" r="8" fill="#fff" stroke="#9897e6" stroke-width="2"/>
      <path d="M301 63l24 20M456 136l-22-10" stroke="#9897e6" stroke-width="2" stroke-dasharray="4 5"/>
      <circle cx="468" cy="43" r="4" fill="#9999e9" opacity=".6"/><circle cx="281" cy="114" r="4" fill="#9999e9" opacity=".6"/>
    </svg>`,
    db:`<svg class="course-art-svg" viewBox="0 0 520 180" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <circle cx="406" cy="51" r="112" fill="#c6ebe5" opacity=".6"/><circle cx="301" cy="154" r="92" fill="#fff" opacity=".36"/>
      <ellipse cx="386" cy="141" rx="110" ry="24" fill="#8fcec2" opacity=".18"/>
      <path d="M320 69v61c0 17 34 30 76 30s76-13 76-30V69" fill="#c5e8e2" stroke="#72b6aa" stroke-width="2"/>
      <path d="M320 92c0 17 34 30 76 30s76-13 76-30M320 112c0 17 34 29 76 29s76-12 76-29" fill="none" stroke="#82bdb2" stroke-width="2" opacity=".77"/>
      <ellipse cx="396" cy="68" rx="76" ry="30" fill="#f9fffd" stroke="#72b6aa" stroke-width="2"/>
      <ellipse cx="396" cy="67" rx="48" ry="18" fill="#e1f3ef" stroke="#8ac3b9" stroke-width="1.5"/>
      <circle cx="334" cy="103" r="4" fill="#579d91"/><circle cx="334" cy="124" r="4" fill="#579d91"/>
      <path d="M295 84h-20M275 84l-10-10M275 84l-10 10" stroke="#6ba99f" stroke-width="2" fill="none"/><circle cx="474" cy="34" r="5" fill="#81bfb3" opacity=".7"/>
    </svg>`,
    dl:`<svg class="course-art-svg" viewBox="0 0 520 180" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <circle cx="412" cy="56" r="112" fill="#fae3c2" opacity=".57"/><circle cx="300" cy="150" r="89" fill="#fff" opacity=".35"/>
      <rect x="339" y="38" width="116" height="107" rx="17" fill="#fff9ee" stroke="#d9b482" stroke-width="2"/>
      <rect x="357" y="56" width="80" height="70" rx="11" fill="#efd5af" fill-opacity=".54" stroke="#d9b482" stroke-width="2"/>
      <path d="M324 65h15m-15 24h15m-15 24h15m116-48h18m-18 24h18m-18 24h18M371 24v14m26-14v14m26-14v14M371 145v15m26-15v15m26-15v15" stroke="#b9905c" stroke-width="3" stroke-linecap="round"/>
      <path d="M373 90l17 17 32-33" fill="none" stroke="#b98a4f" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="296" cy="65" r="5" fill="#ddba83"/><path d="M301 65h17" stroke="#d6af75" stroke-width="2"/><circle cx="481" cy="112" r="4" fill="#ddba83"/>
    </svg>`,
    net:`<svg class="course-art-svg" viewBox="0 0 520 180" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <circle cx="413" cy="56" r="118" fill="#d2e4fd" opacity=".59"/><circle cx="310" cy="158" r="101" fill="#fff" opacity=".4"/>
      <path d="M322 94L385 42L451 93L407 144L322 94L407 144L385 42M451 93L385 42" fill="none" stroke="#8aabd3" stroke-width="2.5"/>
      <circle cx="322" cy="94" r="17" fill="#f4f8fe" stroke="#739dcc" stroke-width="2.5"/>
      <circle cx="385" cy="42" r="22" fill="#f4f8fe" stroke="#739dcc" stroke-width="2.5"/>
      <circle cx="451" cy="93" r="19" fill="#f4f8fe" stroke="#739dcc" stroke-width="2.5"/>
      <circle cx="407" cy="144" r="16" fill="#f4f8fe" stroke="#739dcc" stroke-width="2.5"/>
      <circle cx="322" cy="94" r="6" fill="#89a9d2"/><circle cx="385" cy="42" r="8" fill="#89a9d2"/><circle cx="451" cy="93" r="7" fill="#89a9d2"/><circle cx="407" cy="144" r="6" fill="#89a9d2"/>
      <path d="M267 130l29-22m170-45l21-14" stroke="#82a7d2" stroke-width="2" stroke-dasharray="4 6"/>
    </svg>`
  };
  return `<div class="course-art course-art--${kind}"><span class="course-art-code">${esc(c.code)} · COURSE</span><span class="course-art-subject">${subject}</span>${art[c.id]||art.ds}</div>`;
}
function card(c, featured=false){
  const percent=pct(c), upcoming=next(c), completed=(state.done[c.id]||[]).length;
  const starred=state.stars.includes(c.id);
  const status=percent===100?'Completed':percent===0?'Not started':'In progress';
  return `<article class="coursecard coursecard--refined ${featured?'coursecard--featured':''}">
    <div class="course-media"><a href="#course/${c.id}" class="course-cover-link" aria-label="Open ${esc(c.title)}">${courseArt(c)}</a>
      <button class="iconbtn star" type="button" aria-label="${starred?'Unstar':'Star'} ${esc(c.title)}" aria-pressed="${starred}" data-act="star/${c.id}" title="${starred?'Remove favorite':'Add to favorites'}">${icon('star')}</button></div>
    <div class="coursebody">
      <div class="course-card-eyebrow"><span class="course-status-dot" aria-hidden="true"></span><span>${status}</span><span class="course-card-divider" aria-hidden="true"></span><span>${completed} / 6 activities</span></div>
      <a class="course-title-link" href="#course/${c.id}"><h3>${esc(c.title)}</h3></a>
      <p class="course-description">${esc(c.intro)}</p>
      <div class="course-mentor">${icon('user')}<span>${esc(c.mentor)}</span><span class="course-mentor-sep" aria-hidden="true">·</span><span>Faculty mentor</span></div>
      <div class="course-progress-head"><span>Course progress</span><strong>${percent}%</strong></div>
      ${prog(percent)}
      <a href="#lesson/${c.id}/${upcoming}" class="course-next-link" title="Open your next activity">${icon('play')}<span><small>UP NEXT</small><strong>${percent===100?'Review your course':esc(activities(c)[upcoming])}</strong></span>${icon('chev')}</a>
      <div class="course-card-footer"><a class="course-continue" href="#lesson/${c.id}/${upcoming}">${percent===100?'Review course':percent===0?'Start learning':'Continue learning'} ${icon('arrow')}</a><a class="course-detail-link" href="#course/${c.id}">Course outline</a></div>
    </div>
  </article>`;
}
function events(){
  const blocks=[{id:'studio',c:'ds',off:0,time:'14:00',title:'Tree traversal studio',kind:'Online class',where:'Practice classroom',index:1},{id:'lab',c:'dl',off:1,time:'10:00',title:'Digital logic lab',kind:'On-campus lab',where:'Digital Systems Lab · Block B',index:3}];
  enrolled().forEach((c,i)=>blocks.push({id:c.id+'due',c:c.id,off:2+i,time:'17:00',title:c.task,kind:'Assignment due',where:'Course workspace',index:5}));
  Object.entries(state.bookings).filter(([,v])=>v).forEach(([id,b])=>blocks.push({id:'mentor'+id,c:id,off:b.off,time:b.time,title:'Mentor consultation',kind:'Mentoring',where:'Faculty consultation room',index:0}));
  return blocks.map(x=>({...x,date:offset(x.off)})).sort((a,b)=>(a.date+a.time).localeCompare(b.date+b.time));
}
function eventRow(e){return '<button class="eventrow" data-act="event/'+e.id+'"><span class="daybox"><small>'+human(e.date,{month:'short'}).toUpperCase()+'</small><b>'+dateOf(e.date).getDate()+'</b></span><span class="listcopy"><strong>'+esc(e.title)+'</strong><small>'+esc(e.time+' · '+e.kind)+'</small></span>'+icon('chev')+'</button>'}
function dashboard(){
  const c=getCourse(state.last[0])||enrolled()[0];
  const idx=done(c,state.last[1])?next(c):state.last[1];
  const due=events().filter(e=>e.kind==='Assignment due'&&!state.submissions[e.c]&&e.date>=today());
  const up=events().filter(e=>e.date>=today()&&!(e.kind==='Assignment due'&&state.submissions[e.c])).slice(0,3);
  const total=enrolled().reduce((sum,c)=>sum+(state.done[c.id]||[]).length,0);
  const ready=scheduledTests().filter(t=>testStatus(t)==='available').length;
  const first=state.name.trim().split(/\s+/)[0]||'learner';
  const percent=Math.round(total/Math.max(1,enrolled().length*6)*100);
  return top('Welcome back, '+first+'!','Your learning space · B.E. Computer Science & Engineering · Semester III','<span class="datechip">'+icon('cal')+human(today(),{weekday:'short',day:'numeric',month:'short',year:'numeric'})+'</span>')+
   '<div class="dash-duo"><section class="hero"><div class="hero-body"><span class="hero-kicker">'+icon('sparkle')+' YOUR NEXT CHAPTER STARTS HERE</span><h2>Small steps. Big progress.</h2><p>Keep your momentum going in <strong>'+esc(c.title)+'</strong>. Pick up right where you left off.</p><div class="hero-next">'+icon('target')+' Up next: '+esc(activities(c)[idx])+'</div><div class="herobottom">'+link(pct(c)===100?'Review course':'Continue learning','lesson/'+c.id+'/'+idx,'btn primary','play')+'<div class="heropct">'+pct(c)+'% completed'+prog(pct(c))+'</div></div></div><div class="hero-visual" aria-hidden="true"><div class="visual-aura"></div><div class="visual-circle">'+icon('cap')+'</div><div class="visual-float top">'+icon('trend')+' Keep progressing</div><div class="visual-float bottom">'+icon('trophy')+' Your journey matters</div></div></section>'+
   '<section class="panel schedule">'+sectionHead('Coming up',link('Full calendar','calendar'))+(up.length?up.map(eventRow).join(''):empty('Your schedule is clear.'))+'</section></div>'+
   '<section class="section">'+sectionHead('Your learning snapshot',link('View grade reports','grades'))+'<div class="grid4">'+metric('book','Enrolled courses',enrolled().length,'Courses this semester')+metric('trend','Learning progress',percent+'%','Activities completed')+metric('checkbook','Tests available',ready,'Ready when you are')+metric('cal','Upcoming deadlines',due.length,'Assignments to submit')+'</div></section>'+
   `<section class="section course-feature-section" aria-labelledby="featured-courses-title">
      <div class="course-feature-heading"><div><span class="course-kicker">${icon('book')} PICK UP WHERE YOU LEFT OFF</span><h2 id="featured-courses-title">Pick up a course</h2><p>Your next lesson is ready. Choose a course and keep making progress.</p></div>
      ${link('View my courses','courses','course-all-link','arrow')}</div>
      <div class="grid3 course-feature-grid">${enrolled().slice(0,3).map(c=>card(c,true)).join('')}</div>
    </section>`;
}
function matches(){let list=enrolled().filter(c=>[c.title,c.code,c.mentor].some(x=>x.toLowerCase().includes(courseQuery.toLowerCase())));list=list.filter(c=>courseFilter==='all'||(courseFilter==='starred'&&state.stars.includes(c.id))||(courseFilter==='progress'&&pct(c)>0&&pct(c)<100)||(courseFilter==='completed'&&pct(c)===100)||(courseFilter==='new'&&pct(c)===0));return sort==='name'?list.sort((a,b)=>a.title.localeCompare(b.title)):sort==='progress'?list.sort((a,b)=>pct(b)-pct(a)):list}
function courseResults(){const list=matches();return list.length?list.map(card).join(''):empty('No courses match these filters.')}
function selectOpts(options,selected){return options.map(([v,s])=>'<option value="'+esc(v)+'" '+(v===selected?'selected':'')+'>'+esc(s)+'</option>').join('')}
function catalog(){
  const enrolledCourses=enrolled(), active=enrolledCourses.filter(c=>pct(c)>0&&pct(c)<100).length;
  const overall=enrolledCourses.length?Math.round(enrolledCourses.reduce((sum,c)=>sum+pct(c),0)/enrolledCourses.length):0;
  return top('My courses','All your courses in one place. Find what you need and continue learning.')+
    `<div class="course-library-summary"><div class="course-library-summary-icon">${icon('book')}</div><div class="course-library-summary-copy"><span class="course-kicker">YOUR LEARNING SPACE</span><h2>Make progress, one lesson at a time.</h2><p>Explore your enrolled courses, check what is next, and pick up right where you left off.</p></div><div class="course-library-stats"><div><strong>${enrolledCourses.length}</strong><span>Enrolled</span></div><div><strong>${active}</strong><span>In progress</span></div><div><strong>${overall}%</strong><span>Overall progress</span></div></div></div>`+
    `<div class="course-library-toolbar"><div class="course-library-toolbar-head"><div><h2>Enrolled courses <span class="course-library-count">${enrolledCourses.length}</span></h2><p>Keep your momentum going.</p></div></div><div class="course-library-filters"><label class="field course-search-field"><span>Search</span><input id="courseQuery" class="formfield" type="search" value="${esc(courseQuery)}" placeholder="Search by course, code or faculty" autocomplete="off"></label><label class="field"><span>Status</span><select id="courseFilter">${selectOpts([['all','All courses'],['progress','In progress'],['new','Not started'],['completed','Completed'],['starred','Favorites']],courseFilter)}</select></label><label class="field"><span>Sort by</span><select id="courseSort">${selectOpts([['default','Course code'],['name','Course name'],['progress','Most progress']],sort)}</select></label></div></div>`+
    `<div id="courseResults" class="grid3 course-library-grid">${courseResults()}</div>`;
}
function activityLink(c,i){return '<a class="itemlink" href="#lesson/'+c.id+'/'+i+'"><span class="icbox '+(done(c,i)?'green':'')+'">'+icon(done(c,i)?'check':icons[i])+'</span><span class="listcopy"><strong>'+activities(c)[i]+'</strong><small>'+activityTypes[i]+' · '+(done(c,i)?'Completed':'To do')+'</small></span>'+icon('chev')+'</a>'}
function course(c){
  const outline=c.unit.map((name,u)=>{const ids=u?[2,3,4,5]:[0,1];return '<details open class="outline panel"><summary>Unit 0'+(u+1)+' · '+name+'<small>'+ids.filter(i=>done(c,i)).length+'/'+ids.length+'</small></summary>'+ids.map(i=>activityLink(c,i)).join('')+'</details>'}).join('');
  return top(c.title,c.code+'  ·  Semester III  ·  '+c.mentor,link(pct(c)===100?'Review course':'Resume course','lesson/'+c.id+'/'+next(c),'btn primary','play'))+'<div class="lesson-layout"><div class="stack">'+sectionHead('Course outline',btn('Study plan','plan/'+c.id,'note','textbtn'))+outline+'</div><aside class="stack"><section class="panel">'+sectionHead('Your progress')+'<div class="progressline"><span>'+(state.done[c.id]||[]).length+' of 6 activities</span><b>'+pct(c)+'%</b></div><div class="statusline">'+prog(pct(c))+'</div>'+btn('Download study guide','guide/'+c.id,'down','textbtn')+'</section><section class="panel">'+sectionHead('Course mentor')+'<div class="inline"><span class="avatar">'+c.mentor.split(' ').map(x=>x[0]).join('')+'</span><b>'+c.mentor+'</b></div><div class="stack padded">'+btn('Book a mentoring slot','book/'+c.id,'cal')+btn('Course discussion','discuss/'+c.id,'chat')+'</div></section><section class="panel">'+sectionHead('Course grades')+link('View assessment record','grades/'+c.id,'textbtn','grades')+'</section></aside></div>';
}
function choices(q,name,value){return '<fieldset><legend>'+esc(q[0])+'</legend>'+q[1].map((v,i)=>'<label class="choice"><input type="radio" required name="'+name+'" value="'+i+'" '+(i===value?'checked':'')+'>'+esc(v)+'</label>').join('')+'</fieldset>'}
function review(c,ans){return c.quiz.map((q,i)=>'<div class="review">'+tag(ans[i]===q[2]?'Correct':'Review',ans[i]===q[2]?'green':'amber')+'<p><strong>'+q[0]+'</strong></p><p>Your answer · '+esc(q[1][ans[i]])+'</p><p>Correct answer · '+esc(q[1][q[2]])+'</p><p class="secondary">'+q[3]+'</p></div>').join('')}
function lessonBody(c,i){
  if(i===0||i===2)return '<div class="bodycopy">'+(i===0?c.first:c.body).map(p=>'<p>'+p+'</p>').join('')+(i===2?'<h3>Worked example</h3><pre>'+esc(c.example)+'</pre>':'<img class="lesson-image" src="'+art(c)+'" alt="Illustration of '+esc(c.short)+'">')+'</div>';
  if(i===1)return '<video controls playsinline preload="metadata" poster="'+art(c)+'" src="'+media['lesson'+courses.indexOf(c)]+'" aria-label="'+c.video+'"></video><p class="meta padded">18-second visual walkthrough · On-screen captions</p><details class="fold"><summary>Read transcript</summary><ol>'+c.transcript.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ol></details>';
  if(i===3){const val=state.answers[c.id];return '<form id="practiceForm">'+choices(c.practice,'practice',val)+'<button class="btn primary">Check answer</button></form>'+(val!==undefined?'<p class="note padded">'+(val===c.practice[2]?'Correct. ':'Try again. ')+c.practice[3]+'</p>':'')}
  if(i===4){const attempts=state.attempts[c.id]||[];if(activeAttempt===c.id)return '<form id="quizForm">'+c.quiz.map((q,k)=>choices(q,'q'+k,state.drafts['quiz-'+c.id]?.[k])).join('')+'<div class="actions"><button class="btn primary">Submit quiz</button>'+btn('Save & exit','quizexit/'+c.id)+'</div></form>';
    const last=attempts.at(-1);return '<p>Answer three questions. Each correct answer earns one mark. You can review every attempt and practise again.</p><div class="actions padded">'+btn(last?'Try again':'Start quiz','quizstart/'+c.id,'pen','btn primary')+(last?link('All attempts','grades/'+c.id):'')+'</div>'+(last?'<div class="rule"><h3>Latest result · '+last.score+' / 3</h3>'+review(c,last.answers)+'</div>':'');
  }
  const sub=state.submissions[c.id];return '<div class="bodycopy"><p>'+esc(c.brief)+'</p><h3>Submission criteria</h3><ul>'+c.rubric.map(x=>'<li>'+x+'</li>').join('')+'</ul></div><div class="rule">'+(sub?tag('Submitted in personal learning workspace','green')+'<p class="meta padded">'+esc(new Date(sub.ts).toLocaleString('en-IN'))+'</p><p class="longtext padded">'+esc(sub.text)+'</p>':'<form id="assignmentForm"><label class="field">Your response<textarea class="formfield" name="answer" id="assignmentText" maxlength="12000" required placeholder="Enter your solution and reasoning…">'+esc(state.drafts['task-'+c.id]||'')+'</textarea></label><div class="actions padded"><button class="btn primary">Submit assignment</button>'+btn('Save draft','savedraft/'+c.id)+'</div></form>')+'</div>';
}
function lesson(c,i){
  const key=c.id+'-'+i;let action=i<3?btn(done(c,i)?'Completed':'Mark complete','complete/'+c.id+'/'+i,'check',done(c,i)?'btn':'btn primary'):'';
  if(done(c,i)&&i<3)action=tag('Completed','green');
  return top(activities(c)[i],c.code+'  ·  '+c.title+'  ·  Unit 0'+(i<2?'1':'2'),link('Course outline','course/'+c.id,'btn','list'))+'<div class="lesson-layout"><article class="panel"><div class="secthead"><h2>'+activityTypes[i]+'</h2><span class="meta">Activity '+(i+1)+' of 6</span></div>'+lessonBody(c,i)+'<div class="reading-nav rule">'+action+'<div class="actions">'+(i?link('Previous','lesson/'+c.id+'/'+(i-1)):'')+(i<5?link('Next activity','lesson/'+c.id+'/'+(i+1),'btn'):link('Back to course','course/'+c.id,'btn'))+'</div></div></article><aside class="stack"><section class="panel">'+sectionHead('Lesson notes')+'<form id="notesForm"><label class="field">Private note<textarea name="note" maxlength="6000" class="formfield" placeholder="Write a thought to revisit…">'+esc(state.notes[key]||'')+'</textarea></label><button class="btn padded">Save note</button></form></section><section class="panel">'+sectionHead('Learning tools')+'<div class="stack">'+btn('Study guide','guide/'+c.id,'down')+btn('Course discussion','discuss/'+c.id,'chat')+'</div></section></aside></div>';
}

/* Assessment fixtures are demo content for the offline student prototype. */
const scheduledTests=()=>enrolled().flatMap(c=>[
  {id:c.id+'-fundamentals',course:c.id,title:'Unit 1 · Foundations test',unit:'Unit 01',opens:offset(-1),closes:offset(7),duration:15,questions:c.quiz},
  {id:c.id+'-applications',course:c.id,title:'Unit 2 · Applications test',unit:'Unit 02',opens:offset(4),closes:offset(12),duration:20,questions:[c.practice,c.quiz[1],c.quiz[2]]}
]);
const testById=id=>scheduledTests().find(t=>t.id===id);
const scoredTests=()=>state.testAttempts||{};
function testStatus(t){if(scoredTests()[t.id])return 'completed';if(today()<t.opens)return 'upcoming';if(today()>t.closes)return 'closed';return 'available'}
const testStatusLabel=s=>({completed:'Completed',upcoming:'Upcoming',available:'Available now',closed:'Closed'})[s];
const fmtTime=ts=>new Date(ts).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'});
function gradeRecords(c){
  const quizzes=state.attempts[c.id]||[],latest=quizzes.at(-1),records=[];
  if(latest)records.push({name:'Unit self-assessment',type:'Course quiz',earned:latest.score,total:c.quiz.length,ts:latest.ts,href:'lesson/'+c.id+'/4'});
  for(const t of scheduledTests().filter(t=>t.course===c.id)){
    const a=scoredTests()[t.id];if(a)records.push({name:t.title,type:'Scheduled test',earned:a.score,total:t.questions.length,ts:a.ts,href:'grades/'+c.id,tid:t.id});
  }
  return records.sort((a,b)=>a.ts-b.ts);
}
function gradeData(c){const rec=gradeRecords(c),earned=rec.reduce((n,r)=>n+r.earned,0),total=rec.reduce((n,r)=>n+r.total,0);return {rec,earned,total,percent:total?Math.round(100*earned/total):null}}
function testCount(c){return scheduledTests().filter(t=>t.course===c.id&&scoredTests()[t.id]).length}
function grades(selected='all'){
  const list=enrolled();
  if(selected!=='all'){
    const c=list.find(c=>c.id===selected);
    if(!c)return top('Grade report unavailable','Choose an enrolled course to view its results.',link('All grade reports','grades','btn'));
    return gradeDetail(c);
  }
  const graded=list.filter(c=>gradeData(c).total),results=list.reduce((n,c)=>n+gradeData(c).rec.length,0);
  const upcoming=scheduledTests().filter(t=>testStatus(t)==='available'||testStatus(t)==='upcoming').length;
  return top('Grades & performance','A clearer picture of your learning, course by course.')+
    '<section class="grade-intro"><div><span class="smallcap">'+icon('sparkle')+' YOUR ACADEMIC JOURNEY · SEMESTER III</span><h2>Every bit of progress deserves to be seen.</h2><p>See your graded activities, understand your strengths, and celebrate each improvement with a clear course-by-course view.</p></div>'+link('Explore scheduled tests','tests','btn','arrow')+'</section>'+
    '<div class="grid4 grade-metrics">'+metric('book','Enrolled courses',list.length,'Part of your semester')+metric('trend','Courses with results',graded.length,'Scored assessments')+metric('trophy','Assessments graded',results,'Latest quiz and tests')+metric('cal','Tests on your radar',upcoming,'Available or coming soon')+'</div>'+
    '<section class="section" style="margin-top:0">'+sectionHead('Course grade reports',tag(list.length+' enrolled courses'))+
    '<p class="test-section-sub">Select a card to explore scores, test feedback and a detailed performance breakdown.</p><div class="grade-cards">'+list.map(c=>{
      const d=gradeData(c),status=d.total?'Current performance':'Your journey starts here';
      return '<a href="#grades/'+c.id+'" class="grade-course" aria-label="View grade analysis for '+esc(c.title)+'"><div class="grade-course-top"><div class="grade-course-name"><span class="grade-course-icon">'+icon('book')+'</span><div><span class="grade-code">'+esc(c.code)+' · SEMESTER III</span><h3>'+esc(c.title)+'</h3><span class="meta">'+esc(c.mentor)+' · Faculty mentor</span></div></div><span class="grade-score '+(d.percent===null?'is-empty':'')+'" style="--score:'+(d.percent??0)+'"><strong>'+(d.percent===null?'—':d.percent+'%')+'</strong><small>'+(d.total?'Current':'No marks')+'</small></span></div><div><div class="grade-comparison-label"><strong>'+status+'</strong><span class="secondary">'+d.rec.length+' graded '+(d.rec.length===1?'activity':'activities')+'</span></div><div class="grade-track"><span style="width:'+(d.percent??0)+'%"></span></div></div><div class="grade-foot"><span>'+testCount(c)+' of '+scheduledTests().filter(t=>t.course===c.id).length+' scheduled tests completed</span><b>Explore report '+icon('arrow')+'</b></div></a>';
    }).join('')+'</div></section><p class="grade-note">Results here are calculated from your self-study quizzes and scheduled practice tests, not official college grades or GPA. Written assignment responses are not graded in this workspace.</p>';
}
function gradeDetail(c){
  const d=gradeData(c),quiz=state.attempts[c.id]||[],tlist=scheduledTests().filter(t=>t.course===c.id);
  const quizRec=d.rec.find(r=>r.type==='Course quiz'),testRec=d.rec.filter(r=>r.type==='Scheduled test'),tEarned=testRec.reduce((n,r)=>n+r.earned,0),tMax=testRec.reduce((n,r)=>n+r.total,0);
  const line=(label,score,total)=>'<div><div class="grade-comparison-label"><span>'+esc(label)+'</span><strong>'+(total?Math.round(score/total*100)+'%':'Not graded')+'</strong></div><div class="grade-track"><span style="width:'+(total?Math.round(score/total*100):0)+'%"></span></div></div>';
  return top('Course grade analysis',c.code+' · '+c.title,link('All course grades','grades','btn','back'))+
    '<div class="report-layout"><div class="stack"><section class="panel"><div class="report-header"><span class="report-score '+(d.percent===null?'no-result':'')+'"><strong>'+(d.percent===null?'—':d.percent+'%')+'</strong><small>'+(d.total?'Current score':'Not graded')+'</small></span><div><span class="smallcap secondary">'+esc(c.code)+' · SEMESTER III</span><h2 style="margin:5px 0">'+esc(c.title)+'</h2><p class="secondary">'+(d.total?'Your average across marked activities.':'There are no scored assessments yet for this course.')+'</p></div></div><div class="grade-facts"><div><strong>'+d.earned+' / '+d.total+'</strong><small>Marks earned / available</small></div><div><strong>'+d.rec.length+'</strong><small>Graded assessments</small></div><div><strong>'+quiz.length+'</strong><small>Self-assessment attempts</small></div><div><strong>'+testCount(c)+' / '+tlist.length+'</strong><small>Scheduled tests completed</small></div></div></section>'+
    '<section class="panel">'+sectionHead('Score breakdown')+'<div class="grade-comparison">'+line('Unit self-assessment',quizRec?.earned||0,quizRec?.total||0)+line('Scheduled tests',tEarned,tMax)+'</div><p class="grade-note">These percentages use actual marked questions. An unattempted assessment is not counted as zero; assignments without faculty marks are excluded.</p></section>'+
    '<section class="panel">'+sectionHead('Assessment history')+(d.rec.length?d.rec.map(r=>'<div class="assessment-row"><div><strong>'+esc(r.name)+'</strong><span class="meta">'+esc(r.type)+' · '+fmtTime(r.ts)+'</span></div><div class="right"><b>'+r.earned+' / '+r.total+'</b><small>'+Math.round(r.earned/r.total*100)+'%</small></div></div>').join(''):empty('No results yet. Complete a course quiz or an available scheduled test to see your marks.'))+'</section>'+
    '<section class="panel">'+sectionHead('Quiz attempt review',link('Open course quiz','lesson/'+c.id+'/4'))+(quiz.length?quiz.slice().reverse().map((a,i)=>'<details class="outline"><summary style="padding:12px">Attempt '+(quiz.length-i)+' · '+a.score+'/'+c.quiz.length+' · '+fmtTime(a.ts)+'</summary><div style="padding:0 16px 16px">'+review(c,a.answers)+'</div></details>').join(''):empty('You have not taken the course self-assessment yet.'))+'</section>'+
    '<section class="panel">'+sectionHead('Scheduled test results',link('All scheduled tests','tests'))+tlist.map(t=>{const a=scoredTests()[t.id],status=testStatus(t);return '<div class="line"><div class="inline space wrap"><span><b>'+esc(t.title)+'</b><span class="meta">'+human(t.opens)+' – '+human(t.closes)+' · '+t.questions.length+' questions</span></span>'+(a?tag(a.score+' / '+t.questions.length+' marks','green'):tag(testStatusLabel(status),status==='available'?'green':'amber'))+'</div>'+(a?'<details class="fold"><summary>Review answers & explanations</summary><div>'+reviewTest(t,a.answers)+'</div></details>':status==='available'?'<div class="padded">'+link('Take this test','tests/'+t.id,'btn primary')+'</div>':'')+'</div>'}).join('')+'</section></div>'+
    '<aside class="stack"><section class="panel">'+sectionHead('Next actions')+'<p class="secondary">Keep building your course record.</p><div class="stack padded">'+link('Take a scheduled test','tests','btn primary','checkbook')+link('Open course workspace','course/'+c.id,'btn','book')+'</div></section><section class="panel">'+sectionHead('Written assignment')+'<p><strong>'+esc(c.task)+'</strong></p><div class="padded">'+(state.submissions[c.id]?tag('Submitted · Awaiting faculty grade','amber'):tag('Not submitted'))+'</div><p class="grade-note">Submission receipts do not imply an awarded official grade.</p>'+link('View assignment','lesson/'+c.id+'/5','textbtn')+'</section><section class="panel">'+sectionHead('How this score works')+'<p class="secondary">Current score = total marks earned ÷ total marks available across the latest course quiz and completed scheduled tests.</p><p class="grade-note">This analysis excludes unmarked work and is not an official weighted course grade, semester GPA, or college transcript.</p></section></aside></div>';
}
function reviewTest(t,answers){return t.questions.map((q,i)=>'<div class="review">'+tag(answers[i]===q[2]?'Correct':'Incorrect',answers[i]===q[2]?'green':'amber')+'<p><strong>Question '+(i+1)+': '+esc(q[0])+'</strong></p><p>Your answer · '+esc(q[1][answers[i]]??'No answer')+'</p><p>Correct answer · '+esc(q[1][q[2]])+'</p><p class="secondary">'+esc(q[3])+'</p></div>').join('')}
function tests(id){
  if(id){const t=testById(id);if(!t)return top('Test unavailable','Choose a scheduled test from one of your enrolled courses.',link('All tests','tests','btn'));return testDetail(t)}
  const list=scheduledTests().filter(t=>testFilter==='all'||t.course===testFilter),open=list.filter(t=>testStatus(t)==='available').length,upcoming=list.filter(t=>testStatus(t)==='upcoming').length,completed=list.filter(t=>testStatus(t)==='completed').length;
  const order={available:0,upcoming:1,completed:2,closed:3};list.sort((a,b)=>order[testStatus(a)]-order[testStatus(b)]||a.opens.localeCompare(b.opens));
  return top('Tests','Take scheduled assessments for the courses you are currently enrolled in.')+
    '<section class="grade-intro"><div><span class="smallcap">'+icon('sparkle')+' STUDENT ASSESSMENTS · SEMESTER III</span><h2>Show what you have learned.</h2><p>Stay ahead of upcoming assessments, take available tests confidently, and review your results whenever you need.</p></div>'+link('Explore grade reports','grades','btn','arrow')+'</section>'+
    '<div class="grid4 grade-metrics">'+metric('checkbook','Available now',open,'Ready to take')+metric('cal','Upcoming',upcoming,'Not open yet')+metric('check','Completed',completed,'Marked automatically')+metric('book','Enrolled courses',enrolled().length,'Eligible course tests')+'</div>'+
    '<section class="section" style="margin-top:0">'+sectionHead('Scheduled assessments')+'<div class="test-toolbar"><label class="field">Filter by enrolled course<select id="testFilter">'+selectOpts([['all','All enrolled courses'],...enrolled().map(c=>[c.id,c.title])],testFilter)+'</select></label><span class="secondary">'+list.length+' scheduled test'+(list.length===1?'':'s')+'</span></div><div class="test-grid">'+(list.length?list.map(t=>{
      const c=getCourse(t.course),status=testStatus(t),a=scoredTests()[t.id],label=testStatusLabel(status);
      return '<article class="test-card"><div class="inline space wrap"><span class="grade-code">'+esc(c.code)+' · '+esc(t.unit)+'</span>'+tag(label,status==='completed'||status==='available'?'green':status==='upcoming'?'amber':'')+'</div><div class="test-identity"><span class="test-identity-icon">'+icon('checkbook')+'</span><div><h3>'+esc(t.title)+'</h3><p class="secondary padded" style="margin-top:4px">'+esc(c.title)+'</p></div></div><div class="test-meta"><span>'+icon('cal')+human(t.opens,{day:'numeric',month:'short'})+' – '+human(t.closes,{day:'numeric',month:'short',year:'numeric'})+'</span><span>'+icon('clock')+t.duration+' min suggested</span><span>'+icon('checkbook')+t.questions.length+' questions · '+t.questions.length+' marks</span></div><div class="test-action"><span class="secondary">'+(a?'Scored '+a.score+' / '+t.questions.length:status==='available'?'One submission allowed':status==='upcoming'?'Opens '+human(t.opens):'Submission window ended')+'</span>'+(a?link('View grade','grades/'+c.id,'btn'):status==='closed'?link('View course','course/'+c.id,'btn'):link(status==='available'?'Take test':'View details','tests/'+t.id,'btn '+(status==='available'?'primary':'')))+'</div></article>';
    }).join(''):empty('No scheduled tests for this course.'))+'</div></section><p class="grade-note">These are self-study practice assessments, separate from the institutional exam timetable. They are not proctored. Your practice results are included in these learning reports.</p>';
}
function testDetail(t){
  const c=getCourse(t.course),a=scoredTests()[t.id],status=testStatus(t);
  const back=link('Back to all tests','tests','btn','back');
  if(a)return top(t.title,c.code+' · '+c.title,back)+'<div class="test-paper stack"><section class="panel"><div class="inline space wrap">'+tag('Completed','green')+'<span class="secondary">'+fmtTime(a.ts)+'</span></div><h2 style="font-size:26px;margin:12px 0">'+a.score+' / '+t.questions.length+' marks · '+Math.round(a.score/t.questions.length*100)+'%</h2><p class="secondary">Your attempt is recorded. See the course grade analysis for the full breakdown.</p><div class="actions padded">'+link('Open course grade report','grades/'+c.id,'btn primary','grades')+'</div></section><section class="panel">'+sectionHead('Answer review')+reviewTest(t,a.answers)+'</section></div>';
  if(status!=='available')return top(t.title,c.code+' · '+c.title,back)+'<section class="panel test-paper"><div class="inline space wrap">'+tag(testStatusLabel(status),status==='upcoming'?'amber':'')+'<span class="secondary">'+esc(t.unit)+'</span></div><h2 class="padded">'+(status==='upcoming'?'This test is scheduled for a later date.':'The submission period has ended.')+'</h2><p class="secondary padded">Opens '+human(t.opens,{day:'numeric',month:'long',year:'numeric'})+' · Closes '+human(t.closes,{day:'numeric',month:'long',year:'numeric'})+'</p><div class="actions padded">'+back+'</div></section>';
  if(activeTest!==t.id)return top(t.title,c.code+' · '+c.title,back)+'<section class="panel test-paper"><div class="inline space wrap">'+tag('Available now','green')+'<span class="secondary">'+esc(t.unit)+'</span></div><h2 style="font-size:23px;margin:14px 0 9px">'+esc(t.title)+'</h2><p>'+esc(c.title)+'</p><div class="grade-facts"><div><strong>'+t.questions.length+'</strong><small>Multiple-choice questions</small></div><div><strong>'+t.questions.length+'</strong><small>Maximum marks</small></div><div><strong>'+t.duration+' min</strong><small>Suggested duration</small></div><div><strong>1</strong><small>Submission allowed</small></div></div><p class="grade-note">This is a self-study practice assessment. Each correct answer earns one mark; incorrect answers earn zero. No timer is enforced. Once submitted, your result appears in Grade reports and cannot be resubmitted.</p><div class="actions padded">'+btn('Start test','teststart/'+t.id,'play','btn primary')+'</div></section>';
  const draft=state.drafts['test-'+t.id]||[];
  return top(t.title,c.code+' · '+c.title,tag('In progress','green'))+'<div class="test-paper"><section class="panel"><div class="inline space wrap">'+tag('Test in progress','green')+'<span class="meta">'+t.questions.length+' questions · '+t.duration+' min suggested · '+t.questions.length+' marks</span></div><h2 style="margin-top:12px">'+esc(t.title)+'</h2><p class="grade-note">Choose one answer for each question. Answers are saved automatically in your learning workspace.</p></section><form id="scheduledTestForm">'+t.questions.map((q,i)=>'<div class="test-question"><fieldset><legend><span class="question-num">'+String(i+1).padStart(2,'0')+'</span>'+esc(q[0])+'</legend>'+q[1].map((v,j)=>'<label class="choice"><input type="radio" name="q'+i+'" value="'+j+'" required '+(draft[i]===j?'checked':'')+'>'+esc(v)+'</label>').join('')+'</fieldset></div>').join('')+'<div class="test-paper-actions"><span class="secondary">All questions required · '+t.questions.length+' marks</span><div class="actions">'+btn('Save & exit','testexit/'+t.id)+'<button class="btn primary" type="submit">Submit test</button></div></div></form></div>';
}
function calendar(){
  const d=dateOf(monthStart),year=d.getFullYear(),month=d.getMonth(),count=new Date(year,month+1,0).getDate(),list=events(),selected=list.filter(e=>e.date===calendarDay);
  let grid=['Mo','Tu','We','Th','Fr','Sa','Su'].map(s=>'<span>'+s+'</span>').join('')+'<i></i>'.repeat((d.getDay()+6)%7);
  for(let i=1;i<=count;i++){const key=dayKey(new Date(year,month,i)),ev=list.filter(x=>x.date===key);grid+='<button class="'+(calendarDay===key?'selected ':'')+(today()===key?'today ':'')+(ev.length?'has-event':'')+'" aria-label="'+human(key,{day:'numeric',month:'long'})+', '+ev.length+' events" aria-pressed="'+(calendarDay===key)+'" data-act="day/'+key+'">'+i+'</button>'}
  return top('Calendar','Online classes, on-campus labs, mentoring and submission dates.',btn('Today','today','cal'))+'<div class="grid2"><section class="panel"><div class="secthead"><h2>'+human(monthStart,{month:'long',year:'numeric'})+'</h2><div class="actions"><button class="iconbtn" aria-label="Previous month" data-act="month/-1">'+icon('back')+'</button><button class="iconbtn" aria-label="Next month" data-act="month/1">'+icon('chev')+'</button></div></div><div class="monthgrid">'+grid+'</div></section><div class="stack"><section class="panel">'+sectionHead(human(calendarDay,{weekday:'long',day:'numeric',month:'long'}))+(selected.map(eventRow).join('')||empty('No events scheduled for this day.'))+'</section><section class="panel">'+sectionHead('This month')+(list.filter(e=>e.date.slice(0,7)===monthStart.slice(0,7)).map(eventRow).join('')||empty('No events in this month.'))+'</section></div></div>';
}
const prompts={ds:'Which traversal would you use to list student IDs in sorted order, and why?',db:'How would you include courses with no enrolments in a report?',dl:'Which two input pairs distinguish OR from XOR?',net:'Why can the link-layer destination change while the packet destination stays the same?'};
function discussions(){const c=getCourse(discussionCourse)||enrolled()[0],posts=state.posts.filter(p=>p.c===c.id);return top('Discussions','Explore a course question and keep your responses in this personal learning workspace.')+'<label class="field" style="max-width:360px">Discussion board<select id="board">'+selectOpts(enrolled().map(c=>[c.id,c.title]),c.id)+'</select></label><article class="panel padded">'+sectionHead(c.short+' discussion',tag(c.code))+'<div class="line"><span class="meta">'+c.mentor+' · Course prompt</span><h3 class="padded">'+prompts[c.id]+'</h3></div>'+posts.map(p=>'<div class="line"><span class="meta">'+esc(p.name)+' · '+esc(new Date(p.ts).toLocaleString('en-IN'))+'</span><p class="longtext">'+esc(p.text)+'</p></div>').join('')+'<form class="padded" id="postForm"><label class="field">Your response<textarea class="formfield" name="reply" required maxlength="3000" placeholder="Add your reasoning or ask a question…">'+esc(state.drafts['post-'+c.id]||'')+'</textarea></label><button class="btn primary padded">Post response</button></form></article>'}
function offline(){
  return top('Offline library','Take your lessons, recordings and learning record with you.',btn('Download workspace','portable','down','btn primary'))+'<div class="note">'+icon('info')+' &nbsp; Download the HTML workspace once and open it in your browser without internet. The copy includes your current progress, notes, quiz attempts and assignment drafts. Private files are not included in the downloaded copy.</div><section class="panel padded">'+sectionHead('Course study guides')+enrolled().map(c=>'<div class="itemlink"><span class="icbox">'+icon('book')+'</span><span class="listcopy"><strong>'+c.title+'</strong><small>'+c.code+' · Printable HTML study guide</small></span>'+btn('Download','guide/'+c.id,'down','textbtn')+'</div>').join('')+'</section><section class="panel padded">'+sectionHead('Saved notes')+(Object.entries(state.notes).filter(([,v])=>v.trim()).map(([k,v])=>{const [id,i]=k.split('-'),c=getCourse(id);return '<div class="line">'+link(activities(c)[i],'lesson/'+id+'/'+i)+'<p class="longtext">'+esc(v)+'</p></div>'}).join('')||empty('Notes you save in a lesson appear here.'))+'</section>';
}
function filesPage(){return top('Private files',''+(offlineMode?'Store your own reference files in this browser on this device.':'Keep your reference files securely in your student learning account.')+'')+'<section class="panel">'+sectionHead('My files',btn('Add file','filepick','files','btn primary'))+'<input id="fileinput" hidden type="file" multiple><div id="filelist" aria-live="polite">Loading files…</div></section>'}
let vault;
function database(){if(!vault)vault=new Promise((resolve,reject)=>{const r=indexedDB.open('vcet-learning-private-files',1);r.onupgradeneeded=()=>r.result.createObjectStore('files',{keyPath:'id'});r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)}).catch(e=>{vault=null;throw e});return vault}
async function fileOp(mode,fn){const db=await database();return new Promise((resolve,reject)=>{const tx=db.transaction('files',mode),r=fn(tx.objectStore('files'));tx.oncomplete=()=>resolve(r.result);tx.onerror=tx.onabort=()=>reject(tx.error||r.error)})}
async function refreshFiles(){
  const el=$('#filelist');if(!el)return;
  try{
    let all;
    if(offlineMode)all=await fileOp('readonly',s=>s.getAll());
    else{const response=await fetch('/my/campus/student/lms/files',{credentials:'same-origin'});const data=await response.json();if(!response.ok)throw new Error(data.error);all=data.files;}
    el.innerHTML=all.length?all.map(f=>'<div class="itemlink"><span class="icbox">'+icon('note')+'</span><span class="listcopy"><strong class="longtext">'+esc(f.name)+'</strong><small>'+Math.max(1,Math.ceil((f.size||f.blob?.size||0)/1024))+' KB · '+esc(new Date(f.ts).toLocaleDateString('en-IN'))+'</small></span>'+btn('Save copy','getfile/'+f.id,'down','textbtn')+btn('Remove','dropfile/'+f.id,'','textbtn')+'</div>').join(''):empty('Your library is empty. Add a document to keep it here.');
  }catch{el.innerHTML='<p class="note error">Your private files could not be loaded. Please try again.</p>'+btn('Retry','retryfiles')}
}
function explore(){
  const c=getCourse('net');
  const enrolledNow=state.enrolled.includes(c.id);
  const completed=(state.done[c.id]||[]).length;
  const completion=pct(c);
  const firstUnfinished=next(c);
  const unitMeta=[
    {start:0,count:2,detail:c.reading+' · '+c.video},
    {start:2,count:4,detail:c.lesson+' · '+c.task}
  ];
  const networkArt=`<svg class="iz-network-art" viewBox="0 0 610 250" aria-hidden="true" focusable="false">
    <circle cx="395" cy="122" r="129" fill="#ffffff" fill-opacity=".22"/>
    <circle cx="463" cy="101" r="107" fill="none" stroke="#fff" stroke-opacity=".49" stroke-width="1.3"/>
    <path d="M171 155L276 96L382 145L475 69L530 151L382 145L276 96L530 151" fill="none" stroke="#92a2dc" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M276 96L354 42L475 69M171 155L302 206L382 145M302 206L530 151" fill="none" stroke="#73b0b3" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="7 6" opacity=".83"/>
    <path d="M171 155L171 183M530 151L549 173" stroke="#9da7d9" stroke-width="2" stroke-linecap="round" opacity=".55"/>
    <rect x="247" y="69" width="58" height="55" rx="15" fill="#fbfbff" stroke="#8587d6" stroke-width="2.7"/>
    <rect x="352" y="117" width="60" height="58" rx="15" fill="#fbfbff" stroke="#8587d6" stroke-width="2.7"/>
    <rect x="447" y="42" width="56" height="54" rx="14" fill="#fbfbff" stroke="#6eafae" stroke-width="2.7"/>
    <rect x="505" y="127" width="53" height="50" rx="15" fill="#fbfbff" stroke="#6eafae" stroke-width="2.7"/>
    <rect x="146" y="131" width="50" height="50" rx="13" fill="#fbfbff" stroke="#8c97d1" stroke-width="2.5"/>
    <rect x="282" y="188" width="40" height="40" rx="12" fill="#fbfbff" stroke="#6eafae" stroke-width="2.5"/>
    <circle cx="276" cy="96" r="8" fill="#8786d9"/><circle cx="382" cy="145" r="8" fill="#8786d9"/>
    <circle cx="475" cy="69" r="7" fill="#76b6b3"/><circle cx="530" cy="151" r="7" fill="#76b6b3"/>
    <circle cx="171" cy="155" r="6" fill="#8b9ed8"/><circle cx="302" cy="208" r="5.5" fill="#76b6b3"/>
    <circle cx="414" cy="50" r="4" fill="#f3b866"/><circle cx="573" cy="201" r="4" fill="#9fa5df"/><circle cx="231" cy="205" r="3" fill="#9ebccf"/>
    <path d="M438 183h16m-8-8v16M230 39h12m-6-6v12" stroke="#a5a6e0" stroke-width="2" stroke-linecap="round" opacity=".72"/>
  </svg>`;
  const outline=c.unit.map((name,i)=>{
    const u=unitMeta[i];
    const unitLink=enrolledNow?`<a class="iz-unit-open" href="#lesson/${c.id}/${u.start}">Open unit ${icon('arrow')}</a>`:'';
    return `<div class="iz-unit"><span class="iz-unit-number">0${i+1}</span><div class="iz-unit-body">
      <span class="iz-unit-eyebrow">UNIT 0${i+1}</span><h3>${esc(name)}</h3>
      <p>${esc(u.detail)}</p><div class="iz-unit-foot"><span class="iz-activity-count">${icon('book')}${u.count} activities</span>${unitLink}</div>
    </div></div>`;
  }).join('');
  const action=enrolledNow?
    `${link('Open enrolled course','course/'+c.id,'btn primary','book')}${link('Continue learning','lesson/'+c.id+'/'+firstUnfinished,'iz-secondary-link','arrow')}`:
    btn('Enrol in elective','enrol/'+c.id,'book','btn primary');
  const progress=enrolledNow?
    `<div class="iz-progress"><div class="iz-progress-head"><span>Your course progress · ${completed} of 6 activities</span><strong>${completion}%</strong></div>${prog(completion)}</div>`:
    `<div class="iz-before-enrol">${icon('info')}Explore the course outline and enrol when you're ready.</div>`;
  return top('Interest zone','Discover open electives and broaden your learning beyond core courses.')+
    `<section class="iz-spotlight" aria-label="Discover open electives"><div class="iz-spotlight-copy">
       <span class="iz-eyebrow">${icon('sparkle')} DISCOVER MORE</span>
       <h2>Make room for something new.</h2>
       <p>Explore an open elective, discover a new area of interest and build skills that complement your semester.</p>
     </div><div class="iz-spotlight-stamp" aria-label="One open elective available"><span class="iz-stamp-icon">${icon('compass')}</span><span><strong>01</strong><small>Open elective available</small></span></div></section>`+
    `<div class="iz-grid">
      <article class="iz-feature" aria-labelledby="iz-course-title">
        <div class="iz-cover"><div class="iz-cover-words"><span class="iz-cover-overline">${icon('compass')} EXPLORE • OE204</span>
          <strong>HOW THE WORLD<br>CONNECTS.</strong><small>LEARN THE LANGUAGE OF NETWORKS</small></div>${networkArt}</div>
        <div class="iz-feature-body">
          <div class="iz-feature-top"><span class="iz-course-code">${esc(c.code)} · OPEN ELECTIVE</span>
            <span class="iz-enrol-badge ${enrolledNow?'is-enrolled':''}"><span class="iz-dot" aria-hidden="true"></span>${enrolledNow?'Enrolled':'Available to enrol'}</span></div>
          <h2 id="iz-course-title">${esc(c.title)}</h2><p class="iz-course-description">${esc(c.intro)}</p>
          <div class="iz-course-facts"><span class="iz-fact">${icon('book')}<strong>2</strong> units</span>
            <span class="iz-fact">${icon('list')}<strong>6</strong> activities</span>
            <span class="iz-fact">${icon('user')}<strong>${esc(c.mentor)}</strong></span></div>
          ${progress}<div class="iz-actions">${action}</div>
        </div></article>
      <aside class="iz-outline" aria-labelledby="iz-outline-title"><div class="iz-outline-heading">
        <span class="iz-outline-head-icon">${icon('book')}</span><div><h2 id="iz-outline-title">Elective outline</h2>
          <p>See what you'll explore across the course.</p></div><span class="iz-outline-count">2 units</span></div>
        <div class="iz-timeline">${outline}</div>
        <div class="iz-format"><div class="iz-format-title">${icon('target')} A little learning, every step</div>
          <div class="iz-format-steps"><span>${icon('book')} Reading</span><span>${icon('video')} Recording</span><span>${icon('checkbook')} Practice & quiz</span><span>${icon('pen')} Assignment</span></div>
        </div></aside>
    </div>`+
    `<div class="iz-footnote"><span class="iz-footnote-icon">${icon('sparkle')}</span>
       <span><strong>Curiosity makes progress.</strong> Follow a packet's journey, understand routing decisions and put your knowledge into practice.</span></div>`;
}
function dialog(title,html){$('#dialogtitle').textContent=title;$('#modalbody').innerHTML=html;if(!$('#modal').open)$('#modal').showModal()}
function close(){if($('#modal').open)$('#modal').close()}
function menu(){}
function download(obj,name){const u=URL.createObjectURL(obj),a=document.createElement('a');a.href=u;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),30000)}
function guide(c){
  const doc='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+c.title+' · VCET guide</title><style>body{max-width:760px;margin:32px auto;padding:0 20px;color:#0f172a;font:16px/1.6 Segoe UI,Arial,sans-serif}header{border-bottom:3px solid #4f46e5}pre{white-space:pre-wrap;background:#eef2ff;padding:16px}h2{margin-top:32px}</style><header><p>VCET Learning Studio · '+c.code+'</p><h1>'+c.title+'</h1><p>Offline study guide · '+c.mentor+'</p></header><main><h2>'+c.reading+'</h2>'+c.first.map(p=>'<p>'+esc(p)+'</p>').join('')+'<h2>'+c.video+'</h2><ol>'+c.transcript.map(p=>'<li>'+esc(p)+'</li>').join('')+'</ol><h2>'+c.lesson+'</h2>'+c.body.map(p=>'<p>'+esc(p)+'</p>').join('')+'<pre>'+esc(c.example)+'</pre><h2>Check your understanding</h2><p>'+c.practice[0]+'</p><details><summary>Show explanation</summary>'+c.practice[3]+'</details><h2>'+c.task+'</h2><p>'+c.brief+'</p></main></html>';
  download(new Blob([doc],{type:'text/html'}),c.code+' study guide.html');if(!state.saved.includes(c.id)){state.saved.push(c.id);save()}toast('Study guide prepared for download.');
}
async function portable(){
  toast('Preparing your offline workspace…');
  const clone=document.documentElement.cloneNode(true);
  const readData=async url=>{const response=await fetch(url,{credentials:'same-origin'});if(!response.ok)throw new Error('A learning asset could not be downloaded.');const blob=await response.blob();return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob)})};
  const embedded=Object.fromEntries(await Promise.all(Object.entries(media).map(async([key,url])=>[key,url.startsWith('data:')?url:await readData(url)])));
  const stylesheet=clone.querySelector('#learning-studio-style');
  if(stylesheet.tagName==='LINK'){const response=await fetch(stylesheet.href);if(!response.ok)throw new Error('Styles could not be downloaded.');const style=document.createElement('style');style.id=stylesheet.id;style.textContent=await response.text();stylesheet.replaceWith(style)}
  const current=clone.querySelector('#learning-studio-script');let code=current.src?await (await fetch(current.src)).text():current.textContent;
  code=code.replace(/const media=\{[^\n]+\};/,()=> 'const media='+JSON.stringify(embedded)+';');
  const script=document.createElement('script');script.id='learning-studio-script';script.textContent=code;current.replaceWith(script);
  clone.querySelectorAll('script').forEach(el=>{if(el.hasAttribute('data-lms-bootstrap')||/window\.LEARNING_STUDIO_BOOTSTRAP\s*=/.test(el.textContent))el.remove()});
  const offline=document.createElement('script');offline.setAttribute('data-lms-bootstrap','');offline.textContent='window.LEARNING_STUDIO_OFFLINE=true;';script.before(offline);
  clone.querySelector('#portable-state').textContent=JSON.stringify({...state,files:[],exported:Date.now()}).replace(/</g,'\\u003c');
  for(const selector of ['#student_main','#nav','#modalbody','#dialogtitle','#toast'])clone.querySelector(selector).replaceChildren();
  clone.querySelector('#modal').removeAttribute('open');clone.querySelector('#save-status').hidden=true;
  clone.style.removeProperty('--campus');
  download(new Blob(['<!doctype html>\n',clone.outerHTML],{type:'text/html'}),'VCET Learning Studio - offline.html');toast('Offline workspace prepared for download.');
}
function findResults(q){q=q.trim().toLowerCase();const rows=[];enrolled().forEach(c=>{if(!q||[c.title,c.code,c.mentor].join(' ').toLowerCase().includes(q))rows.push([c.title,c.code+' · Course','course/'+c.id]);if(q)activities(c).forEach((a,i)=>{if(a.toLowerCase().includes(q))rows.push([a,c.code+' · '+activityTypes[i],'lesson/'+c.id+'/'+i])})});return rows.map(([a,b,r])=>'<a class="itemlink" href="#'+r+'"><span class="icbox">'+icon('book')+'</span><span class="listcopy"><strong>'+esc(a)+'</strong><small>'+esc(b)+'</small></span>'+icon('chev')+'</a>').join('')||empty('No courses or activities found.')}
function eventDialog(id){
  const e=events().find(x=>x.id===id);if(!e)return;
  const c=getCourse(e.c);dialog(e.title,'<div class="stack">'+tag(e.kind)+'<p class="inline">'+icon('cal')+human(e.date,{weekday:'long',day:'numeric',month:'long',year:'numeric'})+' · '+e.time+' IST</p><p class="inline">'+icon('pin')+esc(e.where)+'</p><p>'+c.code+' · '+c.title+'</p><div class="actions">'+(e.kind==='Mentoring'?btn('Manage booking','book/'+c.id):e.kind==='Online class'?btn('Enter practice classroom','room/'+c.id,'video','btn primary'):link(e.kind==='Assignment due'?'Open assignment':'Open lab activity','lesson/'+c.id+'/'+e.index,'btn primary'))+btn('Export event','ics/'+id,'down')+'</div></div>');
}
function booking(c){const booked=state.bookings[c.id],slots=[{off:1,time:'15:00'},{off:2,time:'11:00'},{off:3,time:'16:00'}].filter(s=>offset(s.off)>=today());dialog('Mentoring · '+c.mentor,booked?'<div class="stack">'+tag('Reserved in personal study calendar','green')+'<p>'+human(offset(booked.off),{weekday:'long',day:'numeric',month:'long'})+' · '+booked.time+' IST</p>'+btn('Cancel reservation','cancelbook/'+c.id)+'</div>':'<p>Reserve one 20-minute practice slot in your personal study calendar.</p><div class="stack padded">'+(slots.map(s=>btn(human(offset(s.off),{weekday:'short',day:'numeric',month:'short'})+' · '+s.time+' IST','slot/'+c.id+'/'+s.off+'/'+s.time,'cal')).join('')||empty('No slots available for this study period.'))+'</div>')}
function render(focus=false){
  route=location.hash.slice(1).split('/');if(!route[0]||route[0]==='student_main')route=['dashboard'];
  const [p,id,raw]=route,c=getCourse(id),idx=Number(raw);let html;
  if((p==='course'||p==='lesson')&&(!c||!state.enrolled.includes(c.id)||p==='lesson'&&(!Number.isInteger(idx)||idx<0||idx>5))){html=top('Activity unavailable','Choose an enrolled course to continue.',link('My courses','courses','btn'))}
  else if(p==='course')html=course(c);
  else if(p==='lesson'){if(state.last[0]!==c.id||state.last[1]!==idx){state.last=[c.id,idx];save()}html=lesson(c,idx)}
  else if(p==='dashboard')html=dashboard();
  else if(p==='courses')html=catalog();
  else if(p==='calendar')html=calendar();
  else if(p==='grades')html=grades(id||'all');
   else if(p==='tests')html=tests(id);
  else if(p==='discussions')html=discussions();
  else if(p==='offline')html=offline();
  else if(p==='files')html=filesPage();
  else if(p==='explore')html=explore();
  else html=top('Page unavailable','Return to the learning dashboard.',link('Dashboard','dashboard','btn'));
  shell(p);$('#student_main').innerHTML=html+'<footer class="localfoot">'+icon('cloud')+''+(offlineMode?'Offline workspace · Learning record stored on this device':'Learning workspace · Personal study record saved to your student account')+'</footer>';
  if(p==='files')refreshFiles();document.title=($('#student_main h1')?.textContent||'Dashboard')+' · VCET Learning Studio';
  if(focus){$('#student_main').focus({preventScroll:true});window.scrollTo(0,0)}
  if(!offlineMode&&window.parent!==window&&parentNavigationReady)window.parent.postMessage({type:'campus-lms-route',route:route.join('/')},location.origin);
}
function navigate(to){if(location.hash==='#'+to){close();render(true)}else location.hash=to}
window.addEventListener('hashchange',()=>{close();activeAttempt=null;activeTest=null;menu(false);render(true)});
window.addEventListener('online',()=>shell(route[0]));window.addEventListener('offline',()=>shell(route[0]));
window.addEventListener('storage',e=>{if(offlineMode&&e.key===storageKey&&e.newValue){try{state=Object.assign(fresh(),JSON.parse(e.newValue));if(!document.activeElement?.matches('input,textarea,select'))render()}catch{toast('Unable to load a change from another tab.',true)}}});
document.addEventListener('keydown',e=>{if(e.key==='/'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!e.target.matches('input,textarea,select')&&!$('#modal').open){e.preventDefault();act('search')}});
document.addEventListener('click',e=>{const b=e.target.closest('[data-act]');if(b){act(b.dataset.act).catch(()=>toast('The action could not finish. Please try again.',true));return}const a=e.target.closest('a[href^="#"]');if(a){if(a.classList.contains('student_skip')){e.preventDefault();$('#student_main').focus();return}if(a.hash===location.hash){close();menu(false);render(true)}else close()}});
function savedMessage(msg){if(offlineMode){if(save())toast(msg)}else{pendingMessage=msg;save(true)}}
async function act(raw){
  const [a,id,arg,extra]=raw.split('/'),c=getCourse(id);
  switch(a){
    case 'campus-menu':if(!offlineMode&&window.parent!==window)window.parent.postMessage({type:'campus-lms-toggle-navigation'},location.origin);break;
    case 'menu':break;
    case 'retry-save':persist();break;
    case 'reload-state':dirty=false;reportDirty();location.reload();break;
    case 'close':close();break;
    case 'star':{const n=state.stars.indexOf(id);if(n<0)state.stars.push(id);else state.stars.splice(n,1);savedMessage(n<0?'Course starred.':'Star removed.');render();break}
    case 'search':dialog('Search learning studio','<label class="field">Course, code or activity<input type="search" autofocus id="globalsearch" class="formfield" placeholder="Try a course name or lesson…"></label><div id="searchresults" class="padded">'+findResults('')+'</div>');$('#globalsearch').focus();break;
    case 'notices':state.noticed=true;save();shell(route[0]);dialog('Announcements','<span class="meta">Academic office · Semester III</span><h3 class="padded">Semester study guides are ready</h3><p class="padded">The offline library includes a guide for each enrolled course. Use your calendar for lab times and assignment dates.</p><div class="actions padded">'+link('Open offline library','offline','btn')+link('View calendar','calendar','btn')+'</div>');break;
    case 'account':dialog('Learner profile','<div class="inline"><span class="avatar">'+esc(initials())+'</span><div><b>'+esc(state.name)+'</b><div class="meta">'+(offlineMode?'Offline learner':esc(bootstrap.student?.program||'Student learning workspace'))+'</div></div></div>'+(offlineMode?'<form id="profileForm" class="padded"><label class="field">Display name<input class="formfield" name="name" value="'+esc(state.name)+'" minlength="1" maxlength="60" required></label><button class="btn primary padded">Save profile</button></form>':'<p class="secondary padded">Your profile is linked to your student account. Learning progress and private files are saved to your account.</p>'));break;
    case 'plan':dialog('Teaching and learning plan','<p>'+c.intro+'</p><div class="padded">'+c.unit.map((u,x)=>'<div class="line"><h3>Unit 0'+(x+1)+' · '+u+'</h3><ul>'+activities(c).slice(x?2:0,x?6:2).map(a=>'<li>'+a+'</li>').join('')+'</ul></div>').join('')+'</div>'+btn('Download study guide','guide/'+id,'down'));break;
    case 'complete':complete(c,Number(arg));savedMessage('Activity completed. Course progress updated.');render();break;
    case 'guide':guide(c);break;
    case 'portable':await portable();break;
    case 'teststart':{const t=testById(id);if(!t||testStatus(t)!=='available'){toast('This scheduled test is not available.',true);return}activeTest=id;render();$('#scheduledTestForm input')?.focus();break}
     case 'testexit':activeTest=null;savedMessage('Your test answers are saved. You can resume before the closing date.');navigate('tests');break;
     case 'quizstart':activeAttempt=id;render();$('#quizForm input')?.focus();break;
    case 'quizexit':activeAttempt=null;savedMessage('Quiz answers saved as a draft.');render();break;
    case 'savedraft':state.drafts['task-'+id]=$('#assignmentText').value;savedMessage('Assignment draft saved.');break;
    case 'discuss':discussionCourse=id;navigate('discussions');break;
    case 'book':booking(c);break;
    case 'slot':{const clash=Object.entries(state.bookings).some(([other,b])=>other!==id&&b&&b.off===Number(arg)&&b.time===extra);if(clash){toast('You already have a booking at that time.',true);return}state.bookings[id]={off:Number(arg),time:extra};savedMessage('Mentoring study slot added to your learning calendar.');render();booking(c);break}
    case 'cancelbook':delete state.bookings[id];savedMessage('Study reservation cancelled.');close();render();break;
    case 'day':calendarDay=id;render();break;
    case 'today':calendarDay=today();monthStart=calendarDay.slice(0,7)+'-01';render();break;
    case 'month':{const d=dateOf(monthStart);d.setMonth(d.getMonth()+Number(id));monthStart=dayKey(d);calendarDay=monthStart;render();break}
    case 'event':eventDialog(id);break;
    case 'room':dialog('Practice classroom','<div class="stack">'+tag('Recorded demonstration')+'<p>Preview the class on '+esc(c.video.toLowerCase())+'. This rehearsal uses the embedded recording and course discussion.</p><video controls playsinline poster="'+art(c)+'" src="'+media['lesson'+courses.indexOf(c)]+'"></video>'+btn('Open course discussion','discuss/'+id,'chat')+'</div>');break;
    case 'ics':{const e=events().find(x=>x.id===id);const stamp=new Date(e.date+'T'+e.time+':00+05:30'),ical=d=>d.toISOString().replace(/[-:]/g,'').split('.')[0]+'Z',clean=s=>s.replace(/[,;]/g,m=>'\\'+m);download(new Blob([['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//VCET//Learning Studio//EN','BEGIN:VEVENT','UID:'+e.id+'-'+e.date+'@vcet.demo','DTSTAMP:'+ical(new Date()),'DTSTART:'+ical(stamp),'DTEND:'+ical(new Date(+stamp+(e.kind==='Mentoring'?20:45)*60000)),'SUMMARY:'+clean(e.title),'LOCATION:'+clean(e.where),'END:VEVENT','END:VCALENDAR',''].join('\r\n')],{type:'text/calendar'}),e.id+'.ics');break}
    case 'enrol':if(!state.enrolled.includes(id))state.enrolled.push(id);savedMessage('Elective added to My courses.');navigate('course/'+id);break;
    case 'filepick':$('#fileinput').click();break;
    case 'retryfiles':refreshFiles();break;
    case 'getfile':{if(offlineMode){const f=await fileOp('readonly',s=>s.get(id));if(f)download(f.blob,f.name);else toast('The file is no longer in this library.',true)}else{const a=document.createElement('a');a.href='/my/campus/student/lms/files/'+encodeURIComponent(id);a.download='';document.body.append(a);a.click();a.remove()}break}
    case 'dropfile':dialog('Remove private file','<p>This removes the file from your private learning library.</p><div class="actions padded">'+btn('Keep file','close')+btn('Remove file','confirmdrop/'+id)+'</div>');break;
    case 'confirmdrop':{if(offlineMode)await fileOp('readwrite',s=>s.delete(id));else{const response=await fetch('/my/campus/student/lms/files/'+encodeURIComponent(id)+'/delete',{method:'POST',credentials:'same-origin',body:new URLSearchParams({csrf_token:bootstrap.csrfToken})});if(!response.ok)throw new Error('Could not remove file')}close();await refreshFiles();toast('File removed from your library.');break}
  }
}
document.addEventListener('input',e=>{const t=e.target;if(t.id==='globalsearch')$('#searchresults').innerHTML=findResults(t.value);
  if(t.id==='courseQuery'){courseQuery=t.value;$('#courseResults').innerHTML=courseResults()}
  if(t.id==='assignmentText'){state.drafts['task-'+route[1]]=t.value;save()}
  if(t.name==='reply'){state.drafts['post-'+discussionCourse]=t.value;save()}
});
document.addEventListener('change',async e=>{
  const t=e.target;
  if(t.id==='courseFilter'||t.id==='courseSort'){if(t.id==='courseFilter')courseFilter=t.value;else sort=t.value;$('#courseResults').innerHTML=courseResults()}
  if(t.id==='gradeFilter')navigate('grades/'+t.value);
   if(t.id==='testFilter'){testFilter=t.value;render()}
   if(t.closest('#scheduledTestForm')){const exam=testById(route[1]);if(exam){state.drafts['test-'+exam.id]=exam.questions.map((_,i)=>{const val=t.form.elements['q'+i].value;return val===''?null:Number(val)});save()}}
  if(t.id==='board'){discussionCourse=t.value;render()}
  if(t.closest('#quizForm')){const c=getCourse(route[1]),form=t.form;state.drafts['quiz-'+c.id]=c.quiz.map((_,i)=>form.elements['q'+i].value===''?null:Number(form.elements['q'+i].value));save()}
  if(t.id==='fileinput'){try{for(const f of t.files){if(f.size>16*1024*1024){toast('Choose files under 16 MB each.',true);continue}if(offlineMode)await fileOp('readwrite',s=>s.add({id:crypto.randomUUID(),name:f.name,blob:f,ts:Date.now()}));else{const form=new FormData();form.append('file',f);form.append('csrf_token',bootstrap.csrfToken);const response=await fetch('/my/campus/student/lms/files',{method:'POST',credentials:'same-origin',body:form});if(!response.ok){const result=await response.json().catch(()=>({}));throw new Error(result.error||'Upload failed')}}}await refreshFiles()}catch(error){toast(error.message||'File upload failed. Please try again.',true)}t.value=''}
});
document.addEventListener('submit',e=>{
  const form=e.target;e.preventDefault();const data=new FormData(form),c=getCourse(route[1]),ts=Date.now();
  switch(form.id){
    case 'profileForm':{const name=String(data.get('name')).trim();if(!name){toast('Enter a display name.',true);return}state.name=name;savedMessage('Profile updated.');close();render();break}
    case 'notesForm':state.notes[c.id+'-'+route[2]]=String(data.get('note')).trim();savedMessage('Lesson note saved to your offline library.');break;
    case 'practiceForm':{const a=Number(data.get('practice'));state.answers[c.id]=a;if(a===c.practice[2])complete(c,3);savedMessage(a===c.practice[2]?'Checkpoint completed.':'Answer checked. Review the explanation.');render();break}
    case 'scheduledTestForm':{const exam=testById(route[1]);if(!exam||testStatus(exam)!=='available'){toast('This test is not currently available.',true);return}const vals=exam.questions.map((_,i)=>data.get('q'+i));if(vals.some(v=>v===null)){toast('Answer every question before submitting.',true);return}const answers=vals.map(Number),score=answers.reduce((n,a,i)=>n+Number(a===exam.questions[i][2]),0);state.testAttempts||={};if(state.testAttempts[exam.id]){toast('This test has already been submitted.',true);return}state.testAttempts[exam.id]={answers,score,total:exam.questions.length,ts};delete state.drafts['test-'+exam.id];activeTest=null;savedMessage('Test submitted and graded. Your result is now in Grade reports.');navigate('grades/'+exam.course);break}
     case 'quizForm':{const answers=c.quiz.map((_,i)=>Number(data.get('q'+i))),score=answers.reduce((n,a,i)=>n+Number(a===c.quiz[i][2]),0);(state.attempts[c.id]||=[]).push({answers,score,ts});delete state.drafts['quiz-'+c.id];complete(c,4);activeAttempt=null;savedMessage('Quiz submitted. Your result is in Grades.');render();break}
    case 'assignmentForm':{const text=String(data.get('answer')).trim();if(!text){toast('Enter your solution before submitting.',true);return}state.submissions[c.id]={text,ts};delete state.drafts['task-'+c.id];complete(c,5);savedMessage('Submission saved in your learning workspace.');render();break}
    case 'postForm':{const text=String(data.get('reply')).trim();if(!text){toast('Enter a response first.',true);return}state.posts.push({name:state.name,c:discussionCourse,text,ts});delete state.drafts['post-'+discussionCourse];savedMessage('Response added to your learning board.');render();break}
  }
});
document.documentElement.style.setProperty('--campus','url("'+media.campus+'")');
document.querySelectorAll('[data-icon]').forEach(el=>el.outerHTML=icon(el.dataset.icon));

// The reference uses full browser width for typography and layout breakpoints.
// The ERP sidebar lives outside this frame, so retain that reference viewport.
function matchReferenceViewport(){
  if(offlineMode||window.parent===window)return;
  try{
    if(window.parent.location.origin!==location.origin)return;
    const queries=[];
    for(const rule of $('#learning-studio-style').sheet.cssRules){
      if(rule.style?.getPropertyValue('--lms-embedded-boundary'))break;
      if(rule.media&&/\b(?:min|max)-width\s*:/.test(rule.conditionText))queries.push([rule.media,rule.conditionText]);
    }
    const sync=()=>{
      document.documentElement.style.setProperty('--lms-viewport-unit',(window.parent.innerWidth/100)+'px');
      for(const [media,query] of queries)media.mediaText=window.parent.matchMedia(query).matches?'all':'not all';
    };
    sync();window.addEventListener('resize',sync);
  }catch{/* Standalone and cross-origin previews keep native viewport behavior. */}
}
matchReferenceViewport();
if(offlineMode||window.parent===window)document.querySelector('.lms-campus-menu').hidden=true;
render();if(restoreIssue)toast(restoreIssue,true);
window.addEventListener('beforeunload',e=>{if(!offlineMode&&dirty){e.preventDefault();e.returnValue=''}});
window.LEARNING_STUDIO_FLUSH=async()=>{clearTimeout(saveTimer);await persist();while(saveBusy)await new Promise(resolve=>saveWaiters.push(resolve));return offlineMode||!dirty};
window.addEventListener('message',async e=>{
  if(e.source!==window.parent||e.origin!==location.origin||offlineMode)return;
  if(e.data?.type==='campus-lms-navigation-state'){
    const toggle=document.querySelector('.lms-campus-menu');
    toggle.setAttribute('aria-expanded',String(!!e.data.expanded));
    if(typeof e.data.label==='string')toggle.setAttribute('aria-label',e.data.label);
    if(e.data.focus)toggle.focus();
  }
  if(e.data?.type==='campus-lms-navigate'&&typeof e.data.route==='string'&&/^[a-z0-9/-]+$/.test(e.data.route)){parentNavigationReady=true;navigate(e.data.route)}
  if(e.data?.type==='campus-lms-flush'){const saved=await window.LEARNING_STUDIO_FLUSH();window.parent.postMessage({type:'campus-lms-flushed',saved},location.origin)}
});
if(!offlineMode&&window.parent!==window)window.parent.postMessage({type:'campus-lms-ready'},location.origin);


})();
