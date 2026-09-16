import { preact } from "@preact/preset-vite";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";
import { buildLabel } from "./tools/version.mjs";

export default defineConfig({
  // Keep Vite's source document separate from the committed build artifact.
  root: "src",
  base: "./",
  publicDir: false,
  plugins: [preact(), viteSingleFile({ removeViteModuleLoader: true })],
  json: { stringify: true },
  // Baked in as a literal so the stamp survives minification and is greppable in
  // both dist/index.html and the committed index.html.
  define: {
    __BUILD_LABEL__: JSON.stringify(buildLabel()),
  },
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    target: "chrome120",
    minify: true,
    sourcemap: false,
    assetsInlineLimit: Number.MAX_SAFE_INTEGER,
  },
});
