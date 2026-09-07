import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

type RouteContext = {
  params: Promise<{
    workspaceId: string;
    brandId: string;
    generationId: string;
  }>;
};

export async function POST(
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

  const {
    workspaceId,
    brandId,
    generationId,
  } = await context.params;

  try {
    const response = await backendFetch(
      `/api/workspaces/${encodeURIComponent(workspaceId)}/brands/${encodeURIComponent(brandId)}/content/${encodeURIComponent(generationId)}/draft`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    const data = await response.json().catch(() => ({
      detail: "Draft service unavailable",
    }));

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Draft service unavailable" },
      { status: 502 },
    );
  }
}
