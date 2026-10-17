from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

FINANCE = ("ideastone_erp.group_mvp_accountant",)
METHODS = [("cash", "Cash"), ("upi", "UPI"), ("bank", "Bank transfer"), ("card", "Card"), ("other", "Other")]


class FeeHead(models.Model):
    _inherit = "product.template"

    campus_fee_head = fields.Boolean(string="College fee head")


class FeeStructure(models.Model):
    _inherit = "op.fees.terms"

    company_id = fields.Many2one(default=lambda self: self.env.company)
    campus_course_id = fields.Many2one("op.course", string="Programme")
    campus_year_id = fields.Many2one("op.academic.year", string="Academic year")
    campus_term_id = fields.Many2one("op.academic.term", string="Semester (optional)")
    campus_managed = fields.Boolean(default=False)

    @api.constrains("line_ids")
    def terms_validation(self):
        legacy = self.filtered(lambda r: not r.campus_managed)
        if legacy:
            super(FeeStructure, legacy).terms_validation()


class FeeStructureLine(models.Model):
    _inherit = "op.fees.terms.line"

    company_id = fields.Many2one(related="fees_id.company_id", store=True)
    campus_product_id = fields.Many2one("product.product", string="Fee head")
    campus_amount = fields.Monetary(string="Installment amount", currency_field="campus_currency_id")
    campus_currency_id = fields.Many2one(related="company_id.currency_id")

    @api.constrains("campus_amount", "campus_product_id")
    def _check_fee_amount(self):
        for rec in self:
            if rec.campus_amount < 0:
                raise ValidationError(_("Fee amounts cannot be negative."))


class FeeElement(models.Model):
    _inherit = "op.fees.element"

    company_id = fields.Many2one(related="fees_terms_line_id.company_id", store=True, index=True)


class FeeAssignmentWizard(models.TransientModel):
    _name = "campus.fee.assignment.wizard"
    _description = "Assign existing fee structure to an enrolment"
    _inherit = "campus.mvp.mixin"

    enrolment_id = fields.Many2one("op.student.course", required=True)
    structure_id = fields.Many2one("op.fees.terms", required=True)
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    company_id = fields.Many2one(related="structure_id.company_id")

    def action_assign(self):
        self.ensure_one()
        self._mvp_require(*FINANCE)
        self._mvp_lock()
        self.enrolment_id.check_access_rule("read")
        self.env.cr.execute("SELECT id FROM op_student_course WHERE id=%s FOR UPDATE", [self.enrolment_id.id])
        plan, enrolment = self.structure_id, self.enrolment_id
        self._mvp_company("structure_id", "enrolment_id")
        if not plan.campus_managed or not plan.line_ids or plan.campus_course_id != enrolment.course_id or plan.campus_year_id != enrolment.academic_years_id:
            raise ValidationError(_("Select a configured fee structure matching this enrolment's programme and year."))
        if plan.campus_term_id and plan.campus_term_id != enrolment.academic_term_id:
            raise ValidationError(_("Fee structure semester must match the enrolment."))
        for line in plan.line_ids:
            if not line.campus_product_id:
                raise ValidationError(_("Configure a fee head on every installment."))
            existing = self.env["op.student.fees.details"].search([("student_id", "=", enrolment.student_id.id),
                ("fees_line_id", "=", line.id), ("campus_year_id", "=", plan.campus_year_id.id)])
            if not existing:
                from datetime import timedelta
                self.env["op.student.fees.details"].create({"student_id": enrolment.student_id.id, "fees_line_id": line.id,
                    "campus_year_id": plan.campus_year_id.id, "course_id": enrolment.course_id.id,
                    "batch_id": enrolment.batch_id.id, "company_id": self.company_id.id, "amount": line.campus_amount,
                    "product_id": line.campus_product_id.id, "date": line.due_date or self.date_from + timedelta(days=line.due_days),
                    "state": "draft", "campus_managed": True})
        self._mvp_log("Fee structure assigned", details={"student_id": enrolment.student_id.id, "structure_id": plan.id})
        return enrolment.student_id.action_campus_records("fees")


