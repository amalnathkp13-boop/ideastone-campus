// Real Odoo collections, student submission, faculty review and parent visibility.
const {chromium}=require('playwright');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
const base=process.env.MVP_QA_BASE || 'http://127.0.0.1:18069';
const db=process.env.MVP_QA_DB || 'ci';
const out=process.env.MVP_QA_OUT;
if(!out || !process.env.MVP_QA_PASSWORD) throw Error('Disposable MVP QA configuration required');
async function rpc(page,model,method,args=[],kwargs={}) {
    const result=await page.evaluate(async({model,method,args,kwargs})=>(await fetch(`/web/dataset/call_kw/${model}/${method}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',method:'call',params:{model,method,args,kwargs}})})).json(),{model,method,args,kwargs});
    if(result.error) throw Error(result.error.data?.message || result.error.message);
    return result.result;
}
async function login(browser,login) {
    const page=await browser.newPage({viewport:{width:1440,height:1000},timezoneId:'Asia/Kolkata'});
    page.setDefaultTimeout(60000);
    await page.goto(base+'/web/login?db='+db,{waitUntil:'domcontentloaded'});
    await page.locator('input[name=login]').fill(login);
    await page.locator('input[name=password]').fill(process.env.MVP_QA_PASSWORD);
    await Promise.all([page.waitForURL(url=>!url.pathname.endsWith('/web/login')),page.locator('button[type=submit]').click()]);
    return page;
}
async function savePortal(page,button) {
    const previous=await page.locator('#campus_student_workspace').elementHandle();
    try {await button.click(); await page.waitForFunction(node=>!node.isConnected,previous);} finally {await previous.dispose();}
    assert.deepEqual(await page.locator('.student_workspace .alert-danger:visible').allTextContents(),[]);
    await page.getByText('Your changes have been saved.',{exact:true}).waitFor();
}
(async()=>{
    await fs.mkdir(out,{recursive:true});
    const browser=await chromium.launch({headless:true,...(process.env.MVP_QA_CHROME?{channel:'chrome'}:{})});
    const errors=[]; browser.on('page',page=>page.on('pageerror',error=>errors.push(error.message)));
    let current;
    try {
        const owner=current=await login(browser,'owner.ui.qa');
        const scenario=JSON.parse(await rpc(owner,'ir.config_parameter','get_param',['ideastone.mvp_qa_scenario']));
        const starting=await rpc(owner,'account.move','read',[scenario.invoices,['amount_residual']]);
        const openingBalance=starting.reduce((sum,row)=>sum+row.amount_residual,0);
        assert(starting.every(row=>row.amount_residual>=100),'Use a fresh disposable scenario when its test invoices are exhausted');
        const assignmentName='MVP secure programming assignment '+Date.now();
        scenario.task=await rpc(owner,'op.assignment','copy',[[scenario.task],{name:assignmentName,state:'draft'}]);
        await rpc(owner,'op.assignment','act_publish',[[scenario.task]]);
        const reference='QA-REPLAY-'+Date.now();
        const requests=[];
        for(const invoice of scenario.invoices) requests.push(await rpc(owner,'campus.fee.payment.wizard','create',[{invoice_id:invoice,amount:100,journal_id:scenario.bank,method:'upi',reference}]));
        const results=await Promise.allSettled(requests.map(id=>rpc(owner,'campus.fee.payment.wizard','action_pay',[[id]])));
        assert.equal(results.filter(r=>r.status==='fulfilled').length,1,'The same transaction was collected more than once');
        assert.match(results.find(r=>r.status==='rejected').reason.message,/transaction reference.*already/i);
        const invoices=await rpc(owner,'account.move','read',[scenario.invoices,['amount_residual']]);
        assert.equal(invoices.reduce((sum,row)=>sum+row.amount_residual,0),openingBalance-100);
        const receipts=await rpc(owner,'account.payment','search_read',[[['campus_reference','=',reference]],['campus_receipt_number','amount']]);
        assert.equal(receipts.length,1); assert.equal(receipts[0].amount,100);
        await owner.goto(base+'/web#action=ideastone_erp.action_dashboard');
        await owner.locator('.campus_sidebar').getByRole('button',{name:'Fees & Payments',exact:true}).click();
        await owner.locator('.campus_faculty_subnav').getByRole('button',{name:'Overdue follow-up',exact:true}).click();
        await owner.locator('.o_list_view').waitFor();
        await owner.screenshot({path:path.join(out,'fee-followup-1440.png')});
        await owner.locator('.campus_sidebar').getByRole('button',{name:'Learning & LMS',exact:true}).click();
        await owner.getByRole('heading',{name:'Learning & LMS',exact:true,level:1}).waitFor();
        await owner.screenshot({path:path.join(out,'learning-navigation-1440.png')});
        const overview=await rpc(owner,'campus.dashboard','get_overview');
        const learning=overview.faculty_modules.find(module=>module.key==='learning');
        assert.equal(learning.items.length,3);
        for(const item of learning.items) {
            const action=await rpc(owner,'campus.dashboard','get_owner_action',[item.action]);
            const views=action.views || action.view_mode.split(',').map(mode=>[false,mode]);
            await rpc(owner,action.res_model,'get_views',[views],{options:{toolbar:false},context:action.context || {}});
        }
        const student=current=await login(browser,'student.ui.qa');
        await student.goto(base+'/my/campus/student/academics');
        await student.locator('.student_subnav').getByRole('link',{name:'Assignments & feedback',exact:true}).click();
        const work=student.locator(`.student_assignment[data-assignment="${scenario.task}"]`);
        await work.locator('textarea[name=description]').fill('My explanation includes the algorithm and boundary tests.');
        await work.locator('input[type=file]').setInputFiles({name:'coursework.txt',mimeType:'text/plain',buffer:Buffer.from('Synthetic submitted coursework')});
        await savePortal(student,work.getByRole('button',{name:'Submit my work',exact:true}));
        assert.equal(new URL(student.url()).hash,'#student_assignments');
        assert(await student.locator('#student_assignments').isVisible());
        let snapshot=await rpc(student,'campus.student.portal','snapshot');
        let row=snapshot.assignments.find(item=>item.id===scenario.task);
        assert.equal(row.state,'submit'); assert.equal(row.marks,null); assert(!row.feedback);
        const teacher=current=await login(browser,'learning.faculty.qa');
        await teacher.goto(base+`/web#id=${row.submission_id}&model=op.assignment.sub.line&view_type=form`);
        await teacher.locator('.o_field_widget[name=note] textarea').fill('Good solution: remember the empty-input case.');
        // An explicit zero must remain distinguishable from an unentered grade.
        await teacher.locator('.o_field_widget[name=campus_marks_entered] input[type=checkbox]').check();
        await teacher.getByRole('button',{name:'Release grade & feedback',exact:true}).click();
        await teacher.getByRole('button',{name:'Release grade & feedback',exact:true}).waitFor({state:'hidden'});
        snapshot=await rpc(student,'campus.student.portal','snapshot');
        row=snapshot.assignments.find(item=>item.id===scenario.task);
        assert.equal(row.state,'accept'); assert.equal(row.marks,0); assert.match(row.feedback,/Good solution/);
        await student.reload();
        await student.locator('.student_subnav').getByRole('link',{name:'Assignments & feedback',exact:true}).click();
        await work.getByText('Released grade:',{exact:false}).waitFor();
        await work.scrollIntoViewIfNeeded();
        await student.screenshot({path:path.join(out,'coursework-feedback-1440.png')});
        const parent=current=await login(browser,'parent.ui.qa');
        await parent.goto(base+'/my/campus/parent/learning?child='+scenario.student);
        const parentWork=parent.locator('.parent_homework').filter({has:parent.getByRole('heading',{name:assignmentName,exact:true})});
        await parentWork.getByText('Good solution: remember the empty-input case.',{exact:false}).waitFor();
        assert.equal(await parent.getByRole('button',{name:'Submit my work',exact:true}).count(),0);
        await parentWork.scrollIntoViewIfNeeded();
        await parent.screenshot({path:path.join(out,'parent-coursework-feedback-1440.png')});
        await student.setViewportSize({width:390,height:900});
        assert(await student.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
        await work.scrollIntoViewIfNeeded();
        await student.screenshot({path:path.join(out,'coursework-feedback-390.png')});
        assert.deepEqual(errors,[]);
        await fs.writeFile(path.join(out,'verification.json'),JSON.stringify({concurrentReferenceReplay:'one receipt',invoiceResidualTotal:openingBalance-100,learningSubmodules:learning.items.length,studentFileSubmission:true,facultyExplicitZero:true,releasedParentFeedback:true,responsiveWidths:[1440,390],pageErrors:errors},null,2));
        console.log('Finance/LMS browser passed: concurrent duplicate protection, submitted file, explicit zero review, parent release and responsive view.');
    } catch(error) {
        if(current) {await current.screenshot({path:path.join(out,'failure.png')}).catch(()=>{}); await fs.writeFile(path.join(out,'failure.txt'),error.stack+'\n'+await current.locator('body').innerText().catch(()=>''));}
        throw error;
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
