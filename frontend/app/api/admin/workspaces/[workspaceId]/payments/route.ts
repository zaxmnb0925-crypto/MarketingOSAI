import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

type RouteContext = { params: Promise<{ workspaceId: string }> };

export async function POST(request: Request, context: RouteContext) {
  const token = (await cookies()).get("marketingos_access_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { workspaceId } = await context.params;
  const response = await backendFetch(
    `/api/platform-admin/workspaces/${encodeURIComponent(workspaceId)}/payments/manual`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: await request.text(),
    },
  );

  return NextResponse.json(await response.json(), { status: response.status });
}

export async function GET(
  request: Request,
  context: { params: Promise<{ workspaceId: string }> },
) {
  const token = (await cookies()).get(
    "marketingos_access_token",
  )?.value;

  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const { workspaceId } = await context.params;
  const incoming = new URL(request.url);
  const query = new URLSearchParams();

  for (const key of ["status", "limit", "offset"]) {
    const value = incoming.searchParams.get(key);
    if (value !== null) query.set(key, value);
  }

  const queryString = query.toString();
  const target =
    `/api/platform-admin/workspaces/${encodeURIComponent(workspaceId)}/payments` +
    (queryString ? `?${queryString}` : "");

  try {
    const response = await backendFetch(target, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await response.json();

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Payment service unavailable" },
      { status: 502 },
    );
  }
}
