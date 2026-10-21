/** Student OD history search and status filter; no records are changed here. */
(() => {
    function init() {
        const view = document.querySelector(".student_od_view");
        if (!view) return;
        const search = view.querySelector("#od_search");
        const status = view.querySelector("#od_status_filter");
        const rows = [...view.querySelectorAll(".od_history_row")];
        const count = view.querySelector("#od_history_count");
        const filter = () => {
            const query = search.value.trim().toLowerCase();
            let visible = 0;
            for (const row of rows) {
                const match = row.dataset.search.includes(query)
                    && (!status.value || row.dataset.status === status.value);
                row.hidden = !match;
                if (match) visible++;
            }
            if (count) count.textContent = `${visible} of ${rows.length} request(s)`;
        };
        search.addEventListener("input", filter);
        status.addEventListener("change", filter);

        const workflow = view.querySelector("#student_od_workflow");
        const track = workflow.querySelector(".od_workflow_track");
        const stages = [...track.querySelectorAll("[data-step]")];
        const trackingLabel = workflow.querySelector(".od_tracking_label");
        const proofForms = [...view.querySelectorAll(".od_proof_form")];
        const proofDisabled = view.querySelector(".od_proof_disabled");
        const proofHint = view.querySelector(".od_proof_hint");
        const fourthStepNote = stages[3].querySelector("small");
        const fourthStepDefault = fourthStepNote.textContent;
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        let playbackTimer;
        let playbackRevision = 0;

        function selectRequest(row) {
            clearTimeout(playbackTimer);
            const revision = ++playbackRevision;
            for (const item of rows) item.classList.toggle("is-selected", item === row);
            for (const stage of stages) {
                stage.className = "";
                stage.removeAttribute("aria-current");
            }
            if (!row) {
                trackingLabel.textContent = "Submit your first request to start tracking.";
                proofDisabled.hidden = false;
                proofHint.hidden = false;
                for (const form of proofForms) form.hidden = true;
                return;
            }
            trackingLabel.textContent =
                `Tracking ${row.dataset.reference} · ${row.cells[2].textContent.trim()} — ${row.dataset.statusName}`;
            const state = row.dataset.status;
            const general = row.dataset.category === "General OD";
            fourthStepNote.textContent = general && state === "completed"
                ? "Not required for General OD" : fourthStepDefault;
            const progress = {
                draft: { done: 0, current: 0 },
                pending_mentor: { done: 1, current: 2 },
                pending_hod: { done: 2, current: 3 },
                withheld: { done: 3, current: 4 },
                proof_review: { done: 3, current: 4 },
                completed: { done: 5, current: 0 },
                rejected: { done: 1, stopped: 2 },
                invalid: { done: 3, stopped: 4 },
                cancelled: { done: 1, stopped: 2 },
            }[state] || { done: 0, current: 0 };
            const endpoint = progress.current || progress.stopped || progress.done;
            function showStep(number) {
                if (revision !== playbackRevision) return;
                const stage = stages[number - 1];
                if (general && state === "completed" && number === 4) {
                    stage.classList.add("is-skipped");
                } else if (number <= progress.done) {
                    stage.classList.add("is-complete");
                } else if (number === progress.current) {
                    stage.classList.add("is-current");
                    stage.setAttribute("aria-current", "step");
                } else if (number === progress.stopped) {
                    stage.classList.add("is-stopped");
                }
                requestAnimationFrame(() => {
                    if (revision !== playbackRevision) return;
                    track.scrollTo({
                        left: Math.max(0, stage.offsetLeft - (track.clientWidth - stage.clientWidth) / 2),
                        behavior: reducedMotion ? "auto" : "smooth",
                    });
                });
                if (number < endpoint && !reducedMotion) {
                    playbackTimer = setTimeout(() => showStep(number + 1), 420);
                }
            }
            if (reducedMotion) {
                for (let number = 1; number <= endpoint; number++) showStep(number);
            } else if (endpoint) {
                showStep(1);
            }

            const enabledForm = row.dataset.proofEnabled === "true"
                ? proofForms.find(form => form.dataset.odId === row.dataset.odId) : null;
            for (const form of proofForms) form.hidden = form !== enabledForm;
            proofDisabled.hidden = Boolean(enabledForm);
            proofHint.hidden = Boolean(enabledForm);
        }

        for (const row of rows) {
            const details = row.querySelector(".od_details");
            details.addEventListener("toggle", () => {
                if (details.open) selectRequest(row);
            });
        }
        const requested = new URLSearchParams(window.location.search).get("od");
        selectRequest(rows.find(row => row.dataset.reference === requested || row.dataset.odId === requested)
            || rows.find(row => row.dataset.status !== "draft") || rows[0]);
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
