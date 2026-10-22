import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Briefcase,
  ChevronDown,
  ClipboardList,
  History,
  Loader2,
  LogOut,
  Moon,
  PenSquare,
  Sun,
  User,
} from "lucide-react";
import { useActiveTasks, useStatus } from "@/lib/hooks";
import { useAuth } from "@/lib/auth";
import clsx from "clsx";

// ─── Dark-mode hook ────────────────────────────────────────────────────────────
function useDarkMode() {
  const [dark, setDark] = useState<boolean>(() => {
    const stored = localStorage.getItem("ja_theme");
    if (stored) return stored === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (dark) {
      root.classList.add("dark");
      root.style.colorScheme = "dark";
    } else {
      root.classList.remove("dark");
      root.style.colorScheme = "light";
    }
    localStorage.setItem("ja_theme", dark ? "dark" : "light");
  }, [dark]);

  return [dark, setDark] as const;
}

// ─── Nav items ─────────────────────────────────────────────────────────────────
const navItems = [
  { to: "/", label: "Jobs", icon: ClipboardList, end: true },
  { to: "/freeform", label: "Paste JD", icon: PenSquare },
  { to: "/searches", label: "History", icon: History },
];

export default function Layout() {
  const status = useStatus();
  const active = useActiveTasks();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [dark, setDark] = useDarkMode();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const total = status.data?.workspace_total_jobs ?? 0;

  // Close dropdown when clicking outside
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  async function handleLogout() {
    setMenuOpen(false);
    await logout();
    navigate("/login");
  }

  return (
    <div className="flex min-h-screen flex-col bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors duration-200">
      {/* ── Header ───────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          {/* Brand */}
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand-500/20 text-brand-500 dark:text-brand-300">
              <Briefcase size={18} />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight">JobApply</div>
              <div className="text-xs text-slate-400">
                {status.data ? (
                  <>
                    <span className="font-mono">{total}</span>{" "}
                    {total === 1 ? "job" : "jobs"} ·{" "}
                    <span className="text-slate-500 dark:text-slate-400">
                      {status.data.provider}/{status.data.model}
                    </span>
                  </>
                ) : (
                  "loading…"
                )}
              </div>
            </div>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-2">
            {/* In-progress pill */}
            {active.hasActive && (
              <div className="hidden items-center gap-2 rounded-full border border-brand-500/40 bg-brand-500/10 px-3 py-1 text-xs font-medium text-brand-600 dark:text-brand-200 sm:flex">
                <Loader2 size={12} className="animate-spin" />
                <span>
                  {active.all.length} {active.all.length === 1 ? "job" : "jobs"} in progress
                </span>
              </div>
            )}

            {/* Nav links */}
            <nav className="flex items-center gap-1">
              {navItems.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    clsx(
                      "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white"
                        : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-100",
                    )
                  }
                >
                  <item.icon size={16} />
                  <span className="hidden sm:inline">{item.label}</span>
                </NavLink>
              ))}
            </nav>

            {/* Dark/light toggle */}
            <button
              onClick={() => setDark(d => !d)}
              className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
              title={dark ? "Switch to light mode" : "Switch to dark mode"}
            >
              {dark ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            {/* User menu */}
            {user && (
              <div className="relative" ref={menuRef}>
                <button
                  onClick={() => setMenuOpen(o => !o)}
                  className={clsx(
                    "flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm font-medium transition-colors",
                    menuOpen
                      ? "bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                      : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100",
                  )}
                >
                  <div className="grid h-6 w-6 place-items-center rounded-full bg-brand-500/20 text-brand-500 dark:text-brand-300 text-xs font-semibold">
                    {user.email[0].toUpperCase()}
                  </div>
                  <span className="hidden max-w-[120px] truncate sm:inline">{user.email}</span>
                  <ChevronDown size={14} className={clsx("transition-transform", menuOpen && "rotate-180")} />
                </button>

                {/* Dropdown */}
                {menuOpen && (
                  <div className="absolute right-0 mt-2 w-56 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg shadow-black/20 ring-1 ring-black/5">
                    <div className="border-b border-slate-100 dark:border-slate-800 px-3 py-2.5">
                      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Signed in as</p>
                      <p className="mt-0.5 truncate text-sm font-semibold text-slate-800 dark:text-slate-100">
                        {user.email}
                      </p>
                      {!user.email_verified && (
                        <span className="mt-1 inline-flex items-center rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-500">
                          Email unverified
                        </span>
                      )}
                    </div>
                    <div className="p-1">
                      <button
                        className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                        onClick={() => setMenuOpen(false)}
                      >
                        <User size={15} />
                        Account
                      </button>
                      <button
                        className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors"
                        onClick={handleLogout}
                      >
                        <LogOut size={15} />
                        Sign out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ── Page content ─────────────────────────────────────────────── */}
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-10">
        <Outlet />
      </main>

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-200 dark:border-slate-800 px-4 py-4 text-center text-xs text-slate-400">
        Workspace:{" "}
        <span className="font-mono">{status.data?.workspace ?? "…"}</span> ·
        Profile:{" "}
        {status.data?.profile_loaded ? (
          <span className="text-brand-500 dark:text-brand-300">{status.data.profile_name}</span>
        ) : (
          <span className="text-amber-500">not loaded — run `jobapply init`</span>
        )}
      </footer>
    </div>
  );
}
