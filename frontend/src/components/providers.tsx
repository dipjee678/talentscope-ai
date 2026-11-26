"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { apiFetch, clearTokens, getAccessToken, setTokens } from "@/lib/api";
import type { User } from "@/lib/types";

interface AppContextValue {
  user: User | null;
  loadingUser: boolean;
  theme: "light" | "dark";
  toggleTheme: () => void;
  setThemeMode: (mode: "light" | "dark") => void;
  loginWithTokens: (access: string, refresh: string, userObj: User) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
  compareIds: string[];
  toggleCompareId: (jobId: string) => void;
  clearCompareIds: () => void;
}

const AppContext = createContext<AppContextValue | undefined>(undefined);

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [compareIds, setCompareIds] = useState<string[]>([]);

  useEffect(() => {
    const savedTheme =
      (typeof window !== "undefined" &&
        (localStorage.getItem("talentscope_theme") as "light" | "dark" | null)) ||
      "dark";
    setTheme(savedTheme);
    document.documentElement.classList.toggle("dark", savedTheme === "dark");

    const savedCompare = typeof window !== "undefined" ? localStorage.getItem("talentscope_compare") : null;
    if (savedCompare) {
      try {
        setCompareIds(JSON.parse(savedCompare));
      } catch {
        // ignore
      }
    }

    const token = getAccessToken();
    if (!token) {
      setLoadingUser(false);
      return;
    }

    apiFetch<User>("/auth/me")
      .then((u) => setUser(u))
      .catch(() => {
        clearTokens();
        setUser(null);
      })
      .finally(() => setLoadingUser(false));
  }, []);

  const setThemeMode = (mode: "light" | "dark") => {
    setTheme(mode);
    if (typeof window !== "undefined") {
      localStorage.setItem("talentscope_theme", mode);
      document.documentElement.classList.toggle("dark", mode === "dark");
    }
  };

  const toggleTheme = () => {
    setThemeMode(theme === "dark" ? "light" : "dark");
  };

  const loginWithTokens = (access: string, refresh: string, userObj: User) => {
    setTokens(access, refresh);
    setUser(userObj);
  };

  const logout = () => {
    clearTokens();
    setUser(null);
    if (typeof window !== "undefined") {
      window.location.href = "/auth/login";
    }
  };

  const refreshUser = async () => {
    try {
      const u = await apiFetch<User>("/auth/me");
      setUser(u);
    } catch {
      // ignore
    }
  };

  const toggleCompareId = (jobId: string) => {
    setCompareIds((prev) => {
      let next: string[];
      if (prev.includes(jobId)) {
        next = prev.filter((id) => id !== jobId);
      } else {
        if (prev.length >= 4) {
          next = [...prev.slice(1), jobId];
        } else {
          next = [...prev, jobId];
        }
      }
      if (typeof window !== "undefined") {
        localStorage.setItem("talentscope_compare", JSON.stringify(next));
      }
      return next;
    });
  };

  const clearCompareIds = () => {
    setCompareIds([]);
    if (typeof window !== "undefined") {
      localStorage.removeItem("talentscope_compare");
    }
  };

  return (
    <AppContext.Provider
      value={{
        user,
        loadingUser,
        theme,
        toggleTheme,
        setThemeMode,
        loginWithTokens,
        logout,
        refreshUser,
        compareIds,
        toggleCompareId,
        clearCompareIds
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside AppProviders");
  return ctx;
}
