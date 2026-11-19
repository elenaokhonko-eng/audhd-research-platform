const SLUG = /^[a-z0-9-]{1,40}$/;

// A campaign slug from outside is used only when it is a plain slug; anything else is dropped.
export function cleanSlug(value: unknown): string | null {
  return typeof value === "string" && SLUG.test(value) ? value : null;
}
