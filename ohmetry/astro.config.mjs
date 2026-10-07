import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';

// Domain is not purchased yet. Change `site` if the registrar check fails.
export default defineConfig({
  site: 'https://ohmetry.com',
  trailingSlash: 'always',
  integrations: [react(), mdx(), sitemap()],
});
