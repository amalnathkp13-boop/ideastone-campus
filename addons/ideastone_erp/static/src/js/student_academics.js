// Academic subpages and filters enhance only the Academics content area.
(() => {
    const view = () => document.querySelector(".student_academics_view");
    const pageForHash = {
        "#student_academics_overview": "overview",
        "#student_enrolment": "enrolment",
        "#student_subjects": "subjects",
        "#student_assignments": "assignments",
        "#student_materials": "materials",
    };
    const labels = {
        overview: "Academics",
        enrolment: "Enrolment",
        subjects: "Subjects",
        assignments: "Assignments & feedback",
        materials: "Learning materials",
    };
    function showPage() {
        const academic = view();
        if (!academic) return;
        const active = pageForHash[location.hash] || "overview";
        academic.querySelectorAll("[data-academic-page]").forEach(page => {
            page.hidden = page.dataset.academicPage !== active;
        });
        const workspace = academic.closest("#campus_student_workspace");
        const crumb = workspace?.querySelector(".student_breadcrumb > span:first-child");
        if (crumb) crumb.textContent = `My campus / ${labels[active]}`;
        workspace?.querySelectorAll('.student_subnav a[href^="#student_"]').forEach(link => {
            if (pageForHash[link.getAttribute("href")] === active) link.setAttribute("aria-current", "page");
            else link.removeAttribute("aria-current");
        });
    }
    function filterSubjects() {
        const academic = view();
        if (!academic) return;
        const query = academic.querySelector(".academic_search").value.trim().toLocaleLowerCase();
        const type = academic.querySelector(".academic_type_filter").value;
        let visible = 0;
        academic.querySelectorAll(".academic_subject_row").forEach(row => {
            row.hidden = !row.dataset.search.toLocaleLowerCase().includes(query) || (type !== "all" && row.dataset.type !== type);
            if (!row.hidden) visible++;
        });
        const count = academic.querySelector(".academic_subject_count");
        count.textContent = `${visible} ${visible === 1 ? "subject" : "subjects"} listed · Placement: ${count.dataset.placement}`;
        academic.querySelector(".academic_subject_no_match").hidden = visible !== 0 || !academic.querySelectorAll(".academic_subject_row").length;
    }
    function filterMaterials() {
        const academic = view();
        if (!academic) return;
        const query = academic.querySelector(".academic_material_search").value.trim().toLocaleLowerCase();
        const subject = academic.querySelector(".academic_material_subject").value;
        let visible = 0;
        academic.querySelectorAll(".academic_resources .academic_resource").forEach(row => {
            row.hidden = !row.dataset.search.toLocaleLowerCase().includes(query) || (subject !== "all" && row.dataset.subject !== subject);
            if (!row.hidden) visible++;
        });
        academic.querySelector(".academic_material_no_match").hidden = visible !== 0 || !academic.querySelectorAll(".academic_resources .academic_resource").length;
    }
    document.addEventListener("click", event => {
        const academic = view();
        if (!academic) return;
        const link = event.target.closest('a[href^="#student_"]');
        if (link && pageForHash[link.getAttribute("href")] && (academic.contains(link) || link.closest(".student_subnav"))) {
            event.preventDefault();
            history.pushState({}, "", link.href);
            showPage();
            document.getElementById("wrapwrap")?.scrollTo({top: 0});
            window.scrollTo({top: 0});
            return;
        }
        const subject = event.target.closest(".academic_subject_open");
        if (subject && academic.contains(subject)) {
            academic.querySelector(".academic_subject_placeholder").hidden = true;
            academic.querySelectorAll(".academic_subject_detail").forEach(panel => {
                panel.hidden = panel.dataset.subjectPanel !== subject.dataset.subjectId;
            });
            return;
        }
        if (event.target.closest(".academic_reset_subjects")) {
            academic.querySelector(".academic_search").value = "";
            academic.querySelector(".academic_type_filter").value = "all";
            filterSubjects();
        }
        if (event.target.closest(".academic_reset_materials")) {
            academic.querySelector(".academic_material_search").value = "";
            academic.querySelector(".academic_material_subject").value = "all";
            filterMaterials();
        }
    });
    document.addEventListener("input", event => {
        if (event.target.matches(".academic_search")) filterSubjects();
        if (event.target.matches(".academic_material_search")) filterMaterials();
    });
    document.addEventListener("change", event => {
        if (event.target.matches(".academic_type_filter")) filterSubjects();
        if (event.target.matches(".academic_material_subject")) filterMaterials();
    });
    window.addEventListener("hashchange", showPage);
    window.addEventListener("popstate", showPage);
    const watch = () => new MutationObserver(records => {
        if (records.some(record => [...record.addedNodes].some(node => node.nodeType === 1 && (node.matches?.(".student_academics_view") || node.querySelector?.(".student_academics_view"))))) showPage();
    }).observe(document.body, {childList: true, subtree: true});
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => { watch(); showPage(); });
    else { watch(); showPage(); }
})();
