import { Link } from "react-router-dom";
import {
  AlertTriangle, Building2, Calendar, ExternalLink,
  FileCheck2, IndianRupee, Loader2, Mail, MapPin,
  TrendingUp, Users,
} from "lucide-react";
import {
  formatScore, formatStatus, pickAcceptableUrl, shortHostname, relativeTime,
} from "@/lib/format";
import { useActiveTaskFor, useLastTaskFor } from "@/lib/hooks";
import type { JobRecord } from "@/lib/types";
import Markdown from "./Markdown";
import clsx from "clsx";

interface Props {
  job: JobRecord;
  selected?: boolean;
  onToggle?: (checked: boolean) => void;
}

/** Score → colour ring */
function scoreColor(score: number) {
  if (score >= 0.75) return "text-brand-500";
  if (score >= 0.5)  return "text-amber-500";
  return "text-rose-400";
}

/** Pull salary out of the raw job if the board provided it */
function salaryLabel(job: JobRecord): string | null {
  const raw = (job as any).raw ?? {};
  const min = raw.min_amount ?? raw.salary_min;
  const max = raw.max_amount ?? raw.salary_max;
  const currency = (raw.currency ?? "").toUpperCase();
  if (min && max) {
    const fmt = (n: number) =>
      n >= 100000 ? `${(n / 100000).toFixed(1)} LPA` : `${Math.round(n / 1000)}k`;
    return `${currency || "₹"}${fmt(min)}–${fmt(max)}`;
  }
  return null;
}

