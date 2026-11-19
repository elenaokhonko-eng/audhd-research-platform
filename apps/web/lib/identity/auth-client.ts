export type AuthErrorCode =
  | "invalid_email"
  | "link_expired"
  | "link_used"
  | "popup_closed"
  | "network"
  | "unknown";

export class AuthError extends Error {
  constructor(readonly code: AuthErrorCode) {
    super(code);
    this.name = "AuthError";
  }
}

export interface AuthClient {
  sendEmailLink(email: string, continueUrl: string): Promise<void>;
  isEmailLink(href: string): boolean;
  completeEmailLink(email: string, href: string): Promise<string>;
  signInWithGoogle(): Promise<string>;
}

const SDK_CODES: Record<string, AuthErrorCode> = {
  "auth/invalid-email": "invalid_email",
  "auth/expired-action-code": "link_expired",
  "auth/invalid-action-code": "link_used",
  "auth/popup-closed-by-user": "popup_closed",
  "auth/cancelled-popup-request": "popup_closed",
  "auth/network-request-failed": "network",
};

export function toAuthError(error: unknown): AuthError {
  if (error instanceof AuthError) return error;
  const code = (error as { code?: unknown } | null | undefined)?.code;
  return new AuthError(typeof code === "string" ? (SDK_CODES[code] ?? "unknown") : "unknown");
}

function oobCodeOf(href: string): string | null {
  try {
    return new URL(href).searchParams.get("oobCode");
  } catch {
    return null;
  }
}

export function createFirebaseAuthClient(config: { apiKey: string; authDomain: string }): AuthClient {
  let loaded: Promise<{
    auth: import("firebase/auth").Auth;
    sdk: typeof import("firebase/auth");
  }> | null = null;

  function load() {
    loaded ??= (async () => {
      const [{ getApps, initializeApp }, sdk] = await Promise.all([import("firebase/app"), import("firebase/auth")]);
      const app = getApps()[0] ?? initializeApp(config);
      const auth = sdk.initializeAuth(app, { persistence: sdk.inMemoryPersistence });
      return { auth, sdk };
    })();
    return loaded;
  }

  // Take the token, then sign the SDK out so no refresh token stays in the browser.
  async function tokenThenSignOut(
    { auth, sdk }: Awaited<ReturnType<typeof load>>,
    user: import("firebase/auth").User,
  ): Promise<string> {
    const token = await user.getIdToken();
    try {
      await sdk.signOut(auth);
    } catch {
      // The token is already ours; a failed sign-out must not fail the sign-in.
    }
    return token;
  }

  return {
    async sendEmailLink(email, continueUrl) {
      try {
        const { auth, sdk } = await load();
        await sdk.sendSignInLinkToEmail(auth, email, { url: continueUrl, handleCodeInApp: true });
      } catch (error) {
        throw toAuthError(error);
      }
    },
    // Synchronous by contract, so the SDK may not be loaded yet: check the URL
    // for the parameters Firebase puts in a sign-in link (mode=signIn and oobCode).
    isEmailLink(href) {
      try {
        const params = new URL(href).searchParams;
        return params.get("mode") === "signIn" && Boolean(params.get("oobCode"));
      } catch {
        return false;
      }
    },
    async completeEmailLink(email, href) {
      try {
        const ctx = await load();
        const result = await ctx.sdk.signInWithEmailLink(ctx.auth, email, href);
        return await tokenThenSignOut(ctx, result.user);
      } catch (error) {
        throw toAuthError(error);
      }
    },
    async signInWithGoogle() {
      try {
        const ctx = await load();
        const result = await ctx.sdk.signInWithPopup(ctx.auth, new ctx.sdk.GoogleAuthProvider());
        return await tokenThenSignOut(ctx, result.user);
      } catch (error) {
        throw toAuthError(error);
      }
    },
  };
}

export function createFakeAuthClient(): AuthClient {
  return {
    async sendEmailLink() {},
    isEmailLink: (href) => oobCodeOf(href) !== null,
    async completeEmailLink(email, href) {
      const code = oobCodeOf(href);
      if (code === "expired") throw new AuthError("link_expired");
      if (code === "used") throw new AuthError("link_used");
      return `fake-token:${email.split("@")[0]}`;
    },
    async signInWithGoogle() {
      return "fake-token:bo";
    },
  };
}
