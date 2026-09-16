import { defineConfig } from "vitest/config";
import { buildLabel } from "./tools/version.mjs";

export default defineConfig({
  // Mirror the app build so src/version.ts resolves the same stamp under test.
  define: {
    __BUILD_LABEL__: JSON.stringify(buildLabel()),
  },
  test: {
    passWithNoTests: false,
    include: ["src/**/*.test.ts"],
  },
});
