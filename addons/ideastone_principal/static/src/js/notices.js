/** @odoo-module **/
import { Component, onWillStart, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { Dialog } from '@web/core/dialog/dialog';

class NoticeReturn extends Component {
    static template = 'ideastone_principal.NoticeReturn';
    static components = { Dialog };
    static props = ['close', 'notice', 'save'];
    setup() { this.state = useState({reason: '', busy: false, error: ''}); }
    async confirm() {
        if (!this.state.reason.trim()) { this.state.error = 'Enter the correction required.'; return; }
        this.state.busy = true;
        try { await this.props.save(this.state.reason.trim()); this.props.close(); }
        catch (error) { this.state.error = error.data?.message || error.message; }
        finally { this.state.busy = false; }
    }
}

class PrincipalNotices extends Component {
    static template = 'ideastone_principal.Notices';
    static props = ['*'];
    setup() {
        this.orm = useService('orm'); this.action = useService('action');
        this.dialog = useService('dialog'); this.notification = useService('notification');
        this.state = useState({data: null, loading: true, error: '', search: '', status: 'all', audience: 'all', page: 0, busy: false});
        onWillStart(() => this.load());
    }
    async load(reset = false) {
        if (reset) Object.assign(this.state, {search: '', status: 'all', audience: 'all', page: 0});
        this.state.loading = true; this.state.error = '';
        try {
            this.state.data = await this.orm.call('ideastone.principal.notice', 'get_workspace', []);
            this.state.page = Math.min(this.state.page, Math.max(0, this.pageCount - 1));
        }
        catch (error) { this.state.error = error.data?.message || 'Notices could not be loaded. Please retry.'; }
        finally { this.state.loading = false; }
    }
    refresh() { return this.load(true); }
    filtersChanged() { this.state.page = 0; }
    get filtered() {
        const query = this.state.search.trim().toLocaleLowerCase();
        return (this.state.data?.rows || []).filter(r =>
            (!query || `${r.name} ${r.reference} ${r.office}`.toLocaleLowerCase().includes(query)) &&
            (this.state.status === 'all' || r.state === this.state.status) &&
            (this.state.audience === 'all' || r.audience === (this.state.audience === 'all-campus' ? 'all' : this.state.audience)));
    }
    get rows() { return this.filtered.slice(this.state.page * 6, (this.state.page + 1) * 6); }
    get pageCount() { return Math.ceil(this.filtered.length / 6); }
    previous() { this.state.page = Math.max(0, this.state.page - 1); }
    next() { if (this.state.page + 1 < this.pageCount) this.state.page++; }
    statusClass(row) { return {pending: 'statuspending', published: 'statusgreen', returned: 'statusred', scheduled: 'statusviolet'}[row.state] || ''; }
    date(value, part = 'full') {
        if (!value) return '—';
        const date = new Date(value.includes(' ') ? value.replace(' ', 'T') + 'Z' : value + 'T12:00:00');
        return new Intl.DateTimeFormat('en-IN', part === 'month' ? {month: 'short'} : part === 'day' ? {day: '2-digit'} : part === 'time' ? {hour: 'numeric', minute: '2-digit'} : {day: '2-digit', month: 'short', year: 'numeric'}).format(date);
    }
    open(id = false) {
        return this.action.doAction({type: 'ir.actions.act_window', name: id ? 'Notice details' : 'Create notice',
            res_model: 'ideastone.principal.notice', res_id: id, views: [[false, 'form']], target: 'new',
            context: {default_company_id: this.env.services.company.currentCompany.id}}, {onClose: () => this.load()});
    }
    async decide(row, method, reason) {
        this.state.busy = true;
        try {
            await this.orm.call('ideastone.principal.notice', method, [[row.id], ...(reason ? [reason] : [])]);
            await this.load();
            this.notification.add(method === 'action_return' ? 'Notice returned with feedback.' : 'Notice approved. Publication timing has been applied.', {type: 'success'});
        } catch (error) {
            if (reason) throw error;
            this.notification.add(error.data?.message || error.message, {type: 'danger'});
            await this.load();
        } finally { this.state.busy = false; }
    }
    approve(row) { return this.decide(row, 'action_approve'); }
    returnNotice(row) { this.dialog.add(NoticeReturn, {notice: row, save: reason => this.decide(row, 'action_return', reason)}); }
}
registry.category('actions').add('ideastone_principal.notices', PrincipalNotices);
