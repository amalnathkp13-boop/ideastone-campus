// Exercise the real Odoo UI against a disposable, loopback-only CI database.
const {chromium} = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const base = 'http://127.0.0.1:18069';
const out = process.env.FACULTY_QA_OUT;
if (!out || !process.env.FACULTY_QA_PASSWORD) throw Error('Disposable QA configuration required');
(async () => {
    await fs.mkdir(out, {recursive:true});
    const browser = await chromium.launch({headless:true});
    try {
        const page = await browser.newPage({viewport:{width:1440,height:1000}});
        page.setDefaultTimeout(90000);
        const errors=[];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(base+'/web/login?db=ci');
        await page.locator('input[name=login]').fill('faculty.ui.qa');
        await page.locator('input[name=password]').fill(process.env.FACULTY_QA_PASSWORD);
        await page.locator('button[type=submit]').click();
        await page.goto(base+'/web#action=ideastone_erp.action_dashboard');
        await page.locator('body.campus_faculty_workspace').waitFor();
        await page.getByRole('heading', {name:'Welcome back, QA Faculty'}).waitFor();
        await page.screenshot({path:path.join(out,'faculty-overview-1440.png')});
        await page.locator('.campus_sidebar').getByRole('button',{name:'My task list',exact:true}).click();
        await page.getByRole('heading',{name:'My task list',exact:true,level:1}).waitFor();
        await page.screenshot({path:path.join(out,'faculty-module-1440.png')});
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'My tasks & e-diary',exact:true}).click();
        await page.locator('.o_list_button_add').click();
        await page.locator('.o_field_widget[name=name] input').fill('QA browser persisted diary');
        const saveResponse = page.waitForResponse(response => response.url().includes('/campus.faculty.task/web_save'));
        await page.locator('.o_form_button_save').click();
        const saveData = await (await saveResponse).json();
        if (saveData.error) throw Error(JSON.stringify(saveData.error));
        const saved = await page.evaluate(async () => {
            const response=await fetch('/web/dataset/call_kw/campus.faculty.task/search_read',{
                method:'POST',headers:{'Content-Type':'application/json'},
                body:JSON.stringify({jsonrpc:'2.0',method:'call',params:{model:'campus.faculty.task',method:'search_read',
                    args:[[ ['name','=','QA browser persisted diary'] ]],kwargs:{fields:['name','state']}}})});
            return response.json();
        });
        if (saved.result?.length !== 1) throw Error('Diary was not persisted by the real form');
        await page.screenshot({path:path.join(out,'faculty-diary-1440.png')});
        await page.reload();
        await page.locator('body.campus_faculty_workspace').waitFor();
        await page.locator('.campus_faculty_subnav').getByRole('button',{name:'My tasks & e-diary',exact:true}).waitFor();
        await page.setViewportSize({width:390,height:844});
        await page.locator('.campus_mobile_toggle').click();
        await page.locator('.campus_sidebar.is-open').waitFor();
        await page.keyboard.press('Escape');
        await page.locator('.campus_sidebar:not(.is-open)').waitFor();
        await page.screenshot({path:path.join(out,'faculty-mobile-390.png')});
        const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
        if(overflow) throw Error('Faculty document overflows mobile viewport');
        if(errors.length) throw Error(errors.join('\n'));
        await fs.writeFile(path.join(out,'verification.json'),JSON.stringify({passed:true,
            checks:['faculty-only shell','main module and topbar navigation','diary form persistence','reload navigation','mobile drawer Escape','mobile overflow','browser console'],errors},null,2));
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
