import React, { useMemo, useState, useEffect, useRef } from 'react';
import { Button, Alert, Skeleton, Tag, Avatar, Empty } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  SwapOutlined, ReloadOutlined, DesktopOutlined, WarningOutlined,
  FireOutlined, RightOutlined, LoginOutlined, LogoutOutlined,
  CheckCircleFilled, ThunderboltOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, RadialBarChart, RadialBar, PolarAngleAxis,
} from 'recharts';
import apiService from '../../services/api';

// ─── global styles (bento grid + animations) ─────────────────────────────────
const CSS_ID = 'apex-dash-styles';
if (!document.getElementById(CSS_ID)) {
  const s = document.createElement('style');
  s.id = CSS_ID;
  s.textContent = `
    @keyframes apex-fade-up { from { opacity:0; transform:translateY(16px);} to { opacity:1; transform:translateY(0);} }
    .apex-bento > * { animation: apex-fade-up .4s ease both; }
    @keyframes apex-pulse { 0%{box-shadow:0 0 0 0 rgba(34,197,94,.5);} 70%{box-shadow:0 0 0 8px rgba(34,197,94,0);} 100%{box-shadow:0 0 0 0 rgba(34,197,94,0);} }
    .apex-live { animation: apex-pulse 1.8s ease-out infinite; }

    .apex-bento { display:grid; grid-template-columns:repeat(12,1fr); gap:14px; }
    .apex-tile { background:rgba(255,255,255,.58); border-radius:22px; padding:18px;
      border:1px solid rgba(255,255,255,.65);
      -webkit-backdrop-filter:blur(20px) saturate(165%); backdrop-filter:blur(20px) saturate(165%);
      box-shadow:0 8px 32px rgba(15,23,42,.10), inset 0 1px 0 rgba(255,255,255,.55);
      position:relative; overflow:hidden;
      transition:transform .2s ease, box-shadow .2s ease; display:flex; flex-direction:column; }
    .apex-tile.click { cursor:pointer; }
    .apex-tile.click:hover { transform:translateY(-3px); box-shadow:0 12px 30px rgba(15,23,42,.12); }

    .t-hero   { grid-column:span 4; grid-row:span 2; }
    .t-kpi    { grid-column:span 2; }
    .t-trend  { grid-column:span 5; }
    .t-methods{ grid-column:span 3; }
    .t-24h    { grid-column:span 5; }
    .t-dev    { grid-column:span 3; }
    .t-comp   { grid-column:span 4; }
    .t-feed   { grid-column:span 8; }
    .t-emerg  { grid-column:span 4; }
    .t-loc    { grid-column:span 4; }
    .t-zone   { grid-column:span 4; }
    .t-net    { grid-column:span 4; }
    .t-stale  { grid-column:span 4; }

    .apex-blob { position:absolute; border-radius:50%; filter:blur(72px); opacity:.5; pointer-events:none; z-index:0; }
    .apex-blob-1 { width:380px; height:380px; top:-90px; left:-50px; background:radial-gradient(circle,#22d3ee,transparent 70%); }
    .apex-blob-2 { width:440px; height:440px; top:130px; right:-110px; background:radial-gradient(circle,#818cf8,transparent 70%); }
    .apex-blob-3 { width:360px; height:360px; bottom:-130px; left:32%; background:radial-gradient(circle,#f472b6,transparent 70%); opacity:.38; }

    @media (max-width:1200px){
      .apex-bento{ grid-template-columns:repeat(8,1fr); }
      .t-hero{grid-column:span 4;} .t-kpi{grid-column:span 2;}
      .t-trend,.t-24h,.t-feed{grid-column:span 8;}
      .t-methods,.t-dev,.t-comp,.t-emerg,.t-loc,.t-zone,.t-net,.t-stale{grid-column:span 4;}
    }
    @media (max-width:760px){
      .apex-bento{ grid-template-columns:1fr; }
      .apex-bento > *{ grid-column:1/-1 !important; grid-row:auto !important; }
    }
    .apex-scroll::-webkit-scrollbar{ width:5px; }
    .apex-scroll::-webkit-scrollbar-thumb{ background:#dbe2ea; border-radius:99px; }
    .apex-feed-row{ transition:background .15s; border-radius:12px; }
    .apex-feed-row:hover{ background:#f6f9fc; }
  `;
  document.head.appendChild(s);
}