class StudentFee(models.Model):
    _inherit = ["op.student.fees.details", "campus.mvp.mixin"]
    _name = "op.student.fees.details"

    company_id = fields.Many2one(default=lambda self: self.env.company)
    currency_id = fields.Many2one(default=lambda self: self.env.company.currency_id)
    campus_managed = fields.Boolean(default=False)
    campus_year_id = fields.Many2one("op.academic.year", string="Academic year")
    campus_concession = fields.Monetary(string="Proposed concession", currency_field="currency_id")
    campus_concession_reason = fields.Text(string="Concession reason")
    campus_approved_by = fields.Many2one("res.users", readonly=True, copy=False)
    campus_approved_on = fields.Datetime(readonly=True, copy=False)
    campus_balance = fields.Monetary(related="invoice_id.amount_residual", currency_field="currency_id")
    campus_payment_state = fields.Selection(related="invoice_id.payment_state")
    _sql_constraints = [("campus_fee_assignment", "unique(student_id, fees_line_id, campus_year_id)", "This fee installment has already been assigned to this student and year.")]

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(v).intersection({"campus_approved_by", "campus_approved_on"}) for v in vals_list):
            raise AccessError(_("Use concession approval to record the approver."))
        if any(v.get("campus_managed") and v.get("invoice_id") for v in vals_list):
            raise AccessError(_("Generate the fee invoice from the student assessment."))
        records = super().create(vals_list)
        records._mvp_company("student_id", "fees_line_id", "course_id", "batch_id", "campus_year_id")
        return records

    @api.constrains("amount", "campus_concession")
    def _check_mvp_amount(self):
        for rec in self.filtered("campus_managed"):
            if not 0 <= rec.campus_concession <= rec.amount:
                raise ValidationError(_("Fee and concession must be non-negative, and concession cannot exceed the fee."))

    def write(self, vals):
        if {"campus_approved_by", "campus_approved_on"}.intersection(vals):
            raise AccessError(_("Use concession approval."))
        managed = self.filtered("campus_managed")
        if managed and {"student_id", "campus_year_id", "course_id", "batch_id", "fees_line_id", "campus_managed", "invoice_id"}.intersection(vals):
            raise ValidationError(_("Fee assessment identity is fixed. Create a separate assessment when needed."))
        if managed.invoice_id and set(vals) - {"message_follower_ids"}:
            raise ValidationError(_("Invoiced fees are immutable. Use an auditable accounting adjustment."))
        if "campus_concession" in vals:
            vals = dict(vals, campus_approved_by=False, campus_approved_on=False)
        return super().write(vals)

    def action_campus_concession(self):
        self._mvp_require("ideastone_erp.group_mvp_concession")
        self._mvp_lock()
        if any(rec.invoice_id or not rec.campus_concession or not (rec.campus_concession_reason or "").strip() for rec in self):
            raise ValidationError(_("Enter a concession and reason before generating the invoice."))
        super().write({"campus_approved_by": self.env.uid, "campus_approved_on": fields.Datetime.now()})
        self._mvp_log("Fee concession approved")

    def get_invoice(self):
        legacy = self.filtered(lambda r: not r.campus_managed)
        if legacy:
            super(StudentFee, legacy).get_invoice()
        for rec in self - legacy:
            rec._mvp_require(*FINANCE)
            rec._mvp_lock()
            if rec.invoice_id:
                continue
            if rec.campus_concession and not rec.campus_approved_by:
                raise ValidationError(_("Obtain concession approval before invoicing."))
            invoice = self.env["account.move"].with_company(rec.company_id).create({
                "move_type": "out_invoice", "partner_id": rec.student_id.partner_id.id, "company_id": rec.company_id.id,
                "invoice_date": fields.Date.context_today(rec), "invoice_date_due": rec.date,
                "campus_student_id": rec.student_id.id, "campus_year_id": rec.campus_year_id.id,
                "campus_course_id": rec.course_id.id,
                "invoice_line_ids": [(0, 0, {"product_id": rec.product_id.id, "name": rec.product_id.name,
                    "quantity": 1, "price_unit": rec.amount, "discount": rec.campus_concession * 100 / rec.amount if rec.amount else 0})],
            })
            super(StudentFee, rec).write({"invoice_id": invoice.id, "state": "invoice"})
            rec._mvp_log("Student fee invoice created", details={"invoice_id": invoice.id})
        return True

    def action_campus_post(self):
        self._mvp_require(*FINANCE)
        self.get_invoice()
        for rec in self:
            if rec.invoice_id.state == "draft":
                rec.invoice_id.action_post()
        return True

    def action_campus_pay(self):
        self.ensure_one()
        self._mvp_require(*FINANCE)
        if self.invoice_id.state != "posted" or self.invoice_id.amount_residual <= 0:
            raise ValidationError(_("Post an unpaid invoice before recording a payment."))
        return {"type": "ir.actions.act_window", "name": _("Record payment"), "res_model": "campus.fee.payment.wizard", "view_mode": "form", "target": "new",
                "context": {"default_invoice_id": self.invoice_id.id, "default_amount": self.invoice_id.amount_residual}}

    def unlink(self):
        if self.filtered("campus_managed"):
            raise ValidationError(_("Retain fee assessments and use cancellation or adjustments."))
        return super().unlink()


