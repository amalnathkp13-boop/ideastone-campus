/** @odoo-module **/
import { useEffect, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { FacultyQuestionPapers, FacultySopPapers } from "./faculty_question_papers";

export class HODQuestionPapers extends FacultyQuestionPapers {
    static template = "ideastone_erp.HODQuestionPapers";
    static role = "hod";
    static components = { FacultySopPapers };
    setup() {
        super.setup();
        this.queue = useRef("reviewQueue");
        this.author = useRef("authorPanel");
        this.state.showAuthor = false;
        useEffect(() => {
            if (this.state.showAuthor) {
                this.author.el?.focus();
            }
        }, () => [this.state.showAuthor]);
    }
    get reviewRows() { return this.constructor.role === "coe" ? this.rows : this.rows.filter(r=>r.state === "submitted"); }
    get types() { return [...new Set((this.state.data?.rows || []).map(r=>r.exam_type))]; }
    get receivedSets() {
        return String(this.state.data.rows.reduce((total, row) => total + row.sets.length, 0)).padStart(2, "0");
    }
    view(row) {
        super.view(row);
        if (row.state === "submitted") this.state.selectedSet = "";
    }
    filterDepartment(id) {
        this.state.department=String(id);
        this.queue.el?.querySelector("input")?.focus();
    }
    openAuthor() {
        if (this.state.showAuthor) this.author.el?.focus();
        else this.state.showAuthor = true;
    }
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
