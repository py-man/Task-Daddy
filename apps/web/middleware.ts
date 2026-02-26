import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_APP_PATHS = new Set(["/app/help"]);

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (!pathname.startsWith("/app")) return NextResponse.next();
  if (PUBLIC_APP_PATHS.has(pathname)) return NextResponse.next();

  const session = request.cookies.get("nl_session")?.value;
  if (session) return NextResponse.next();

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/app/:path*"],
};
