/** @odoo-module **/
import { Component, onWillStart, useEffect, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { OwnerStaffDirectory } from "@ideastone_erp/js/owner_staff";

export class PrincipalStaffDirectory extends OwnerStaffDirectory {
    static template = "ideastone_principal.StaffDirectory";
    departmentGlyph(department) {return {CSE:"⌘",ECE:"⌁",EEE:"ϟ",MECH:"⚙",CIVIL:"⌂",IT:"▤",BME:"✚",ADMIN:"▥"}[department.code] || "▥";}
    get profileSections() {
        return super.profileSections.map(group => ({...group,title:group.title === "Work & contact" ? "Work & contact details" : group.title,
            fields:group.fields.map(field => field[0] === "Joining date" ? ["Date joined",field[1]] : field)}));
    }
    async load() {
        this.state.loading = true; this.state.error = "";
        try { this.state.data = await this.orm.call("ideastone.principal.staff.workspace", "get_directory", []); }
        catch (error) { this.state.error = error.data?.message || "Staff records could not be loaded."; }
        finally { this.state.loading = false; }
    }
}

export class PrincipalStaffWorkspace extends Component {
    static template = "ideastone_principal.StaffWorkspace";
    static props = ["*"];
    setup() {
        this.orm = useService("orm"); this.action = useService("action"); this.notification = useService("notification");
        this.view = this.props.action.params?.view || "applications";
        this.modal = useRef("modal");
        this.state = useState({loading:true,error:"",data:null,query:"",type:"",status:"",year:"",month:"",report:"history",
            modal:"",selected:null,decision:"",note:"",busy:false,modalError:""});
        onWillStart(() => this.load());
        useEffect(() => {this.modal.el?.querySelector("textarea,button")?.focus();}, () => [this.state.modal]);
        useExternalListener(window,"keydown",event => {
            if (!this.state.modal) return;
            if (event.key === "Escape") {event.preventDefault();event.stopPropagation();this.close();}
            if (event.key === "Tab" && this.modal.el) {
                const controls=[...this.modal.el.querySelectorAll("button:not(:disabled),textarea")],first=controls[0],last=controls.at(-1);
                if (event.shiftKey && document.activeElement===first) {event.preventDefault();last?.focus();}
                else if (!event.shiftKey && document.activeElement===last) {event.preventDefault();first?.focus();}
            }
        },{capture:true});
    }
    async load() {
        const request = this.request = (this.request || 0)+1;
        this.state.loading=true; this.state.error="";
        try {
            const data=await this.orm.call("ideastone.principal.staff.workspace",this.view === "payroll" ? "get_payroll" : "get_applications",
                this.view === "payroll" ? [this.state.year,this.state.month] : []);
            if (request===this.request) this.state.data=data;
        } catch(error) {if (request===this.request) this.state.error=error.data?.message || "Staff records could not be loaded.";}
        finally {if (request===this.request) this.state.loading=false;}
    }
    get rows() {return this.state.data?.rows || [];}
    get applications() {
        const q=this.state.query.trim().toLowerCase();
        return this.rows.filter(r=>(!this.state.type || r.staff_type===this.state.type) && (!this.state.status || r.state===this.state.status) &&
            (!q || [r.name,r.reference,r.role,r.department_id[1]].join(" ").toLowerCase().includes(q)));
    }
    get pending() {return this.rows.filter(r=>["pending","interview"].includes(r.state)).length;}
    get scheduled() {return this.rows.filter(r=>["pending","interview"].includes(r.state) && r.interview_date).length;}
    get incomplete() {return this.rows.filter(r=>["pending","interview"].includes(r.state) && r.documents!=="verified").length;}
    get decisionTitle() {return this.state.decision === "approved" ? "Approve application" : "Reject application";}
    get decisionConfirmation() {return this.state.decision === "approved" ? "Confirm approval" : "Confirm rejection";}
    get applicationCards() {return [["Total applications",this.rows.length,"Teaching and non-teaching","▤"],
        ["Pending principal review",this.pending,"Requires review","⚑"],["Interview scheduled",this.scheduled,"Recruitment panel dates set","▦"],
        ["Document follow-up",this.incomplete,"Incomplete submissions","▧"]];}
    initials(name) {return name.split(/\s+/).filter(Boolean).slice(0,2).map(s=>s[0]).join("").toUpperCase();}
    label(value) {return {pending:"Pending",interview:"Interview",approved:"Approved",rejected:"Rejected",verified:"Verified",incomplete:"Incomplete",teaching:"Teaching",non_teaching:"Non-teaching"}[value] || value;}
    statusClass(value) {return value==="approved" || value==="verified" ? "" : value==="interview" ? "blue" : "pending";}
    date(value) {return value ? new Date(value.replace(" ","T")+"Z").toLocaleString("en-GB",{day:"2-digit",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit"}) : "Not scheduled";}
    money(value) {return "₹" + new Intl.NumberFormat("en-IN",{maximumFractionDigits:2}).format(value || 0);}
    reset() {Object.assign(this.state,{query:"",type:"",status:""});}
    async changePeriod(key,value) {this.state[key]=value;await this.load();}
    show(row,decision="") {this.opener=document.activeElement;Object.assign(this.state,{modal:decision ? "decision" : "details",selected:row,decision,note:"",modalError:""});}
    close() {if (!this.state.busy) {this.state.modal="";this.opener?.focus();}}
    closeOverlay(event) {if (event.target===event.currentTarget) this.close();}
    async decide(event) {
        event.preventDefault(); if (this.state.busy) return;
        this.state.busy=true;this.state.modalError="";
        try {
            await this.orm.call("ideastone.principal.staff.workspace","decide_application",[this.state.selected.id,this.state.decision,this.state.note]);
            this.state.modal="";await this.load();this.opener?.focus();
            this.notification.add("Recruitment decision saved.",{type:"success"});
        } catch(error) {this.state.modalError=error.data?.message || "The decision could not be saved.";}
        finally {this.state.busy=false;}
    }
    async openApplication(id=false) {
        this.close();
        await this.action.doAction({type:"ir.actions.act_window",name:id ? "Staff application" : "New staff application",
            res_model:"ideastone.principal.staff.application",res_id:id,views:[[false,"form"]],target:"new",
            context:{default_company_id:this.env.services.company.currentCompany.id}}, {onClose:()=>this.load()});
    }
    get payrollColumns() {
        return this.state.report==="salary" ? ["Staff member","Department","Gross salary","P.F","T.D.S","Late deduction","Net salary","Status"] :
            this.state.report==="deductions" ? ["Staff member","Department","Late count","Deducted days","Deduction","Approved periods"] :
            ["Staff member","Department","In punch","Out punch","Late count","Deducted days","Deduction","Status"];
    }
    payrollValues(row,format=true) {
        const money=n=>format ? this.money(n) : n;
        return this.state.report==="salary" ? [row.name,row.department,money(row.gross),money(row.pf),money(row.tds),money(row.deduction),money(row.net),row.approved_periods ? "Approved payroll" : "No approved payroll"] :
            this.state.report==="deductions" ? [row.name,row.department,row.late_count,row.deducted_days,money(row.deduction),row.approved_periods] :
            [row.name,row.department,row.check_in,row.check_out,row.late_count,row.deducted_days,money(row.deduction),row.status];
    }
    get reportTitle() {return {history:"Staff punching & deduction register",salary:"Staff salary summary",deductions:"Late deduction summary"}[this.state.report];}
    get trend() {const values=this.state.data?.trend || [],max=Math.max(1,...values.map(r=>r.late));return values.map(r=>({...r,height:r.late/max*175}));}
    get trendText() {
        const highest=[...this.trend].sort((a,b)=>b.late-a.late)[0];
        return highest?.late ? `${highest.label} has the highest late-punch count this week (${highest.late}). Use verified attendance records for decisions.` : "No late first punches recorded this week.";
    }
    exportReport() {
        const cell=value=>{let text=String(value ?? "");if (typeof value==="string" && /^[=+@-]/.test(text)) text="'"+text;return '"'+text.replaceAll('"','""')+'"';};
        const csv=[this.payrollColumns,...this.rows.map(row=>this.payrollValues(row,false))].map(row=>row.map(cell).join(",")).join("\r\n");
        const url=URL.createObjectURL(new Blob(["\ufeff",csv],{type:"text/csv;charset=utf-8;"})),link=document.createElement("a");
        link.href=url;link.download=`staff-${this.state.report}-${this.state.year || "all"}-${this.state.month || "all"}.csv`;link.click();URL.revokeObjectURL(url);
    }
}
registry.category("actions").add("ideastone_principal.staff_directory",PrincipalStaffDirectory);
registry.category("actions").add("ideastone_principal.staff_workspace",PrincipalStaffWorkspace);
