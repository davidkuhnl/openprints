import cloudflare from "@astrojs/cloudflare";
import sitemap from "@astrojs/sitemap";
import tailwind from "@astrojs/tailwind";
import icon from "astro-icon";
import { defineConfig } from "astro/config";

// https://astro.build/config
export default defineConfig({
  site: "https://openprints.dev",
  adapter: cloudflare(),
  integrations: [tailwind(), icon(), sitemap()],
  // Browsers still request /favicon.ico by default; we only ship SVG.
  redirects: {
    "/favicon.ico": "/favicon.svg",
  },
});
