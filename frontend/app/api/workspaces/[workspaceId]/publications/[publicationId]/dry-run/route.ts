import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

type RouteContext = {
  params: Promise<{
    workspaceId: string;
    publicationId: string;
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

  const { workspaceId, publicationId } =
    await context.params;

  try {
    const response = await backendFetch(
      `/api/workspaces/${encodeURIComponent(
        workspaceId,
      )}/publications/${encodeURIComponent(
        publicationId,
      )}/dry-run`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    const data = await response.json().catch(() => ({
      detail: "Publication preflight unavailable",
    }));

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Publication preflight unavailable" },
      { status: 502 },
    );
  }
}
