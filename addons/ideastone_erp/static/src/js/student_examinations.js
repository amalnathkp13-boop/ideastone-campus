// Enhances only the student examination content; shared navigation is reused.
(() => {
    const view = () => document.querySelector(".exam_view");
    const pageForHash = {"#student_exam_schedule": "overview", "#student_results": "results"};

    function showPage() {
        const exams = view();
        if (!exams) return;
        const active = pageForHash[location.hash] || "overview";
        exams.querySelectorAll("[data-exam-page]").forEach(page => { page.hidden = page.dataset.examPage !== active; });
        const workspace = exams.closest("#campus_student_workspace");
        const crumb = workspace?.querySelector(".student_breadcrumb > span:first-child");
        if (crumb) crumb.textContent = `My campus / ${active === "results" ? "My Results" : "Examinations & Results"}`;
        workspace?.querySelectorAll('.student_subnav a[href^="#student_"]').forEach(link => {
            if (pageForHash[link.getAttribute("href")] === active) link.setAttribute("aria-current", "page");
            else link.removeAttribute("aria-current");
        });
    }

    function filterResults(exams) {
        const assessment = exams.querySelector('[data-exam-filter="assessment"]').value;
        const subject = exams.querySelector('[data-exam-filter="subject"]').value;
        let visible = 0;
        exams.querySelectorAll(".exam_result_row").forEach(row => {
            row.hidden = (assessment !== "all" && row.dataset.assessment !== assessment) || (subject !== "all" && row.dataset.subject !== subject);
            visible += Number(!row.hidden);
        });
        const empty = exams.querySelector("[data-exam-empty]");
        if (empty) empty.hidden = visible > 0;
    }

    document.addEventListener("click", event => {
        const exams = view();
        if (!exams) return;
        const link = event.target.closest('a[href^="#"]');
        if (link && (exams.contains(link) || link.closest(".student_subnav")) && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
            const destination = link.getAttribute("href");
            if (pageForHash[destination]) {
                event.preventDefault();
                history.pushState({}, "", destination);
                showPage();
                document.getElementById("student_main")?.scrollIntoView({block: "start"});
                return;
            }
        }
        if (!exams.contains(event.target)) return;
        if (event.target.closest("[data-exam-apply]")) filterResults(exams);
        if (event.target.closest("[data-exam-reset]")) {
            exams.querySelectorAll("[data-exam-filter]").forEach(select => { select.value = "all"; });
            filterResults(exams);
        }
        if (event.target.closest("[data-exam-print]")) window.print();
    });
    window.addEventListener("hashchange", showPage);
    window.addEventListener("popstate", showPage);
    function watch() {
        new MutationObserver(changes => {
            if (changes.some(change => [...change.addedNodes].some(node => node.nodeType === 1 && (node.matches?.(".exam_view") || node.querySelector?.(".exam_view"))))) showPage();
        }).observe(document.body, {childList: true, subtree: true});
        showPage();
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch);
    else watch();
})();
