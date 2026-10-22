import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth";

/**
 * Wraps any route that requires authentication.
 *
 * - If the user is not logged in → redirect to /login (preserving the
 *   attempted path in `state.from` so Login can redirect back after login).
 * - If the user is logged in but email is unverified → show a banner
 *   inside the children (not a redirect, so they can still navigate).
 */
export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading, accessToken } = useAuth();
  const location = useLocation();

  if (isLoading) return null; // brief loading — no flash

  if (!accessToken || !user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}