// ─── count-up hook ────────────────────────────────────────────────────────────
function useCountUp(target, duration = 900) {
  const [val, setVal] = useState(0);
  const raf = useRef(); const t0 = useRef();
  useEffect(() => {
    const n = Number(target) || 0;
    if (n === 0) { setVal(0); return; }
    t0.current = performance.now();
    const tick = (now) => {
      const p = Math.min((now - t0.current) / duration, 1);
      const e = 1 - Math.pow(1 - p, 3);
      setVal(Math.round(e * n));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);
  return val;
}

// ─── helpers ────────────────────────────────────────────────────────────────
const PUNCH_META = {
  0: { label: 'Check In',  color: '#22c55e', icon: <LoginOutlined /> },
  1: { label: 'Check Out', color: '#3b82f6', icon: <LogoutOutlined /> },
  2: { label: 'Break Out', color: '#f59e0b', icon: <SwapOutlined /> },
  3: { label: 'Break In',  color: '#8b5cf6', icon: <SwapOutlined /> },
  255:{ label: 'Punch',    color: '#94a3b8', icon: <ThunderboltOutlined /> },
};
const punchMeta = s => PUNCH_META[s] ?? PUNCH_META[255];
const ZONE_BAR_COLORS = ['#0ea5e9', '#22c55e', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6'];

function relativeTime(iso) {
  if (!iso) return '—';
  const d = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (d < 60) return `${d}s ago`;
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

const fmtName = t =>
  (t.full_name || t.name || `${t.first_name || ''} ${t.last_name || ''}`.trim() || t.emp_code || '—');

function TileHead({ title, sub, action, navigate, path }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
      <div>
        <div style={{ fontWeight: 700, fontSize: 13.5, color: '#0f172a' }}>{title}</div>
        {sub && <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{sub}</div>}
      </div>
      {action || (path && (
        <span onClick={() => navigate(path)}
          style={{ fontSize: 11, color: '#6366f1', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}>
          View all <RightOutlined style={{ fontSize: 9 }} />
        </span>
      ))}
    </div>
  );
}

const chartTooltip = {
  contentStyle: { borderRadius: 12, border: 'none', boxShadow: '0 6px 20px rgba(15,23,42,.15)', fontSize: 12 },
  cursor: { fill: 'rgba(99,102,241,.06)' },
};

// ─── KPI tile ─────────────────────────────────────────────────────────────────
function Kpi({ label, value, icon, color, sub, subUp, path, navigate }) {
  const n = useCountUp(value);
  return (
    <div className={`apex-tile t-kpi ${path ? 'click' : ''}`} onClick={path ? () => navigate(path) : undefined}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{
          width: 40, height: 40, borderRadius: 12, background: `${color}1a`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', color, fontSize: 18,
        }}>{icon}</div>
        {sub !== undefined && sub !== null && (
          <span style={{ fontSize: 11, fontWeight: 700, color: subUp ? '#16a34a' : '#ef4444' }}>
            {subUp ? '▲' : '▼'} {Math.abs(sub)}
          </span>
        )}
      </div>
      <div style={{ fontSize: 30, fontWeight: 900, color: '#0f172a', lineHeight: 1.1, marginTop: 12 }}>{n}</div>
      <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.4px' }}>{label}</div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const navigate = useNavigate();
  const POLL = 30_000;

  const { data: pobRaw, isLoading: pobLoading, refetch: rPob } = useQuery({
    queryKey: ['dash-pob'], queryFn: () => apiService.get('/api/v1/pob-status/dashboard'),
    refetchInterval: POLL, refetchOnWindowFocus: false,
  });
  const { data: devRaw, isLoading: devLoading, refetch: rDev } = useQuery({
    queryKey: ['dash-devices'], queryFn: () => apiService.get('/api/device/terminals/'),
    refetchInterval: POLL, refetchOnWindowFocus: false,
  });
  const { data: persRaw } = useQuery({
    queryKey: ['dash-personnel'], queryFn: () => apiService.get('/api/v1/personnel/?page_size=1'),
    refetchInterval: 60_000, refetchOnWindowFocus: false,
  });
  const { data: txRaw, isLoading: txLoading, refetch: rTx } = useQuery({
    queryKey: ['dash-tx'], queryFn: () => apiService.get('/api/device/transactions/live/?limit=100'),
    refetchInterval: 15_000, refetchOnWindowFocus: false,
  });
  const { data: trendRaw } = useQuery({
    queryKey: ['dash-trend'], queryFn: () => apiService.get('/api/v1/pob-status/attendance-trend?days=30'),
    refetchInterval: 5 * 60_000, refetchOnWindowFocus: false,
  });
  const { data: methodRaw } = useQuery({
    queryKey: ['dash-methods'], queryFn: () => apiService.get('/api/v1/pob-status/verify-methods'),
    refetchInterval: POLL, refetchOnWindowFocus: false,
  });
  const { data: emergencyRaw } = useQuery({
    queryKey: ['dash-emergency'], queryFn: () => apiService.get('/api/emergency/metrics'),
    refetchInterval: POLL, refetchOnWindowFocus: false,
  });
  const { data: mtdRaw } = useQuery({
    queryKey: ['dash-mtd'], queryFn: () => apiService.get('/api/mtd/dashboard/compliance/'),
    refetchInterval: 5 * 60_000, refetchOnWindowFocus: false,
  });
  const { data: zonesRaw } = useQuery({
    queryKey: ['dash-zones'], queryFn: () => apiService.get('/api/v1/zones/dashboard'),
    refetchInterval: POLL, refetchOnWindowFocus: false,
  });
  const { data: lastActRaw } = useQuery({
    queryKey: ['dash-last-activity'], queryFn: () => apiService.get('/api/v1/pob-status/last-activity?limit=50'),
    refetchInterval: POLL, refetchOnWindowFocus: false,
  });

  const [alertDismissed, setAlertDismissed] = useState(false);

  // ── transforms ──
  const pob = pobRaw ?? {};
  // /api/device/terminals/ returns { data: [...], total } — not a bare array.
  const devices = Array.isArray(devRaw) ? devRaw : (devRaw?.data ?? []);
  const tx = txRaw?.data ?? [];
  const lastSeen = lastActRaw?.data ?? [];
  const totalPersonnel = pob.active_personnel ?? persRaw?.count ?? 0;   // active staff (leavers excluded)
  const online = devices.filter(d => d.state === 1 || d.status === 'online');
  const offline = devices.filter(d => d.state !== 1 && d.status !== 'online');

  const todayStr = new Date().toDateString();
  const todayTx = tx.filter(t => new Date(t.punch_time).toDateString() === todayStr);
  // People clocked in / out today, counted on the server the way attendance does
  // (site day, T&A readers, first tap = in, later tap = out).
  const todayIns = pob.checkins_today ?? 0;
  const todayOuts = pob.checkouts_today ?? 0;
  const inTrend = todayIns - (pob.checkins_yesterday ?? 0);
  const outTrend = todayOuts - (pob.checkouts_yesterday ?? 0);

  const offCount = pob.offshore_count ?? 0;
  const onCount = pob.onshore_count ?? 0;
  const trCount = pob.transit_count ?? 0;

  // POB donut
  const pobDonut = [
    { name: 'Offshore', value: offCount, color: '#0ea5e9' },
    { name: 'Onshore', value: onCount, color: '#22c55e' },
    { name: 'Transit', value: trCount, color: '#f59e0b' },
  ];

  // 24h hourly in/out (grouped bars)
  const hourly = useMemo(() => {
    const h = {};
    todayTx.forEach(t => {
      const k = `${String(new Date(t.punch_time).getHours()).padStart(2, '0')}h`;
      if (!h[k]) h[k] = { time: k, In: 0, Out: 0 };
      t.punch_state === 1 ? h[k].Out++ : h[k].In++;
    });
    return Object.values(h).sort((a, b) => a.time.localeCompare(b.time));
  }, [tx]);

  // 30-day trend (gradient area)
  const trend30 = useMemo(() => {
    const raw = trendRaw?.trend ?? [];
    return raw.map(({ day, check_ins, check_outs }) => ({
      day: new Date(day).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      checkIn: check_ins ?? 0, checkOut: check_outs ?? 0,
    }));
  }, [trendRaw]);

  // verify methods
  const METHOD_COLORS = { Face: '#6366f1', Fingerprint: '#06b6d4', Card: '#ec4899', Password: '#f59e0b' };
  const methods = (methodRaw?.methods ?? []).map(m => ({
    name: m.type, value: m.count, color: METHOD_COLORS[m.type] ?? '#94a3b8',
  }));
  const methodsTotal = methods.reduce((s, m) => s + m.value, 0);

  // device donut
  const deviceDonut = [
    { name: 'Online', value: online.length, color: '#22c55e' },
    { name: 'Offline', value: offline.length, color: '#ef4444' },
  ];

  // emergency
  const em = emergencyRaw ?? {};
  const emActive = em.active_events ?? 0;
  const emResolved = em.resolved_events ?? 0;
  const emTotal = em.total_events ?? 0;
  const emRate = em.resolution_rate ?? 0;

  // compliance
  const mtdData = mtdRaw?.data ?? {};
  const mtdRate = mtdData.compliance_rate ?? 0;
  const mtdCompliant = mtdData.compliant_count ?? 0;
  const mtdNonComp = mtdData.non_compliant_count ?? 0;
  const mtdCats = useMemo(() => {
    const list = mtdData.non_compliant_list ?? [];
    const c = { med: 0, cert: 0, ppe: 0 };
    list.forEach(p => (p.missing_items ?? []).forEach(i => {
      if (i.includes('Medical')) c.med++;
      else if (i.includes('Expired')) c.cert++;
      else if (i.includes('PPE')) c.ppe++;
    }));
    return [
      { label: 'Compliant', count: mtdCompliant, color: '#22c55e' },
      { label: 'Medical', count: c.med, color: '#ef4444' },
      { label: 'Expired Certs', count: c.cert, color: '#f59e0b' },
      { label: 'Overdue PPE', count: c.ppe, color: '#8b5cf6' },
    ];
  }, [mtdData]);

  // Personnel by location
  const byLocation = pob.by_location ?? {};
  const locationData = Object.entries(byLocation)
    .map(([name, value]) => ({ name, value: Number(value) || 0 }))
    .filter(d => d.value > 0).sort((a, b) => b.value - a.value).slice(0, 6);

  // Zone occupancy (live count per zone)
  const zoneList = Array.isArray(zonesRaw) ? zonesRaw : (zonesRaw?.data ?? []);
  const zoneData = zoneList
    .map(z => ({ name: z.name, value: z.current_personnel_count ?? z.current_occupancy ?? 0 }))
    .filter(d => d.value > 0).sort((a, b) => b.value - a.value).slice(0, 6);

  // Cumulative net on-site through the day (entries − exits)
  const netSeries = useMemo(() => {
    const byHour = {};
    todayTx.forEach(t => {
      const h = new Date(t.punch_time).getHours();
      byHour[h] = (byHour[h] || 0) + (t.punch_state === 1 ? -1 : 1);
    });
    let cum = 0; const r = []; const nowH = new Date().getHours();
    for (let h = 0; h <= nowH; h++) { cum += (byHour[h] || 0); r.push({ time: `${String(h).padStart(2, '0')}h`, net: Math.max(cum, 0) }); }
    return r;
  }, [tx]);

  const totalPob = offCount + onCount + trCount;
  const offlineNames = offline.map(d => (d.alias || d.sn || '').trim()).filter(Boolean).join(', ');
  const refresh = () => { rPob(); rDev(); rTx(); };

  const heroCount = useCountUp(totalPob);

  return (
    <div style={{ position: 'relative', overflow: 'hidden', minHeight: '100vh', padding: '18px 22px',
      background: 'linear-gradient(180deg,#e7edf5 0%,#eef2f8 45%,#f3eef9 100%)' }}>
      {/* decorative colour blobs — give the frosted-glass tiles something to blur */}
      <div className="apex-blob apex-blob-1" />
      <div className="apex-blob apex-blob-2" />
      <div className="apex-blob apex-blob-3" />
      <div style={{ position: 'relative', zIndex: 1 }}>
      {/* offline banner */}
      {!devLoading && offline.length > 0 && !alertDismissed && (
        <Alert type="warning" showIcon icon={<WarningOutlined />} closable
          onClose={() => setAlertDismissed(true)}
          message={<span style={{ fontWeight: 700, fontSize: 13 }}>
            {offline.length} reader{offline.length > 1 ? 's' : ''} offline — {offlineNames}
          </span>}
          action={<span style={{ color: '#6366f1', cursor: 'pointer', fontWeight: 700, fontSize: 12 }}
            onClick={() => navigate('/devices')}>View →</span>}
          style={{ marginBottom: 14, borderRadius: 14, border: '1px solid #fde68a' }}
        />
      )}

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 900, color: '#0f172a', letterSpacing: '-0.4px' }}>
            Operations Overview
          </h1>
          <div style={{ fontSize: 12, color: '#94a3b8' }}>
            Live personnel, access & safety · updated {new Date().toLocaleTimeString()}
          </div>
        </div>
        <Button icon={<ReloadOutlined />} shape="round" onClick={refresh}
          style={{ fontWeight: 600 }}>Refresh</Button>
      </div>

      <div className="apex-bento">
        {/* ── HERO: Personnel On Board ── */}
        <div className="apex-tile t-hero" style={{ background: 'linear-gradient(135deg,#0f2740 0%,#1a3a5c 60%,#13558a 100%)', color: '#fff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: 13, fontWeight: 700, opacity: .85, letterSpacing: '.3px' }}>PERSONNEL ON BOARD</div>
            <Tag color="rgba(255,255,255,.15)" style={{ border: 'none', color: '#fff', borderRadius: 8, fontWeight: 700 }}>
              <span className="apex-live" style={{ display: 'inline-block', width: 7, height: 7, borderRadius: 99, background: '#22c55e', marginRight: 6 }} />LIVE
            </Tag>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
            <div style={{ flex: '0 0 150px', height: 150, position: 'relative' }}>
              {pobLoading ? <Skeleton.Avatar active size={120} shape="circle" /> : (
                <>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pobDonut.filter(d => d.value > 0)} dataKey="value" nameKey="name"
                        innerRadius={48} outerRadius={68} paddingAngle={3} stroke="none">
                        {pobDonut.map((d, i) => <Cell key={i} fill={d.color} />)}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ fontSize: 34, fontWeight: 900, lineHeight: 1 }}>{heroCount}</div>
                    <div style={{ fontSize: 10, opacity: .7, letterSpacing: '.5px' }}>ON BOARD</div>
                  </div>
                </>
              )}
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {pobDonut.map(d => (
                <div key={d.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, opacity: .9 }}>
                    <span style={{ width: 9, height: 9, borderRadius: 3, background: d.color }} />{d.name}
                  </span>
                  <span style={{ fontWeight: 800, fontSize: 15 }}>{d.value}</span>
                </div>
              ))}
              <div style={{ borderTop: '1px solid rgba(255,255,255,.12)', paddingTop: 8, marginTop: 2, display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ opacity: .8 }}>Total workforce</span>
                <span style={{ fontWeight: 800 }}>{totalPersonnel}</span>
              </div>
            </div>
          </div>
          {/* today flow strip — fills the tall hero with useful at-a-glance numbers */}
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            {[
              { l: 'Today In', v: todayIns, c: '#34d399' },
              { l: 'Today Out', v: todayOuts, c: '#60a5fa' },
              { l: 'On Board Now', v: pob.total ?? 0, c: '#fbbf24' },
            ].map(s => (
              <div key={s.l} style={{ flex: 1, background: 'rgba(255,255,255,0.08)', borderRadius: 12, padding: '9px 6px', textAlign: 'center' }}>
                <div style={{ fontSize: 19, fontWeight: 900, color: s.c }}>{s.v}</div>
                <div style={{ fontSize: 9, opacity: .65, letterSpacing: '.4px' }}>{s.l.toUpperCase()}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── KPI tiles ── */}
        <Kpi label="Today In" value={todayIns} icon={<LoginOutlined />} color="#22c55e" sub={inTrend} subUp={inTrend >= 0} navigate={navigate} />
        <Kpi label="Today Out" value={todayOuts} icon={<LogoutOutlined />} color="#3b82f6" sub={outTrend} subUp={outTrend >= 0} navigate={navigate} />
        <Kpi label="Online Readers" value={online.length} icon={<DesktopOutlined />} color="#0ea5e9" path="/devices" navigate={navigate} />
        <Kpi label="Active Alarms" value={emActive} icon={<FireOutlined />} color={emActive ? '#ef4444' : '#22c55e'} path="/emergency" navigate={navigate} />

        {/* ── 30-day trend (gradient area) ── */}
        <div className="apex-tile t-trend">
          <TileHead title="Attendance Trend" sub="Check-ins vs check-outs · last 30 days" navigate={navigate} path="/attendance" />
          <div style={{ flex: 1, minHeight: 200 }}>
            {trend30.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No data" style={{ marginTop: 50 }} /> : (
              <ResponsiveContainer width="100%" height={210}>
                <BarChart data={trend30} margin={{ top: 6, right: 8, left: -18, bottom: 0 }} barGap={2}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={24} />
                  <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} width={34} />
                  <Tooltip {...chartTooltip} />
                  <Bar dataKey="checkIn" name="Check In" fill="#22c55e" radius={[3, 3, 0, 0]} maxBarSize={14} />
                  <Bar dataKey="checkOut" name="Check Out" fill="#3b82f6" radius={[3, 3, 0, 0]} maxBarSize={14} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* ── Verify methods donut ── */}
        <div className="apex-tile t-methods">
          <TileHead title="Verification Methods" sub="How people authenticate" />
          {methodsTotal === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No data" style={{ marginTop: 40 }} /> : (
            <div style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
              <div style={{ width: 130, height: 150, position: 'relative' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={methods} dataKey="value" nameKey="name" innerRadius={44} outerRadius={62} paddingAngle={3} stroke="none">
                      {methods.map((d, i) => <Cell key={i} fill={d.color} />)}
                    </Pie>
                    <Tooltip {...chartTooltip} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <div style={{ fontSize: 22, fontWeight: 900, color: '#0f172a' }}>{methodsTotal}</div>
                  <div style={{ fontSize: 9, color: '#94a3b8' }}>EVENTS</div>
                </div>
              </div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {methods.map(m => (
                  <div key={m.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 7, color: '#475569' }}>
                      <span style={{ width: 8, height: 8, borderRadius: 3, background: m.color }} />{m.name}
                    </span>
                    <b style={{ color: '#0f172a' }}>{m.value}</b>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── 24h activity (grouped bars) ── */}
        <div className="apex-tile t-24h">
          <TileHead title="Today's Activity" sub="Hourly entries & exits" />
          <div style={{ flex: 1, minHeight: 190 }}>
            {hourly.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No activity yet today" style={{ marginTop: 46 }} /> : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={hourly} margin={{ top: 6, right: 8, left: -18, bottom: 0 }} barGap={2}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} width={28} allowDecimals={false} />
                  <Tooltip {...chartTooltip} />
                  <Bar dataKey="In" fill="#22c55e" radius={[4, 4, 0, 0]} maxBarSize={16} />
                  <Bar dataKey="Out" fill="#3b82f6" radius={[4, 4, 0, 0]} maxBarSize={16} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* ── Device status ── */}
        <div className="apex-tile t-dev click" onClick={() => navigate('/devices')}>
          <TileHead title="Reader Status" sub={`${devices.length} total devices`} />
          <div style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
            <div style={{ width: 120, height: 140, position: 'relative' }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={deviceDonut.filter(d => d.value > 0)} dataKey="value" nameKey="name" innerRadius={42} outerRadius={60} paddingAngle={3} stroke="none">
                    {deviceDonut.map((d, i) => <Cell key={i} fill={d.color} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 900, color: '#22c55e' }}>{online.length}</div>
                <div style={{ fontSize: 9, color: '#94a3b8' }}>ONLINE</div>
              </div>
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12.5 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7, color: '#475569' }}>
                  <span style={{ width: 9, height: 9, borderRadius: 3, background: '#22c55e' }} />Online</span>
                <b style={{ color: '#0f172a' }}>{online.length}</b>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12.5 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7, color: '#475569' }}>
                  <span style={{ width: 9, height: 9, borderRadius: 3, background: '#ef4444' }} />Offline</span>
                <b style={{ color: '#0f172a' }}>{offline.length}</b>
              </div>
            </div>
          </div>
        </div>

        {/* ── Compliance ── */}
        <div className="apex-tile t-comp click" onClick={() => navigate('/personnel')}>
          <TileHead title="Workforce Compliance" sub="Medical · Certs · PPE readiness" />
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flex: 1 }}>
            <div style={{ width: 120, height: 120, position: 'relative', flexShrink: 0 }}>
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart innerRadius="72%" outerRadius="100%" data={[{ value: mtdRate, fill: mtdRate >= 90 ? '#22c55e' : mtdRate >= 70 ? '#f59e0b' : '#ef4444' }]} startAngle={90} endAngle={-270}>
                  <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                  <RadialBar dataKey="value" cornerRadius={20} background={{ fill: '#eef2f7' }} />
                </RadialBarChart>
              </ResponsiveContainer>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 900, color: '#0f172a' }}>{Math.round(mtdRate)}%</div>
                <div style={{ fontSize: 9, color: '#94a3b8' }}>READY</div>
              </div>
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 9 }}>
              {mtdCats.map(c => (
                <div key={c.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 7, color: '#475569' }}>
                    <span style={{ width: 8, height: 8, borderRadius: 3, background: c.color }} />{c.label}
                  </span>
                  <b style={{ color: '#0f172a' }}>{c.count}</b>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Live activity feed ── */}
        <div className="apex-tile t-feed">
          <TileHead title="Live Activity" sub="Most recent badge events" navigate={navigate} path="/attendance" />
          <div className="apex-scroll" style={{ flex: 1, overflowY: 'auto', maxHeight: 340 }}>
            {txLoading ? Array.from({ length: 5 }).map((_, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, padding: '8px 6px', alignItems: 'center' }}>
                <Skeleton.Avatar active size={34} /><Skeleton active paragraph={false} title={{ width: '50%' }} />
              </div>
            )) : tx.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No recent events" style={{ marginTop: 60 }} /> : (
              tx.slice(0, 30).map((t, i) => {
                const m = punchMeta(t.punch_state);
                return (
                  <div key={i} className="apex-feed-row" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 8px' }}>
                    <Avatar size={36} src={t.photo_url} style={{ background: `${m.color}1a`, color: m.color, flexShrink: 0 }}>
                      {(fmtName(t)[0] || '?').toUpperCase()}
                    </Avatar>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#0f172a', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{fmtName(t)}</div>
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>{t.terminal_alias || t.terminal_sn || t.device_sn || 'Reader'}</div>
                    </div>
                    <Tag style={{ border: 'none', background: `${m.color}1a`, color: m.color, borderRadius: 8, fontWeight: 700, margin: 0 }}>
                      {m.icon} {m.label}
                    </Tag>
                    <div style={{ fontSize: 11, color: '#cbd5e1', width: 60, textAlign: 'right', flexShrink: 0 }}>{relativeTime(t.punch_time)}</div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ── Longest since last seen (early missing-person signal) ── */}
        <div className="apex-tile t-stale click" onClick={() => navigate('/pob-status')}>
          <TileHead title="Longest Since Last Seen" sub="On-site · idle 2h+ flagged" navigate={navigate} path="/pob-status" />
          <div className="apex-scroll" style={{ flex: 1, overflowY: 'auto', maxHeight: 340 }}>
            {lastSeen.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No on-site personnel" style={{ marginTop: 60 }} /> : (
              lastSeen.slice(0, 20).map((r, i) => {
                const col = r.stale ? '#dc2626' : '#64748b';
                return (
                  <div key={r.id || i} className="apex-feed-row" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 8px' }}>
                    <Avatar size={36} src={r.photo_url} style={{ background: `${col}1a`, color: col, flexShrink: 0 }}>
                      {(r.name?.[0] || '?').toUpperCase()}
                    </Avatar>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#0f172a', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.name}</div>
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>{r.location}{r.department && r.department !== '—' ? ` · ${r.department}` : ''}</div>
                    </div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: col, width: 82, textAlign: 'right', flexShrink: 0 }}>
                      {r.never_seen ? 'never seen' : relativeTime(r.last_event)}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ── Emergency / safety ── */}
        <div className="apex-tile t-emerg click" onClick={() => navigate('/emergency')}
          style={emActive ? { background: 'linear-gradient(135deg,#7f1d1d,#b91c1c)', color: '#fff' } : {}}>
          <TileHead title={<span style={emActive ? { color: '#fff' } : {}}>Emergency & Safety</span>}
            sub={emActive ? null : 'All systems normal'} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flex: 1 }}>
            <div style={{ width: 110, height: 110, position: 'relative', flexShrink: 0 }}>
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart innerRadius="72%" outerRadius="100%" data={[{ value: emRate, fill: emActive ? '#fca5a5' : '#22c55e' }]} startAngle={90} endAngle={-270}>
                  <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                  <RadialBar dataKey="value" cornerRadius={20} background={{ fill: emActive ? 'rgba(255,255,255,.18)' : '#eef2f7' }} />
                </RadialBarChart>
              </ResponsiveContainer>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 900, color: emActive ? '#fff' : '#0f172a' }}>{Math.round(emRate)}%</div>
                <div style={{ fontSize: 9, opacity: .7, color: emActive ? '#fff' : '#94a3b8' }}>RESOLVED</div>
              </div>
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, opacity: emActive ? .95 : 1 }}>
                <span style={{ color: emActive ? 'rgba(255,255,255,.85)' : '#475569' }}>Active</span>
                <b style={{ color: emActive ? '#fff' : '#ef4444' }}>{emActive}</b>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
                <span style={{ color: emActive ? 'rgba(255,255,255,.85)' : '#475569' }}>Resolved</span>
                <b style={{ color: emActive ? '#fff' : '#0f172a' }}>{emResolved}</b>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
                <span style={{ color: emActive ? 'rgba(255,255,255,.85)' : '#475569' }}>Total events</span>
                <b style={{ color: emActive ? '#fff' : '#0f172a' }}>{emTotal}</b>
              </div>
              {!emActive && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#16a34a', fontWeight: 700, marginTop: 2 }}>
                  <CheckCircleFilled /> No active alarms
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Personnel by Location ── */}
        <div className="apex-tile t-loc">
          <TileHead title="Personnel by Location" sub="Distribution across sites" navigate={navigate} path="/personnel" />
          <div style={{ flex: 1, minHeight: 200 }}>
            {locationData.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No data" style={{ marginTop: 48 }} /> : (
              <ResponsiveContainer width="100%" height={Math.max(200, locationData.length * 34)}>
                <BarChart data={locationData} layout="vertical" margin={{ top: 4, right: 18, left: 6, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#475569' }} axisLine={false} tickLine={false} width={94} />
                  <Tooltip {...chartTooltip} />
                  <Bar dataKey="value" fill="#6366f1" radius={[0, 6, 6, 0]} maxBarSize={18} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* ── Zone Occupancy ── */}
        <div className="apex-tile t-zone click" onClick={() => navigate('/zones')}>
          <TileHead title="Zone Occupancy" sub="Live headcount per zone" navigate={navigate} path="/zones" />
          <div style={{ flex: 1, minHeight: 200 }}>
            {zoneData.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No one in a zone yet" style={{ marginTop: 48 }} /> : (
              <ResponsiveContainer width="100%" height={Math.max(200, zoneData.length * 34)}>
                <BarChart data={zoneData} layout="vertical" margin={{ top: 4, right: 18, left: 6, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#475569' }} axisLine={false} tickLine={false} width={94} />
                  <Tooltip {...chartTooltip} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={18}>
                    {zoneData.map((d, i) => <Cell key={i} fill={ZONE_BAR_COLORS[i % ZONE_BAR_COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* ── Net On-Site Today ── */}
        <div className="apex-tile t-net">
          <TileHead title="Net On-Site Today" sub="Cumulative entries − exits" />
          <div style={{ flex: 1, minHeight: 200 }}>
            {netSeries.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No activity yet today" style={{ marginTop: 48 }} /> : (
              <ResponsiveContainer width="100%" height={210}>
                <AreaChart data={netSeries} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gNet" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} minTickGap={20} />
                  <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} width={28} allowDecimals={false} />
                  <Tooltip {...chartTooltip} />
                  <Area type="monotone" dataKey="net" name="On site" stroke="#6366f1" strokeWidth={2.5} fill="url(#gNet)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}
