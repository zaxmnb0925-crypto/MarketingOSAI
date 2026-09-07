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

export async function PATCH(
  request: Request,
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
      `/api/workspaces/${encodeURIComponent(workspaceId)}/brands/${encodeURIComponent(brandId)}/content/${encodeURIComponent(generationId)}`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: await request.text(),
      },
    );

    const data = await response.json().catch(() => ({
      detail: "Content save service unavailable",
    }));

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Content save service unavailable" },
      { status: 502 },
    );
  }
}
