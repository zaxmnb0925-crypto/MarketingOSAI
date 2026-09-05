import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

type RouteContext = {
  params: Promise<{ requestId: string }>;
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

  const { requestId } = await context.params;

  const response = await backendFetch(
    `/api/platform-admin/payment-requests/${requestId}/contact`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  return NextResponse.json(await response.json(), {
    status: response.status,
  });
}
