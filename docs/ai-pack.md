# Ideastone Campus AI Pack

The AI Pack is the `ideastone_ai` add-on module. It adds two capabilities on top of the
college ERP and is designed to be sold as an upgrade tier: it installs and uninstalls on its
own, changes nothing in the base modules, and works on day one with the data a college
already has.

| Feature | What it does | Needs an AI provider? | Who sees it |
|---|---|---|---|
| **Student Success Radar** | An early-warning score (0–100) for every active student, with the reason behind every point and a suggested action. Nudges in the student and parent portals. | No | Owner/admin, HODs (their department), mentors (their mentees), students and parents (own guidance only) |
| **Campus Assistant** | Plain-English questions over live college figures, notice/circular drafting, feedback themes. | Yes, any OpenAI-compatible endpoint | Owner / registrar workspace |

## Student Success Radar

### How the score is built

The score is an explainable rule set, not a black box. Every point is traceable to a record
in the ERP, so a mentor can act on it and a student can verify it.

| Factor | Max points | Source records | Rule |
|---|---|---|---|
| Attendance | 40 | Completed attendance sheets this semester, scheduled future sessions | Only once 5 classes are completed: `(threshold + 5 − rate) × 3`, capped at 40; +10 if the last four weeks are 10 points below the term rate; 40 if the threshold can no longer be reached |
| Results | 30 | Published exam results | `(50 − average %) × 1.2` up to 25, +5 per paper below pass marks (max 10) |
| Fees | 15 | Posted invoices past their due date | 8 if anything is overdue, +3 per 30 days overdue |
| Engagement | 15 | Approved leave, OD requests, counselling records | 2 per leave/OD day (max 10), +5 if a counselling follow-up date has passed |

Bands: **Needs attention** ≥ 50, **Watch** 25–49, **On track** < 25.

The attendance projection answers the question students actually ask: *"How many of the
remaining classes must I attend?"* It uses the scheduled sessions still to come this
semester, so the message in the portal reads, for example, "Attend 9 of your next 12 classes
to finish the semester at or above 75%", or says plainly when the threshold is out of reach so
the condonation process can start early.

### Scope and privacy

* Owners and reporting users see the whole college; an OD-approving HOD sees their
  department; a mentor sees only students routed to them (`campus.student.leave.routing`).
* Students and parents see one card about themselves or their child, never scores of others.
* All aggregation runs server-side. Nothing leaves the server.

### Where it appears

* Owner workspace → **AI insights → Student Success Radar** (also under Campus Operations → AI insights).
* Staff workspace → **Student success** module (HODs and mentors with routed students).
* Student portal dashboard and parent portal dashboard → guidance card.
* "Record counselling" opens the existing counselling form pre-filled with the student.

## Campus Assistant

### Setup

1. **College profile → AI assistant**: enter the endpoint, model and API key, tick *Enable*.
   * OpenAI: `https://api.openai.com/v1`, model `gpt-4o-mini`.
   * Groq: `https://api.groq.com/openai/v1`.
   * On-campus, no data leaves the building: run [Ollama](https://ollama.com) next to the
     stack (`http://ollama:11434/v1`, model `llama3.1`, no key needed).
2. Set a monthly call cap (default 500). The assistant stops at the cap and says so.
3. Open **AI insights → Campus Assistant**.

### What it sends to the provider, and what it never sends

| Sent | Never sent |
|---|---|
| College name and today's date | Student, guardian or staff records |
| Aggregate figures from the Admin overview (counts, totals, funnel, programme split, monthly fees) | Marks, attendance or fee rows for any person |
| Student Success Radar counts per band and factor | Passwords, API keys |
| The text the administrator types (question, notice brief) | — |
| Feedback: anonymous scores and comment text only | Who wrote the feedback |

Every call is written to **AI insights → Assistant log** (user, feature, data categories
shared, size, duration, success/error). The log cannot be edited or deleted.

### Features

* **Ask the campus** — answers are grounded: the model is instructed to use only the
  figures supplied and to say when the data does not contain the answer.
* **Draft a notice** — produces a title and body from a brief, for students, parents, staff
  or everyone, in a formal, friendly or urgent tone. *Create circular from this draft* opens
  the circular form pre-filled; nothing is published without review.
* **Feedback themes** — turns a period's feedback into three to five themes with counts and
  three suggested actions.

## Why colleges pay for it

* **Retention and compliance evidence.** NAAC (Criterion 2 and 5) and NBA reviewers ask how
  a college identifies and supports at-risk students. The radar plus counselling records is
  that evidence, generated continuously instead of assembled before an audit.
* **Fewer attendance disputes.** Students see the projection all semester, so the end-of-term
  "I did not know" argument disappears.
* **Fee follow-up that reaches the right people.** Overdue fees surface on the mentor's screen
  as a student-welfare signal, not only in the accounts office.
* **Admin time.** Notices, circulars and feedback reports that used to take an afternoon take
  minutes, and the owner can ask a question instead of opening five reports.
* **Low cost to run.** The radar costs nothing. The assistant's provider bill is capped per
  month by the college itself; at typical usage (a few hundred calls a month on a small model)
  it is a few hundred rupees.

Suggested packaging: include the Student Success Radar in a "Plus" tier and the Campus
Assistant in a "Pro" tier, with the provider cost passed through or bundled.

## Operations

* Install: the module is in the default `CAMPUS_MODULES` list, so a fresh stack installs it.
  Existing stacks pick it up on the next `./scripts/update.sh`.
* Uninstall: remove `ideastone_ai` from `CAMPUS_MODULES` and uninstall it from Apps; the base
  modules are unaffected.
* Tests: `--test-tags=/ideastone_ai` (11 tests; the provider is mocked, nothing is called).
