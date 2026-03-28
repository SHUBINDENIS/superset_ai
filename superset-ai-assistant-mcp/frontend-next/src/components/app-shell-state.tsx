"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const MOBILE_CHAT_HELPER_HIDDEN_STORAGE_KEY =
  "superset-ai:mobile-chat-helper-hidden";

interface AppShellStateValue {
  isMobileViewport: boolean;
  mobileChatHelperHidden: boolean;
  setMobileChatHelperHidden: (hidden: boolean) => void;
  toggleMobileChatHelper: () => void;
}

const AppShellStateContext = createContext<AppShellStateValue | null>(null);

export function AppShellStateProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const [mobileChatHelperHidden, setMobileChatHelperHidden] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const media = window.matchMedia("(max-width: 767px)");
    const syncViewport = () => {
      setIsMobileViewport(media.matches);
    };

    syncViewport();
    media.addEventListener("change", syncViewport);
    return () => media.removeEventListener("change", syncViewport);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      const stored = window.localStorage.getItem(
        MOBILE_CHAT_HELPER_HIDDEN_STORAGE_KEY,
      );
      if (stored === "true" || stored === "false") {
        setMobileChatHelperHidden(stored === "true");
        return;
      }
    } catch {
      // Ignore storage read errors and fall back to viewport-based default.
    }

    setMobileChatHelperHidden(window.innerWidth < 768);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(
        MOBILE_CHAT_HELPER_HIDDEN_STORAGE_KEY,
        mobileChatHelperHidden ? "true" : "false",
      );
    } catch {
      // Preference persistence is non-critical.
    }
  }, [mobileChatHelperHidden]);

  const value = useMemo<AppShellStateValue>(
    () => ({
      isMobileViewport,
      mobileChatHelperHidden,
      setMobileChatHelperHidden,
      toggleMobileChatHelper: () =>
        setMobileChatHelperHidden((current) => !current),
    }),
    [isMobileViewport, mobileChatHelperHidden],
  );

  return (
    <AppShellStateContext.Provider value={value}>
      {children}
    </AppShellStateContext.Provider>
  );
}

export function useAppShellState() {
  const context = useContext(AppShellStateContext);
  if (!context) {
    throw new Error("useAppShellState must be used within AppShellStateProvider");
  }
  return context;
}
