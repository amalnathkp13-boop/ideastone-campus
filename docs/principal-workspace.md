# Principal workspace

The Principal signs in at the shared `/web/login` page. The internal user has
`ideastone_principal.group_principal`, which includes management read access
without owner/system administration rights. The user's home action is
`ideastone_principal.action_principal_overview`.

The persistent sidebar is the same `ideastone_erp.Navigation` component used by
faculty and college administration. The Principal navigation selects oversight
pages from the existing styled admissions, students, academics, faculty,
calendar, attendance, fees, LMS, exams, and reports workspaces.
Operational pages such as payroll history, fee setup, receipts, and attendance
entry are excluded. The Principal action model supplies the overview, decision
queue, and notices pages. Navigation preferences use the `principal` scope.

Staff can create a `ideastone.principal.request` draft and submit it. Only a
Principal can approve or reject a submitted request; rejection requires a note.
Decisions record the actor and timestamp, and submitted requests cannot be
deleted. Principals can draft, publish, and archive notices. Both models use
company rules. The decision page also lists `campus.student.leave` records
assigned to the signed-in Principal at the existing principal review stage.
That workflow retains its advisor, HOD, and Principal decision log.

The overview counts saved records in the active company. The all-applications
count includes legacy admissions, while the Admissions workspace focuses on
college-managed applications. Student directory filters default to the current
academic year, so its count can differ from the Principal's all-year count.

For a preview account, assign the Principal group and home action to an
internal user in the target database. Do not put preview passwords in source
control. Module tests cover request and notice permissions plus shared
navigation.
