"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  FileUp,
  Lock,
  Trash2,
  UserCheck
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { API_BASE_URL, apiFetch, getFreshAccessToken } from "@/lib/api";
import type { UploadedCV } from "@/lib/types";
import { cn, formatBytes, formatDate, humanize } from "@/lib/utils";

export default function CVUploadPage() {
  const [cvs, setCvs] = useState<UploadedCV[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latestUploaded, setLatestUploaded] = useState<UploadedCV | null>(null);

  const loadCvs = async () => {
    try {
      const list = await apiFetch<UploadedCV[]>("/cvs");
      setCvs(list);
    } catch (err: any) {
      setError(err.message);
    }
  };

  useEffect(() => {
    loadCvs();
  }, []);

  const [dragging, setDragging] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) await uploadFile(file);
  };

  const handleDrop = async (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && !uploading) await uploadFile(file);
  };

  const uploadFile = async (file: File) => {
    if (!/.(pdf|docx|doc)$/i.test(file.name)) {
      setError("Please choose a PDF, DOCX, or DOC file.");
      return;
    }
    setError(null);
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const created = await apiFetch<UploadedCV>("/cvs/upload", {
        method: "POST",
        body: formData
      });
      setLatestUploaded(created);
      await loadCvs();
    } catch (err: any) {
      setError(err.message || "CV upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const handleActivate = async (cvId: string) => {
    await apiFetch(`/cvs/${cvId}/activate`, { method: "POST" });
    await loadCvs();
  };

  const handleDelete = async (cvId: string) => {
    if (!confirm("Permanently delete this encrypted CV and its extracted profile?")) return;
    await apiFetch(`/cvs/${cvId}`, { method: "DELETE" });
    if (latestUploaded?.id === cvId) setLatestUploaded(null);
    await loadCvs();
  };

  const handleDownload = async (cv: UploadedCV) => {
    const token = await getFreshAccessToken();
    const res = await fetch(`${API_BASE_URL}/cvs/${cv.id}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    });
    if (!res.ok) {
      setError(`Download failed (${res.status}).`);
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = cv.original_filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppShell>
      <div className="space-y-8 max-w-4xl">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Your CV</h1>
          <p className="text-sm text-muted-foreground">
            Upload a PDF or Word file. We scan it for malware, encrypt it, and read your skills, education and
            experience — you can review and edit everything on your Profile page afterwards.
          </p>
        </div>

        {/* Upload Dropzone */}
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={cn(
            "block rounded-2xl border-2 border-dashed bg-card p-10 text-center cursor-pointer transition",
            dragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/60",
            uploading && "pointer-events-none opacity-80"
          )}
        >
          <input
            type="file"
            accept=".pdf,.docx,.doc"
            onChange={handleFileChange}
            disabled={uploading}
            className="hidden"
          />
          <div className="mx-auto h-12 w-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-3">
            <FileUp className="h-6 w-6" />
          </div>
          <div className="font-semibold text-base">
            {uploading
              ? "Scanning and reading your CV… this takes a few seconds"
              : dragging
              ? "Drop your CV here"
              : "Drag & drop your CV here, or click to browse"}
          </div>
          <div className="mt-1 text-xs text-muted-foreground flex items-center justify-center gap-2">
            <Lock className="h-3.5 w-3.5 text-emerald-500" /> PDF, DOCX or DOC • up to 10 MB • stored encrypted
          </div>
        </label>

        {error && (
          <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-sm text-rose-500 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {latestUploaded?.profile && (
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 font-semibold text-sm text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="h-4 w-4" /> AI Analysis Complete for {latestUploaded.original_filename}
              </div>
              <div className="flex items-center gap-2">
                <Link
                  href="/profile"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card text-xs font-medium hover:bg-accent"
                >
                  <UserCheck className="h-3.5 w-3.5" /> Review & Edit Profile
                </Link>
                <Link
                  href="/search/new"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold"
                >
                  Configure AI Job Search →
                </Link>
              </div>
            </div>
            <div className="text-xs text-muted-foreground">
              Extracted{" "}
              <strong className="text-foreground">
                {latestUploaded.profile.programming_languages.length +
                  latestUploaded.profile.technical_skills.length}
              </strong>{" "}
              technical/programming skills • Highest Degree:{" "}
              <strong className="text-foreground">
                {latestUploaded.profile.highest_degree || "Not stated"}
              </strong>{" "}
              • Scanned-text OCR: <strong className="text-foreground">{humanize(latestUploaded.ocr_status)}</strong>
            </div>
            {latestUploaded.profile.missing_or_unclear.length > 0 && (
              <div className="text-xs text-amber-600 dark:text-amber-400 space-y-0.5">
                <div className="font-semibold">Items flagged for optional manual review:</div>
                {latestUploaded.profile.missing_or_unclear.map((item, idx) => (
                  <div key={idx}>• {item}</div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* CV Version History */}
        <div className="space-y-3">
          <h2 className="font-semibold text-base">Stored CV Versions ({cvs.length})</h2>
          {cvs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No CVs uploaded yet.</p>
          ) : (
            <div className="space-y-3">
              {cvs.map((cv) => (
                <div
                  key={cv.id}
                  className="rounded-xl border border-border bg-card p-4 flex flex-wrap items-center justify-between gap-4"
                >
                  <div className="flex items-start gap-3">
                    <FileText className="h-5 w-5 text-primary mt-0.5" />
                    <div>
                      <div className="flex items-center gap-2 font-medium text-sm">
                        <span>{cv.original_filename}</span>
                        <span className="text-[11px] px-2 py-0.5 rounded bg-muted">v{cv.version_number}</span>
                        {cv.is_active && (
                          <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-semibold">
                            Active
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {formatBytes(cv.file_size_bytes)} • Uploaded {formatDate(cv.created_at)} • Security scan:{" "}
                        {humanize(cv.security_scan_status)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 text-xs">
                    {!cv.is_active && (
                      <button
                        onClick={() => handleActivate(cv.id)}
                        className="px-3 py-1.5 rounded-lg border border-border hover:bg-accent font-medium"
                      >
                        Set Active
                      </button>
                    )}
                    <button
                      onClick={() => handleDownload(cv)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border hover:bg-accent font-medium"
                    >
                      <Download className="h-3.5 w-3.5" /> Original
                    </button>
                    <button
                      onClick={() => handleDelete(cv.id)}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-border text-rose-500 hover:bg-rose-500/10"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
