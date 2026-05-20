import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/stores/auth";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const isAuth = useAuth((s) => s.isAuthenticated());
  const location = useLocation();
  if (!isAuth) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}
