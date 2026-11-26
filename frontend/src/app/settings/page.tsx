"use client";

import React, { useEffect, useState } from "react";
import { CheckCircle2, Plus, Save, Shield, Trash2 } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { useApp } from "@/components/providers";
import { apiFetch } from "@/lib/api";
import type { CustomATSBoard, JobSourceInfo } from "@/lib/types";

export default function SettingsPage() {
  const { user, theme, setThemeMode, refreshUser, logout } = useApp();
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [retentionDays, setRetentionDays] = useState(user?.data_retention_days || 365);
  const [weights, setWeights] = useState<Record<string, number>>(
    user?.default_weights || {
      technical_skills: 30,
      education: 15,
      work_experience: 20,
      required_qualifications: 15,
      projects_achievements: 10,
      role_relevance: 10
    }
  );
  const [boards, setBoards] = useState<CustomATSBoard[]>(user?.custom_ats_boards || []);
  const [newProvider, setNewProvider] = useState<"greenhouse" | "lever" | "ashby">("greenhouse");
  const [newSlug, setNewSlug] = useState("");
  const [newCompany, setNewCompany] = useState("");

  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [sources, setSources] = useState<JobSourceInfo[]>([]);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([apiFetch("/settings/system-status"), apiFetch<JobSourceInfo[]>("/sources")])
      .then(([sys, src]) => {
        setSystemStatus(sys);
        setSources(src);
      })
      .catch(() => {});
  }, []);

  const addBoard = () => {
    if (!newSlug.trim() || !newCompany.trim()) return;
    setBoards((prev) => [
      ...prev,
      { provider: newProvider, slug: newSlug.trim().toLowerCase(), company_name: newCompany.trim() }
    ]);
    setNewSlug("");
    setNewCompany("");
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavedMsg(null);
    await apiFetch("/settings", {
      method: "PUT",
      body: JSON.stringify({
        full_name: fullName,
        theme_preference: theme,
        data_retention_days: retentionDays,
        default_weights: weights,
        custom_ats_boards: boards
      })
    });
    await refreshUser();
    setSavedMsg("Settings saved.");
  };

  const handlePurgeCvs = async () => {
    if (!confirm("Permanently delete ALL uploaded CVs and extracted profiles from encrypted storage?")) return;
    await apiFetch("/settings/purge-cvs", { method: "DELETE" });
    setSavedMsg("All uploaded CVs permanently purged.");
  };

  const handleDeleteAccount = async () => {
    if (!confirm("Permanently delete your entire account, CVs, searches, and tracked applications?")) return;
    await apiFetch("/settings/account", { method: "DELETE" });
    logout();
  };

  return (
    <AppShell>
      <div className="max-w-4xl space-y-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Workspace Settings, Integrations & Privacy</h1>
          <p className="text-sm text-muted-foreground">
            Configure theme, default CV matching weights, custom company career boards, and data retention controls.
          </p>
        </div>

        {savedMsg && (
          <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" /> {savedMsg}
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-6">
          <div className="rounded-xl border border-border bg-card p-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-medium">Full Name</label>
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium">Appearance Mode</label>
              <select
                value={theme}
                onChange={(e) => setThemeMode(e.target.value as "light" | "dark")}
                className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
              >
                <option value="dark">Dark Mode</option>
                <option value="light">Light Mode</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium">CV Data Retention (Days)</label>
              <input
                type="number"
                min={7}
                max={3650}
                value={retentionDays}
                onChange={(e) => setRetentionDays(Number(e.target.value))}
                className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
              />
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 space-y-3">
            <h2 className="font-semibold text-base">Default 6-Dimension Matching Weights</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {Object.entries(weights).map(([k, v]) => (
                <div key={k} className="p-3 rounded-lg border border-border bg-background">
                  <label className="text-xs font-medium capitalize block">{k.replace(/_/g, " ")} (%)</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={v}
                    onChange={(e) => setWeights((prev) => ({ ...prev, [k]: Number(e.target.value) }))}
                    className="mt-1 w-full px-2.5 py-1 rounded border border-border bg-card text-sm"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 space-y-4">
            <div>
              <h2 className="font-semibold text-base">Custom Company Career Pages (Greenhouse / Lever / Ashby)</h2>
              <p className="text-xs text-muted-foreground">
                Add any company’s public ATS slug so Agent 2 searches their direct career page automatically.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <select
                value={newProvider}
                onChange={(e) => setNewProvider(e.target.value as any)}
                className="px-3 py-2 rounded-lg border border-border bg-background text-xs"
              >
                <option value="greenhouse">Greenhouse</option>
                <option value="lever">Lever</option>
                <option value="ashby">Ashby</option>
              </select>
              <input
                placeholder="Board slug (e.g. anthropic)"
                value={newSlug}
                onChange={(e) => setNewSlug(e.target.value)}
                className="px-3 py-2 rounded-lg border border-border bg-background text-xs"
              />
              <input
                placeholder="Company Name (e.g. Anthropic)"
                value={newCompany}
                onChange={(e) => setNewCompany(e.target.value)}
                className="px-3 py-2 rounded-lg border border-border bg-background text-xs"
              />
              <button
                type="button"
                onClick={addBoard}
                className="inline-flex items-center gap-1 px-3 py-2 rounded-lg border border-border hover:bg-accent text-xs font-medium"
              >
                <Plus className="h-3.5 w-3.5" /> Add Career Board
              </button>
            </div>
            {boards.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {boards.map((b, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-muted text-xs"
                  >
                    {b.company_name} ({b.provider}: {b.slug})
                    <button
                      type="button"
                      onClick={() => setBoards((prev) => prev.filter((_, idx) => idx !== i))}
                      className="text-rose-500"
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <button
            type="submit"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold"
          >
            <Save className="h-4 w-4" /> Save Settings
          </button>
        </form>

        <div className="rounded-xl border border-border bg-card p-6 space-y-4">
          <h2 className="font-semibold text-base flex items-center gap-2">
            <Shield className="h-4 w-4 text-primary" /> System & Job-Source Integration Status
          </h2>
          {systemStatus && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3 rounded-lg bg-muted/50">
                <div className="text-muted-foreground">AI / LLM Engine</div>
                <div className="font-semibold mt-0.5">
                  {systemStatus.llm_available ? systemStatus.llm_provider : "Hybrid Deterministic NLP"}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted/50">
                <div className="text-muted-foreground">Task Orchestrator</div>
                <div className="font-semibold mt-0.5 uppercase">{systemStatus.task_runner_mode}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted/50">
                <div className="text-muted-foreground">Database</div>
                <div className="font-semibold mt-0.5">{systemStatus.database_dialect}</div>
              </div>
              <div className="p-3 rounded-lg bg-muted/50">
                <div className="text-muted-foreground">CV Vault Encryption</div>
                <div className="font-semibold mt-0.5 text-emerald-500">Fernet AES Active</div>
              </div>
            </div>
          )}

          <div className="space-y-1.5 text-xs max-h-64 overflow-y-auto">
            {sources.map((s) => (
              <div
                key={s.slug}
                className="flex flex-wrap items-center justify-between gap-2 py-2 border-b border-border/60"
              >
                <div>
                  <span className="font-medium">{s.name}</span>{" "}
                  <span className="text-muted-foreground">({s.source_type})</span>
                </div>
                <span
                  className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${
                    s.api_key_configured
                      ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                      : "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                  }`}
                >
                  {s.api_key_configured ? "Active" : `Requires ${s.api_key_env_vars.join(" & ")}`}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-6 space-y-3">
          <h2 className="font-semibold text-base text-rose-500">Privacy & Data Deletion Controls</h2>
          <p className="text-xs text-muted-foreground">
            You have full ownership of your personal data. Deleting CVs immediately destroys the encrypted files
            and extracted profiles.
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handlePurgeCvs}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-rose-500/40 text-xs font-semibold text-rose-500 hover:bg-rose-500/10"
            >
              <Trash2 className="h-3.5 w-3.5" /> Purge All Uploaded CVs
            </button>
            <button
              type="button"
              onClick={handleDeleteAccount}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-rose-500 text-white text-xs font-semibold hover:opacity-90"
            >
              Delete Entire Account
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
