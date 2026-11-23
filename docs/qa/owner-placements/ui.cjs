// Run only against the disposable owner placements preview database.
// OWNER_PLACEMENTS_PREVIEW_PASSWORD is required; all created data stays in that preview.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

const base = process.env.OWNER_PLACEMENTS_PREVIEW_BASE || 'http://127.0.0.1:18111';
const db = process.env.OWNER_PLACEMENTS_PREVIEW_DB || 'owner_placements_preview';
const loginName = process.env.OWNER_PLACEMENTS_PREVIEW_LOGIN || 'owner.placements.preview';
const password = process.env.OWNER_PLACEMENTS_PREVIEW_PASSWORD;
const out = process.env.OWNER_PLACEMENTS_PREVIEW_OUT || path.join(os.tmpdir(), 'owner-placements-qa');
const tabs = [
    ['overview', 'Overview', 'Placement performance'],
    ['departments', 'Departments', 'Department placement records'],
    ['students', 'Students', 'Student placement register'],
    ['drives', 'Placement drives', 'Recruitment calendar'],
    ['offers', 'Offers & outcomes', 'Offers & joining register'],
    ['history', 'Past records', 'Placement records by graduating batch'],
    ['insights', 'AI insights', 'Placement improvement opportunities'],
];
if (!password) throw Error('Set OWNER_PLACEMENTS_PREVIEW_PASSWORD for the disposable preview.');

async function rpc(page, model, method, args = [], kwargs = {}) {
    const data = await page.evaluate(async ({model, method, args, kwargs}) => {
        const response = await fetch(`/web/dataset/call_kw/${model}/${method}`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {model, method, args, kwargs}}),
        });
        return response.json();
    }, {model, method, args, kwargs});
    if (data.error) throw Error(data.error.data?.message || data.error.message);
    return data.result;
}

async function login(page, name) {
    await page.goto(`${base}/web/login?db=${encodeURIComponent(db)}`, {waitUntil: 'domcontentloaded'});
    await page.locator('input[name=login]').fill(name);
    await page.locator('input[name=password]').fill(password);
    await Promise.all([
        page.waitForURL(url => !url.pathname.endsWith('/web/login'), {waitUntil: 'domcontentloaded', timeout: 90000}),
        page.locator('button[type=submit]').click(),
    ]);
    await page.locator('.o_main_navbar').waitFor({timeout: 90000});
}

async function downloaded(page, action, extension) {
    const [download] = await Promise.all([page.waitForEvent('download'), action()]);
    assert(download.suggestedFilename().endsWith(extension), `Expected ${extension} download`);
    assert.equal(await download.failure(), null);
    const contents = await fs.readFile(await download.path(), 'utf8');
    assert(contents.length > 20, 'Export is unexpectedly empty');
    return contents;
}

async function assertVerticalFill(page, width) {
    const bounds = await page.locator('.owner_placements_action iframe').evaluate(frame => {
        const rect = frame.getBoundingClientRect();
        const header = document.querySelector('.o_main_navbar').getBoundingClientRect();
        const subnav = document.querySelector('.campus_faculty_subnav');
        const navRect = subnav?.getBoundingClientRect();
        return {top: rect.top, bottom: rect.bottom, headerBottom: navRect?.height ? navRect.bottom : header.bottom, viewport: innerHeight};
    });
    assert(Math.abs(bounds.bottom - bounds.viewport) <= 1, `Bottom gap at ${width}: ${JSON.stringify(bounds)}`);
    assert(Math.abs(bounds.top - bounds.headerBottom) <= 1, `Header gap at ${width}: ${JSON.stringify(bounds)}`);
}

function nativeTab(page, id) {
    return page.locator('.campus_faculty_subnav').getByRole('button', {name: tabs.find(tab => tab[0] === id)[1], exact: true});
}

