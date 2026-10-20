// Local enhancements for the published student notice and calendar content.
(() => {
    const view = () => document.querySelector('.notices_view');
    const pages = {'#student_notices_overview':'overview', '#student_notice_list':'notices', '#student_college_events':'events', '#student_academic_calendar':'calendar'};
    const labels = {overview:'Notices & Calendar', notices:'Notices & Circulars', events:'College Events', calendar:'Academic Calendar'};
    const isoDay = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
    function showPage() {
        const root = view();
        if (!root) return;
        const active = pages[location.hash] || 'overview';
        root.querySelectorAll('[data-notices-page]').forEach(page => { page.hidden = page.dataset.noticesPage !== active; });
        const workspace = root.closest('#campus_student_workspace');
        const crumb = workspace?.querySelector('.student_breadcrumb > span:first-child');
        if (crumb) crumb.textContent = `My campus / ${labels[active]}`;
        workspace?.querySelectorAll('.student_subnav a').forEach(link => {
            if (pages[link.getAttribute('href')] === active) link.setAttribute('aria-current','page');
            else link.removeAttribute('aria-current');
        });
        if (!root.dataset.month) root.dataset.month = root.dataset.today.slice(0,7);
        if (active === 'calendar') renderCalendar(root);
    }
    function filterRows(root, kind) {
        const prefix = kind === 'notices' ? 'notices' : 'events';
        const value = name => root.querySelector(`[data-${prefix}-filter="${name}"]`).value;
        let count = 0;
        root.querySelectorAll(kind === 'notices' ? '[data-notice-record]' : '[data-event-record]').forEach(row => {
            const show = (value('category') === 'all' || row.dataset.category === value('category')) &&
                (kind === 'notices' ? value('priority') === 'all' || row.dataset.priority === value('priority') : value('period') === 'all' || row.dataset.period === value('period')) &&
                row.textContent.toLocaleLowerCase().includes(value('search').trim().toLocaleLowerCase());
            row.hidden = !show;
            count += Number(show);
        });
        root.querySelector(`[data-notices-empty="${kind}"]`).hidden = count > 0;
    }
    function renderCalendar(root) {
        const [year, month] = root.dataset.month.split('-').map(Number);
        const first = new Date(year,month-1,1,12);
        const title = first.toLocaleDateString('en-IN',{month:'long',year:'numeric'});
        root.querySelector('[data-notices-month-title]').textContent = title;
        root.querySelector('[data-notices-month-label]').textContent = title;
        const grid = root.querySelector('[data-notices-month-grid]');
        const items = [...root.querySelectorAll('[data-notices-calendar-source] > span')].map(item => item.dataset);
        const cells = ['SUN','MON','TUE','WED','THU','FRI','SAT'].map(name => {
            const cell = document.createElement('div'); cell.className='day-name'; cell.textContent=name; return cell;
        });
        let count = 0;
        for (let index=0; index<42; index++) {
            const date = new Date(year,month-1,1-first.getDay()+index,12);
            const day = isoDay(date);
            const cell = document.createElement('div');
            cell.className = `day-cell${date.getMonth() !== month-1 ? ' muted' : ''}${day === root.dataset.today ? ' today' : ''}`;
            const number = document.createElement('div'); number.className='day-num'; number.textContent=date.getDate(); cell.append(number);
            const matches = items.filter(item => item.start <= day && day <= item.end);
            for (const item of matches) {
                const tag = document.createElement('span'); tag.className=`cal-event ${item.tone}`; tag.textContent=item.name; cell.append(tag);
                if (date.getMonth() === month-1) count++;
            }
            cell.setAttribute('aria-label', `${day}${matches.length ? ': '+matches.map(item=>item.name).join(', ') : ''}`);
            cells.push(cell);
        }
        grid.replaceChildren(...cells);
        root.querySelector('[data-notices-calendar-empty]').hidden = count > 0;
    }
    function calendarFile(button) {
        const escape = value => String(value || '').replace(/\\/g,'\\\\').replace(/\r\n|\r|\n/g,'\\n').replace(/[;,]/g,'\\$&');
        const encoder = new TextEncoder();
        const fold = line => {
            const parts=[]; let segment='', bytes=0;
            for (const char of line) {
                const size=encoder.encode(char).length;
                if (bytes+size > 75) { parts.push(segment); segment=' '+char; bytes=1+size; }
                else { segment+=char; bytes+=size; }
            }
            parts.push(segment); return parts.join('\r\n');
        };
        const data=button.dataset;
        const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Ideastone//Student Campus Calendar//EN','BEGIN:VEVENT',`UID:${data.key}@ideastone-campus`,
            `DTSTAMP:${new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'')}`,`DTSTART:${data.start}`,`DTEND:${data.end}`,
            `SUMMARY:${escape(data.title)}`,`LOCATION:${escape(data.location)}`,'END:VEVENT','END:VCALENDAR'];
        const url=URL.createObjectURL(new Blob([lines.map(fold).join('\r\n')+'\r\n'],{type:'text/calendar;charset=utf-8'}));
        const link=document.createElement('a'); link.href=url; link.download=`${data.key}.ics`; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    document.addEventListener('click', event => {
        const root=view(); if (!root) return;
        const link=event.target.closest('a[href^="#"]');
        if (link && (root.contains(link) || link.closest('.student_subnav')) && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
            const hash=link.getAttribute('href');
            if (pages[hash]) { event.preventDefault(); history.pushState({},'',hash); showPage(); document.getElementById('student_main')?.scrollIntoView({block:'start'}); return; }
        }
        if (!root.contains(event.target)) return;
        const apply=event.target.closest('[data-notices-apply]'); if (apply) filterRows(root,apply.dataset.noticesApply);
        const reset=event.target.closest('[data-notices-reset]');
        if (reset) {
            const kind=reset.dataset.noticesReset, prefix=kind === 'notices' ? 'notices' : 'events';
            root.querySelectorAll(`[data-${prefix}-filter]`).forEach(input=>{ input.value=input.type === 'search' ? '' : 'all'; }); filterRows(root,kind);
        }
        const month=event.target.closest('[data-notices-month]');
        if (month) {
            const [year,number]=root.dataset.month.split('-').map(Number);
            root.dataset.month=isoDay(new Date(year,number-1+(month.dataset.noticesMonth === 'next' ? 1 : -1),1,12)).slice(0,7); renderCalendar(root);
        }
        const ics=event.target.closest('[data-event-ics]'); if (ics) calendarFile(ics);
        if (event.target.closest('[data-notices-print]')) window.print();
    });
    window.addEventListener('hashchange',showPage); window.addEventListener('popstate',showPage);
    function watch() {
        new MutationObserver(changes=>{ if (changes.some(change=>[...change.addedNodes].some(node=>node.nodeType===1 && (node.matches?.('.notices_view') || node.querySelector?.('.notices_view'))))) showPage(); }).observe(document.body,{childList:true,subtree:true});
        showPage();
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',watch); else watch();
})();
