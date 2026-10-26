/** @odoo-module **/
import { Component, onWillStart, onMounted, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const emptyForm = () => ({ department_id: "", subject_id: "", exam_type: "", exam_date: "", paper_code: "", duration: "3 hours", notes: "" });

export class FacultyQuestionPapers extends Component {
    static template = "ideastone_erp.FacultyQuestionPapers";
    static props = ["*"];
    static role = "faculty";
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.formRef = useRef("paperForm");
        this.dialogRef = useRef("paperDialog");
        this.state = useState({ data: null, busy: false, error: "", form: emptyForm(), id: null,
            levels: { balanced: true, moderate: false, advanced: false }, files: {}, search: "", filter: "",
            department: "", examType: "", modal: null, selectedSet: "", note: "", history: false });
        this.levels = [{ key: "balanced", label: "Balanced", hint: "Mixed difficulty" },
            { key: "moderate", label: "Moderate", hint: "Core concepts" }, { key: "advanced", label: "Advanced", hint: "Higher-order problems" }];
        this.examTypes = ["Internal Assessment — CAT I", "Internal Assessment — CAT II", "Internal Assessment — CAT III",
            "University Semester Examination", "Model Examination", "Campus / Certification Examination"];
        onWillStart(() => this.load());
        onMounted(() => document.body.classList.add("campus_question_paper_shell"));
        onWillUnmount(() => document.body.classList.remove("campus_question_paper_shell"));
        useEffect(() => { if(this.state.modal || this.state.history) this.dialogRef.el?.querySelector('button')?.focus(); }, () => [this.state.modal, this.state.history]);
    }
    async load() {
        try { this.state.data = await this.orm.call("campus.question.paper", "get_workspace", [this.constructor.role]); this.state.error = ""; }
        catch (error) { this.state.error = error.data?.message || "The question-paper workspace could not be loaded. Retry."; }
    }
    get rows() {
        const q = this.state.search.toLowerCase().trim();
        return (this.state.data?.rows || []).filter(r => (!q || `${r.subject} ${r.staff} ${r.exam_type} ${r.paper_code}`.toLowerCase().includes(q))
            && (!this.state.filter || r.state === this.state.filter)
            && (!this.state.department || r.department_id === Number(this.state.department))
            && (!this.state.examType || r.exam_type === this.state.examType));
    }
    get subjects() { return (this.state.data?.subjects || []).filter(s => !this.state.form.department_id || s.department_id === Number(this.state.form.department_id)); }
    get events() { return (this.state.data?.rows || []).flatMap(r => r.history.map((e,index) => ({ ...e, subject: r.subject, key: `${r.id}-${index}`, order:index }))).sort((a,b) => b.at.localeCompare(a.at) || b.order-a.order).slice(0, 8); }
    get departmentCards() { return (this.state.data?.departments || []).map(d => { const rows=this.state.data.rows.filter(r => r.department_id===d.id); const reviewed=rows.filter(r => ["approved","forwarded"].includes(r.state)).length; return {...d,total:rows.length, reviewed, pending:rows.filter(r=>r.state==="submitted").length, percent:rows.length?Math.round(reviewed*100/rows.length):0}; }); }
    count(key) { const counts=this.state.data?.counts || {}; return String((counts[key] || 0) + (key === "approved" ? counts.forwarded || 0 : 0)).padStart(2,"0"); }
    tone(state) { return ({submitted:"review",approved:"approved",returned:"returned",forwarded:"forwarded"})[state] || "draft"; }
    date(value, time=false) {
        if (!value) return "—";
        return new Intl.DateTimeFormat("en-IN", {day:"2-digit",month:"short",year:"numeric", ...(time?{hour:"2-digit",minute:"2-digit"}:{})}).format(new Date(time?value.replace(" ","T")+"Z":value+"T00:00:00"));
    }
    notice(text, type="info") { this.notification.add(text,{type}); }
    guide() { this.notice("Select your assigned department and subject. Upload one PDF per difficulty set, save a draft or submit to your HOD. Returned papers can be revised; approved papers are locked."); }
    newPaper() { this.state.form=emptyForm(); this.state.id=null; this.state.files={}; this.state.levels={balanced:true,moderate:false,advanced:false}; this.state.modal=null; this.formRef.el?.scrollIntoView({behavior:"smooth",block:"start"}); }
    departmentChanged() { this.state.form.subject_id=""; this.state.form.paper_code=""; }
    subjectChanged() { const s=this.state.data.subjects.find(s=>s.id===Number(this.state.form.subject_id)); if(s) { this.state.form.paper_code=s.code || ""; this.state.form.department_id=String(s.department_id); } }
    async upload(level, event) {
        const file=event.target.files?.[0] || event.dataTransfer?.files?.[0];
        if (!file) return;
        if (!file.name.toLowerCase().endsWith(".pdf") || file.size>20*1024*1024) { this.notice("Choose a PDF up to 20 MB.","warning"); return; }
        const reader=new FileReader();
        reader.onload=()=>{this.state.files[level]={level,filename:file.name,content:reader.result.split(",")[1]};};
        reader.onerror=()=>this.notice("The file could not be read. Please choose it again.","danger");
        reader.readAsDataURL(file);
    }
    drop(level,event) { event.preventDefault(); this.upload(level,event); }
    existing(level) { return this.state.data?.rows.find(r=>r.id===this.state.id)?.sets.find(s=>s.level===level); }
    async save(submit=false, readiness=false) {
        if(this.state.busy) return;
        if (!this.formRef.el?.reportValidity()) return;
        const files=this.levels.filter(l=>this.state.levels[l.key]).map(l=>this.state.files[l.key]).filter(Boolean);
        const missing=this.levels.filter(l=>this.state.levels[l.key] && !this.state.files[l.key] && !this.existing(l.key));
        if ((submit || readiness) && missing.length) { this.notice(`Attach a PDF for: ${missing.map(l=>l.label).join(", ")}.`,"warning"); return; }
        this.state.busy=true;
        try {
            const values={...this.state.form,department_id:Number(this.state.form.department_id),subject_id:Number(this.state.form.subject_id)};
            this.state.id=await this.orm.call("campus.question.paper","save_submission",[values,files,this.state.id,submit,this.levels.filter(l=>this.state.levels[l.key]).map(l=>l.key)]);
            this.state.files={};
            await this.load();
            if(readiness) this.notice("Draft saved. PDF format, size, encryption and page count passed. Syllabus coverage, marks, difficulty and duplicates still require academic review.","success");
            else this.notice(submit?"Question-paper sets submitted to your department HOD.":"Draft saved.","success");
            if(submit) this.newPaper();
        } catch(error) { this.notice(error.data?.message || "The submission could not be saved. Please retry.","danger"); }
        finally {this.state.busy=false;}
    }
    view(row) { this.lastFocus=document.activeElement; this.state.modal=row; this.state.selectedSet=String(row.selected_set_id || row.sets[0]?.id || ""); this.state.note=""; this.state.history=false; }
    closeModal() { this.state.modal=null; this.state.history=false; this.lastFocus?.focus(); }
    modalKey(event) {
        if(event.key === "Escape") { event.stopPropagation(); this.closeModal(); }
        if(event.key !== "Tab") return;
        const nodes=[...(this.dialogRef.el?.querySelectorAll('button:not(:disabled),input,textarea,a[href],select') || [])];
        const first=nodes[0], last=nodes[nodes.length-1];
        if(event.shiftKey && document.activeElement===first) { event.preventDefault(); last?.focus(); }
        else if(!event.shiftKey && document.activeElement===last) { event.preventDefault(); first?.focus(); }
    }
    edit(row) {
        this.state.form=Object.fromEntries(Object.keys(emptyForm()).map(k=>[k,row[k] ?? ""]));
        this.state.id=row.id; this.state.files={}; this.state.modal=null;
        for(const l of this.levels) this.state.levels[l.key]=row.sets.some(s=>s.level===l.key);
        if(!row.sets.length) this.state.levels.balanced=true;
        this.formRef.el?.scrollIntoView({behavior:"smooth",block:"start"});
    }
    async download(item) {
        try {
            const data=await this.orm.call("campus.question.paper","download_set",[item.id]);
            const bytes=Uint8Array.from(atob(data.content),c=>c.charCodeAt(0));
            const url=URL.createObjectURL(new Blob([bytes],{type:"application/pdf"}));
            const link=document.createElement("a"); link.href=url; link.download=data.filename; link.click();
            setTimeout(()=>URL.revokeObjectURL(url),1000);
        } catch(error) { this.notice(error.data?.message || "The PDF could not be opened.","danger"); }
    }
    async decide(decision, row=this.state.modal) {
        if(this.state.busy || !row) return;
        this.state.busy=true;
        try {
            await this.orm.call("campus.question.paper","decide",[row.id,decision,Number(this.state.selectedSet)||null,this.state.note]);
            this.state.modal=null; await this.load(); this.notice("Review saved. The faculty submission status is updated.","success");
        } catch(error) {this.notice(error.data?.message || "Review could not be saved. Refresh and retry.","danger");}
        finally {this.state.busy=false;}
    }
    exportCSV() {
        const quote=x=>'"'+String(x??"").replaceAll('"','""').replace(/^[=+@-]/,"'$&")+'"';
        const csv=[["Subject","Staff","Department","Examination","Exam date","Status"],...this.rows.map(r=>[r.subject,r.staff,r.department,r.exam_type,r.exam_date,r.status])].map(r=>r.map(quote).join(",")).join("\r\n");
        const url=URL.createObjectURL(new Blob(["\ufeff"+csv],{type:"text/csv;charset=utf-8"})); const a=document.createElement("a"); a.href=url;a.download="question-paper-status.csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
}
registry.category("actions").add("ideastone_erp.faculty_question_papers",FacultyQuestionPapers);
