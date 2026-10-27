const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function component(file, name, globals = {}) {
    const source = fs.readFileSync(path.join(__dirname, '../../../addons/ideastone_ai/static/src/js', file), 'utf8')
        .replace(/^import .*;$/gm, '').replace('export class ', 'class ');
    return vm.runInNewContext(source + '\n' + name, {
        Component: class {}, registry: { category: () => ({ add() {} }) }, ...globals,
    });
}
function deferred() {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}

test('rapid radar filter changes retain the latest response and ignore stale errors', async () => {
    const Radar = component('success_radar.js', 'SuccessRadarPage');
    const page = Object.create(Radar.prototype);
    const requests = [deferred(), deferred(), deferred()];
    let count = 0;
    page.orm = { call: () => requests[count++].promise };
    page.requestId = 0;
    page.state = { loading: false, error: '', departmentId: '1', batchId: '', band: '', query: '', open: 5 };
    const first = page.load();
    page.state.departmentId = '2';
    const second = page.load();
    requests[1].resolve({ rows: [{ id: 2 }] });
    await second;
    requests[0].resolve({ rows: [{ id: 1 }] });
    await first;
    assert.equal(page.state.data.rows[0].id, 2);
    assert.equal(page.state.open, null);
    assert.equal(page.state.loading, false);
    const third = page.load();
    requests[2].reject({ data: { message: 'Access denied' } });
    await third;
    assert.equal(page.state.error, 'Access denied');
});

test('feedback kind changes cannot install the previous kind\'s periods', async () => {
    const Assistant = component('assistant.js', 'CampusAssistantPage');
    const page = Object.create(Assistant.prototype);
    const requests = [deferred(), deferred()];
    let count = 0;
    page.orm = { call: () => requests[count++].promise };
    page.periodRequest = 0;
    page.state = { kind: 'student', period: 'Old period', periods: [], feedback: { summary: 'old' } };
    const first = page.changeKind({ target: { value: 'parent' } });
    const second = page.changeKind({ target: { value: 'staff' } });
    requests[1].resolve(['Staff term']);
    await second;
    requests[0].resolve(['Parent term']);
    await first;
    assert.equal(page.state.kind, 'staff');
    assert.equal(page.state.periods[0], 'Staff term');
    assert.equal(page.state.period, '');
    assert.equal(page.state.feedback, null);
    assert.equal(page.state.periodsLoading, false);
});

test('failed provider attempts refresh the visible usage count', async () => {
    const Assistant = component('assistant.js', 'CampusAssistantPage');
    const page = Object.create(Assistant.prototype);
    page.state = { status: { used: 0 } };
    page.notification = { add() {} };
    page.orm = { call: async () => ({ used: 1 }) };
    await page.fail({ data: { message: 'Timeout' } }, 'Failed');
    assert.equal(page.state.status.used, 1);
});

test('CSV quotes formula-like names and labels money with the college currency', async () => {
    let blob;
    const Radar = component('success_radar.js', 'SuccessRadarPage', {
        Blob, URL: { createObjectURL: value => { blob = value; return 'blob:test'; }, revokeObjectURL() {} },
        document: { createElement: () => ({ click() {} }) },
    });
    const page = Object.create(Radar.prototype);
    page.state = { data: { currency_code: 'USD', rows: [{
        name: '=HYPERLINK("https://example.test")', number: '+123', programme: '@example', batch: 'A',
        semester: 'I', mentor: 'Mentor', score: 0, band: 'low', attendance: { rate: 90 },
        academics: { average: 75 }, fees: { overdue: 10 }, factors: [], action: 'Review',
    }] } };
    page.exportCsv();
    const csv = await blob.text();
    assert(csv.includes("\"'=HYPERLINK"));
    assert(csv.includes("\"'+123\""));
    assert(csv.includes('Overdue fees (USD)'));
});
