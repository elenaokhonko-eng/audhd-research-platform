// Ends the session in this browser. Used by every control that signs a person out.
export async function defaultSignOut(): Promise<void> {
  await fetch("/api/session", { method: "DELETE", credentials: "same-origin" });
}

// Signs out, forgets any stored sign-in address, then goes to /join even when the sign-out failed.
export async function leaveToJoin(signOut: () => Promise<void>, go: (url: string) => void): Promise<void> {
  try {
    await signOut();
  } catch {
    // Go to the sign-in page either way.
  }
  try {
    localStorage.removeItem("signin.email");
  } catch {
    // Storage unavailable: nothing to remove.
  }
  go("/join");
}
