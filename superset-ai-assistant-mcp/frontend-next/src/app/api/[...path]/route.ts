import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100").replace(/\/+$/, "");
}

function buildTargetUrl(path: string[], search: string): string {
  const encodedPath = path.map((segment) => encodeURIComponent(segment)).join("/");
  return `${getApiBaseUrl()}/api/${encodedPath}${search}`;
}

function buildProxyHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  const target = new URL(getApiBaseUrl());
  headers.set("host", target.host);
  headers.set("x-forwarded-host", request.headers.get("host") || "");
  headers.set("x-forwarded-proto", request.nextUrl.protocol.replace(":", ""));
  headers.set("x-forwarded-for", request.headers.get("x-forwarded-for") || "127.0.0.1");
  return headers;
}

function buildResponseHeaders(upstream: Response): Headers {
  const headers = new Headers();
  upstream.headers.forEach((value, key) => {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase()) || key.toLowerCase() === "set-cookie") {
      return;
    }
    headers.append(key, value);
  });

  const getSetCookie = (upstream.headers as Headers & {
    getSetCookie?: () => string[];
  }).getSetCookie;
  if (typeof getSetCookie === "function") {
    for (const cookie of getSetCookie.call(upstream.headers)) {
      headers.append("set-cookie", cookie);
    }
  } else {
    const cookie = upstream.headers.get("set-cookie");
    if (cookie) {
      headers.append("set-cookie", cookie);
    }
  }

  return headers;
}

async function proxyRequest(
  request: NextRequest,
  { params }: { params: { path: string[] } },
): Promise<Response> {
  const targetUrl = buildTargetUrl(params.path, request.nextUrl.search);
  const headers = buildProxyHeaders(request);
  const method = request.method.toUpperCase();

  const init: RequestInit = {
    method,
    headers,
    redirect: "manual",
    cache: "no-store",
  };

  if (method !== "GET" && method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  try {
    const upstream = await fetch(targetUrl, init);
    const responseHeaders = buildResponseHeaders(upstream);
    const responseBody =
      method === "HEAD" ? null : await upstream.arrayBuffer();

    return new Response(responseBody, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    const detail =
      error instanceof Error ? error.message : "Failed to reach assistant API";
    return Response.json(
      { detail: `Assistant API proxy error: ${detail}` },
      { status: 502 },
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
export const OPTIONS = proxyRequest;
export const HEAD = proxyRequest;
