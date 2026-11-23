// @vitest-environment node
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { identityConfig } from "@/lib/identity/config";
import { readLegal } from "@/lib/legal";

const dirWith = (name: string, text: string) => { const d = mkdtempSync(join(tmpdir(), "legal-")); writeFileSync(join(d, `${name}.md`), text); return d; };

describe("readLegal", () => {
  it("reads the two approved texts with their versions", () => {
    for (const name of ["terms", "privacy"] as const) {
      const doc = readLegal(name);
      expect(doc.version).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(doc.effectiveFrom).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(doc.html).toContain("<h1");
      expect(doc.html).not.toContain("effective_from");
    }
    expect(readLegal("privacy").html).toContain("<table>");
  });
  it("names a missing front-matter key", () => {
    const dir = dirWith("terms", "---\ntitle: T\nversion: 2026-01-01\n---\n\n# T\n");
    expect(() => readLegal("terms", dir)).toThrow(/effective_from/);
  });
  it("refuses a file without front matter", () =>
    expect(() => readLegal("terms", dirWith("terms", "# T\n"))).toThrow(/front matter/));
});

describe("identityConfig, Google button", () => {
  const base = { IDENTITY_API_KEY: "k", IDENTITY_AUTH_DOMAIN: "d", SITE_ENV: "dev" };
  it("is off unless the setting says 1", () => {
    expect(identityConfig(base)).toMatchObject({ kind: "firebase", googleEnabled: false });
    expect(identityConfig({ ...base, IDENTITY_GOOGLE_ENABLED: "1" })).toMatchObject({ kind: "firebase", googleEnabled: true });
    expect(identityConfig({ PLATFORM_API_FAKE: "1", SITE_ENV: "dev" })).toMatchObject({ kind: "fake", googleEnabled: true });
  });
});
