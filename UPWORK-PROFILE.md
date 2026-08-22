# Upwork Profile & Proposal Kit

Copy-paste-ready content for your Upwork profile, built from the real client work in this repo (not generic filler). I couldn't fetch or edit your live profile directly — this environment has no network access to upwork.com and no way to log into your account — so this is the source content for you to paste in yourself. Should take about 20 minutes to apply everything.

**Why zero clients so far, most likely:** a mixed engineering + software portfolio reads as "not sure what he does" to a client scanning search results in 3 seconds. Upwork rewards a sharp, specific title and overview over a broad one. Below is a focused version aimed at the buyers your delivered work actually fits — small business owners and teams needing automation, ERPs, and AI workflows. Your GCC engineering line (ProtectionGrid) is real and valuable, but it's a B2B sales motion (direct outreach, Gumroad, LinkedIn) more than an Upwork-job-post motion — keep it as a secondary specialized profile, not the main pitch.

---

## 1. Professional Title (main profile)

Upwork's title field is short (~70 characters) and is the single biggest factor in search ranking + click-through. Pick one:

- `Python Automation Developer | n8n, AI Workflows & Business Systems`
- `Business Automation Developer | Python, n8n, Google Sheets/Excel ERPs`
- `AI Workflow & Automation Developer | Python · n8n · Claude/GPT`

Recommended: the second one — "ERP" and "Google Sheets" are things small-business buyers literally type into Upwork search, and you have three delivered projects to prove it.

---

## 2. Profile Overview

Paste into the Overview box. Written to open with proof (not "I am a..."), state outcomes in numbers, and close with a clear next step — the structure Upwork's own ranking and client behavior both reward.

```
I build the systems small businesses run on when spreadsheets and manual work stop scaling — inventory trackers, payroll/billing tools, booking systems, and AI-driven automations that remove repetitive work from your team's day.

Recent examples:
• Rebuilt a manufacturer's tracking process from an Excel sheet into a full Python desktop app, then again into a mobile-installable web app — three iterations until it actually fit how the team worked, not just how a spec described it.
• Built a payroll and billing system handling recurring invoicing and payroll for a 300-person workforce.
• Designed an n8n + Claude AI content pipeline that takes an idea from a spreadsheet to an approved, published LinkedIn post with zero manual formatting — running in production today.
• Delivered a lightweight Google Sheets ERP that a small business still runs daily operations on.

Before software, I spent 15+ years as a protection & automation engineer on industrial panel floors, running acceptance tests and living inside AS9100/ISO 9001 quality systems. That background shows up in how I build for you: I document what I ship, I test before I hand it over, and I don't consider a project done until you can run it without me in the room.

Stack: Python, Flask, FastAPI, SQLite/PostgreSQL, n8n, Claude/OpenAI APIs, React, Google Apps Script, Excel/openpyxl.

If something in your business runs on manual work, duct-taped spreadsheets, or a tool nobody likes using — tell me what's slow, and I'll tell you what's fixable, realistically, before you spend a dollar.
```

