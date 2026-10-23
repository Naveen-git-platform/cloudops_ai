import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function proxy(request: NextRequest) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) {
    // Fail closed for the dashboard if auth is not configured.
    if (request.nextUrl.pathname === "/" || request.nextUrl.pathname.startsWith("/dashboard")) {
      return NextResponse.redirect(new URL("/login?error=auth_not_configured", request.url));
    }
    return NextResponse.next({ request });
  }

  let response = NextResponse.next({ request });
  const supabase = createServerClient(url, key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
      },
    },
  });

  // getUser verifies the session with Supabase; do not trust getSession alone.
  const { data: { user } } = await supabase.auth.getUser();
  const path = request.nextUrl.pathname;
  const protectedPath = path === "/" || path.startsWith("/dashboard");
  const authPath = ["/login", "/signup", "/forgot-password"].includes(path);

  if (protectedPath && !user) return NextResponse.redirect(new URL("/login", request.url));
  if (authPath && user) return NextResponse.redirect(new URL("/", request.url));
  return response;
}

export const config = {
  matcher: ["/", "/dashboard/:path*", "/login", "/signup", "/forgot-password"],
};
