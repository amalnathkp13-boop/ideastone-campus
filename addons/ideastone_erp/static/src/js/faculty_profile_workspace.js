/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

const PAGES = {myprofile: "My staff profile", qualifications: "Staff qualifications and documents", development: "Faculty development and appraisal", agreements: "Salary agreements", monthly: "Monthly payroll", history: "Payroll History", leave: "Leave requests"};
const CATEGORIES = [{key:"all",name:"All activities",copy:"Complete portfolio view",icon:"▦"}, {key:"research",name:"Research",copy:"Publications, projects, patents",icon:"⌘",kinds:["paper","patent","mphil"]}, {key:"training",name:"Training programmes",copy:"FDP, workshops, seminars",icon:"▣",kinds:["training","fdp"]}, {key:"reviews",name:"Reviews, editorial & consultancy",copy:"Peer review and consultancy",icon:"◎",kinds:["review","mou","award","appraisal"]}, {key:"courses",name:"MOOC & qualified courses",copy:"Online and qualified courses",icon:"▤",kinds:["mooc","qualified"]}, {key:"vacation",name:"Summer / winter courses",copy:"Vacation course attendance",icon:"☼",kinds:["vacation"]}, {key:"guest",name:"Guest lecture / participation",copy:"Academic talks and participation",icon:"♧",kinds:["guest"]}, {key:"resource",name:"Resource person",copy:"Invited expert and facilitation roles",icon:"✦",kinds:["resource"]}];

class StaffRecordDialog extends Component {
    static template = "ideastone_erp.StaffRecordDialog";
    static components = {Dialog};
    static props = ["kind", "record", "data", "saved", "close"];
    setup() {
        this.orm = useService("orm"); this.action = useService("action");
        this.state = useState({busy:false,error:"",values:{name:"",kind:this.props.kind === "document" ? "document" : "fdp",campus_category:"academic",campus_expiry_date:"",date_from:this.props.data.today,date_to:"",campus_hours:0,description:"",...this.props.record,description:this.props.record?.description||"",date_to:this.props.record?.date_to||"",campus_expiry_date:this.props.record?.campus_expiry_date||""}});
    }
    get readOnly() { return this.props.kind === "agreement" || (this.props.kind === "activity" && this.props.record && this.props.record.state !== "draft"); }
    get title() { return this.props.record?.name || (this.props.kind === "document" ? "Upload document" : "Add development activity"); }
    async file(event) {
        this.state.error=""; const file=event.target.files[0]; if(!file)return;
        if(file.size>10*1024*1024){this.state.error="Choose a file up to 10 MB.";return;}
        try { const value=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(",")[1]);reader.onerror=reject;reader.readAsDataURL(file);});
            this.state.values[this.props.kind === "document" ? "document" : "evidence"]=value;this.state.values.filename=file.name;
        } catch {this.state.error="This file could not be read. Choose it again.";}
    }
    async save() {
        if(this.state.busy||this.readOnly)return; this.state.busy=true;this.state.error="";
        const keys=this.props.kind === "document" ? ["name","kind","campus_category","campus_expiry_date","document","filename"] : ["name","kind","date_from","date_to","campus_hours","description","evidence","filename"];
        const values=Object.fromEntries(keys.filter(k=>this.state.values[k]!==undefined).map(k=>[k,this.state.values[k] === "" ? false : this.state.values[k]]));
        values.campus_hours=Number(values.campus_hours || 0);if(this.props.kind === "document")delete values.campus_hours;
        try {await this.orm.call("campus.faculty.workspace","save_record",[this.props.kind,values,this.props.record?.id||0]);await this.props.saved();this.props.close();}
        catch(error){this.state.error=error.data?.message||"The record could not be saved.";}finally{this.state.busy=false;}
    }
    async attachment() {
        try{await this.action.doAction(await this.orm.call("campus.faculty.workspace","record_action",[this.props.kind,this.props.record.id]));}
        catch(error){this.state.error=error.data?.message||"The attachment could not be opened.";}
    }
}

