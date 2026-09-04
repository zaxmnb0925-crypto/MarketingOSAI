import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

type RouteContext = {
  params: Promise<{
    workspaceId: string;
    brandId: string;
    segments: string[];
  }>;
};

const ALLOWED_ROOTS = new Set([
  "recommendations",
  "activations",
  "effects",
  "degradation-recommendations",
  "remediations",
  "governance-cases",
]);

function safeSegments(segments: string[]) {
  return (
    segments.length > 0 &&
    ALLOWED_ROOTS.has(segments[0]) &&
    segments.every((segment) => /^[a-z0-9-]+$/i.test(segment))
  );
}

async function forward(
  request: Request,
  context: RouteContext,
) {
  const cookieStore = await cookies();
  const token = cookieStore.get("marketingos_access_token")?.value;

  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const { workspaceId, brandId, segments } = await context.params;

  if (
    !/^[0-9a-f-]{36}$/i.test(workspaceId) ||
    !/^[0-9a-f-]{36}$/i.test(brandId) ||
    !safeSegments(segments)
  ) {
    return NextResponse.json(
      { detail: "Unsupported governance route" },
      { status: 400 },
    );
  }

  const upstreamPath =
    `/api/workspaces/${workspaceId}/brands/${brandId}` +
    `/content/quality-policy/${segments.join("/")}`;

  try {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
    };
    let body: string | undefined;

    if (request.method !== "GET") {
      headers["Content-Type"] = "application/json";
      body = await request.text();
    }

    const response = await backendFetch(upstreamPath, {
      method: request.method,
      headers,
      body,
    });
    const text = await response.text();
    const data = text ? JSON.parse(text) : null;

    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Quality governance service unavailable" },
      { status: 502 },
    );
  }
}

export async function GET(request: Request, context: RouteContext) {
  return forward(request, context);
}

export async function POST(request: Request, context: RouteContext) {
  return forward(request, context);
}