export default function JobCard({ job, selected, onToggle }: Props) {
  const status   = formatStatus(job.status);
  const url      = pickAcceptableUrl(job);
  const host     = shortHostname(url);
  const isTailored = job.status === "done" || !!job.tailored_resume;
  const recipient  = job.application?.primary_email;
  const hasEmailDraft = Boolean(job.available_artifacts?.["email.txt"]);
  const live       = useActiveTaskFor(job.job_id);
  const liveKind   = live.task?.kind;
  const lastTask   = useLastTaskFor(job.job_id);
  const failedTask =
    !live.task && lastTask && lastTask.status === "failed" && lastTask.kind !== "run"
      ? lastTask : null;
  const salary = salaryLabel(job);
  const missingKw = job.fit?.missing_keywords ?? [];
  const mustHave  = job.fit?.must_haves_present ?? [];

  return (
    <div className={clsx(
      "card flex flex-col gap-3 p-4 transition-all duration-150",
      selected ? "ring-2 ring-brand-500/60 border-brand-500/40" : "hover:border-slate-300 dark:hover:border-slate-600",
      live.task ? "border-brand-500/40 ring-1 ring-brand-500/30" : "",
    )}>

      {/* ── Top row: checkbox + title + badge + score ─────────────── */}
      <div className="flex items-start gap-3">
        {onToggle && (
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 accent-brand-500 shrink-0"
            checked={!!selected}
            onChange={(e) => onToggle(e.target.checked)}
          />
        )}
        <div className="min-w-0 flex-1">
          <Link
            to={`/jobs/${job.job_id}`}
            className="block truncate text-base font-semibold text-slate-900 dark:text-slate-100 hover:text-brand-500 dark:hover:text-brand-300 transition-colors"
          >
            {job.title || "Untitled role"}
          </Link>

          {/* Meta row: company · location · source */}
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
            {job.company && (
              <span className="flex items-center gap-1">
                <Building2 size={11} /> {job.company}
              </span>
            )}
            {job.location && (
              <span className="flex items-center gap-1">
                <MapPin size={11} /> {job.location}
              </span>
            )}
            {host && url && (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="flex items-center gap-1 hover:text-brand-500 transition-colors"
              >
                <ExternalLink size={11} /> {host}
              </a>
            )}
            {job.processed_at && (
              <span className="flex items-center gap-1">
                <Calendar size={11} /> {relativeTime(job.processed_at)}
              </span>
            )}
          </div>

          {/* Salary + work arrangement if available */}
          {salary && (
            <div className="mt-1 flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400">
              <IndianRupee size={11} /> {salary}
            </div>
          )}
        </div>

        {/* Badge + score */}
        <div className="flex flex-col items-end gap-1 shrink-0">
          {job.has_referral && (
            <span className="badge bg-purple-500/15 text-purple-600 dark:text-purple-300 ring-1 ring-purple-500/40" title="Referral program available">
              <Users size={10} className="mr-1" /> Referral
            </span>
          )}
          {live.task ? (
            <span className="badge bg-brand-500/15 text-brand-600 dark:text-brand-200 ring-1 ring-brand-500/40">
              <Loader2 size={10} className="mr-1 animate-spin" />
              {liveKind === "email" ? "Drafting" : "Tailoring"}
            </span>
          ) : failedTask ? (
            <span className="badge bg-rose-500/15 text-rose-500 ring-1 ring-rose-500/40" title={failedTask.error ?? ""}>
              <AlertTriangle size={10} className="mr-1" /> Failed
            </span>
          ) : (
            <span className={"badge " + status.className}>{status.label}</span>
          )}
          {job.fit && (
            <span className={clsx("text-xs font-bold", scoreColor(job.fit.score))}>
              {formatScore(job.fit.score)} match
            </span>
          )}
        </div>
      </div>

      {/* ── Live progress bar ────────────────────────────────────── */}
      {live.task && (
        <div className="space-y-1">
          <div className="h-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
            <div
              className="h-full rounded-full bg-brand-500 transition-all"
              style={{ width: `${Math.max(8, Math.min(100, live.percent || 12))}%` }}
            />
          </div>
          <p className="text-[11px] uppercase tracking-wide text-brand-500">{live.label}</p>
        </div>
      )}

      {/* ── Match breakdown ─────────────────────────────────────── */}
      {job.fit?.rationale ? (
        <p className="line-clamp-2 text-xs text-slate-500 dark:text-slate-400 leading-snug">
          {job.fit.rationale}
        </p>
      ) : job.description ? (
        <Markdown compact className="line-clamp-2 text-xs leading-snug text-slate-500">
          {job.description.slice(0, 400)}
        </Markdown>
      ) : null}

      {/* Strong matches */}
      {mustHave.length > 0 && (
        <div className="flex flex-wrap gap-1">
          <TrendingUp size={11} className="text-brand-500 mt-0.5 shrink-0" />
          {mustHave.slice(0, 4).map((kw) => (
            <span key={kw} className="badge bg-brand-500/10 text-brand-600 dark:text-brand-300 text-[10px]">
              {kw}
            </span>
          ))}
        </div>
      )}

      {/* Missing skills */}
      {missingKw.length > 0 && (
        <div className="flex flex-wrap gap-1">
          <AlertTriangle size={11} className="text-amber-500 mt-0.5 shrink-0" />
          {missingKw.slice(0, 3).map((kw) => (
            <span key={kw} className="badge bg-amber-500/10 text-amber-600 dark:text-amber-300 text-[10px]">
              {kw}
            </span>
          ))}
          {missingKw.length > 3 && (
            <span className="text-[10px] text-slate-400">+{missingKw.length - 3} more</span>
          )}
        </div>
      )}

      {/* ── Bottom row: status indicators + actions ──────────────── */}
      <div className="flex flex-wrap items-center gap-2 text-xs pt-1 border-t border-slate-100 dark:border-slate-800">
        {isTailored ? (
          <span className="flex items-center gap-1 text-brand-500">
            <FileCheck2 size={12} /> Resume ready
          </span>
        ) : (
          <span className="text-slate-400 dark:text-slate-500">No resume yet</span>
        )}
        {hasEmailDraft || recipient ? (
          <span className="flex items-center gap-1 text-amber-500">
            <Mail size={12} /> {hasEmailDraft ? "Email drafted" : recipient}
          </span>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost text-[11px] px-2 py-1 text-slate-500 hover:text-brand-500"
              onClick={(e) => e.stopPropagation()}
            >
              Apply <ExternalLink size={10} />
            </a>
          )}
          <Link
            to={`/jobs/${job.job_id}`}
            className="text-brand-500 hover:text-brand-400 font-medium"
          >
            Details →
          </Link>
        </div>
      </div>
    </div>
  );
}
