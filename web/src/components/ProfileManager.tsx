/**
 * ProfileManager — shows current profile data, upload new resume, delete profile.
 * Visual feedback showing exactly what was extracted from the resume.
 */
import { useRef, useState } from "react";
import { 
  CheckCircle2, FileText, Loader2, Upload, X, Trash2, 
  User, Mail, Phone, Briefcase, Award, GithubIcon, Linkedin 
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/hooks";
import { getValidToken } from "@/lib/auth";
import clsx from "clsx";

type State = "idle" | "uploading" | "success" | "error";

interface ProfileData {
  profile_name: string;
  skills_count: number;
  experience_count: number;
  email?: string;
  phone?: string;
  linkedin?: string;
  github?: string;
}

interface Props {
  currentProfile?: {
    name: string;
    email?: string;
    phone?: string;
    skills?: string[];
    linkedin?: string;
    github?: string;
  };
  onDone?: () => void;
}

export default function ProfileManager({ currentProfile, onDone }: Props) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<State>("idle");
  const [message, setMessage] = useState("");
  const [fileName, setFileName] = useState("");
  const [dragging, setDragging] = useState(false);
  const [extractedProfile, setExtractedProfile] = useState<ProfileData | null>(null);
  const [deleting, setDeleting] = useState(false);

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
    setExtractedProfile(null);

    const form = new FormData();
    form.append("resume", file);

    try {
      const token = await getValidToken();
      const res = await fetch("/api/profile/upload", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      const data = await res.json() as ProfileData & { detail?: string };
      if (!res.ok) {
        setState("error");
        setMessage(data.detail ?? `Upload failed (${res.status})`);
        return;
      }
      setState("success");
      setExtractedProfile(data);
      setMessage(`Profile created for ${data.profile_name}`);
      qc.invalidateQueries({ queryKey: queryKeys.status });
      qc.invalidateQueries({ queryKey: queryKeys.jobs });
      onDone?.();
    } catch (err) {
      setState("error");
      setMessage(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  async function deleteProfile() {
    if (!confirm("Delete your profile? This cannot be undone. You'll need to upload a new resume.")) return;
    setDeleting(true);
    try {
      const token = await getValidToken();
      const res = await fetch("/api/profile", {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      qc.invalidateQueries({ queryKey: queryKeys.status });
      qc.invalidateQueries({ queryKey: queryKeys.jobs });
      setState("idle");
      setExtractedProfile(null);
      onDone?.();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    upload(files[0]);
  }

  return (
    <div className="space-y-4">
      
      {/* Why upload resume - explanation */}
      {!currentProfile && state === "idle" && (
        <div className="card border-amber-500/30 bg-amber-500/5 p-4 space-y-2">
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-semibold text-sm">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
            Why do I need to upload a resume?
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            Your resume is the <strong>source of truth</strong> for tailoring. We extract your skills, experience, education, 
            and projects to customize each application. We also <strong>save your resume format/template</strong> so 
            tailored resumes match your original style — not some generic template. <strong>Your resume never leaves 
            your machine</strong> and no LLM processes it during upload.
          </p>
        </div>
      )}
      
      {/* Current profile display */}
      {currentProfile && state !== "success" && (
        <div className="card border-brand-500/30 bg-brand-500/5 p-4 space-y-3">
          <div className="flex items-start justify-between">
            <div className="space-y-2 flex-1">
              <div className="flex items-center gap-2 text-brand-600 dark:text-brand-400 font-semibold">
                <User size={16} />
                {currentProfile.name}
              </div>
              <div className="grid gap-2 text-xs text-slate-600 dark:text-slate-400">
                {currentProfile.email && (
                  <div className="flex items-center gap-2">
                    <Mail size={12} /> {currentProfile.email}
                  </div>
                )}
                {currentProfile.phone && (
                  <div className="flex items-center gap-2">
                    <Phone size={12} /> {currentProfile.phone}
                  </div>
                )}
                {currentProfile.linkedin && (
                  <a href={currentProfile.linkedin} target="_blank" rel="noopener" className="flex items-center gap-2 hover:text-brand-500">
                    <Linkedin size={12} /> LinkedIn
                  </a>
                )}
                {currentProfile.github && (
                  <a href={currentProfile.github} target="_blank" rel="noopener" className="flex items-center gap-2 hover:text-brand-500">
                    <GithubIcon size={12} /> GitHub
                  </a>
                )}
              </div>
              {currentProfile.skills && currentProfile.skills.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  <Award size={12} className="text-brand-500 mt-1" />
                  {currentProfile.skills.slice(0, 10).map((s) => (
                    <span key={s} className="badge bg-brand-500/10 text-brand-600 dark:text-brand-300 text-[10px]">
                      {s}
                    </span>
                  ))}
                  {currentProfile.skills.length > 10 && (
                    <span className="text-[10px] text-slate-400">+{currentProfile.skills.length - 10} more</span>
                  )}
                </div>
              )}
            </div>
            <button
              onClick={deleteProfile}
              disabled={deleting}
              className="btn-ghost text-rose-400 hover:text-rose-300 text-xs"
              title="Delete profile"
            >
              {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            </button>
          </div>
          <p className="text-xs text-slate-500">
            Upload a new resume below to replace this profile & format template
          </p>
        </div>
      )}

      {/* Upload success display */}
      {state === "success" && extractedProfile && (
        <div className="card border-brand-500/60 bg-brand-500/5 p-5 space-y-3">
          <div className="flex items-center gap-2 text-brand-600 dark:text-brand-400 font-semibold">
            <CheckCircle2 size={20} />
            Profile created successfully
          </div>
          <div className="grid gap-2 text-sm">
            <div className="flex items-center gap-2">
              <User size={14} className="text-brand-500" />
              <span className="font-medium">{extractedProfile.profile_name}</span>
            </div>
            <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
              <Award size={14} className="text-brand-500" />
              <span>{extractedProfile.skills_count} skills extracted</span>
            </div>
            {extractedProfile.experience_count > 0 && (
              <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                <Briefcase size={14} className="text-brand-500" />
                <span>{extractedProfile.experience_count} work experiences</span>
              </div>
            )}
          </div>
          <button
            onClick={() => { setState("idle"); setExtractedProfile(null); setFileName(""); }}
            className="btn-secondary text-xs w-full"
          >
            Upload another resume
          </button>
        </div>
      )}

      {/* Upload error */}
      {state === "error" && (
        <div className="card border-rose-500/60 bg-rose-500/5 p-4">
          <div className="flex items-center gap-2 text-rose-500 font-semibold text-sm mb-2">
            <X size={16} /> Upload failed
          </div>
          <p className="text-sm text-rose-400">{message}</p>
          <button
            onClick={() => { setState("idle"); setMessage(""); }}
            className="btn-secondary text-xs mt-3"
          >
            Try again
          </button>
        </div>
      )}

      {/* Drop zone */}
      {state !== "success" && (
        <div
          onClick={() => state !== "uploading" && inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
          className={clsx(
            "relative flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-all",
            dragging ? "border-brand-400 bg-brand-500/10 scale-[1.01]" :
            state === "uploading" ? "border-brand-500/60 bg-brand-500/5 pointer-events-none" :
            "border-slate-300 dark:border-slate-700 hover:border-brand-400 hover:bg-brand-500/5",
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />

          {state === "uploading" ? (
            <>
              <Loader2 size={32} className="animate-spin text-brand-500" />
              <div>
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                  Parsing {fileName}…
                </p>
                <p className="text-xs text-slate-400 mt-1">Extracting name, email, skills, experience</p>
              </div>
              <div className="w-full max-w-xs h-1 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                <div className="h-full bg-brand-500 rounded-full animate-pulse w-2/3" />
              </div>
            </>
          ) : (
            <>
              <div className="grid h-12 w-12 place-items-center rounded-xl bg-brand-500/10">
                <Upload size={22} className="text-brand-500" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {currentProfile ? "Upload new resume to replace profile" : "Drop your resume here"} or <span className="text-brand-500">click to browse</span>
                </p>
                <p className="mt-1 text-xs text-slate-400">PDF or DOCX · parsed instantly · no LLM needed</p>
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
      )}
    </div>
  );
}
