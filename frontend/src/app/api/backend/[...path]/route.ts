import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  // The proxy only reaches this configured server, never a URL supplied by a caller.
  const base = new URL(process.env.BACKEND_URL ?? "http://127.0.0.1:18000");
  if (path.some((segment) => segment === ".." || segment === "." || segment.includes("/"))) {
    return Response.json({ error: "Chemin invalide." }, { status: 400 });
  }
  base.pathname = `/${path.map(encodeURIComponent).join("/")}`;
  base.search = request.nextUrl.search;
  const isStream = path.at(-1) === "events";
  const signal = isStream
    ? request.signal
    : AbortSignal.any([request.signal, AbortSignal.timeout(8000)]);
  try {
    const headers = new Headers({ Accept: isStream ? "text/event-stream" : "application/json" });
    if (request.headers.has("Content-Type")) headers.set("Content-Type", request.headers.get("Content-Type")!);
    if (request.headers.has("Last-Event-ID")) headers.set("Last-Event-ID", request.headers.get("Last-Event-ID")!);
    const upstream = await fetch(base, {
      method: request.method, cache: "no-store", signal,
      headers,
      body: request.method === "POST" ? await request.text() : undefined,
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
        "Cache-Control": "no-store, no-transform",
        "X-Accel-Buffering": "no",
      },
    });
  } catch {
    return Response.json({ error: "Service applicatif injoignable." }, { status: 502 });
  }
}

export const GET = forward;
export const POST = forward;
