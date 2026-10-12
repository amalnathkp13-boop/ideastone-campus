# Architecture

```
                 ┌──────────────────────┐
   browser ────► │  nginx (port 80)     │
                 └──┬─────────┬───────┬─┘
                    │         │       │
        campus.local│  lms.campus.local│  sso.campus.local
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

## ERP ↔ LMS sync (phase 2)

Planned as a small service (`services/lms-sync/`, Python) that:

1. Listens to Odoo (automated action / webhook on `op.student` create, `op.student.course` enrolment).
2. Calls OpenOlat REST (`/restapi/users`, `/restapi/repo/courses/{id}/members`) to create the user and enrol them in the course mapped to their programme/semester.
3. Pulls assessment results back into OpenEduCat exam records on a schedule.

A mapping table (Odoo student id ↔ OpenOlat identity key, Odoo subject ↔ OpenOlat course resource id) keeps the sync idempotent. See `docs/sso.md` for the identity side.
