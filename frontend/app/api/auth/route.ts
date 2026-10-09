import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/apiProxy";

export async function POST(request: NextRequest) {
  return proxyToBackend("/api/auth", request, "POST");
}

export async function GET(request: NextRequest) {
  return proxyToBackend("/api/auth", request, "GET");
}
