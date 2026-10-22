/**
 * SearchForm — job search with multi-location chips, experience level,
 * and collapsible advanced options.
 *
 * LOCATION CHIPS:
 *   Each location is stored as a separate string. On submit we fire one
 *   search per location so results don't bleed across city boundaries.
 *   "Remote — India" and "Remote — Anywhere" are kept distinct.
 */
import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { ChevronDown, Loader2, MapPin, Search, X } from "lucide-react";
import { useStartSearch, useStatus } from "@/lib/hooks";
import type { TaskRecord } from "@/lib/types";
import clsx from "clsx";

interface Props {
  onTaskStarted: (task: TaskRecord) => void;
}

const QUICK_LOCATIONS = [
  "Hyderabad",
  "Bengaluru",
  "Mumbai",
  "Pune",
  "Delhi NCR",
  "Chennai",
  "Remote — India",
  "Remote — Anywhere",
];

const EXPERIENCE_LEVELS = [
  { value: "", label: "Any level" },
  { value: "internship", label: "Internship" },
  { value: "entry", label: "Entry level  (0–2 yrs)" },
  { value: "mid", label: "Mid level  (2–5 yrs)" },
  { value: "senior", label: "Senior  (5+ yrs)" },
  { value: "lead", label: "Lead / Staff" },
];

const JOB_TYPES = [
  { value: "fulltime", label: "Full-time" },
  { value: "parttime", label: "Part-time" },
  { value: "contract", label: "Contract" },
  { value: "freelance", label: "Freelance" },
  { value: "internship_type", label: "Internship" },
];

