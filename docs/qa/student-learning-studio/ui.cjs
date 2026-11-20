// Run against the disposable LMS preview with Playwright and LMS_PREVIEW_PASSWORD.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
    const base = process.env.LMS_BASE_URL || 'http://localhost:18107';
    const output = process.env.LMS_QA_OUT || path.join(process.env.TEMP || '/tmp', 'student-learning-studio-proof');
    await fs.mkdir(output, {recursive: true});
    const browser = await chromium.launch({headless: true});
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    const auth = await context.request.post(`${base}/web/session/authenticate`, {data: {
        jsonrpc: '2.0', method: 'call', params: {db: 'student_learning_studio_preview',
            login: 'student@openeducat.com', password: process.env.LMS_PREVIEW_PASSWORD}, id: 1,
    }});
    assert.ok((await auth.json()).result?.uid, 'Preview student login');
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${base}/my/campus/student/lms#lms/explore`);
    const frame = page.frameLocator('#student_learning_studio');
    await frame.locator('.iz-spotlight').waitFor();
    assert.ok(page.url().endsWith('#lms/explore'), 'Deep link stays on Interest zone');
    assert.equal(await frame.locator('#nav a').count(), 9, 'Exactly nine LMS sections');
    assert.equal(await page.locator('.student_sidebar').count(), 1, 'One original ERP sidebar');
    assert.equal(await frame.locator('.student_sidebar').count(), 0, 'Reference sidebar is excluded');
    assert.equal(await frame.locator('h1').evaluate(el => getComputedStyle(el).fontSize), '33px');
    assert.equal(await frame.locator('body').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(248, 250, 252)');
    for (const section of ['dashboard', 'courses', 'calendar', 'grades', 'tests', 'discussions', 'offline', 'files', 'explore']) {
        await frame.locator(`#nav a[href="#${section}"]`).click();
        await frame.locator('h1').waitFor();
        assert.ok(await frame.locator('h1').innerText(), `${section} heading renders`);
    }
    for (const width of [1920, 1440, 1280, 1151, 1024, 768, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        for (const section of ['dashboard', 'courses', 'calendar', 'grades', 'tests', 'discussions', 'offline', 'files', 'explore']) {
            await frame.locator(`#nav a[href="#${section}"]`).click();
            await page.waitForURL(`**#lms/${section}`);
            assert.ok(await frame.locator('html').evaluate(el => el.scrollWidth <= innerWidth + 1), `${section} fits ${width}px`);
            assert.ok(await page.locator('html').evaluate(el => el.scrollWidth <= innerWidth + 1), `ERP fits ${width}px`);
        }
        if (width === 1440 || width === 390) await page.screenshot({path: path.join(output, `interest-zone-${width}.png`)});
    }
    if (process.env.LMS_LAYOUT_ONLY) {
        assert.deepEqual(errors, [], 'No browser runtime errors');
        console.log('PASS: all nine sections at eight device widths, reference typography/colors and deep link.');
        await browser.close();
        return;
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await frame.locator('[data-act="search"]').click();
    await frame.locator('#globalsearch').fill('database');
    assert.ok((await frame.locator('#searchresults').innerText()).includes('Database'));
    await frame.locator('#modal [data-act="close"]').click();
    await frame.locator('#nav a[href="#files"]').click();
    await frame.locator('#fileinput').setInputFiles({name: 'LMS QA note.txt', mimeType: 'text/plain', buffer: Buffer.from('Private learning file check')});
    const fileRow = frame.locator('#filelist .itemlink').filter({hasText: 'LMS QA note.txt'});
    await fileRow.waitFor();
    const downloadEvent = page.waitForEvent('download');
    await fileRow.locator('[data-act^="getfile/"]').click();
    const download = await downloadEvent;
    assert.equal(download.suggestedFilename(), 'LMS QA note.txt');
    assert.equal(await fs.readFile(await download.path(), 'utf8'), 'Private learning file check');
    await fileRow.locator('[data-act^="dropfile/"]').click();
    await frame.locator('#modal [data-act^="confirmdrop/"]').click();
    await fileRow.waitFor({state: 'detached'});
    // A draft typed just before leaving the iframe must reach the server.
    await page.goto(`${base}/my/campus/student/lms#lms/lesson/db/5`);
    await frame.locator('#assignmentText').waitFor();
    const draft = 'Use a primary key to identify each row and a foreign key to connect related tables.';
    await frame.locator('#assignmentText').fill(draft);
    await page.locator('.student_sidebar a[data-navigation-key="academics"]').click();
    await page.waitForURL('**/student/academics*');
    await page.goto(`${base}/my/campus/student/lms#lms/lesson/db/5`);
    await frame.locator('#assignmentText').waitFor();
    assert.equal(await frame.locator('#assignmentText').inputValue(), draft, 'Draft saved before leaving LMS');
    await frame.locator('#nav a[href="#dashboard"]').click();
    await page.screenshot({path: path.join(output, 'dashboard-1440.png')});
    assert.deepEqual(errors, [], 'No browser runtime errors');
    console.log('PASS: nine sections, deep link, reference typography/colors, eight device widths, search dialog, private files, and draft navigation persistence.');
    console.log(`Screenshots: ${output}`);
    await browser.close();
})().catch(error => {console.error(error); process.exit(1);});
