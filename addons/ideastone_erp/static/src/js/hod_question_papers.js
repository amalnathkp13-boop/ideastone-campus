/** @odoo-module **/
import { registry } from "@web/core/registry";
import { FacultyQuestionPapers } from "./faculty_question_papers";

export class HODQuestionPapers extends FacultyQuestionPapers {
    static template = "ideastone_erp.HODQuestionPapers";
    static role = "hod";
    get reviewRows() { return this.constructor.role === "coe" ? this.rows : this.rows.filter(r=>r.state === "submitted"); }
    get types() { return [...new Set((this.state.data?.rows || []).map(r=>r.exam_type))]; }
    filterDepartment(id) { this.state.department=String(id); }
    async decide(decision, row=this.state.modal) {
        const id=row?.id;
        await super.decide(decision,row);
        const saved=this.state.data?.rows.find(r=>r.id===id);
        if(decision === "approve" && saved?.state === "approved") this.view(saved);
    }
    openHistory() { this.lastFocus=document.activeElement; this.state.modal=null; this.state.history=true; }
}
class COEQuestionPapers extends HODQuestionPapers { static role="coe"; }
registry.category("actions").add("ideastone_erp.hod_question_papers",HODQuestionPapers);
registry.category("actions").add("ideastone_erp.coe_question_papers",COEQuestionPapers);
