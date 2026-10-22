import { useState } from "react";
import { Link } from "react-router-dom";
import { Briefcase, Loader2, AlertCircle, CheckCircle2, ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.auth.requestPasswordReset(email);
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
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
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">Reset password</h1>
            <p className="mt-1 text-sm text-slate-400">
              {sent
                ? "Check your inbox for the reset link."
                : "Enter your email and we'll send a reset link."}
            </p>
          </div>
        </div>

        <div className="card p-6 shadow-xl shadow-black/40">
          {sent ? (
            <div className="flex flex-col items-center gap-4 py-2 text-center">
              <CheckCircle2 size={36} className="text-brand-400" />
              <p className="text-sm text-slate-300">
                If <span className="font-medium text-slate-100">{email}</span> is registered,
                you'll receive a password reset link shortly.
              </p>
              <Link to="/login" className="btn-secondary mt-2">
                <ArrowLeft size={14} />
                Back to sign in
              </Link>
            </div>
          ) : (
            <>
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
                    required
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="input"
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary w-full justify-center py-2.5"
                >
                  {loading ? (
                    <><Loader2 size={16} className="animate-spin" /> Sending…</>
                  ) : (
                    "Send reset link"
                  )}
                </button>
              </form>
            </>
          )}
        </div>

        <p className="mt-5 text-center text-sm text-slate-400">
          <Link to="/login" className="inline-flex items-center gap-1 text-brand-400 hover:text-brand-300 hover:underline">
            <ArrowLeft size={12} />
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
