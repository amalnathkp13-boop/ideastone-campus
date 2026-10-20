// Reuse the student shell and enhance only the fee content and its view links.
(() => {
    const view = () => document.querySelector('.fee_view');
    const pages = {'#student_fees_overview': 'overview', '#student_fee_ledger': 'details', '#student_receipts': 'history', '#student_fee_aid': 'aid'};
    const labels = {overview: 'Fees & Payments', details: 'Fee details', history: 'Payment history & receipts', aid: 'Scholarships & concessions'};
    function showPage() {
        const fees = view();
        if (!fees) return;
        const active = pages[location.hash] || 'overview';
        fees.querySelectorAll('[data-fee-page]').forEach(page => { page.hidden = page.dataset.feePage !== active; });
        const workspace = fees.closest('#campus_student_workspace');
        const crumb = workspace?.querySelector('.student_breadcrumb > span:first-child');
        if (crumb) crumb.textContent = `My campus / ${labels[active]}`;
        workspace?.querySelectorAll('.student_subnav a').forEach(link => {
            if (pages[link.getAttribute('href')] === active) link.setAttribute('aria-current', 'page');
            else link.removeAttribute('aria-current');
        });
    }
    function filterRows(fees, kind) {
        const value = name => fees.querySelector(`[data-fee-filter="${name}"]`).value;
        let count = 0;
        fees.querySelectorAll(kind === 'details' ? '.fee_ledger_row' : '.fee_receipt_row').forEach(row => {
            const show = kind === 'details'
                ? (value('year') === 'all' || row.dataset.year === value('year')) && (value('status') === 'all' || row.dataset.status === value('status'))
                : (value('method') === 'all' || row.dataset.method === value('method')) && row.textContent.toLocaleLowerCase().includes(value('search').trim().toLocaleLowerCase());
            row.hidden = !show;
            count += Number(show);
        });
        fees.querySelector(`[data-fee-empty="${kind}"]`).hidden = count > 0;
    }
    document.addEventListener('click', event => {
        const fees = view();
        if (!fees) return;
        const link = event.target.closest('a[href^="#"]');
        if (link && (fees.contains(link) || link.closest('.student_subnav')) && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
            const destination = link.getAttribute('href');
            if (pages[destination]) {
                event.preventDefault();
                history.pushState({}, '', destination);
                showPage();
                document.getElementById('student_main')?.scrollIntoView({block: 'start'});
                return;
            }
        }
        if (!fees.contains(event.target)) return;
        const apply = event.target.closest('[data-fee-apply]');
        if (apply) filterRows(fees, apply.dataset.feeApply);
        const reset = event.target.closest('[data-fee-reset]');
        if (reset) {
            const kind = reset.dataset.feeReset;
            for (const name of kind === 'details' ? ['year', 'status'] : ['method', 'search']) {
                fees.querySelector(`[data-fee-filter="${name}"]`).value = name === 'search' ? '' : 'all';
            }
            filterRows(fees, kind);
        }
        if (event.target.closest('[data-fee-print]')) window.print();
    });
    window.addEventListener('hashchange', showPage);
    window.addEventListener('popstate', showPage);
    function watch() {
        new MutationObserver(changes => {
            if (changes.some(change => [...change.addedNodes].some(node => node.nodeType === 1 && (node.matches?.('.fee_view') || node.querySelector?.('.fee_view'))))) showPage();
        }).observe(document.body, {childList: true, subtree: true});
        showPage();
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
    else watch();
})();
