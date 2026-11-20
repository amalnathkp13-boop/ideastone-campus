// Run with Node: exercise reference routes and live save ordering without an ERP database.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const sample = JSON.parse(fs.readFileSync(new URL('./sample_state.json', import.meta.url), 'utf8'));
const source = fs.readFileSync(new URL('./workspace.js', import.meta.url), 'utf8');
function element() {
    const children = new Map();
    return {innerHTML: '', textContent: '', hidden: false, className: '', open: false,
        focus() {}, showModal() { this.open = true; }, close() { this.open = false; },
        querySelector(key) { if (!children.has(key)) children.set(key, element()); return children.get(key); }};
}
const elements = new Map();
const document = {querySelector(key) { if (!elements.has(key)) elements.set(key, element()); return elements.get(key); },
    querySelectorAll() { return []; }, addEventListener() {},
    documentElement: {style: {setProperty() {}}}, activeElement: {matches() { return false; }}};
const location = {hash: '#dashboard', origin: 'http://localhost', reload() {}};
const requests = [];
const replies = [];
const events = new Map();
const messages = [];
const window = {LEARNING_STUDIO_BOOTSTRAP: {state: structuredClone(sample), revision: 0, csrfToken: 'test-token', student: {}},
    addEventListener(type, handler) { events.set(type, handler); }, scrollTo() {}, parent: {postMessage(message) { messages.push(message); }}};
const timers = new Set();
const context = vm.createContext({window, document, location, navigator: {onLine: true}, URLSearchParams, Date, console,
    setTimeout(fn, delay) { const timer = setTimeout(fn, delay); timers.add(timer); return timer; },
    clearTimeout(timer) { clearTimeout(timer); timers.delete(timer); },
    fetch(url, options) { requests.push({url, options}); return new Promise(resolve => replies.push(resolve)); }});
const instrumented = source.replace(/\}\)\(\);\s*$/, `globalThis.app={render,act,save,persist,getState:()=>state,getRevision:()=>revision,isDirty:()=>dirty,isConflicted:()=>conflicted};})();`);
vm.runInContext(instrumented, context);
const app = context.app;
assert.equal(messages.some(message => message.type === 'campus-lms-route'), false, 'Initial render must not overwrite the parent deep link');
await events.get('message')({source: window.parent, origin: location.origin, data: {type: 'campus-lms-navigate', route: 'dashboard'}});
assert.equal(messages.at(-1).type, 'campus-lms-route');
const routes = ['dashboard', 'courses', 'calendar', 'grades', 'tests', 'discussions', 'offline', 'files', 'explore'];
// Private-file listing has a separate API; skip its pending response during save checks.
for (const route of routes) {
    location.hash = '#' + route;
    app.render();
    assert.match(document.querySelector('#student_main').innerHTML, /<h1/);
}
assert.equal((document.querySelector('#nav').innerHTML.match(/lms-section-link/g) || []).length, 9);
assert.equal(requests[0].url, '/my/campus/student/lms/files');
replies.shift()({ok: true, json: async () => ({files: []})});
requests.length = 0;
for (const course of ['ds', 'db', 'dl', 'net']) {
    for (const route of [`course/${course}`, `grades/${course}`, `tests/${course}-fundamentals`, ...Array.from({length: 6}, (_, index) => `lesson/${course}/${index}`)]) {
        location.hash = '#' + route;
        app.render();
        assert.match(document.querySelector('#student_main').innerHTML, /<h1/);
    }
}
app.getState().notes['ds-0'] = 'First queued note';
app.save(true);
assert.equal(requests.length, 1);
assert.equal(requests[0].options.body.get('revision'), '0');
app.getState().notes['ds-0'] = 'Later queued note';
app.save(true);
const flushed = window.LEARNING_STUDIO_FLUSH();
assert.equal(requests.length, 1, 'Only one state save may be in flight');
replies.shift()({ok: true, status: 200, json: async () => ({state: JSON.parse(requests[0].options.body.get('state')), revision: 1})});
await new Promise(resolve => setImmediate(resolve));
assert.equal(requests.length, 2);
assert.equal(requests[1].options.body.get('revision'), '1');
assert.equal(JSON.parse(requests[1].options.body.get('state')).notes['ds-0'], 'Later queued note');
replies.shift()({ok: true, status: 200, json: async () => ({state: JSON.parse(requests[1].options.body.get('state')), revision: 2})});
await new Promise(resolve => setImmediate(resolve));
assert.equal(app.getRevision(), 2);
assert.equal(app.isDirty(), false);
assert.equal(await flushed, true, 'Leaving the portal waits for all queued changes');
app.getState().notes['ds-0'] = 'Conflicting note';
app.save(true);
replies.shift()({ok: false, status: 409, json: async () => ({error: 'Changed in another tab'})});
await new Promise(resolve => setImmediate(resolve));
assert.equal(app.isConflicted(), true);
assert.equal(app.isDirty(), true);
assert.equal(await window.LEARNING_STUDIO_FLUSH(), false, 'A conflict blocks navigation until resolved');
assert.equal(document.querySelector('#save-status').hidden, false);
assert.match(document.querySelector('#save-status').querySelector('span').textContent, /another tab/);
app.persist();
assert.equal(requests.length, 3, 'A revision conflict must not silently overwrite newer server state');
for (const timer of timers) clearTimeout(timer);
console.log('Passed: nine LMS sections, 36 detail routes, serialized saves, queued edits, and revision-conflict protection.');
