// Fails when a component shows text that does not come from the catalogs (FR-001, D-013).
// It looks at JSX text between tags and at the visible attributes a person reads or hears.
// Punctuation, symbols and numbers pass; words do not, except the brand name.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("../src", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const ALLOWED = new Set(["Pono", "P"]);
// Answered to machines, never shown to a person: the health probe.
const MACHINE_ROUTES = new Set(["routes/health.tsx"]);
const VISIBLE_ATTRIBUTES = ["title", "alt", "placeholder", "aria-label", "aria-description"];
const LETTERS = /\p{L}{2,}/u;

function files(directory) {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) return name === "paraglide" ? [] : files(path);
    return path.endsWith(".tsx") ? [path] : [];
  });
}

/** True when the text holds a word that is not the brand. */
function hasWords(text) {
  const rest = text
    .split(/\s+/)
    .filter((word) => !ALLOWED.has(word))
    .join(" ");
  return LETTERS.test(rest);
}

function lineOf(source, index) {
  return source.slice(0, index).split("\n").length;
}

const problems = [];
for (const file of files(ROOT)) {
  if (MACHINE_ROUTES.has(relative(ROOT, file).split("\\").join("/"))) continue;
  const source = readFileSync(file, "utf8");
  // Text nodes: after a tag's closing ">" and before the next "<" or "{".
  // The ">" of an arrow function (=>) opens no text.
  for (const match of source.matchAll(/(?<!=)>([^<>{}]+)(?=[<{])/g)) {
    const text = match[1].trim();
    if (!text || !hasWords(text)) continue;
    // Skip TypeScript generics and arrow bodies that look like text to a regex.
    if (/[;=()]|=>|\b(const|return|type|import)\b/.test(text)) continue;
    problems.push(`${relative(ROOT, file)}:${lineOf(source, match.index)} text "${text}"`);
  }
  for (const attribute of VISIBLE_ATTRIBUTES) {
    const pattern = new RegExp(`\\b${attribute}="([^"]*)"`, "g");
    for (const match of source.matchAll(pattern)) {
      if (hasWords(match[1])) {
        problems.push(`${relative(ROOT, file)}:${lineOf(source, match.index)} ${attribute}="${match[1]}"`);
      }
    }
  }
}

if (problems.length > 0) {
  console.error("Visible text must come from messages/{fr,en}.json:\n" + problems.join("\n"));
  process.exit(1);
}
console.log("No hard-coded visible text.");
