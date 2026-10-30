const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../../addons/ideastone_erp/static/src/js/staff_od_management.js'), 'utf8')
    .replace(/^import .*;$/gm, '').replace(/export class /g, 'class ');
const Workspace = vm.runInNewContext(source + '\nStaffODManagement', {
    Component: class {}, Dialog: class {}, registry: { category: () => ({ add() {} }) },
});
function workspace() {
    const page = Object.create(Workspace.prototype);
    page.state = { search: '', page: 1, selectedId: 1, classKey: 'A', note: 'For A' };
    page.notification = { add() {} };
    return page;
}
function deferred() {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}
test('late class responses cannot replace the current class and current errors remain visible', async () => {
    const page = workspace();
    const requests = [deferred(), deferred(), deferred()];
    let index = 0;
    page.orm = { call: () => requests[index++].promise };
    const first = page.load();
    const second = page.changeClass({ target: { value: 'B' } });
    assert.equal(page.state.note, '');
    requests[1].resolve({ class_key: 'B', rows: [{ id: 2, can_review: true }] });
    await second;
    requests[0].resolve({ class_key: 'A', rows: [{ id: 1, can_review: true }] });
    await first;
    assert.equal(page.state.data.class_key, 'B');
    assert.equal(page.state.selectedId, 2);
    const third = page.load();
    requests[2].reject({ data: { message: 'Access denied' } });
    await third;
    assert.equal(page.state.error, 'Access denied');
    assert.equal(page.state.loading, false);
});
test('selecting another request clears the previous student note; return requires a note', async () => {
    const page = workspace();
    let calls = 0;
    page.orm = { call: async () => calls++ };
    page.selectRow({ id: 2 });
    assert.equal(page.state.note, '');
    await page.review({ id: 2, can_review: true }, 'return');
    assert.equal(calls, 0);
    page.state.note = 'Private note for 2';
    await page.review({ id: 3, can_review: true }, 'forward');
    assert.equal(calls, 0);
    assert.equal(page.state.note, '');
});
test('pending dates use the server local day and keep all requests accessible', () => {
    const page = workspace();
    page.state.data = { today: '2026-10-28', rows: [
        { id: 3, can_review: true, date_from: '2026-10-29' },
        { id: 1, can_review: true, date_from: '2026-10-27' },
        { id: 2, can_review: true, date_from: '2026-10-28' },
        { id: 4, can_review: false, date_from: '2026-10-28' },
        { id: 5, can_review: true, date_from: '2026-10-30' },
        { id: 6, can_review: true, date_from: '2026-11-02' },
    ] };
    assert.equal(page.pendingActions.length, 4);
    assert.equal(page.pendingActions[0].id, 1);
    assert.equal(page.dueStatus(page.pendingRows[0]).label, 'Event passed');
    assert.equal(page.dueStatus(page.pendingRows[1]).label, 'Due today');
    assert.equal(page.dueStatus(page.pendingRows[2]).label, 'Due tomorrow');
    page.state.pendingAll = true;
    assert.equal(page.pendingActions.length, 5);
    assert.equal(page.dueStatus(page.pendingRows[4]).label, 'Upcoming');
});
