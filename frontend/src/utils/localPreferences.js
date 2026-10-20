const PREFIX = "churnshield.preference.";

export function readLocalPreference(key, fallback, storage) {
  try {
    const value = (storage ?? globalThis.localStorage)?.getItem(`${PREFIX}${key}`);
    return value == null ? fallback : value === "true";
  } catch {
    return fallback;
  }
}

export function writeLocalPreference(key, value, storage) {
  try {
    (storage ?? globalThis.localStorage)?.setItem(`${PREFIX}${key}`, String(Boolean(value)));
    return true;
  } catch {
    return false;
  }
}
