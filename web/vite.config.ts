import { defineConfig } from "vite";

export default defineConfig({
  base: "/play/",
  build: {
    outDir: "../docs/play",
    emptyOutDir: true,
  },
});
