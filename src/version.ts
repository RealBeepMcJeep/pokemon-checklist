// The build stamp is injected as a literal by vite.config.ts / vitest.config.ts.
// The typeof guard keeps this module usable when neither define is applied.
declare const __BUILD_LABEL__: string;

/** Release version plus the commit the build came from, e.g. "v1.0.0 - 8d7c12". */
export const BUILD_LABEL =
  typeof __BUILD_LABEL__ === "string" ? __BUILD_LABEL__ : "v0.0.0 - unknown";