class FeeInvoice(models.Model):
    _inherit = "account.move"

    campus_student_id = fields.Many2one("op.student", ondelete="restrict", index=True)
    campus_course_id = fields.Many2one("op.course", ondelete="restrict", index=True)
    campus_year_id = fields.Many2one("op.academic.year", ondelete="restrict", index=True)

    def write(self, vals):
        posted = self.filtered(lambda r: r.campus_student_id and r.state == "posted")
        if posted and ({"invoice_line_ids", "line_ids", "partner_id", "currency_id", "company_id", "campus_student_id", "campus_year_id", "campus_course_id", "invoice_date", "invoice_date_due", "date", "move_type", "journal_id", "invoice_payment_term_id", "fiscal_position_id"}.intersection(vals) or vals.get("state") == "draft"):
            raise ValidationError(_("Posted college invoices are retained unchanged. Use a credit note or reversal for corrections."))
        if vals.get("state") == "draft" and self.filtered(lambda r: r.payment_id.campus_receipt_number):
            raise ValidationError(_("A college receipt journal entry must be reversed, never reset to draft."))
        return super().write(vals)

    @api.constrains("campus_student_id", "campus_year_id", "campus_course_id", "company_id", "currency_id")
    def _check_college_invoice_scope(self):
        for rec in self.filtered("campus_student_id"):
            if any(r.company_id and r.company_id != rec.company_id for r in (rec.campus_student_id | self.env["op.student"])):
                raise ValidationError(_("Invoice and student must belong to the same college."))
            if rec.currency_id != rec.company_id.currency_id:
                raise ValidationError(_("College MVP invoices use the college currency."))

    def unlink(self):
        if self.filtered("campus_student_id"):
            raise ValidationError(_("College invoices must be cancelled or reversed and retained."))
        return super().unlink()


class FeeInvoiceLine(models.Model):
    _inherit = "account.move.line"

    def write(self, vals):
        financial_fields = {"price_unit", "quantity", "discount", "account_id", "tax_ids", "debit", "credit", "balance", "amount_currency", "partner_id", "currency_id", "move_id"}
        if financial_fields.intersection(vals):
            for line in self.filtered(lambda r: r.move_id.state == "posted" and (r.move_id.campus_student_id or r.move_id.payment_id.campus_receipt_number)):
                # Native invoice synchronization reassigns unchanged balances at
                # posting time. Reuse its field-aware comparison, not a bypass flag.
                if any(self.env["account.move"]._field_will_change(line, vals, name) for name in financial_fields.intersection(vals)):
                    raise ValidationError(_("Posted college invoice and receipt lines cannot be overwritten. Use the documented reversal or credit note workflow."))
        return super().write(vals)


