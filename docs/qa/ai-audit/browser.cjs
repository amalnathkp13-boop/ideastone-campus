// Real Odoo HTTP requests; only the external provider boundary is a deterministic local server.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');

const base = process.env.AI_QA_BASE || 'http://127.0.0.1:18069';
const db = process.env.AI_QA_DB || 'ci';
assert(['localhost', '127.0.0.1'].includes(new URL(base).hostname), 'Loopback QA only');
assert(['ci', 'campus_ai_audit_20261027'].includes(db), 'Disposable QA database only');
const out = process.env.AI_QA_OUT;
assert(out && process.env.AI_QA_PASSWORD, 'QA output and runtime password required');

(async () => {
    await fs.mkdir(out, { recursive: true });
    let status = 200, malformed = false, delay = 0;
    const calls = [];
    const server = http.createServer(async (request, response) => {
        const chunks = [];
        for await (const chunk of request) chunks.push(chunk);
        const payload = JSON.parse(Buffer.concat(chunks).toString());
        calls.push(payload);
        const requestStatus = status;
        const body = malformed ? [] : { choices: [{ message: { content:
            payload.messages[0].content.includes('official notices') ? 'TITLE: Synthetic notice\n\nBring your <b>identity card</b>.' :
            payload.messages[0].content.includes('aggregate feedback') ? 'Library and laboratory topics require review. These are category counts, not individual comments.' :
            'The supplied college data contains three active students.' } }] };
        if (delay) await new Promise(resolve => setTimeout(resolve, delay));
        response.writeHead(requestStatus, { 'Content-Type': 'application/json' });
        response.end(JSON.stringify(body));
    });
    await new Promise(resolve => server.listen(18081, '127.0.0.1', resolve));
    const browser = await chromium.launch({ headless: true, channel: process.env.AI_QA_CHANNEL });
    const contexts = [];
    const checks = [];
    const errors = [];
    async function account(login) {
        const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
        contexts.push(context);
        const data = await (await context.request.post(base + '/web/session/authenticate', { data: {
            jsonrpc: '2.0', params: { db, login, password: process.env.AI_QA_PASSWORD },
        } })).json();
        assert(data.result?.uid, 'QA sign-in failed');
        return context;
    }
    async function raw(context, model, method, args = []) {
        return (await context.request.post(base + '/web/dataset/call_kw/' + model + '/' + method,
            { data: { jsonrpc: '2.0', params: { model, method, args, kwargs: {} } } })).json();
    }
    async function rpc(context, model, method, args = []) {
        const data = await raw(context, model, method, args);
        assert(!data.error, data.error?.data?.message);
        return data.result;
    }
    try {
        const owner = await account('ai.owner.qa');
        const mentor = await account('ai.mentor.qa');
        const hod = await account('ai.hod.qa');
        const student = await account('ai.student.qa');
        const parent = await account('ai.parent.qa');
        const workspace = await rpc(owner, 'campus.success.radar', 'get_workspace');
        const companyId = (await rpc(owner, 'res.users', 'context_get')).allowed_company_ids?.[0]
            || (await rpc(owner, 'res.company', 'search', [[['name', '=', 'AI QA Synthetic College']]]))[0];
        await rpc(owner, 'res.company', 'write', [[companyId], { campus_ai_enabled: true, campus_ai_monthly_limit: 100 }]);
        assert.equal(workspace.summary.students, 3);
        assert.equal((await rpc(mentor, 'campus.success.radar', 'get_workspace')).rows.length, 1);
        assert.equal((await rpc(hod, 'campus.success.radar', 'get_workspace')).rows.length, 3);
        assert((await raw(student, 'campus.success.radar', 'get_workspace')).error);
        assert((await raw(mentor, 'campus.ai.assistant', 'get_status')).error);
        checks.push('owner/HOD/mentor scope and portal/assistant access denials');

        const page = await owner.newPage();
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(base + '/web#action=ideastone_ai.action_success_radar');
        await page.getByRole('heading', { name: 'Student Success Radar', exact: true }).waitFor();
        await page.locator('.radar_row').first().waitFor();
        assert.equal(await page.locator('.radar_row').count(), 3);
        await page.locator('.radar_buttons').first().getByRole('button', { name: 'Details', exact: true }).click();
        assert((await page.locator('.radar_details').innerText()).includes('0%'));
        await page.screenshot({ path: path.join(out, 'radar-desktop.png') });
        checks.push('radar renders scored records and explanations');

        for (const context of [student, parent]) {
            const portal = await context.newPage();
            await portal.goto(base + '/my/campus');
            await portal.locator('.success_nudge').waitFor();
            const text = await portal.locator('.success_nudge').innerText();
            assert(text.includes('Attendance needs attention'));
            assert(!text.includes('on track'));
        }
        checks.push('student and parent do not call zero attendance on track');

        await page.goto(base + '/web#action=ideastone_ai.action_assistant');
        await page.getByRole('heading', { name: 'Campus Assistant', exact: true }).waitFor();
        await page.locator('#ai_question').fill('How many active students are recorded?');
        await page.getByRole('button', { name: 'Ask', exact: true }).click();
        await page.locator('.ai_answer_a').waitFor();
        assert((await page.locator('.ai_answer_a').innerText()).includes('three active students'));
        await page.getByRole('button', { name: 'Draft a notice', exact: true }).click();
        await page.locator('#ai_brief').fill('Synthetic campus notice: bring your identity card.');
        await page.getByRole('button', { name: 'Draft notice', exact: true }).click();
        await page.locator('.ai_notice_body').waitFor();
        assert.equal(await page.locator('.ai_notice_body b').count(), 0);
        checks.push('ask and notice workflows render provider output safely');
        await page.getByRole('button', { name: 'Create circular from this draft', exact: true }).click();
        const title = page.locator('.o_field_widget[name="name"] input');
        await title.waitFor();
        assert.equal(await title.inputValue(), 'Synthetic notice');
        assert(await title.isEditable());
        checks.push('generated notice opens as an editable unsaved circular');
        await page.goto(base + '/web#action=ideastone_ai.action_assistant');
        await page.getByRole('heading', { name: 'Campus Assistant', exact: true }).waitFor();

        await page.getByRole('button', { name: 'Feedback themes', exact: true }).click();
        await page.getByRole('button', { name: 'Find themes', exact: true }).click();
        await page.locator('.ai_answer_a').waitFor();
        assert((await page.locator('.ai_answer_a').innerText()).includes('category counts'));
        await page.getByRole('heading', { name: 'Recorded counts', exact: true }).waitFor();
        for (const width of [1440, 1728, 390]) {
            await page.setViewportSize({ width, height: 1000 });
            assert(!await page.locator('.campus_ai_page').evaluate(el => el.scrollWidth > el.clientWidth + 2));
            await page.screenshot({ path: path.join(out, `assistant-feedback-${width}.png`) });
        }
        assert(!JSON.stringify(calls).includes('PRIVATE'));
        assert(!JSON.stringify(calls).includes('@example.test'));
        checks.push('provider payload contains no saved feedback text or student identifiers');

        let used = (await rpc(owner, 'campus.ai.assistant', 'get_status')).used;
        status = 503;
        assert((await raw(owner, 'campus.ai.assistant', 'ask', ['Test provider failure'])).error);
        assert.equal((await rpc(owner, 'campus.ai.assistant', 'get_status')).used, used + 1);
        const logs = await rpc(owner, 'campus.ai.log', 'search_read', [[['company_id', '=', companyId], ['ok', '=', false]], ['error']]);
        assert(logs.some(log => log.error.includes('HTTP 503')));
        checks.push('failure log survives the failed HTTP transaction');
        status = 200; malformed = true;
        assert((await raw(owner, 'campus.ai.assistant', 'ask', ['Test malformed response'])).error);
        malformed = false;
        used = (await rpc(owner, 'campus.ai.assistant', 'get_status')).used;
        checks.push('malformed provider JSON produces a controlled audited error');

        await rpc(owner, 'res.company', 'write', [[companyId], { campus_ai_monthly_limit: used + 1 }]);
        delay = 500;
        const before = calls.length;
        const attempts = await Promise.all([raw(owner, 'campus.ai.assistant', 'draft_notice', ['First request']),
            raw(owner, 'campus.ai.assistant', 'draft_notice', ['Concurrent request'])]);
        assert.equal(attempts.filter(item => item.error).length, 1);
        assert.equal(calls.length, before + 1);
        assert.equal((await rpc(owner, 'campus.ai.assistant', 'get_status')).used, used + 1);
        checks.push('concurrent requests cannot exceed the monthly provider cap');
        await rpc(owner, 'res.company', 'write', [[companyId], { campus_ai_enabled: false }]);
        assert((await raw(owner, 'campus.ai.assistant', 'ask', ['Disabled request'])).error);
        assert.equal(calls.length, before + 1);
        checks.push('disabled assistant makes no provider request');
        assert.deepEqual(errors, []);
        await page.setViewportSize({ width: 390, height: 844 });
        await page.reload();
        await page.getByRole('heading', { name: 'Campus Assistant', exact: true }).waitFor();
        assert(await page.getByText('Switch the assistant on', { exact: true }).isVisible());
        await page.screenshot({ path: path.join(out, 'assistant-mobile-disabled.png') });
        await fs.writeFile(path.join(out, 'results.json'), JSON.stringify({ checks, pageErrors: errors, providerAttempts: calls.length }, null, 2));
        console.log(JSON.stringify({ passed: checks.length, pageErrors: errors }));
    } finally {
        await browser.close();
        await new Promise(resolve => server.close(resolve));
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
