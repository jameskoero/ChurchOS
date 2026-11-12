// Small, careful wrappers around localStorage for the offline check-in. They never throw.
const ROSTER = 'cos.roster.v1';
const QUEUE = 'cos.queue.v1';
const MAX_AGE_MS = 14 * 24 * 3600 * 1000;

function read(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (e) {
    return fallback;
  }
}

function write(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (e) {
    return false;
  }
}

export function newId() {
  const id = (window.crypto && window.crypto.randomUUID)
    ? window.crypto.randomUUID()
    : 'c' + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
  return id.slice(0, 40);
}

// The saved member list holds names and member numbers only, and expires after 14 days.
export function loadRoster() {
  const saved = read(ROSTER, null);
  if (saved && saved.savedAt && Date.now() - saved.savedAt < MAX_AGE_MS && Array.isArray(saved.members)) return saved;
  return { savedAt: 0, members: [] };
}
export const saveRoster = roster => write(ROSTER, roster);
export function clearRoster() {
  try { window.localStorage.removeItem(ROSTER); } catch (e) { /* nothing to do */ }
}

// Marks waiting to sync: ids and the service only, never names.
export function loadQueue() {
  const queue = read(QUEUE, []);
  return Array.isArray(queue) ? queue : [];
}
export const saveQueue = queue => write(QUEUE, queue);
