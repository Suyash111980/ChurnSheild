import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "churnshield-theme";
const ThemeContext = createContext(null);

function readSavedTheme() {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return ["light", "dark", "system"].includes(saved) ? saved : "system";
  } catch {
    return "system";
  }
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(readSavedTheme);
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false);
  const resolvedTheme = theme === "system" ? (systemDark ? "dark" : "light") : theme;

  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    const syncSystem = () => setSystemDark(media?.matches ?? false);
    syncSystem();
    media?.addEventListener?.("change", syncSystem);
    return () => media?.removeEventListener?.("change", syncSystem);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.dataset.themeMode = theme;
    try { window.localStorage.setItem(STORAGE_KEY, theme); }
    catch { /* Theme still applies for this session when storage is unavailable. */ }
  }, [theme, resolvedTheme]);

  const toggleTheme = useCallback(() => setTheme(resolvedTheme === "dark" ? "light" : "dark"), [resolvedTheme]);
  const value = useMemo(() => ({ theme, setTheme, resolvedTheme, toggleTheme }), [theme, resolvedTheme, toggleTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within a ThemeProvider");
  return context;
}
