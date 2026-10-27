import re

from odoo.exceptions import AccessError, UserError, ValidationError

from odoo import _, api, fields, models

SCOPES = {"student", "parent", "owner", "faculty", "hod", "coe", "staff"}
KEY = re.compile(r"[a-zA-Z0-9_.:/-]{1,200}\Z")


class NavigationPreferences(models.Model):
    _inherit = "res.users"

    campus_navigation_preferences = fields.Json(copy=False, groups="base.group_system")

    def _campus_navigation_key(self, scope):
        if self.env.user._is_public():
            raise AccessError(_("Sign in to customize navigation."))
        if not isinstance(scope, str) or scope not in SCOPES:
            raise ValidationError(_("Unknown navigation workspace."))
        return f"{self.env.company.id}:{scope}"

    @api.model
    def campus_get_navigation(self, scope):
        key = self._campus_navigation_key(scope)
        return (self.env.user.sudo().campus_navigation_preferences or {}).get(key, {"revision": 0, "items": []})

    @api.model
    def campus_save_navigation(self, scope, items, revision):
        key = self._campus_navigation_key(scope)
        if type(revision) is not int or revision < 0 or not isinstance(items, list) or len(items) > 100:
            raise ValidationError(_("Invalid navigation preferences."))
        clean, ids = [], set()
        for row in items:
            if not isinstance(row, dict) or set(row) - {"id", "target", "label", "visible", "removed"}:
                raise ValidationError(_("Invalid navigation button."))
            if any(not isinstance(row.get(k), str) or not KEY.fullmatch(row[k]) for k in ("id", "target")):
                raise ValidationError(_("Invalid navigation destination."))
            label = row.get("label")
            if not isinstance(label, str) or not 1 <= len(label.strip()) <= 40 or any(ord(c) < 32 for c in label):
                raise ValidationError(_("Button names must contain 1–40 characters."))
            if row["id"] in ids or type(row.get("visible")) is not bool or type(row.get("removed", False)) is not bool:
                raise ValidationError(_("Invalid or duplicate navigation button."))
            ids.add(row["id"])
            clean.append({"id": row["id"], "target": row["target"], "label": label.strip(),
                          "visible": row["visible"], "removed": row.get("removed", False)})
        shown = [row["label"].casefold() for row in clean if row["visible"] and not row["removed"]]
        if not shown or len(set(shown)) != len(shown):
            raise ValidationError(_("Keep at least one visible button and use unique visible names."))
        # Serialize edits to this user's JSON, including saves from different role tabs.
        user = self.env.user.sudo()
        self.env.cr.execute("SELECT id FROM res_users WHERE id = %s FOR UPDATE", [user.id])
        user.invalidate_recordset(["campus_navigation_preferences"])
        preferences = dict(user.campus_navigation_preferences or {})
        current = preferences.get(key, {"revision": 0})
        if current["revision"] != revision:
            raise UserError(_("Navigation changed in another tab. Close and reopen Customize Navigation, then try again."))
        preferences[key] = {"revision": revision + 1, "items": clean}
        user.campus_navigation_preferences = preferences
        return preferences[key]
