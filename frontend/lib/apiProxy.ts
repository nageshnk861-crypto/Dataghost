import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

export async function proxyToBackend(
  backendPath: string,
  request: NextRequest,
  method: string
) {
  try {
    const url = new URL(request.url);
    const searchParams = url.searchParams.toString();
    const fullBackendUrl = `${BACKEND_URL}${backendPath}${searchParams ? `?${searchParams}` : ''}`;

    const body = ['GET', 'HEAD'].includes(method) ? undefined : await request.text();

    const response = await fetch(fullBackendUrl, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': request.headers.get('Authorization') || '',
      },
      body,
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend error: ${response.statusText}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to proxy request to backend', details: String(error) },
      { status: 500 }
    );
  }
}
