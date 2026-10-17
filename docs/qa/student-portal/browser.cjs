// Real authenticated Odoo pages on the disposable CI database; no mocked records.
const {chromium} = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const base = 'http://127.0.0.1:18069';
const out = process.env.STUDENT_QA_OUT;
if (!out || !process.env.STUDENT_QA_PASSWORD) throw Error('Disposable CI configuration required');
async function rpc(page, model, method, args=[], kwargs={}) {
    const data = await page.evaluate(async ({model,method,args,kwargs}) => (await fetch(`/web/dataset/call_kw/${model}/${method}`, {
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',method:'call',params:{model,method,args,kwargs}})
    })).json(),{model,method,args,kwargs});
    if(data.error) throw Error(data.error.data?.message || data.error.message);
    return data.result;
}
async function login(page, name) {
    await page.goto(base+'/web/login?db=ci');
    await page.locator('input[name=login]').fill(name);
    await page.locator('input[name=password]').fill(process.env.STUDENT_QA_PASSWORD);
    await page.locator('button[type=submit]').click();
}
async function visit(page, section) {
    await page.locator(`.student_sidebar a[href*="/student/${section}"]`).click();
    await page.waitForURL(new RegExp(`/student/${section}`));
    await page.locator('#student_main h1').waitFor();
    assert.equal(await page.locator('.student_network_error:visible').count(),0);
}
async function snapshot(page) {return rpc(page,'campus.student.portal','snapshot');}
async function save(page, control) {
    const previous=await page.locator('#campus_student_workspace').elementHandle();
    try {
        await control.click();
        await page.waitForFunction(element=>!element.isConnected,previous);
        await page.getByText('Your changes have been saved.',{exact:true}).waitFor();
    } finally {await previous.dispose();}
}
(async()=>{
    await fs.mkdir(out,{recursive:true});
    const browser=await chromium.launch({headless:true});
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    const page=await context.newPage();
    page.setDefaultTimeout(60000);
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    try {
        await login(page,'student.ui.qa');
        await page.waitForURL(/\/my\/campus/);
        if(await page.getByText('500: Internal Server Error',{exact:true}).count()) throw Error('Student landing returned a server error');
        await page.getByRole('heading',{name:'Student Dashboard',exact:true}).waitFor();
        const initial=await snapshot(page);
        assert.equal(initial.fees.assessed,500); assert.equal(initial.fees.paid,400); assert.equal(initial.fees.due,100);
        assert.equal(initial.attendance.rate,100); assert.equal(initial.results.length,1); assert.equal(initial.results[0].marks,75);
        assert.equal(await page.locator('.student_stat').count(),5);
        assert.equal(await page.locator('.campus_owner_actions,.o_menu_systray,.campus_owner_stat').count(),0);
        assert(!await page.locator('#student_main').innerText().then(s=>s.includes('PRIVATE STAFF ONLY')));
        const cache=await page.request.get(base+'/my/campus/student/dashboard');
        assert.match(cache.headers()['cache-control'],/no-store/);
        await page.screenshot({path:path.join(out,'student-dashboard-1440.png'),fullPage:true});
        await page.locator('.student_grid section').first().evaluate(element=>element.scrollIntoView({block:'start'}));
        await page.screenshot({path:path.join(out,'student-dashboard-details-1440.png')});
        await page.evaluate(()=>{document.getElementById('wrapwrap')?.scrollTo({top:0});window.scrollTo(0,0);});
        const routes=initial.navigation.map(item=>item[0]);
        for(const route of routes) await visit(page,route);
        await visit(page,'timetable');
        await page.getByRole('button',{name:'Today',exact:true}).click();
        assert.equal(await page.locator('.student_timetable_row:visible').count(),initial.schedule.filter(row=>row.day===initial.today_iso).length);
        await page.getByRole('button',{name:'Selected period',exact:true}).click();
        assert.equal(await page.locator('.student_timetable_row:visible').count(),initial.schedule.length);
        await visit(page,'profile');
        await page.locator('.student_subnav').getByRole('link',{name:'Documents',exact:true}).click();
        assert(await page.locator('#student_documents').evaluate(element=>element.getBoundingClientRect().top>=128),'Sticky header obscures the document anchor');
        await page.locator('#profile_phone').fill('+91 90000 00123');
        await page.locator('#profile_city').fill('Coimbatore');
        await save(page,page.getByRole('button',{name:'Save contact details'}));
        await page.reload();
        assert.equal(await page.locator('#profile_city').inputValue(),'Coimbatore');
        assert.equal((await snapshot(page)).student.phone,'+91 90000 00123');
        await assert.rejects(()=>rpc(page,'campus.student.portal','act',['profile',{first_name:'Forged'}]));
        await assert.rejects(()=>rpc(page,'op.student','write',[[initial.student_id],{first_name:'Forged'}]));
        await assert.rejects(()=>rpc(page,'campus.dashboard','get_owner_metrics'));
        await page.screenshot({path:path.join(out,'student-profile-1440.png'),fullPage:true});
        await visit(page,'notices');
        assert(await page.locator('#student_main h1').evaluate(element=>element.getBoundingClientRect().top>=120),'Navigation did not reset the native portal scroll container');
        await save(page,page.getByRole('button',{name:'Mark read',exact:true}).first());
        assert.equal((await snapshot(page)).unread,initial.unread-1);
        await visit(page,'requests');
        const kind=initial.request_types.find(item=>item.code==='bonafide') || initial.request_types[0];
        await page.locator('#student_request_type').selectOption(String(kind.id));
        await page.locator('#student_request_title').fill('Bonafide for scholarship verification');
        await page.locator('#student_request_description').fill('Please issue an official bonafide certificate for the scholarship office.');
        await page.locator('#student_request_file').setInputFiles({name:'support.txt',mimeType:'text/plain',buffer:Buffer.from('Synthetic student supporting document.')});
        await save(page,page.getByRole('button',{name:'Submit request',exact:true}));
        let data=await snapshot(page);
        assert.equal(data.requests.length,1);
        const record=data.requests[0];
        const retry={type_id:kind.id,key:data.submission_key,title:'Retry request',description:'Retry after a network interruption.'};
        const duplicate=await Promise.all([rpc(page,'campus.student.portal','act',['request',retry]),rpc(page,'campus.student.portal','act',['request',retry])]);
        assert(duplicate.every(item=>item.reference===record.reference));
        assert.equal((await snapshot(page)).requests.length,1);
        const staff=await browser.newPage();
        await login(staff,'owner.ui.qa');
        await staff.goto(base+'/web');
        await rpc(staff,'campus.service.request','write',[[record.id],{portal_reply:'Confirm the institution receiving the certificate.'}]);
        await rpc(staff,'campus.service.request','action_portal_information',[[record.id]]);
        await page.reload();
        await page.locator('.student_case summary').first().click();
        await page.locator('textarea[name=reply]').fill('Scholarship office, QA Demo College');
        await save(page,page.getByRole('button',{name:'Send information',exact:true}));
        assert.equal((await snapshot(page)).requests.find(item=>item.id===record.id).state,'submitted');
        await rpc(staff,'campus.service.request','action_approve',[[record.id]]);
        await rpc(staff,'campus.service.request','write',[[record.id],{portal_reply:'Your bonafide certificate is ready.',portal_result_file:Buffer.from('Official synthetic certificate for QA Arun.').toString('base64'),portal_result_filename:'bonafide.txt'}]);
        await rpc(staff,'campus.service.request','action_portal_ready',[[record.id]]);
        await page.reload();
        await page.locator('.student_case summary').first().click();
        const final=await page.request.get(base+`/my/campus/student/download/request/${record.id}`);
        assert.equal(final.status(),200); assert.match(await final.text(),/QA Arun/);
        const support=initial.request_types.find(item=>item.code==='support');
        const attempt={type_id:support.id,key:(await snapshot(page)).submission_key,title:'Student support QA',description:'Concurrent first submission from two tabs.'};
        const simultaneous=await Promise.all([
            rpc(page,'campus.student.portal','act',['request',attempt]),
            rpc(page,'campus.student.portal','act',['request',{...attempt,key:require('node:crypto').randomUUID().replaceAll('-','')}])
        ]);
        assert.equal(simultaneous[0].reference,simultaneous[1].reference);
        assert.equal((await snapshot(page)).requests.filter(item=>item.type_id===support.id).length,1);
        await page.screenshot({path:path.join(out,'student-requests-1440.png'),fullPage:true});
        await visit(page,'fees');
        const receipts=(await snapshot(page)).fees.payments;
        assert.equal(receipts.length,2);
        const pdf=await page.request.get(base+receipts[0].url);
        assert.equal(pdf.status(),200); assert.equal((await pdf.body()).subarray(0,5).toString(),'%PDF-');
        await fs.writeFile(path.join(out,'student-receipt.pdf'),await pdf.body());
        await page.screenshot({path:path.join(out,'student-fees-1440.png'),fullPage:true});
        const other=await browser.newPage();
        await login(other,'student.other.qa');
        await other.goto(base+'/my/campus');
        const foreign=await snapshot(other);
        assert.notEqual(foreign.student_id,initial.student_id); assert.equal(foreign.fees.recorded,false);
        await assert.rejects(()=>rpc(page,'campus.student.portal','snapshot',[foreign.placement.id]));
        for(const url of [receipts[0].url,`/my/campus/student/download/request/${record.id}`]) {
            assert.equal((await other.request.get(base+url)).status(),404);
        }
        await assert.rejects(()=>rpc(other,'campus.student.portal','act',['cancel',{request_id:record.id}]));
        const noCsrf=await page.request.post(base+'/my/campus/student/action',{form:{operation:'profile',city:'Forged'}});
        assert.equal(noCsrf.status(),400);
        const oldUrl=page.url();
        await page.route('**/my/campus/student/attendance*',route=>route.abort());
        await page.locator('.student_sidebar a[href*="/student/attendance"]').click();
        await page.locator('.student_network_error:visible').waitFor();
        assert.equal(page.url(),oldUrl); assert(await page.locator('#student_fee_ledger').isVisible());
        await page.unroute('**/my/campus/student/attendance*');
        await page.getByRole('button',{name:'Retry',exact:true}).click();
        await page.waitForURL(/\/student\/attendance/);
        await page.screenshot({path:path.join(out,'student-attendance-1440.png'),fullPage:true});
        for(const width of [768,390]) {
            await page.setViewportSize({width,height:900});
            await page.getByRole('button',{name:'Toggle student navigation'}).click();
            await page.keyboard.press('Escape');
            assert.equal(await page.getByRole('button',{name:'Toggle student navigation'}).getAttribute('aria-expanded'),'false');
            for(const route of ['dashboard','fees','requests']) {
                await page.goto(base+'/my/campus/student/'+route);
                assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Overflow on ${route} at ${width}`);
            }
            await page.goto(base+'/my/campus/student/dashboard');
            await page.screenshot({path:path.join(out,`student-dashboard-${width}.png`),fullPage:true});
            if(width===390) {
                await page.locator('.student_stats').first().evaluate(element=>element.scrollIntoView({block:'start'}));
                await page.screenshot({path:path.join(out,'student-summary-390.png')});
            }
        }
        await page.goto(base+'/web/session/logout?redirect=/web/login');
        await page.goBack();
        await page.waitForURL(/\/web\/login/);
        assert.equal(await page.locator('#student_main').count(),0);
        assert.deepEqual(errors,[]);
        await fs.writeFile(path.join(out,'verification.json'),JSON.stringify({source:process.env.GITHUB_SHA,run:process.env.GITHUB_RUN_ID,
            routes,profileReload:true,noticePersistence:true,requestConcurrentRetry:true,staffRequestWorkflow:true,
            receiptPdf:true,studentIDOR:true,csrf:true,networkRetry:true,logoutBack:true,responsive:[1440,768,390],
            ledger:{assessed:initial.fees.assessed,paid:initial.fees.paid,due:initial.fees.due},attendance:initial.attendance.rate,consoleErrors:errors},null,2));
        console.log('Student Portal: all scoped routes, saved workflows, PDF, IDOR, CSRF, retry, logout and responsive checks passed.');
    } catch(error) {
        await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});
        await fs.writeFile(path.join(out,'failure.html'),await page.evaluate(()=>{
            const body=document.body.cloneNode(true);
            body.querySelectorAll('script,input[name=csrf_token],input[type=password]').forEach(node=>node.remove());
            return body.outerHTML;
        })).catch(()=>{});
        await fs.writeFile(path.join(out,'failure.txt'),String(error.stack));
        throw error;
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
