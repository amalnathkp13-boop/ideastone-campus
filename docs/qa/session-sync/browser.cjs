const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const playwright = require('playwright');

const base = process.env.SESSION_QA_BASE || 'http://127.0.0.1:18069';
assert(['localhost', '127.0.0.1'].includes(new URL(base).hostname), 'Local QA only');
const password = process.env.SESSION_QA_PASSWORD;
const staff = [process.env.SESSION_QA_BACKEND_LOGIN || 'owner.ui.qa', process.env.SESSION_QA_BACKEND_PASSWORD || password];
const portal = [process.env.SESSION_QA_PORTAL_LOGIN || 'parent.ui.qa', process.env.SESSION_QA_PORTAL_PASSWORD || password];
const other = [process.env.SESSION_QA_OTHER_LOGIN || 'parent.other.qa', process.env.SESSION_QA_OTHER_PASSWORD || password];
assert(staff[1] && portal[1] && other[1], 'Runtime QA passwords required');
const out = process.env.SESSION_QA_OUT || path.join(process.env.PARENT_QA_OUT, 'session-sync');
const engine = process.env.SESSION_QA_ENGINE || 'chromium';

(async () => {
    await fs.mkdir(out, { recursive: true });
    const browser = await playwright[engine].launch({ headless: true, channel: process.env.SESSION_QA_CHANNEL });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const first = await context.newPage();
    const second = await context.newPage();
    const errors = [];
    const results = [];
    for (const page of [first, second]) page.on('pageerror', error => errors.push(error.message));
    async function authenticate(account) {
        const response = await context.request.post(base + '/web/session/authenticate', { data: {
            jsonrpc: '2.0', params: { db: process.env.SESSION_QA_DB || 'ci', login: account[0], password: account[1] },
        } });
        const data = await response.json();
        assert(data.result?.uid, 'QA login failed');
        return data.result.uid;
    }
    async function expectUser(page, uid) {
        await page.waitForFunction(uid => {
            const match = [...document.scripts].map(script => script.textContent)
                .join('\n').match(/odoo\.__session_info__\s*=\s*(\{.*?\});/s);
            if (!match) return false;
            const info = JSON.parse(match[1]);
            return (info.uid || info.user_id) === uid;
        }, uid, { timeout: 20000 });
        assert.equal(await page.getByText('Campus data could not be loaded. Check your access or retry.', { exact: true }).count(), 0);
    }
    try {
        const staffUid = await authenticate(staff);
        await first.goto(base + '/web#action=ideastone_erp.action_dashboard');
        await first.locator('.campus_sidebar').waitFor();
        for (const label of ['My task list', 'Search', 'Home']) {
            const button = first.locator('.campus_sidebar').getByRole('button', { name: label, exact: true });
            if (await button.count()) await button.click();
        }
        await expectUser(first, staffUid);
        results.push('same-account module navigation');

        const portalUid = await authenticate(portal);
        await second.goto(base + '/my/campus');
        await first.waitForURL(base + '/my/campus');
        await expectUser(first, portalUid);
        results.push('background staff tab follows portal sign-in');

        const otherUid = await authenticate(other);
        await second.goto(base + '/my/campus');
        await expectUser(first, otherUid);
        results.push('portal identity refreshes even when URL is unchanged');

        await authenticate(staff);
        await second.goto(base + '/web');
        await first.waitForURL(base + '/web');
        await expectUser(first, staffUid);
        results.push('portal tab follows staff sign-in without old action hash');

        await context.request.get(base + '/web/session/logout?redirect=/web/login');
        await second.goto(base + '/web/login');
        await first.waitForURL(base + '/web/login');
        await first.locator('input[name=login]').waitFor();
        results.push('logout clears stale authenticated tabs');

        await authenticate(staff);
        await first.goto(base + '/web#action=ideastone_erp.action_dashboard');
        await first.locator('.campus_sidebar').waitFor();
        await authenticate(portal);
        await first.evaluate(() => window.dispatchEvent(new Event('focus')));
        await first.waitForURL(base + '/my/campus');
        await expectUser(first, portalUid);
        results.push('focus detects changed cookie without a storage announcement');
        await first.screenshot({ path: path.join(out, engine + '-session-restored.png') });
        assert.deepEqual(errors, []);
        await fs.writeFile(path.join(out, engine + '-results.json'), JSON.stringify({ engine, results, errors }, null, 2));
        console.log(JSON.stringify({ engine, passed: results.length, errors }));
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
