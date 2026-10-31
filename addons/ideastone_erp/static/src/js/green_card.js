/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

const labels = {mentor:"Pending Mentor",mentor_proof:"Mentor · Proof Required",mentor_return:"Returned by Mentor",hod:"Awaiting HOD Decision",hod_proof:"HOD · Proof Required",hod_return:"Returned by HOD",principal:"Pending Principal",approved:"Approved",rejected:"Rejected"};
const key = () => crypto.randomUUID().replaceAll("-", "");
const initialForm = () => ({type:"announced",from:"",to:"",fromSession:"FN",toSession:"AN",reason:"",key:key()});

export class GreenCard extends Component {
    static template = "ideastone_erp.GreenCard";
    static props = ["*"];
    setup() {
        this.orm=useService("orm"); this.dialog=useService("dialog"); this.notification=useService("notification");
        this.state=useState({data:null,error:"",loading:true,busy:false,search:"",type:"all",status:"all",period:"weekly",form:initialForm(),upload:null});
        onWillStart(()=>this.load());
    }
    get role(){return this.state.data?.role;}
    get student(){return this.role==="student";}
    get hod(){return this.role==="hod";}
    get all(){return this.state.data?.rows || [];}
    async load(){
        this.state.loading=true; this.state.error="";
        try {this.state.data=await this.orm.call("campus.green.card.ui","get_workspace",[this.props.action?.context?.green_role || this.props.expectedRole || null]);}
        catch(error){this.state.error=error.data?.message || "Your Green Card workspace could not be loaded.";}
        finally {this.state.loading=false;}
    }
    label(row){return labels[row.state] || row.state;}
    tone(row){return row.state==="approved"?"green":row.state==="rejected"?"red":/proof|return/.test(row.state)?"amber":"blue";}
    get title(){return this.student?"Green Card":this.hod?"Green Card":"Green Card – Mentor Review";}
    get subtitle(){return this.student?"Apply for announced or unannounced leave, respond to verification, and follow approvals.":this.hod?"Review mentor-approved department applications and record the final decision.":"Review your mentorship class requests, verify exceptions, and forward to the HOD.";}
    get rows(){
        const query=this.state.search.trim().toLowerCase();
        const rows=this.all.filter(r=>(r.student+" "+r.register+" "+r.reference).toLowerCase().includes(query)
            &&(this.state.type==="all"||r.type===this.state.type)
            &&(this.state.status==="all" || this.state.status==="pending"&&!['approved','rejected'].includes(r.state)
                || this.state.status==="returned"&&r.state.endsWith("return") || r.state===this.state.status));
        const priority=r=>this.student?0:this.hod?({hod:0,hod_proof:1,hod_return:2,principal:3,approved:4,rejected:5}[r.state]??6):r.stage==='advisor'?0:1;
        return rows.sort((a,b)=>priority(a)-priority(b)||b.id-a.id);
    }
    get metrics(){
        const rows=this.all,count=fn=>rows.filter(fn).length;
        return this.student?[
            ["Requests Submitted",rows.length,"file-text-o","blue","Your saved requests"],
            ["Approved",count(r=>r.state==="approved"),"check","green","Final approval recorded"],
            ["Under Review",count(r=>!['approved','rejected'].includes(r.state)),"clock-o","amber","Mentor / HOD"],
            ["Action Required",count(r=>/proof|return/.test(r.state)),"exclamation-triangle","amber","Proof or correction"]]:this.hod?[
            ["Awaiting HOD",count(r=>r.state==="hod"),"clock-o","blue","Ready for your decision"],
            ["Approved",count(r=>r.state==="approved"),"check","green","Final approval issued"],
            ["Rejected",count(r=>r.state==="rejected"),"times","red","Final department decisions"],
            ["Proof Requested",count(r=>r.state==="hod_proof"),"file-text-o","amber","Awaiting student evidence"]]:[
            ["Pending Mentor",count(r=>r.stage==="advisor"),"clock-o","blue","My mentorship class"],
            ["Forwarded to HOD",count(r=>r.mentorApproved),"arrow-right","green","First-stage signed"],
            ["Verification Needed",count(r=>/proof|return/.test(r.state)),"file-text-o","amber","Proof / clarification"],
            ["Finalized",count(r=>['approved','rejected'].includes(r.state)),"check","purple","Closed requests"]];
    }
    get attention(){return this.all.filter(r=>this.student?/proof|return/.test(r.state):r.stage===(this.hod?"hod":"advisor"));}
    get decisions(){return this.all.filter(r=>this.hod?['approved','rejected'].includes(r.state):r.mentorApproved).slice(0,5);}
    get audit(){return this.all.flatMap(r=>r.history.map(event=>({...event,reference:r.reference,student:r.student}))).sort((a,b)=>b.at.localeCompare(a.at)).slice(0,5);}
    get insights(){return this.hod?[
        ["Ready for HOD decision",`${this.all.filter(r=>r.state==='hod').length} mentor-forwarded application(s) are ready for your decision.`],
        ["Awaiting proof",`${this.all.filter(r=>r.state==='hod_proof').length} application(s) are on hold after your proof request.`],
        ["Mentor approval preserved","Only applications approved and forwarded by assigned mentors appear in this workspace."]]:[
        ["Unannounced leave patterns",`${this.all.filter(r=>r.type==='unannounced').length} saved request(s) explain an existing absence.`],
        ["Pending verification",`${this.all.filter(r=>/proof|return/.test(r.state)).length} request(s) need evidence or clarification.`],
        ["Formal approvals remain required","Parent contact and supporting proof never replace mentor or HOD authorization."]];}
    get chart(){
        const today=this.state.data.today,month=today.slice(0,7);
        let buckets;
        if(this.hod){
            buckets=[['Awaiting HOD','hod'],['Proof hold','hod_proof'],['Returned','hod_return'],['Approved','approved'],['Rejected','rejected'],['Principal','principal']].map(([label,state])=>({label,match:r=>r.state===state&&(this.state.period==='monthly'||r.from.startsWith(month))}));
        }else if(this.state.period==='weekly'){
            buckets=Array.from({length:5},(_,i)=>({label:`Week ${i+1}`,match:r=>r.from.startsWith(month)&&Math.floor((Number(r.from.slice(-2))-1)/7)===i}));
        }else{
            const date=new Date(today+'T12:00:00Z');
            buckets=Array.from({length:6},(_,i)=>{const d=new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth()-5+i,1)); const ym=d.toISOString().slice(0,7);return {label:d.toLocaleDateString('en-GB',{month:'short',year:'2-digit',timeZone:'UTC'}),match:r=>r.from.startsWith(ym)};});
        }
        const rows=buckets.map(b=>({label:b.label,announced:this.all.filter(r=>b.match(r)&&r.type==='announced').length,unannounced:this.all.filter(r=>b.match(r)&&r.type==='unannounced').length}));
        const max=Math.max(2,...rows.flatMap(r=>[r.announced,r.unannounced])),step=Math.max(1,Math.ceil(max/4)),ceiling=Math.ceil(max/step)*step;
        return {rows,ceiling,ticks:Array.from({length:ceiling/step+1},(_,i)=>i*step),width:636/rows.length};
    }
    chartY(value){return 172-value/this.chart.ceiling*138;}
    error(error){this.notification.add(error.data?.message || error.message || "The action could not be saved.",{type:"danger"});}
    async file(event,target=this.state){
        const file=event.target.files[0];target.upload=null;
        if(!file)return;
        if(file.size>2*1024*1024||! /\.(pdf|png|jpe?g)$/i.test(file.name)){event.target.value="";this.error(new Error("Use PDF, PNG or JPEG, up to 2 MB."));return;}
        target.reading=true;
        try{const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});target.upload={filename:file.name,file:data};}
        catch{this.error(new Error("The selected file could not be read."));}
        finally{target.reading=false;}
    }
    clear(){this.state.form=initialForm();this.state.upload=null;const input=document.querySelector('.green_card input[type=file]');if(input)input.value="";}
    async submit(event){
        event.preventDefault(); if(this.state.busy||this.state.reading)return;this.state.busy=true;
        try{await this.orm.call("campus.green.card.ui","submit",[{...this.state.form,...(this.state.upload||{})}]);this.clear();await this.load();this.notification.add("Green Card submitted to your assigned mentor.",{type:"success"});}
        catch(error){this.error(error);}finally{this.state.busy=false;}
    }
    open(row){this.dialog.add(GreenCardDialog,{owner:this,row});}
    csv(rows,name){const safe=v=>{const t=String(v??'');return /^[\s]*[=+@\-\t\r]/.test(t)?"'"+t:t;};const text=rows.map(r=>r.map(v=>'"'+safe(v).replaceAll('"','""')+'"').join(',')).join('\r\n');const url=URL.createObjectURL(new Blob(['\uFEFF'+text],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);}
    exportRequests(){this.csv([['Request','Student','Type','From','Session','To','Session','Days','Status'],...this.rows.map(r=>[r.reference,r.student,r.type,r.from,r.fromSession,r.to,r.toSession,r.days,this.label(r)])],'green-card-requests.csv');}
    exportChart(){this.csv([['Period / Status','Announced','Unannounced'],...this.chart.rows.map(r=>[r.label,r.announced,r.unannounced])],'green-card-chart.csv');}
}

class GreenCardDialog extends Component {
    static template="ideastone_erp.GreenCardDialog";
    static components={Dialog};
    static props=['owner','row','close'];
    setup(){this.state=useState({note:"",reason:this.props.row.reason,parent:false,upload:null,reading:false,busy:false});}
    get owner(){return this.props.owner;}
    get row(){return this.props.row;}
    get canReview(){return !this.owner.student && this.row.stage===(this.owner.hod?'hod':'advisor');}
    async act(action){
        if(this.state.busy||this.state.reading)return;this.state.busy=true;
        try{
            if(this.owner.student){await this.owner.orm.call('campus.green.card.ui','respond',[this.row.id,{reason:this.state.reason,...(this.state.upload||{})}]);}
            else {await this.owner.orm.call('campus.green.card.ui','review',[this.row.id,action,this.state.note,this.state.parent?'parent':'none']);}
            await this.owner.load();this.props.close();this.owner.notification.add('Green Card action saved.',{type:'success'});
        }catch(error){this.owner.error(error);}finally{this.state.busy=false;}
    }
}
registry.category('actions').add('ideastone_erp.green_card',GreenCard);
registry.category('public_components').add('ideastone_erp.GreenCard',GreenCard);
