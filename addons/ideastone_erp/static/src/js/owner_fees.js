/** @odoo-module **/
import {Component, onWillStart, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {Dialog} from "@web/core/dialog/dialog";

const PAGES = {overview:"Financial overview", heads:"Fee heads", structures:"Fee structures", accounts:"Student fee accounts", assign:"Assign fee structure", invoices:"Invoices & dues", followup:"Overdue follow-up", receipts:"Receipts"};
const FREQUENCIES = {semester:"Semester", annual:"Annual", monthly:"Monthly", once:"One-time", exam:"Per exam", term:"Term"};

class FeesDialog extends Component {
    static template="ideastone_erp.OwnerFeesDialog";
    static components={Dialog};
    static props=["kind","workspace","record?","values?","close"];
    setup(){
        this.orm=useService("orm");this.action=useService("action");
        this.state=useState({busy:false,error:"",prepared:0,values:{name:"",default_code:"",campus_fee_category:"academic",campus_fee_frequency:"semester",campus_fee_optional:false,property_account_income_id:"",tax_id:"",year_id:this.w.state.year,course_id:"",term_id:"",quota:"gq",study_year:"1",effective:this.d.today,lines:[this.newLine()],invoice_id:"",amount:"",method:"cash",reference:"",journal_id:"",note:"",channel:"phone",outcome:"",next_action:"",next_date:this.d.today,promise:false,enrolment_id:"",product_id:"",date:this.d.today,...this.props.values}});
    }
    get w(){return this.props.workspace;}get d(){return this.w.d;}
    get title(){return {head:"New fee head",plan:"New fee structure",payment:"Record payment",contact:"Log contact",invoice:"Create invoice",detail:this.props.record?.name||"Department fee structures"}[this.props.kind];}
    get journals(){return this.d.journals.filter(j=>j.type===(this.state.values.method==="cash"?"cash":"bank"));}
    get unpaid(){return this.d.invoices.filter(i=>i.state==="posted"&&i.balance>0);}
    get terms(){return this.d.terms.filter(t=>!t.course_id||t.course_id===Number(this.state.values.course_id));}
    get departmentPlans(){return this.d.plans.filter(p=>p.department_id===this.props.record?.id);}
    newLine(){return {uid:Math.random().toString(36).slice(2),product_id:"",amount:"",date:"",days:0};}
    addLine(){this.state.values.lines.push(this.newLine());}
    removeLine(line){this.state.values.lines.splice(this.state.values.lines.indexOf(line),1);}
    async save(){
        if(this.state.busy)return;this.state.busy=true;this.state.error="";
        const v=this.state.values;
        try{
            if(this.props.kind==="head")await this.orm.call("campus.owner.fees","save_head",[{name:v.name,default_code:v.default_code,campus_fee_category:v.campus_fee_category,campus_fee_frequency:v.campus_fee_frequency,campus_fee_optional:v.campus_fee_optional,property_account_income_id:Number(v.property_account_income_id)||false,tax_id:Number(v.tax_id)||false},this.props.record?.id||0]);
            if(this.props.kind==="plan")await this.orm.call("campus.owner.fees","save_plan",[{name:v.name,year_id:Number(v.year_id),course_id:Number(v.course_id),term_id:Number(v.term_id)||false,quota:v.quota,study_year:Number(v.study_year),effective:v.effective||false,lines:v.lines.map(l=>({product_id:Number(l.product_id),amount:Number(l.amount),date:l.date||false,days:Number(l.days||0)}))}]);
            if(this.props.kind==="contact")await this.orm.call("campus.owner.fees","log_contact",[{invoice_id:Number(v.invoice_id),channel:v.channel,outcome:v.outcome,next_action:v.next_action,next_date:v.next_date,promise:v.promise}]);
            if(this.props.kind==="invoice"){
                const id=await this.orm.call("campus.owner.fees","create_invoice",[{enrolment_id:Number(v.enrolment_id),product_id:Number(v.product_id),amount:Number(v.amount),date:v.date}]);
                await this.w.load();this.props.close();await this.w.openRecord("invoice",id);return;
            }
            if(this.props.kind==="payment"){
                if(!this.state.prepared)this.state.prepared=await this.orm.call("campus.owner.fees","prepare_payment",[{invoice_id:Number(v.invoice_id),amount:Number(v.amount),method:v.method,reference:v.reference,journal_id:Number(v.journal_id)||this.journals[0]?.id||0,note:v.note}]);
                const receipt=await this.orm.call("campus.owner.fees","post_payment",[this.state.prepared]);
                await this.w.load();this.props.close();await this.action.doAction(receipt);return;
            }
            await this.w.load();this.props.close();
        }catch(error){this.state.error=error.data?.message||"The record could not be saved. Retry using the same payment request if the connection was interrupted.";if(/ValidationError|UserError|AccessError/.test(error.data?.name||""))this.state.prepared=0;}
        finally{this.state.busy=false;}
    }
    async planAction(plan,action){
        if(this.state.busy)return;this.state.busy=true;this.state.error="";
        try{await this.orm.call("campus.owner.fees","plan_action",[plan.id,action]);await this.w.load();}
        catch(error){this.state.error=error.data?.message||"The structure could not be updated.";}finally{this.state.busy=false;}
    }
    copyPlan(plan){this.props.close();this.w.edit("plan",null,{name:plan.name+" · new version",year_id:this.w.state.year,course_id:plan.course_id,term_id:plan.term_id||"",quota:plan.quota||"gq",study_year:plan.study_year,effective:this.d.today,lines:plan.lines.map(l=>({...this.newLine(),product_id:l.product_id,amount:l.amount,date:l.date,days:l.days}))});}
}

export class OwnerFeesWorkspace extends Component {
    static template="ideastone_erp.OwnerFeesWorkspace";
    static props=["*"];
    setup(){
        this.orm=useService("orm");this.action=useService("action");this.dialog=useService("dialog");this.notification=useService("notification");
        const page=this.props.action?.params?.page||"overview";this.page=Object.hasOwn(PAGES,page)?page:"overview";
        this.state=useState({data:null,loading:true,busy:false,error:"",year:Number(this.props.action?.context?.campus_fee_year)||0,month:"",query:"",quota:"all",status:"all",course:"0",due:"all",method:"all",assignment:{course_id:"0",plan_id:"",batch_id:"0",term_id:"0",date:""},preview:null});
        this.request=0;onWillStart(()=>this.load());
    }
    get d(){return this.state.data;}get title(){return PAGES[this.page];}
    get year(){return this.d.years.find(y=>y.id===Number(this.state.year));}
    money(value){return this.d.symbol+" "+new Intl.NumberFormat("en-IN",{maximumFractionDigits:2}).format(value||0);}
    compact(value){const n=Math.abs(value),scale=n>=1e7?1e7:n>=1e5?1e5:1;return this.money(value/scale)+(scale===1e7?" Cr":scale===1e5?" L":"");}
    lakh(value){return this.money(value/100000)+" L";}
    date(value){return value?new Date(value.slice(0,10)+"T12:00:00Z").toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric",timeZone:"UTC"}):"—";}
    monthName(value,short=false){return new Date(value.slice(0,7)+"-15T12:00:00Z").toLocaleDateString("en-GB",{month:short?"short":"long",...(short?{}:{year:"numeric"}),timeZone:"UTC"});}
    monthOnly(value){return new Date(value.slice(0,7)+"-15T12:00:00Z").toLocaleDateString("en-GB",{month:"long",timeZone:"UTC"});}
    percent(amount,target){return target?new Intl.NumberFormat("en-IN",{maximumFractionDigits:0}).format(amount/target*100)+"%":"—";}
    label(value){return {academic:"Academic",facilities:"Facilities",services:"Services",student_services:"Student services",draft:"Draft",review:"Needs review",published:"Published",configured:"Configured",gq:"Government Quota",mq:"Management Quota",...FREQUENCIES}[value]||value;}
    tone(value){return ["Published","published","Paid","Active","Settled","Recorded"].includes(value)?"green":["Overdue","Unpaid","Reversed"].includes(value)?"red":"amber";}
    get snapshot(){return this.d.monthly.find(r=>r.key===this.state.month)||this.d.monthly[0]||{income:0,expense:0,scheduled:0,date:this.d.today};}
    get chartMax(){return Math.max(1,...this.d.monthly.flatMap(m=>[Math.abs(m.income),Math.abs(m.expense)]));}
    barStyle(value){return "height:"+Math.abs(value)/this.chartMax*100+"%;"+(value<0?"background:#c94c55":"");}
    matches(row){return JSON.stringify(row).toLowerCase().includes(this.state.query.toLowerCase());}
    get heads(){return this.d.heads.filter(r=>this.matches(r));}
    get accounts(){return this.d.accounts.filter(r=>this.matches(r)&&(!Number(this.state.course)||r.course_id===Number(this.state.course)));}
    get soonLimit(){const date=new Date(this.d.today+"T12:00:00Z");date.setUTCDate(date.getUTCDate()+7);return date.toISOString().slice(0,10);}
    get invoices(){return this.d.invoices.filter(r=>this.matches(r)&&(this.state.status==="all"||r.status===this.state.status)&&(!Number(this.state.course)||r.course_id===Number(this.state.course))&&(this.state.due==="all"||r.due&&(this.state.due==="overdue"?r.due<this.d.today:r.due>=this.d.today&&r.due<=this.soonLimit)));}
    get receipts(){return this.d.receipts.filter(r=>this.matches(r));}
    get followups(){return this.d.followups.filter(r=>this.matches(r));}
    get overdueStudents(){return new Set(this.d.followups.map(r=>r.register)).size;}
    quotaPlans(id,quota){
        const latest=new Map();
        for(const p of this.d.plans.filter(p=>p.department_id===id&&p.quota===quota&&p.active).sort((a,b)=>(b.state==="published")-(a.state==="published")||b.version-a.version)){
            const key=p.course_id+":"+p.study_year+":"+p.term_id;if(!latest.has(key))latest.set(key,p);
        }
        return [...latest.values()];
    }
    quotaAmount(id,quota){const values=this.quotaPlans(id,quota).map(p=>p.total);if(!values.length)return "Not configured";const min=Math.min(...values),max=Math.max(...values);return min===max?this.money(min):this.money(min)+" – "+this.money(max);}
    quotaState(id,quota){const plans=this.quotaPlans(id,quota);return !plans.length?"Not configured":plans.every(p=>p.state==="published")?"Published":"Needs review";}
    departmentDescription(id){const courses=this.d.courses.filter(c=>c.department_id===id),levels=[...new Set(courses.map(c=>({undergraduate:"Undergraduate",postgraduate:"Postgraduate",diploma:"Diploma / other"}[c.level]||"Degree programmes")))],awards=[...new Set(courses.map(c=>c.award).filter(Boolean))];return levels.join(' / ')+(awards.length?' · '+awards.join(' / '):'');}
    get departments(){return this.d.departments.map((d,index)=>{const plans=this.d.plans.filter(p=>p.department_id===d.id&&p.active);return {...d,color:["purple","blue","green"][index%3],icon:["⌘","⌁","ϟ","⚙","▰","▣"][index%6],count:plans.length,review:plans.filter(p=>["draft","review"].includes(p.state)).length};}).filter(d=>this.matches({name:d.name,code:d.code})&&(this.state.status==="all"||(this.state.status==="review"?d.review>0:d.count>0&&!d.review)));}
    get assignmentPlans(){return this.d.plans.filter(p=>p.active&&p.state==="published"&&p.course_id===Number(this.state.assignment.course_id));}
    get selectedPlan(){return this.assignmentPlans.find(p=>p.id===Number(this.state.assignment.plan_id));}
    get assignmentBatches(){return this.d.batches.filter(b=>b.course_id===Number(this.state.assignment.course_id));}
    get assignmentTerms(){return this.d.terms.filter(t=>!t.course_id||t.course_id===Number(this.state.assignment.course_id));}
    get installmentCount(){return new Set(this.selectedPlan?.lines.map(l=>l.date||l.days)||[]).size;}
    get stats(){const d=this.d,s=d.summary;return {
        overview:[s.income,s.expense,s.income-s.expense,s.dues].map(v=>this.compact(v)),
        heads:[d.heads.filter(h=>h.active).length,d.heads.filter(h=>h.active&&!["once","exam"].includes(h.frequency)).length,d.heads.filter(h=>h.active&&h.optional).length,d.heads.filter(h=>!h.active).length],
        structures:[d.departments.length,d.plans.filter(p=>p.active&&p.quota==="gq").length,d.plans.filter(p=>p.active&&p.quota==="mq").length,d.plans.filter(p=>p.active&&["draft","review"].includes(p.state)).length],
        accounts:[d.accounts.length,d.accounts.filter(a=>a.status==="Paid").length,d.accounts.filter(a=>a.status==="Partial").length,d.accounts.filter(a=>["Unpaid","Unassigned"].includes(a.status)).length],
        invoices:[this.compact(s.billed),this.compact(d.invoices.filter(i=>i.state==="posted").reduce((sum,i)=>sum+i.amount-i.balance,0)),this.compact(s.due_soon),this.compact(s.overdue)],
        followup:[this.compact(s.overdue),new Set(d.followups.map(f=>f.register)).size,s.contacted,s.promises],
        receipts:[d.receipts.length,this.compact(this.snapshot.income),d.receipts.filter(r=>r.status==="Awaiting settlement").length,d.receipts.filter(r=>r.status==="Reversed").length],
    }[this.page]||[];}
    async load(){
        const request=++this.request;this.state.loading=true;this.state.error="";
        try{const data=await this.orm.call("campus.owner.fees","get_workspace",[Number(this.state.year)||0]);if(request!==this.request)return;this.state.data=data;this.state.year=data.year_id;if(!data.monthly.some(m=>m.key===this.state.month))this.state.month=data.monthly.find(m=>m.key===data.today.slice(0,7))?.key||data.monthly[0]?.key||"";if(!this.state.assignment.date)this.state.assignment.date=data.today;}
        catch(error){if(request===this.request)this.state.error=error.data?.message||"Finance records could not be loaded. Retry.";}finally{if(request===this.request)this.state.loading=false;}
    }
    async changeYear(){this.state.preview=null;this.state.assignment={course_id:"0",plan_id:"",batch_id:"0",term_id:"0",date:this.d.today};await this.load();}
    clearAssignment(){this.state.assignment={course_id:"0",plan_id:"",batch_id:"0",term_id:"0",date:this.d.today};this.state.preview=null;}
    assignmentValues(){const a=this.state.assignment;return {plan_id:Number(a.plan_id),batch_id:Number(a.batch_id)||0,term_id:Number(a.term_id)||0,date:a.date};}
    async previewAssignment(){this.state.preview=null;try{this.state.preview=await this.orm.call("campus.owner.fees","preview_assignment",[this.assignmentValues()]);}catch(error){this.notification.add(error.data?.message||"The assignment could not be previewed.",{type:"danger"});}}
    async commitAssignment(){if(this.state.busy)return;this.state.busy=true;try{await this.orm.call("campus.owner.fees","commit_assignment",[this.assignmentValues()]);await this.load();await this.previewAssignment();this.notification.add("Fee installments assigned. Existing charges were retained.",{type:"success"});}catch(error){this.notification.add(error.data?.message||"The assignment could not be completed.",{type:"danger"});}finally{this.state.busy=false;}}
    async go(page){return this.action.doAction("ideastone_erp.action_owner_fees_"+page,{additionalContext:{campus_fee_year:this.state.year}});}
    activateAttention(event,page){if(["Enter"," "].includes(event.key)){event.preventDefault();this.go(page);}}
    edit(kind,record=null,values={}){this.dialog.add(FeesDialog,{kind,record,workspace:this,values});}
    editHead(row){if(!this.d.can_write||!row.owned)return;this.edit("head",row,{name:row.name,default_code:row.code==="—"?"":row.code,campus_fee_category:row.category,campus_fee_frequency:row.frequency,campus_fee_optional:row.optional,property_account_income_id:row.account_id||"",tax_id:row.tax_id||""});}
    async openRecord(kind,id){try{await this.action.doAction(await this.orm.call("campus.owner.fees","open_record",[kind,id]),{onClose:()=>this.load()});}catch(error){this.notification.add(error.data?.message||"The finance record could not be opened.",{type:"danger"});}}
    async source(kind){try{await this.action.doAction(await this.orm.call("campus.owner.fees","source_action",[kind]),{onClose:()=>this.load()});}catch(error){this.notification.add(error.data?.message||"The register could not be opened.",{type:"danger"});}}
    exportData(kind=this.page){
        const rows={overview:this.d.monthly,heads:this.heads,structures:this.d.plans.map(p=>({name:p.name,programme:p.course,quota:p.quota,study_year:p.study_year,version:p.version,status:this.label(p.state),annual_amount:p.total})),accounts:this.accounts,invoices:this.invoices,followup:this.followups,receipts:this.receipts}[kind]||[];
        if(!rows.length){this.notification.add("No records match these filters.",{type:"info"});return;}
        const columns=Object.keys(rows[0]).filter(k=>k!=="id"&&!k.endsWith("_id"));const cell=v=>'"'+String(v??"").replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';
        const csv=[columns,...rows.map(r=>columns.map(k=>r[k]))].map(row=>row.map(cell).join(",")).join("\r\n");const url=URL.createObjectURL(new Blob(["\ufeff"+csv],{type:"text/csv;charset=utf-8"}));const link=document.createElement("a");link.href=url;link.download="fees-"+kind+".csv";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
}
registry.category("actions").add("ideastone_erp.owner_fees",OwnerFeesWorkspace);
