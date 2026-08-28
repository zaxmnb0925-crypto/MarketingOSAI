import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";


export async function GET() {
  try {
    const response = await backendFetch(
      "/api/subscription-plans",
    );
    const data = await response.json();

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Pricing service unavailable" },
      { status: 502 },
    );
  }
}
