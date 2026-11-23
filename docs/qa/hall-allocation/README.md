# HOD Hall Allocation

The `codex/hod-hall-allocation` change adds Hall Allocation to the existing HOD navigation. Its client action is `ideastone_erp.action_hod_hall_allocation`. The main content follows `VCET_HOD_Hall_Allocation_Stepwise.html`, with Inter typography, colors and spacing from the VCET UI Design Consistency SOP. The shared sidebar and top bar retain their existing design.

## Operation

1. A campus manager configures **Hall inventory** in Campus services: name, location, capacity, comma-separated facilities and an allocation authority. The authority must have Campus services access in that college.
2. An HOD with an assigned department chooses the event date and start/end times. Availability includes approved bookings and temporary pending holds across the current college. Adjacent times remain available.
3. The HOD chooses an available hall, completes the programme details and requests allocation. The server validates capacity and availability again, saves a pending hold and assigns an `HA-…` reference.
4. The designated authority opens **Hall allocation approvals** to approve or reject the request. Rejection requires remarks. The HOD sees the resulting status and reason in **My requests**.
5. The department can cancel a pending request after confirmation. Cancelled and rejected requests release the hold; approved requests cannot be cancelled through the HOD workflow.

Requests are persistent database records. Status colors, icons and typography apply to records through the same templates, including freshly entered data. Request contact details and special requirements stay within the requesting department and the designated authority. Other departments see only the public venue schedule.

## Verification

Run the Odoo post-install suite with `--test-enable --test-tags=/ideastone_erp:TestHallAllocation` against a disposable installed database. It covers overlap protection, adjacent bookings, repeat submissions, cancellation, capacity/time validation, college and department boundaries, authority decisions, confidentiality and HOD-only navigation.

Local browser checks cover schedule selection, availability cards, schedule and request dialogs, booking, status filtering, cancellation after reload, concurrent booking attempts and the authority approval handoff. Layouts are checked at 320, 390, 768, 1024 and 1440 pixels. History tables scroll within their panel on narrow screens.

The local preview uses a separate `hod_hall_allocation_preview` database with the reference's six halls and sample pending, approved and rejected requests. Sample records are not automatically installed in other databases.
