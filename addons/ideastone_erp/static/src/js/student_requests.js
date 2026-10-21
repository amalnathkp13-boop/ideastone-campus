// Presentation of the existing authenticated student request workflow.
(() => {
    const view = () => document.querySelector('.requests_view');
    const pages = {'#student_requests_overview':'overview', '#student_request_new':'new', '#student_request_history':'mine', '#student_certificates':'certificates'};
    const labels = {overview:'Requests & Certificates', new:'New request', mine:'My requests', certificates:'Certificates & documents'};
    function showPage() {
        const root=view(); if (!root) return;
        const detail=location.hash.match(/^#student_request_detail_(\d+)$/);
        const active=detail ? 'mine' : pages[location.hash] || 'overview';
        root.querySelectorAll('dialog[open]').forEach(dialog=>{
            if (!detail || dialog.dataset.requestDialog !== detail[1]) dialog.close();
        });
        root.querySelectorAll('[data-requests-page]').forEach(page=>{page.hidden=page.dataset.requestsPage !== active;});
        const workspace=root.closest('#campus_student_workspace');
        const crumb=workspace?.querySelector('.student_breadcrumb>span:first-child');
        if (crumb) crumb.textContent=`My campus / ${labels[active]}`;
        workspace?.querySelectorAll('.student_subnav a').forEach(link=>{
            if (pages[link.getAttribute('href')] === active) link.setAttribute('aria-current','page');
            else link.removeAttribute('aria-current');
        });
        if (detail) {
            const dialog=root.querySelector(`[data-request-dialog="${detail[1]}"]`);
            if (dialog && !dialog.open) dialog.showModal();
        }
    }
    function go(hash, replace=false) {
        view()?.closest('#student_main')?.querySelectorAll(':scope>.alert:not(.student_network_error), .request-form-error').forEach(message=>{message.hidden=true;});
        history[replace ? 'replaceState' : 'pushState']({},'',hash);
        showPage();
        if (!hash.startsWith('#student_request_detail_')) document.getElementById('student_main')?.scrollIntoView({block:'start'});
    }
    function filterRequests() {
        const root=view(); if (!root) return;
        const value=name=>root.querySelector(`[data-request-filter="${name}"]`).value;
        const search=value('search').trim().toLocaleLowerCase();
        let count=0;
        root.querySelectorAll('[data-request-row]').forEach(row=>{
            const text=[...row.cells].slice(0,2).map(cell=>cell.textContent).join(' ').toLocaleLowerCase();
            const show=text.includes(search) && (value('status') === 'all' || row.dataset.state === value('status')) && (value('type') === 'all' || row.dataset.type === value('type'));
            row.hidden=!show; count+=Number(show);
        });
        root.querySelector('[data-request-count]').textContent=`${count} request${count === 1 ? '' : 's'}`;
        root.querySelector('[data-request-empty]').hidden=count > 0;
    }
    document.addEventListener('click',event=>{
        const root=view(); if (!root) return;
        const link=event.target.closest('a[href^="#"]');
        if (link && (root.contains(link) || link.closest('.student_subnav')) && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
            const hash=link.getAttribute('href');
            if (pages[hash] || /^#student_request_detail_\d+$/.test(hash)) {event.preventDefault(); go(hash); return;}
        }
        if (!root.contains(event.target)) return;
        if (event.target.closest('[data-request-close]')) {go('#student_request_history',true); return;}
        if (event.target.closest('[data-request-reset]')) {
            root.querySelectorAll('[data-request-filter]').forEach(input=>{input.value=input.type === 'search' ? '' : 'all';}); filterRequests();
        }
        const certificate=event.target.closest('[data-certificate-type]');
        if (certificate && !certificate.disabled) {
            const select=root.querySelector('#student_request_type');
            if (![...select.options].some(option=>option.value === certificate.dataset.certificateType)) return;
            select.value=certificate.dataset.certificateType;
            select.dispatchEvent(new Event('change',{bubbles:true}));
            root.querySelector('#student_request_title').value=certificate.dataset.certificateTitle;
            root.querySelector('#student_request_accuracy').checked=false;
            go('#student_request_new'); root.querySelector('#student_request_description').focus();
        }
    });
    document.addEventListener('input',event=>{if (event.target.matches('[data-request-filter]') && view()?.contains(event.target)) filterRequests();});
    document.addEventListener('change',event=>{if (event.target.matches('[data-request-filter]') && view()?.contains(event.target)) filterRequests();});
    document.addEventListener('reset',event=>{
        if (event.target.matches('[data-student-request-create]')) setTimeout(()=>event.target.querySelector('.student_request_type')?.dispatchEvent(new Event('change',{bubbles:true})),0);
    });
    document.addEventListener('cancel',event=>{
        if (event.target.matches('[data-request-dialog]') && view()?.contains(event.target)) {event.preventDefault(); go('#student_request_history',true);}
    },true);
    window.addEventListener('hashchange',showPage); window.addEventListener('popstate',showPage);
    function resetInitialScroll() {
        if (view()) {document.getElementById('wrapwrap')?.scrollTo({top:0}); window.scrollTo({top:0});}
    }
    window.addEventListener('load',()=>requestAnimationFrame(resetInitialScroll));
    function watch() {
        new MutationObserver(changes=>{
            if (changes.some(change=>[...change.addedNodes].some(node=>node.nodeType === 1 && (node.matches?.('.requests_view') || node.querySelector?.('.requests_view'))))) showPage();
        }).observe(document.body,{childList:true,subtree:true});
        showPage();
        requestAnimationFrame(resetInitialScroll);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',watch); else watch();
})();
