import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

type RouteContext = {
  params: Promise<{ conversationId: string }>;
};

async function proxy(
  request: Request,
  context: RouteContext,
) {
  const token = (await cookies()).get("marketingos_access_token")?.value;

  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const { conversationId } = await context.params;
  const response = await backendFetch(
    `/api/platform-admin/support/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: request.method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(request.method === "POST"
          ? { "Content-Type": "application/json" }
          : {}),
      },
      ...(request.method === "POST"
        ? { body: await request.text() }
        : {}),
    },
  );

  const data = await response.json().catch(() => ({
    detail: "Support service unavailable",
  }));

  return NextResponse.json(data, { status: response.status });
}

export const GET = proxy;
export const POST = proxy;
