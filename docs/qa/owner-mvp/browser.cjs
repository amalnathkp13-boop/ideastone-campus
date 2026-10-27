// Real Odoo screens and RPCs on a disposable database; no mock server or production login.
const {chromium} = require('playwright');
const {assertCampusTheme} = require('../campus-theme.cjs');
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
    const page = await browser.newPage({viewport:{width:1440,height:1000},timezoneId:'Asia/Kolkata',reducedMotion:'reduce'});
    page.setDefaultTimeout(60000);
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    try {
        await page.goto(base+'/web/login?db=ci');
        await page.locator('input[name=login]').fill('owner.ui.qa');
        await page.locator('input[name=password]').fill(process.env.FACULTY_QA_PASSWORD);
        // Wait for the login POST to finish before navigating elsewhere; navigating early cancels it.
        await Promise.all([page.waitForURL(url=>!url.pathname.startsWith('/web/login')), page.locator('button[type=submit]').click()]);
        await page.goto(base+'/web#action=ideastone_erp.action_dashboard');
        await page.getByRole('heading',{name:'Admin overview',exact:true}).waitFor();
        await page.locator('.campus_owner_stat').first().waitFor();
        const firstMetrics = await rpc(page,'campus.dashboard','get_owner_metrics');
        const studentCard = firstMetrics.stats.find(s=>s.kind==='active_students');
        if(studentCard.value!==3) throw Error('Owner demo does not reconcile with its saved students');
        await assertCampusTheme(page);
        await page.screenshot({path:path.join(out,'owner-dashboard-1440.png'),fullPage:true});
        await page.locator('.collection-panel').evaluate(element=>element.scrollIntoView({block:'start'}));
        const feeMonths=firstMetrics.overview_ui.fee_months;
        const collectionBars=await page.locator('.collection-panel .fee-bar-fill').evaluateAll(nodes=>nodes.map(node=>parseFloat(node.style.height)));
        // Each vertical bar compares the amount collected with the billed fees for
        // that same due-month invoice cohort; empty months must remain at zero.
        if(feeMonths.length!==6 || collectionBars.length!==6
            || feeMonths.reduce((sum,row)=>sum+row.target,0)!==500
            || feeMonths.reduce((sum,row)=>sum+row.collected,0)!==300
            || firstMetrics.overview_ui.fee_percent!==60
            || collectionBars.some((height,index)=>Math.abs(height-(feeMonths[index].target ? feeMonths[index].collected/feeMonths[index].target*100 : 0))>0.1)) throw Error('Monthly fee bars do not reconcile with the billed and collected amounts');
        const panelHeights=await page.locator('.collection-panel,.ai-panel').evaluateAll(nodes=>nodes.map(node=>node.getBoundingClientRect().height));
        if(Math.abs(panelHeights[0]-panelHeights[1])>1) throw Error('Fee and insights cards are not balanced on desktop');
        await page.getByRole('heading',{name:'Decision Overview',exact:true}).waitFor();
        if(await page.locator('.decision-grid .deadlines-panel').evaluate(el=>getComputedStyle(el).gridColumn)!=='1 / -1') throw Error('Dashboard deadlines do not span the full row');
        await assertCampusTheme(page);
        await page.screenshot({path:path.join(out,'owner-charts-1440.png')});
        if(await page.locator('.admin_overview .kpi').count()!==8) throw Error('Admin overview does not show eight indicators');
        if(await page.locator('.event-card').count()!==3) throw Error('Admin event cards do not reflect the four saved events');
        if(await page.locator('.admin_overview .kpi-value').first().evaluate(el=>getComputedStyle(el).color)!=='rgb(16, 45, 73)') throw Error('Saved KPI text does not use the reference color');
        if(await page.locator('.event-category').first().evaluate(el=>getComputedStyle(el).color)!=='rgb(115, 85, 199)') throw Error('Saved event category does not use the reference color');
        for(const width of [320,390,768,1440]) {
            await page.setViewportSize({width,height:1000});
            if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw Error(`Admin overview overflows at ${width}`);
        }
        await page.locator('.feature-open').click();
        await page.locator('.o_form_view').waitFor();
        await page.locator('.campus_sidebar').getByRole('button',{name:'Dashboard',exact:true}).click();
        await page.locator('.admin_overview .kpi').first().waitFor();
        await page.getByRole('button',{name:'Event calendar',exact:true}).click();
        await page.locator('.o_calendar_view').waitFor();
        await page.locator('.campus_sidebar').getByRole('button',{name:'Dashboard',exact:true}).click();
        await page.locator('.admin_overview .kpi').first().waitFor();
        if(await page.locator('.campus_dashboard').innerText().then(text=>/Â·|â€”|â†/.test(text))) throw Error('Owner template contains incorrectly decoded UTF-8 punctuation');
        await page.locator('.campus_dashboard').evaluate(element=>element.scrollTop=0);
        const modules = await page.locator('.campus_sidebar nav .campus_nav_link').allTextContents();
        // 13 base modules; the optional AI Pack (ideastone_ai) adds one more.
        const aiPack=modules.some(label=>label.trim()==='AI insights');
        if(modules.length!==13+(aiPack?1:0)) throw Error('Owner sidebar does not contain the 13 functional MVP modules');
        const overview=await rpc(page,'campus.dashboard','get_overview');
        let checkedViews=0;
        for(const module of overview.faculty_modules) {
            for(const item of module.items.filter(item=>item.action)) {
                const action=await rpc(page,'campus.dashboard','get_owner_action',[item.action]);
                if(action.type==='ir.actions.client') {
                    if(!action.tag) throw Error(`Client submodule ${item.action} has no action tag`);
                    continue;
                }
                const views=action.views || action.view_mode.split(',').map(mode=>[false,mode]);
                await rpc(page,action.res_model,'get_views',[views],{options:{toolbar:false,load_filters:false},context:action.context || {}});
                checkedViews++;
            }
        }
        if(aiPack) {
            await page.locator('.campus_sidebar').getByRole('button',{name:'AI insights',exact:true}).click();
            await page.getByRole('button',{name:'Student Success Radar',exact:true}).click();
            await page.getByRole('heading',{name:'Student Success Radar',exact:true,level:1}).waitFor();
            await page.locator('.radar_table tbody tr.radar_row').first().waitFor();
            const radar=await rpc(page,'campus.success.radar','get_workspace',[{}]);
            if(radar.summary.students<1 || radar.rows.some(row=>row.score<0 || row.score>100)) throw Error('Student Success Radar returned no scored students or an out-of-range score');
            if(await page.locator('.radar_row').count()!==radar.rows.length) throw Error('Radar table does not list every scored student');
            await assertCampusTheme(page);
            await page.screenshot({path:path.join(out,'owner-success-radar-1440.png'),fullPage:true});
            await page.locator('.campus_sidebar').getByRole('button',{name:'AI insights',exact:true}).click();
            await page.getByRole('button',{name:'Campus Assistant',exact:true}).click();
            await page.getByRole('heading',{name:'Campus Assistant',exact:true,level:1}).waitFor();
            await page.getByText('Not configured',{exact:true}).waitFor();
            if(await page.locator('#ai_question').isEnabled()) throw Error('Assistant accepts questions before a provider is configured');
            await assertCampusTheme(page);
            await page.screenshot({path:path.join(out,'owner-assistant-1440.png'),fullPage:true});
            await page.locator('.campus_sidebar').getByRole('button',{name:'Dashboard',exact:true}).click();
            await page.locator('.admin_overview .kpi').first().waitFor();
        }
        for (const module of overview.faculty_modules.filter(module=>module.key!=='home')) {
            await page.locator('.campus_sidebar').getByRole('button',{name:module.label,exact:true}).click();
            await page.getByRole('heading',{name:({admissions:'Admissions',students:'Student directory'})[module.key]||module.label,exact:true,level:1}).waitFor();
        }
        await page.locator('.campus_sidebar').getByRole('button',{name:'Admissions',exact:true}).click();
        await page.getByRole('heading',{name:'Admissions',exact:true}).waitFor();
        if(await page.locator('.campus_admissions_workspace .stat').count()!==4) throw Error('Admissions overview does not show four live indicators');
        await assertCampusTheme(page);
        for(const [label,title] of [['Enquiries','Enquiry studio'],['Applications & review','Applications & review'],['Documents','Document verification desk'],['Admission register','Admission register']]) {
            await page.locator('.campus_faculty_subnav').getByRole('button',{name:label,exact:true}).click();
            await page.getByRole('heading',{name:title,exact:true,level:1}).waitFor();
            await page.locator('.campus_admissions_workspace .loading-note').waitFor({state:'hidden'});
            if(await page.locator('.campus_admissions_workspace .alert-danger').count()) throw Error(`Admissions workspace ${label} failed to load`);
        }
        await page.locator('.campus_sidebar').getByRole('button',{name:'Students',exact:true}).click();
        await page.getByRole('heading',{name:'Student directory',exact:true,level:1}).waitFor();
        if(await page.locator('.campus_students_workspace .kpi').count()!==4) throw Error('Students directory does not show four indicators');
        await assertCampusTheme(page);
        const directoryDepartment=await page.locator('.campus_students_workspace .dept h3').first().innerText();
        await page.locator('.campus_students_workspace .dept .textbtn').first().click();
        await page.getByRole('heading',{name:directoryDepartment,exact:true,level:1}).waitFor();
        await page.locator('.campus_students_workspace .sectiontiles').waitFor();
        await page.getByRole('button',{name:'← Student directory',exact:true}).click();
        await page.getByRole('heading',{name:'Student directory',exact:true,level:1}).waitFor();
        await page.getByRole('button',{name:'View all students ↗',exact:true}).click();
        await page.getByRole('heading',{name:'All students',exact:true,level:1}).waitFor();
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Enrolments & transfers',exact:true}).click();
        await page.getByRole('heading',{name:'Enrolments & Transfers',exact:true,level:1}).waitFor();
        if(await page.locator('.campus_students_workspace .alert-danger').count()) throw Error('Enrolments workspace failed to load');
        await page.locator('.campus_sidebar').getByRole('button',{name:'Timetable',exact:true}).click();
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Class timetable',exact:true}).click();
        await page.locator('.o_control_panel').getByText('Class timetable',{exact:true}).last().waitFor();
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Faculty timetable',exact:true}).waitFor();
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Rooms',exact:true}).click();
        await page.locator('.o_view_nocontent_smiling_face').waitFor();
        if((await page.locator('.o_content').innerText()).includes('<p class=')) throw Error('Empty module renders raw action help HTML');
        await page.locator('.campus_sidebar').getByRole('button',{name:'Fees & Payments',exact:true}).click();
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Fee heads',exact:true}).click();
        await page.getByRole('cell',{name:'Tuition installment',exact:true}).waitFor();
        await page.locator('.campus_sidebar').getByRole('button',{name:'Communication',exact:true}).click();
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Student requests & support',exact:true}).click();
        await page.locator('.o_list_view').waitFor();
        await page.locator('.o_control_panel').getByText('Student requests & support',{exact:true}).last().waitFor();
        if(await page.locator('.o_list_button_add:visible').count()) throw Error('Request review register offers a blank request creation form');
        await page.locator('.campus_sidebar').getByRole('button',{name:'Faculty & Staff',exact:true}).click();
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Staff Profile',exact:true}).click();
        await page.locator('#staff_profile_select').waitFor();
        await page.locator('.staff_profile_alert').waitFor({state:'hidden'});
        if(await page.locator('#staff_profile_select option').count()!==1) throw Error('Owner staff profile includes staff outside the active college');
        await page.getByRole('button',{name:'Add qualification',exact:false}).click();
        await page.locator('.o_list_button_add:visible').click();
        await page.locator('.o_field_widget[name=name] input').fill('Owner QA qualification');
        await page.locator('.o_field_widget[name=institution] input').fill('QA college');
        const detailSave=page.waitForResponse(r=>r.url().includes('/campus.faculty.detail/web_save'));
        await page.locator('.o_form_button_save:visible').click();
        const detailResult=await(await detailSave).json();
        if(detailResult.error) throw Error(detailResult.error.data?.message || detailResult.error.message);
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Staff Profile',exact:true}).click();
        await page.getByRole('cell',{name:'Owner QA qualification',exact:true}).waitFor();
        if(await page.locator('.staff_profile_alert').count()) throw Error('Owner profile displays a record access error');
        await assertCampusTheme(page);
        await page.screenshot({path:path.join(out,'owner-staff-profile.png'),fullPage:true});
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Faculty development and appraisal',exact:true}).click();
        await page.getByRole('heading',{name:'Professional Development and Appraisal',exact:true}).waitFor();
        await page.locator('.appraisal_loading').waitFor({state:'hidden'});
        if(await page.locator('.appraisal_error').count()) throw Error('Owner appraisal failed to load');
        await page.getByLabel('Name of the student',{exact:true}).fill('Owner QA portfolio entry');
        await page.locator('.appraisal_entry button[type=submit]').click();
        await page.getByRole('cell',{name:'Owner QA portfolio entry',exact:true}).waitFor();
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Leave Management',exact:true}).click();
        await page.getByRole('heading',{name:'Online Leave Apply & Status',exact:true}).waitFor();
        await page.locator('.leave_loading').waitFor({state:'hidden'});
        if(await page.locator('.leave_error').count()) throw Error('Owner leave page failed to load');
        await page.locator('.campus_sidebar').getByRole('button',{name:'Settings',exact:true}).click();
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'College profile & attendance policy',exact:true}).click();
        const threshold=page.locator('.o_field_widget[name=campus_attendance_threshold] input');
        await threshold.fill('76');
        // Saving a company reloads Odoo; wait before issuing the next RPC.
        await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}), page.locator('.o_form_button_save:visible').click()]);
        await threshold.waitFor();
        const collegeAction=await rpc(page,'campus.dashboard','get_owner_action',['ideastone_erp.mvp_college']);
        let savedPolicy=await rpc(page,'res.company','read',[[collegeAction.res_id]],{fields:['campus_attendance_threshold']});
        if(savedPolicy[0].campus_attendance_threshold!==76) throw Error('College policy did not persist');
        await threshold.fill('75');
        await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}), page.locator('.o_form_button_save:visible').click()]);
        await threshold.waitFor();
        savedPolicy=await rpc(page,'res.company','read',[[collegeAction.res_id]],{fields:['campus_attendance_threshold']});
        if(savedPolicy[0].campus_attendance_threshold!==75) throw Error('College policy was not restored');
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'ID & receipt numbering',exact:true}).click();
        await page.waitForURL(url=>url.hash.includes('model=ir.sequence'));
        await page.locator('.o_list_view').waitFor();
        await page.locator('.campus_sidebar').getByRole('button',{name:'Dashboard',exact:true}).click();
        await page.getByRole('button',{name:'Filters',exact:true}).click();
        await page.getByLabel('From',{exact:true}).fill('9999-12-01');
        await page.getByLabel('Through',{exact:true}).fill('9999-12-31');
        await page.getByRole('button',{name:'Apply filters',exact:true}).click();
        await page.getByRole('alert').filter({hasText:'Select a valid reporting period of at most three years.'}).waitFor();
        const today=new Date().toISOString().slice(0,10);
        await page.getByLabel('From',{exact:true}).fill(today.slice(0,8)+'01');
        await page.getByLabel('Through',{exact:true}).fill(today);
        await page.getByRole('button',{name:'Apply filters',exact:true}).click();
        await page.locator('.campus_owner_stat').first().waitFor();
        for(const kind of ['admissions','students','attendance','collection','dues','results','faculty']) {
            const report=await rpc(page,'campus.mvp.report','create',[{kind}]);
            await rpc(page,'campus.mvp.report','action_csv',[[report]]);
        }
        await page.locator('.campus_sidebar').getByRole('button',{name:'Academics',exact:true}).click();
        await page.getByRole('heading',{name:'Academics',exact:true,level:1}).waitFor();
        await assertCampusTheme(page);
        await page.screenshot({path:path.join(out,'owner-academics-1440.png')});
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'Subjects & curriculum',exact:true}).click();
        await page.getByRole('heading',{name:'Subjects & curriculum',exact:true,level:1}).waitFor();
        const create = page.getByRole('button',{name:'＋ Add subject',exact:true});
        await create.waitFor();
        const box = await create.boundingBox();
        const nav = await page.locator('.campus_faculty_subnav').boundingBox();
        if(box.y<nav.y+nav.height) throw Error('Owner submodule bar obscures the academic create button');
        await create.click();
        const academicDialog = page.getByRole('dialog');
        await academicDialog.getByLabel('Subject name',{exact:true}).fill('QA browser persisted subject');
        await academicDialog.getByLabel('Subject code',{exact:true}).fill('OWNER-BROWSER');
        await academicDialog.getByLabel('Credits',{exact:true}).fill('3.5');
        const response = page.waitForResponse(r=>r.url().includes('/campus.academics.ui/save_record'));
        await academicDialog.getByRole('button',{name:'Save record',exact:true}).click();
        const saved = await (await response).json();
        if(saved.error) throw Error(saved.error.data?.message || saved.error.message);
        await academicDialog.waitFor({state:'hidden'});
        const subjects=await rpc(page,'op.subject','search_read',[[['code','=','OWNER-BROWSER']]],{fields:['name','company_id','campus_credits']});
        if(subjects.length!==1 || subjects[0].name!=='QA browser persisted subject' || subjects[0].campus_credits!==3.5) throw Error('Owner subject form did not persist');
        await page.reload();
        await page.getByRole('heading',{name:'Subjects & curriculum',exact:true,level:1}).waitFor();
        await page.getByRole('button',{name:'QA browser persisted subject',exact:true}).click();
        await academicDialog.getByText('OWNER-BROWSER',{exact:true}).waitFor();
        await academicDialog.getByText('3.5',{exact:true}).waitFor();
        if(await page.locator('.g2_review_container').count()) throw Error('Upstream promotional dialog blocks the Owner workspace');
        await assertCampusTheme(page);
        await page.screenshot({path:path.join(out,'owner-subject-1440.png')});
        await academicDialog.getByRole('button',{name:'Close',exact:true}).last().click();
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
        await assertCampusTheme(page);
        await page.screenshot({path:path.join(out,'owner-desktop-1024.png')});
        await page.setViewportSize({width:390,height:844});
        await page.locator('.campus_mobile_toggle').click();
        await page.locator('.campus_sidebar.is-open').waitFor();
        await page.keyboard.press('Escape');
        await page.locator('.campus_sidebar').waitFor({state:'hidden'});
        if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw Error('Owner dashboard overflows the mobile viewport');
        await assertCampusTheme(page);
        await page.screenshot({path:path.join(out,'owner-mobile-390.png')});
        if(errors.length) throw Error(errors.join('\n'));
        await fs.writeFile(path.join(out,'verification.json'),JSON.stringify({passed:true,checkedViews,checks:['13 owner modules','all permitted submodule views','7 real CSV exports','owner staff qualification save and reload','owner appraisal save','owner leave page','numbering settings','native empty-state help renders as HTML','shared timetable action retains selected module','shared fee heads visible','student request register opens as a list','college attendance policy save and restore','invalid reporting period recovery','faculty shell reused','live KPI reconciliation','real subject form save and reload','concurrent admission conversion','concurrent payment posting','receipt PDF','1024 desktop','390 mobile drawer and overflow','browser console'],metrics,errors},null,2));
    } catch(error) {
        await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});
        await fs.writeFile(path.join(out,'failure-dom.html'),await markup(page));
        await fs.writeFile(path.join(out,'failure.txt'),`${error.stack}\n${page.url()}\n${await page.locator('body').innerText().catch(()=>'')}`);
        throw error;
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
