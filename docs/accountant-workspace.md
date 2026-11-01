# Accountant workspace

Upgrade **Ideastone Campus Operations** after deploying these changes. In Odoo, open **Settings → Users**, create an internal user or edit an existing one, and assign the **Accountant** group under Campus Operations. The user signs in through the same campus login page as other roles. SSO credentials and the Odoo role are managed separately; assigning a Keycloak realm role alone does not grant Odoo accounting access.

The Accountant dashboard uses saved, company scoped records:

- **Student fee directory and pending fees:** posted college fee invoices, their current residual balance, and the student's running enrolment for department and semester.
- **Collections:** college receipts less reversals; the existing fee assessment, invoice, payment, and CSV reports remain the source records.
- **Transport billing:** campus services approves the allocation and configures the boarding point fee plus a transport fee product with an income account. The accountant opens the approved allocation, creates the invoice, then posts and collects it using the existing accounting workflow.
- **Spending:** create a vendor bill in Event & maintenance bills and set **College spending category** to College event, Maintenance, or Other. Posted vendor bills and credits feed the outgoing total; drafts do not. The bill and its lines remain in Odoo Accounting.
- **Fee circulars:** the accountant may create, publish, and archive fee circulars for students or parents in the active college.

The owner retains the broad admin workspace and can open **Fees & Payments → Accounts summary** for the same figures, source registers, collection and dues reports, and a printable period snapshot. Income and outgoing are based on posted invoices and bills by invoice date; collections use receipt dates. The dashboard labels these measures separately to avoid treating unpaid bills as cash paid.
