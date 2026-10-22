import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Briefcase, Eye, EyeOff, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";

export default function Register() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const strength = (() => {
    if (!password) return 0;
    let s = 0;
    if (password.length >= 8) s++;
    if (/[A-Z]/.test(password)) s++;
    if (/[0-9]/.test(password)) s++;
    if (/[^A-Za-z0-9]/.test(password)) s++;
    return s;
  })();
  const strengthLabel = ["", "Weak", "Fair", "Good", "Strong"][strength];
  const strengthColor = ["", "bg-rose-500", "bg-amber-500", "bg-brand-500", "bg-brand-400"][strength];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      await api.auth.register(email, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
        <div className="w-full max-w-md">
          <div className="card p-8 text-center shadow-xl shadow-black/40">
            <CheckCircle2 size={40} className="mx-auto mb-4 text-brand-400" />
            <h2 className="text-xl font-semibold text-slate-100">Check your inbox</h2>
            <p className="mt-2 text-sm text-slate-400">
              We sent a verification link to{" "}
              <span className="font-medium text-slate-200">{email}</span>.
              Click it to activate your account, then sign in.
            </p>
            <button
              onClick={() => navigate("/login")}
              className="btn-primary mt-6 w-full justify-center py-2.5"
            >
              Go to sign in
            </button>
          </div>
        </div>
      </div>
    );
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
              Create your account
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Free to use · Your data stays yours
            </p>
          </div>
        </div>

        <div className="card p-6 shadow-xl shadow-black/40">
          {error && (
            <div className="mb-4 flex items-start gap-2.5 rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="label">Email address</label>
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
              <label htmlFor="password" className="label">Password</label>
              <div className="relative">
                <input
                  id="password"
                  type={showPw ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
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
              {/* Strength bar */}
              {password && (
                <div className="mt-2 flex items-center gap-2">
                  <div className="flex flex-1 gap-1">
                    {[1, 2, 3, 4].map(i => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition-colors ${
                          i <= strength ? strengthColor : "bg-slate-700"
                        }`}
                      />
                    ))}
                  </div>
                  <span className="text-xs text-slate-400">{strengthLabel}</span>
                </div>
              )}
            </div>

            <div>
              <label htmlFor="confirm" className="label">Confirm password</label>
              <input
                id="confirm"
                type={showPw ? "text" : "password"}
                autoComplete="new-password"
                required
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                placeholder="••••••••"
                className={`input ${confirm && confirm !== password ? "border-rose-500/60" : ""}`}
              />
              {confirm && confirm !== password && (
                <p className="mt-1 text-xs text-rose-400">Passwords don't match</p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-2.5"
            >
              {loading ? (
                <><Loader2 size={16} className="animate-spin" /> Creating account…</>
              ) : (
                "Create account"
              )}
            </button>
          </form>
        </div>

        <p className="mt-5 text-center text-sm text-slate-400">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-brand-400 hover:text-brand-300 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
