import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

type RouteContext = { params: Promise<{ workspaceId: string }> };

async function proxy(request: Request, context: RouteContext) {
  const token = (await cookies()).get("marketingos_access_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { workspaceId } = await context.params;
  const response = await backendFetch(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/payment-requests`,
    {
      method: request.method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(request.method === "POST" ? { "Content-Type": "application/json" } : {}),
      },
      ...(request.method === "POST" ? { body: await request.text() } : {}),
    },
  );

  return NextResponse.json(await response.json(), { status: response.status });
}

export const GET = proxy;
export const POST = proxy;
