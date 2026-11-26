"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Calendar, ExternalLink, Trash2 } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import type { ApplicationStatus, TrackedApplication } from "@/lib/types";
import { formatDate } from "@/lib/utils";

const STATUSES: ApplicationStatus[] = [
  "saved",
  "interested",
  "applied",
  "assessment",
  "interview",
  "offer",
  "rejected"
];

export default function ApplicationTrackerPage() {
  const [apps, setApps] = useState<TrackedApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingNotes, setEditingNotes] = useState<Record<string, string>>({});
  const [editingFollowUp, setEditingFollowUp] = useState<Record<string, string>>({});

  const loadApps = async () => {
    setLoading(true);
    try {
      const list = await apiFetch<TrackedApplication[]>("/tracker/applications");
      setApps(list);
      const notesMap: Record<string, string> = {};
      const followMap: Record<string, string> = {};
      list.forEach((a) => {
        notesMap[a.id] = a.notes || "";
        followMap[a.id] = a.follow_up_at ? a.follow_up_at.slice(0, 10) : "";
      });
      setEditingNotes(notesMap);
      setEditingFollowUp(followMap);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApps();
  }, []);

  const updateApp = async (appId: string, patch: Record<string, any>) => {
    const updated = await apiFetch<TrackedApplication>(`/tracker/applications/${appId}`, {
      method: "PATCH",
      body: JSON.stringify(patch)
    });
    setApps((prev) => prev.map((a) => (a.id === appId ? updated : a)));
  };

  const deleteApp = async (appId: string) => {
    await apiFetch(`/tracker/applications/${appId}`, { method: "DELETE" });
    setApps((prev) => prev.filter((a) => a.id !== appId));
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Job Application Tracker</h1>
            <p className="text-sm text-muted-foreground">
              Track progress from Saved through Offer, record notes, store direct URLs, and schedule follow-ups.
              Applications are never submitted automatically without your explicit action.
            </p>
          </div>
          <Link
            href="/jobs"
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-semibold"
          >
            + Add Jobs from Results
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
          {STATUSES.map((st) => {
            const count = apps.filter((a) => a.status === st).length;
            return (
              <div key={st} className="rounded-xl border border-border bg-card p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
                  {st}
                </div>
                <div className="text-xl font-bold mt-1">{count}</div>
              </div>
            );
          })}
        </div>

        {loading ? (
          <div className="h-48 rounded-xl border border-border bg-card animate-pulse" />
        ) : apps.length === 0 ? (
          <div className="rounded-xl border border-border bg-card p-10 text-center space-y-3">
            <p className="text-sm text-muted-foreground">
              No tracked applications yet. Click <strong>Mark Applied</strong> on any matching job card to begin
              tracking.
            </p>
            <Link
              href="/jobs"
              className="inline-block px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-semibold"
            >
              Browse Matching Jobs →
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {apps.map((app) => (
              <div key={app.id} className="rounded-xl border border-border bg-card p-5 space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="text-xs text-muted-foreground">
                      {app.job.company_name} • {app.job.location_raw}
                      {app.match_score != null && (
                        <span className="ml-2 font-semibold text-primary">
                          ({Math.round(app.match_score)}% CV Match)
                        </span>
                      )}
                    </div>
                    <Link
                      href={`/jobs/${app.job_id}`}
                      className="text-base font-semibold hover:text-primary transition"
                    >
                      {app.job.title}
                    </Link>
                    <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-3">
                      {app.applied_at && (
                        <span className="inline-flex items-center gap-1">
                          <Calendar className="h-3 w-3" /> Applied {formatDate(app.applied_at)}
                        </span>
                      )}
                      <span>History events: {app.history.length}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      value={app.status}
                      onChange={(e) => updateApp(app.id, { status: e.target.value })}
                      className="px-3 py-1.5 rounded-lg border border-border bg-background text-xs font-semibold uppercase"
                    >
                      {STATUSES.map((st) => (
                        <option key={st} value={st}>
                          {st}
                        </option>
                      ))}
                    </select>

                    <a
                      href={app.application_url || app.job.apply_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border hover:bg-accent text-xs font-medium"
                    >
                      Portal <ExternalLink className="h-3 w-3" />
                    </a>

                    <button
                      onClick={() => deleteApp(app.id)}
                      className="p-1.5 rounded-lg border border-border text-rose-500 hover:bg-rose-500/10"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 border-t border-border text-xs">
                  <div className="md:col-span-2">
                    <label className="text-[11px] font-medium text-muted-foreground">
                      Notes & Interview Takeaways
                    </label>
                    <div className="mt-1 flex gap-2">
                      <input
                        value={editingNotes[app.id] || ""}
                        onChange={(e) =>
                          setEditingNotes((prev) => ({ ...prev, [app.id]: e.target.value }))
                        }
                        placeholder="Add recruiter contact, interview stage notes..."
                        className="flex-1 px-3 py-1.5 rounded-lg border border-border bg-background"
                      />
                      <button
                        onClick={() => updateApp(app.id, { notes: editingNotes[app.id] || "" })}
                        className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground font-medium"
                      >
                        Save
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="text-[11px] font-medium text-muted-foreground">
                      Follow-Up Reminder Date
                    </label>
                    <div className="mt-1 flex gap-2">
                      <input
                        type="date"
                        value={editingFollowUp[app.id] || ""}
                        onChange={(e) => {
                          const v = e.target.value;
                          setEditingFollowUp((prev) => ({ ...prev, [app.id]: v }));
                          if (v) updateApp(app.id, { follow_up_at: new Date(v).toISOString() });
                        }}
                        className="w-full px-3 py-1.5 rounded-lg border border-border bg-background"
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
