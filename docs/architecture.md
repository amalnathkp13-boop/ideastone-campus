# Architecture

```
                 ┌──────────────────────┐
   browser ────► │  nginx (one domain)  │
                 └──┬─────────┬───────┬─┘
                    │         │       │
                  /          /lms/   /sso/
                    ▼         ▼       ▼
          ┌──────────────┐ ┌────────────┐ ┌──────────┐
          │ Odoo 17      │ │ OpenOlat   │ │ Keycloak │
          │ + OpenEduCat │ │ (Tomcat)   │ │          │
          │ + ideastone_ │ │            │ │          │
          │   campus     │ │            │ │          │
          └──────┬───────┘ └─────┬──────┘ └────┬─────┘
                 │  db=campus    │ db=openolat  │ db=keycloak
                 └───────────────┴──────────────┘
                              PostgreSQL 16
```

## Who owns what

| Data | System of record |
|---|---|
| Applicants, students, faculty, programmes, batches, fees, invoices, receipts, attendance, exam marks | **Odoo / OpenEduCat** |
| Learning content, SCORM packages, online tests, question banks, forums, certificates | **OpenOlat** |
| Identities, passwords, roles (`admin`, `faculty`, `student`, `parent`) | **Keycloak** |

## How we extend OpenEduCat without touching it

Odoo's inheritance lets a separate module change almost anything:

```python
class OpStudent(models.Model):
    _inherit = "op.student"            # add fields / override methods
    register_no = fields.Char()
```

```xml
<record id="view_op_student_form_ideastone" model="ir.ui.view">
  <field name="inherit_id" ref="openeducat_core.view_op_student_form"/>  <!-- add to existing view -->
  <field name="arch" type="xml">
    <xpath expr="//field[@name='gender']" position="before"><field name="register_no"/></xpath>
  </field>
</record>
```

Because `vendor/openeducat_erp` stays byte-for-byte upstream, (a) we can pull OpenEduCat updates with a submodule bump, and (b) the LGPL source-sharing obligation never applies to our code.

## Adding a new module

```
addons/ideastone_hostel/
  __manifest__.py      depends: ["ideastone_campus"]
  models/ views/ security/ir.model.access.csv data/
```

Add it to the install list in `odoo/entrypoint-campus.sh` (`-i ideastone_campus,ideastone_hostel`) if it should be installed on first boot.

## ERP ↔ LMS (implemented in `ideastone_lms`)

* **UI**: `ideastone_lms.lms_frame` client action embeds `/lms/` in an iframe; nginx strips `X-Frame-Options` from OpenOlat and sets `frame-ancestors 'self'`, so it only frames on our own domain.
* **Identity**: both apps trust Keycloak; a user signed in to the ERP is signed in to the LMS in the frame.
* **Provisioning** (`models/lms_client.py`): `GET /restapi/users?login="x"` → `PUT /restapi/users` → `PUT /restapi/repo/courses/{key}/participants/{identityKey}`. Each student/faculty stores `lms_login`, `lms_identity_key`, `lms_synced_on`, `lms_sync_error`; `op.course.lms_course_key` maps a programme to an OpenOlat course. Runs from the record button, a list action, or the nightly cron (`ideastone.lms_auto_provision`).
* **Phase 3 (open)**: pull assessment results back from OpenOlat into OpenEduCat exam records.
