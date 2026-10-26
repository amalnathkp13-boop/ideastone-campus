"""Campus Assistant: generative AI for the owner workspace.

Design rules
* Off until a college enables it and points it at a provider. Any OpenAI-compatible
  chat endpoint works: OpenAI, Groq, or a self-hosted Ollama/vLLM server for colleges
  that keep data on campus.
* Only aggregate numbers and the user's own text are sent. Student, staff and guardian
  records never leave the server. Every call is logged with what was shared.
* Answers are grounded: the model is told to answer only from the figures supplied.
"""
import json
import time
from html import escape

import requests
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo import _, api, fields, models

DEFAULT_ENDPOINT = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
FEATURES = [("ask", "Ask the campus"), ("notice", "Draft a notice"), ("feedback", "Feedback themes")]


class CompanyAISettings(models.Model):
    _inherit = "res.company"

    campus_ai_enabled = fields.Boolean(string="Enable the Campus Assistant", groups="ideastone_erp.group_manager,ideastone_erp.group_mvp_owner")
    campus_ai_endpoint = fields.Char(string="AI endpoint (OpenAI-compatible)", default=DEFAULT_ENDPOINT, groups="ideastone_erp.group_manager,ideastone_erp.group_mvp_owner",
                                     help="Base URL of a chat-completions API. Examples: https://api.openai.com/v1, "
                                          "https://api.groq.com/openai/v1, or http://ollama:11434/v1 for an on-campus model.")
    campus_ai_model = fields.Char(string="AI model", default=DEFAULT_MODEL, groups="ideastone_erp.group_manager,ideastone_erp.group_mvp_owner")
    campus_ai_api_key = fields.Char(string="AI API key", groups="base.group_system,ideastone_erp.group_mvp_owner", help="Leave empty for a local server that needs no key.")
    campus_ai_monthly_limit = fields.Integer(string="Assistant calls per month", default=500, groups="ideastone_erp.group_manager,ideastone_erp.group_mvp_owner",
                                             help="A safety cap on provider usage. 0 disables the cap.")

    @api.constrains("campus_ai_endpoint", "campus_ai_monthly_limit")
    def _check_ai_settings(self):
        for company in self:
            endpoint = (company.campus_ai_endpoint or "").strip()
            if endpoint and not endpoint.startswith(("https://", "http://")):
                raise ValidationError(_("The AI endpoint must start with https:// or http://."))
            if company.campus_ai_monthly_limit < 0:
                raise ValidationError(_("The monthly call limit cannot be negative."))


class AILog(models.Model):
    _name = "campus.ai.log"
    _description = "Campus Assistant audit log"
    _order = "id desc"

    company_id = fields.Many2one("res.company", required=True, readonly=True, index=True)
    user_id = fields.Many2one("res.users", required=True, readonly=True)
    feature = fields.Selection(FEATURES, required=True, readonly=True)
    model_name = fields.Char(readonly=True)
    shared = fields.Char(string="Data shared with the provider", readonly=True)
    prompt_chars = fields.Integer(readonly=True)
    response_chars = fields.Integer(readonly=True)
    duration_ms = fields.Integer(readonly=True)
    ok = fields.Boolean(readonly=True)
    error = fields.Char(readonly=True)

    def write(self, vals):
        raise AccessError(_("The assistant log cannot be edited."))

    def unlink(self):
        raise AccessError(_("The assistant log must be retained."))


