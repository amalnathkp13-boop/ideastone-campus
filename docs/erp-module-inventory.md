# ERP discovery and architecture audit

Discovery date: 14 October 2026. Baseline: `origin/main` at `d6f99fa`. Implementation branch: `feature/complete-campus-erp-modules`.

The public [module map](https://www.impreserp.co.in/modules.php) and [edition list](https://www.impreserp.co.in/impres-erp.php) were reviewed, including linked academic, finance, examination, library, HR, placement, alumni, transport, hostel and purchase pages. The non-www URL initially returned a verification screen; the public www navigation worked. No protected screens or proprietary source were accessed. Names below are website-confirmed; proposed entities, permission assignments and business rules are implementation assumptions unless the reference register says otherwise.

## Inventory before implementation

Roles: A = campus administrator; F = faculty; O = module operator; S/P = student/parent with access to their own records. Existing means an installed dependency implements the named capability; it does not certify every advertised workflow.

| Module | Identified submodules / capabilities | Roles | Proposed data and dependencies | Baseline | Source |
|---|---|---|---|---|---|
| Student academics | Subjects; faculty mapping; timetable; lesson plans; attendance; lesson notes; internal/university marks; parent intimation; photos/certificates | A/F/S/P | Students, subjects, batches, faculty, teaching plans, assessment records, attachments | Partial | [Academics](https://www.impreserp.co.in/modules/academics.php) |
| ERP administration | Years, semesters, privileges | A | Existing academic year/term and Odoo users/groups | Existing | Edition list |
| Admission | Enquiry, application, enrollment, transfer, certificates | A/O | CRM leads, OpenEduCat applications, student enrollment, document requests | Partial | Edition list |
| Billing | Demand, concessions, collection, balance | A/O/S/P | Fee terms, invoices, payments, credits; account/payment/portal | Partial | [Finance](https://www.impreserp.co.in/modules/finance.php) |
| Staff academics | Profile, education, experience, subject allocations | A/F | Faculty, employee, qualifications, service history | Partial | [HR](https://www.impreserp.co.in/modules/hr-payroll.php) |
| Transport | Annual routes/stages; boarding; fuel; trips; mileage; expenses | A/O | Routes, stops, allocations, trips; student, academic year, billing | Missing | [Transport](https://www.impreserp.co.in/modules/transport.php) |
| My Performance | Own attendance, marks, schedule, lesson information, fees, mentor remarks | S/P | Identity-linked student records, portal | Partial | Academics |
| Staff Login | Classes, subjects, leave, results, teaching, self-evaluation | F | Faculty user, lesson plans, HR leave, appraisal | Partial | HR |
| Hostel | Buildings, rooms, facilities, residents, vacancy, attendance, gate, dining, quitting | A/O/S/P | Rooms, dated allocations, presence, movements; students | Missing | [Hostel](https://www.impreserp.co.in/modules/hostel.php) |
| Payroll | Salary, allowances, deductions, monthly run, advance, bank/statutory reporting | A/O/F | Employee, salary agreement, payroll period and lines; attendance | Missing | HR |
| Biometric integration | Device API attendance | A/O | Employee-linked unique external event; hr.attendance | Missing | HR |
| Online leave | Arrangement, HOD/principal approval, payroll linkage | A/F | hr.leave, employee, replacement faculty | Missing | HR |
| Library web | Catalogue, circulation, OPAC, gate, stock check, periodicals, reporting | A/O/S/P | Existing library records; gate log, verification | Partial | [Library](https://www.impreserp.co.in/modules/library.php) |
| Library to billing | Overdue fines | A/O | Existing movement penalty invoice | Existing | Library / Finance |
| Digital library | Restricted electronic resources | A/F/S/P | Authenticated attachments and access groups | Partial | Edition list |
| Online exam | MCQ assessment | A/F/S | OpenOlat courses, questions, enrollment and tests | Existing integration | Edition list; existing LMS |
| Student feedback | Faculty evaluation | A/S | Feedback target, respondent, period, score, comments | Missing | Edition list |
| MIS | Institutional reports | A/O | Secured Odoo pivot/graph views over operational records | Partial | Edition list |
| Messaging | Email, SMS, WhatsApp | A/O | Odoo mail; external provider configuration | Partial (email) | Edition list |
| Payment gateway | Student/parent payment | A/O/S/P | Invoice portal, payment provider and transactions | Partial | Finance |
| Circulars | Official announcements | A/F/S/P | Audience, publication dates, body, attachments | Missing | Edition list |
| Mentor/tutor | Counseling and guidance | A/F/S/P | Student, mentor, meeting, restricted notes, shared remarks | Missing | Edition list |
| Purchase/stock/inventory | Indent, PO, GRN, quality/quantity checks, stock, movements, work/service orders, assets | A/O | Approved requisitions, purchase.order, stock.picking, inspection, maintenance, asset register | Missing | [Purchase](https://www.impreserp.co.in/modules/purchase-inventory.php) |
| Parent feedback | Parent responses | A/P | Feedback with parent identity and linked child | Missing | Edition list |
| Staff feedback | Staff responses | A/F | Staff respondent feedback | Missing | Edition list |
| Placement | Recruiters, locations, representatives, SPOC, communication, shortlisting, interviews, selection | A/O/S | res.partner, drive, candidate, exam outcomes | Missing | [Placement](https://www.impreserp.co.in/modules/placement.php) |
| Alumni | Profile, career/studies, photos/family, forums, chapters, events, jobs | A/O/S | Alumni profile, chapter, event, job; student and partner | Missing | [Alumni](https://www.impreserp.co.in/modules/alumni.php) |
| Faculty appraisal | Proforma and performance | A/F | Faculty achievements, objectives, evaluation, score | Missing | Edition list / HR |
| Agent | Admission leads | A/O | CRM lead, referring partner, application link | Missing | Edition list |
| Accounts | Ledgers, journals, payments, creditors and financial reports | A/O | Existing Odoo accounting, approval configuration | Partial | Finance |
| Visitors | Campus entry | A/O | Visitor identity, host, purpose, in/out timestamps | Missing | Edition list |
| Examination / CoE | Regulations, electives, grades, assessments, eligibility, registration, schedule, seating, evaluators, attendance, dummy/packet numbers, malpractice, verification, publication, revaluation, certification and clearance | A/F/S | OpenEduCat exams/results/seating; additional verified-result and revaluation records | Partial | [Examination](https://www.impreserp.co.in/modules/examination.php), [CoE](https://www.impreserp.co.in/impres-coe.php) |

## Repository audit

Odoo 17 Community and the pinned OpenEduCat 17 submodule use Python ORM models, PostgreSQL, XML views/actions, OWL client actions, SCSS assets, Odoo authentication and access rules. `ideastone_campus` owns branding, Indian student data, master data and Keycloak configuration. `ideastone_lms` owns the launcher and OpenOlat provisioning. Existing admission, fee, exam, library, timetable and attendance services must be retained through inheritance. Vendor code stays unchanged.

The existing CI runs Ruff, XML parsing, Compose validation and a real Odoo module install. New features will use PostgreSQL-backed Odoo records and standard list/form/search/pivot interfaces, with company rules and role-specific permissions. External biometric, messaging and payment providers need college-specific configuration; a local test cannot establish live provider operation.

## College references

The originally supplied Drive folder is the **Logo folder itself**, with the VCET wide logo and `VCET_Staff_Profile_Complete.html`. The parent folder subsequently supplied by the user contains `Logo`, `Erp old ss`, and `Erp new ss`. Only Logo governs visual design. All 117 files under the 11 old ERP folders were listed and downloaded into a private review directory outside Git; the field-review register will distinguish OCR inspection from detailed visual review. Screenshot contents, names of individuals and prototype sample records must not be committed as fixtures.

The authoritative HTML confirms the staff profile sections: personal identity, contact/residence, employment, qualification, service history, reporting, language abilities, prior education, organization and document verification. Its browser-local sample data is a design reference only, and will not become production records.
