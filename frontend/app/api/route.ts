import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "ok",
    name: "DataGhost DLP Cloud API",
    version: "2.4.0",
    timestamp: new Date().toISOString(),
  });
}
