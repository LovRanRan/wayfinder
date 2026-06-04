import { cookies } from "next/headers";

export const SESSION_COOKIE = "wayfinder_session";

export async function sessionTokenFromCookies(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(SESSION_COOKIE)?.value ?? null;
}

export function authorizationHeader(token: string | null): Record<string, string> {
  return token ? { authorization: `Bearer ${token}` } : {};
}
