/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class AccountantDirectory extends Component {
    static template = "ideastone_erp.AccountantDirectory";
    setup() {
        this.orm = useService("orm"); this.action = useService("action");
        this.state = useState({rows: [], currency: "₹", mode: this.props.action.params?.mode || "directory", level: "department", department: "", year: "", section: "", student: null, search: "", status: "", semester: "", error: ""});
        onWillStart(async () => { try { Object.assign(this.state, await this.orm.call("campus.dashboard", "get_accountant_directory", [])); } catch (e) { this.state.error = e.data?.message || "Fee records could not be loaded."; } });
    }
    money(n) { return "₹" + new Intl.NumberFormat("en-IN", {maximumFractionDigits: 2}).format(n || 0); }
    initials(name) { return name.split(" ").map(s => s[0]).slice(0, 2).join(""); }
    get years() { return [...new Set(this.state.rows.map(r => r.year))].sort(); }
    get departments() { return [...new Set(this.state.rows.map(r => r.department))].sort(); }
    get semesters() { return [...new Set(this.state.rows.map(r => r.semester))].sort(); }
    get filterBarVisible() { return !this.state.student && (this.state.mode === "accounts" || this.state.level === "students"); }
    resetFilters() {
        Object.assign(this.state, {search: "", year: "", semester: "", status: ""});
        if (this.state.mode === "accounts") this.state.department = "";
    }
    get rows() {
        const s = this.state;
        return s.rows.filter(r => (!s.department || r.department === s.department) && (!s.year || r.year === s.year) && (!s.section || r.section === s.section) && (!s.semester || r.semester === s.semester) && (s.mode !== "pending" || r.pending > 0) && (!s.status || (s.status === "Overdue" ? r.overdue : s.status === "Cleared" ? !r.pending : s.status === "Due soon" ? r.pending && !r.overdue : r.pending > 0)));
    }
    get filteredRows() { const q = this.state.search.toLowerCase(); return this.rows.filter(r => `${r.name} ${r.number} ${r.department}`.toLowerCase().includes(q)); }
    get cards() {
        const field = this.state.level; const key = field === "department" ? "department" : field === "year" ? "year" : "section";
        return [...new Set(this.rows.map(r => r[key]))].filter(name => name.toLowerCase().includes(this.state.search.toLowerCase())).map(name => {
            const rows = this.rows.filter(r => r[key] === name), total = rows.reduce((n,r) => n+r.total,0), paid = rows.reduce((n,r) => n+r.paid,0);
            return {name, code: key === "department" ? rows[0].code : key === "section" ? this.initials(name) : "Y", count: rows.length, pending: rows.reduce((n,r)=>n+r.pending,0), rate: total ? Math.round(paid/total*100) : 0};
        });
    }
    get metrics() {
        const rows = this.state.student ? [this.state.student] : this.rows, sum = key => rows.reduce((n,r)=>n+r[key],0);
        if (!this.state.student && this.state.mode === "directory") return [
            {label:"Total students",value:rows.length,icon:"♙",note:"Selected scope"},
            {label:"Departments",value:new Set(rows.map(r=>r.department)).size,icon:"▦",note:"Academic programmes"},
            {label:"Fee collection",value:(sum("total") ? Math.round(sum("paid")/sum("total")*100) : 0)+"%",icon:"↗",note:"Overall collection rate"},
            {label:"Pending fee",value:this.money(sum("pending")),icon:"₹",note:"Outstanding balance"}];
        if (!this.state.student) return [
            {label:this.state.mode === "pending" ? "Students with dues" : "Student accounts",value:rows.length,icon:"♙",note:"Selected scope"},
            {label:"Outstanding accounts",value:rows.filter(r=>r.pending>0).length,icon:"₹",note:"Students with balance due"},
            {label:"Total outstanding",value:this.money(sum("pending")),icon:"◷",note:"Combined unpaid balance"},
            {label:this.state.mode === "pending" ? "Overdue" : "Accounts cleared",value:rows.filter(r=>this.state.mode === "pending" ? r.overdue : !r.pending).length,icon:"✓",note:"Current account status"}];
        return [{label: "Total fee", value: this.money(sum("total")), icon:"₹",note:"Selected scope"},
            {label:"Amount paid", value:this.money(sum("paid")),icon:"✓",note:"Recorded against posted invoices"},
            {label:"Pending fee",value:this.money(sum("pending")),icon:"₹",note:"Outstanding balance"},
            {label:"Fee collection",value:(sum("total") ? Math.round(sum("paid")/sum("total")*100) : 0)+"%",icon:"↗",note:"Payment completion"}];
    }
    get title() { return this.state.student ? "Student fee history" : this.state.mode === "accounts" ? "Student fee accounts" : this.state.mode === "pending" ? "Pending fee students" : this.state.section || this.state.year || this.state.department || "Student directory"; }
    reset() { Object.assign(this.state,{department:"",year:"",section:"",student:null,search:"",status:"",semester:"",level:"department"}); }
    drill(card) { const s=this.state; s.search=""; if(s.level==="department") {s.department=card.name;s.level=s.mode==="pending"?"students":"year";} else if(s.level==="year") {s.year=card.name;s.level="section";} else {s.section=card.name;s.level="students";} }
    back(level) { this.state.student=null; this.state.search=""; this.state.level=level; if(level==="department")this.reset(); if(level==="year")Object.assign(this.state,{year:"",section:""}); if(level==="section")this.state.section=""; }
    openStudent(row) { this.state.student=row; this.state.search=""; }
    receipt(row) { return this.action.doAction({type:"ir.actions.act_window",res_model:row.model,res_id:row.record_id,views:[[false,"form"]],target:"new",context:{form_view_initial_mode:"view"}}); }
    reminders() { return this.action.doAction("ideastone_erp.accountant_notices"); }
    exportRows() {
        const rows=this.state.student ? this.state.student.ledger : this.filteredRows;
        const keys=this.state.student ? ["date","name","description","total","paid","pending","status"] : ["number","name","department","year","section","semester","total","paid","pending"];
        const cell=v=>'"'+String(v??"").replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';
        const blob=new Blob([keys.map(cell).join(",")+"\n"+rows.map(r=>keys.map(k=>cell(r[k])).join(",")).join("\n")],{type:"text/csv;charset=utf-8"});
        const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="student-fees.csv";a.click();URL.revokeObjectURL(url);
    }
}
registry.category("actions").add("ideastone_erp.accountant_directory", AccountantDirectory);
