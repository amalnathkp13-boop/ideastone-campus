'use strict';

// The standalone preview uses sample values; the Odoo action always loads live data.
const preview = new URLSearchParams(window.location.search).get('preview') === '1';
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[character]);

const initialHistory = [
    {type: 'Permission', date: '25/09/2026 (FN)', days: 0.5, reason: 'going to function', status: 'Approved'},
    {type: 'General On Duty', date: '19/09/2026 (Full Day)', days: 1, reason: 'going to attend meeting', status: 'Approved'},
    {type: 'Compensatory Leave', date: '11/09/2026 (Full Day)', days: 1, reason: 'going to function', status: 'Approved'},
    {type: 'Casual Leave', date: '29/08/2026 (Full Day)', days: 1, reason: 'going to native', status: 'Approved'},
    {type: 'Permission', date: '28/08/2026 (AN)', days: 0.5, reason: 'going to coordinator meeting', status: 'Approved'},
];
let history = preview ? [...initialHistory] : [];
let liveData = null;
let toastTimeout;

function toast(message) {
    const element = $('toast');
    element.textContent = message;
    element.classList.add('visible');
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => element.classList.remove('visible'), 4000);
}

function modal(title, body) {
    $('modalTitle').textContent = title;
    $('modalContent').innerHTML = body;
    $('modalBackdrop').classList.add('open');
    $('modalBackdrop').setAttribute('aria-hidden', 'false');
    $('closeModal').focus();
}

function closeModal() {
    $('modalBackdrop').classList.remove('open');
    $('modalBackdrop').setAttribute('aria-hidden', 'true');
}

function parseDate(text) {
    const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text.trim());
    if (!match) return null;
    const value = new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1]));
    return value.getFullYear() === Number(match[3]) && value.getMonth() === Number(match[2]) - 1
        && value.getDate() === Number(match[1]) ? value : null;
}

function formatDate(value) {
    const pad = (number) => String(number).padStart(2, '0');
    return `${pad(value.getDate())}/${pad(value.getMonth() + 1)}/${value.getFullYear()}`;
}

