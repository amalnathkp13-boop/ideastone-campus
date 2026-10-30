# Faculty Library & learning reference implementation

Branch: `codex/faculty-library-learning`.

The four faculty main pages follow `Faculty_Library_Learning_Submodules_Redesigned.html`: OPAC & digital library, Library catalogue, Library circulation, and Learning platform. The existing faculty sidebar and application header remain in place. Reference typography is scoped to these pages so shared theme rules cannot enlarge the controls or change the banner text. Saved requests and refreshed data render through the same components.

Catalogue data comes from `op.media` and college-scoped `op.media.unit` records. Publication year, department, call number, accession number, library location and shelf can be entered in the existing authorized media/copy forms. Newly entered records appear on refresh; filtering and pagination use the returned records. Circulation shows only the authenticated faculty member's loans and borrowing policy. Renewals and desk enquiries create submitted `campus.service.request` records. A renewal remains pending until reviewed and does not automatically extend the loan's due date. Appointed librarians retain access to the existing circulation desk.

The learning page uses the configured LMS URL and approved `campus.digital.resource` downloads. It does not provision external LMS accounts. Totals reflect saved records rather than the prototype's illustrative large numbers.

## Local preview

The preview is signed in as synthetic account `faculty.library.preview`, in the isolated **VCET Question Paper Preview College** (local company 13). Open [OPAC preview](http://localhost/web#action=886&cids=13&menu_id=321). The local fixture contains twelve copies, nine available titles, three issued copies across the library, two current loans for this faculty member, one returned loan, and three approved learning resources. The browser verification also saved one enquiry and one pending renewal.

`seed.py` only accepts the named local databases and a localhost base URL. It creates namespaced synthetic records, preserves existing college records, and never embeds a password. Set `FACULTY_LIBRARY_PREVIEW_PASSWORD` in the environment before the first run. After installing/upgrading the addon, run from the repository root in PowerShell:

```powershell
docker cp docs/qa/faculty-library-reference/books.json ideastone-campus-odoo-1:/tmp/faculty-library-books.json
docker cp docs/qa/faculty-library-reference/seed.py ideastone-campus-odoo-1:/tmp/faculty-library-seed.py
'exec(compile(open("/tmp/faculty-library-seed.py").read(), "/tmp/faculty-library-seed.py", "exec"))' | docker exec -i -e FACULTY_LIBRARY_PREVIEW_PASSWORD ideastone-campus-odoo-1 odoo shell -c /etc/odoo/odoo.conf -d campus --no-http
```

## Verification

- Five new faculty-library transaction tests and nineteen existing VCET workspace tests passed: **24 tests, zero failures/errors**.
- Ruff, JavaScript syntax checks, XML parsing, SCSS compilation, Compose validation and `git diff --check` passed.
- All four pages were checked at 1440, 768, 390 and 320 pixels: no document or main-content overflow. Wide tables scroll inside their panels. Fields remain 13px; page headings are 28px on desktop and 24px on phones.
- Author search, combined filters, department filtering, phone search, renewal persistence after reload, saved assistance, and the configured LMS link were checked in the faculty browser. No browser console errors were recorded. The approved download endpoint returned authenticated HTTP 200; the browser download event was not captured.
- Backend tests cover new catalogue entries, ownership and company boundaries, invalid renewal targets, duplicate renewal prevention, unchanged due dates, saved assistance, forged loan links and approved-material visibility.

Detailed observations: [browser-verification.json](browser-verification.json).

| Page | Evidence |
| --- | --- |
| OPAC | [Desktop](opac-desktop.png), [tablet](opac-tablet.png) |
| Catalogue | [Desktop](catalogue-desktop.png), [phone](catalogue-phone.png), [phone search](catalogue-phone-search.png) |
| Circulation | [Desktop after saved renewal](circulation-desktop.png) |
| Learning | [Desktop](learning-desktop.png) |
