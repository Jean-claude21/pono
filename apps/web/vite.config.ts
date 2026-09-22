import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import netlify from "@netlify/vite-plugin-tanstack-start";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    tanstackStart(),
    // L'émulateur Edge imposerait Deno à quiconque lance simplement `pnpm dev`.
    netlify({ dev: { edgeFunctions: { enabled: false } } }),
    tailwindcss(),
    react(),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