class FeePaymentWizard(models.TransientModel):
    _name = "campus.fee.payment.wizard"
    _description = "Record and reconcile a college fee payment"
    _inherit = "campus.mvp.mixin"

    invoice_id = fields.Many2one("account.move", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="invoice_id.company_id")
    currency_id = fields.Many2one(related="invoice_id.currency_id")
    amount = fields.Monetary(required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    method = fields.Selection(METHODS, required=True, default="cash")
    reference = fields.Char()
    journal_id = fields.Many2one("account.journal", required=True, domain="[('type','in',['cash','bank']),('company_id','=',company_id)]")
    payment_id = fields.Many2one("account.payment", readonly=True, copy=False)

    def action_pay(self):
        self.ensure_one()
        self._mvp_require(*FINANCE)
        self._mvp_lock()
        if self.payment_id:
            return self.payment_id.action_campus_receipt()
        invoice = self.invoice_id
        invoice.check_access_rights("write")
        invoice.check_access_rule("write")
        self.env.cr.execute("SELECT id FROM account_move WHERE id=%s FOR UPDATE", [invoice.id])
        invoice.invalidate_recordset()
        self._mvp_company("invoice_id", "journal_id")
        if not invoice.campus_student_id or invoice.state != "posted" or invoice.move_type != "out_invoice":
            raise ValidationError(_("Select a posted college fee invoice."))
        if self.currency_id.compare_amounts(self.amount, 0) <= 0 or self.currency_id.compare_amounts(self.amount, invoice.amount_residual) > 0:
            raise ValidationError(_("Payment must be positive and cannot exceed the current unpaid balance."))
        if self.method != "cash" and not (self.reference or "").strip():
            raise ValidationError(_("Enter the transaction reference for a non-cash payment."))
        if (self.method == "cash") != (self.journal_id.type == "cash"):
            raise ValidationError(_("Choose a cash journal for cash, or a bank journal for other payment methods."))
        wizard = self.env["account.payment.register"].with_context(active_model="account.move", active_ids=invoice.ids).create({
            "amount": self.amount, "payment_date": self.date, "journal_id": self.journal_id.id,
            "communication": self.reference or invoice.name,
        })
        payment = wizard.with_context(campus_fee_method=self.method, campus_fee_reference=self.reference)._create_payments()
        payment.ensure_one()
        # Native payment register posts and reconciles the receivable against the invoice.
        payment._campus_issue_receipt(invoice, self.method, self.reference)
        super().write({"payment_id": payment.id})
        self._mvp_log("Fee payment recorded", details={"invoice_id": invoice.id, "payment_id": payment.id, "amount": self.amount})
        return payment.action_campus_receipt()

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("payment_id") for v in vals_list):
            raise AccessError(_("Payment references are assigned by payment posting."))
        return super().create(vals_list)

    def write(self, vals):
        if "payment_id" in vals or self.payment_id:
            raise AccessError(_("A completed payment request cannot be changed."))
        return super().write(vals)


