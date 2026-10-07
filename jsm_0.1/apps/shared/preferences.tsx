"use client";

// Language and theme preferences, shared by every JSM web app.
//
// They live in localStorage, so on one origin (the API server)
// a choice made in one app carries over to the others.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { LANGUAGE_KEY, THEME_KEY } from "./preferences-script";

export type Language = "ar" | "en";
export type Theme = "system" | "light" | "dark";

export const LANGUAGES: readonly Language[] = ["ar", "en"];
export const THEMES: readonly Theme[] = ["system", "light", "dark"];

export const DEFAULT_LANGUAGE: Language = "ar";
export const DEFAULT_THEME: Theme = "light";

const CHANGE_EVENT = "jsm:preferences";

type Preferences = {
  language: Language;
  setLanguage: (language: Language) => void;
  /** The user's choice, which may be "system". */
  theme: Theme;
  setTheme: (theme: Theme) => void;
  /** "rtl" for Arabic, "ltr" for English. */
  direction: "rtl" | "ltr";
};

const PreferencesContext = createContext<Preferences | null>(null);

function read<T extends string>(
  key: string,
  allowed: readonly T[],
  fallback: T,
): T {
  try {
    const value = window.localStorage.getItem(key);
    return allowed.includes(value as T) ? (value as T) : fallback;
  } catch {
    // Storage can be blocked (private mode); use the default.
    return fallback;
  }
}

function write(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // The choice still applies for this page view.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function subscribe(onChange: () => void) {
  window.addEventListener(CHANGE_EVENT, onChange);
  // Another tab, or another JSM app on the same origin.
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function resolveTheme(theme: Theme): "light" | "dark" {
  if (theme !== "system") return theme;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

type ProviderProps = {
  children: ReactNode;
  /** false pins the app to the light theme (the public website). */
  themable?: boolean;
};

export function PreferencesProvider({
  children,
  themable = true,
}: ProviderProps) {
  // The static HTML is rendered with the defaults; the stored
  // choice takes over on the client.
  const language = useSyncExternalStore(
    subscribe,
    () => read(LANGUAGE_KEY, LANGUAGES, DEFAULT_LANGUAGE),
    () => DEFAULT_LANGUAGE,
  );

  const storedTheme = useSyncExternalStore(
    subscribe,
    () => read(THEME_KEY, THEMES, DEFAULT_THEME),
    () => DEFAULT_THEME,
  );

  const theme: Theme = themable ? storedTheme : "light";
  const direction: "rtl" | "ltr" = language === "ar" ? "rtl" : "ltr";

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = direction;
  }, [language, direction]);

  useEffect(() => {
    const apply = () => {
      document.documentElement.dataset.theme = resolveTheme(theme);
    };

    apply();

    if (theme !== "system") return;

    // Follow the operating system while "system" is selected.
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);

  const setLanguage = useCallback((next: Language) => {
    write(LANGUAGE_KEY, next);
  }, []);

  const setTheme = useCallback((next: Theme) => {
    write(THEME_KEY, next);
  }, []);

  const value = useMemo(
    () => ({ language, setLanguage, theme, setTheme, direction }),
    [language, setLanguage, theme, setTheme, direction],
  );

  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  );
}

export function usePreferences(): Preferences {
  const preferences = useContext(PreferencesContext);

  if (preferences === null) {
    throw new Error(
      "usePreferences must be used inside <PreferencesProvider>",
    );
  }

  return preferences;
}
