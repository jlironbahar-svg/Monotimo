import AsyncStorage from '@react-native-async-storage/async-storage';

const PREFIX = 'df:';

export async function load<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(PREFIX + key);
    return raw == null ? fallback : { ...fallbackShape(fallback), ...JSON.parse(raw) };
  } catch {
    return fallback;
  }
}

/** Objects are merged with the fallback so new settings get defaults after an update. */
function fallbackShape<T>(fallback: T): object {
  return fallback && typeof fallback === 'object' && !Array.isArray(fallback) ? (fallback as object) : {};
}

export async function loadRaw<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(PREFIX + key);
    return raw == null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export async function save(key: string, value: unknown): Promise<void> {
  try {
    if (value === null || value === undefined) await AsyncStorage.removeItem(PREFIX + key);
    else await AsyncStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    // storage full / unavailable: the app keeps working with in-memory state
  }
}

export function randomId(len = 16): string {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let out = '';
  for (let i = 0; i < len; i++) out += chars[Math.floor(Math.random() * chars.length)];
  return out;
}
