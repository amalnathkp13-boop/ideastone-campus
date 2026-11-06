const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function page(file, name, values = {}) {
    const source = fs.readFileSync(path.join(__dirname, '../../addons', file), 'utf8')
        .replace(/^import .*;$/gm, '').replace(/export class /g, 'class ');
    const stub = class {};
    const Type = vm.runInNewContext(source + '\n' + name, {
        Component: stub, Dialog: stub, OwnerStaffDirectory: stub, FacultyHome: stub,
        FacultyDepartments: stub, FacultyCommunication: stub, FacultyCampusServices: stub,
        OwnerSettings: stub, HodDashboard: stub, registry: {category: () => ({add() {}})},
    });
    return Object.assign(Object.create(Type.prototype), values);
}

test('every custom money formatter displays rupees for USD records without changing numbers', () => {
    const root = 'ideastone_erp/static/src/js/';
    const cases = [
        ['accountant_directory.js', 'AccountantDirectory', {state: {currency: '$'}}, 'money', '₹1,234.56'],
        ['accountant_spending.js', 'AccountantSpending', {state: {currency: '$'}}, 'money', '₹1,234.56'],
        ['owner_fees.js', 'OwnerFeesWorkspace', {state: {data: {symbol: '$'}}}, 'money', '₹ 1,234.56'],
        ['payroll_history.js', 'PayrollHistoryPage', {state: {currencySymbol: '₹', currencyPosition: 'before'}}, 'formatMoney', '₹ 1,235'],
    ];
    for (const [file, name, values, method, expected] of cases) {
        assert.equal(page(root + file, name, values)[method](1234.56), expected, file);
    }
    const principal = page('ideastone_principal/static/src/js/staff_workspace.js', 'PrincipalStaffWorkspace',
        {state: {data: {currency: '$'}}});
    assert.equal(principal.money(1234.56), '₹1,234.56');
    const decisions = page('ideastone_principal/static/src/js/workspace.js', 'PrincipalWorkspace',
        {state: {data: {rows: [{kind: 'event', currency: '$', budget: 1234.56}]}}});
    assert.equal(decisions.money(1234.56), '₹1,235');
    assert.equal(decisions.compactMoney(100000), '₹1.0L');
});

test('accountant charts retain original compact scales while replacing only the symbol', () => {
    const dashboard = page('ideastone_erp/static/src/js/dashboard.js', 'CampusDashboard', {
        state: {collectionRecords: {currency: '$'}, collectionOverview: {currency: '$'}, accountantMetrics: {currency: '$'}},
    });
    assert.equal(dashboard.collectionFullMoney(1234.56), '₹1,234.56');
    assert.equal(dashboard.collectionMoney(1000000), '₹1M');
    assert.equal(dashboard.accountantCompactMoney(-1200), '₹-1.2K');
    assert.equal(dashboard.accountantMoney(1234.56), '₹1,234.56');
    const transport = page('ideastone_erp/static/src/js/accountant_transport.js', 'AccountantTransport',
        {state: {data: {currency: '$'}}});
    assert.equal(transport.money(-1200, true), '-₹1.2K');
    assert.equal(dashboard.state.collectionOverview.currency, '$');
});

test('faculty payroll retains Intl rounding and compact parts for every source currency', () => {
    const faculty = page('ideastone_erp/static/src/js/faculty_profile_workspace.js', 'FacultyProfileWorkspace',
        {state: {data: {currency: 'USD'}}});
    for (const currency of ['USD', 'INR', 'EUR', 'JPY']) {
        faculty.state.data.currency = currency;
        for (const value of [0, -1234.56, 1000000]) {
            const expected = new Intl.NumberFormat('en-IN', {style: 'currency', currency,
                minimumFractionDigits: 0, maximumFractionDigits: 2}).formatToParts(value)
                .map(part => part.type === 'currency' ? '₹' : part.value).join('');
            assert.equal(faculty.money(value), expected);
            assert(!faculty.compactMoney(value).includes('$'));
        }
        assert.equal(faculty.state.data.currency, currency);
    }
});
