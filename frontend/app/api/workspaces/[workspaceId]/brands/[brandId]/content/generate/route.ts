import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

type RouteContext = {
  params: Promise<{
    workspaceId: string;
    brandId: string;
  }>;
};

export async function POST(
  request: Request,
  context: RouteContext,
) {
  const cookieStore =
    await cookies();

  const token = cookieStore.get(
    "marketingos_access_token",
  )?.value;

  if (!token) {
    return NextResponse.json(
      {
        detail: "Not authenticated",
      },
      {
        status: 401,
      },
    );
  }

  const {
    workspaceId,
    brandId,
  } = await context.params;

  try {
    const body =
      await request.json();

    const response =
      await backendFetch(
        `/api/workspaces/${workspaceId}/brands/${brandId}/content/generate`,
        {
          method: "POST",
          headers: {
            Authorization:
              `Bearer ${token}`,
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify(body),
        },
      );

    const data =
      await response.json();

    return NextResponse.json(
      data,
      {
        status: response.status,
      },
    );
  } catch {
    return NextResponse.json(
      {
        detail:
          "AI generation service unavailable",
      },
      {
        status: 502,
      },
    );
  }
}
