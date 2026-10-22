import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { Briefcase, Eye, EyeOff, Loader2, AlertCircle } from "lucide-react";
import { useAuth } from "@/lib/auth";

export default function Login() {
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string })?.from ?? "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-500/20 text-brand-400 ring-1 ring-brand-500/30">
            <Briefcase size={24} />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              Welcome back
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Sign in to your JobApply account
            </p>
          </div>
        </div>

        {/* Card */}
        <div className="card p-6 shadow-xl shadow-black/40">
          {error && (
            <div className="mb-4 flex items-start gap-2.5 rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="label">
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="input"
              />
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label htmlFor="password" className="label">
                  Password
                </label>
                <Link
                  to="/forgot-password"
                  className="text-xs text-brand-400 hover:text-brand-300 hover:underline"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={showPw ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input pr-10"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPw(v => !v)}
                  className="absolute inset-y-0 right-3 flex items-center text-slate-400 hover:text-slate-200"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full justify-center py-2.5"
            >
              {isLoading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Signing in…
                </>
              ) : (
                "Sign in"
              )}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="mt-5 text-center text-sm text-slate-400">
          Don't have an account?{" "}
          <Link
            to="/register"
            className="font-medium text-brand-400 hover:text-brand-300 hover:underline"
          >
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
