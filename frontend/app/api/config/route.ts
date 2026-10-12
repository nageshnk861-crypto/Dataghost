import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";
  return NextResponse.json({
    backendUrl,
    environment: process.env.NODE_ENV,
    configStatus: process.env.BACKEND_URL ? "BACKEND_URL is set" : "BACKEND_URL is NOT set (using default localhost)",
  });
}
