import { cookies, headers } from "next/headers";

export async function serverFetch(path: string, init?: RequestInit): Promise<Response> {
  const cookieStore = await cookies();
  const headersList = await headers();

  const base =
    process.env.API_BASE_URL ??
    (() => {
      const host = headersList.get("host") ?? "localhost:3000";
      const proto = headersList.get("x-forwarded-proto") ?? "http";
      return `${proto}://${host}`;
    })();

  return fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      cookie: cookieStore.toString(),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
}
