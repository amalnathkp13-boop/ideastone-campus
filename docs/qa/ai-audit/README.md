# Student Success Radar and Campus Assistant audit

The AI pack now restricts each staff role to its students, gives attendance guidance that matches the recorded timetable, and keeps saved feedback comments out of provider requests. Assistant attempts are recorded independently of failed business requests, with a company lock enforcing the monthly limit. The shared campus shell is unchanged.

## Confirmed defects and corrections

| Area | Before | Correction and verification |
| --- | --- | --- |
| HOD access | A HOD without a department could fall through to college-wide access. Historic placements could admit a student now in another department. | All HOD groups require an active-college department; the effective current placement is checked for both Radar and counselling. Role and transfer regression tests. |
| Attendance guidance | Zero attendance with no future timetable could be called on track. Incomplete history looked like a clean bill of health. | Explicit shortage and missing-history messages in student and parent portals; low scores identify recorded concerns only. High risk remains visible when attendance is provisional. |
| Term boundaries | Future sessions after the term could enter the recovery calculation; zero threshold fell back to 75. | Exclusive local term-end boundary, active sessions only, explicit zero retained. Effective placements bound the term window; missing legacy dates retain term history. |
| Engagement | Future leave/OD, pending requests, overlapping days and old resolved follow-ups could inflate scores. | Approved workflow states, dates clipped through today in the active term, deduplicated OD/leave days, latest past counselling follow-up. |
| Published results | Results from another placement could affect the current semester. | Current batch and term constrain exam results. |
| Money | INR labels could accompany another company currency. Foreign-currency residuals were mixed. | Company-currency invoice residuals and matching display/export/context currency. |
| Performance and export | Filtered Radar scored students twice, silently capped the scored population at 5,000, and exported formula-like names. | One assessment per student; full scoped population totals; displayed/exported rows explicitly limited to 500; spreadsheet formula prefixes escaped. |
| Feedback privacy | Saved comments, including identifiers or embedded instructions, were sent to the provider. Only the latest 80 comments were considered. | All scoped feedback contributes to rating totals and predefined English keyword topic counts, computed locally. Only fixed labels and totals leave the server. Canary HTTP tests check outgoing payloads. |
| Audit durability | Provider errors raised through RPC rolled back their own logs. | A private independent audit transaction reserves the attempt and persists its result without committing business data. A real failed HTTP transaction retains its failure record. |
| Monthly limit | Only successful calls counted and concurrent calls could exceed the cap. | All reserved attempts count in the UTC month; a company lock and READ COMMITTED audit cursor prevent stale concurrent reservations. Two requests with one remaining slot produce one provider call. |
| Provider errors | Malformed response shapes could crash; redirects could forward payloads elsewhere. Configuration was labelled Connected before a call succeeded. | Validate response types, reject redirects, show controlled errors, refresh failed-attempt usage, label configuration accurately. OpenAI's default host requires a key; local compatible endpoints can work without one. |
| UI state and layout | Late filter responses could overwrite current selections. The model/status badge overflowed at mobile widths. | Ignore stale requests; clear previous feedback when its category changes; wrap headings, badges and generated text within the feature page. |
| Notice drafts | Local models can return a bold TITLE marker or omit it; the title was then lost. New circular defaults did not select the managed workflow. | Parse plain/bold title markers, fall back to the user's brief if the model omits a title, escape the generated body, open an unsaved managed circular for human review. |
| Generated factual accuracy | The small local model misstated feedback counts in a real test. | Show server-calculated topic and rating counts separately from AI suggestions, with review guidance. The model's prose is not treated as an authoritative report. |

## Validation

- Odoo 17 with the pinned OpenEduCat vendor and this add-on: **23 test cases, zero failures or errors**. Odoo's statistics include four fixture entries and report 27 tests.
- Four Node tests cover stale requests, failed-attempt usage refresh, and CSV escaping/currency.
- Ten real Odoo HTTP/browser checks cover owner/HOD/mentor isolation, student/parent messages, safe notice rendering, the editable circular handoff, provider-payload privacy, durable failure logs, malformed responses, concurrent limits and the disabled gate. A deterministic local provider makes failure/concurrency checks repeatable.
- Assistant feedback layouts are checked at 390, 1440 and 1728 pixels. CI uploads screenshots and results as `ai-audit-proof`.
- Local Mac: Ollama `qwen2.5:1.5b` answered the exact active-student count, drafted a notice, and generated feedback suggestions through the ERP UI. Chromium and WebKit rendered the Radar and completed a real provider question without page errors. A 390-pixel generated-feedback screen was checked for horizontal overflow.
- Ruff, XML parsing, JavaScript syntax and whitespace checks pass.

CI runs the unit, UI-state and deterministic HTTP checks. It does not download or depend on Ollama. Unit fixtures use the current test transaction; independent audit durability and quota concurrency are verified through real HTTP requests in the disposable database.

## Local preview and deployment

The `campus_latest` presentation database was backed up before upgrading only `ideastone_ai`. Its 1,000 synthetic students and 100 synthetic staff remain present. Twenty-five labelled demo mentor assignments and three labelled feedback responses make both features demonstrable. The previous session-switch fix remains in the local preview branch; it is independent of this PR.

Local Ollama is a user service bound to loopback, with cloud access disabled. Odoo reaches it through `host.docker.internal:11434/v1`; only the local demo company was enabled. Installation/model files and local credentials are not repository changes. On a deployment, configure the college's own provider endpoint or leave the Assistant off. After merging, upgrade `ideastone_ai` using the normal update workflow and reload browser assets. No production data, passwords or logins were changed by this audit.

## Limits and follow-up

The Radar is a transparent rules score, not a prediction model. Missing records need review. Recovery guidance applies to recorded and currently scheduled classes, not to an unentered future timetable. Topic matching uses a fixed English keyword vocabulary, can overlap, and does not infer sentiment; unmatched or non-English comments need local review. AI drafts can still invent details or misinterpret supplied figures and require human review before use. Logs contain metadata, not prompts, answers or API keys.

Public preview publication and production/LMS/SSO deployment were outside this private-repository task. During fixture preparation, a separate existing HOD leave-approval write guard rejected an approval; this PR does not change that workflow. The scoring test uses an approved fixture and does not claim to validate that separate approval path.
