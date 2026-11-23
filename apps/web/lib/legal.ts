import { readFileSync } from "node:fs";
import { join } from "node:path";
import { marked } from "marked";

export type LegalDoc = { title: string; version: string; effectiveFrom: string; html: string };

// Reads the owner-approved Markdown from the repository. Only these files are ever passed to
// marked; nothing a visitor typed is.
export function readLegal(name: "terms" | "privacy", dir: string = join(process.cwd(), "content", "legal")): LegalDoc {
  const text = readFileSync(join(dir, `${name}.md`), "utf8").replace(/\r\n/g, "\n");
  const lines = text.split("\n");
  if (lines[0] !== "---") throw new Error(`${name}.md has no front matter block`);
  const end = lines.indexOf("---", 1);
  if (end === -1) throw new Error(`${name}.md has no closing --- for its front matter`);
  const fields: Record<string, string> = {};
  for (const line of lines.slice(1, end)) {
    const at = line.indexOf(":");
    if (at > 0) fields[line.slice(0, at).trim()] = line.slice(at + 1).trim();
  }
  const need = (key: string): string => {
    const value = fields[key];
    if (!value) throw new Error(`${name}.md front matter is missing ${key}`);
    return value;
  };
  const title = need("title");
  const version = need("version");
  const effectiveFrom = need("effective_from");
  const html = marked.parse(lines.slice(end + 1).join("\n"), { async: false, gfm: true });
  return { title, version, effectiveFrom, html };
}
