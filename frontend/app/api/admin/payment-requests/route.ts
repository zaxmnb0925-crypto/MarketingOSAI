import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

export async function GET() {
  const token = (await cookies()).get("marketingos_access_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const response = await backendFetch(
    "/api/platform-admin/payment-requests",
    { headers: { Authorization: `Bearer ${token}` } },
  );

  return NextResponse.json(await response.json(), { status: response.status });
}
