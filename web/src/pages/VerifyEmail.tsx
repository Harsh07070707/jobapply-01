import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Briefcase, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

type State = "loading" | "success" | "error";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [state, setState] = useState<State>("loading");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [resending, setResending] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("No verification token found in the link.");
      return;
    }
    api.auth
      .verifyEmail(token)
      .then(res => {
        setState("success");
        setMessage(res.message);
      })
      .catch(err => {
        setState("error");
        setMessage(
          err instanceof Error
            ? err.message
            : "Verification failed. The link may have expired or already been used.",
        );
      });
  }, [token]);

  async function handleResend() {
    if (!email.trim()) return;
    setResending(true);
    setResendSuccess(false);
    try {
      await api.auth.resendVerification(email);
      setResendSuccess(true);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to resend email");
    } finally {
      setResending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-500/20 text-brand-400 ring-1 ring-brand-500/30">
            <Briefcase size={24} />
          </div>
        </div>

        <div className="card p-8 text-center shadow-xl shadow-black/40">
          {state === "loading" && (
            <>
              <Loader2 size={36} className="mx-auto mb-4 animate-spin text-brand-400" />
              <h2 className="text-lg font-semibold text-slate-100">Verifying your email…</h2>
            </>
          )}
          {state === "success" && (
            <>
              <CheckCircle2 size={36} className="mx-auto mb-4 text-brand-400" />
              <h2 className="text-xl font-semibold text-slate-100">Email verified!</h2>
              <p className="mt-2 text-sm text-slate-400">{message}</p>
              <Link to="/login" className="btn-primary mx-auto mt-6 justify-center px-6 py-2.5">
                Sign in
              </Link>
            </>
          )}
          {state === "error" && (
            <>
              <XCircle size={36} className="mx-auto mb-4 text-rose-400" />
              <h2 className="text-xl font-semibold text-slate-100">Verification failed</h2>
              <p className="mt-2 text-sm text-slate-400">{message}</p>
              
              {!resendSuccess ? (
                <div className="mt-6 space-y-3">
                  <div className="text-left">
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Resend verification email
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="email"
                        className="input flex-1"
                        placeholder="your.email@example.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                      />
                      <button
                        onClick={handleResend}
                        disabled={resending || !email.trim()}
                        className="btn-primary px-4"
                      >
                        {resending ? <Loader2 size={14} className="animate-spin" /> : "Resend"}
                      </button>
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 pt-2">
                    <Link to="/login" className="btn-secondary w-full justify-center py-2.5">
                      Go to sign in
                    </Link>
                    <Link to="/register" className="btn-ghost w-full justify-center py-2.5 text-xs">
                      Create a new account
                    </Link>
                  </div>
                </div>
              ) : (
                <div className="mt-6 space-y-3">
                  <div className="rounded-lg bg-brand-500/10 border border-brand-500/30 p-3 text-sm text-brand-300">
                    ✓ Verification email sent! Check your inbox.
                  </div>
                  <Link to="/login" className="btn-primary w-full justify-center py-2.5">
                    Go to sign in
                  </Link>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