(~1,650 characters — well inside Upwork's 5,000 limit, but short enough that clients actually read the whole thing.)

---

## 3. Skills (add exactly these — Upwork allows up to 15, and search matches on them directly)

```
Python
Automation
n8n
Business Process Automation
API Integration
Flask
FastAPI
Google Apps Script
Google Sheets
Excel VBA
SQLite
PostgreSQL
AI Chatbot Development
Workflow Automation
ERP Development
```

Swap any 1-2 for terms you see repeated in job posts you're targeting once you start browsing — Upwork's algorithm favors skills that match live demand.

---

## 4. Portfolio Projects (add each as a separate Upwork Portfolio entry)

Upwork portfolio items need a title, short description, skills tags, and ideally an image — even a clean screenshot or the mockup graphics already in this repo's `index.html` project cards work fine as placeholders until you have real screenshots.

**1. School Furniture Manufacturing ERP**
> Rebuilt a manufacturer's operations tracking from a manual Excel sheet into a Python/Tkinter/SQLite desktop app, then again into a Flask-based progressive web app packaged as a single-file Android install — three iterations to match exactly how the team actually worked.
> Skills: Python, Tkinter, SQLite, Flask, PWA

**2. Payroll & Billing System for a 300-Person Workforce**
> Built a payroll and billing system for a manpower contracting company, automating recurring billing cycles and staff payroll that were previously handled manually.
> Skills: Python, SQLite, Business Automation

**3. AI Content Pipeline (n8n + Claude API)**
> Designed and shipped a production automation: content ideas in Google Sheets get drafted by the Claude API, routed through Telegram for one-tap human approval, then auto-published to LinkedIn — zero manual formatting, running daily.
> Skills: n8n, Claude API, Workflow Automation, Telegram Bot API

**4. Google Sheets ERP for Small Business Operations**
> Built a lightweight but complete ERP inside Google Sheets + Apps Script to run day-to-day inventory and operations for a small business — no separate software license or hosting needed.
> Skills: Google Sheets, Google Apps Script, ERP Development

**5. WhatsApp Salon Booking System (Prototype)**
> Built a booking system prototype that lets customers schedule salon appointments entirely through WhatsApp conversation, on a FastAPI/PostgreSQL/Redis backend.
> Skills: FastAPI, PostgreSQL, Redis, Chatbot Development

**6. ProtectionGrid — LV/MV Panel Engineering Tools** *(add to a secondary "engineering" specialized profile, not the main one)*
> A product line of estimation, configuration, and ATP/FAT testing tools for GCC LV/MV panel builders and commissioning engineers, built from 15+ years of hands-on panel-floor and QMS experience. Includes a costing tool, a genset configurator, and a 5-tool ATP/FAT Excel pack distributed commercially.
> Skills: Excel/VBA, Engineering Documentation, ETAP, Process Automation

---

## 5. Proposal (Cover Letter) Templates

Upwork ranks proposals partly on relevance and speed of response — send these within the first hour of a job posting when possible, and always edit the bracketed parts to reference something specific from the actual job post (client names get flagged; specifics don't).

### Template A — Automation / n8n / Workflow jobs

```
Hi [Client name],

I read through your post — sounds like [specific task/pain point from their listing] is eating time your team could spend elsewhere.

I built something close to this recently: an n8n workflow that pulls content from Google Sheets, drafts it with the Claude API, routes it through Telegram for approval, and auto-publishes — running in production with zero manual steps today. I also automated payroll/billing for a 300-person workforce, so I'm comfortable with real operational stakes, not just demo workflows.

For your project, I'd start by [one concrete first step specific to their post] — happy to hop on a quick call to scope it properly before any commitment.

15+ years in engineering/QMS before software means I document what I build and test it before handing it over — you won't be left guessing how it works.

[Your name]
```

### Template B — Google Sheets / Excel / small-business systems jobs

```
Hi [Client name],

Spreadsheets that turn into a real system without turning into a mess — that's most of what I do. I built a Google Sheets ERP that a small business still runs live operations on, and I rebuilt another client's Excel tracker into a full desktop app, then a mobile-ready web app, iterating until it actually matched how their team worked.

For [their specific need], I'd approach it by [one concrete detail from their post]. I can start with a quick working version so you can react to something real, not a spec.

Happy to share the Sheets ERP as a reference if useful.

[Your name]
```

### Template C — Python/Flask app development jobs

```
Hi [Client name],

On the stack you're asking for — Python/Flask backend work is what I ship most. Recent example: a payroll and billing system for a 300-person workforce (Python + SQLite), and a manufacturing tracker that went from Excel → Python desktop app → Flask PWA across three rebuilds to match real usage, not just a spec.

For your project, my first move would be [one specific detail from their post] so we can validate the core flow early rather than late.

15 years in engineering before software means documentation and testing aren't an afterthought — what I hand you will be something your team can actually maintain.

[Your name]
```

---

## 6. Getting the first review (zero-reviews strategy)

- **Rate:** with zero reviews, price a shade below market to win the first 2-3 jobs on trust, then raise it. For this skillset, $20-30/hr fixed or hourly to start is reasonable in most markets — raise after your first 3 five-star jobs.
- **First jobs:** target small, well-scoped fixed-price jobs (Sheets/Excel fixes, small automations) over big ones — faster to deliver, faster to get a review, lower client risk on their end too.
- **Connects:** spend them on jobs posted in the last few hours where the client has a payment method verified — response speed matters more than proposal length early on.
- **Specialized profile:** once the main profile has a few reviews, add a second Upwork "specialized profile" for the ProtectionGrid/engineering-tools niche — different title, different portfolio subset (item 6 above), same account.
- **Video intro:** Upwork profiles with a 30-60s intro video convert noticeably better — even a simple screen-recorded walkthrough of the AI content pipeline or the Sheets ERP would work as a demo.
