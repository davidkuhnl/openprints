import cloudflare from "@astrojs/cloudflare";
import tailwind from "@astrojs/tailwind";
import icon from "astro-icon";
import { defineConfig } from "astro/config";

// https://astro.build/config
export default defineConfig({
  site: "https://openprints.dev",
  output: "hybrid",
  adapter: cloudflare(),
  integrations: [tailwind(), icon()],
});
