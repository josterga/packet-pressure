import { defineConfig } from "vite";
import { readFileSync } from "fs";
import { resolve } from "path";

export default defineConfig({
  base: "/play/",
  build: {
    outDir: "../docs/play",
    emptyOutDir: true,
  },
  plugins: [
    {
      name: "serve-landing",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          const url = req.url?.split("?")[0];
          if (url === "/" || url === "/index.html") {
            res.setHeader("Content-Type", "text/html");
            res.end(readFileSync(resolve(__dirname, "../docs/index.html"), "utf-8"));
          } else if (url === "/style.css") {
            res.setHeader("Content-Type", "text/css");
            res.end(readFileSync(resolve(__dirname, "../docs/style.css"), "utf-8"));
          } else {
            next();
          }
        });
      },
    },
  ],
});