class FeePayment(models.Model):
    _inherit = "account.payment"

    campus_receipt_number = fields.Char(readonly=True, copy=False, index=True)
    campus_invoice_id = fields.Many2one("account.move", readonly=True, copy=False, ondelete="restrict")
    campus_method = fields.Selection(METHODS, readonly=True, copy=False)
    campus_reference = fields.Char(readonly=True, copy=False)
    campus_cashier_id = fields.Many2one("res.users", readonly=True, copy=False)
    campus_reversal_id = fields.Many2one("account.move", readonly=True, copy=False, ondelete="restrict")
    campus_reversal_reason = fields.Text(string="Reversal reason")
    _sql_constraints = [("campus_receipt_unique", "unique(campus_receipt_number)", "Receipt numbers must be unique and never reused.")]

    @api.model_create_multi
    def create(self, vals_list):
        protected = {"campus_receipt_number", "campus_invoice_id", "campus_method", "campus_reference", "campus_cashier_id", "campus_reversal_id"}
        if any(protected.intersection(vals) for vals in vals_list):
            raise AccessError(_("Receipt evidence can only be assigned to a posted and reconciled payment."))
        return super().create(vals_list)

    def _campus_issue_receipt(self, invoice, method, reference):
        self.ensure_one()
        if self.campus_receipt_number:
            return
        number = self.env["ir.sequence"].with_company(self.company_id).next_by_code("campus.receipt")
        if not number:
            raise ValidationError(_("Configure the college receipt sequence before collecting fees."))
        super().write({"campus_receipt_number": number, "campus_invoice_id": invoice.id, "campus_method": method,
                       "campus_reference": reference, "campus_cashier_id": self.env.uid})

    def write(self, vals):
        protected = {"campus_receipt_number", "campus_invoice_id", "campus_method", "campus_reference", "campus_cashier_id", "campus_reversal_id"}
        if protected.intersection(vals):
            raise AccessError(_("Receipt evidence is maintained by the payment workflow."))
        if self.filtered("campus_receipt_number") and {"amount", "date", "partner_id", "journal_id", "state"}.intersection(vals):
            raise ValidationError(_("Posted college payments cannot be overwritten. Reverse with a reason."))
        return super().write(vals)

    def action_draft(self):
        if self.filtered("campus_receipt_number"):
            raise ValidationError(_("Use Reverse payment to correct a college receipt."))
        return super().action_draft()

    def action_campus_reverse(self):
        self.ensure_one()
        if not self.env.user.has_group("ideastone_erp.group_mvp_accountant") and not self.env.su:
            raise AccessError(_("Fee accountant permission is required."))
        self.check_access_rights("write")
        self.check_access_rule("write")
        self.env.cr.execute("SELECT id FROM account_move WHERE id IN %s ORDER BY id FOR UPDATE", [tuple((self.move_id | self.campus_invoice_id).ids)])
        self.invalidate_recordset()
        if self.campus_reversal_id:
            return True
        if not self.campus_receipt_number or not (self.campus_reversal_reason or "").strip():
            raise ValidationError(_("Enter a reason before reversing this receipt."))
        self.move_id.line_ids.remove_move_reconcile()
        reversal = self.move_id._reverse_moves([{"date": fields.Date.context_today(self), "ref": self.campus_reversal_reason}], cancel=True)
        super().write({"campus_reversal_id": reversal.id})
        self.env["campus.mvp.audit"]._log(self, "Fee payment reversed", self.campus_reversal_reason, {"reversal_id": reversal.id})
        return True

    def action_campus_receipt(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        if not self.campus_receipt_number:
            raise ValidationError(_("This payment does not have a college fee receipt."))
        return self.env.ref("ideastone_erp.mvp_receipt_report").report_action(self)

    def unlink(self):
        if self.filtered("campus_receipt_number"):
            raise ValidationError(_("Receipts must be retained, including reversed payments."))
        return super().unlink()


class NativeFeePaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _create_payments(self):
        self.ensure_one()
        invoices = self.line_ids.move_id.filtered("campus_student_id")
        if invoices:
            if not self.env.su and not self.env.user.has_group("ideastone_erp.group_mvp_accountant"):
                raise AccessError(_("College fee accountant permission is required to collect this invoice."))
            if len(invoices) != 1 or len(self.line_ids.move_id) != 1:
                raise ValidationError(_("Record one college invoice per payment to retain its exact receipt allocation."))
            invoice = invoices[0]
            self.env.cr.execute("SELECT id FROM account_move WHERE id=%s FOR UPDATE", [invoice.id])
            invoice.invalidate_recordset()
            if self.currency_id != invoice.company_id.currency_id:
                raise ValidationError(_("College MVP payments use the college currency. Configure a matching journal."))
            if self.currency_id.compare_amounts(self.amount, 0) <= 0 or self.currency_id.compare_amounts(self.amount, invoice.amount_residual) > 0:
                raise ValidationError(_("College payment must be positive and cannot exceed the unpaid invoice balance."))
        payments = super()._create_payments()
        if invoices:
            payments.ensure_one()
            method = self.env.context.get("campus_fee_method") or ("cash" if payments.journal_id.type == "cash" else "bank")
            payments._campus_issue_receipt(invoices[0], method, self.env.context.get("campus_fee_reference") or self.communication)
        return payments
