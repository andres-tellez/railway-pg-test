/** Marker on errors thrown when we’ve triggered Auth0 login — UI should not show raw Auth0 strings. */
export const AUTH_REDIRECT_ERROR_CODE = "AUTH_REDIRECT" as const;

export function isAuthRedirectError(err: unknown): boolean {
  return (
    typeof err === "object" &&
    err !== null &&
    (err as { code?: string }).code === AUTH_REDIRECT_ERROR_CODE
  );
}

export function createAuthRedirectError(): Error {
  const e = new Error("Redirecting to sign in…");
  (e as { code?: string }).code = AUTH_REDIRECT_ERROR_CODE;
  return e;
}

/**
 * Auth0 / SDK errors when refresh or silent auth fails — force interactive login instead of broken API calls.
 */
export function needsReauthentication(err: unknown): boolean {
  const parts: string[] = [];
  const collect = (v: unknown) => {
    if (v == null) return;
    if (typeof v === "string") {
      parts.push(v);
      return;
    }
    if (typeof v === "number") {
      parts.push(String(v));
      return;
    }
    if (typeof v === "object") {
      const o = v as Record<string, unknown>;
      for (const k of ["message", "error", "error_description", "description"]) {
        if (typeof o[k] === "string") parts.push(o[k] as string);
      }
    }
  };

  collect(err);
  if (typeof err === "object" && err !== null) {
    const o = err as Record<string, unknown>;
    collect(o.error);
    collect(o.message);
    collect(o.error_description);
    if (typeof o.response === "object" && o.response !== null) {
      const r = o.response as Record<string, unknown>;
      collect(r.data);
      collect(r.status);
    }
  }

  const msg = parts.join(" ").toLowerCase();

  return (
    msg.includes("missing_refresh_token") ||
    msg.includes("consent_required") ||
    msg.includes("login_required") ||
    msg.includes("invalid refresh token") ||
    msg.includes("invalid_refresh_token") ||
    msg.includes("unknown or invalid refresh token") ||
    msg.includes("invalid_grant") ||
    (msg.includes("refresh token") && msg.includes("invalid")) ||
    /\b403\b/.test(msg)
  );
}