export class FacultyProfileWorkspace extends Component {
    static template="ideastone_erp.FacultyProfileWorkspace";
    static props=["*"];
    setup(){
        this.orm=useService("orm");this.action=useService("action");this.dialog=useService("dialog");this.notification=useService("notification");
        const page=this.props.action?.params?.page||"myprofile";
        this.page=Object.hasOwn(PAGES,page)?page:"myprofile";
        this.state=useState({data:null,loading:true,busy:false,error:"",editing:false,profile:{},query:"",status:"",category:"all",month:"",year:"",report:"Complete History",slip:0,leaveDuration:"one",leaveView:"apply",leaveForm:{leave_type_id:"",date_from:"",date_to:"",from_session:"FN",to_session:"AN",reason:""}});
        this.request=0;onWillStart(()=>this.load());
    }
    async load(){const request=++this.request;this.state.loading=true;this.state.error="";try{const data=await this.orm.call("campus.faculty.workspace","get_workspace",[]);if(request!==this.request)return;this.state.data=data;this.state.profile=Object.fromEntries(["email","mobile","campus_emergency_phone","campus_communication_address"].map(k=>[k,data.profile[k]||""]));if(!data.payroll.some(p=>p.id===Number(this.state.slip)))this.state.slip=data.payroll[0]?.id||0;if(!this.state.leaveForm.date_from)this.resetLeave();}catch(error){if(request===this.request)this.state.error=error.data?.message||"Your staff workspace could not be loaded. Retry.";}finally{if(request===this.request)this.state.loading=false;}}
    get d(){return this.state.data;} get p(){return this.d.profile;} get title(){return PAGES[this.page];}
    get subtitles(){return {myprofile:"Keep your personal details accurate and your employment information up to date.",qualifications:"Manage academic credentials, identity records and required staff documentation.",development:"Manage your professional activities, appraisal evidence and annual development goals in one place.",agreements:"Review approved salary structures, effective dates and the status of agreement records.",monthly:"View the monthly salary breakdown, deductions, payment status and payslip availability.",history:"A clear view of your salary, contributions and payslips.",leave:""};}
    relation(value){return Array.isArray(value)?value[1]:value||"Not recorded";}
    initials(value){return String(value||"").trim().split(/\s+/).slice(0,2).map(w=>w[0]).join("").toUpperCase();}
    num(v){return new Intl.NumberFormat("en-IN",{maximumFractionDigits:2}).format(v||0);}
    money(v){return new Intl.NumberFormat("en-IN",{style:"currency",currency:this.d.currency,minimumFractionDigits:0,maximumFractionDigits:2}).format(v||0);}
    date(v){return v?new Date(String(v).slice(0,10)+"T12:00:00Z").toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric",timeZone:"UTC"}):"Not recorded";}
    period(v){return v?new Date(String(v).slice(0,10)+"T12:00:00Z").toLocaleDateString("en-GB",{month:"long",year:"numeric",timeZone:"UTC"}):"No approved payroll";}
    stateLabel(v){return {draft:"Draft",submitted:"Awaiting review",approved:"Approved",done:"Completed",cancelled:"Cancelled"}[v]||v;}
    tone(v){return ["verified","Verified","Approved","approved","done","Completed"].includes(v)?"green":["Pending","pending","submitted","Expiring soon","Draft","draft"].includes(v)?"amber":"blue";}
    get verified(){return this.d.documents.filter(r=>r.verification==="verified").length;}
    get activityVerified(){return this.d.activities.filter(r=>["approved","done"].includes(r.state)).length;}
    get evidenced(){return this.d.activities.filter(r=>r.filename).length;}
    get readiness(){return this.d.activities.length?Math.round(this.activityVerified/this.d.activities.length*100):0;}
    get categories(){return CATEGORIES.map(c=>({...c,count:this.d.activities.filter(r=>!c.kinds||c.kinds.includes(r.kind)).length}));}
    kindName(kind){return this.d.kinds.find(k=>k.id===kind)?.name||kind;}
    get documents(){return this.d.documents.filter(r=>(!this.state.status||r.status===this.state.status)&&r.name.toLowerCase().includes(this.state.query.toLowerCase()));}
    get activities(){const cat=CATEGORIES.find(c=>c.key===this.state.category);return this.d.activities.filter(r=>(!cat?.kinds||cat.kinds.includes(r.kind))&&(!this.state.status||(this.state.status==="Missing"?!r.filename:this.state.status==="Verified"?["approved","done"].includes(r.state):!!r.filename&&!["approved","done"].includes(r.state)))&&(r.name+" "+(r.description||"")).toLowerCase().includes(this.state.query.toLowerCase()));}
    get mphil(){return this.d.activities.filter(r=>r.kind==="mphil");}
    get agreement(){return this.d.agreements.find(r=>r.date_from<=this.d.today&&(!r.date_to||r.date_to>=this.d.today))||null;}
    get slip(){return this.d.payroll.find(r=>r.id===Number(this.state.slip))||null;}
    get history(){return this.d.payroll.filter(r=>(!this.state.year||r.date_from.slice(0,4)===this.state.year)&&(!this.state.month||Number(r.date_from.slice(5,7))===Number(this.state.month)));}
    get years(){return [...new Set(this.d.payroll.map(r=>r.date_from.slice(0,4)))];}
    get ytd(){const year=this.state.year||this.d.today.slice(0,4);let rows=this.d.payroll.filter(r=>r.date_from.slice(0,4)===year);return {year,pf:rows.reduce((a,r)=>a+r.pf,0),tds:rows.reduce((a,r)=>a+r.tds,0),count:rows.length};}
    get latest(){return this.history[0]||null;}
    get trend(){const rows=this.history.slice(0,12).reverse(),max=Math.max(...rows.map(r=>r.net),1);return rows.map(r=>({...r,height:Math.max(2,r.net/max*100)}));}
    get breakdown(){const s=this.slip;if(!s)return[];const basic=s.basic+s.allowance?Math.round(s.gross*s.basic/(s.basic+s.allowance)*100)/100:s.gross;return [["Basic pay (earned)","Earning",basic],["Allowances (earned)","Earning",s.gross-basic],["Provident fund","Deduction",s.pf],["ESI","Deduction",s.esi],["Income tax withholding","Deduction",s.tds],["Late punch deduction","Deduction",s.late_deduction],["Other deductions / advances","Deduction",s.deductions-s.pf-s.esi-s.tds-s.late_deduction]];}
    get details(){return [["Official email",this.p.email,"email"],["Mobile number",this.p.mobile,"mobile"],["Date of birth",this.date(this.p.birth_date)],["Gender",this.capitalize(this.p.gender)],["Department",this.relation(this.p.main_department_id)],["Designation",this.p.campus_designation],["Employee type",this.capitalize(this.p.campus_service_type)+" · Teaching"],["Reporting authority",this.relation(this.p.campus_reporting_id)],["Emergency contact",this.p.campus_emergency_phone,"campus_emergency_phone"],["Address",this.p.campus_communication_address,"campus_communication_address"]];}
    shortDate(value){return value?new Date(String(value).slice(0,10)+"T12:00:00Z").toLocaleDateString("en-GB",{day:"2-digit",month:"short",timeZone:"UTC"}):"Not set";}
    capitalize(value){return value?value[0].toUpperCase()+value.slice(1):"Not recorded";}
    longStat(value){return String(value).length>15;}
    monthName(value){return this.months[Number(value.slice(5,7))-1];}
    get months(){return ["January","February","March","April","May","June","July","August","September","October","November","December"];}
    get stats(){const docs=this.d.documents,activities=this.d.activities,a=this.agreement,l=this.d.leave;return {
        myprofile:[["Profile completion",this.p.completion+"%",this.p.missing+" details need attention","◔"],["Documents verified",this.verified+" / "+docs.length,"Saved qualification and document records","▤"],["Service tenure",this.p.tenure===null?"—":this.p.tenure+" yrs","Joined "+this.date(this.p.campus_joining_date),"◷"],["Next profile review",this.date(this.p.campus_profile_review_date),"Annual staff data review","▣"]],
        qualifications:[["Total documents",docs.length,"Academic credentials and staff records","▤"],["Verified",this.verified,"HR-verified records","✓"],["Pending review",docs.filter(r=>r.verification!=="verified").length,"Awaiting HR verification","◷"],["Expiring soon",docs.filter(r=>r.status==="Expiring soon"||r.status==="Expired").length,"Review validity date","⚑"]],
        development:[["Appraisal readiness",this.readiness+"%","Approved activities / recorded activities","◔"],["Activities recorded",activities.length,"Across research, training and service","▤"],["Development hours",this.num(activities.reduce((sum,r)=>sum+r.campus_hours,0))+" hrs","From saved development activities","◷"],["Evidence pending",activities.filter(r=>!r.filename).length,"Upload supporting documents","⚑"]],
        agreements:[["Current agreement",a?.name||"Not recorded","Approved and effective terms","▤"],["Effective from",this.date(a?.date_from),"Current salary agreement","▣"],["Basic monthly pay",a?this.money(a.basic):"—","Approved salary terms","₹"],["Agreement status",a?this.stateLabel(a.state):"No active agreement","HR / Finance approval","✓"]],
        history:[["Latest Net Salary",this.latest?this.money(this.latest.net):"—",this.period(this.latest?.date_from),"▣"],["YTD PF Contribution",this.money(this.ytd.pf),this.ytd.year+" · "+this.ytd.count+" payslips","▤"],["YTD TDS Deducted",this.money(this.ytd.tds),this.ytd.year+" · Approved payroll","％"],["Payslips Available",this.history.length,"Filtered approved salary records","▤"]],
        leave:[["Available Casual Leave",l.balance===null?"—":this.num(l.balance),"Leaves available for application","▦"],["This Month Eligibility",l.monthly_eligibility===null?"—":this.num(l.monthly_eligibility),"According to configured leave policy","▤"],["Approved Requests",l.approved_count,"Total approved leave applications","✓"],["Pending Approval",l.pending_count,"Leave applications awaiting approval","◷"]]
    }[this.page]||[];}
    get guidance(){return {
        myprofile:["AI profile assistant","Personalised checklist",`${this.p.missing} profile details remain incomplete. Keep contact and emergency details current.`,"Official employment details are maintained by HR. Contact your reporting authority for corrections.","Review bank details privately through the authorised payroll office."],
        qualifications:["Document intelligence","Completeness & validity",`${this.d.documents.length-this.verified} records still await verification. Only an authorised HR reviewer can verify evidence.`,"Check expiry dates and use a clear StaffID_DocumentType_Year filename.","Document checks do not certify authenticity."],
        development:["AI appraisal coach","Portfolio guidance · Advisory",`${this.d.activities.filter(r=>!r.filename).length} activities have no attached evidence. Add certificates or approved supporting proof.`,`${this.d.activities.filter(r=>r.state==='submitted').length} activities await an authorised reviewer.`,"Readiness reflects recorded approvals and does not determine an official appraisal score."],
        agreements:["AI agreement review","Consistency checks","Confirm the approved agreement is effective for the payroll period.","Changes to basic pay or allowances require authorised HR / Finance approval.","Salary documents are private. These checks do not determine salary entitlements."],
        monthly:["AI payroll assistant","Explain & verify","Gross earnings minus the listed deductions equals the displayed net pay.","Review changes against the previous month and raise unexplained differences with payroll.","Only approved campus payslips are shown. These checks do not change payroll or give tax advice."]
    }[this.page]||["Payroll insights","Recorded payroll",`${this.history.length} approved payslips match the selected period.`,`Recorded TDS for ${this.ytd.year}: ${this.money(this.ytd.tds)}.`,"Review late days and deductions against approved attendance records."];}
    get agreementDetails(){const a=this.agreement;return [["Employee",this.p.name+" · "+(this.p.campus_staff_code||"—")],["Designation",this.p.campus_designation],["Basic pay / month",a?this.money(a.basic):"—"],["Allowances / month",a?this.money(a.allowance):"—"],["Gross monthly pay",a?this.money(a.basic+a.allowance):"—"],["Effective date",this.date(a?.date_from)],["Approved by",this.relation(a?.approved_by)],["Review due",a?.date_to?this.date(a.date_to):"As per institutional policy"]];}
    async go(page){return this.action.doAction("ideastone_erp.action_faculty_profile_"+page);}
    async saveProfile(){if(!this.state.editing||this.state.busy)return;this.state.busy=true;this.state.error="";try{await this.orm.call("campus.faculty.workspace","save_profile",[this.state.profile]);await this.load();this.state.editing=false;this.notification.add("Contact details saved.",{type:"success"});}catch(error){this.state.error=error.data?.message||"Your profile could not be saved.";}finally{this.state.busy=false;}}
    edit(kind,record=null){this.dialog.add(StaffRecordDialog,{kind,record,data:this.d,saved:()=>this.load()});}
    async recordAction(kind,id){if(!id)return;try{const result=await this.orm.call("campus.faculty.workspace","record_action",[kind,id]);if(kind==="submit")await this.load();else await this.action.doAction(result);}catch(error){this.notification.add(error.data?.message||"This record could not be opened.",{type:"danger"});}}
    selectSlip(id){this.state.slip=Number(id);if(this.page!=="monthly")this.go("monthly");}
    async saveSupervision(event){event.preventDefault();if(this.state.busy)return;const form=event.target;this.state.busy=true;try{await this.orm.call("campus.faculty.workspace","save_record",["activity",{name:form.elements.student.value,kind:"mphil",date_from:form.elements.date.value,description:form.elements.remarks.value}]);form.reset();await this.load();}catch(error){this.notification.add(error.data?.message||"Supervision could not be saved.",{type:"danger"});}finally{this.state.busy=false;}}
    resetLeave(){const today=this.d.today;this.state.leaveDuration="one";this.state.leaveForm={leave_type_id:String(this.d.leave.leave_types[0]?.id||""),date_from:today,date_to:today,from_session:"FN",to_session:"AN",reason:""};}
    async submitLeave(event){event.preventDefault();if(this.state.busy)return;this.state.busy=true;this.state.error="";try{const values={...this.state.leaveForm,leave_type_id:Number(this.state.leaveForm.leave_type_id)};if(this.state.leaveDuration==="one")values.date_to=values.date_from;await this.orm.call("campus.faculty.leave.ui","submit_leave",[values]);await this.load();this.resetLeave();this.notification.add("Leave request submitted for review.",{type:"success"});}catch(error){this.state.error=error.data?.message||"Leave request could not be submitted.";}finally{this.state.busy=false;}}
    exportData(kind=this.page){let rows;if(kind==="history")rows=this.history.map(r=>({Period:this.period(r.date_from),...(!["Deductions only","Contributions only"].includes(this.state.report)?{Net:r.net}:{}),...(!["Salary only","Contributions only"].includes(this.state.report)?{Late_days:r.late_days,Late_deduction:r.late_deduction}:{}),...(!["Salary only","Deductions only"].includes(this.state.report)?{PF:r.pf,TDS:r.tds}:{})}));else if(kind==="myprofile")rows=this.details.map(r=>({Field:r[0],Value:r[1]||""}));else rows=kind==="development"?this.activities:kind==="agreements"?this.d.agreements:kind==="leave"?this.d.leave.history:this.documents;
        if(!rows.length){this.notification.add("No records match the selected filters.",{type:"info"});return;}const keys=Object.keys(rows[0]).filter(k=>k!=="id");const cell=v=>'"'+String(v??"").replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';const csv=[keys,...rows.map(r=>keys.map(k=>r[k]))].map(row=>row.map(cell).join(",")).join("\r\n");const url=URL.createObjectURL(new Blob(["\ufeff"+csv],{type:"text/csv;charset=utf-8"}));const link=document.createElement("a");link.href=url;link.download="faculty-"+kind+".csv";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
}
registry.category("actions").add("ideastone_erp.faculty_profile_workspace",FacultyProfileWorkspace);
