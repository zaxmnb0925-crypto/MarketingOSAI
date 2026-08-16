import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

type RouteContext = {
  params: Promise<{
    workspaceId: string;
  }>;
};

async function getAccessToken() {
  const cookieStore = await cookies();

  return cookieStore.get(
    "marketingos_access_token",
  )?.value;
}

export async function GET(
  _request: NextRequest,
  context: RouteContext,
) {
  const token = await getAccessToken();

  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const { workspaceId } =
    await context.params;

  const response = await backendFetch(
    `/api/workspaces/${workspaceId}/brands`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  const body = await response.json();

  return NextResponse.json(
    body,
    { status: response.status },
  );
}

export async function POST(
  request: NextRequest,
  context: RouteContext,
) {
  const token = await getAccessToken();

  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const { workspaceId } =
    await context.params;

  const payload = await request.json();

  const response = await backendFetch(
    `/api/workspaces/${workspaceId}/brands`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );

  const body = await response.json();

  return NextResponse.json(
    body,
    { status: response.status },
  );
}
