import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle, Filter, Loader2, PenSquare,
  RefreshCw, Trash2, Upload, Wand2,
} from "lucide-react";
import { Link } from "react-router-dom";
import SearchForm from "@/components/SearchForm";
import JobCard from "@/components/JobCard";
import ProfileManager from "@/components/ProfileManager";
import TailorModal, { type TailorOptions } from "@/components/TailorModal";
import TaskProgress from "@/components/TaskProgress";
import { useJobs, useStartRun, useStatus } from "@/lib/hooks";
import type { JobRecord, TaskRecord } from "@/lib/types";
import { api } from "@/lib/api";
import clsx from "clsx";

const STATUS_FILTERS = [
  { value: "all",     label: "All" },
  { value: "pending", label: "Pending" },
  { value: "done",    label: "Tailored" },
  { value: "skipped", label: "Low fit" },
  { value: "failed",  label: "Failed" },
];

type SortOrder = "fit" | "title" | "workspace";

export default function Dashboard() {
  const status   = useStatus();
  const jobs     = useJobs();
  const startRun = useStartRun();

  const [filter,      setFilter]     = useState<string>(() => {
    const saved = sessionStorage.getItem("dashboard_filter");
    return saved || "all";
  });
  const [query,       setQuery]      = useState(() => {
    const saved = sessionStorage.getItem("dashboard_query");
    return saved || "";
  });
  const [sort,        setSort]       = useState<SortOrder>(() => {
    const saved = sessionStorage.getItem("dashboard_sort");
    return (saved as SortOrder) || "fit";
  });
  const [selected,    setSelected]   = useState<Set<string>>(new Set());
  const [searchTask,  setSearchTask] = useState<TaskRecord | null>(null);
  const [runTask,     setRunTask]    = useState<TaskRecord | null>(null);
  const [tailorOpen,  setTailorOpen] = useState(false);
  const [showUpload,  setShowUpload] = useState(false);
  const [searching,   setSearching]  = useState(false);
  // Initialize state from sessionStorage - runs on EVERY mount (including after back navigation)
  const [lastSearchJobIds, setLastSearchJobIds] = useState<string[] | null>(() => {
    const saved = sessionStorage.getItem("dashboard_lastSearchJobIds");
    console.log("[Dashboard Init] lastSearchJobIds from storage:", saved);
    return saved ? JSON.parse(saved) : null;
  });
  const [showAllJobs, setShowAllJobs] = useState(() => {
    const saved = sessionStorage.getItem("dashboard_showAllJobs");
    console.log("[Dashboard Init] showAllJobs from storage:", saved);
    return saved ? JSON.parse(saved) : false;
  });
  const [hasSearched, setHasSearched] = useState(() => {
    const saved = sessionStorage.getItem("dashboard_hasSearched");
    console.log("[Dashboard Init] hasSearched from storage:", saved);
    return saved ? JSON.parse(saved) : false;
  });
  const [currentPage, setCurrentPage] = useState(() => {
    const saved = sessionStorage.getItem("dashboard_currentPage");
    console.log("[Dashboard Init] currentPage from storage:", saved);
    return saved ? parseInt(saved, 10) : 1;
  });
  const [confirmClearAll, setConfirmClearAll] = useState(false);
  const JOBS_PER_PAGE = 20;

  // Persist dashboard state to sessionStorage
  useEffect(() => {
    console.log("[Dashboard] Persisting filter:", filter);
    sessionStorage.setItem("dashboard_filter", filter);
  }, [filter]);

  useEffect(() => {
    console.log("[Dashboard] Persisting query:", query);
    sessionStorage.setItem("dashboard_query", query);
  }, [query]);

  useEffect(() => {
    console.log("[Dashboard] Persisting sort:", sort);
    sessionStorage.setItem("dashboard_sort", sort);
  }, [sort]);

  useEffect(() => {
    console.log("[Dashboard] Persisting currentPage:", currentPage);
    sessionStorage.setItem("dashboard_currentPage", String(currentPage));
  }, [currentPage]);

  useEffect(() => {
    if (lastSearchJobIds) {
      console.log("[Dashboard] Persisting lastSearchJobIds:", lastSearchJobIds.length, "jobs");
      sessionStorage.setItem("dashboard_lastSearchJobIds", JSON.stringify(lastSearchJobIds));
    }
  }, [lastSearchJobIds]);

  useEffect(() => {
    console.log("[Dashboard] Persisting showAllJobs:", showAllJobs);
    sessionStorage.setItem("dashboard_showAllJobs", JSON.stringify(showAllJobs));
  }, [showAllJobs]);

  useEffect(() => {
    console.log("[Dashboard] Persisting hasSearched:", hasSearched);
    sessionStorage.setItem("dashboard_hasSearched", JSON.stringify(hasSearched));
  }, [hasSearched]);

  const resultsRef = useRef<HTMLDivElement>(null);
  const profileLoaded = status.data?.profile_loaded ?? false;

  /* ── derived lists ─────────────────────────────────────────────── */
  const filtered: JobRecord[] = useMemo(() => {
    const allJobs = jobs.data?.jobs ?? [];
    console.log("[Dashboard Filter] Total jobs in workspace:", allJobs.length);
    console.log("[Dashboard Filter] hasSearched:", hasSearched, "showAllJobs:", showAllJobs);
    console.log("[Dashboard Filter] lastSearchJobIds:", lastSearchJobIds?.length || "null");
    
    // If user hasn't searched yet AND showAllJobs is false, show nothing
    if (!hasSearched && !showAllJobs) {
      console.log("[Dashboard Filter] No search yet, showing empty");
      return [];
    }
    
    // If we have a recent search and "show all" is off, filter to only those job IDs
    const list = (lastSearchJobIds && !showAllJobs)
      ? allJobs.filter((j) => lastSearchJobIds.includes(j.job_id))
      : allJobs;
    
    console.log("[Dashboard Filter] After search filter:", list.length, "jobs");
    
    const q = query.trim().toLowerCase();
    const out = list.filter((j) => {
      if (filter !== "all" && j.status !== filter) return false;
      if (!q) return true;
      return (
        (j.title || "") + " " +
        (j.company || "") + " " +
        (j.location || "") + " " +
        (j.description || "")
      ).toLowerCase().includes(q);
    });
    if (sort === "fit")   out.sort((a, b) => (b.fit?.score ?? -1) - (a.fit?.score ?? -1));
    if (sort === "title") out.sort((a, b) => (a.title || "").localeCompare(b.title || ""));
    
    console.log("[Dashboard Filter] Final filtered:", out.length, "jobs");
    return out;
  }, [jobs.data, filter, query, sort, lastSearchJobIds, showAllJobs, hasSearched]);

  // Paginated jobs
  const totalPages = Math.ceil(filtered.length / JOBS_PER_PAGE);
  const paginatedJobs = filtered.slice(
    (currentPage - 1) * JOBS_PER_PAGE,
    currentPage * JOBS_PER_PAGE
  );

  // Reset to page 1 when filters change (but not on initial mount)
  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    setCurrentPage(1);
  }, [filter, query, sort, lastSearchJobIds, showAllJobs]);

  /* ── keep selection in sync with job list ──────────────────────── */
  useEffect(() => {
    if (!jobs.data) return;
    const avail = new Set(jobs.data.jobs.map((j) => j.job_id));
    setSelected((cur) => {
      const next = new Set([...cur].filter((id) => avail.has(id)));
      return next.size === cur.size ? cur : next;
    });
  }, [jobs.data]);

  const totalCount          = jobs.data?.jobs.length ?? 0;
  const visibleSelectedCount = filtered.filter((j) => selected.has(j.job_id)).length;
  const allVisibleSelected   = filtered.length > 0 && visibleSelectedCount === filtered.length;
  const hiddenSelectedCount  = selected.size - visibleSelectedCount;
  const hasFilters           = filter !== "all" || query.trim().length > 0;

  /* ── helpers ────────────────────────────────────────────────────── */
  const clearFilters  = () => { setFilter("all"); setQuery(""); };
  const toggleVisible = () => {
    setSelected((cur) => {
      const next = new Set(cur);
      paginatedJobs.forEach((j) => allVisibleSelected ? next.delete(j.job_id) : next.add(j.job_id));
      return next;
    });
  };
  const toggleSelected = (jobId: string, on: boolean) =>
    setSelected((s) => { const n = new Set(s); on ? n.add(jobId) : n.delete(jobId); return n; });

  /* ── search started ────────────────────────────────────────────── */
  function handleSearchStarted(task: TaskRecord) {
    setSearchTask(task);
    setSearching(true);
    setFilter("all");
    setQuery("");
    setShowAllJobs(false); // Hide all jobs, only show new search results
    setHasSearched(true); // Mark that user has searched
    setLastSearchJobIds([]); // Clear previous search
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
  }

  /* ── search finished ───────────────────────────────────────────── */
  async function handleSearchDone() {
    console.log("[Search Done] Starting...");
    setSearching(false);
    const { data } = await jobs.refetch();
    
    // Get ONLY the jobs from THIS search (most recent by processed_at)
    // This ensures we show EXACTLY the results from this search
    const allJobs = data?.jobs ?? [];
    
    // Get the most recent timestamp before this search started
    const searchStartTime = searchTask?.created_at ?? "";
    
    // Filter jobs that were processed during or after this search
    const freshJobs = allJobs.filter((j) => 
      (j.processed_at || "") >= searchStartTime
    );
    
    const jobIds = freshJobs.map((j) => j.job_id);
    console.log("[Search Done] Setting lastSearchJobIds:", jobIds.length, "jobs");
    setLastSearchJobIds(jobIds);
    setShowAllJobs(false); // Keep showing only search results
  }

  /* ── tailor ─────────────────────────────────────────────────────── */
  const onConfirmTailor = async (opts: TailorOptions) => {
    if (selected.size === 0) return;
    try {
      const t = await startRun.mutateAsync({
        job_ids: Array.from(selected),
        provider: opts.provider,
        model:    opts.model,
        no_pdf:   opts.no_pdf,
        force:    opts.force,
      });
      setRunTask(t);
      setSelected(new Set());
      setTailorOpen(false);
    } catch { /* modal shows error */ }
  };

  /* ── clear all jobs ────────────────────────────────────────────── */
  const handleClearAll = async () => {
    try {
      const result = await api.deleteAllJobs();
      console.log("[Clear Workspace] Delete result:", result);
      
      if (result.deleted_count === 0) {
        alert(`Warning: No jobs were deleted. Failed: ${result.failed_count || 0}. Check server logs.`);
        return;
      } else if (result.failed_count && result.failed_count > 0) {
        alert(`Deleted ${result.deleted_count} jobs, but ${result.failed_count} failed. Check server logs.`);
      }
      
      // Clear all state
      setConfirmClearAll(false);
      setLastSearchJobIds(null);
      setHasSearched(false);
      setShowAllJobs(false);
      setSelected(new Set());
      setFilter("all");
      setQuery("");
      
      // Clear sessionStorage
      sessionStorage.removeItem("dashboard_lastSearchJobIds");
      sessionStorage.removeItem("dashboard_hasSearched");
      sessionStorage.removeItem("dashboard_showAllJobs");
      sessionStorage.removeItem("dashboard_filter");
      sessionStorage.removeItem("dashboard_query");
      
      // Force refetch and wait for it
      await jobs.refetch();
      
      // Show success message
      alert(`Successfully deleted ${result.deleted_count} jobs!`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to clear workspace");
    }
  };

  return (
    <div className="space-y-6">

      {/* ── Page header ─────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Jobs
          </h1>
          <p className="text-sm text-slate-500">
            Search job boards, then tailor your resume for the roles you want.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {totalCount > 0 && (
            confirmClearAll ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Delete all {totalCount} jobs?</span>
                <button
                  onClick={handleClearAll}
                  className="btn-danger px-3 py-1.5 text-xs"
                >
                  Yes, clear all
                </button>
                <button 
                  onClick={() => setConfirmClearAll(false)} 
                  className="btn-secondary px-3 py-1.5 text-xs"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmClearAll(true)}
                className="btn-ghost text-xs text-rose-400 hover:text-rose-300"
                title="Delete all jobs from workspace"
              >
                <Trash2 size={13} />
                Clear workspace
              </button>
            )
          )}
          <button
            onClick={() => setShowUpload((v) => !v)}
            className={clsx(
              "btn-secondary shrink-0 text-xs gap-1.5",
              showUpload && "ring-1 ring-brand-500",
            )}
            title="Upload or replace your resume profile"
          >
            <Upload size={13} />
            {profileLoaded
              ? (showUpload ? "Hide upload" : `Profile: ${status.data?.profile_name}`)
              : "Upload resume"}
          </button>
        </div>
      </div>

      {/* ── Profile upload panel ────────────────────────────────── */}
      {(!profileLoaded || showUpload) && (
        <ProfileManager
          currentProfile={profileLoaded && status.data ? {
            name: status.data.profile_name,
            email: status.data.profile_email ?? undefined,
            phone: status.data.profile_phone ?? undefined,
            skills: status.data.profile_skills ?? undefined,
            linkedin: status.data.profile_linkedin ?? undefined,
            github: status.data.profile_github ?? undefined,
          } : undefined}
          onDone={() => {
            setShowUpload(false);
            status.refetch?.();
          }}
        />
      )}

      {/* ── Search form ─────────────────────────────────────────── */}
      <SearchForm onTaskStarted={handleSearchStarted} />

      {/* ── Progress ────────────────────────────────────────────── */}
      <div ref={resultsRef}>
        {searchTask && (
          <TaskProgress
            key={searchTask.task_id}
            taskId={searchTask.task_id}
            onDone={handleSearchDone}
          />
        )}
        {runTask && (
          <TaskProgress
            key={runTask.task_id}
            taskId={runTask.task_id}
            onDone={() => jobs.refetch()}
          />
        )}
      </div>

      {/* ── Filter / action bar ─────────────────────────────────── */}
      <div className="card flex flex-wrap items-center gap-3 p-4">
        <div className="flex min-w-0 flex-[1_1_220px] items-center gap-2">
          <Filter size={15} className="text-slate-400 shrink-0" />
          <input
            className="input flex-1"
            placeholder="Filter by title, company, description…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="flex flex-wrap gap-1">
          {STATUS_FILTERS.map((f) => {
            const count = f.value === "all"
              ? totalCount
              : (jobs.data?.jobs ?? []).filter((j) => j.status === f.value).length;
            
            // Don't show counts if user hasn't searched yet
            if (!hasSearched && count === 0) return null;
            
            return (
              <button
                key={f.value}
                onClick={() => setFilter(f.value)}
                className={clsx(
                  "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  filter === f.value
                    ? "bg-brand-500/20 text-brand-600 dark:text-brand-200"
                    : "text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100",
                )}
              >
                {f.label}{" "}
                {hasSearched && (
                  <span className="font-mono opacity-70">{count}</span>
                )}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <Link to="/freeform" className="btn-ghost text-sm">
            <PenSquare size={13} />
            Paste JD
          </Link>
          <button
            className="btn-secondary text-sm"
            disabled={jobs.isFetching}
            onClick={() => jobs.refetch()}
            title="Refresh job list"
          >
            <RefreshCw size={13} className={clsx(jobs.isFetching && "animate-spin")} />
            Refresh
          </button>
          <button
            className="btn-primary text-sm"
            disabled={selected.size === 0 || startRun.isPending || !profileLoaded}
            onClick={() => { startRun.reset(); setTailorOpen(true); }}
          >
            {startRun.isPending
              ? <Loader2 size={13} className="animate-spin" />
              : <Wand2 size={13} />}
            Tailor selected ({selected.size})
          </button>
        </div>
      </div>

      {/* ── Results meta ────────────────────────────────────────── */}
      {hasSearched && (
        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500">
          <p aria-live="polite">
            {searching ? (
              <span className="flex items-center gap-1.5">
                <Loader2 size={13} className="animate-spin text-brand-500" /> Searching — results will appear below…
              </span>
            ) : lastSearchJobIds && !showAllJobs ? (
              <>
                Showing <span className="font-mono text-slate-800 dark:text-slate-200">{filtered.length}</span> latest search results
                {hiddenSelectedCount > 0 && <span className="ml-2 text-amber-500"> · {hiddenSelectedCount} selected outside view</span>}
              </>
            ) : (
              <>
                Showing <span className="font-mono text-slate-800 dark:text-slate-200">{filtered.length}</span> of <span className="font-mono text-slate-800 dark:text-slate-200">{totalCount}</span> jobs
                {hiddenSelectedCount > 0 && <span className="ml-2 text-amber-500"> · {hiddenSelectedCount} selected outside view</span>}
              </>
            )}
          </p>
          {hasFilters && <button className="btn-ghost text-xs" onClick={clearFilters}>Clear filters</button>}
          {lastSearchJobIds && !showAllJobs && lastSearchJobIds.length < totalCount && (
            <button className="btn-ghost text-xs text-brand-500" onClick={() => setShowAllJobs(true)}>
              Show all {totalCount} workspace jobs
            </button>
          )}
          {showAllJobs && lastSearchJobIds && lastSearchJobIds.length > 0 && (
            <button className="btn-ghost text-xs text-brand-500" onClick={() => setShowAllJobs(false)}>
              ← Back to search results ({lastSearchJobIds.length})
            </button>
          )}

          <div className="ml-auto flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs">
            Sort by
            <select
              className="input w-auto text-xs py-1"
              value={sort}
              onChange={(e) => setSort(e.target.value as SortOrder)}
            >
              <option value="fit">Highest fit</option>
              <option value="title">Title A–Z</option>
              <option value="workspace">Workspace order</option>
            </select>
          </label>
          <button
            className="btn-secondary text-xs"
            disabled={filtered.length === 0 || startRun.isPending}
            onClick={toggleVisible}
          >
            {allVisibleSelected ? "Deselect visible" : "Select visible"}
          </button>
          {selected.size > 0 && (
            <button className="btn-ghost text-xs" onClick={() => setSelected(new Set())}>
              Clear selection
            </button>
          )}
        </div>
        </div>
      )}

      {/* ── Job list ────────────────────────────────────────────── */}
      {jobs.isError ? (
        <div className="card flex items-center gap-3 border-rose-500/30 p-4 text-sm text-rose-400">
          <AlertTriangle size={16} />
          <span className="flex-1">Could not load jobs — {jobs.error.message}</span>
          <button className="btn-secondary text-xs" onClick={() => jobs.refetch()}>Retry</button>
        </div>
      ) : jobs.isLoading ? (
        <div className="card flex items-center gap-2 p-6 text-sm text-slate-400">
          <Loader2 size={15} className="animate-spin" /> Loading jobs…
        </div>
      ) : filtered.length === 0 ? (
        <div className="card flex flex-col items-center gap-3 p-10 text-center">
          <p className="text-base font-semibold text-slate-700 dark:text-slate-200">
            {!hasSearched && totalCount === 0
              ? "Ready to search"
              : !hasSearched && totalCount > 0
              ? "Ready to search"
              : totalCount === 0
              ? "No jobs yet"
              : "No jobs match these filters"}
          </p>
          <p className="max-w-sm text-sm text-slate-500">
            {!hasSearched && totalCount === 0
              ? "Enter job titles above and click Search to get started."
              : !hasSearched && totalCount > 0
              ? "Enter job titles and filters above, then click Search to find matching roles."
              : totalCount === 0
              ? "Enter job titles above and hit Search to find roles."
              : "Try a different title, company, or status filter."}
          </p>
          {hasFilters && <button className="btn-secondary text-sm" onClick={clearFilters}>Clear filters</button>}
          {hasSearched && totalCount > 0 && filtered.length === 0 && (
            <button className="btn-secondary text-sm" onClick={() => { setShowAllJobs(true); setFilter("all"); setQuery(""); }}>
              Show all {totalCount} workspace jobs
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {paginatedJobs.map((job) => (
              <JobCard
                key={job.job_id}
                job={job}
                selected={selected.has(job.job_id)}
                onToggle={(on) => toggleSelected(job.job_id, on)}
              />
            ))}
          </div>
          
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-200 dark:border-slate-800 pt-4">
              <p className="text-sm text-slate-500">
                Page {currentPage} of {totalPages} · Showing {(currentPage - 1) * JOBS_PER_PAGE + 1}–{Math.min(currentPage * JOBS_PER_PAGE, filtered.length)} of {filtered.length}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="btn-secondary text-xs px-3 py-1.5 disabled:opacity-40"
                >
                  Previous
                </button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const page = currentPage <= 3 ? i + 1 : currentPage + i - 2;
                  if (page > totalPages) return null;
                  return (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className={clsx(
                        "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                        page === currentPage
                          ? "bg-brand-500 text-white"
                          : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-brand-500/20"
                      )}
                    >
                      {page}
                    </button>
                  );
                })}
                <button
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="btn-secondary text-xs px-3 py-1.5 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}

      <TailorModal
        open={tailorOpen}
        onClose={() => setTailorOpen(false)}
        onConfirm={onConfirmTailor}
        pending={startRun.isPending}
        error={startRun.error?.message}
        jobCount={selected.size}
      />
    </div>
  );
}
