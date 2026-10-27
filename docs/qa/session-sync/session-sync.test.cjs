const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../../addons/ideastone_erp/static/src/js/session_sync.js'), 'utf8')
    .replace(/^import .*;$/gm, '').replace('export const campusSessionService', 'const campusSessionService');

function start(rpc, session = { uid: 26, db: 'campus' }) {
    const window = new EventTarget();
    const document = new EventTarget();
    const bus = new EventTarget();
    const redirects = [];
    const stored = new Map();
    window.location = { pathname: '/web', replace: url => redirects.push(url) };
    window.localStorage = { setItem: (key, value) => stored.set(key, value) };
    document.hidden = false;
    const context = vm.createContext({ window, document, session,
        registry: { category: () => ({ add: () => {} }) } });
    const service = vm.runInContext(source + '\ncampusSessionService;', context);
    const guard = service.start({ bus }, { rpc, user: { userId: session.uid } });
    return { window, document, bus, guard, redirects, stored };
}

test('module navigation under the same login keeps the current screen', async () => {
    const app = start(async () => ({ uid: 26, db: 'campus', is_internal_user: true }));
    await app.guard.check();
    assert.deepEqual(app.redirects, []);
});

for (const [name, current, target] of [
    ['staff to student', { uid: 32, db: 'campus', is_internal_user: false }, '/my/campus'],
    ['student to staff', { uid: 27, db: 'campus', is_internal_user: true }, '/web'],
    ['database switch with same numeric user ID', { uid: 26, db: 'other', is_internal_user: true }, '/web'],
]) {
    test(name + ' drops the previous action and company context', async () => {
        const app = start(async () => current);
        await app.guard.check();
        await app.guard.check();
        assert.deepEqual(app.redirects, [target]);
    });
}

test('logout redirects to sign in; connection failures keep the valid screen', async () => {
    const expired = start(async () => { throw { code: 100 }; });
    await expired.guard.check();
    assert.deepEqual(expired.redirects, ['/web/login']);
    const offline = start(async () => { throw new Error('connection lost'); });
    await offline.guard.check();
    assert.deepEqual(offline.redirects, []);
});

test('focus, restored pages and failed module requests share one pending identity check', async () => {
    let finish;
    let calls = 0;
    const app = start(() => { calls++; return new Promise(resolve => { finish = resolve; }); });
    app.window.dispatchEvent(new Event('focus'));
    app.window.dispatchEvent(Object.assign(new Event('pageshow'), { persisted: true }));
    app.document.dispatchEvent(new Event('visibilitychange'));
    app.bus.dispatchEvent(Object.assign(new Event('RPC:RESPONSE'), {
        detail: { error: new Error('access'), data: { params: { model: 'campus.dashboard' } } },
    }));
    assert.equal(calls, 1);
    finish({ uid: 26, db: 'campus' });
    await app.guard.check();
    assert.deepEqual(app.redirects, []);
});

test('cross-tab hints are verified by the server and never trusted as a login', async () => {
    let calls = 0;
    const app = start(async () => { calls++; return { uid: 26, db: 'campus' }; });
    app.window.dispatchEvent(Object.assign(new Event('storage'), {
        key: 'ideastone.campus.session', newValue: '999',
    }));
    await app.guard.check();
    assert.equal(calls, 1);
    assert.deepEqual(app.redirects, []);
});
