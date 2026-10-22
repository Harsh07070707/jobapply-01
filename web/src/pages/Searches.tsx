import { useState } from "react";
import { History, Loader2, Trash2, Search } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useSearches, queryKeys } from "@/lib/hooks";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/format";

export default function Searches() {
  const q = useSearches();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [confirmClear, setConfirmClear] = useState(false);

  const deleteOne = useMutation({
    mutationFn: (id: number) => api.deleteSearch(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.searches }),
  });

  const deleteAll = useMutation({
    mutationFn: () => api.deleteAllSearches(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.searches });
      setConfirmClear(false);
    },
  });

  const restoreSearch = (searchInput: any) => {
    // Store search params in sessionStorage so Dashboard can restore them
    sessionStorage.setItem("restore_search", JSON.stringify(searchInput));
    navigate("/");
  };

  if (q.isLoading) {
    return (
      <div className="card flex items-center gap-2 p-6 text-sm text-slate-400">
        <Loader2 size={16} className="animate-spin" /> Loading…
      </div>
    );
  }

  const rows = q.data?.searches ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <History size={20} className="text-brand-400" />
        <h1 className="text-2xl font-bold tracking-tight flex-1">Search history</h1>
        {rows.length > 0 && (
          confirmClear ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-slate-400">Delete all {rows.length} entries?</span>
              <button
                onClick={() => deleteAll.mutate()}
                disabled={deleteAll.isPending}
                className="btn-danger px-3 py-1.5 text-xs"
              >
                {deleteAll.isPending ? <Loader2 size={12} className="animate-spin" /> : "Yes, delete all"}
              </button>
              <button onClick={() => setConfirmClear(false)} className="btn-secondary px-3 py-1.5 text-xs">
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmClear(true)}
              className="btn-ghost text-xs text-rose-400 hover:text-rose-300"
            >
              <Trash2 size={13} />
              Clear all
            </button>
          )
        )}
      </div>

      {rows.length === 0 ? (
        <div className="card p-8 text-center text-sm text-slate-400">
          No searches yet. Run one from the Jobs page.
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 dark:bg-slate-900/70 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-2 text-left">#</th>
                <th className="px-4 py-2 text-left">Command</th>
                <th className="px-4 py-2 text-left">Started</th>
                <th className="px-4 py-2 text-left">Provider / Model</th>
                <th className="px-4 py-2 text-right">Fetched</th>
                <th className="px-4 py-2 text-right text-brand-500">New</th>
                <th className="px-4 py-2 text-right text-amber-500">Dup</th>
                <th className="px-4 py-2 text-right"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
              {rows.map((r) => {
                const titles = (r.search_input?.titles as string[]) ?? [];
                const isDeleting = deleteOne.isPending && deleteOne.variables === r.id;
                return (
                  <tr 
                    key={r.id} 
                    className="hover:bg-brand-500/5 dark:hover:bg-brand-500/10 cursor-pointer transition-colors group"
                    onClick={() => restoreSearch(r.search_input)}
                    title="Click to restore this search"
                  >
                    <td className="px-4 py-2 text-xs text-slate-400">#{r.id}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <Search size={14} className="text-brand-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                        <div>
                          <div className="font-medium text-slate-800 dark:text-slate-100">{r.command}</div>
                          {titles.length ? (
                            <div className="text-xs text-slate-400">{titles.join(", ")}</div>
                          ) : null}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">{relativeTime(r.started_at)}</td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {r.provider || "—"}{r.model ? ` / ${r.model}` : ""}
                    </td>
                    <td className="px-4 py-2 text-right font-mono text-xs">{r.fetched}</td>
                    <td className="px-4 py-2 text-right font-mono text-xs text-brand-500">{r.new_jobs}</td>
                    <td className="px-4 py-2 text-right font-mono text-xs text-amber-500">{r.duplicate_jobs}</td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation(); // Prevent row click
                          deleteOne.mutate(r.id);
                        }}
                        disabled={isDeleting}
                        className="p-1 text-slate-400 hover:text-rose-400 transition-colors"
                        title="Delete this entry"
                      >
                        {isDeleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
