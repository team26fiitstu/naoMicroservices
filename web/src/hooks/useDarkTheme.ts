import { useSyncExternalStore } from "react";

const STORAGE_KEY = "theme";
const listeners = new Set<() => void>();

const isDark = () => document.documentElement.classList.contains("dark");

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

const setDark = (dark: boolean) => {
  document.documentElement.classList.toggle("dark", dark);
  try {
    localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
  } catch {
    // storage unavailable, theme lasts until reload
  }
  listeners.forEach((listener) => listener());
};

// Initial theme is applied by the script in index.html before first paint
export function useDarkTheme() {
  const dark = useSyncExternalStore(subscribe, isDark);
  return { dark, toggle: () => setDark(!dark) };
}
