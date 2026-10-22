import { lazy, Suspense } from "react";
import { Loader2 } from "lucide-react";
import { Route, Routes } from "react-router-dom";

import { AuthProvider } from "@/lib/auth";
import { SearchStateProvider } from "@/lib/SearchStateContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";

// Auth pages — small, eager-load them
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import VerifyEmail from "@/pages/VerifyEmail";

// App pages
import Dashboard from "@/pages/Dashboard";
import JobDetail from "@/pages/JobDetail";
import Freeform from "@/pages/Freeform";
import Searches from "@/pages/Searches";
import NotFound from "@/pages/NotFound";

// CodeMirror editor — code-split to keep initial bundle small
const ArtifactEditor = lazy(() => import("@/pages/ArtifactEditor"));

function EditorFallback() {
  return (
    <div className="card flex items-center gap-2 p-6 text-sm text-slate-300">
      <Loader2 size={16} className="animate-spin" /> Loading editor…
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <SearchStateProvider>
        <Routes>
          {/* ── Public auth routes (no Layout shell) ─────────────────── */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/verify-email" element={<VerifyEmail />} />

          {/* ── Protected routes (require login) ─────────────────────── */}
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/jobs/:jobId" element={<JobDetail />} />
            <Route
              path="/jobs/:jobId/edit/:name"
              element={
                <Suspense fallback={<EditorFallback />}>
                  <ArtifactEditor />
                </Suspense>
              }
            />
            <Route path="/freeform" element={<Freeform />} />
            <Route path="/searches" element={<Searches />} />
          </Route>

          {/* ── 404 ──────────────────────────────────────────────────── */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </SearchStateProvider>
    </AuthProvider>
  );
}
