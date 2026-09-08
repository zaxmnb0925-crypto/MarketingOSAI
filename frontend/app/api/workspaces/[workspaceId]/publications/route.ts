import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

type RouteContext = {
  params: Promise<{ workspaceId: string }>;
};

export async function GET(
  _request: Request,
  context: RouteContext,
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

  try {
    const response = await backendFetch(
      `/api/workspaces/${encodeURIComponent(workspaceId)}/publications`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    const data = await response.json().catch(() => ({
      detail: "Publication service unavailable",
    }));

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Publication service unavailable" },
      { status: 502 },
    );
  }
}
