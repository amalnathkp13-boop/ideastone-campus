/** @odoo-module **/
import { Component, onWillStart, useEffect, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class AccountantSpending extends Component {
    static template = "ideastone_erp.AccountantSpending";
    setup() {
        this.orm = useService("orm"); this.action = useService("action"); this.notification = useService("notification");
        this.picker = useRef("picker"); this.modal = useRef("modal");
        this.state = useState({rows: [], departments: [], vendors: [], today: "", currency: "₹", loading: true,
            search: "", department: "", payment: "", category: this.props.action.params?.mode === "maintenance" ? "maintenance" : "event",
            period: "Last 6 months", menu: false, modal: "", selected: null, form: {}, saving: false, error: "", formError: ""});
        onWillStart(() => this.load());
        useExternalListener(window, "click", event => { if (this.picker.el && !this.picker.el.contains(event.target)) this.state.menu = false; });
        useExternalListener(window, "keydown", event => {
            if (event.key === "Escape" && (this.state.modal || this.state.menu)) {
                event.preventDefault(); event.stopPropagation(); this.state.menu = false; this.close();
            }
            if (event.key === "Tab" && this.modal.el) {
                const controls = [...this.modal.el.querySelectorAll("button:not(:disabled), input, select")];
                const first = controls[0], last = controls.at(-1);
                if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
                else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
            }
        }, {capture: true});
        useEffect(() => { this.modal.el?.querySelector("input, select, button")?.focus(); }, () => [this.state.modal]);
    }
    get mode() { return this.props.action.params?.mode === "maintenance" ? "maintenance" : "event"; }
    get label() { return this.mode === "event" ? "Event" : "Maintenance"; }
    get description() { return this.mode === "event" ? "Track college events, vendor bills, payments and department-wise event expenditure." : "Track campus maintenance work, service invoices, upkeep costs and payment status."; }
    get bills() { return this.state.rows.filter(r => r.category === this.mode); }
    get filtered() {
        const s = this.state, q = s.search.trim().toLowerCase();
        return this.bills.filter(r => (!q || `${r.name} ${r.partner} ${r.reference}`.toLowerCase().includes(q)) &&
            (!s.category || r.category === s.category) && (!s.department || String(r.department_id) === s.department) && (!s.payment || r.status === s.payment));
    }
    get stats() {
        const total = this.bills.reduce((n,r) => n + r.total, 0), due = this.bills.reduce((n,r) => n + r.due, 0);
        return [{label:"Total spending",value:this.money(total,0),icon:"₹",tone:"",note:"Across recorded bills"},
            {label:"Amount paid",value:this.money(total-due,0),icon:"✓",tone:"green",note:"Recorded settled amounts"},
            {label:"Amount due",value:this.money(due,0),icon:"◷",tone:"amber",note:"Awaiting payment"},
            {label:"Bills requiring review",value:this.bills.filter(r=>r.state==="draft").length,icon:"!",tone:"violet",note:"Verify details before payment"}];
    }
    get chart() {
        if (!this.state.today) return [];
        const today = new Date(this.state.today+"T12:00:00"), count = this.state.period === "Current year" ? today.getMonth()+1 : 6;
        const months = Array.from({length:count},(_,i) => {
            const d=new Date(today.getFullYear(),today.getMonth()-count+1+i,1), key=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;
            const rows=this.bills.filter(r=>r.date.startsWith(key));
            return {key,label:d.toLocaleDateString("en",{month:"short"}),total:rows.reduce((n,r)=>n+r.total,0),paid:rows.reduce((n,r)=>n+r.total-r.due,0)};
        });
        const max=Math.max(1,...months.map(m=>m.total));
        return months.map(m=>({...m,totalHeight:Math.max(0,m.total)/max*100,paidHeight:Math.max(0,m.paid)/max*100}));
    }
    get largestDue() { return [...this.bills].filter(r=>r.due>0).sort((a,b)=>b.due-a.due)[0]; }
    money(value, digits=2) { return "₹" + new Intl.NumberFormat("en-IN",{minimumFractionDigits:digits,maximumFractionDigits:digits}).format(value || 0); }
    dateLabel(value) { return new Date(value+"T12:00:00").toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric"}); }
    categoryLabel(value) { return value === "event" ? "College event" : "Maintenance"; }
    async load() {
        this.state.loading=true; this.state.error="";
        try { Object.assign(this.state,await this.orm.call("campus.dashboard","get_accountant_spending",[])); }
        catch(e) { this.state.error=e.data?.message || "Spending records could not be loaded."; }
        finally { this.state.loading=false; }
    }
    reset() { Object.assign(this.state,{search:"",department:"",payment:"",category:this.mode}); }
    period(value) { this.state.period=value; this.state.menu=false; }
    view(row) { this.opener=document.activeElement; Object.assign(this.state,{modal:"view",selected:row}); }
    openNew() { this.opener=document.activeElement; Object.assign(this.state,{modal:"new",formError:"",form:{vendor_id:"",department_id:"",category:this.mode,amount:"",date:this.state.today,reference:""}}); }
    close() { if (!this.state.saving) { this.state.modal=""; this.opener?.focus(); } }
    closeOverlay(event) { if (event.target === event.currentTarget) this.close(); }
    async openRecord() {
        const id=this.state.selected.id; this.close();
        await this.action.doAction({type:"ir.actions.act_window",res_model:"account.move",res_id:id,views:[[false,"form"]],target:"new",context:{form_view_initial_mode:"view"},name:"Vendor bill"},{onClose:()=>this.load()});
    }
    async save(event) {
        event.preventDefault(); if(this.state.saving)return;
        this.state.saving=true; this.state.formError="";
        try {
            const f=this.state.form;
            await this.orm.call("campus.dashboard","create_accountant_spending",[{...f,vendor_id:Number(f.vendor_id),department_id:Number(f.department_id),amount:Number(f.amount)}]);
            this.state.modal=""; await this.load(); this.reset();
            this.notification.add("Draft bill saved. Review and post it through the existing bill workflow.",{type:"success"});
            this.opener?.focus();
            if(f.category !== this.mode) {
                await this.action.doAction("ideastone_erp.accountant_spending_" + (f.category === "event" ? "events" : "maintenance"));
            }
        } catch(e) { this.state.formError=e.data?.message || "The bill could not be saved."; }
        finally {this.state.saving=false;}
    }
}
registry.category("actions").add("ideastone_erp.accountant_spending",AccountantSpending);
