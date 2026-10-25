import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState } from "react";

const ThemeContext = createContext(null);
const STORAGE_KEY = "churnshield-theme";

function getInitialMode() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return ["light", "dark", "system"].includes(saved) ? saved : "light";
  } catch {
    return "light";
  }
}

function getSystemTheme() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }) {
  const [mode, setMode] = useState(getInitialMode);
  const [systemTheme, setSystemTheme] = useState(getSystemTheme);
  const theme = mode === "system" ? systemTheme : mode;

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return undefined;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const updateSystemTheme = (event) => setSystemTheme(event.matches ? "dark" : "light");
    setSystemTheme(media.matches ? "dark" : "light");
    media.addEventListener?.("change", updateSystemTheme);
    if (!media.addEventListener) media.addListener?.(updateSystemTheme);
    return () => {
      media.removeEventListener?.("change", updateSystemTheme);
      if (!media.removeEventListener) media.removeListener?.(updateSystemTheme);
    };
  }, []);

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(STORAGE_KEY, mode); } catch { /* Theme remains available for this session. */ }
  }, [mode, theme]);

  const toggleTheme = useCallback(() => {
    setMode(theme === "dark" ? "light" : "dark");
  }, [theme]);
  const value = useMemo(() => ({ theme, mode, setMode, toggleTheme }), [theme, mode, toggleTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within ThemeProvider");
  return context;
}
