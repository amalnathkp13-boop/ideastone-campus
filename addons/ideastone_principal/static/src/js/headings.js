/** @odoo-module **/
import { onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { AdmissionsWorkspace } from "@ideastone_erp/js/admissions";
import { StudentsDirectoryWorkspace } from "@ideastone_erp/js/students_directory";
import { OwnerStaffDirectory } from "@ideastone_erp/js/owner_staff";
import { CollegeCalendar } from "@ideastone_erp/js/college_calendar";
import { FacultyAttendancePage } from "@ideastone_erp/js/faculty_attendance";
import { OwnerFeesWorkspace } from "@ideastone_erp/js/owner_fees";
import { ExaminationsWorkspace } from "@ideastone_erp/js/examinations";

// Shared pages keep their original titles for other roles and for submodules.
for (const [Workspace, label] of [
    [AdmissionsWorkspace, "Admissions oversight"],
    [StudentsDirectoryWorkspace, "Student affairs"],
    [OwnerStaffDirectory, "Faculty oversight"],
    [CollegeCalendar, "Calendar"],
    [FacultyAttendancePage, "Attendance oversight"],
    [OwnerFeesWorkspace, "Finance oversight"],
    [ExaminationsWorkspace, "Examination oversight"],
]) {
    patch(Workspace.prototype, {
        setup() {
            super.setup(...arguments);
            const user = useService("user");
            onWillStart(async () => {
                this.principalHeadings = await user.hasGroup("ideastone_principal.group_principal");
            });
        },
        principalHeading(original, landing = true) {
            return this.principalHeadings && landing ? label : original;
        },
    });
}
