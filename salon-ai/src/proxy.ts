import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import jwt from "jsonwebtoken";
import { SESSION_COOKIE } from "@/lib/auth/session";

const SECRET = process.env.AUTH_SECRET ?? "dev-only-insecure-secret-change-me";

const PUBLIC_PATHS = ["/login", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/apple-icon"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // PWA install metadata must be reachable without a session — the OS reads
  // these before/without ever loading an authenticated page.
  if (PUBLIC_PATHS.some((p) => pathname === p)) {
    return NextResponse.next();
  }

  const token = request.cookies.get(SESSION_COOKIE)?.value;
  let authenticated = false;
  if (token) {
    try {
      jwt.verify(token, SECRET);
      authenticated = true;
    } catch {
      authenticated = false;
    }
  }

  if (!authenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|widget.js).*)",
  ],
};
