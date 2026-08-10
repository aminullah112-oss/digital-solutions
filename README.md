# Aminullah — Digital Solutions Portfolio

A static, interactive portfolio site positioning **ProtectionGrid** (GCC engineering tools) as the flagship product, alongside digital solutions for small business, AI/automation, branding, and compliance/training work.

Built with plain HTML/CSS/JS + Bootstrap 5 — no build step required.

## Structure

```
index.html            Main page
css/style.css         Design system + dark mode
js/main.js            Scroll reveals, project filter, stat counters, theme toggle, lead form
leads-backend/Code.gs  Google Apps Script backend for the contact-section lead form (see below)
.claude/launch.json   Local dev-preview config (npx serve)
```

## Local preview

```bash
npx serve .
```

Then open the printed `http://localhost:PORT` URL. (Opening `index.html` directly via `file://` also works, but scroll-based animations behave better over HTTP.)

## Deploy to GitHub Pages

Deployed as a project repo (the account's root `aminullah112-oss.github.io` already hosts a different existing site, so this lives alongside it):

- Repo: `aminullah112-oss/digital-solutions`
- Live URL: `https://aminullah112-oss.github.io/digital-solutions/`

To redeploy after edits:
```bash
git add .
git commit -m "Update portfolio"
git push
```
GitHub Pages is served from the `main` branch root and rebuilds automatically within a minute or two of each push.

**After editing `css/style.css` or `js/main.js`**, bump that file's version query string in `index.html` (e.g. `style.css?v=3` → `?v=4`, `main.js?v=2` → `?v=3`). GitHub Pages' CDN caches these for 10 minutes with no versioning of its own, so without this bump, visitors (and you) can see a stale file for a while after a redeploy even though the new one is live. If a change looks like it "didn't take," hard-refresh (`Ctrl+Shift+R`) before assuming something broke.

## Lead Capture Backend Setup (Google Sheets + Apps Script)

The Contact section has a real lead-intake form (Name, Company, City, Phone, Email, Interest, Message). It's wired up client-side but needs a one-time backend setup on your Google account — I can't create the Sheet or deploy the script for you, since that requires your own Google login.

**What you get once it's set up:** every submission lands as a new row in a private Google Sheet (only you can see it), Chennai-based submissions are auto-flagged `🔥 Chennai` so they're easy to spot and prioritize, and you get an email notification the moment someone submits.

Steps (about 10 minutes, one-time):

1. Create a new Google Sheet. Rename the first tab to exactly `Leads`.
2. In row 1, add these column headers exactly, in this order:
   `Timestamp | Name | Company | City | Priority | Phone | Email | Interest | Message | Status | Notes`
3. In the Sheet, go to **Extensions → Apps Script**. Delete the placeholder code and paste in the full contents of [`leads-backend/Code.gs`](leads-backend/Code.gs) from this repo.
4. Click **Deploy → New deployment**. Click the gear icon next to "Select type" and choose **Web app**.
   - Description: `Leads intake` (or anything)
   - Execute as: **Me**
   - Who has access: **Anyone**
5. Click **Deploy**. Google will ask you to authorize the script — it's your own script accessing your own Sheet, so approve it (click through the "unverified app" warning: **Advanced → Go to \[project name\] (unsafe)** — this warning is normal for scripts you write yourself and haven't published to the Marketplace).
6. Copy the **Web app URL** it gives you.
7. Open [`js/main.js`](js/main.js), find `var LEADS_ENDPOINT = '';` near the top, and paste the URL between the quotes.
8. Commit and push. Test by submitting the form on the live site yourself — confirm a row appears in the Sheet and you get an email.

**Running it as a lightweight CRM:** once leads are landing in the Sheet, select the `Status` column and add a dropdown (**Data → Data validation**) with values like `New`, `Contacted`, `Qualified`, `Proposal Sent`, `Won`, `Lost`. Add conditional formatting on the `Priority` column to highlight `🔥 Chennai` rows. That's the whole CRM — no separate tool needed.

If you ever redeploy the Apps Script (not just edit-and-save, but a *new* deployment), the Web App URL changes and you'll need to update `LEADS_ENDPOINT` again. Editing the script and using **Deploy → Manage deployments → Edit → New version** keeps the same URL.

## Editing content later

- Real project links: search `index.html` for `href="#"`-style placeholders once you have live URLs for Gumroad, LinkedIn, etc.
- Swap the `data-count` numbers in the hero stats as your shipped-product count grows.
- Filter categories live as `data-category` attributes on `.project-item` — add a new project by copying an existing `.project-card` block and tagging it with `business`, `ai`, `branding`, or `compliance`.
