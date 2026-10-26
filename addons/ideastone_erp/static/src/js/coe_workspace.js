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
        this.dialogRef = useRef("coeDialog"); this.formRef = useRef("coeForm"); this.pageRef = useRef("coePage");
        this.view = this.props.action?.params?.view || "overview";
        const hash = this.router.current.hash;
        this.filtersKey = "campus-coe-filters:"+String(hash.cids || "default");
        let saved={};
        try {saved=JSON.parse(sessionStorage.getItem(this.filtersKey) || "{}");} catch { /* Ignore an expired filter preference. */ }
        const restored=this.props.action?.context?.coe_filters;
        this.requestId=0;
        this.state = useState({data:null, loading:false, busy:false, error:"", search:"", subject:"", modal:null, form:{},
            year:String(restored?.year ?? hash.coe_year ?? saved.year ?? ""),
            department:String(restored?.department ?? hash.coe_department ?? saved.department ?? ""),
            study:String(restored?.study ?? hash.coe_study ?? saved.study ?? "")});
        onWillStart(() => this.load());
        onMounted(() => document.body.classList.add("campus_question_paper_shell"));
        onWillUnmount(() => {this.requestId++;document.body.classList.remove("campus_question_paper_shell");});
        useEffect(() => {if (this.state.modal) this.dialogRef.el?.querySelector("button")?.focus();}, () => [this.state.modal]);
    }
    async load() {
        const request=++this.requestId;
        const scope={year:this.state.year,department:this.state.department,study:this.state.study};
        this.state.loading = true; this.state.error = "";
        this.persistFilters();
        try {
            const data = await this.orm.call("campus.coe.workspace", "get_workspace", [this.view,
                {year_id:scope.year, department_id:scope.department, study_year:scope.study}]);
            if(request !== this.requestId) return;
            this.state.data=data; this.state.year=String(data.year_id);
            this.persistFilters();
        } catch (error) {if(request === this.requestId) this.state.error = error.data?.message || "The COE workspace could not be loaded. Retry.";}
        finally {if(request === this.requestId) this.state.loading = false;}
    }
    persistFilters() {
        const scope={year:this.state.year,department:this.state.department,study:this.state.study};
        sessionStorage.setItem(this.filtersKey,JSON.stringify(scope));
        this.router.pushState({coe_year:scope.year,coe_department:scope.department,coe_study:scope.study});
        return scope;
    }
    async changeFilter(key,event) {
        this.state[key]=event.target.value;
        if(key === "department") this.state.study="";
        this.state.subject="";this.state.search="";
        await this.load();this.pageRef.el?.scrollTo({top:0});
    }
    async resetFilters() {
        this.state.year=String(this.state.data?.default_year_id || "");
        this.state.department="";this.state.study="";this.state.subject="";this.state.search="";
        await this.load();this.pageRef.el?.scrollTo({top:0});
    }
    async selectDepartment(id="") {
        this.state.department=String(id);this.state.study="";this.state.subject="";this.state.search="";
        if(this.view === "overview" && id) return this.navigate("records");
        await this.load();this.pageRef.el?.scrollTo({top:0});
    }
    async selectStudy(year="") {
        this.state.study=String(year);this.state.subject="";this.state.search="";
        if(this.view === "overview" && year) return this.navigate("records");
        await this.load();this.pageRef.el?.scrollTo({top:0});
    }
    selectSubject(id="") {this.state.subject=String(id);this.state.search="";this.pageRef.el?.scrollTo({top:0});}
    date(value, time=false) {return FacultyQuestionPapers.prototype.date.call(this,value,time);}
    get heading() {return this.state.data?.title || "COE workspace";}
    get isPaperView() {return paperViews.includes(this.view);}
    get isExamView() {return examViews.includes(this.view);}
    get isReportView() {return ["departments","year-summary"].includes(this.view);}
    get isGroupedView() {return this.isExamView || this.isPaperView || this.isReportView || ["cases","audit"].includes(this.view);}
    get showRegister() {
        if(this.view === "routes") return Boolean(this.state.department);
        if(this.view === "years") return false;
        return !this.isGroupedView || Boolean(this.state.department && this.state.study && this.state.subject);
    }
    get departmentName() {return this.state.data?.departments.find(d=>d.id===Number(this.state.department))?.name || "";}
    get studyLabel() {return this.state.study === "unassigned" ? "Needs year assignment" : "Year "+({1:"I",2:"II",3:"III",4:"IV"}[this.state.study] || "");}
    get subjectName() {return this.state.data?.subject_progress.find(s=>s.subject_id===Number(this.state.subject))?.subject || "";}
    get caseView() {return this.view === "cases" || this.view === "attendance";}
    get subtitle() {
        return this.view === "papers" ? "Browse each department and year to track subjects, HOD updates and official question papers." :
            this.isPaperView ? "The HOD-selected official version, receipt and controlled dispatch in one place." :
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
    async navigate(view) {await this.action.doAction("ideastone_erp.action_coe_"+view,{additionalContext:{coe_filters:this.persistFilters()}});}
    get register() {
        const d=this.state.data;
        if(!d) return {columns:[],rows:[]};
        let columns=[], rows=[];
        const cols=(...items)=>items.map(([key,label])=>({key,label}));
        if(this.isPaperView) {
            columns=cols(["code","Paper / subject"],["staff","Author"],["department","Department / year"],["exam_date","Exam date"],["version","Official set"],["hod","Approved by"],["status","COE status"]);
            rows=this.papers.filter(r=>this.view !== "received" || r.received_at).filter(r=>this.view !== "dispatch" || r.dispatched_at)
                .map(r=>({...r,kind:"paper",raw:r,code:r.paper_code+" · "+r.subject,department:r.department+" · "+(r.study_year?"Year "+r.study_year:"Needs year assignment"),
                    exam_date:this.date(r.exam_date),version:r.sets[0]?.label || "—",
                    status:r.dispatched_at?"Dispatched":r.received_at?"Received":r.state === "approved"?"Awaiting HOD transfer":"Receipt pending"}));
        } else if(this.isExamView || this.isReportView) {
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
        } else if(this.view === "years") {
            columns=cols(["name","Academic year"],["start","From"],["end","Until"]); rows=d.years.map(r=>({...r,kind:"year"}));
        } else if(this.view === "routes") {
            columns=cols(["department","Department"],["hod","HOD reviewer"],["coe","Exam control recipient"]); rows=d.routes.map(r=>({...r,kind:"route"}));
        } else if(this.view === "audit") {
            columns=cols(["action","Recorded action"],["actor","By"],["when","Time"],["reason","Reference / reason"]); rows=d.audit.map(r=>({...r,kind:"audit",when:this.date(r.at,true)}));
        }
        return {columns,rows};
    }
    get table() {
        const {columns,rows}=this.register,q=this.state.search.trim().toLowerCase();
        return {columns,rows:rows.filter(r=>(!this.state.subject || this.state.subject === "all" || r.subject_id===Number(this.state.subject))
            && (!q || columns.some(c=>String(r[c.key]??"").toLowerCase().includes(q))))};
    }
    get progressSubjects() {
        let entries=this.state.data?.subject_progress || [];
        const records=this.register.rows;
        if(this.isExamView || ["cases","audit","received","dispatch"].includes(this.view)) {
            const ids=new Set(records.map(r=>r.subject_id));
            entries=entries.filter(s=>ids.has(s.subject_id));
        }
        return entries.map(s=>{const statuses=[...new Set(s.updates.map(u=>u.status))];
            const latest=[...s.updates].sort((a,b)=>b.updated.localeCompare(a.updated))[0],route=this.state.data.routes.find(r=>r.id===s.department_id);
            return {...s,id:s.department_id+":"+(s.study_year||"unassigned")+":"+s.subject_id,
                latest,hod:latest?.hod || route?.hod || "Not configured",
                status:statuses.length?statuses.join(" · "):"Awaiting submission",
                pending:s.updates.filter(u=>["submitted","returned"].includes(u.state)).length,
                approved:s.updates.filter(u=>["approved","forwarded"].includes(u.state)).length,
                records:records.filter(r=>r.subject_id===s.subject_id && r.department_id===s.department_id).length};
        }).sort((a,b)=>a.subject.localeCompare(b.subject));
    }
    get departmentCards() {
        const progress=this.progressSubjects;
        return (this.state.data?.departments || []).map(d=>{const subjects=progress.filter(s=>s.department_id===d.id);
            const route=this.state.data.routes.find(r=>r.id===d.id);
            return {...d,subjects:subjects.length,records:subjects.reduce((n,s)=>n+s.records,0),
                pending:subjects.reduce((n,s)=>n+s.pending,0),approved:subjects.reduce((n,s)=>n+s.approved,0),
                hod:route?.hod || "Not configured"};});
    }
    get activeDepartments() {return this.departmentCards.filter(d=>this.view === "routes" || d.subjects);}
    get emptyDepartments() {return this.departmentCards.filter(d=>this.view !== "routes" && !d.subjects);}
    get yearCards() {
        const progress=this.progressSubjects;
        return ["1","2","3","4","unassigned"].map(year=>{const subjects=progress.filter(s=>s.department_id===Number(this.state.department) && (s.study_year||"unassigned")===year);
            return {id:year,label:year === "unassigned"?"Needs year assignment":"Year "+({1:"I",2:"II",3:"III",4:"IV"})[year],
                subjects:subjects.length,pending:subjects.reduce((n,s)=>n+s.pending,0),approved:subjects.reduce((n,s)=>n+s.approved,0)};
        }).filter(y=>y.id !== "unassigned" || y.subjects);
    }
    get visibleSubjects() {const q=this.state.search.trim().toLowerCase();return this.progressSubjects.filter(s=>s.department_id===Number(this.state.department)
        && (s.study_year||"unassigned")===this.state.study && (!q || (s.subject+" "+s.code+" "+s.hod+" "+s.status).toLowerCase().includes(q)));}
    actionable(row) {return ["paper","exam","case","summary","year"].includes(row.kind);}
    open(row) {
        if(row.kind === "summary") {this.state.department=String(row.id); return this.navigateWithFilters("records");}
        if(row.kind === "year") {this.state.year=String(row.id);this.state.department="";this.state.study="";this.state.subject="";return this.navigate("records");}
        if(row.kind === "exam") this.state.form={coe_hall:row.raw.hall,coe_invigilator:row.raw.invigilator,
            coe_expected:row.raw.expected,coe_present:row.raw.present,coe_evaluation_due:row.raw.evaluation_due,
            coe_study_year:row.raw.study_year,note:row.raw.notes};
        if(row.kind === "case") this.state.form={name:row.raw.name,exam_id:String(row.raw.exam_id),kind:row.raw.kind,reference:row.raw.reference,note:row.raw.note,state:row.raw.state};
        if(row.kind === "paper") this.state.form={exam_id:String(row.raw.exam_id || ""),note:""};
        this.lastFocus=document.activeElement; this.state.modal=row;
    }
    navigateWithFilters(view) {return this.navigate(view);}
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
        let {columns,rows}=this.table;
        if(this.isReportView && !this.state.subject) {
            columns=[["name","Department"],["one","Year I"],["two","Year II"],["three","Year III"],["four","Year IV"],["total","Examinations"],["papers","Official papers"]].map(([key,label])=>({key,label}));
            rows=this.state.data.summaries.map(r=>({...r,one:r.years[0],two:r.years[1],three:r.years[2],four:r.years[3]}));
        }
        const quote=x=>'"'+String(x??"").replaceAll('"','""').replace(/^[=+@-]/,"'$&")+'"';
        const csv=[columns.map(c=>c.label),...rows.map(r=>columns.map(c=>r[c.key]))].map(r=>r.map(quote).join(",")).join("\r\n");
        const url=URL.createObjectURL(new Blob(["\ufeff"+csv],{type:"text/csv;charset=utf-8"}));
        const a=document.createElement("a");a.href=url;a.download="coe-"+this.view+".csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
}
registry.category("actions").add("ideastone_erp.coe_workspace",COEWorkspace);
