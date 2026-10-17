# Parent Portal acceptance checklist

Use a disposable database with the real college modules installed. Prepare two children linked to Parent A, one unlinked child for Parent B, an additional guardian for one shared child, a staff reviewer, two colleges and separate student/staff accounts. Use synthetic records and temporary passwords. Record the build commit, browser, width, timezone, child, academic placement and actual result for each case.

## Login, access and child selection

1. Sign in as Parent A. `/my/campus` opens Overview with only the two linked children and the college name.
2. Select each child. Profile, header, placement, counts, schedules, marks, fee balances, notices, requests and downloads all follow that child.
3. Refresh and use browser back/forward. The child and date context remain correct.
4. Sign in as Parent B. The one linked child's name is shown without an unnecessary selector.
5. Replace the child ID with an unlinked ID, negative ID and non-number. Access is denied without displaying another child's records.
6. Carry Child A's enrolment ID into Child B's URL. The invalid placement is denied.
7. Revoke a guardian link while the parent is signed in. Refresh and previously saved download URLs immediately fail.
8. Repeat with an archived parent, archived child, disabled college policy and removed company access.
9. Check that parents cannot open staff/Owner services, Student write services, arbitrary student searches or raw official-record writes.
10. Log out and retry a saved receipt URL. Authentication is required. Browser back must not reveal cached private pages.

## Overview and appearance

11. Reconcile all four cards with their detail pages. Missing attendance is labelled unavailable rather than 0%.
12. Verify subject and monthly attendance charts use submitted attendance and the college's configured threshold.
13. Confirm work count, nearest deadline and overdue/submitted statuses against allocated published assignments.
14. Confirm upcoming classes, released exams and future assignment deadlines are sorted chronologically with explicit dates.
15. Confirm fee totals and nearest due date against posted invoices. Earlier-period amounts are clearly labelled as included.
16. Click every summary card and quick action. Each opens its real detail page for the selected child.
17. Verify explicit empty states on a child without attendance, assignments, results, notices or fees.
18. Check 1440px desktop, 768px tablet and 390px phone layouts. No document overflow, hidden actions, overlapping headers or clipped cards.
19. Open and close the mobile drawer with button, backdrop and Escape. Use keyboard Tab/Shift+Tab and visible focus; the drawer must not trap the user after closing.
20. Test a network failure during navigation. Last-loaded records are labelled; Retry works after reconnection. Successful submissions show a saved state.

## Academic and learning records

21. Compare the same child/period attendance across Faculty, Student and Parent. Draft sheets and cancelled classes must not increase the denominator.
22. Test late/excused policy and a shortage boundary using the configured institutional values.
23. Apply another date range and placement. Invalid ranges show a clear error; no unrelated subject/section leaks.
24. Verify confirmed/cancelled timetable entries, room, teacher, dates, daily/weekly/all filters and empty days.
25. A draft homework assignment remains hidden. Publish and allocate it to Child A: only Child A sees it.
26. Submit/accept the assignment as the student/staff. Parent status and pending count update without a second submission record.
27. Filter all/pending/completed work. Parents have no submit or modify-work action.
28. Publish approved learning materials. Authorized downloads work; another child's private resource ID is denied.
29. A draft exam and draft marks stay hidden. Release the schedule, then publish results through the academic workflow; visible dates, marks and grades match the Student view.
30. Confirm no unsupported report-card/hall-ticket or calendar action is displayed as a working feature.

## Fees, notices and documents

31. Post distinct fee invoices for each child, then record a partial payment through the staff workflow. Each portal shows its own residual and payment history.
32. Download the official receipt; the file is a valid PDF with the correct receipt, amount and child.
33. Change the receipt child/record ID, omit the child, use a foreign college ID and retry after revocation. All unauthorized downloads fail privately.
34. No payment is posted by clicking a browser link or supplying a success query parameter. Online payment stays unavailable without a configured provider.
35. Publish parent, all-audience, student-only, staff-only, section/group-targeted, future, expired and draft notices. Only currently eligible parent/all notices appear.
36. Pinned notices appear first. Read/unread can be changed and persists after reload.
37. A read acknowledgement does not mark the notice read for another child or guardian. Attachment authorization follows the notice's current audience.
38. Save the badge preference, refresh and sign in again. The preference is retained for that parent without hiding the notice feed.
39. A draft/unverified/unreleased document stays hidden. Authorized staff verify and release it; only linked parents can download it.
40. Revoke document release. Existing download URLs stop working. Direct writes to the release flag and parent attempts to change it are rejected.

## Requests and staff workflow

41. Confirm student-only request types do not appear for parents and parent-only types do not appear for students. Test college override/disable settings.
42. Submit an enquiry/correction request and reload. One saved reference and history appear only for that requester and child.
43. Submit again with the same key. Only one request is created; retry cannot alter its original absence dates.
44. Submit an absence intimation without dates, reversed dates and a range over one year. Validation prevents saving invalid evidence.
45. Submit a valid absence range and reason. Staff see dates and requester. Official attendance remains unchanged.
46. Staff request additional information. Parent replies through the displayed form; the same case returns to Submitted and retains history.
47. Staff approve and complete the case. The parent sees the response/status after refresh. A meeting is confirmed only by the staff response.
48. Submit and cancel a permitted request. Refresh confirms cancellation. Another parent/child cannot reply to or cancel it by changing an ID.
49. Test permitted PDF/image/text evidence, required evidence, oversized uploads and unsupported content. Server validation must enforce the configured type/size limit.
50. Staff attach an official ready/completed response. Only the requester and selected child can download it; another guardian's private correspondence stays hidden.
51. POST without CSRF and attempt unsupported profile/marks/payment/submission actions. The server rejects them; official data stays unchanged.

## Optional transport and help

52. Transport is absent with policy disabled, no allocation, a draft/cancelled allocation, another academic year, archived route or archived stop.
53. Enable policy and approve a current allocation. Only that child's scheduled pickup, boarding point and route contact appear. No live location or invented drop time is claimed.
54. Verify account/security links, configured college contact details and logout. No plaintext password or unrelated guardian contact is displayed.

## Automated evidence

Run the existing Odoo module test suite, then the disposable Owner/Student/Parent seeds and `browser.cjs`. Supply `PARENT_QA_PASSWORD` and `PARENT_QA_OUT`; defaults are `PARENT_QA_BASE=http://127.0.0.1:18069` and `PARENT_QA_DB=ci`. Local Windows verification can select installed Chrome with `PARENT_QA_CHROME=1`. Do not run the synthetic seeds on a production or shared demonstration database.

Committed screenshots contain synthetic sample-college records only. Runtime passwords, session cookies, database credentials and local configurations are excluded from the repository.
