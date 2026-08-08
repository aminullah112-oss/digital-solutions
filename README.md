# Aminullah — Digital Solutions Portfolio

A static, interactive portfolio site positioning **ProtectionGrid** (GCC engineering tools) as the flagship product, alongside digital solutions for small business, AI/automation, branding, and compliance/training work.

Built with plain HTML/CSS/JS + Bootstrap 5 — no build step required.

## Structure

```
index.html        Main page
css/style.css      Design system + dark mode
js/main.js         Scroll reveals, project filter, stat counters, theme toggle
.claude/launch.json  Local dev-preview config (npx serve)
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

## Editing content later

- Real project links: search `index.html` for `href="#"`-style placeholders once you have live URLs for Gumroad, LinkedIn, etc.
- Swap the `data-count` numbers in the hero stats as your shipped-product count grows.
- Filter categories live as `data-category` attributes on `.project-item` — add a new project by copying an existing `.project-card` block and tagging it with `business`, `ai`, `branding`, or `compliance`.
