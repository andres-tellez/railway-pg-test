/**
 * Auth0 SPA `redirect_uri` must match the page origin (www vs apex vs app) that the user
 * actually uses, or silent token refresh (`/oauth/token`) can return 403. `VITE_AUTH0_REDIRECT_URI`
 * is only a build-time fallback (e.g. prerender). In Auth0, add every host you use, e.g.:
 * - `https://www.smartcoach.dev/post-oauth`
 * - `https://smartcoach.dev/post-oauth`
 * - `https://app.smartcoach.dev/post-oauth`
 */
export function getAuth0RedirectUri(): string {
  if (typeof window !== "undefined" && window.location?.origin) {
    return `${window.location.origin}/post-oauth`;
  }
  return import.meta.env.VITE_AUTH0_REDIRECT_URI ?? "";
}