export default function SearchForm({ onTaskStarted }: Props) {
  const status = useStatus();
  const [titles, setTitles] = useState("");
  const [skills, setSkills] = useState("");
  const [locations, setLocations] = useState<string[]>([]);
  const [locInput, setLocInput] = useState("");
  const [showLocSuggestions, setShowLocSuggestions] = useState(false);
  const [results, setResults] = useState<number | "">("");
  const [expLevel, setExpLevel] = useState("");
  const [jobTypes, setJobTypes] = useState<string[]>([]); // Changed to array for multi-select
  const [score, setScore] = useState(false);
  const [remote, setRemote] = useState(false);
  const [linkedin, setLinkedin] = useState(false); // Changed to FALSE for faster searches
  const [force, setForce] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const locRef = useRef<HTMLDivElement>(null);
  const start = useStartSearch();

  // Restore search from history if present
  useEffect(() => {
    const restored = sessionStorage.getItem("restore_search");
    if (restored) {
      try {
        const params = JSON.parse(restored);
        if (params.titles) setTitles(params.titles.join(", "));
        if (params.skills) setSkills(params.skills.join(", "));
        if (params.location) setLocations([params.location]);
        if (params.results_wanted) setResults(params.results_wanted);
        if (params.experience_level) setExpLevel(params.experience_level);
        if (params.job_types) setJobTypes(params.job_types); // Changed from job_type
        if (params.remote !== undefined) setRemote(params.remote);
        if (params.linkedin_fetch_description !== undefined) setLinkedin(params.linkedin_fetch_description);
        sessionStorage.removeItem("restore_search"); // Clear after restore
      } catch (e) {
        console.error("Failed to restore search:", e);
      }
    }
  }, []);

  // Save form state to sessionStorage whenever it changes
  useEffect(() => {
    const formState = {
      titles,
      skills,
      locations,
      results,
      expLevel,
      jobTypes,
      score,
      remote,
      linkedin,
    };
    sessionStorage.setItem("search_form_state", JSON.stringify(formState));
  }, [titles, skills, locations, results, expLevel, jobTypes, score, remote, linkedin]);

  // Restore form state on mount
  useEffect(() => {
    const savedState = sessionStorage.getItem("search_form_state");
    if (savedState) {
      try {
        const state = JSON.parse(savedState);
        if (state.titles) setTitles(state.titles);
        if (state.skills) setSkills(state.skills);
        if (state.locations) setLocations(state.locations);
        if (state.results) setResults(state.results);
        if (state.expLevel) setExpLevel(state.expLevel);
        if (state.jobTypes) setJobTypes(state.jobTypes);
        if (state.score !== undefined) setScore(state.score);
        if (state.remote !== undefined) setRemote(state.remote);
        if (state.linkedin !== undefined) setLinkedin(state.linkedin);
      } catch (e) {
        console.error("Failed to restore form state:", e);
      }
    }
  }, []);

  // Toggle job type selection
  function toggleJobType(value: string) {
    setJobTypes(prev => 
      prev.includes(value) 
        ? prev.filter(t => t !== value)
        : [...prev, value]
    );
  }

  // ── Location chip helpers ───────────────────────────────────────────

  function addLocation(loc: string) {
    const trimmed = loc.trim();
    if (!trimmed || locations.includes(trimmed)) return;
    setLocations((prev) => [...prev, trimmed]);
    setLocInput("");
    setShowLocSuggestions(false);
  }

  function removeLocation(loc: string) {
    setLocations((prev) => prev.filter((l) => l !== loc));
  }

  function handleLocKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addLocation(locInput);
    } else if (e.key === "Backspace" && !locInput && locations.length > 0) {
      setLocations((prev) => prev.slice(0, -1));
    }
  }

  const suggestions = QUICK_LOCATIONS.filter(
    (l) =>
      !locations.includes(l) &&
      (locInput.trim() === "" || l.toLowerCase().includes(locInput.toLowerCase())),
  );

  // ── Submit ─────────────────────────────────────────────────────────

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const titleList = titles.split(",").map((t) => t.trim()).filter(Boolean);
    if (!titleList.length) return;

    const skillsList = skills.split(",").map((t) => t.trim()).filter(Boolean);

    const locationTargets = locations.length > 0 ? locations : [undefined as unknown as string];
    const resultsNum = typeof results === "number" ? results : (status.data?.results_wanted ?? 30);

    try {
      let firstTask: TaskRecord | null = null;
      for (const loc of locationTargets) {
        const locationStr = loc === "Remote — India"
          ? "India Remote"
          : loc === "Remote — Anywhere"
          ? undefined
          : loc;
        const task = await start.mutateAsync({
          titles: titleList,
          skills: skillsList,
          location: locationStr,
          remote: remote || loc === "Remote — Anywhere" || loc === "Remote — India",
          results_wanted: resultsNum,
          score,
          linkedin_descriptions: linkedin,
          force,
          experience_level: expLevel || undefined,
          job_types: jobTypes.length > 0 ? jobTypes : undefined, // Send array instead of single value
        });
        if (!firstTask) { firstTask = task; onTaskStarted(task); }
      }
    } catch {
      // rendered via start.isError
    }
  };

  return (
    <form onSubmit={onSubmit} className="card space-y-4 p-5">
      {/* Header */}
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-200">
        <Search size={16} className="text-brand-500" />
        Search job boards
        <span className="ml-auto text-xs font-normal text-slate-400">
          Sites: {status.data?.sites?.join(", ") ?? "—"}
        </span>
      </div>

      {/* Row 1: Titles + Experience */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label>
          <span className="label">Job titles (comma-separated)</span>
          <input
            className="input"
            placeholder="Data Engineer, Analytics Engineer"
            value={titles}
            onChange={(e) => setTitles(e.target.value)}
            required
          />
        </label>
        <label>
          <span className="label">Experience level</span>
          <select
            className="input"
            value={expLevel}
            onChange={(e) => setExpLevel(e.target.value)}
          >
            {EXPERIENCE_LEVELS.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
        </label>
      </div>

      {/* Job Types - Multi-select checkboxes */}
      <div>
        <span className="label">Job types (select multiple)</span>
        <div className="flex flex-wrap gap-x-4 gap-y-2 mt-1.5">
          {JOB_TYPES.map((type) => (
            <label key={type.value} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={jobTypes.includes(type.value)}
                onChange={() => toggleJobType(type.value)}
                className="accent-brand-500 cursor-pointer"
              />
              {type.label}
            </label>
          ))}
        </div>
        {jobTypes.length > 0 && (
          <p className="text-xs text-brand-500 mt-1">
            Selected: {jobTypes.map(jt => JOB_TYPES.find(t => t.value === jt)?.label).join(", ")}
          </p>
        )}
      </div>

      {/* Location chips */}
      <div ref={locRef}>
        <span className="label flex items-center gap-1">
          <MapPin size={11} />
          Locations (add multiple — each searched separately)
        </span>
        <p className="text-xs text-slate-500 mb-1">
          Type any city and press Enter, or choose from suggestions
        </p>
        <div
          className={clsx(
            "input flex min-h-[38px] flex-wrap items-center gap-1.5 py-1.5",
            "cursor-text",
          )}
          onClick={() => locRef.current?.querySelector("input")?.focus()}
        >
          {locations.map((loc) => (
            <span
              key={loc}
              className="inline-flex items-center gap-1 rounded-full bg-brand-500/15 px-2.5 py-0.5 text-xs font-medium text-brand-600 dark:text-brand-300"
            >
              {loc}
              <button
                type="button"
                onClick={() => removeLocation(loc)}
                className="ml-0.5 hover:text-rose-400"
              >
                <X size={11} />
              </button>
            </span>
          ))}
          <div className="relative flex-1">
            <input
              className="w-full min-w-[120px] bg-transparent text-sm outline-none placeholder-slate-400"
              placeholder={locations.length === 0 ? "Hyderabad, Remote — India, …" : "Add another…"}
              value={locInput}
              onChange={(e) => { setLocInput(e.target.value); setShowLocSuggestions(true); }}
              onKeyDown={handleLocKey}
              onFocus={() => setShowLocSuggestions(true)}
              onBlur={() => setTimeout(() => setShowLocSuggestions(false), 150)}
            />
            {showLocSuggestions && suggestions.length > 0 && (
              <div className="absolute left-0 top-full z-20 mt-1 w-56 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onMouseDown={() => addLocation(s)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800"
                  >
                    <MapPin size={12} className="text-slate-400" />
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        {locations.length > 1 && (
          <p className="mt-1 text-xs text-brand-500">
            {locations.length} locations → {locations.length} separate searches
          </p>
        )}
      </div>

      {/* Skills */}
      <label>
        <span className="label">Skills (optional)</span>
        <input
          className="input"
          placeholder="Python, AWS, PySpark"
          value={skills}
          onChange={(e) => setSkills(e.target.value)}
        />
      </label>

      {/* Quick toggles */}
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-600 dark:text-slate-300">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={score} onChange={(e) => setScore(e.target.checked)} className="accent-brand-500" />
          Score against profile
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} className="accent-brand-500" />
          Remote-friendly only
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={linkedin} onChange={(e) => setLinkedin(e.target.checked)} className="accent-brand-500" />
          Fetch LinkedIn descriptions (slower)
        </label>
      </div>

      {/* Advanced */}
      <div>
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="flex items-center gap-1 text-xs font-medium text-slate-400 hover:text-brand-500 transition-colors"
        >
          <ChevronDown size={14} className={clsx("transition-transform", showAdvanced && "rotate-180")} />
          {showAdvanced ? "Hide" : "More"} options
        </button>
        {showAdvanced && (
          <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 border-t border-slate-200 dark:border-slate-800 pt-4">
            <label>
              <span className="label">Results wanted</span>
              <input
                className="input"
                type="number"
                min={1}
                max={500}
                placeholder={String(status.data?.results_wanted ?? 30)}
                value={results}
                onChange={(e) => setResults(e.target.value ? Number(e.target.value) : "")}
              />
            </label>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="accent-brand-500" />
                Force (ignore dedupe)
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Submit */}
      <div className="flex items-center justify-between border-t border-slate-200 dark:border-slate-800 pt-3">
        {start.isError ? (
          <p className="text-sm text-rose-500">{String(start.error?.message ?? start.error)}</p>
        ) : (
          <p className="text-xs text-slate-400">
            {locations.length > 1
              ? `Will run ${locations.length} searches, one per location.`
              : expLevel || jobTypes.length > 0
              ? `Filters: ${[
                  expLevel ? EXPERIENCE_LEVELS.find((l) => l.value === expLevel)?.label : "",
                  jobTypes.length > 0 ? `${jobTypes.length} job type${jobTypes.length > 1 ? 's' : ''}` : ""
                ].filter(Boolean).join(", ")}`
              : "New jobs added to workspace; duplicates skipped."}
          </p>
        )}
        <button type="submit" className="btn-primary" disabled={start.isPending}>
          {start.isPending ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
          Search
        </button>
      </div>
    </form>
  );
}
