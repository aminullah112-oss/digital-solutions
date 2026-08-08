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

1. Create a new GitHub repository (e.g. `portfolio`, or `aminullah112-oss.github.io` if you want it at the root of your GitHub domain).
2. From this folder, run:
   ```bash
   git init
   git add .
   git commit -m "Initial portfolio"
   git branch -M main
   git remote add origin https://github.com/aminullah112-oss/<your-repo-name>.git
   git push -u origin main
   ```
3. On GitHub: go to the repo's **Settings → Pages**, set **Source** to `Deploy from a branch`, branch `main`, folder `/ (root)`, then **Save**.
4. After a minute or two, your site will be live at:
   - `https://aminullah112-oss.github.io/<your-repo-name>/` (normal repo), or
   - `https://aminullah112-oss.github.io/` (if the repo is named exactly `aminullah112-oss.github.io`)

## Editing content later

- Real project links: search `index.html` for `href="#"`-style placeholders once you have live URLs for Gumroad, LinkedIn, etc.
- Swap the `data-count` numbers in the hero stats as your shipped-product count grows.
- Filter categories live as `data-category` attributes on `.project-item` — add a new project by copying an existing `.project-card` block and tagging it with `business`, `ai`, `branding`, or `compliance`.
