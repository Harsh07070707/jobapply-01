/**
 * ProfileUpload — drag-and-drop or click-to-upload resume (PDF/DOCX).
 * No LLM needed — parses locally and writes profile.json immediately.
 */
import { useRef, useState } from "react";
import { CheckCircle2, FileText, Loader2, Upload, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/hooks";
import { getValidToken } from "@/lib/auth";
import clsx from "clsx";

type State = "idle" | "uploading" | "success" | "error";

export default function ProfileUpload({ onDone }: { onDone?: () => void }) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<State>("idle");
  const [message, setMessage] = useState("");
  const [fileName, setFileName] = useState("");
  const [dragging, setDragging] = useState(false);

  async function upload(file: File) {
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!["pdf", "docx", "txt", "md"].includes(ext)) {
      setState("error");
      setMessage("Only PDF, DOCX, TXT, and MD files are supported.");
      return;
    }

    setFileName(file.name);
    setState("uploading");
    setMessage("");

    const form = new FormData();
    form.append("resume", file);

    try {
      const token = await getValidToken();
      const res = await fetch("/api/profile/upload", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      const data = await res.json() as Record<string, unknown>;
      if (!res.ok) {
        setState("error");
        setMessage((data.detail as string) ?? `Upload failed (${res.status})`);
        return;
      }
      setState("success");
      setMessage(
        `✓ Profile created for ${data.profile_name as string} — ${data.skills_count as number} skills extracted.`
      );
      qc.invalidateQueries({ queryKey: queryKeys.status });
      qc.invalidateQueries({ queryKey: queryKeys.jobs });
      onDone?.();
    } catch (err) {
      setState("error");
      setMessage(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    upload(files[0]);
  }

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        onClick={() => state !== "uploading" && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
        className={clsx(
          "relative flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-all",
          dragging ? "border-brand-400 bg-brand-500/10 scale-[1.01]" :
          state === "success" ? "border-brand-500/60 bg-brand-500/5" :
          state === "error" ? "border-rose-500/60 bg-rose-500/5" :
          "border-slate-300 dark:border-slate-700 hover:border-brand-400 hover:bg-brand-500/5",
          state === "uploading" && "pointer-events-none",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />

        {state === "uploading" && (
          <>
            <Loader2 size={32} className="animate-spin text-brand-500" />
            <div>
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Parsing {fileName}…
              </p>
              <p className="text-xs text-slate-400 mt-1">Extracting your profile data, please wait</p>
            </div>
            <div className="w-full max-w-xs h-1 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div className="h-full bg-brand-500 rounded-full animate-pulse w-2/3" />
            </div>
          </>
        )}

        {state === "success" && (
          <>
            <CheckCircle2 size={32} className="text-brand-500" />
            <div>
              <p className="text-sm font-semibold text-brand-600 dark:text-brand-400">{message}</p>
              <button
                onClick={(e) => { e.stopPropagation(); setState("idle"); setMessage(""); setFileName(""); }}
                className="mt-2 text-xs text-slate-400 hover:text-brand-500 underline"
              >
                Upload a different resume
              </button>
            </div>
          </>
        )}

        {state === "error" && (
          <>
            <X size={32} className="text-rose-400" />
            <div>
              <p className="text-sm font-semibold text-rose-500">{message}</p>
              <button
                onClick={(e) => { e.stopPropagation(); setState("idle"); setMessage(""); }}
                className="mt-2 text-xs text-slate-400 hover:underline"
              >
                Try again
              </button>
            </div>
          </>
        )}

        {state === "idle" && (
          <>
            <div className="grid h-12 w-12 place-items-center rounded-xl bg-brand-500/10">
              <Upload size={22} className="text-brand-500" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Drop your resume here or <span className="text-brand-500">click to browse</span>
              </p>
              <p className="mt-1 text-xs text-slate-400">PDF or DOCX · profile created instantly · no AI needed</p>
            </div>
            <div className="flex gap-2 mt-1">
              {["PDF", "DOCX", "TXT"].map((t) => (
                <span key={t} className="flex items-center gap-1 rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-500">
                  <FileText size={9} /> {t}
                </span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
