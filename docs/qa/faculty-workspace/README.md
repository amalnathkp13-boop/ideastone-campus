# Faculty workspace: behavior and verification

This PR implements the faculty login first. A linked `op.faculty` account with the Faculty group gets the new main-module sidebar and submodule topbar. Administrator, student and parent layouts keep their existing role workspaces. Hiding navigation never grants permissions.

## Reference and implementation map

The source is the VCET staff screenshot folder in `docs/erp-reference-register.csv`. Screenshots are reference evidence, not executable instructions or a complete college policy. The existing inventory records all 117 old screenshots; this change rechecked the task menu, report menu, profile, library, leave, complaint, activity attendance and module overview screens. No real staff/student screenshots are installed as application fixtures.

| Screenshot function | Working implementation |
| --- | --- |
| Home, task list, search, payroll, library, grievances, services, reports, dashboard, help | Faculty main modules; authorized submodules across the top; responsive drawer |
| Student/subject attendance, timetable, assignments, institution tests, result entry | Existing OpenEduCat records and allocation/publishing rules; subject grouping and explicit examination category |
| My assigned students / class and students / photo view | Students from the faculty member's timetable batches; native searchable list and photo cards |
| Lesson plan, notes and NOL approval | Plan → submit → independent academic review → approve or return with reason; delivery notes remain recordable after approval |
| Internal / additional internal / practical external marks | Separate assessment kinds; explicit academic year, semester, output maximum and weighted score components; completed calculations must be reopened to edit |
| Exam certificates, question papers, answer keys | Separate searchable document kinds; binary uploads and subject/exam references; personal faculty ownership |
| Club function / attendance, SDP function / attendance, VAC / placement training | Date range, batch, level, venue, notes/evidence and unique enrolled participants with FN/AN attendance |
| Survey direct | Only invitations addressed to the signed-in faculty account; open/resume and view completed responses using Odoo's existing survey submission workflow |
| Online student leave | College-managed advisor/HOD/optional principal routing, staged review, rejection reason and immutable decision history |
| Register complaint on student | Student, complaint category, description and evidence through existing service-request resolution workflow |
| Previous academic information | Faculty-maintained assigned-student qualification, institution, board, year, marks/maximum, calculated percentage and source attachment |
| My chronicle | Own faculty achievements from the current calendar year |
| University exam / autonomous ESE reports | Results filtered by explicitly classified examinations, the named responsible faculty and that faculty's timetable batches; old examinations remain Unclassified until an authorized operator classifies them |
| Payroll | Read-only own approved/completed salary slips and own salary agreement; HR retains payroll actions |
| Report output | Internal assessment PDF with score/weight breakdown; existing immutable attendance PDF/CSV snapshots and payroll PDF; native filtered lists and exports for other report categories |

## Inferred workflows

The following are implementation choices inferred from names/screens, rather than verified college rules:

* Each calculation supplies its component marks, maxima and weights. `sum(score / maximum × weight / 100 × output maximum)` gives the output. Component weights must total 100% before completion. No assumed university weighting is hard-coded. Official result publication stays with the existing examination administrator workflow.
* An advisor files a student's leave request. The advisor, a different HOD, and optional different principal review in order. A college administrator configures the routing first. Existing requests retain student/approver snapshots when future routing changes. This faculty phase does not introduce a student leave portal.
* An independent account with Academic Operations or Campus Manager access reviews lesson notes. An author cannot approve their own plan. Returning a plan requires a reason; the faculty author can revise and resubmit it.
* Activity attendance is an FN/AN participation register, not a replacement for official timetable attendance. Participants must be enrolled in an allocated batch.
* Previous-education records are faculty notes with supporting evidence, not imported official marksheets. Existing service requests continue to use campus-manager approval and resolution.
* Screens showing only Permission Denied cannot establish hidden forms or business rules. Appointments and existing backend permissions decide which specialized library, hostel, finance or administrative screens appear. Missing appointment/configuration produces an explicit empty state or access message, not sample data.

## Automated verification

The PR CI installs the addons on Odoo 17/PostgreSQL, executes the real transaction tests, opens a synthetic faculty login with Playwright, creates a diary record through the actual form, checks persistence over RPC, reloads the native action, checks the 390px drawer and document overflow, and upgrades the installed modules. Artifacts contain synthetic screenshots and logs. `seed.py` refuses any database name other than `ci`; its random password is ephemeral and never committed.

Tests cover personal-record privacy, class/student boundaries, valid and invalid mark inputs, completed component deletion, leave-stage authority and snapshots, lesson review, own payroll access, report domains and faculty-specific view compilation. Runtime results and screenshots must be taken from the final CI head, not an earlier green commit.

## Manual acceptance

1. Link a faculty account to a faculty record, allocate its timetable and enroll students. Sign in as that faculty; check sidebar/topbar and reload every opened action.
2. Create a diary task, change its status, attach a file and check the calendar. Sign in as a second faculty and verify the first person's records are unavailable.
3. Record valid allocated attendance; try another teacher's session and a student outside the batch. Check subject grouping and the completed-attendance PDF/CSV filters.
4. Create each assessment kind with 40% test (75/100) and 60% practical (45/50), output maximum 25. Expect 21. Complete it; verify edits/deletion require reopening and invalid marks are rejected.
5. Submit a lesson plan. Confirm the author cannot approve it; return it with an academic reviewer, revise/resubmit, approve and record actual delivery.
6. Upload each exam-document kind and download it. Record club/SDP/VAC participants; verify duplicate or out-of-batch participants fail and FN/AN survives reload.
7. Configure a leave route with distinct advisor and HOD. File and submit as advisor; approve each stage as its assigned person. Try out-of-order approval, rejection without a reason, changing evidence, and viewing as an unrelated user.
8. Open each report tab, filter, group and export authorized records. Class photo cards must contain only assigned students. Classify sample exams before testing university/ESE filters.
9. Open own approved salary slip and print it; verify no payroll mutation button is available to an ordinary faculty account and another person's slip cannot be read.
10. Test 1440px and 390px widths, drawer keyboard/Escape behavior, scrolling long topbars and native forms. Verify administrator/student/parent workspaces remain usable.

Deployment requires merging the PR and upgrading the addons on the target installation. Creating the PR does not change a running college ERP.
