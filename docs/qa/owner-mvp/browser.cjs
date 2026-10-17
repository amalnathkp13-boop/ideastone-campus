// Real Odoo screens and RPCs on a disposable database; no mock server or production login.
const {chromium} = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const out = process.env.OWNER_QA_OUT;
const base = 'http://127.0.0.1:18069';
if (!out || !process.env.FACULTY_QA_PASSWORD) throw Error('Disposable CI configuration required');
async function rpc(page, model, method, args = [], kwargs = {}) {
    const data = await page.evaluate(async ({model, method, args, kwargs}) => {
        const response = await fetch(`/web/dataset/call_kw/${model}/${method}`, {method:'POST', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({jsonrpc:'2.0', method:'call', params:{model, method, args, kwargs}})});
        return response.json();
    }, {model, method, args, kwargs});
    if (data.error) throw Error(`${model}.${method}: ${data.error.data?.message || data.error.message}`);
    return data.result;
}
async function markup(page) {
    return page.evaluate(() => {
        const body = document.body.cloneNode(true);
        body.querySelectorAll('script,input[name=csrf_token],input[type=password]').forEach(node=>node.remove());
        return body.outerHTML;
    });
}
(async()=>{
    await fs.mkdir(out,{recursive:true});
    const browser = await chromium.launch({headless:true});
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    page.setDefaultTimeout(60000);
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    try {
        await page.goto(base+'/web/login?db=ci');
        await page.locator('input[name=login]').fill('owner.ui.qa');
        await page.locator('input[name=password]').fill(process.env.FACULTY_QA_PASSWORD);
        await page.locator('button[type=submit]').click();
        await page.goto(base+'/web#action=ideastone_erp.action_dashboard');
        await page.getByRole('heading',{name:'Welcome back, College Owner'}).waitFor();
        await page.locator('.campus_owner_stat').first().waitFor();
        const firstMetrics = await rpc(page,'campus.dashboard','get_owner_metrics');
        const studentCard = firstMetrics.stats.find(s=>s.kind==='active_students');
        if(studentCard.value!==3) throw Error('Owner demo does not reconcile with its saved students');
        await page.screenshot({path:path.join(out,'owner-dashboard-1440.png'),fullPage:true});
        await page.locator('.campus_owner_charts').evaluate(element=>element.scrollIntoView({block:'start'}));
        const collectionBars=await page.locator('.campus_owner_charts section').nth(1).locator('.campus_chart_track span').evaluateAll(nodes=>nodes.map(node=>parseFloat(node.style.width)));
        if(collectionBars.length!==2 || Math.abs(collectionBars[0]-100)>0.1 || Math.abs(collectionBars[1]-200/300*100)>0.1) throw Error('Collection and dues chart does not use a common amount scale');
        await page.screenshot({path:path.join(out,'owner-charts-1440.png')});
        if(await page.locator('.campus_dashboard').innerText().then(text=>/Â·|â€”|â†/.test(text))) throw Error('Owner template contains incorrectly decoded UTF-8 punctuation');
        await page.locator('.campus_dashboard').evaluate(element=>element.scrollTop=0);
        const modules = await page.locator('.campus_sidebar nav .campus_nav_link').allTextContents();
        if(modules.length!==12) throw Error('Owner sidebar does not contain the 12 functional MVP modules');
        const overview=await rpc(page,'campus.dashboard','get_overview');
        let checkedViews=0;
        for(const module of overview.faculty_modules) {
            for(const item of module.items.filter(item=>item.action)) {
                const action=await rpc(page,'campus.dashboard','get_owner_action',[item.action]);
                const views=action.views || action.view_mode.split(',').map(mode=>[false,mode]);
                await rpc(page,action.res_model,'get_views',[views],{options:{toolbar:false,load_filters:false},context:action.context || {}});
                checkedViews++;
            }
        }
        for(const kind of ['admissions','students','attendance','collection','dues','results','faculty']) {
            const report=await rpc(page,'campus.mvp.report','create',[{kind}]);
            await rpc(page,'campus.mvp.report','action_csv',[[report]]);
        }
        await page.locator('.campus_sidebar').getByRole('button',{name:'Academics',exact:true}).click();
        await page.getByRole('heading',{name:'Academics',exact:true,level:1}).waitFor();
        await page.screenshot({path:path.join(out,'owner-academics-1440.png')});
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Subjects & curriculum',exact:true}).click();
        const create = page.locator('.o_list_button_add:visible');
        await create.waitFor();
        const box = await create.boundingBox();
        const nav = await page.locator('.campus_faculty_subnav').boundingBox();
        if(box.y<nav.y+nav.height) throw Error('Owner submodule bar obscures native form controls');
        await create.click();
        await page.locator('.o_field_widget[name=name] input').fill('QA browser persisted subject');
        await page.locator('.o_field_widget[name=code] input').fill('OWNER-BROWSER');
        const response = page.waitForResponse(r=>r.url().includes('/op.subject/web_save'));
        await page.locator('.o_form_button_save:visible').click();
        const saved = await (await response).json();
        if(saved.error) throw Error(saved.error.data?.message || saved.error.message);
        const subjects=await rpc(page,'op.subject','search_read',[[['code','=','OWNER-BROWSER']]],{fields:['name','company_id']});
        if(subjects.length!==1 || subjects[0].name!=='QA browser persisted subject') throw Error('Owner subject form did not persist');
        await page.reload();
        await page.locator('.o_form_view:visible').waitFor();
        if(await page.locator('.g2_review_container').count()) throw Error('Upstream promotional dialog blocks the Owner workspace');
        await page.screenshot({path:path.join(out,'owner-subject-1440.png')});
        const apps=await rpc(page,'op.admission','search_read',[[['name','=','QA Concurrent Applicant']]],{fields:['campus_stage']});
        await Promise.all([rpc(page,'op.admission','enroll_student',[[apps[0].id]]),rpc(page,'op.admission','enroll_student',[[apps[0].id]])]);
        const converted=await rpc(page,'op.admission','read',[[apps[0].id]],{fields:['student_id','campus_enrolment_id']});
        const enrolments=await rpc(page,'op.student.course','search_count',[[['student_id','=',converted[0].student_id[0]]]]);
        if(enrolments!==1) throw Error('Concurrent conversion duplicated an enrolment');
        const invoices=await rpc(page,'account.move','search_read',[[['campus_student_id','!=',false],['state','=','posted']]],{fields:['amount_residual']});
        const journals=await rpc(page,'account.journal','search_read',[[['code','=','QAC']]],{fields:['name']});
        const request=await rpc(page,'campus.fee.payment.wizard','create',[{invoice_id:invoices[0].id,amount:100,journal_id:journals[0].id}]);
        await Promise.all([rpc(page,'campus.fee.payment.wizard','action_pay',[[request]]),rpc(page,'campus.fee.payment.wizard','action_pay',[[request]])]);
        const balance=await rpc(page,'account.move','read',[[invoices[0].id]],{fields:['amount_residual']});
        const receipts=await rpc(page,'account.payment','search_read',[[['campus_invoice_id','=',invoices[0].id]]],{fields:['campus_receipt_number','amount']});
        if(balance[0].amount_residual!==100 || receipts.length!==2) throw Error('Concurrent payment posting duplicated collection or failed reconciliation');
        const pdf=await page.request.get(`${base}/report/pdf/ideastone_erp.mvp_receipt_document/${receipts[0].id}`);
        const bytes=await pdf.body();
        if(!pdf.ok() || bytes.subarray(0,5).toString()!=='%PDF-') throw Error('College receipt PDF failed');
        await fs.writeFile(path.join(out,'owner-receipt.pdf'),bytes);
        await page.locator('.campus_sidebar').getByRole('button',{name:'Dashboard',exact:true}).click();
        await page.locator('.campus_owner_stat').first().waitFor();
        const metrics=await rpc(page,'campus.dashboard','get_owner_metrics');
        if(metrics.stats.find(s=>s.kind==='active_students').value!==4 || !metrics.stats.find(s=>s.kind==='collection').value.includes('400.00')) throw Error('Dashboard did not reflect the committed lifecycle changes');
        await page.setViewportSize({width:1024,height:768});
        await page.screenshot({path:path.join(out,'owner-desktop-1024.png')});
        await page.setViewportSize({width:390,height:844});
        await page.locator('.campus_mobile_toggle').click();
        await page.locator('.campus_sidebar.is-open').waitFor();
        await page.keyboard.press('Escape');
        await page.locator('.campus_sidebar').waitFor({state:'hidden'});
        if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw Error('Owner dashboard overflows the mobile viewport');
        await page.screenshot({path:path.join(out,'owner-mobile-390.png')});
        if(errors.length) throw Error(errors.join('\n'));
        await fs.writeFile(path.join(out,'verification.json'),JSON.stringify({passed:true,checkedViews,checks:['12 owner modules','all permitted submodule views','7 real CSV exports','faculty shell reused','live KPI reconciliation','real subject form save and reload','concurrent admission conversion','concurrent payment posting','receipt PDF','1024 desktop','390 mobile drawer and overflow','browser console'],metrics,errors},null,2));
    } catch(error) {
        await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});
        await fs.writeFile(path.join(out,'failure-dom.html'),await markup(page));
        await fs.writeFile(path.join(out,'failure.txt'),`${error.stack}\n${page.url()}\n${await page.locator('body').innerText().catch(()=>'')}`);
        throw error;
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