async function waitSection(page, frame, id) {
    const tab = tabs.find(tab => tab[0] === id);
    await nativeTab(page, id).and(page.locator('button.active')).waitFor();
    await frame.getByRole('region', {name: 'Campus placements · ' + tab[1], exact: true}).waitFor();
    await frame.getByRole('heading', {name: tab[2], exact: true}).waitFor();
}

async function checkNativeNavigation(page, frame) {
    const select = async id => {await nativeTab(page, id).click(); await waitSection(page, frame, id);};
    const marker = 'navigation-' + Date.now();
    await frame.locator('body').evaluate((body, value) => {body.dataset.qaNavigation = value;}, marker);
    await frame.locator('#year').selectOption('2026');
    const department = await frame.locator('#department option').nth(1).getAttribute('value');
    await frame.locator('#department').selectOption(department);
    await page.waitForFunction(dept => {
        const hash = new URLSearchParams(location.hash.slice(1));
        return hash.get('placements_year') === '2026' && hash.get('placements_department') === dept;
    }, department);
    for (const [id] of tabs) {
        await select(id);
        assert.equal(await frame.locator('#year').inputValue(), '2026');
        assert.equal(await frame.locator('#department').inputValue(), department);
        assert.equal(await frame.locator('body').getAttribute('data-qa-navigation'), marker, `Iframe reloaded on ${id}`);
    }
    await select('overview');
    await frame.getByRole('button', {name: /Yet to be placed/}).click();
    await waitSection(page, frame, 'students');
    assert.equal(await frame.getByLabel('Placement status', {exact: true}).inputValue(), 'Unplaced');
    await frame.getByLabel('Search students', {exact: true}).fill('Aarav');
    await nativeTab(page, 'students').click();
    assert.equal(await frame.getByLabel('Placement status', {exact: true}).inputValue(), 'Unplaced');
    assert.equal(await frame.getByLabel('Search students', {exact: true}).inputValue(), 'Aarav');
    assert.equal(await frame.locator('body').getAttribute('data-qa-navigation'), marker);
    await select('departments');
    await page.waitForFunction(() => new URLSearchParams(location.hash.slice(1)).get('placements_screen') === 'departments');
    await select('drives');
    await page.waitForFunction(() => new URLSearchParams(location.hash.slice(1)).get('placements_screen') === 'drives');
    await page.goBack(); await waitSection(page, frame, 'departments');
    await page.goForward(); await waitSection(page, frame, 'drives');
    await page.reload(); await waitSection(page, frame, 'drives');
    assert.equal(await frame.locator('#year').inputValue(), '2026');
    assert.equal(await frame.locator('#department').inputValue(), department);
    const placementLink = page.url();
    const barStyle = () => page.locator('.campus_faculty_subnav').evaluate(nav => {
        const r = nav.getBoundingClientRect(), css = getComputedStyle(nav);
        const button = getComputedStyle(nav.querySelector('button.active'));
        return {top: r.top, bottom: r.bottom, height: r.height, left: r.left, background: css.backgroundColor,
            font: css.fontFamily, fontSize: css.fontSize, border: css.borderBottomColor,
            buttonFont: button.fontFamily, buttonSize: button.fontSize, buttonWeight: button.fontWeight};
    });
    const placementsStyle = await barStyle();
    await page.locator('.campus_sidebar').getByRole('button', {name: 'Students', exact: true}).click();
    await page.locator('.campus_students_workspace').waitFor();
    const studentsStyle = await barStyle();
    assert.deepEqual(placementsStyle, studentsStyle, 'Placement bar differs from existing Students bar');
    await page.goto(placementLink); await waitSection(page, frame, 'drives');
    await frame.locator('#year').selectOption('2027');
    await frame.locator('#department').selectOption('All');
    await select('overview');
    for (const width of [320, 768, 1440]) {
        await page.setViewportSize({width, height: 900});
        await assertVerticalFill(page, width);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        if (width < 1024) {
            const before = await page.locator('.campus_faculty_subnav > div').evaluate(strip => strip.scrollLeft);
            await page.getByRole('button', {name: 'Next submodules', exact: true}).click();
            await page.waitForFunction(previous => document.querySelector('.campus_faculty_subnav > div').scrollLeft > previous, before);
        }
        await select('insights');
        await page.getByRole('button', {name: 'Customize top navigation', exact: true}).click();
        await page.locator('.campus_nav_dialog.is-top-navigation').waitFor();
        await page.screenshot({path: path.join(out, `native-customization-${width}.png`)});
        await page.keyboard.press('Escape');
        await page.locator('.campus_nav_dialog').waitFor({state: 'hidden'});
        await select('overview');
        await page.screenshot({path: path.join(out, `native-overview-${width}.png`)});
    }
    const result = {ok: true, checks: ['Seven native tabs without iframe reload', 'Year and department scope preserved',
        'Inner Unplaced drill-down updates native highlight', 'Active-tab click preserves student search and status',
        'Back/Forward/reload and saved link', 'Native bar matches existing Students placement and typography',
        'Mobile tab scrolling, customization and vertical fill at320/768/1440'], placementsStyle, studentsStyle};
    await fs.writeFile(path.join(out, 'native-navigation-verification.json'), JSON.stringify(result, null, 2));
    return result;
}

