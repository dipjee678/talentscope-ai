// Same-origin by default: next.config.mjs proxies /api/v1/* to the backend (BACKEND_URL),
// so no CORS setup is needed in production. Set NEXT_PUBLIC_API_URL only to call the
// backend directly (e.g. http://localhost:8000/api/v1).
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

const TOKEN_KEY = "talentscope_access_token";
const REFRESH_KEY = "talentscope_refresh_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

// One shared in-flight refresh so parallel 401s don't each rotate the token.
let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh })
        });
        if (!res.ok) return false;
        const data = await res.json();
        setTokens(data.access_token, data.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }
  return refreshInFlight;
}

/** Returns a valid access token, refreshing it first if the current one has expired. */
export async function getFreshAccessToken(): Promise<string | null> {
  const token = getAccessToken();
  if (token && !isExpired(token)) return token;
  return (await refreshAccessToken()) ? getAccessToken() : token;
}

function isExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp === "number" && payload.exp * 1000 < Date.now() + 10_000;
  } catch {
    return false;
  }
}

// Requests slower than this show the "server is waking up" banner (free-tier hosts sleep when idle).
const SLOW_REQUEST_MS = 4000;
let slowRequests = 0;
export const SLOW_EVENT = "talentscope:slow-requests";

function trackSlow(delta: number): void {
  slowRequests = Math.max(0, slowRequests + delta);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(SLOW_EVENT, { detail: slowRequests }));
  }
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {},
  _retried = false
): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let res: Response;
  let countedSlow = false;
  const slowTimer = setTimeout(() => {
    countedSlow = true;
    trackSlow(+1);
  }, SLOW_REQUEST_MS);
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers
    });
  } catch {
    throw new Error("Cannot reach the TalentScope server. It may be waking up — please retry in a few seconds.");
  } finally {
    clearTimeout(slowTimer);
    if (countedSlow) trackSlow(-1);
  }

  if (res.status === 401 && token && !_retried && !path.startsWith("/auth/")) {
    if (await refreshAccessToken()) {
      return apiFetch<T>(path, options, true);
    }
  }

  if (res.status === 204) {
    return undefined as T;
  }

  let payload: any = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }

  if (!res.ok) {
    const detail =
      payload?.detail ||
      (typeof payload === "string" ? payload : `Request failed (${res.status})`);
    throw new Error(Array.isArray(detail) ? detail.map((d) => d.msg).join(", ") : detail);
  }

  return payload as T;
}
