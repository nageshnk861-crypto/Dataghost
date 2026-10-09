import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/apiProxy";

export async function GET(request: NextRequest) {
  return proxyToBackend("/api/users", request, "GET");
}

export async function POST(request: NextRequest) {
  return proxyToBackend("/api/users", request, "POST");
}
