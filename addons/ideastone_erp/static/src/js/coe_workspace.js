/** @odoo-module **/
import { Component, onWillStart, onMounted, onWillUnmount, useRef, useEffect, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { FacultyQuestionPapers } from "./faculty_question_papers";

const examViews = ["records", "upcoming", "recent", "past", "timetable", "halls", "invigilation", "attendance", "evaluation", "results", "attention"];
const paperViews = ["papers", "received", "dispatch"];
export class COEWorkspace extends Component {
    static template = "ideastone_erp.COEWorkspace";
    static props = ["*"];
    setup() {
        this.orm = useService("orm"); this.action = useService("action");
        this.router = useService("router"); this.notification = useService("notification");
        this.dialogRef = useRef("coeDialog"); this.formRef = useRef("coeForm");
        this.view = this.props.action?.params?.view || "overview";
        const hash = this.router.current.hash;
        this.filtersKey = "campus-coe-filters:"+String(hash.cids || "default");
        let saved={};
        try {saved=JSON.parse(sessionStorage.getItem(this.filtersKey) || "{}");} catch { /* Ignore an expired filter preference. */ }
        this.state = useState({data:null, loading:false, busy:false, error:"", search:"", modal:null, form:{},
            year:String(hash.coe_year ?? saved.year ?? ""), department:String(hash.coe_department ?? saved.department ?? ""), study:String(hash.coe_study ?? saved.study ?? "")});
        onWillStart(() => this.load());
        onMounted(() => document.body.classList.add("campus_question_paper_shell"));
        onWillUnmount(() => document.body.classList.remove("campus_question_paper_shell"));
        useEffect(() => {if (this.state.modal) this.dialogRef.el?.querySelector("button")?.focus();}, () => [this.state.modal]);
    }
    async load() {
        this.state.loading = true; this.state.error = "";
        try {
            this.state.data = await this.orm.call("campus.coe.workspace", "get_workspace", [this.view,
                {year_id:this.state.year, department_id:this.state.department, study_year:this.state.study}]);
            this.state.year = String(this.state.data.year_id);
            sessionStorage.setItem(this.filtersKey,JSON.stringify({year:this.state.year,department:this.state.department,study:this.state.study}));
            this.router.pushState({coe_year:this.state.year, coe_department:this.state.department, coe_study:this.state.study});
        } catch (error) {this.state.error = error.data?.message || "The COE workspace could not be loaded. Retry.";}
        finally {this.state.loading = false;}
    }
    date(value, time=false) {return FacultyQuestionPapers.prototype.date.call(this,value,time);}
    get heading() {return this.state.data?.title || "COE workspace";}
    get isPaperView() {return paperViews.includes(this.view);}
    get isExamView() {return examViews.includes(this.view);}
    get caseView() {return this.view === "cases" || this.view === "attendance";}
    get subtitle() {
        return this.isPaperView ? "The HOD-selected official version, receipt and controlled dispatch in one place." :
            this.view === "overview" ? "One examination cell. Every department. Years I to IV." :
            "Examination records for the selected academic year, department and year of study.";
    }
    get exams() {return this.state.data?.exams || [];}
    get papers() {return this.state.data?.papers || [];}
    get tasks() {
        const c=this.state.data.counts;
        return [{label:"Official papers to acknowledge",count:c.unreceived,view:"papers",icon:"file-text-o"},
            {label:"Upcoming exams with allocation gaps",count:c.readiness,view:"attention",icon:"building-o"},
            {label:"Open examination cases",count:c.cases,view:"cases",icon:"flag-o"}];
    }
    get nextExams() {return this.exams.filter(r=>r.period === "upcoming").sort((a,b)=>a.start.localeCompare(b.start)).slice(0,5);}
    async navigate(view) {await this.action.doAction("ideastone_erp.action_coe_"+view);}
    get table() {
        const d=this.state.data;
        if(!d) return {columns:[],rows:[]};
        let columns=[], rows=[];
        const cols=(...items)=>items.map(([key,label])=>({key,label}));
        if(this.isPaperView) {
            columns=cols(["code","Paper / subject"],["staff","Author"],["department","Department / year"],["exam_date","Exam date"],["version","Official set"],["hod","Approved by"],["status","COE status"]);
            rows=this.papers.filter(r=>this.view !== "received" || r.received_at).filter(r=>this.view !== "dispatch" || r.dispatched_at)
                .map(r=>({...r,kind:"paper",raw:r,code:r.paper_code+" · "+r.subject,department:r.department+" · "+(r.study_year?"Year "+r.study_year:"Year not linked"),
                    exam_date:this.date(r.exam_date),version:r.sets[0]?.label || "—",
                    status:r.dispatched_at?"Dispatched":r.received_at?"Received":r.state === "approved"?"Awaiting HOD transfer":"Receipt pending"}));
        } else if(this.isExamView) {
            let exams=this.exams;
            if(["upcoming","recent","past"].includes(this.view)) exams=exams.filter(r=>r.period === this.view);
            if(this.view === "attention") exams=exams.filter(r=>r.period === "upcoming" && (!r.hall || !r.invigilator));
            if(this.view === "results") exams=exams.filter(r=>r.period !== "upcoming");
            columns=cols(["subject","Subject / examination"],["department","Department"],["year","Year"],["startLabel","Date & time"],["status","Status"]);
            if(["halls","timetable","invigilation","attention"].includes(this.view)) columns=cols(["subject","Subject"],["department","Department / year"],["startLabel","Date & time"],["hallLabel","Hall"],["invigilatorLabel","Invigilator"]);
            if(this.view === "attendance") columns=cols(["subject","Subject"],["department","Department"],["year","Year"],["candidates","Present / expected"],["status","Status"]);
            if(["evaluation","results"].includes(this.view)) columns=cols(["subject","Subject"],["department","Department / year"],["marks","Marks entered"],["due","Evaluation due"],["status","Result workflow"]);
            rows=exams.map(r=>({...r,raw:r,kind:"exam",year:"Year "+r.study_year,startLabel:this.date(r.start,true),
                hallLabel:r.hall || "Allocation needed",invigilatorLabel:r.invigilator || "Assignment needed",
                candidates:r.present+" / "+r.expected,marks:r.entered+" / "+r.roster+(r.roster?"":" · roster not loaded"),due:r.evaluation_due?this.date(r.evaluation_due):"Not set"}));
        } else if(this.view === "cases") {
            columns=cols(["name","Case"],["reference","Reference"],["exam","Examination"],["department","Department"],["status","Status"]);
            rows=d.cases.map(r=>({...r,raw:r,kind:"case",status:({open:"Open",review:"Under review",resolved:"Resolved"})[r.state]}));
        } else if(["departments","year-summary"].includes(this.view)) {
            columns=cols(["name","Department"],["one","Year I"],["two","Year II"],["three","Year III"],["four","Year IV"],["total","Examinations"],["papers","Official papers"]);
            rows=d.summaries.map(r=>({...r,kind:"summary",one:r.years[0],two:r.years[1],three:r.years[2],four:r.years[3]}));
        } else if(this.view === "years") {
            columns=cols(["name","Academic year"],["start","From"],["end","Until"]); rows=d.years.map(r=>({...r,kind:"year"}));
        } else if(this.view === "routes") {
            columns=cols(["department","Department"],["hod","HOD reviewer"],["coe","Exam control recipient"]); rows=d.routes.map(r=>({...r,kind:"route"}));
        } else if(this.view === "audit") {
            columns=cols(["action","Recorded action"],["actor","By"],["when","Time"],["reason","Reference / reason"]); rows=d.audit.map(r=>({...r,kind:"audit",when:this.date(r.at,true)}));
        }
        const q=this.state.search.trim().toLowerCase();
        return {columns,rows:rows.filter(r=>!q || columns.some(c=>String(r[c.key]??"").toLowerCase().includes(q)))};
    }
    actionable(row) {return ["paper","exam","case","summary","year"].includes(row.kind);}
    open(row) {
        if(row.kind === "summary") {this.state.department=String(row.id); return this.navigateWithFilters("records");}
        if(row.kind === "year") {this.state.year=String(row.id); return this.navigateWithFilters("records");}
        if(row.kind === "exam") this.state.form={coe_hall:row.raw.hall,coe_invigilator:row.raw.invigilator,
            coe_expected:row.raw.expected,coe_present:row.raw.present,coe_evaluation_due:row.raw.evaluation_due,
            coe_study_year:row.raw.study_year,note:row.raw.notes};
        if(row.kind === "case") this.state.form={name:row.raw.name,exam_id:String(row.raw.exam_id),kind:row.raw.kind,reference:row.raw.reference,note:row.raw.note,state:row.raw.state};
        if(row.kind === "paper") this.state.form={exam_id:String(row.raw.exam_id || ""),note:""};
        this.lastFocus=document.activeElement; this.state.modal=row;
    }
    navigateWithFilters(view) {this.router.pushState({coe_year:this.state.year,coe_department:this.state.department,coe_study:this.state.study});return this.navigate(view);}
    newCase() {this.lastFocus=document.activeElement;this.state.form={name:"",exam_id:"",kind:"revaluation",reference:"",note:"",state:"open"};this.state.modal={kind:"case",id:null};}
    close() {this.state.modal=null;this.lastFocus?.focus();}
    modalKey(event) {FacultyQuestionPapers.prototype.modalKey.call({...this,closeModal:()=>this.close()},event);}
    async save() {
        if(this.state.busy || !this.formRef.el?.reportValidity()) return;
        this.state.busy=true;
        try {
            const f={...this.state.form};
            if(this.state.modal.kind === "exam") {
                f.coe_expected=Number(f.coe_expected);f.coe_present=Number(f.coe_present); f.coe_evaluation_due=f.coe_evaluation_due || false;
                await this.orm.call("campus.coe.workspace","save_operations",[this.state.modal.id,f]);
            } else {
                f.exam_id=Number(f.exam_id);
                await this.orm.call("campus.coe.workspace","save_case",[f,this.state.modal.id]);
            }
            this.close(); await this.load(); this.notification.add("Examination record saved.",{type:"success"});
        } catch(error) {this.notification.add(error.data?.message || "The record could not be saved.",{type:"danger"});}
        finally {this.state.busy=false;}
    }
    async paperAction(action) {
        if(this.state.busy) return;
        this.state.busy=true;
        try {
            await this.orm.call("campus.coe.workspace","paper_action",[this.state.modal.id,action,this.state.form.note,Number(this.state.form.exam_id)||null]);
            this.close();await this.load();this.notification.add(action === "receive"?"Official paper receipt acknowledged.":"Dispatch recorded.",{type:"success"});
        } catch(error) {this.notification.add(error.data?.message || "The paper action could not be completed.",{type:"danger"});}
        finally {this.state.busy=false;}
    }
    download(item) {return FacultyQuestionPapers.prototype.download.call({...this,notice:(message,type)=>this.notification.add(message,{type})},item);}
    get dispatchExams() {const p=this.state.modal?.raw;return this.exams.filter(e=>e.subject_id===p?.subject_id && e.department_id===p?.department_id && e.period === "upcoming" && new Date(e.start.replace(" ","T")+"Z").toLocaleDateString("en-CA",{timeZone:"Asia/Kolkata"})===p.exam_date);}
    async marks() {await this.action.doAction(await this.orm.call("campus.coe.workspace","exam_action",[this.state.modal.id]));}
    async newExam() {await this.action.doAction(await this.orm.call("campus.coe.workspace","exam_action",[]));}
    exportCSV() {
        const {columns,rows}=this.table, quote=x=>'"'+String(x??"").replaceAll('"','""').replace(/^[=+@-]/,"'$&")+'"';
        const csv=[columns.map(c=>c.label),...rows.map(r=>columns.map(c=>r[c.key]))].map(r=>r.map(quote).join(",")).join("\r\n");
        const url=URL.createObjectURL(new Blob(["\ufeff"+csv],{type:"text/csv;charset=utf-8"}));
        const a=document.createElement("a");a.href=url;a.download="coe-"+this.view+".csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
}
registry.category("actions").add("ideastone_erp.coe_workspace",COEWorkspace);
