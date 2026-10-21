// Library presentation over the authenticated catalogue and service workflows.
(() => {
    const view = () => document.querySelector('.library_view');
    const pages = {'#student_library_overview':'overview', '#student_library_catalogue':'catalogue', '#student_library_loans':'loans', '#student_library_reservations':'reservations', '#student_library_digital':'digital'};
    const labels = {overview:'Library', catalogue:'Catalogue', loans:'My loans', reservations:'Reservations & requests', digital:'Digital resources'};
    function updateIntent() {
        const root=view(), form=root?.querySelector('[data-library-enquiry]'); if (!form) return;
        const renewal=form.elements.intent.value === 'renew';
        form.querySelector('[data-library-loan-field]').hidden=!renewal;
        form.elements.loan_id.required=renewal;
        form.elements.book_title.readOnly=renewal;
        if (renewal) form.elements.book_title.value=form.elements.loan_id.selectedOptions[0]?.dataset.title || '';
    }
    function showPage() {
        const root=view(); if (!root) return;
        const detail=location.hash.match(/^#student_library_book_(\d+)$/);
        const active=detail ? 'catalogue' : pages[location.hash] || 'overview';
        root.querySelectorAll('dialog[open]').forEach(dialog=>{if (!detail || dialog.dataset.libraryDialog !== detail[1]) dialog.close();});
        root.querySelectorAll('[data-library-page]').forEach(page=>{page.hidden=page.dataset.libraryPage !== active;});
        const workspace=root.closest('#campus_student_workspace');
        const crumb=workspace?.querySelector('.student_breadcrumb>span:first-child');
        if (crumb) crumb.textContent=`My campus / ${labels[active]}`;
        workspace?.querySelectorAll('.student_subnav a').forEach(link=>{
            if (pages[link.getAttribute('href')] === active) link.setAttribute('aria-current','page');
            else link.removeAttribute('aria-current');
        });
        updateIntent();
        if (detail) {
            const dialog=root.querySelector(`[data-library-dialog="${detail[1]}"]`);
            if (dialog && !dialog.open) dialog.showModal();
        }
    }
    function go(hash,replace=false) {
        view()?.closest('#student_main')?.querySelectorAll(':scope>.alert:not(.student_network_error)').forEach(message=>{message.hidden=true;});
        history[replace ? 'replaceState' : 'pushState']({},'',hash); showPage();
        if (!hash.startsWith('#student_library_book_')) document.getElementById('student_main')?.scrollIntoView({block:'start'});
    }
    function filterCatalogue() {
        const root=view(); if (!root) return;
        const value=name=>root.querySelector(`[data-library-filter="${name}"]`).value;
        const q=value('search').trim().toLocaleLowerCase(); let count=0;
        root.querySelectorAll('[data-library-book]').forEach(row=>{
            const show=row.dataset.search.toLocaleLowerCase().includes(q) && (value('category') === 'all' || JSON.parse(row.dataset.category).includes(value('category'))) && (value('availability') === 'all' || value('availability') === row.dataset.availability);
            row.hidden=!show; count+=Number(show);
        });
        root.querySelector('[data-library-count]').textContent=`${count} title${count === 1 ? '' : 's'}`;
        root.querySelector('[data-library-empty]').hidden=count > 0;
    }
    document.addEventListener('click',event=>{
        const root=view(); if (!root) return;
        const link=event.target.closest('a[href^="#"]');
        if (link && (root.contains(link) || link.closest('.student_subnav')) && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
            const hash=link.getAttribute('href');
            if (pages[hash] || /^#student_library_book_\d+$/.test(hash)) {event.preventDefault(); go(hash); return;}
        }
        if (!root.contains(event.target)) return;
        if (event.target.closest('[data-library-close]')) {go('#student_library_catalogue',true); return;}
        if (event.target.closest('[data-library-reset]')) {
            root.querySelectorAll('[data-library-filter]').forEach(input=>{input.value=input.type === 'search' ? '' : 'all';}); filterCatalogue();
        }
        const request=event.target.closest('[data-library-title]');
        if (request) {
            go('#student_library_reservations');
            const form=root.querySelector('[data-library-enquiry]'); if (!form) return;
            form.elements.intent.value=request.dataset.libraryIntent;
            form.elements.loan_id.value=request.dataset.libraryLoan || '';
            form.elements.book_title.value=request.dataset.libraryTitle;
            updateIntent(); form.elements.note.focus();
        }
    });
    document.addEventListener('submit',event=>{
        const root=view(); if (!root || !root.contains(event.target) || !event.target.matches('[data-library-search]')) return;
        event.preventDefault(); event.stopPropagation();
        root.querySelector('[data-library-filter="search"]').value=root.querySelector('#library_overview_search').value;
        root.querySelector('[data-library-filter="category"]').value='all';
        root.querySelector('[data-library-filter="availability"]').value='all';
        filterCatalogue(); go('#student_library_catalogue');
    },true);
    document.addEventListener('input',event=>{if (event.target.matches('[data-library-filter]') && view()?.contains(event.target)) filterCatalogue();});
    document.addEventListener('change',event=>{
        if (!view()?.contains(event.target)) return;
        if (event.target.matches('[data-library-filter]')) filterCatalogue();
        if (event.target.matches('#library_request_intent,#library_request_loan')) updateIntent();
    });
    document.addEventListener('cancel',event=>{if (event.target.matches('[data-library-dialog]') && view()?.contains(event.target)) {event.preventDefault(); go('#student_library_catalogue',true);}},true);
    window.addEventListener('hashchange',showPage); window.addEventListener('popstate',showPage);
    function resetScroll() {if (view()) {document.getElementById('wrapwrap')?.scrollTo({top:0}); window.scrollTo({top:0});}}
    window.addEventListener('load',()=>requestAnimationFrame(resetScroll));
    function watch() {
        new MutationObserver(changes=>{if (changes.some(change=>[...change.addedNodes].some(node=>node.nodeType === 1 && (node.matches?.('.library_view') || node.querySelector?.('.library_view'))))) showPage();}).observe(document.body,{childList:true,subtree:true});
        showPage(); requestAnimationFrame(resetScroll);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',watch); else watch();
})();
