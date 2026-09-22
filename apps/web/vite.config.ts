import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

// Pono tourne sur Coolify (D-012) : la sortie est un serveur Node servi par srvx,
// sans plugin propre à un hébergeur.
export default defineConfig({
  plugins: [tailwindcss(), tanstackStart(), react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