(async () => {
    await fs.mkdir(out, {recursive: true});
    const browser = await chromium.launch({headless: true});
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, timezoneId: 'Asia/Kolkata', reducedMotion: 'reduce'});
    const page = await context.newPage();
    page.setDefaultTimeout(45000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const checked = [];
    let frame, savedDriveLink;
    const selectTab = async id => {
        await nativeTab(page, id).click();
        await waitSection(page, frame, id);
    };
    const closeDialog = async () => {
        await frame.getByRole('button', {name: 'Close details', exact: true}).click();
        await frame.locator('#dialog[open]').waitFor({state: 'hidden'});
    };
    try {
        await login(page, loginName);
        await page.goto(`${base}/web#action=ideastone_erp.action_dashboard`);
        await page.locator('.campus_sidebar').getByRole('button', {name: /^Campus placements$/i}).waitFor();
        const overview = await rpc(page, 'campus.dashboard', 'get_overview');
        const module = overview.faculty_modules.find(item => /^Campus placements$/i.test(item.label));
        assert(module, 'Owner shell has no Campus Placements module');
        assert.deepEqual(module.items.map(item => item.label), tabs.map(item => item[1]));
        await page.locator('.campus_sidebar').getByRole('button', {name: /^Campus placements$/i}).click();
        await page.locator('.owner_placements_action iframe').waitFor();
        frame = page.frameLocator('.owner_placements_action iframe');
        await waitSection(page, frame, 'overview');
        assert.equal(await frame.locator('#tabs').isVisible(), false, 'Embedded tabs duplicate the owner bar');
        assert.equal(await frame.locator('.sidebar,.topbar').count(), 0, 'Reference shell duplicates ERP navigation');
        assert.equal(await page.locator('.o_main_navbar:visible').count(), 1);
        assert.equal(await page.locator('.campus_faculty_subnav:visible').count(), 1);
        for (const [id] of tabs) assert.equal(await nativeTab(page, id).count(), 1);
        assert.equal(await frame.locator('.kpi').count(), 6);
        const style = await frame.locator('body').evaluate(body => {
            const css = getComputedStyle(body);
            return {color: css.color, background: css.backgroundColor, font: css.fontFamily};
        });
        assert.equal(style.color, 'rgb(19, 42, 68)');
        assert.equal(style.background, 'rgb(244, 247, 251)');
        assert.match(style.font, /Inter/);
        const iframeURL = await page.locator('.owner_placements_action iframe').getAttribute('src');
        assert.equal(new URL(iframeURL, base).origin, new URL(base).origin);
        checked.push('Original owner shell, seven tabs, reference colors and fonts');
        if (process.env.OWNER_PLACEMENTS_NAVIGATION_ONLY === '1') {
            const result = await checkNativeNavigation(page, frame);
            assert.deepEqual(errors, []);
            console.log(JSON.stringify({...result, out}, null, 2));
            return;
        }
        const scrollBefore = await frame.locator('body').evaluate(body => body.ownerDocument.scrollingElement.scrollTop);
        await frame.locator('.kpi').first().hover();
        await page.mouse.wheel(0, 600);
        const wheelScrolled = await frame.locator('body').evaluate((body, before) => new Promise(resolve => {
            const started = performance.now();
            const check = () => {
                if (body.ownerDocument.scrollingElement.scrollTop > before + 20) return resolve(true);
                if (performance.now() - started > 2000) return resolve(false);
                requestAnimationFrame(check);
            };
            check();
        }), scrollBefore);
        assert(wheelScrolled, 'Mouse wheel does not scroll the placement iframe');
        await frame.locator('body').evaluate(body => body.ownerDocument.defaultView.scrollTo(0, 0));
        checked.push('Mouse wheel scrolls the main page inside the iframe');

        for (const [id] of tabs) {
            await selectTab(id);
            assert.equal(await frame.locator('#content').getAttribute('aria-label'), 'Campus placements · ' + tabs.find(tab => tab[0] === id)[1]);
            await page.screenshot({path: path.join(out, `${id}-1440.png`)});
        }
        checked.push('All seven sections render and activate correctly');
        await selectTab('students');
        await page.waitForFunction(() => new URLSearchParams(location.hash.slice(1)).get('placements_screen') === 'students');
        await selectTab('drives');
        await page.waitForFunction(() => new URLSearchParams(location.hash.slice(1)).get('placements_screen') === 'drives');
        const driveLink = page.url();
        savedDriveLink = driveLink;
        await page.goBack();
        await waitSection(page, frame, 'students');
        await page.goForward();
        await waitSection(page, frame, 'drives');
        await page.goto(`${base}/web#action=ideastone_erp.action_dashboard`);
        await page.locator('.owner_placements_action').waitFor({state: 'hidden'});
        await page.goto(driveLink);
        await waitSection(page, frame, 'drives');
        checked.push('Browser Back/Forward and a direct saved tab link restore the correct section');
        await selectTab('departments');
        await frame.locator('.dept-name').first().click();
        await frame.locator('#dialog[open]').waitFor();
        await frame.getByRole('button', {name: 'View unplaced students', exact: true}).click();
        await waitSection(page, frame, 'students');
        assert.notEqual(await frame.locator('#department').inputValue(), 'All');
        assert.equal(await frame.getByLabel('Placement status', {exact: true}).inputValue(), 'Unplaced');
        assert.equal(await frame.locator('#dialog[open]').count(), 0);
        await frame.locator('#department').selectOption('All');
        await frame.getByLabel('Placement status', {exact: true}).selectOption('All');
        const firstStudent = (await frame.locator('#content tbody tr td button').first().innerText()).trim();
        await frame.getByLabel('Search students', {exact: true}).fill(firstStudent);
        const searchRows = await frame.locator('#content tbody tr').allTextContents();
        assert(searchRows.length && searchRows.every(text => text.includes(firstStudent)), 'Search leaked unrelated students');
        await frame.locator('#content tbody tr td button').first().click();
        await frame.locator('#dialog[open]').waitFor();
        assert((await frame.locator('#modal-title').innerText()).includes(firstStudent));
        await closeDialog();
        await frame.getByLabel('Search students', {exact: true}).fill('');
        const csv = await downloaded(page, () => frame.locator('#exportBtn').click(), '.csv');
        assert.match(csv, /Student|Register|Name/i);
        checked.push('Department drill-down, student search/details, and CSV download');

        await selectTab('drives');
        await frame.getByRole('button', {name: 'View drive & eligible students →', exact: true}).first().click();
        await frame.locator('#dialog[open]').waitFor();
        const calendar = await downloaded(page, () => frame.getByRole('button', {name: 'Download calendar event', exact: true}).click(), '.ics');
        assert.match(calendar, /BEGIN:VEVENT/);
        assert.match(calendar, /DTSTART/);
        assert.match(calendar, /DTEND/);
        await frame.getByRole('button', {name: /^View eligible students/}).click();
        await frame.getByRole('heading', {name: /Eligible student shortlist/}).waitFor();
        await downloaded(page, () => frame.getByRole('button', {name: /Export shortlist CSV/}).click(), '.csv');
        await closeDialog();
        checked.push('Drive details, eligibility shortlist, calendar and shortlist exports');

        const company = `Preview QA ${Date.now()}`;
        await frame.getByRole('button', {name: /Add placement drive/}).click();
        const date = new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10);
        const later = new Date(Date.now() + 15 * 86400000).toISOString().slice(0, 10);
        await frame.locator('#drive-form [name=company]').fill(company);
        await frame.locator('#drive-form [name=role]').fill('Graduate engineer');
        await frame.locator('#drive-form [name=date]').fill(date);
        await frame.locator('#drive-form [name=deadline]').fill(later);
        await frame.locator('#drive-form [name=salary]').fill('8.5');
        await frame.locator('#drive-form [name=cgpa]').fill('6.5');
        await frame.locator('#drive-form [name=location]').fill('Preview campus');
        await frame.locator('#drive-form [name=coordinator]').fill('Preview placement office');
        await frame.getByRole('button', {name: 'Save drive', exact: true}).click();
        assert.match(await frame.locator('#form-error').innerText(), /deadline.*before.*drive date/i);
        await frame.locator('#drive-form [name=deadline]').fill(date);
        await frame.getByRole('button', {name: 'Save drive', exact: true}).click();
        await frame.getByRole('heading', {name: company, exact: true}).waitFor();
        await page.reload();
        await waitSection(page, frame, 'drives');
        await frame.getByRole('heading', {name: company, exact: true}).waitFor();
        checked.push('Drive validation and saved data survive a full reload');

        await selectTab('insights');
        await frame.getByRole('button', {name: 'Review & create plan →', exact: true}).first().click();
        await frame.locator('#dialog[open]').waitFor();
        const planTitle = await frame.locator('#modal-title').innerText();
        await frame.getByRole('button', {name: 'View affected students', exact: true}).click();
        await frame.getByRole('heading', {name: 'Students requiring follow-up', exact: true}).waitFor();
        await closeDialog();
        await frame.getByRole('button', {name: 'Review & create plan →', exact: true}).first().click();
        await frame.getByRole('button', {name: 'Save improvement plan', exact: true}).click();
        // Repeated runs may use the existing idempotent plan, leaving the dialog open.
        if (await frame.locator('#dialog[open]').count()) await closeDialog();
        await frame.locator('.plan').filter({hasText: planTitle}).waitFor();
        await page.reload();
        await waitSection(page, frame, 'insights');
        assert.equal(await frame.locator('.plan').filter({hasText: planTitle}).count(), 1);
        checked.push('Rule-based insight drill-down and persisted, non-duplicated plan');

        for (const width of [320, 390, 768, 1440]) {
            await page.setViewportSize({width, height: 900});
            await assertVerticalFill(page, width);
            for (const [id] of tabs) {
                await selectTab(id);
                assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `ERP overflow at ${width}/${id}`);
                assert(await frame.locator('html').evaluate(el => el.scrollWidth <= innerWidth + 1), `Module overflow at ${width}/${id}`);
                const clipped = await frame.locator('.head button,.filters select,.kpi,.grid-main>.panel,.cards>.panel,.summary-strip>.mini-stat,.donut-row,.detail-grid').evaluateAll(nodes => nodes.filter(node => {
                    const rect = node.getBoundingClientRect();
                    return rect.width && (rect.left < -1 || rect.right > innerWidth + 1);
                }).map(node => node.className || node.tagName));
                assert.deepEqual(clipped, [], `Content clipped horizontally at ${width}/${id}`);
            }
            await selectTab('overview');
            await page.screenshot({path: path.join(out, `overview-${width}.png`)});
            await selectTab('students');
            await frame.locator('#content tbody tr td button').first().click();
            const fits = await frame.locator('#dialog').evaluate(el => {
                const r = el.getBoundingClientRect();
                return r.left >= -1 && r.right <= innerWidth + 1 && r.top >= -1 && r.bottom <= innerHeight + 1;
            });
            assert(fits, `Student dialog exceeds viewport at ${width}`);
            await page.screenshot({path: path.join(out, `student-dialog-${width}.png`)});
            await closeDialog();
        }
        checked.push('Seven sections and modal fit 320, 390, 768 and 1440 pixel widths');

        await selectTab('history');
        await frame.locator('body').evaluate(body => {
            body.ownerDocument.defaultView.print = () => {body.dataset.printRequested = 'yes';};
        });
        await frame.getByRole('button', {name: 'Print report', exact: true}).click();
        assert.equal(await frame.locator('body').getAttribute('data-print-requested'), 'yes');
        await frame.getByRole('button', {name: 'Definitions & references', exact: true}).click();
        await frame.getByRole('heading', {name: 'Module notes & reference sources', exact: true}).waitFor();
        await frame.getByRole('button', {name: 'View metric definitions', exact: true}).click();
        await frame.locator('#dialog[open]').waitFor();
        assert.match(await frame.locator('#modal-body').innerText(), /eligible|willing/i);
        await closeDialog();
        checked.push('Print dispatch and definitions/reference help dialogs');
        if (await frame.locator('#reset-preview').isVisible()) {
            await frame.locator('#reset-preview').click();
            await frame.getByRole('heading', {name: 'Reset preview changes', exact: true}).waitFor();
            await frame.getByRole('button', {name: 'Reset preview changes', exact: true}).click();
            await frame.locator('#dialog[open]').waitFor({state: 'hidden'});
            await selectTab('drives');
            assert.equal(await frame.getByRole('heading', {name: company, exact: true}).count(), 0);
            assert(await frame.locator('.drive-card').count() > 0, 'Reset removed seeded drives');
            checked.push('Reset removes preview additions while keeping seeded drives');
        }

        // A separate cookie-free client must never receive the authenticated page.
        const anonymous = await browser.newContext();
        const response = await anonymous.request.get(new URL(iframeURL, base).href, {maxRedirects: 0});
        assert([302, 303, 401, 403].includes(response.status()), `Anonymous module route returned ${response.status()}`);
        await anonymous.close();
        if (process.env.OWNER_PLACEMENTS_NONOWNER_LOGIN) {
            const otherContext = await browser.newContext();
            const other = await otherContext.newPage();
            await login(other, process.env.OWNER_PLACEMENTS_NONOWNER_LOGIN);
            await assert.rejects(rpc(other, 'campus.owner.placements.ui', 'get_data'), /access|owner|permission|allowed/i);
            const denied = await other.request.get(new URL(iframeURL, base).href, {maxRedirects: 0});
            assert([302, 303, 401, 403].includes(denied.status()), `Non-owner module route returned ${denied.status()}`);
            await otherContext.close();
            checked.push('Non-owner route and RPC deny access');
        }
        checked.push('Anonymous route denies access');
        assert.deepEqual(errors, [], 'Uncaught browser errors');
        await fs.writeFile(path.join(out, 'verification.json'), JSON.stringify({ok: true, checked}, null, 2));
        console.log(JSON.stringify({ok: true, checked, out}, null, 2));
    } catch (error) {
        await page.screenshot({path: path.join(out, 'failure.png')}).catch(() => {});
        const frameSrc = await page.locator('.owner_placements_action iframe').getAttribute('src', {timeout: 1000}).catch(() => null);
        await fs.writeFile(path.join(out, 'verification.json'), JSON.stringify({ok: false, checked, error: error.message,
            errors, currentURL: page.url(), savedDriveLink, frameSrc}, null, 2));
        throw error;
    } finally {
        await browser.close();
    }
})().catch(error => {console.error(error); process.exitCode = 1;});
