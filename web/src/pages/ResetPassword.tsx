import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Briefcase, Eye, EyeOff, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    if (!token) { setError("Invalid or missing reset token."); return; }
    setLoading(true);
    try {
      await api.auth.confirmPasswordReset(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-500/20 text-brand-400 ring-1 ring-brand-500/30">
            <Briefcase size={24} />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Set new password</h1>
        </div>

        <div className="card p-6 shadow-xl shadow-black/40">
          {done ? (
            <div className="flex flex-col items-center gap-4 py-2 text-center">
              <CheckCircle2 size={36} className="text-brand-400" />
              <p className="text-sm text-slate-300">Password updated successfully.</p>
              <button onClick={() => navigate("/login")} className="btn-primary mt-2 w-full justify-center py-2.5">
                Sign in with new password
              </button>
            </div>
          ) : (
            <>
              {!token && (
                <div className="mb-4 flex items-start gap-2.5 rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  <span>Invalid reset link. Please request a new one.</span>
                </div>
              )}
              {error && (
                <div className="mb-4 flex items-start gap-2.5 rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  <span>{error}</span>
                </div>
              )}
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="password" className="label">New password</label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPw ? "text" : "password"}
                      required
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      placeholder="At least 8 characters"
                      className="input pr-10"
                    />
                    <button type="button" tabIndex={-1} onClick={() => setShowPw(v => !v)}
                      className="absolute inset-y-0 right-3 flex items-center text-slate-400 hover:text-slate-200">
                      {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
                <div>
                  <label htmlFor="confirm" className="label">Confirm password</label>
                  <input
                    id="confirm"
                    type={showPw ? "text" : "password"}
                    required
                    value={confirm}
                    onChange={e => setConfirm(e.target.value)}
                    placeholder="••••••••"
                    className={`input ${confirm && confirm !== password ? "border-rose-500/60" : ""}`}
                  />
                </div>
                <button type="submit" disabled={loading || !token}
                  className="btn-primary w-full justify-center py-2.5">
                  {loading ? <><Loader2 size={16} className="animate-spin" /> Updating…</> : "Set new password"}
                </button>
              </form>
            </>
          )}
        </div>

        <p className="mt-5 text-center text-sm">
          <Link to="/login" className="text-brand-400 hover:text-brand-300 hover:underline">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
