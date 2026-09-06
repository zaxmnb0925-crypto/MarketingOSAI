import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

export async function POST(request: Request) {
  try {
    const response = await backendFetch(
      "/api/public/support/inquiries",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: await request.text(),
      },
    );

    const data = await response.json().catch(() => ({
      detail: "Support service unavailable",
    }));

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Support service unavailable" },
      { status: 502 },
    );
  }
}
