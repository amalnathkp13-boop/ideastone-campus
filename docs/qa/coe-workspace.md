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
| Question papers | Question papers and HOD status, received papers, dispatch register |
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

## Department-first organization update

COE registers now open with department cards. Choosing a department shows Years I–IV; choosing a year shows current examination subjects and the HOD's question-paper progress. Subject records retain the existing examination, case, official-PDF and dispatch actions. Departments without matching records are grouped under a collapsed directory. Academic years use year cards; HOD routing uses department cards because routes are independent of a study year.

The four dashboard summary cards appear only on Overview. Filters use explicit change handlers, a latest-request guard and a consistent stored scope, so an older response cannot replace a later choice or update a page after navigating away. Refresh reloads the current scope. Reset returns to the default current academic year and all departments/years, clearing the subject and search. Setup pages omit filters that do not apply to that register.

HOD progress is a limited projection of submitted, returned, approved and forwarded papers routed to the authenticated COE in the active college. Drafts, unselected PDFs and confidential HOD notes are excluded. Year grouping uses an explicit examination link first, then matching scheduled dates, then an unambiguous subject/year allocation in the selected academic year. Ambiguous or unscheduled subjects remain under Needs year assignment. PDF permissions and the approval/receipt/dispatch workflow remain enforced by the existing methods.

Validation: 18 backend tests passed. All 21 COE subpages were opened and refreshed in the browser; summary cards were present only on Overview. Rapid year changes, academic-year switching, reset, department → year → subject navigation, scoped refresh and department-summary CSV export were checked. See `coe-evidence/organization-checks.json` and the department/year/subject screenshots.
