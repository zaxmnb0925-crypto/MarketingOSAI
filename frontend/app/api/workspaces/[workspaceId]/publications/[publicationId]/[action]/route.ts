import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

type RouteContext = {
  params: Promise<{
    workspaceId: string;
    publicationId: string;
    action: string;
  }>;
};

const allowedActions = new Set([
  "publish-activation",
  "publish-confirmation",
  "publish",
]);

export async function POST(
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
    publicationId,
    action,
  } = await context.params;

  if (!allowedActions.has(action)) {
    return NextResponse.json(
      { detail: "Unsupported publication action" },
      { status: 404 },
    );
  }

  const headers: HeadersInit = {
    Authorization: `Bearer ${token}`,
  };

  let body: string | undefined;

  if (action === "publish") {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(await request.json());
  }

  try {
    const response = await backendFetch(
      `/api/workspaces/${encodeURIComponent(
        workspaceId,
      )}/publications/${encodeURIComponent(
        publicationId,
      )}/${action}`,
      {
        method: "POST",
        headers,
        ...(body ? { body } : {}),
      },
    );

    const data = await response.json().catch(() => ({
      detail: "Publication action unavailable",
    }));

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Publication action unavailable" },
      { status: 502 },
    );
  }
}
