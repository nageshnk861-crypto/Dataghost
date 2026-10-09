import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/apiProxy";

export async function GET(request: NextRequest) {
  return proxyToBackend("/api/dashboard/stats", request, "GET");
}

export async function POST(request: NextRequest) {
  return proxyToBackend("/api/dashboard/stats", request, "POST");
}
