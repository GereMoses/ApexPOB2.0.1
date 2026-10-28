/**
 * Live Muster Board — one screen for the control room / big TV during a muster.
 *
 * No muster running: one-tap start (general alarm, fire, gas, man down, drill) and
 * the printable muster list. Muster running: % accounted, live counts, people safe
 * per assembly point, and the missing list grouped by last known location with
 * one-tap Safe / Hurt for wardens. Refreshes every 4 seconds.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { App, Button, Input, Modal, Select, Tooltip, Empty } from 'antd';
import {
  FireOutlined, AlertOutlined, ExperimentOutlined, UserDeleteOutlined, SoundOutlined, PrinterOutlined,
  FullscreenOutlined, FullscreenExitOutlined, ArrowLeftOutlined, CheckOutlined, MedicineBoxOutlined,
  SearchOutlined, StopOutlined, EnvironmentOutlined, TeamOutlined, WhatsAppOutlined, MailOutlined, SendOutlined,
} from '@ant-design/icons';
import apiService from '../../services/api';

const TYPES = {
  0: { label: 'General alarm', color: '#ef4444' }, 1: { label: 'Drill', color: '#3b82f6' },
  2: { label: 'Fire', color: '#f97316' }, 3: { label: 'Gas', color: '#eab308' }, 4: { label: 'Man down', color: '#a855f7' },
};
const QUICK = [
  { kind: 'general', label: 'General alarm', sub: 'Whole-site muster', icon: <SoundOutlined />, color: '#ef4444' },
  { kind: 'fire', label: 'Fire', sub: 'Unlock exits · sirens · muster', icon: <FireOutlined />, color: '#f97316' },
  { kind: 'gas', label: 'Gas', sub: 'Unlock exits · sirens · muster', icon: <AlertOutlined />, color: '#eab308' },
  { kind: 'mandown', label: 'Man down', sub: 'Whole-site muster', icon: <UserDeleteOutlined />, color: '#a855f7' },
  { kind: 'drill', label: 'Drill', sub: 'Practice muster', icon: <ExperimentOutlined />, color: '#3b82f6' },
];

const fmtElapsed = (start) => {
  if (!start) return '00:00';
  const s = Math.max(0, Math.floor((Date.now() - new Date(start.endsWith('Z') || start.includes('+') ? start : start + 'Z')) / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return `${h ? `${h}:` : ''}${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
};

async function openPdf(message) {
  try {
    const res = await fetch('/api/mustering/muster-list.pdf', { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const url = URL.createObjectURL(await res.blob());
    window.open(url, '_blank');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) { message.error(`Could not build the muster list: ${e.message}`); }
}

export default function MusterBoard() {
  const { message, modal } = App.useApp();
  const qc = useQueryClient();
  const nav = useNavigate();
  const [full, setFull] = useState(false);
  const [, tick] = useState(0);
  const [q, setQ] = useState('');
  const [start, setStart] = useState(null);
  const [points, setPoints] = useState([]);
  const [endOpen, setEndOpen] = useState(false);
  const [endReason, setEndReason] = useState('');

  useEffect(() => { const t = setInterval(() => tick(x => x + 1), 1000); return () => clearInterval(t); }, []);
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && setFull(false);
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, []);

  const { data: activeRaw } = useQuery({
    queryKey: ['board-active'], queryFn: () => apiService.get('/api/mustering/events/?status=0'), refetchInterval: 4000,
  });
  const event = (Array.isArray(activeRaw?.data) ? activeRaw.data : [])[0] || null;
  const { data: hcRaw } = useQuery({
    queryKey: ['board-hc', event?.id], enabled: !!event,
    queryFn: () => apiService.get(`/api/mustering/events/${event.id}/headcount/`), refetchInterval: 4000,
  });
  const { data: logsRaw } = useQuery({
    queryKey: ['board-logs', event?.id], enabled: !!event,
    queryFn: () => apiService.get(`/api/mustering/events/${event.id}/logs/?limit=1000`), refetchInterval: 4000,
  });
  const { data: zonesRaw } = useQuery({ queryKey: ['board-zones'], queryFn: () => apiService.get('/api/mustering/zones/') });
  const { data: pobRaw } = useQuery({ queryKey: ['board-pob'], queryFn: () => apiService.get('/api/v1/pob-status/dashboard'), refetchInterval: 15000 });
  const { data: alertsRaw } = useQuery({ queryKey: ['board-alerts'], queryFn: () => apiService.get('/api/v1/settings/alerts') });

  const hc = hcRaw?.data || {};
  const logs = useMemo(() => (Array.isArray(logsRaw?.data?.logs) ? logsRaw.data.logs : []), [logsRaw]);
  const musterPoints = (Array.isArray(zonesRaw?.data) ? zonesRaw.data : []).filter(z => z.zone_kind === 'MUSTER_POINT');
  const channels = alertsRaw?.data?.channels || {};

  const startM = useMutation({
    mutationFn: (body) => apiService.post('/api/mustering/events/quick-start', body),
    onSuccess: () => { message.success('Muster started — alerts are going out'); setStart(null); qc.invalidateQueries(['board-active']); },
    onError: (e) => message.error(e.message),
  });
  const markM = useMutation({
    mutationFn: ({ emp_code, status }) => apiService.post(`/api/mustering/events/${event.id}/mark/`, { emp_code, status }),
    onSuccess: () => { qc.invalidateQueries(['board-logs']); qc.invalidateQueries(['board-hc']); },
    onError: (e) => message.error(e.message),
  });
  const endM = useMutation({
    mutationFn: () => apiService.post(`/api/mustering/events/${event.id}/end/`, { reason: endReason || 'Muster complete' }),
    onSuccess: () => { message.success('Muster ended — all-clear sent'); setEndOpen(false); setEndReason(''); qc.invalidateQueries(['board-active']); },
    onError: (e) => message.error(e.message),
  });

  const missing = logs.filter(l => l.status === 0);
  const safe = logs.filter(l => l.status === 1);
  const term = q.trim().toLowerCase();
  const groups = useMemo(() => {
    const g = {};
    missing.filter(l => !term || `${l.emp_name} ${l.emp_code} ${l.dept_name}`.toLowerCase().includes(term))
      .forEach(l => { const k = l.last_known_zone || l.last_punch_area || 'Location unknown'; (g[k] = g[k] || []).push(l); });
    return Object.entries(g).sort((a, b) => b[1].length - a[1].length);
  }, [missing, term]);
  const byPoint = useMemo(() => {
    const g = {};
    safe.forEach(l => { const k = l.last_punch_area || 'Marked safe'; g[k] = (g[k] || 0) + 1; });
    return Object.entries(g).sort((a, b) => b[1] - a[1]);
  }, [safe]);

  const expected = hc.total_expected ?? event?.total_expected ?? 0;
  const accounted = hc.total_accounted ?? 0;
  const pct = expected ? Math.round((accounted / expected) * 100) : 0;
  const type = TYPES[event?.event_type] || TYPES[0];

  const markOne = (l, status) => {
    if (status === 2) {
      modal.confirm({ title: `Mark ${l.emp_name} as injured?`, okText: 'Injured', okButtonProps: { danger: true },
        onOk: () => markM.mutateAsync({ emp_code: l.emp_code, status }) });
    } else markM.mutate({ emp_code: l.emp_code, status });
  };

  return (
    <div className={`mb-root ${full ? 'mb-full' : ''}`}>
      <style>{CSS}</style>
      <header className="mb-top">
        <div className="mb-top-l">
          {!full && <Button className="mb-ghost" icon={<ArrowLeftOutlined />} onClick={() => nav('/emergency-response')} />}
          <span className={`mb-live ${event ? 'on' : ''}`}><span /> {event ? 'MUSTER IN PROGRESS' : 'NO ACTIVE MUSTER'}</span>
          {event && <span className="mb-type" style={{ background: type.color }}>{type.label}</span>}
          {event && <span className="mb-clock">{fmtElapsed(event.start_time)}</span>}
        </div>
        <div className="mb-top-r">
          <span className="mb-chan"><WhatsAppOutlined style={{ color: channels.whatsapp ? '#4ade80' : '#64748b' }} /> <SendOutlined style={{ color: channels.telegram ? '#4ade80' : '#64748b' }} /> <MailOutlined style={{ color: channels.email ? '#4ade80' : '#64748b' }} /></span>
          <Button className="mb-ghost" icon={<PrinterOutlined />} onClick={() => openPdf(message)}>Muster list</Button>
          <Tooltip title={full ? 'Exit full screen (Esc)' : 'Full screen'}>
            <Button className="mb-ghost" icon={full ? <FullscreenExitOutlined /> : <FullscreenOutlined />} onClick={() => setFull(!full)} />
          </Tooltip>
          {event && <Button danger type="primary" icon={<StopOutlined />} onClick={() => setEndOpen(true)}>End muster</Button>}
        </div>
      </header>

      {!event ? (
        <div className="mb-idle">
          <div className="mb-idle-h">
            <div className="mb-ok"><CheckOutlined /></div>
            <div>
              <div className="mb-idle-t">All clear</div>
              <div className="mb-idle-s"><TeamOutlined /> {pobRaw?.total ?? '—'} people on board · tap an alarm to start a whole-site muster</div>
            </div>
          </div>
          <div className="mb-quick">
            {QUICK.map(k => (
              <button key={k.kind} className="mb-q" style={{ '--c': k.color }} onClick={() => { setPoints([]); setStart(k); }}>
                <span className="mb-q-i">{k.icon}</span>
                <span className="mb-q-t">{k.label}</span>
                <span className="mb-q-s">{k.sub}</span>
              </button>
            ))}
          </div>
          {!channels.whatsapp && !channels.telegram && !channels.email && (
            <div className="mb-warn">No alert channel is set up — nobody will be messaged. Settings → Email / WhatsApp &amp; Alerts.</div>
          )}
        </div>
      ) : (
        <div className="mb-grid">
          <section className="mb-panel mb-score">
            <div className="mb-ring" style={{ '--p': pct, '--c': pct === 100 ? '#22c55e' : pct > 70 ? '#eab308' : '#ef4444' }}>
              <div><b>{pct}%</b><span>accounted</span></div>
            </div>
            <div className="mb-tiles">
              {[['Expected', expected, '#94a3b8'], ['Safe', hc.total_safe ?? 0, '#22c55e'], ['Missing', hc.total_missing ?? missing.length, '#ef4444'],
                ['Injured', hc.total_injured ?? 0, '#f97316'], ['Left site', hc.total_left_site ?? 0, '#38bdf8'], ['Visitors', hc.total_visitors ?? 0, '#a78bfa']]
                .map(([l, v, c]) => <div key={l} className="mb-tile" style={{ '--c': c }}><b>{v}</b><span>{l}</span></div>)}
            </div>
            <div className="mb-sub-h"><EnvironmentOutlined /> Safe at assembly points</div>
            {byPoint.length === 0 ? <div className="mb-dim">Nobody has reached an assembly point yet.</div> : byPoint.map(([k, v]) => (
              <div key={k} className="mb-bar">
                <span>{k}</span><b>{v}</b>
                <i style={{ width: `${Math.min(100, (v / Math.max(1, expected)) * 100)}%` }} />
              </div>
            ))}
          </section>

          <section className="mb-panel mb-missing">
            <div className="mb-miss-h">
              <div><span className="mb-big-red">{missing.length}</span> still missing</div>
              <Input allowClear prefix={<SearchOutlined />} placeholder="Find a name…" value={q} onChange={e => setQ(e.target.value)} className="mb-search" />
            </div>
            {missing.length === 0 ? (
              <div className="mb-done"><CheckOutlined /> Everyone is accounted for — end the muster to send the all-clear.</div>
            ) : (
              <div className="mb-groups">
                {groups.map(([zone, people]) => (
                  <div key={zone} className="mb-group">
                    <div className="mb-group-h"><EnvironmentOutlined /> Last seen: {zone} <span>{people.length}</span></div>
                    {people.map(l => (
                      <div key={l.emp_code} className="mb-person">
                        <div className="mb-person-n">
                          <b>{l.emp_name}</b>
                          <span>{l.emp_code}{l.dept_name ? ` · ${l.dept_name}` : ''}</span>
                        </div>
                        <Button size="large" className="mb-safe" icon={<CheckOutlined />} loading={markM.isPending && markM.variables?.emp_code === l.emp_code}
                          onClick={() => markOne(l, 1)}>Safe</Button>
                        <Button size="large" className="mb-hurt" icon={<MedicineBoxOutlined />} onClick={() => markOne(l, 2)}>Hurt</Button>
                      </div>
                    ))}
                  </div>
                ))}
                {groups.length === 0 && <Empty description={<span style={{ color: '#94a3b8' }}>No match</span>} />}
              </div>
            )}
          </section>
        </div>
      )}

      <Modal open={!!start} onCancel={() => setStart(null)} okText={`Start ${start?.label || ''}`} okButtonProps={{ danger: true, size: 'large' }}
        confirmLoading={startM.isPending}
        onOk={() => startM.mutate({ kind: start.kind, muster_zone_ids: points })}
        title={<span style={{ color: start?.color }}>{start?.icon} Start {start?.label?.toLowerCase()}</span>}>
        <p>Everyone on board{start?.kind === 'drill' ? '' : ' and every visitor'} goes on the muster list and is told to go to the assembly point
          {channels.whatsapp || channels.telegram || channels.email ? ` by ${[channels.whatsapp && 'WhatsApp', channels.telegram && 'Telegram', channels.email && 'email'].filter(Boolean).join(' and ')}` : ' (no alert channel is set up)'}.
          {['fire', 'gas'].includes(start?.kind) ? ' Fire exits unlock and sirens sound.' : ''}</p>
        <div style={{ fontWeight: 600, margin: '12px 0 6px' }}>Assembly points</div>
        <Select mode="multiple" allowClear style={{ width: '100%' }} value={points} onChange={setPoints}
          placeholder="Any assembly point" options={musterPoints.map(z => ({ value: z.id, label: z.name }))} />
      </Modal>

      <Modal open={endOpen} onCancel={() => setEndOpen(false)} okText="End muster & send all-clear" confirmLoading={endM.isPending}
        onOk={() => endM.mutate()} title="End the muster?">
        {missing.length > 0 && <p style={{ color: '#dc2626', fontWeight: 600 }}>{missing.length} people are still not accounted for.</p>}
        <Input.TextArea rows={3} value={endReason} onChange={e => setEndReason(e.target.value)} placeholder="e.g. All accounted for, drill complete" />
      </Modal>
    </div>
  );
}

const CSS = `
.mb-root { min-height: calc(100vh - 56px); background: radial-gradient(900px 400px at 100% -10%, rgba(239,68,68,.12), transparent 60%), #0b1220;
  color: #e2e8f0; padding: 16px 20px 28px; font-family: Inter, -apple-system, 'Segoe UI', sans-serif; }
.mb-full { position: fixed; inset: 0; z-index: 1000; overflow: auto; }
.mb-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.mb-top-l, .mb-top-r { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.mb-ghost.ant-btn { background: rgba(255,255,255,.06) !important; border: 1px solid rgba(255,255,255,.14) !important; color: #e2e8f0 !important; }
.mb-ghost.ant-btn:hover { background: rgba(255,255,255,.14) !important; }
.mb-live { display: inline-flex; align-items: center; gap: 10px; font-weight: 800; letter-spacing: .12em; font-size: 13px; color: #94a3b8; }
.mb-live span { width: 12px; height: 12px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 0 4px rgba(34,197,94,.2); }
.mb-live.on { color: #fecaca; }
.mb-live.on span { background: #ef4444; animation: mbPulse 1.2s infinite; }
@keyframes mbPulse { 0% { box-shadow: 0 0 0 0 rgba(239,68,68,.7); } 70% { box-shadow: 0 0 0 12px rgba(239,68,68,0); } 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); } }
.mb-type { color: #fff; font-weight: 800; padding: 4px 12px; border-radius: 999px; font-size: 13px; text-transform: uppercase; letter-spacing: .06em; }
.mb-clock { font-variant-numeric: tabular-nums; font-size: 26px; font-weight: 800; color: #fff; letter-spacing: .02em; }
.mb-chan { display: inline-flex; gap: 8px; font-size: 18px; padding: 0 6px; }
.mb-idle { max-width: 1100px; margin: 40px auto 0; }
.mb-idle-h { display: flex; align-items: center; gap: 18px; margin-bottom: 26px; }
.mb-ok { width: 64px; height: 64px; border-radius: 50%; display: grid; place-items: center; font-size: 30px; color: #22c55e; background: rgba(34,197,94,.12); border: 2px solid rgba(34,197,94,.4); }
.mb-idle-t { font-size: 34px; font-weight: 800; color: #fff; }
.mb-idle-s { color: #94a3b8; font-size: 15px; display: flex; gap: 8px; align-items: center; }
.mb-quick { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
.mb-q { all: unset; cursor: pointer; box-sizing: border-box; display: flex; flex-direction: column; gap: 6px; padding: 22px 20px; border-radius: 18px;
  background: linear-gradient(160deg, color-mix(in srgb, var(--c) 30%, #0f172a), #0f172a 75%); border: 1px solid color-mix(in srgb, var(--c) 45%, transparent);
  transition: transform .15s, box-shadow .15s; }
.mb-q:hover { transform: translateY(-3px); box-shadow: 0 16px 34px -14px var(--c); }
.mb-q-i { font-size: 30px; color: var(--c); }
.mb-q-t { font-size: 20px; font-weight: 800; color: #fff; }
.mb-q-s { font-size: 13px; color: #94a3b8; }
.mb-warn { margin-top: 18px; padding: 12px 16px; border-radius: 12px; background: rgba(234,179,8,.12); border: 1px solid rgba(234,179,8,.35); color: #fde68a; }
.mb-grid { display: grid; grid-template-columns: minmax(320px, 420px) minmax(0, 1fr); gap: 16px; align-items: start; }
.mb-panel { background: rgba(15,23,42,.85); border: 1px solid rgba(148,163,184,.16); border-radius: 18px; padding: 18px; }
.mb-ring { --p: 0; width: 210px; height: 210px; margin: 6px auto 18px; border-radius: 50%; display: grid; place-items: center;
  background: conic-gradient(var(--c) calc(var(--p) * 1%), rgba(148,163,184,.15) 0); }
.mb-ring > div { width: 168px; height: 168px; border-radius: 50%; background: #0b1220; display: grid; place-items: center; align-content: center; }
.mb-ring b { font-size: 50px; font-weight: 900; color: #fff; line-height: 1; }
.mb-ring span { color: #94a3b8; font-size: 13px; margin-top: 4px; }
.mb-tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 18px; }
.mb-tile { background: rgba(255,255,255,.04); border: 1px solid rgba(148,163,184,.14); border-left: 3px solid var(--c); border-radius: 12px; padding: 10px 12px; }
.mb-tile b { display: block; font-size: 26px; font-weight: 800; color: #fff; line-height: 1.1; }
.mb-tile span { font-size: 12px; color: #94a3b8; }
.mb-sub-h { font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #94a3b8; margin: 4px 0 10px; display: flex; gap: 6px; align-items: center; }
.mb-dim { color: #64748b; font-size: 13px; }
.mb-bar { position: relative; display: flex; justify-content: space-between; padding: 9px 12px; border-radius: 10px; background: rgba(255,255,255,.04); margin-bottom: 6px; overflow: hidden; }
.mb-bar span, .mb-bar b { position: relative; z-index: 1; }
.mb-bar b { color: #4ade80; }
.mb-bar i { position: absolute; left: 0; top: 0; bottom: 0; background: rgba(34,197,94,.16); }
.mb-miss-h { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; font-size: 18px; font-weight: 700; color: #fff; }
.mb-big-red { font-size: 40px; font-weight: 900; color: #f87171; margin-right: 6px; }
.mb-search.ant-input-affix-wrapper { width: 280px; background: rgba(255,255,255,.06); border-color: rgba(148,163,184,.25); color: #fff; }
.mb-search input { background: transparent; color: #fff; }
.mb-groups { display: flex; flex-direction: column; gap: 14px; max-height: calc(100vh - 220px); overflow: auto; padding-right: 4px; }
.mb-full .mb-groups { max-height: calc(100vh - 170px); }
.mb-group-h { display: flex; gap: 8px; align-items: center; font-weight: 700; color: #fca5a5; margin-bottom: 8px; }
.mb-group-h span { margin-left: auto; background: rgba(239,68,68,.18); color: #fecaca; border-radius: 999px; padding: 0 10px; font-size: 13px; }
.mb-person { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 12px; background: rgba(239,68,68,.06); border: 1px solid rgba(239,68,68,.18); margin-bottom: 6px; }
.mb-person-n { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.mb-person-n b { font-size: 16px; color: #fff; }
.mb-person-n span { font-size: 12.5px; color: #94a3b8; }
.mb-safe.ant-btn { background: #16a34a !important; border: 0 !important; color: #fff !important; font-weight: 700; }
.mb-hurt.ant-btn { background: rgba(249,115,22,.18) !important; border: 1px solid rgba(249,115,22,.5) !important; color: #fdba74 !important; font-weight: 700; }
.mb-done { padding: 40px 20px; text-align: center; font-size: 20px; font-weight: 700; color: #4ade80; }
@media (max-width: 1000px) { .mb-grid { grid-template-columns: 1fr; } }
`;
