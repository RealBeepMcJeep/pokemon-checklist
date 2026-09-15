import { preact } from "@preact/preset-vite";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  // Keep Vite's source document separate from the committed build artifact.
  root: "src",
  base: "./",
  publicDir: false,
  plugins: [preact(), viteSingleFile({ removeViteModuleLoader: true })],
  json: { stringify: true },
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    target: "chrome120",
    minify: true,
    sourcemap: false,
    assetsInlineLimit: Number.MAX_SAFE_INTEGER,
  },
});