function isoDate(value) {
    const pad = (number) => String(number).padStart(2, '0');
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

function formatIso(value) {
    if (!value) return '';
    const parts = value.split('-');
    return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : value;
}

function dateLabel(record) {
    if (record.date) return record.date;
    if (!record.from) return '—';
    if (record.from !== record.to) return `${formatIso(record.from)} - ${formatIso(record.to)}`;
    if (record.days === 0.5) return `${formatIso(record.from)} (Half Day)`;
    return `${formatIso(record.from)} (Full Day)`;
}

function rangeDays(from, to, first, last) {
    let days = Math.round((to - from) / 86400000) + 1;
    if (first === 'AN') days -= 0.5;
    if (last === 'FN') days -= 0.5;
    return Math.max(0, days);
}

function renderHistory() {
    const rows = history.slice(0, 5);
    $('historyRows').innerHTML = rows.length ? rows.map((record, index) => `
        <tr><td title="${esc(record.type)}">${esc(record.type)}</td>
        <td>${esc(dateLabel(record))}</td><td>${esc(record.days)}</td>
        <td title="${esc(record.reason)}">${esc(record.reason)}</td>
        <td><span class="status-badge ${record.status === 'Pending' ? 'pending' : ''}">${esc(record.status)}</span></td>
        <td><button type="button" class="eye-btn" aria-label="View application ${index + 1}" data-history="${index}"><svg class="svg-icon"><use href="#ico-eye"/></svg></button></td></tr>`).join('')
        : '<tr><td colspan="6" class="empty-row">No leave requests recorded</td></tr>';
}

function renderAttendance(rows) {
    const tbody = document.querySelector('.attendance-table tbody');
    tbody.innerHTML = rows.length ? rows.map((row) => {
        const tag = (value) => `<span class="att-tag ${value === 'Present' ? 'present' : value === 'OD' ? 'od' : value === 'Leave Applied' ? 'leave' : ''}">${esc(value)}</span>`;
        return `<tr><td>${esc(formatIso(row.date))}</td><td>${esc(row.day)}</td><td>${tag(row.fn)}</td><td>${tag(row.an)}</td></tr>`;
    }).join('') : '<tr><td colspan="4" class="empty-row">No attendance entries recorded</td></tr>';
}

async function rpc(method, args = []) {
    const response = await fetch(`/web/dataset/call_kw/campus.faculty.leave.ui/${method}`, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({jsonrpc: '2.0', method: 'call', id: Date.now(),
            params: {model: 'campus.faculty.leave.ui', method, args, kwargs: {}}}),
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
        throw new Error(payload.error?.data?.message || payload.error?.message || 'The campus server could not complete this request.');
    }
    return payload.result;
}

function renderLive(data) {
    liveData = data;
    const balance = data.balance == null ? '—' : String(data.balance);
    $('leaveBalanceKpi').textContent = balance;
    $('leaveBalanceText').textContent = balance;
    document.querySelector('.kpi-grid .kpi:nth-child(2) .kpi-value').textContent =
        data.monthly_eligibility == null ? '—' : String(data.monthly_eligibility);
    document.querySelector('.kpi-grid .kpi:nth-child(3) .kpi-value').textContent = String(data.approved_count);
    $('pendingKpi').textContent = String(data.pending_count);
    document.querySelector('.side-foot > span:first-child').textContent = data.company_name;
    document.querySelector('.side-foot > span:nth-child(2)').textContent = data.role;
    const avatar = $('accountButton').querySelector('.avatar');
    avatar.textContent = (data.user_name || '?').trim().charAt(0).toUpperCase();
    $('accountMenu').querySelector('.menu-line').innerHTML = `${esc(data.user_name)}<br>${esc(data.role)}`;
    const notificationDot = $('notificationsButton').querySelector('.notify-dot');
    notificationDot.textContent = String(data.notification_count);
    notificationDot.hidden = !data.notification_count;
    $('notificationsButton').setAttribute('aria-label', `Notifications, ${data.notification_count} current`);
    $('notificationMenu').innerHTML = `<div class="menu-line">Notifications</div>${data.notifications.length
        ? data.notifications.map((item) => `<div class="menu-line">${esc(item)}</div>`).join('')
        : '<div class="menu-line">No current notifications</div>'}`;
    $('semesterMenu').querySelector('.menu-line').textContent = `VCET : ${data.academic_years[0]}`;
    $('academicYear').innerHTML = data.academic_years.map((year) =>
        `<option value="${esc(year)}">VCET : ${esc(year.replace('-', ' - '))}</option>`).join('');
    $('leaveType').innerHTML = data.leave_types.length ? data.leave_types.map((type) =>
        `<option value="${type.id}">${esc(type.name)}</option>`).join('') : '<option value="">No leave types available</option>';
    $('authority').innerHTML = `<option>${esc(data.reporting_authority)}</option>`;
    $('leaveForm').querySelector('[type=submit]').disabled = !data.can_apply;
    $('fromDate').value = formatIso(data.today);
    $('toDate').value = formatIso(data.today);
    history = data.history;
    renderHistory();
    renderAttendance(data.attendance);
    document.querySelector('.insight-items .insight:nth-child(1) strong').textContent =
        data.approval_percent == null ? '—' : `${data.approval_percent}%`;
    document.querySelector('.insight-items .insight:nth-child(2) strong').textContent = data.most_common_leave;
    document.querySelector('.insight-items .insight:nth-child(3) strong').textContent =
        data.balance == null ? '—' : `${data.balance} days`;
    document.querySelector('.insight-items .insight:nth-child(4) strong').textContent = 'Not configured';
    if (!data.can_apply) toast('A linked employee and an available leave type are required to apply.');
}

async function loadLive() {
    try {
        renderLive(await rpc('get_page_data'));
    } catch (error) {
        toast(error.message);
        document.querySelector('.form-content .primary-button').disabled = true;
        $('historyRows').innerHTML = '<tr><td colspan="6" class="empty-row">Leave data could not be loaded</td></tr>';
    }
}

function showHistoryDetails(record) {
    modal('Leave Application Details', `<dl class="detail-list">
        <dt>Leave Type</dt><dd>${esc(record.type)}</dd>
        <dt>Date</dt><dd>${esc(dateLabel(record))}</dd>
        <dt>Days</dt><dd>${esc(record.days)}</dd>
        <dt>Reason</dt><dd>${esc(record.reason)}</dd>
        <dt>Status</dt><dd><span class="status-badge ${record.status === 'Pending' ? 'pending' : ''}">${esc(record.status)}</span></dd>
        </dl>${preview ? '<p class="data-note">Sample data for visual review.</p>' : ''}`);
}

function resetForm() {
    setTimeout(() => {
        const date = preview ? '07/10/2026' : formatIso(liveData?.today || isoDate(new Date()));
        $('fromDate').value = date;
        $('toDate').value = date;
        $('fromSession').value = 'FN';
        $('toSession').value = 'AN';
        $('oneDay').checked = true;
        $('reason').value = '';
    }, 0);
}

function toggleMenu(menuId, button) {
    const target = $(menuId);
    const open = !target.classList.contains('open');
    document.querySelectorAll('.pop-menu.open').forEach((menu) => menu.classList.remove('open'));
    document.querySelectorAll('[aria-expanded]').forEach((item) => item.setAttribute('aria-expanded', 'false'));
    if (open) {
        target.classList.add('open');
        button.setAttribute('aria-expanded', 'true');
    }
}

function navigate(module) {
    if (module === 'Payroll') return;
    if (preview) {
        toast(`${module} is outside this leave-management preview.`);
    } else if (module === 'Sign out') {
        window.top.location.href = '/web/session/logout';
    } else {
        window.parent.postMessage({type: 'vcet-leave:navigate', module}, window.location.origin);
    }
}

$('closeModal').addEventListener('click', closeModal);
$('modalBackdrop').addEventListener('click', (event) => {
    if (event.target === $('modalBackdrop')) closeModal();
});
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeModal();
        document.querySelectorAll('.pop-menu.open').forEach((menu) => menu.classList.remove('open'));
    }
});
document.addEventListener('click', (event) => {
    if (!event.target.closest('.menu-wrap')) {
        document.querySelectorAll('.pop-menu.open').forEach((menu) => menu.classList.remove('open'));
        document.querySelectorAll('[aria-expanded]').forEach((button) => button.setAttribute('aria-expanded', 'false'));
    }
});

