import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/react-assets/",
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, "../api/app/static/debug/react"),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, "index.html"),
    },
  },
});
