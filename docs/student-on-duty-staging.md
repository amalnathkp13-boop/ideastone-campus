# Student On Duty implementation staging

## Existing rules reused

- Student identity and portal authorization come from `campus.student.portal._identity()`.
- Active semester placement comes from the same portal service used by attendance and academics.
- The college-managed `campus.student.leave.routing` record supplies the student's assigned advisor/mentor and HOD. OD requests have their own model because leave is advisor-filed and has a different workflow.
- `campus.student.portal._serialize()` is used before token checks and writes so concurrent submissions for one student cannot spend the same remaining allowance.
- Attendance is owned by OpenEduCat attendance sheets and the existing college excused policy. This student stage does not mutate attendance.

## Student stage

- A portal student can submit a Special OD for dates within an active semester and enrolment. The request starts at Pending Mentor and reserves its token cost.
- Repeated submissions with the same form key are idempotent. Overlapping active requests are blocked.
- The student can cancel while Pending Mentor, releasing the reservation. Once a later HOD stage places a Special OD in Withheld, the student can upload validated proof before the separately recorded deadline.
- The portal shows the 30-token college default, optional per-enrolment override, used/reserved/remaining counters, route availability, application history, and immutable action events.
- General OD is visible as a staff-initiated category only; this stage does not let a student initiate it.

## Next stage and institutional decisions

- Mentor and HOD decision services, a separate HOD login, proof requirements/deadline assignment, expiry scheduling, General OD initiation, and attendance integration are not enabled by this student-only stage.
- The existing HOD group is read-only. The later decision stage needs a scoped approval group and a validated department-to-HOD assignment.
- Confirm whether cancellation after mentor review is allowed and how a later quota reduction handles reservations already made.
- Confirm whether provisional Special OD should display separately from the existing `excused` attendance status. No attendance line should be overwritten or created for a future date merely because OD is approved.
