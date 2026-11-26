"use client";

import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  FileSearch,
  Globe2,
  Layers,
  Lock,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import { useApp } from "@/components/providers";

const AGENTS = [
  { num: "01", name: "CV Analysis Agent", desc: "Parses PDF/DOCX/OCR into a verified candidate profile without inventing credentials." },
  { num: "02", name: "Job Discovery Agent", desc: "Queries 16+ permitted global APIs, country boards, and direct ATS career pages in parallel." },
  { num: "03", name: "Job Extraction Agent", desc: "Separates mandatory vs preferred requirements and strips untrusted prompt injections." },
  { num: "04", name: "Matching Engine", desc: "Scores 6 weighted dimensions (Skills 30%, Exp 20%, Edu 15%, Quals 15%, Projects 10%, Role 10%)." },
  { num: "05", name: "Verification Agent", desc: "Validates live application links, detects closed roles, and deduplicates across job boards." },
  { num: "06", name: "Ranking Agent", desc: "Enforces your minimum match threshold and prioritizes direct company application links." },
  { num: "07", name: "Reporting Agent", desc: "Produces transparent coverage reports, source disclosures, and live dashboard updates." }
];

export default function LandingPage() {
  const { user, theme, toggleTheme } = useApp();

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <header className="border-b border-border/80 backdrop-blur sticky top-0 z-30 bg-background/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5 font-semibold tracking-tight">
            <div className="h-8 w-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center font-bold text-sm">
              TS
            </div>
            <span>TalentScope AI</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              className="px-3 py-1.5 rounded-lg border border-border text-xs font-medium hover:bg-accent transition"
            >
              {theme === "dark" ? "Light Mode" : "Dark Mode"}
            </button>
            {user ? (
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition"
              >
                Open Dashboard <ArrowRight className="h-4 w-4" />
              </Link>
            ) : (
              <>
                <Link
                  href="/auth/login"
                  className="px-3.5 py-2 rounded-lg text-sm font-medium hover:bg-accent transition"
                >
                  Log in
                </Link>
                <Link
                  href="/auth/register"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition"
                >
                  Get Started <ArrowRight className="h-4 w-4" />
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="max-w-6xl mx-auto px-4 sm:px-6 pt-20 pb-16 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/30 bg-primary/10 text-primary text-xs font-semibold mb-6">
            <Bot className="h-3.5 w-3.5" /> Autonomous 7-Agent Job Discovery & Matching Platform
          </div>
          <h1 className="text-4xl sm:text-6xl font-bold tracking-tight leading-[1.1] max-w-4xl mx-auto">
            Upload your CV. Set your match bar. Let autonomous agents hunt worldwide.
          </h1>
          <p className="mt-6 text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto">
            TalentScope AI extracts your verified qualifications, searches permitted international job boards and
            direct employer ATS career pages, verifies live links, removes duplicates, and explains every matching
            percentage transparently.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <Link
              href={user ? "/search/new" : "/auth/register"}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-primary text-primary-foreground font-semibold shadow-sm hover:opacity-90 transition"
            >
              Start Autonomous Job Search <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href={user ? "/dashboard" : "/auth/login"}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl border border-border bg-card font-semibold hover:bg-accent transition"
            >
              Explore Workspace
            </Link>
          </div>
        </section>

        {/* Core Pillars */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 py-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {[
            {
              icon: FileSearch,
              title: "Grounded CV Analysis",
              body: "Extracts skills, degrees, internships, projects, and flags missing details—never inventing credentials."
            },
            {
              icon: Globe2,
              title: "Multi-Source Discovery",
              body: "Searches Remotive, Arbeitnow, Remote OK, The Muse, Jobicy, Himalayas, WWR, JobTechDev, Greenhouse, Lever & Ashby."
            },
            {
              icon: ShieldCheck,
              title: "Verified & Deduplicated",
              body: "Checks live HTTP availability, removes expired postings, and prioritizes direct employer career links."
            },
            {
              icon: Lock,
              title: "Privacy & Injection Defense",
              body: "Fernet encryption at rest, active-content malware checks, PII-redacted logs, and untrusted-data isolation."
            }
          ].map((f) => {
            const Icon = f.icon;
            return (
              <div key={f.title} className="rounded-xl border border-border bg-card p-5 space-y-2.5">
                <div className="h-9 w-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="font-semibold text-base">{f.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{f.body}</p>
              </div>
            );
          })}
        </section>

        {/* 7-Agent Architecture Grid */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 py-14">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-primary mb-2">
            <Layers className="h-4 w-4" /> Multi-Agent Pipeline
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-8">
            Seven Specialized Agents. Zero Black-Box Guessing.
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {AGENTS.map((a) => (
              <div key={a.num} className="rounded-xl border border-border bg-card/70 p-4 flex flex-col gap-2">
                <span className="font-mono text-xs font-bold text-primary">AGENT {a.num}</span>
                <h3 className="font-semibold text-sm">{a.name}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">{a.desc}</p>
              </div>
            ))}
            <div className="rounded-xl border border-primary/40 bg-primary/5 p-4 flex flex-col justify-between">
              <div>
                <span className="font-mono text-xs font-bold text-primary flex items-center gap-1">
                  <Sparkles className="h-3.5 w-3.5" /> CENTRAL ORCHESTRATOR
                </span>
                <h3 className="font-semibold text-sm mt-1">Real-Time SSE Telemetry</h3>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                  Watch every agent execute live with per-source counts, deduplication metrics, and honest source
                  limitation disclosures.
                </p>
              </div>
              <div className="mt-3 flex items-center gap-1 text-xs font-medium text-emerald-500">
                <CheckCircle2 className="h-3.5 w-3.5" /> Explainable & Non-Inflated Scoring
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        TalentScope AI • Respects robots.txt, rate limits, and official APIs • Matching scores reflect CV alignment,
        never guaranteed hiring outcomes.
      </footer>
    </div>
  );
}
