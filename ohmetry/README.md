# Ohmetry

Static electrical/solar/protection calculator site. Astro + React islands + MDX, Vitest for calculation logic. No backend.

```bash
npm install
npm run dev      # local dev
npm test         # golden-case tests for src/lib/calc
npm run build    # outputs dist/
```

## Adding a calculator (one TS file, one test, one component, one MDX page)

1. `src/lib/calc/<name>.ts`: pure function, no UI imports.
2. `src/lib/calc/<name>.test.ts`: expected values from a published worked example or hand calculation, with the source in a comment.
3. `src/components/<Name>.tsx`: thin React wrapper.
4. `src/pages/<slug>-calculator/index.mdx`: use `layout: ../../layouts/CalcPage.astro`; include formula, code section, worked example, 500 to 900 words, FAQ, related links.
5. Link it from its hub page.

Code tables (NEC 310.16 etc.) go in as data files with the section cited. Do not paste NFPA text.

## Deploy (Cloudflare Pages)

Root directory `ohmetry`, build command `npm run build`, output `dist`. Sitemap is at `/sitemap-index.xml`.

## Before launch

- Domain is not bought. `site` in `astro.config.mjs` and `public/robots.txt` assume `ohmetry.com`.
- Trust pages contain `TODO` placeholders (author bio, contact email, privacy details).
- Calculator pages are under the 500-word target and have no FAQ or related links yet.
