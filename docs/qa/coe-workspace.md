# COE examination-cell preview

Branch: `codex/coe-examinations-workspace` (based on the HOD question-paper branch).

Local preview: <http://coe.localhost:18074/web#action=854&cids=1>.
Use the existing `exam.coe.preview` account. Credentials are not stored in this document.
The container is `ideastone-coe-exams-preview`; the isolated database is `question_papers_preview`.
Faculty and HOD previews share this database so handoffs remain connected.

## First workflow

1. Select the academic year, department and Year I–IV.
2. Create examinations using the existing examination-officer form; allocate halls and invigilators in COE operations.
3. Faculty submits PDF alternatives. HOD selects one official version and approves it.
4. The selected approved PDF appears in the assigned COE inbox. Alternatives remain restricted.
5. HOD forwards the paper; COE acknowledges receipt.
6. COE chooses a matching subject, department and examination date, then records the dispatch reference.
7. Use the existing marks roster, approval and result-publication workflow. Missing marks remain explicit.
8. Retain revaluation, correction and incident cases, exports and workflow audit history.

## Navigation

| Main module | Submodules |
| --- | --- |
| COE overview | Overview, action queue |
| Examination records | All examinations, upcoming, recent (last 30 days), past records, timetable |
| Question papers | Approved paper inbox, received papers, dispatch register |
| Exam operations | Hall allocations, invigilation, attendance and incidents |
| Evaluation and results | Evaluation tracker, results register, revaluation and corrections |
| Reports and audit | Department summary, Years I–IV, workflow audit |
| Academic setup | Academic years, departments and HOD routes |

This initial workspace stores allocation details and candidate totals, rather than generating seating charts or importing biometric attendance. Case resolution records a decision and notes; it does not alter a student's marks. Publication continues through the ERP's existing approval checks. Reviewer configuration remains a college-administrator action.

## Sample data and validation

Run `question-papers/seed_coe.py` through Odoo shell in the preview database only. It reuses the existing COE account and engineering departments, adds sample examinations across two academic years, and preserves earlier question-paper history. Empty department rows mean no matching examinations are recorded; no synthetic results have been published.

Verified on 2026-10-26:

- 16 targeted `TestQuestionPapers` backend tests, including COE role and company checks, academic-year and Year III filtering, official-PDF restrictions, duplicate receipt/dispatch prevention, candidate-count validation and incorrect examination-date rejection.
- Browser sign-in and automatic COE landing page; seven sidebar modules with related submodules.
- Official selected PDF downloaded, receipt acknowledged, and sample dispatch persisted for `COE-PACKET-01`.
- Hall and invigilation record saved; department and Year III filters persisted while navigating to reports.
- Department CSV downloaded; existing examination-officer marks form loaded without additional faculty permissions.

Release screenshots and structured evidence are in `coe-evidence/`.
