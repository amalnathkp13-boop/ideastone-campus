// Browser history must flush an LMS draft before the portal replaces its iframe.
const assert = require('node:assert/strict');
const {chromium} = require('playwright');

(async () => {
    const base = process.env.LMS_BASE_URL || 'http://localhost:18107';
    const browser = await chromium.launch({headless: true});
    try {
        const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
        const auth = await context.request.post(`${base}/web/session/authenticate`, {data: {
            jsonrpc: '2.0', method: 'call', params: {db: 'student_learning_studio_preview',
                login: 'student@openeducat.com', password: process.env.LMS_PREVIEW_PASSWORD}, id: 1,
        }});
        assert.ok((await auth.json()).result?.uid, 'Preview student login');
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${base}/my/campus/student/academics`);
        await page.locator('.campus_desktop_toggle[title]').waitFor();
        await page.evaluate(() => { window.lmsHistoryTestDocument = true; });
        await page.locator('.student_sidebar a[data-navigation-key="lms"]').click();
        const frame = page.frameLocator('#student_learning_studio');
        await frame.locator('#nav').waitFor();
        await page.waitForURL('**#lms/dashboard');
        assert.equal(await page.evaluate(() => window.lmsHistoryTestDocument), true, 'Exercise AJAX portal navigation');
        // Open an unsubmitted assignment without adding a lesson history entry.
        await frame.locator('body').evaluate(() => location.replace('#lesson/db/5'));
        await frame.locator('#assignmentText').waitFor();
        await page.waitForURL('**#lms/lesson/db/5');
        assert.equal(await frame.locator('body').evaluate(() => window.LEARNING_STUDIO_FLUSH()), true);
        const originalDraft = await frame.locator('#assignmentText').inputValue();
        const lmsUrl = page.url();
        let rejectSaves = false;
        await page.route('**/my/campus/student/lms/state', async route => {
            await new Promise(resolve => setTimeout(resolve, 1200));
            if (rejectSaves) await route.fulfill({status: 503, contentType: 'application/json', body: '{"error":"Temporary test failure"}'});
            else await route.continue();
        });
        // Seed adjacent parent history entries so the traversal crosses pages,
        // without depending on how many lesson entries the iframe has created.
        const prepareBack = () => page.evaluate(({base, lmsUrl}) => {
            history.replaceState({}, '', `${base}/my/campus/student/academics`);
            history.pushState({}, '', lmsUrl);
        }, {base, lmsUrl});
        await prepareBack();
        const backDraft = `Back navigation draft ${Date.now()}`;
        await frame.locator('#assignmentText').fill(backDraft);
        await page.evaluate(() => history.back());
        await page.waitForURL('**/student/academics*');
        await page.locator('#student_learning_studio').waitFor({state: 'detached'});
        await page.goto(lmsUrl);
        await frame.locator('#assignmentText').waitFor();
        assert.equal(await frame.locator('#assignmentText').inputValue(), backDraft, 'Back saves the pending draft');

        await page.evaluate(({base, lmsUrl}) => {
            history.replaceState({}, '', lmsUrl);
            history.pushState({}, '', `${base}/my/campus/student/profile`);
            history.back();
        }, {base, lmsUrl});
        await page.waitForURL(lmsUrl);
        await frame.locator('#assignmentText').waitFor();
        const forwardDraft = `Forward navigation draft ${Date.now()}`;
        await frame.locator('#assignmentText').fill(forwardDraft);
        await page.evaluate(() => history.forward());
        await page.waitForURL('**/student/profile*');
        await page.locator('#student_learning_studio').waitFor({state: 'detached'});
        await page.goto(lmsUrl);
        await frame.locator('#assignmentText').waitFor();
        assert.equal(await frame.locator('#assignmentText').inputValue(), forwardDraft, 'Forward saves the pending draft');
        await prepareBack();
        rejectSaves = true;
        const unsaved = `Retained after save failure ${Date.now()}`;
        await frame.locator('#assignmentText').fill(unsaved);
        const failedSave = page.waitForResponse(response => response.url().endsWith('/lms/state') && response.status() === 503);
        await page.evaluate(() => history.back());
        await failedSave;
        await page.waitForURL(lmsUrl);
        await frame.locator('#save-status').waitFor();
        assert.equal(await frame.locator('#assignmentText').inputValue(), unsaved, 'Failed save keeps the LMS draft visible');
        rejectSaves = false;
        await frame.locator('[data-act="retry-save"]').click();
        await frame.locator('#save-status').waitFor({state: 'hidden'});
        await frame.locator('#assignmentText').fill(originalDraft);
        assert.equal(await frame.locator('body').evaluate(() => window.LEARNING_STUDIO_FLUSH()), true);
        assert.deepEqual(errors, [], 'No browser runtime errors');
        console.log('PASS: Back/Forward preserve pending drafts; failed saves retain the draft and retry works.');
    } finally {
        await browser.close();
    }
})().catch(error => {console.error(error); process.exit(1);});
