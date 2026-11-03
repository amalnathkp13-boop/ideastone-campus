/** @odoo-module **/
import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PrincipalWorkspace extends Component {
    static template = "ideastone_principal.Workspace";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.view = this.props.action.params?.view || "overview";
        this.state = useState({loading:true,error:"",data:null,search:"",type:"",status:"",category:"",modal:null,outcome:"approved",remark:"",saving:false,modalError:""});
        this.dialog = useRef("dialog");
        useEffect(() => { if (this.state.modal) this.dialog.el?.querySelector("textarea, button")?.focus(); }, () => [this.state.modal]);
        useEffect(() => {
            if (!this.state.loading) document.querySelector('.campus_faculty_subnav button.active')?.scrollIntoView({block:"nearest",inline:"nearest"});
        }, () => [this.state.loading,this.view]);
        onWillStart(() => this.load());
    }
    get title() { return {overview:"Principal overview",decisions:"Decisions",staff:"Staff leave approvals",student:"Student leave approvals",events:"Event management",notices:"Notices & circulars"}[this.view]; }
    get isQueue() { return ["overview","decisions"].includes(this.view); }
    get modalTitle() {
        if (this.state.modal?.balances) return "Leave policy & balances";
        if (this.state.modal?.readonly) return "Request details";
        return {staff:"Review staff leave request",student:"Review long-term student leave request",request:"Review principal decision",event:"Principal decision & signature"}[this.state.modal?.row.kind] || "Review request";
    }
    get allRows() { return this.state.data?.rows || []; }
    get filteredRows() {
        return this.allRows.filter(row => (this.isQueue ? row.status === "pending" : row.kind === {staff:"staff",student:"student",events:"event"}[this.view])
            && (!this.state.search || `${row.name} ${row.subject} ${row.code || ""} ${row.department || ""} ${row.reason}`.toLowerCase().includes(this.state.search.toLowerCase()))
            && (!this.state.type || row.type === this.state.type) && (!this.state.category || row.category === this.state.category)
            && (!this.state.status || this.statusLabel(row.status,row.kind) === this.state.status))
            .sort((a,b) => ({pending:0,changes:1,approved:2,rejected:3}[a.status] - {pending:0,changes:1,approved:2,rejected:3}[b.status])
                || (a.from || a.submitted || "").localeCompare(b.from || b.submitted || ""));
    }
    get leaveTypes() { return [...new Set(this.allRows.filter(row => row.kind === this.view).map(row => row.type))].sort(); }
    get categories() { return [...new Set(this.allRows.filter(row => row.status === "pending").map(row => row.category))].sort(); }
    get pendingCount() { return this.allRows.filter(row => row.status === "pending").length; }
    get eventPending() { return this.allRows.filter(row => row.kind === "event" && row.status === "pending").length; }
    get calendarRows() { return this.allRows.filter(row => row.kind === "event" && ["approved","pending"].includes(row.status) && row.to >= this.state.data.today && row.from <= this.state.data.upcoming_end).sort((a,b) => a.from.localeCompare(b.from)); }
    get history() { return (this.state.data?.history || []).filter(row => this.view !== "staff" || row.kind === "staff"); }
    get metrics() {
        const d = this.state.data;
        if (!d) return [];
        if (this.isQueue) return [d.counts.students,d.counts.faculty,d.counts.applications,this.pendingCount].map(value => ({value}));
        const rows = this.allRows.filter(row => row.kind === this.view);
        if (this.view === "events") return [this.calendarRows.length,this.eventPending,this.allRows.filter(row => row.kind === "event" && row.status === "pending" && !row.checks).length,this.compactMoney(this.calendarRows.reduce((sum,row) => sum + row.budget,0))].map(value => ({value}));
        const approvedMonth = d.approved_month[this.view] || 0;
        return [rows.filter(row => row.status === "pending").length,approvedMonth,rows.filter(row => row.status === "approved" && row.from <= d.today && row.to >= d.today).length,
            this.view === "staff" ? rows.filter(row => row.status === "pending").reduce((sum,row) => sum + row.days,0) : rows.filter(row => row.status === "pending" && !row.details).length].map(value => ({value}));
    }
    async load() {
        this.state.loading=true; this.state.error="";
        try { this.state.data = await this.orm.call("ideastone.principal.decisions","get_data",[]); }
        catch(error) { this.state.error=error.data?.message || "Principal records could not be loaded. Retry to refresh saved data."; }
        finally { this.state.loading=false; }
    }
    statusLabel(value,kind="") { return {pending:kind === "event" ? "Pending signature" : "Pending",approved:"Approved",rejected:"Rejected",changes:"Needs changes"}[value] || value; }
    date(value) { return value ? new Date(`${value.slice(0,10)}T12:00:00`).toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric"}) : "—"; }
    timestamp(value) { return new Date(`${value.replace(" ","T")}Z`).toLocaleString("en-GB"); }
    initials(name) { return name.split(/\s+/).filter(Boolean).slice(0,2).map(word=>word[0]).join("").toUpperCase(); }
    money(value) { return `${this.allRows.find(row=>row.kind === "event")?.currency || "₹"}${Number(value || 0).toLocaleString("en-IN",{maximumFractionDigits:0})}`; }
    compactMoney(value) { return value >= 100000 ? `${this.allRows.find(row=>row.kind === "event")?.currency || "₹"}${(value/100000).toFixed(1)}L` : this.money(value); }
    async go(view) { return this.action.doAction(`ideastone_principal.${{overview:"action_principal_overview",decisions:"action_principal_decisions",staff:"action_principal_staff_leave",student:"action_principal_student_leave",events:"action_principal_events"}[view]}`); }
    async related(key) {
        try { await this.action.doAction(await this.orm.call("ideastone.principal.decisions","related_action",[key])); }
        catch(error) { this.notification.add(error.data?.message || "The related workspace is unavailable.",{type:"danger"}); }
    }
    openDecision(row,outcome="approved",readonly=false) {
        this.previousFocus=document.activeElement;
        Object.assign(this.state,{modal:{row,readonly},outcome,remark:"",modalError:""});
    }
    balances() { this.previousFocus=document.activeElement; this.state.modal={balances:true}; }
    get staffBalances() { return this.allRows.filter(row=>row.kind === "staff").filter((row,index,rows)=>rows.findIndex(other=>other.code === row.code && other.type === row.type) === index); }
    closeModal() { if (!this.state.saving) { this.state.modal=null; this.previousFocus?.focus(); } }
    backdropClick(event) { if (event.target === event.currentTarget) this.closeModal(); }
    modalKeys(event) {
        if (event.key === "Escape") this.closeModal();
        if (event.key === "Tab") {
            const nodes=[...this.dialog.el.querySelectorAll("button:not([disabled]),textarea,select,a[href]")],first=nodes[0],last=nodes[nodes.length-1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
    }
    async saveDecision() {
        if (!this.state.remark.trim()) { this.state.modalError="Please add a decision remark."; return; }
        if (this.state.saving) return;
        this.state.saving=true;
        const row=this.state.modal.row;
        try {
            await this.orm.call("ideastone.principal.decisions","decide",[row.kind,row.id,this.state.outcome,this.state.remark]);
            this.state.saving=false; this.closeModal(); await this.load();
            this.notification.add("Decision saved to the college records.",{type:"success"});
        } catch(error) { this.state.modalError=error.data?.message || "Decision could not be saved. Refresh and try again."; }
        finally { this.state.saving=false; }
    }
    exportCSV() {
        const rows=[["Staff name","Staff ID","Department","Leave type","From","To","Days","Balance","Recommendation","Status","Reason","Coverage"],...this.filteredRows.map(row=>[row.name,row.code,row.department,row.type,row.from,row.to,row.days,row.balance ?? "Not allocation based",row.recommendation,this.statusLabel(row.status),row.reason,row.coverage])];
        const cell=value=>{ let text=String(value ?? ""); if (typeof value !== "number" && /^[\s]*[=+@-]/.test(text)) text=`'${text}`; return `"${text.replaceAll('"','""')}"`; };
        const blob=new Blob(["\uFEFF"+rows.map(row=>row.map(cell).join(",")).join("\r\n")],{type:"text/csv;charset=utf-8"}),url=URL.createObjectURL(blob),link=document.createElement("a");
        link.href=url; link.download="staff-leave-register.csv"; link.click(); URL.revokeObjectURL(url);
    }
    openNotices() { return this.action.doAction("ideastone_principal.action_principal_notices"); }
    openNotice(id) { return this.action.doAction({type:"ir.actions.act_window",res_model:"ideastone.principal.notice",res_id:id,views:[[false,"form"]],target:"current"}); }
    requestRegister() { return this.action.doAction("ideastone_principal.action_principal_requests"); }
}
registry.category("actions").add("ideastone_principal.workspace",PrincipalWorkspace);
