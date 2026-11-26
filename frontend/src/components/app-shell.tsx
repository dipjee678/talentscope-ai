"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Briefcase,
  CheckSquare,
  Compass,
  FileUp,
  GitCompare,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Settings,
  Sparkles,
  Sun,
  UserCheck,
  X
} from "lucide-react";
import { useApp } from "@/components/providers";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/cv/upload", label: "My CV", icon: FileUp },
  { href: "/profile", label: "My Profile", icon: UserCheck },
  { href: "/search/new", label: "New Job Search", icon: Compass },
  { href: "/jobs", label: "Matched Jobs", icon: Briefcase },
  { href: "/jobs/compare", label: "Compare Jobs", icon: GitCompare },
  { href: "/tracker", label: "Applications", icon: CheckSquare },
  { href: "/assistant", label: "Career Assistant", icon: Sparkles },
  { href: "/settings", label: "Settings", icon: Settings }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loadingUser, theme, toggleTheme, logout, compareIds } = useApp();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!loadingUser && !user) {
      router.replace("/auth/login");
    }
  }, [loadingUser, user, router]);

  if (loadingUser) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <div className="h-4 w-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          Loading workspace...
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-border bg-card/60 backdrop-blur">
        <div className="h-16 px-5 flex items-center justify-between border-b border-border">
          <Link href="/dashboard" className="flex items-center gap-2.5 font-semibold tracking-tight">
            <div className="h-8 w-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center font-bold text-sm shadow-sm">
              TS
            </div>
            <span>TalentScope AI</span>
          </Link>
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active =
              pathname === item.href ||
              (item.href !== "/jobs" && pathname.startsWith(item.href)) ||
              (item.href === "/jobs" && pathname === "/jobs");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                )}
              >
                <span className="flex items-center gap-2.5">
                  <Icon className="h-4 w-4" />
                  {item.label}
                </span>
                {item.href === "/jobs/compare" && compareIds.length > 0 && (
                  <span
                    className={cn(
                      "text-[11px] px-1.5 py-0.5 rounded-full font-semibold",
                      active ? "bg-white/20 text-white" : "bg-primary/15 text-primary"
                    )}
                  >
                    {compareIds.length}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t border-border space-y-2">
          <div className="px-3 py-2 rounded-lg bg-muted/60 text-xs">
            <div className="font-medium text-foreground truncate">{user.full_name}</div>
            <div className="text-muted-foreground truncate">{user.email}</div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-border text-xs font-medium hover:bg-accent transition"
              aria-label="Toggle theme"
            >
              {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
              {theme === "dark" ? "Light" : "Dark"}
            </button>
            <button
              onClick={logout}
              className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-border text-xs font-medium text-rose-500 hover:bg-rose-500/10 transition"
            >
              <LogOut className="h-3.5 w-3.5" />
              Exit
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div className="fixed inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <div className="relative z-10 w-72 bg-card border-r border-border flex flex-col p-4">
            <div className="flex items-center justify-between pb-4 border-b border-border">
              <span className="font-semibold">TalentScope AI</span>
              <button onClick={() => setMobileOpen(false)} className="p-1 rounded hover:bg-accent">
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="flex-1 py-4 space-y-1 overflow-y-auto">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      "flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium",
                      pathname === item.href
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="lg:hidden h-14 px-4 border-b border-border bg-card flex items-center justify-between">
          <button onClick={() => setMobileOpen(true)} className="p-2 rounded-lg hover:bg-accent">
            <Menu className="h-5 w-5" />
          </button>
          <span className="font-semibold text-sm">TalentScope AI</span>
          <button onClick={toggleTheme} className="p-2 rounded-lg hover:bg-accent">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}