for (const [buttonId, menuId] of [
    ['semesterButton', 'semesterMenu'], ['notificationsButton', 'notificationMenu'], ['accountButton', 'accountMenu'],
]) {
    $(buttonId).addEventListener('click', () => toggleMenu(menuId, $(buttonId)));
}
document.querySelectorAll('[data-semester]').forEach((button) => button.addEventListener('click', () => {
    $('semesterMenu').classList.remove('open');
    $('semesterButton').querySelectorAll('span')[1].textContent = button.dataset.semester === 'Odd Semester' ? 'ODD' : 'EVEN';
}));
document.querySelectorAll('.side-menu [data-module], #accountMenu [data-module]').forEach((button) =>
    button.addEventListener('click', () => navigate(button.dataset.module)));
$('campusLink').setAttribute('href', '/my/campus');

$('historyRows').addEventListener('click', (event) => {
    const button = event.target.closest('[data-history]');
    if (button) showHistoryDetails(history[Number(button.dataset.history)]);
});
$('viewAll').addEventListener('click', () => modal('Leave Application History',
    `<div style="overflow-x:auto"><table class="small-table"><thead><tr><th>Leave Type</th><th>Date</th><th>Days</th><th>Reason</th><th>Status</th></tr></thead><tbody>${history.length
        ? history.map((record) => `<tr><td>${esc(record.type)}</td><td>${esc(dateLabel(record))}</td><td>${esc(record.days)}</td><td>${esc(record.reason)}</td><td>${esc(record.status)}</td></tr>`).join('')
        : '<tr><td colspan="5">No leave requests recorded</td></tr>'}</tbody></table></div>`));
$('viewAI').addEventListener('click', () => modal('AI Insights for Leave Management', `<dl class="detail-list">
    <dt>Approval Trend</dt><dd>${preview ? '100%' : liveData?.approval_percent == null ? '—' : `${liveData.approval_percent}%`}</dd>
    <dt>Most Common Leave</dt><dd>${esc(preview ? 'Casual Leave' : liveData?.most_common_leave || '—')}</dd>
    <dt>Leave Balance</dt><dd>${esc(preview ? '11 days' : liveData?.balance == null ? '—' : `${liveData.balance} days`)}</dd>
    <dt>Payroll Sync</dt><dd>${preview ? 'Sample status' : 'Not configured'}</dd></dl>`));
$('printHistory').addEventListener('click', () => window.print());
$('tabProcess').addEventListener('click', () => {
    $('tabProcess').classList.add('active');
    $('tabApproval').classList.remove('active');
});
$('tabApproval').addEventListener('click', () => modal('Online Leave Application Approval By HoD',
    '<p class="approval-demo">The HoD approval workflow remains a separate authorized screen.</p>'));

