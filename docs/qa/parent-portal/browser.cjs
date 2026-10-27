// Real Odoo and saved synthetic records. No route mocks, storage mocks or production credentials.
const {chromium}=require('playwright');
const {assertCampusTheme} = require('../campus-theme.cjs');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
const base=process.env.PARENT_QA_BASE || 'http://127.0.0.1:18069';
const db=process.env.PARENT_QA_DB || 'ci';
const out=process.env.PARENT_QA_OUT;
if(!out || !process.env.PARENT_QA_PASSWORD) throw Error('Disposable Parent QA configuration required');
async function rpc(page,model,method,args=[],kwargs={}) {
    const data=await page.evaluate(async({model,method,args,kwargs})=>(await fetch(`/web/dataset/call_kw/${model}/${method}`,{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',method:'call',params:{model,method,args,kwargs}})
    })).json(),{model,method,args,kwargs});
    if(data.error) throw Error(data.error.data?.message || data.error.message);
    return data.result;
}
async function login(page,user) {
    await page.goto(base+'/web/login?db='+db,{waitUntil:'domcontentloaded'});
    await page.locator('input[name=login]').fill(user);
    await page.locator('input[name=password]').fill(process.env.PARENT_QA_PASSWORD);
    const response=page.waitForResponse(r=>r.url().includes('/web/login') && r.request().method()==='POST');
    await page.locator('button[type=submit]').click();
    assert([302,303].includes((await response).status()));
    await page.waitForURL(url=>!url.pathname.endsWith('/web/login'));
}
async function clickAndWaitForWorkspace(page,control) {
    const previous=await page.locator('#campus_student_workspace').elementHandle();
    try {
        await control.click();
        await page.waitForFunction(element=>!element.isConnected,previous);
    } finally {await previous.dispose();}
}
async function assertParentTheme(page) {
    const theme=await page.evaluate(()=>{
        const style=selector=>getComputedStyle(document.querySelector(selector));
        const primary=document.querySelector('.parent_workspace .btn-primary');
        return {sidebar:style('.student_sidebar').backgroundImage,
            selected:style('.student_nav_link.active').backgroundColor,
            selectedText:style('.student_nav_link.active').color,
            primary:primary?getComputedStyle(primary).backgroundColor:null};
    });
    assert.match(theme.sidebar,/rgb\(9, 47, 80\)/,'Parent sidebar must retain the shared navy surface');
    assert.equal(theme.selected,'rgb(22, 104, 223)');
    assert.equal(theme.selectedText,'rgb(255, 255, 255)');
    if(theme.primary) assert(['rgb(23, 105, 210)','rgb(17, 83, 168)'].includes(theme.primary),'Parent primary controls must use the shared blue or its hover shade');
}
async function visit(page,section) {
    // Revisiting the same URL must wait for the new form, not the old heading/URL.
    await clickAndWaitForWorkspace(page,page.locator(`.student_sidebar a[href*="/parent/${section}"]`));
    await page.waitForURL(new RegExp('/parent/'+section));
    await page.locator('#student_main h1').waitFor();
    assert.equal(await page.locator('.student_network_error:visible').count(),0);
    await assertParentTheme(page);
}
async function submit(page,button) {
    await clickAndWaitForWorkspace(page,button);
    const errors=page.locator('.parent_workspace .alert-danger:visible');
    assert.equal(await errors.count(),0,await errors.allTextContents().then(messages=>messages.join('\n')));
    await page.getByText('Your changes have been saved.',{exact:true}).waitFor();
}
(async()=>{
    await fs.mkdir(out,{recursive:true});
    const browser=await chromium.launch({headless:true,...(process.env.PARENT_QA_CHROME?{channel:'chrome'}:{})});
    const context=await browser.newContext({viewport:{width:1440,height:1000},timezoneId:'Asia/Kolkata'});
    const page=await context.newPage(); page.setDefaultTimeout(60000);
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    const requestTitle='QA parent absence intimation '+Date.now();
    const cancelTitle='QA enquiry to cancel '+Date.now();
    try {
        await login(page,'parent.ui.qa');
        await page.locator('.parent_workspace').waitFor();
        const initial=await rpc(page,'campus.parent.portal','snapshot');
        assert.equal(initial.children.length,2);
        assert.equal(initial.pending_work,1);
        assert(!('phone' in initial.student));
        assert(!('assignments' in initial));
        assert(!JSON.stringify(initial).includes('PRIVATE STUDENT DRAFT'));
        assert(!JSON.stringify(initial).includes('PRIVATE FACULTY DRAFT'));
        assert(!initial.navigation.some(row=>row[0]==='transport'));
        assert(!initial.notices.some(row=>row.name==='PRIVATE STAFF ONLY'));
        for(const notice of initial.notices) await rpc(page,'campus.parent.portal','act',['notice',initial.student_id,{notice_id:notice.id,read:false}]);
        await page.reload();
        await assertCampusTheme(page);
        await page.screenshot({path:path.join(out,'parent-overview-1440.png'),fullPage:true});
        await page.locator('.student_quick').scrollIntoViewIfNeeded();
        await assertCampusTheme(page);
        await page.screenshot({path:path.join(out,'parent-overview-details-1440.png'),fullPage:true});
        await page.evaluate(()=>document.getElementById('wrapwrap').scrollTo({top:0}));
        const first=initial.student_id, second=initial.children.find(c=>c.id!==first).id;
        let destinations=0;
        for(const child of [first,second]) {
            if(child!==first) {
                await page.locator('#parent_child').selectOption(String(child));
                await clickAndWaitForWorkspace(page,page.getByRole('button',{name:'Switch child',exact:true}));
            }
            for(const [section] of initial.navigation) {
                await visit(page,section);
                assert.equal(new URL(page.url()).searchParams.get('child'),String(child));
                assert.equal(await page.locator('#parent_child').inputValue(),String(child));
                destinations++;
            }
            const data=await rpc(page,'campus.parent.portal','snapshot',[child]);
            assert.equal(data.student_id,child);
            assert.equal(data.pending_work,child===first?1:0);
        }
        await page.goto(base+'/my/campus/parent/requests?child='+first,{waitUntil:'domcontentloaded'});
        await page.locator('.student_request_type').selectOption(String(initial.request_types.find(t=>t.name==='Absence / leave intimation').id));
        await page.locator('#student_request_title').fill(requestTitle);
        await page.locator('#student_request_description').fill('Please review this synthetic absence intimation.');
        await page.locator('#parent_absence_from').fill(initial.today_iso);
        await page.locator('#parent_absence_to').fill(initial.today_iso);
        await submit(page,page.getByRole('button',{name:'Submit request',exact:true}));
        await page.reload();
        const created=await rpc(page,'campus.parent.portal','snapshot',[first]);
        const request=created.requests.find(r=>r.name===requestTitle);
        assert(request?.reference);
        assert.deepEqual(created.attendance,initial.attendance);
        await assertCampusTheme(page);
        await page.screenshot({path:path.join(out,'parent-requests-1440.png'),fullPage:true});
        await visit(page,'notices');
        const unread=await rpc(page,'campus.parent.portal','snapshot',[first]);
        await submit(page,page.getByRole('button',{name:'Mark read',exact:true}).first());
        assert.equal((await rpc(page,'campus.parent.portal','snapshot',[first])).unread,unread.unread-1);
        const staff=await browser.newPage(); staff.setDefaultTimeout(60000); await login(staff,'owner.ui.qa');
        await staff.goto(base+'/web#action=ideastone_erp.action_dashboard',{waitUntil:'domcontentloaded'});
        await staff.locator('.campus_owner_stat').first().waitFor();
        const studentWork=await rpc(staff,'op.assignment.sub.line','search_read',[[['student_id','=',first],['assignment_id','=',initial.homework[0].id]]],{fields:['id']});
        assert.equal(studentWork.length,1);
        assert.equal((await page.request.get(base+`/my/campus/parent/download/assignment/${studentWork[0].id}?child=${first}`)).status(),404);
        await rpc(staff,'campus.service.request','write',[[request.id],{portal_reply:'Please confirm the preferred contact time.'}]);
        await rpc(staff,'campus.service.request','action_portal_information',[[request.id]]);
        await visit(page,'requests');
        const caseRow=page.locator('.student_case').filter({has:page.getByText(requestTitle,{exact:true})});
        await caseRow.locator('summary').click();
        await caseRow.locator('textarea[name=reply]').fill('Please call after 16:00.');
        await submit(page,caseRow.getByRole('button',{name:'Send information',exact:true}));
        assert.equal((await rpc(page,'campus.parent.portal','snapshot',[first])).requests.find(r=>r.id===request.id).state,'submitted');
        await rpc(staff,'campus.service.request','write',[[request.id],{portal_reply:'The college has received your intimation. Official attendance is recorded independently.'}]);
        await rpc(staff,'campus.service.request','action_approve',[[request.id]]);
        await rpc(staff,'campus.service.request','action_done',[[request.id]]);
        assert.equal((await rpc(page,'campus.parent.portal','snapshot',[first])).requests.find(r=>r.id===request.id).state,'done');
        await staff.close();
        await visit(page,'requests');
        await page.locator('.student_request_type').selectOption(String(initial.request_types.find(t=>t.name==='School enquiry / profile correction').id));
        await page.locator('#student_request_title').fill(cancelTitle);
        await page.locator('#student_request_description').fill('Synthetic request to verify parent cancellation.');
        await submit(page,page.getByRole('button',{name:'Submit request',exact:true}));
        const cancelCase=page.locator('.student_case').filter({has:page.getByText(cancelTitle,{exact:true})});
        await cancelCase.locator('summary').click();
        await submit(page,cancelCase.getByRole('button',{name:'Cancel request',exact:true}));
        assert.equal((await rpc(page,'campus.parent.portal','snapshot',[first])).requests.find(r=>r.name===cancelTitle).state,'cancelled');
        await visit(page,'fees');
        const receipt=page.getByRole('link',{name:'Download receipt',exact:true}).first();
        const pdf=await page.request.get(base+await receipt.getAttribute('href'));
        const bytes=await pdf.body(); assert(pdf.ok() && bytes.subarray(0,5).toString()==='%PDF-');
        await fs.writeFile(path.join(out,'parent-receipt.pdf'),bytes);
        const tampered=new URL(base+await receipt.getAttribute('href')); tampered.searchParams.set('child',String(second));
        assert.equal((await page.request.get(tampered.href)).status(),404);
        const receiptUrl=await receipt.getAttribute('href');
        assert.equal((await page.request.get(base+receiptUrl.split('?')[0])).status(),404);
        await visit(page,'documents');
        const doc=page.getByRole('link',{name:'Download college-letter.txt',exact:true});
        assert.equal((await page.request.get(base+await doc.getAttribute('href'))).status(),200);
        const other=await browser.newPage(); await login(other,'parent.other.qa');
        await other.locator('.parent_workspace').waitFor();
        assert.equal(await other.locator('#parent_child').count(),0);
        const foreign=(await rpc(other,'campus.parent.portal','snapshot')).student_id;
        await other.close();
        await assert.rejects(()=>rpc(page,'campus.parent.portal','snapshot',[foreign]));
        await assert.rejects(()=>rpc(page,'campus.parent.portal','act',['profile',first,{first_name:'Forged'}]));
        await assert.rejects(()=>rpc(page,'campus.dashboard','get_owner_metrics'));
        assert.equal((await page.request.get(base+'/my/campus/parent/dashboard?child='+foreign)).status(),403);
        assert.equal((await page.request.post(base+'/my/campus/parent/action',{form:{child:String(first),operation:'request'}})).status(),400);
        await page.goto(base+'/my/campus/parent/dashboard?child='+first,{waitUntil:'domcontentloaded'});
        for(const width of [768,390]) {
            await page.setViewportSize({width,height:900});
            assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Parent document overflows viewport');
            await page.locator('.student_menu').click();
            await page.locator('.student_sidebar.is-open').waitFor();
            await page.keyboard.press('Escape');
            await page.locator('.student_sidebar').waitFor({state:'hidden'});
            await assertCampusTheme(page);
            await page.screenshot({path:path.join(out,`parent-overview-${width}.png`),fullPage:true});
        }
        assert.deepEqual(errors,[]);
        const headers=(await page.request.get(base+'/my/campus/parent/dashboard?child='+first)).headers();
        assert.match(headers['cache-control'],/no-store/);
        await page.goto(base+'/web/session/logout?redirect=/web/login',{waitUntil:'domcontentloaded'});
        const after=await page.request.get(base+receiptUrl,{maxRedirects:0});
        assert([302,303].includes(after.status()));
        await fs.writeFile(path.join(out,'verification.json'),JSON.stringify({destinations,children:2,requestWorkflow:true,receipt:true,document:true,IDOR:true,CSRF:true,logout:true,widths:[1440,768,390],pageErrors:errors},null,2));
        console.log('Parent browser checks passed: '+destinations+' destinations, requests, receipts, child isolation and responsive views.');
    } catch(error) {
        await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});
        await fs.writeFile(path.join(out,'failure.txt'),error.stack+'\nURL: '+page.url()+'\n'+await page.locator('body').innerText().catch(()=>''));
        throw error;
    } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1);});
