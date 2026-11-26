"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useApp } from "@/components/providers";
import { PasswordInput } from "@/components/password-input";

export default function RegisterPage() {
  const { loginWithTokens } = useApp();
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const data = await apiFetch<{ access_token: string; refresh_token: string; user: any }>(
        "/auth/register",
        {
          method: "POST",
          body: JSON.stringify({ full_name: fullName, email, password })
        }
      );
      loginWithTokens(data.access_token, data.refresh_token, data.user);
      router.push("/cv/upload");
    } catch (err: any) {
      setError(err.message || "Registration failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-7 shadow-sm space-y-6">
        <div className="space-y-1 text-center">
          <Link href="/" className="inline-flex items-center gap-2 font-semibold text-base">
            <span className="h-7 w-7 rounded-lg bg-primary text-primary-foreground inline-flex items-center justify-center text-xs font-bold">
              TS
            </span>
            TalentScope AI
          </Link>
          <h1 className="text-xl font-bold pt-2">Create your account</h1>
          <p className="text-xs text-muted-foreground">
            Upload your CV and launch autonomous multi-country job discovery in minutes.
          </p>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-500">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium">Full name</label>
            <input
              type="text"
              required
              minLength={2}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Ada Lovelace"
              className="w-full px-3.5 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium">Email address</label>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ada@example.com"
              className="w-full px-3.5 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium">Password (min 8 characters)</label>
            <PasswordInput value={password} onChange={setPassword} autoComplete="new-password" minLength={8} />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:opacity-90 disabled:opacity-50 transition"
          >
            {submitting ? "Creating workspace..." : "Create Account"} <ArrowRight className="h-4 w-4" />
          </button>
        </form>

        <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border">
          <span className="inline-flex items-center gap-1">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" /> User-isolated data
          </span>
          <Link href="/auth/login" className="text-primary font-medium hover:underline">
            Already have an account? Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