$('leaveForm').addEventListener('reset', resetForm);
$('fromDate').addEventListener('change', () => {
    if ($('oneDay').checked) $('toDate').value = $('fromDate').value;
});
$('oneDay').addEventListener('change', () => { $('toDate').value = $('fromDate').value; });

document.querySelectorAll('[data-date-target]').forEach((button) => button.addEventListener('click', () => {
    const field = $(button.dataset.dateTarget);
    const native = $(button.dataset.dateTarget === 'fromDate' ? 'nativeFrom' : 'nativeTo');
    const date = parseDate(field.value);
    native.value = date ? isoDate(date) : '';
    try { native.showPicker(); } catch { field.focus(); }
}));
$('nativeFrom').addEventListener('change', (event) => {
    if (event.target.value) {
        $('fromDate').value = formatIso(event.target.value);
        if ($('oneDay').checked) $('toDate').value = $('fromDate').value;
    }
});
$('nativeTo').addEventListener('change', (event) => {
    if (event.target.value) $('toDate').value = formatIso(event.target.value);
});

$('leaveForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const from = parseDate($('fromDate').value);
    const to = parseDate($('toDate').value);
    const reason = $('reason').value.trim();
    if (!from || !to) return toast('Enter valid From and To dates (DD/MM/YYYY).');
    if (to < from) return toast('To Date cannot be before From Date.');
    if ($('oneDay').checked && from.getTime() !== to.getTime()) return toast('For one day, both dates must match.');
    const first = $('fromSession').value;
    const last = $('toSession').value;
    const days = rangeDays(from, to, first, last);
    if (days <= 0) return toast('Choose a valid FN/AN session range.');
    if (!reason) { $('reason').focus(); return toast('Please enter a reason for applying.'); }
    if (preview) {
        history.unshift({type: $('leaveType').selectedOptions[0].textContent,
            date: days === 0.5 ? `${formatDate(from)} (${first})` : days === 1 ? `${formatDate(from)} (Full Day)` : `${formatDate(from)} - ${formatDate(to)}`,
            days, reason, status: 'Pending'});
        $('pendingKpi').textContent = String(history.filter((record) => record.status === 'Pending').length);
        renderHistory();
        event.target.reset();
        return toast('Preview request added. No request was sent to the campus ERP.');
    }
    if ((first === 'AN' || last === 'FN') && from.getTime() !== to.getTime()) {
        return toast('Submit separate requests for partial days across a date range.');
    }
    const button = event.target.querySelector('[type=submit]');
    button.disabled = true;
    try {
        await rpc('submit_leave', [{leave_type_id: Number($('leaveType').value),
            date_from: isoDate(from), date_to: isoDate(to), from_session: first, to_session: last, reason}]);
        event.target.reset();
        await loadLive();
        toast('Leave request submitted for approval.');
    } catch (error) {
        toast(error.message);
    } finally {
        button.disabled = !liveData?.can_apply;
    }
});

if (preview) {
    renderHistory();
} else {
    $('leaveBalanceKpi').textContent = '—';
    $('leaveBalanceText').textContent = '—';
    document.querySelector('.kpi-grid .kpi:nth-child(2) .kpi-value').textContent = '—';
    document.querySelector('.kpi-grid .kpi:nth-child(3) .kpi-value').textContent = '—';
    $('pendingKpi').textContent = '—';
    $('historyRows').innerHTML = '<tr><td colspan="6" class="empty-row">Loading leave requests…</td></tr>';
    renderAttendance([]);
    document.querySelector('.side-foot > span:first-child').textContent = 'Campus';
    document.querySelector('.side-foot > span:nth-child(2)').textContent = 'Staff';
    $('accountButton').querySelector('.avatar').textContent = '?';
    $('accountMenu').querySelector('.menu-line').textContent = 'Loading account…';
    $('notificationsButton').querySelector('.notify-dot').hidden = true;
    $('notificationsButton').setAttribute('aria-label', 'Notifications loading');
    $('notificationMenu').innerHTML = '<div class="menu-line">Loading notifications…</div>';
    $('academicYear').innerHTML = '<option value="">Loading academic years…</option>';
    $('leaveType').innerHTML = '<option value="">Loading leave types…</option>';
    $('authority').innerHTML = '<option>Not assigned</option>';
    document.querySelectorAll('.insight-items strong').forEach((element) => { element.textContent = '—'; });
    $('leaveForm').querySelector('[type=submit]').disabled = true;
    loadLive();
}
