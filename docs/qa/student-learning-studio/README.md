# Student Learning Studio

The student sidebar gains one **LMS** entry and retains its existing layout and navigation controls. On the LMS page, the merged first row contains the title, online status, search, notifications and student avatar; the second row contains the nine submodules. Other pages retain their original headers. The supplied Learning Studio main-content theme runs in an authenticated same-origin frame so its typography, media, illustrations and card colors are not overridden by global ERP styles. Reference breakpoints and heading sizes use the outer viewport; embedded navigation adapts to the available content width.

The nine sections are Dashboard, My courses, Calendar, Grades, Tests, Discussions, Offline library, Private files and Interest zone. Course outlines, six activity types, repeatable quizzes, scheduled practice tests, notes, assignment drafts/submissions, personal discussion responses, practice mentoring slots, search, study-guide downloads, calendar exports and offline workspace exports are retained.

Learning records are private to the authenticated student. They are self-study records, not official examination results or faculty appointments. The reference's four educational courses are bundled as learning content. New student records start with no completed activities; the reference progress is loaded only by the guarded preview seed. Private files are limited to 16 MB each, 20 files and 64 MB per student. Offline exports include the learner's progress but not their uploaded private files.

State saves validate the payload, recompute practice scores and check revisions. Sidebar navigation waits for pending saves. A conflict or network error leaves the local draft visible with retry/reload/export options. The parent portal is not allowed to access another student's record through a supplied student ID. Download responses use attachment disposition and private cache headers.

## Validation

- Odoo: `--test-enable --test-tags=/ideastone_erp:TestStudentLearningStudio --stop-after-init --workers=0 --max-cron-threads=0`
- Browser: install/use the existing Playwright package, set `LMS_PREVIEW_PASSWORD`, then run `node docs/qa/student-learning-studio/ui.cjs`.
- Browser history: with the same preview credentials, run `node docs/qa/student-learning-studio/history.cjs` to check that Back/Forward preserve pending drafts.
- State and routing: `node addons/ideastone_erp/static/src/learning_studio/check_workspace.mjs`.
- Optional browser settings: `LMS_BASE_URL` defaults to `http://localhost:18107`; `LMS_QA_OUT` selects the screenshot folder.
- The `seed.py` script refuses to run outside `student_learning_studio_preview`. Run through Odoo shell with `LMS_PREVIEW_PASSWORD` set.

The preview uses normal database-backed Odoo views. Upgrade `ideastone_erp` before restarting the service. Use the same committed assets after deployment; the authenticated workspace adds content hashes to CSS/JavaScript URLs to prevent a stale browser cache.
