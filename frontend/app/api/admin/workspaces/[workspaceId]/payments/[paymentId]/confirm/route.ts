import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

type RouteContext = {
  params: Promise<{ workspaceId: string; paymentId: string }>;
};

export async function POST(request: Request, context: RouteContext) {
  const token = (await cookies()).get("marketingos_access_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { workspaceId, paymentId } = await context.params;
  const response = await backendFetch(
    `/api/platform-admin/workspaces/${encodeURIComponent(workspaceId)}/payments/${encodeURIComponent(paymentId)}/confirm`,
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
