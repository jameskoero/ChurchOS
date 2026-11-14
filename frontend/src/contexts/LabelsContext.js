import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { governanceAPI } from '../api';
import { useAuth } from './AuthContext';

export const GENERIC = {
  region_label: 'Region', unit_label: 'Church', region_leader_title: 'Regional leader',
  unit_leader_title: 'Pastor', seat_label: 'Headquarters church',
};

/** Church -> Churches, Altar -> Altars. */
export function plural(word) {
  const w = String(word || '');
  return /(s|x|z|ch|sh)$/i.test(w) ? w + 'es' : w + 's';
}

const Ctx = createContext({ labels: GENERIC, church: '', info: null, reload: () => {} });

export function LabelsProvider({ children }) {
  const { user } = useAuth();
  const [info, setInfo] = useState(null);
  const reload = useCallback(() => {
    if (!user) { setInfo(null); return; }
    governanceAPI.church().then(r => setInfo(r.data)).catch(() => {});
  }, [user]);
  useEffect(() => { reload(); }, [reload]);
  const value = useMemo(() => ({
    labels: { ...GENERIC, ...(info?.labels || {}) }, church: info?.church || '', info, reload,
  }), [info, reload]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useLabels = () => useContext(Ctx);
