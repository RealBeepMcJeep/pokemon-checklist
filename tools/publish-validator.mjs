const RESOURCE_TAGS = /<\s*(img|source|iframe|object|embed|audio|video|track)\b[^>]*>/gis;
const ATTRIBUTE = /\b(src|srcset|data|poster)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/gi;
const LINK_TAGS = /<\s*link\b[^>]*>/gis;
const REL = /\brel\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/i;
const HREF = /\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/i;
const SCRIPT_TAGS = /<\s*script\b[^>]*>/gis;
const SCRIPT_SRC = /\bsrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/i;
const STYLE_BLOCK = /<\s*style\b[^>]*>([\s\S]*?)<\s*\/style\s*>/gi;
const STYLE_ATTRIBUTE = /\bstyle\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/gi;
const CSS_URL = /\burl\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*))\s*\)/gi;
const CSS_IMPORT = /@import\s+(?:"([^"]*)"|'([^']*)')/gi;

function firstValue(match) {
  return (match?.[1] ?? match?.[2] ?? match?.[3] ?? "").trim();
}

function isEmbedded(value) {
  return /^(?:data:|#)/i.test(value);
}

/** Extract image URLs from normal HTML srcset candidates, keeping data URL commas. */
export function srcsetCandidates(value) {
  const candidates = [];
  let cursor = 0;
  while (cursor < value.length) {
    while (cursor < value.length && (/[\s,]/.test(value[cursor]))) cursor += 1;
    if (cursor >= value.length) break;
    const start = cursor;
    const isData = value.slice(cursor, cursor + 5).toLowerCase() === "data:";
    while (
      cursor < value.length &&
      (isData ? !/\s/.test(value[cursor]) : !/[\s,]/.test(value[cursor]))
    ) {
      cursor += 1;
    }
    if (cursor > start) candidates.push(value.slice(start, cursor));
    while (cursor < value.length && value[cursor] !== ",") cursor += 1;
    if (value[cursor] === ",") cursor += 1;
  }
  return candidates;
}

/** Return labels for resource references that would make an artifact non-standalone. */
export function standaloneResourceFailures(html) {
  const failures = [];
  const add = (label) => {
    if (!failures.includes(label)) failures.push(label);
  };

  for (const match of html.matchAll(RESOURCE_TAGS)) {
    const tag = match[1].toLowerCase();
    for (const attribute of match[0].matchAll(ATTRIBUTE)) {
      const value = (attribute[2] ?? attribute[3] ?? attribute[4] ?? "").trim();
      const candidates = attribute[1].toLowerCase() === "srcset"
        ? srcsetCandidates(value)
        : [value];
      if (candidates.some((candidate) => !isEmbedded(candidate))) {
        add(`external ${tag}`);
      }
    }
  }

  for (const match of html.matchAll(LINK_TAGS)) {
    const rel = firstValue(match[0].match(REL));
    if (!rel.split(/\s+/).some((value) => value.toLowerCase() === "stylesheet")) continue;
    const value = firstValue(match[0].match(HREF));
    if (!isEmbedded(value)) add("external stylesheet");
  }

  for (const match of html.matchAll(SCRIPT_TAGS)) {
    const source = match[0].match(SCRIPT_SRC);
    if (source && !isEmbedded(firstValue(source))) add("external script");
  }

  const css = [
    ...html.matchAll(STYLE_BLOCK),
    ...html.matchAll(STYLE_ATTRIBUTE),
  ].map((match) => firstValue(match)).join("\n");
  for (const match of css.matchAll(CSS_URL)) {
    if (!isEmbedded(firstValue(match))) add("external CSS url");
  }
  for (const match of css.matchAll(CSS_IMPORT)) {
    if (!isEmbedded(firstValue(match))) add("external CSS import");
  }

  return failures;
}