class CampusAssistant(models.AbstractModel):
    _name = "campus.ai.assistant"
    _description = "Campus Assistant (generative AI)"

    # ------------------------------------------------------------ access
    def _require_owner(self):
        if not self.env["campus.dashboard"]._is_mvp_user() or not self.env["campus.ai.log"].check_access_rights("read", raise_exception=False):
            raise AccessError(_("The Campus Assistant is available to the college administration workspace."))

    @api.model
    def get_status(self):
        self._require_owner()
        company = self.env.company.sudo()
        month_start = fields.Date.context_today(self).replace(day=1)
        used = self.env["campus.ai.log"].sudo().search_count([
            ("company_id", "=", company.id), ("ok", "=", True),
            ("create_date", ">=", fields.Datetime.to_string(fields.Datetime.now().replace(day=1, hour=0, minute=0, second=0)))])
        return {"enabled": bool(company.campus_ai_enabled), "configured": bool(company.campus_ai_enabled and (company.campus_ai_endpoint or "").strip()),
                "model": company.campus_ai_model or DEFAULT_MODEL, "endpoint_host": (company.campus_ai_endpoint or "").split("//")[-1].split("/")[0],
                "has_key": bool(company.campus_ai_api_key), "limit": company.campus_ai_monthly_limit, "used": used,
                "month": month_start.strftime("%B %Y"), "can_configure": self.env.user.has_group("ideastone_erp.group_manager") or self.env.user.has_group("ideastone_erp.group_mvp_owner"),
                "shares": [_("College name and today's date"), _("Aggregate figures from the Admin overview for the selected period"),
                           _("Student Success Radar counts per risk band and factor (no names)"), _("The text you type")],
                "never_shares": [_("Student, guardian or staff records"), _("Marks, attendance or fee rows for any person"), _("Passwords or API keys")]}

    # ------------------------------------------------------------ provider
    def _complete(self, feature, messages, shared, max_tokens=700):
        company = self.env.company.sudo()
        if not company.campus_ai_enabled or not (company.campus_ai_endpoint or "").strip():
            raise UserError(_("The Campus Assistant is not configured for this college. An administrator can enable it under College profile > AI assistant."))
        limit = company.campus_ai_monthly_limit
        if limit:
            month_start = fields.Datetime.now().replace(day=1, hour=0, minute=0, second=0)
            used = self.env["campus.ai.log"].sudo().search_count([("company_id", "=", company.id), ("ok", "=", True), ("create_date", ">=", fields.Datetime.to_string(month_start))])
            if used >= limit:
                raise UserError(_("The assistant has reached this month's call limit (%s). An administrator can raise it under College profile > AI assistant.") % limit)
        url = company.campus_ai_endpoint.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if company.campus_ai_api_key:
            headers["Authorization"] = "Bearer " + company.campus_ai_api_key
        payload = {"model": company.campus_ai_model or DEFAULT_MODEL, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens}
        prompt_chars = sum(len(m["content"]) for m in messages)
        started = time.monotonic()
        text, error = "", ""
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=45)
            if response.status_code >= 400:
                error = _("Provider returned HTTP %s") % response.status_code
            else:
                body = response.json()
                text = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
                if not isinstance(text, str) or not text.strip():
                    error = _("Provider returned an empty answer")
        except (requests.RequestException, ValueError) as exc:
            error = type(exc).__name__
        duration = int((time.monotonic() - started) * 1000)
        self.env["campus.ai.log"].sudo().create({
            "company_id": company.id, "user_id": self.env.uid, "feature": feature, "model_name": payload["model"],
            "shared": ", ".join(shared), "prompt_chars": prompt_chars, "response_chars": len(text),
            "duration_ms": duration, "ok": not error, "error": error[:200]})
        if error:
            raise UserError(_("The AI provider could not answer (%s). Check the endpoint, model and key under College profile > AI assistant.") % error)
        return text.strip()

    # ------------------------------------------------------------ context
    def _metrics_context(self, filters):
        dashboard = self.env["campus.dashboard"]
        metrics = dashboard.get_owner_metrics(filters or {})
        f = dashboard._mvp_filters(filters or {})
        context = {"college": self.env.company.name, "today": fields.Date.to_string(fields.Date.context_today(self)),
                   "period": {"from": str(f["date_from"]), "to": str(f["date_to"])},
                   "figures": {card["label"]: card["value"] for card in metrics.get("stats", []) if card.get("allowed")},
                   "admission_funnel": {row["label"]: row["value"] for row in metrics.get("funnel", [])},
                   "students_by_programme": {row["label"]: row["value"] for row in metrics.get("programmes", [])},
                   "monthly_fees": metrics.get("collection", [])}
        try:
            radar = self.env["campus.success.radar"].get_workspace({})
            context["student_success"] = {"students": radar["summary"]["students"], "high_risk": radar["summary"]["high"],
                                          "watch": radar["summary"]["watch"], "on_track": radar["summary"]["low"],
                                          "leading_factors": {item["key"]: item["count"] for item in radar["summary"]["top_factors"]}}
        except AccessError:
            pass
        return context

    # ------------------------------------------------------------ features
    @api.model
    def ask(self, question, filters=None):
        self._require_owner()
        question = str(question or "").strip()
        if not question or len(question) > 1000:
            raise ValidationError(_("Ask a question of up to 1,000 characters."))
        context = self._metrics_context(filters)
        messages = [
            {"role": "system", "content": (
                "You are the Campus Assistant for an Indian college ERP. Answer the administrator's question using ONLY the JSON data "
                "provided. If the data does not contain the answer, say so plainly and suggest which report to open. Be concise: "
                "a short paragraph or a few bullet points. Use Indian rupee formatting for money. Never invent figures.")},
            {"role": "user", "content": "DATA:\n" + json.dumps(context, default=str) + "\n\nQUESTION: " + question},
        ]
        shared = [_("college name"), _("period"), _("overview figures"), _("admission funnel"), _("students per programme"), _("monthly fees"), _("success radar counts")]
        answer = self._complete("ask", messages, shared)
        return {"answer": answer, "shared": shared, "period": context["period"]}

    @api.model
    def draft_notice(self, brief, audience="all", tone="formal"):
        self._require_owner()
        brief = str(brief or "").strip()
        if not brief or len(brief) > 2000:
            raise ValidationError(_("Describe the notice in up to 2,000 characters."))
        audiences = dict(self.env["campus.circular"]._fields["audience"].selection)
        if audience not in audiences:
            raise ValidationError(_("Choose a valid audience."))
        if tone not in {"formal", "friendly", "urgent"}:
            raise ValidationError(_("Choose a valid tone."))
        messages = [
            {"role": "system", "content": (
                "You write official notices and circulars for an Indian college. Produce a title on the first line prefixed 'TITLE: ', "
                "then the notice body as plain-text paragraphs (no markdown, no HTML). Include what, who, when and what to do. "
                f"Tone: {tone}. Audience: {audiences[audience]}. Keep it under 220 words. Do not invent dates or names that are not in the brief.")},
            {"role": "user", "content": brief},
        ]
        text = self._complete("notice", messages, [_("your brief"), _("audience"), _("tone")])
        title, body = "", text
        if text.upper().startswith("TITLE:"):
            first, _sep, rest = text.partition("\n")
            title, body = first[6:].strip(), rest.strip()
        paragraphs = [escape(p.strip()) for p in body.split("\n\n") if p.strip()] or [escape(body)]
        html = "".join("<p>%s</p>" % p.replace("\n", "<br/>") for p in paragraphs)
        create = None
        if self.env["campus.circular"].check_access_rights("create", raise_exception=False):
            create = {"type": "ir.actions.act_window", "res_model": "campus.circular", "view_mode": "form", "views": [(False, "form")],
                      "target": "current", "name": _("New circular"),
                      "context": {"default_name": title[:120], "default_body": html, "default_audience": audience, "default_company_id": self.env.company.id}}
        return {"title": title, "body_html": html, "body_text": body, "create_action": create}

    @api.model
    def summarise_feedback(self, period=None, kind="student"):
        self._require_owner()
        if kind not in {"student", "parent", "staff"}:
            raise ValidationError(_("Choose a valid feedback type."))
        # Owners and registrars see only an anonymous aggregate, so the rows are read under the
        # workflow and scoped to this college; names and identifiers never leave this method.
        domain = [("company_id", "=", self.env.company.id), ("kind", "=", kind)]
        if period:
            domain.append(("period", "=", str(period)[:40]))
        rows = self.env["campus.feedback"].sudo().search(domain, order="id desc", limit=80)
        if not rows:
            raise UserError(_("No %s feedback has been submitted for that period yet.") % kind)
        # Anonymised: scores and comment text only, no names, no respondent or student identifiers.
        sample = [{"score": row.score, "comment": (row.comments or "").strip()[:300]} for row in rows if (row.comments or "").strip()]
        average = round(sum(rows.mapped("score")) / len(rows), 2)
        messages = [
            {"role": "system", "content": (
                "You analyse anonymous feedback for a college administrator. From the JSON list of {score (1-5), comment}, write: "
                "1) three to five themes, each with how many comments mention it and one representative paraphrase (never quote names); "
                "2) three concrete actions the college can take this month. Plain text, under 250 words.")},
            {"role": "user", "content": json.dumps({"responses": len(rows), "average_score": average, "comments": sample})},
        ]
        summary = self._complete("feedback", messages, [_("anonymous scores"), _("anonymous comment text")], max_tokens=600)
        return {"summary": summary, "responses": len(rows), "with_comments": len(sample), "average": average,
                "period": period or _("all periods"), "kind": kind}

    @api.model
    def feedback_periods(self, kind="student"):
        self._require_owner()
        if kind not in {"student", "parent", "staff"}:
            raise ValidationError(_("Choose a valid feedback type."))
        groups = self.env["campus.feedback"].sudo().read_group([("company_id", "=", self.env.company.id), ("kind", "=", kind)], ["period"], ["period"])
        return sorted({g["period"] for g in groups if g.get("period")}, reverse=True)
