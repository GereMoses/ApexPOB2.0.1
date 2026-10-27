import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  App, Tabs, Row, Col, Button, Modal, Form, Input, Select, Table, Tag, Progress,
  Space, Popconfirm, Card, Spin, Checkbox, DatePicker, InputNumber, Tooltip, Divider, Radio,
} from 'antd';
import {
  TeamOutlined, UserOutlined, ClockCircleOutlined, EnvironmentOutlined,
  CalendarOutlined, FileTextOutlined, PlayCircleOutlined, StopOutlined,
  CheckCircleOutlined, CloseCircleOutlined, WarningOutlined, ReloadOutlined,
  PlusOutlined, EditOutlined, DeleteOutlined, ThunderboltOutlined,
  AlertOutlined, FireOutlined, AimOutlined, ScanOutlined, LockOutlined,
  UnlockOutlined, DashboardOutlined, BarChartOutlined, DownloadOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService from '../../services/api';
import MusteringLiveMap from './MusteringLiveMap';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
dayjs.extend(relativeTime);

const { TextArea } = Input;
const { RangePicker } = DatePicker;

/* ── Constants ────────────────────────────────────────────────── */

const EVENT_TYPES = [
  { value: 0, label: 'Real Emergency', tag: 'error',   icon: <AlertOutlined /> },
  { value: 1, label: 'Drill',          tag: 'blue',    icon: <AimOutlined />   },
  { value: 2, label: 'Fire',           tag: 'orange',  icon: <FireOutlined />  },
  { value: 3, label: 'Gas Leak',       tag: 'gold',    icon: <WarningOutlined /> },
  { value: 4, label: 'Man Down',       tag: 'purple',  icon: <UserOutlined />  },
];

const ZONE_TYPES = [
  { value: 0, label: 'Assembly Point' },
  { value: 1, label: 'Safe Room' },
  { value: 2, label: 'Hospital' },
];

const DEPT_COLORS = ['#1890ff','#722ed1','#52c41a','#fa8c16','#f5222d','#08979c','#7c3aed','#389e0d','#d48806','#c41d7f'];

const fmtTime  = (v) => v ? dayjs(v).format('DD MMM YYYY HH:mm') : '—';
const fmtShort = (v) => v ? dayjs(v).format('HH:mm:ss') : '—';

const elapsedStr = (t) => {
  if (!t) return '00:00:00';
  const s = Math.max(0, dayjs().diff(dayjs(t), 'second'));
  return [Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60]
    .map(n => String(n).padStart(2, '0')).join(':');
};

const evTypeMeta = (v) => EVENT_TYPES.find(t => t.value === v) ?? EVENT_TYPES[0];

const downloadEventReport = (eventId, fmt = 'excel') => {
  // Canonical token key is 'token' (see services/api.js getAuthToken) — the old
  // 'auth_token' lookup was always empty, so every export 401'd and silently failed.
  const token = localStorage.getItem('token') || localStorage.getItem('authToken') || localStorage.getItem('access_token') || '';
  const url = `/api/mustering/events/${eventId}/export/?format=${fmt}`;
  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then(r => {
      if (!r.ok) throw new Error('Export failed');
      const cd = r.headers.get('Content-Disposition') || '';
      const match = cd.match(/filename="([^"]+)"/);
      const filename = match ? match[1] : `muster_${eventId}.${fmt === 'excel' ? 'xlsx' : 'csv'}`;
      return r.blob().then(blob => ({ blob, filename }));
    })
    .then(({ blob, filename }) => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    })
    .catch(err => console.error('Download error:', err));
};

/* ── Shared UI pieces ─────────────────────────────────────────── */

const StatCard = ({ label, value, icon, color, sub, onClick }) => (
  <Card
    size="small"
    styles={{ body: { padding: '16px 20px' } }}
    style={{ borderTop: `3px solid ${color}`, cursor: onClick ? 'pointer' : 'default', height: '100%' }}
    hoverable={!!onClick}
    onClick={onClick}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      <div style={{ width: 44, height: 44, borderRadius: 10, background: `${color}15`, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {React.cloneElement(icon, { style: { fontSize: 20, color } })}
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, whiteSpace: 'nowrap' }}>{label}</div>
        <div style={{ fontSize: 26, fontWeight: 800, color: '#141414', lineHeight: 1.2 }}>{value}</div>
        {sub && <div style={{ fontSize: 11, color: '#bfbfbf', marginTop: 1 }}>{sub}</div>}
      </div>
    </div>
  </Card>
);

const EvTypeBadge = ({ type }) => {
  const m = evTypeMeta(type);
  return <Tag icon={m.icon} color={m.tag} style={{ borderRadius: 4, fontSize: 11 }}>{m.label}</Tag>;
};

const CircleProgress = ({ percent, size = 80 }) => {
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - Math.min(100, Math.max(0, percent)) / 100);
  const color = percent >= 80 ? '#4ade80' : percent >= 50 ? '#facc15' : '#f87171';
  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth={7} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={7}
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 0.6s ease, stroke 0.4s ease' }} />
    </svg>
  );
};

const EvStatusBadge = ({ status }) => {
  const cfg = { 0: ['error', 'Active'], 1: ['success', 'Completed'], 2: ['default', 'Cancelled'] };
  const [color, label] = cfg[status] ?? cfg[2];
  return <Tag color={color} style={{ borderRadius: 4, fontSize: 11 }}>{label}</Tag>;
};

const PersonChip = ({ status }) => {
  const cfg = { 0: ['error', 'Not Found'], 1: ['success', 'Found'], 2: ['warning', 'Injured'] };
  const [color, label] = cfg[status] ?? cfg[0];
  return <Tag color={color} style={{ borderRadius: 4, fontSize: 11 }}>{label}</Tag>;
};

const SectionTitle = ({ icon, children, extra }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 14, color: '#141414' }}>
      {icon}{children}
    </div>
    {extra}
  </div>
);

const ModalHeader = ({ icon, title, sub, color }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
    <div style={{ width: 36, height: 36, borderRadius: 8, background: `${color}15`, border: `1px solid ${color}30`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      {React.cloneElement(icon, { style: { color, fontSize: 16 } })}
    </div>
    <div>
      <div style={{ fontWeight: 700, fontSize: 15, color: '#141414' }}>{title}</div>
      {sub && <div style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 400 }}>{sub}</div>}
    </div>
  </div>
);

/* Full CSS ring stat — matches the reference design */
const RingStat = ({ label, value, color, pulse }) => (
  <Card styles={{ body: { padding: '22px 16px', textAlign: 'center' } }} style={{ height: '100%' }}>
    <div style={{
      width: 112, height: 112, borderRadius: '50%',
      border: `10px solid ${color}`,
      background: `radial-gradient(circle at 40% 35%, ${color}10 0%, white 70%)`,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      margin: '0 auto',
      boxShadow: `0 0 0 4px ${color}18, 0 6px 24px ${color}25`,
      position: 'relative',
    }}>
      {pulse && (
        <span style={{
          position: 'absolute', top: -4, right: -4,
          width: 14, height: 14, borderRadius: '50%', background: color,
          boxShadow: `0 0 0 3px ${color}30`,
          animation: 'msPulse 1.4s infinite',
        }} />
      )}
      <div style={{ fontSize: 38, fontWeight: 900, color, lineHeight: 1, letterSpacing: '-1px' }}>{value ?? '—'}</div>
    </div>
    <div style={{ marginTop: 12, fontWeight: 700, fontSize: 12, color: '#262626', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
  </Card>
);

/* Person list card — left panel quick view */
const PersonListCard = ({ person, onMark, marking }) => {
  const colors = { 0: { bg: '#fff1f0', border: '#f5222d', text: '#cf1322' }, 1: { bg: '#f6ffed', border: '#52c41a', text: '#389e0d' }, 2: { bg: '#fffbe6', border: '#faad14', text: '#d46b08' } };
  const c = colors[person.status] ?? colors[0];
  return (
    <div style={{
      padding: '10px 14px', borderBottom: '1px solid rgba(0,0,0,0.04)',
      background: c.bg, borderLeft: `3px solid ${c.border}`,
      transition: 'background 0.15s',
    }}>
      <div style={{ fontWeight: 700, fontSize: 13, color: '#141414', marginBottom: 1 }}>{person.emp_name || person.emp_code}</div>
      <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 4 }}>{person.dept_name || '—'}</div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: c.text, textTransform: 'uppercase', letterSpacing: 0.3 }}>
          {person.status === 0 ? 'Not Found' : person.status === 1 ? 'Found' : 'Injured'}
        </span>
        {person.status !== 1 && (
          <button onClick={() => onMark(person.emp_code, 1)}
            style={{ fontSize: 10, padding: '2px 8px', background: '#52c41a', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>
            Found
          </button>
        )}
      </div>
    </div>
  );
};

/* ── Elapsed Timer Hook ───────────────────────────────────────── */
const useElapsed = (startTime, active) => {
  const [elapsed, setElapsed] = useState('00:00:00');
  useEffect(() => {
    if (!startTime || !active) { setElapsed('00:00:00'); return; }
    setElapsed(elapsedStr(startTime));
    const id = setInterval(() => setElapsed(elapsedStr(startTime)), 1000);
    return () => clearInterval(id);
  }, [startTime, active]);
  return elapsed;
};

/* ── Dept Rollup ──────────────────────────────────────────────── */
const buildDeptRollup = (logs) => {
  const map = {};
  for (const l of logs) {
    const d = l.dept_name || 'Unassigned';
    if (!map[d]) map[d] = { dept: d, safe: 0, missing: 0, injured: 0 };
    if (l.status === 1) map[d].safe++;
    else if (l.status === 0) map[d].missing++;
    else map[d].injured++;
  }
  return Object.values(map).sort((a, b) => b.missing - a.missing);
};

/* ── Zone Topology Map (SVG) ──────────────────────────────────── */
const VW = 1000, VH = 560, NW = 134, NH = 78;

const ZoneMapCanvas = ({ zones, allLogs, editMode, connectFrom, setConnectFrom, onPositionChange, onConnectionToggle }) => {
  const svgRef = useRef(null);
  const [dragging, setDragging] = useState(null);

  const zoneStats = React.useMemo(() => {
    const m = {};
    for (const z of zones) m[z.id] = { total: 0, found: 0, missing: 0, injured: 0 };
    for (const l of allLogs) {
      // Match by zone name (last_punch_area = zone name at event start)
      const z = zones.find(z => z.name && l.last_punch_area && z.name === l.last_punch_area);
      if (z) {
        m[z.id].total++;
        if (l.status === 1) m[z.id].found++;
        else if (l.status === 0) m[z.id].missing++;
        else m[z.id].injured++;
      }
    }
    return m;
  }, [zones, allLogs]);

  const getPos = (zone, idx) => {
    if (zone.map_x != null && zone.map_y != null) return { x: zone.map_x, y: zone.map_y };
    const total = zones.length;
    const cols = Math.max(2, Math.ceil(Math.sqrt(total)));
    const rows = Math.ceil(total / cols);
    const col = idx % cols;
    const row = Math.floor(idx / cols);
    return {
      x: 120 + col * ((VW - 240) / Math.max(cols - 1, 1)),
      y: 110 + row * ((VH - 200) / Math.max(rows - 1, 1)),
    };
  };

  const getConns = (zone) => { try { return JSON.parse(zone.map_connections || '[]'); } catch { return []; } };

  const getSvgPt = (e) => {
    const svg = svgRef.current;
    if (!svg) return { x: VW / 2, y: VH / 2 };
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  };

  const handleMouseDown = (e, zone) => {
    if (!editMode || connectFrom) return;
    e.stopPropagation(); e.preventDefault();
    const pt = getSvgPt(e);
    const pos = getPos(zone, zones.indexOf(zone));
    setDragging({ id: zone.id, ox: pt.x - pos.x, oy: pt.y - pos.y });
  };

  const handleMouseMove = (e) => {
    if (!dragging) return;
    const pt = getSvgPt(e);
    const nx = Math.max(NW / 2 + 10, Math.min(VW - NW / 2 - 10, pt.x - dragging.ox));
    const ny = Math.max(NH / 2 + 10, Math.min(VH - NH / 2 - 10, pt.y - dragging.oy));
    onPositionChange(dragging.id, nx, ny);
  };

  const handleMouseUp = () => setDragging(null);

  const handleZoneClick = (zone) => {
    if (!editMode || !connectFrom) return;
    if (connectFrom === -1) { setConnectFrom(zone.id); return; }
    if (connectFrom === zone.id) { setConnectFrom(null); return; }
    onConnectionToggle(connectFrom, zone.id);
    setConnectFrom(null);
  };

  return (
    <svg ref={svgRef} viewBox={`0 0 ${VW} ${VH}`}
      style={{ width: '100%', height: '100%', display: 'block', background: editMode ? '#eef2f7' : '#f8fafc' }}
      onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}>

      <defs>
        <filter id="msRedGlow" x="-25%" y="-25%" width="150%" height="150%">
          <feDropShadow dx="0" dy="0" stdDeviation="7" floodColor="#f5222d" floodOpacity="0.45" />
        </filter>
        <filter id="msGreenGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="4" floodColor="#52c41a" floodOpacity="0.22" />
        </filter>
      </defs>

      {/* Grid overlay in edit mode */}
      {editMode && Array.from({ length: 9 }, (_, i) => (i + 1) * 100).map(v => (
        <g key={v} opacity="0.18">
          <line x1={0} y1={v} x2={VW} y2={v} stroke="#64748b" strokeWidth="1" strokeDasharray="5,5" />
          <line x1={v} y1={0} x2={v} y2={VH} stroke="#64748b" strokeWidth="1" strokeDasharray="5,5" />
        </g>
      ))}

      {/* Connection lines */}
      {zones.flatMap((zone, idx) => {
        const conns = getConns(zone);
        const from = getPos(zone, idx);
        return conns.filter(toId => toId > zone.id).map(toId => {
          const toIdx = zones.findIndex(z => z.id === toId);
          if (toIdx < 0) return null;
          const to = getPos(zones[toIdx], toIdx);
          return (
            <line key={`c${zone.id}-${toId}`}
              x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke={editMode ? '#93c5fd' : '#b0bec5'} strokeWidth="3"
              strokeDasharray={editMode ? '10,6' : undefined} strokeLinecap="round" />
          );
        });
      })}

      {/* Zone nodes */}
      {zones.map((zone, idx) => {
        const pos = getPos(zone, idx);
        const s = zoneStats[zone.id] || {};
        const total = s.total || 0;
        const missing = s.missing || 0;
        const found = s.found || 0;
        const hasMissing = missing > 0;
        const hasData = total > 0;
        const borderColor = hasMissing ? '#f5222d' : hasData ? '#52c41a' : '#9ca3af';
        const fillColor   = hasMissing ? '#fff1f0' : hasData ? '#f6ffed' : '#ffffff';
        const isConnFrom   = connectFrom === zone.id;
        const isConnTarget = !!connectFrom && connectFrom !== zone.id;

        return (
          <g key={zone.id} transform={`translate(${pos.x},${pos.y})`}
            style={{ cursor: editMode ? (connectFrom ? 'crosshair' : dragging?.id === zone.id ? 'grabbing' : 'grab') : 'default', userSelect: 'none' }}
            onMouseDown={e => handleMouseDown(e, zone)}
            onClick={() => handleZoneClick(zone)}>

            {isConnFrom   && <circle r={74} fill="none" stroke="#1890ff" strokeWidth="2.5" strokeDasharray="8,5" opacity="0.8" />}
            {isConnTarget && <circle r={74} fill="rgba(24,144,255,0.06)" stroke="#1890ff" strokeWidth="1.5" opacity="0.55" />}

            {/* Shadow for missing zones */}
            {hasMissing && <rect x={-NW/2} y={-NH/2+4} width={NW} height={NH} rx={10} fill="#f5222d" opacity="0.1" />}

            {/* Main box */}
            <rect x={-NW/2} y={-NH/2} width={NW} height={NH} rx={10}
              fill={fillColor} stroke={borderColor} strokeWidth={hasMissing ? 2.8 : 1.8}
              filter={hasMissing ? 'url(#msRedGlow)' : hasData ? 'url(#msGreenGlow)' : undefined} />

            {/* Top color stripe */}
            <rect x={-NW/2} y={-NH/2} width={NW} height={9} rx={10} fill={borderColor} />
            <rect x={-NW/2} y={-NH/2+5} width={NW} height={5} fill={borderColor} />

            {/* Zone name */}
            <text x={0} y={-NH/2+26} textAnchor="middle" fontSize={15} fontWeight="800" fill="#111827"
              fontFamily="system-ui,-apple-system,sans-serif">
              {zone.name.length > 13 ? zone.name.slice(0, 13) + '…' : zone.name}
            </text>

            {/* Divider */}
            <line x1={-NW/2+10} y1={-NH/2+34} x2={NW/2-10} y2={-NH/2+34} stroke="#e5e7eb" strokeWidth="1" />

            {/* Large "on-site" count */}
            <text x={-NW/2+36} y={12} textAnchor="middle" fontSize={30} fontWeight="900" fill="#111827"
              fontFamily="system-ui,-apple-system,sans-serif">{total}</text>
            <text x={-NW/2+36} y={27} textAnchor="middle" fontSize={9} fill="#6b7280" fontWeight="600">on site</text>

            {/* Missing count */}
            <text x={18} y={4} textAnchor="start" fontSize={22} fontWeight="900"
              fill={missing > 0 ? '#f5222d' : '#d1d5db'}
              fontFamily="system-ui,-apple-system,sans-serif">{missing}</text>
            <text x={18} y={17} textAnchor="start" fontSize={9} fill={missing > 0 ? '#f5222d' : '#d1d5db'} fontWeight="600">missing</text>

            {/* Found count */}
            <text x={18} y={32} textAnchor="start" fontSize={11} fontWeight="700" fill={found > 0 ? '#52c41a' : '#d1d5db'}>
              {found} found
            </text>

            {/* Capacity bar */}
            {zone.capacity > 0 && total > 0 && (
              <>
                <rect x={-NW/2+8} y={NH/2-13} width={NW-16} height={5} rx={2.5} fill="#e5e7eb" />
                <rect x={-NW/2+8} y={NH/2-13} width={(NW-16)*Math.min(1, total/zone.capacity)} height={5} rx={2.5}
                  fill={total >= zone.capacity ? '#f5222d' : '#52c41a'} />
              </>
            )}
          </g>
        );
      })}

      {/* Empty state */}
      {zones.length === 0 && (
        <>
          <rect x={310} y={200} width={380} height={150} rx={16} fill="white" stroke="#e5e7eb" strokeWidth="2" strokeDasharray="8,5" />
          <text x={500} y={263} textAnchor="middle" fontSize={18} fill="#9ca3af" fontFamily="system-ui,sans-serif">No zones on map</text>
          <text x={500} y={290} textAnchor="middle" fontSize={12} fill="#d1d5db" fontFamily="system-ui,sans-serif">Add zones in the Zones tab, then edit the map layout</text>
        </>
      )}
    </svg>
  );
};

/* ══════════════════════════════════════════════════════════════ */

const MusteringManagement = ({ embedded = false, onSectionSwitch }) => {
  const { message, modal } = App.useApp();
  const qc = useQueryClient();

  const [activeTab,       setActiveTab]       = useState('dashboard');
  const [selectedEventId, setSelectedEventId] = useState(null);

  const [startModal,    setStartModal]    = useState(false);
  const [endModal,      setEndModal]      = useState(null);
  const [zoneModal,     setZoneModal]     = useState(null);
  const [drillModal,    setDrillModal]    = useState(false);
  const [templateModal, setTemplateModal] = useState(null);
  const [summaryModal,  setSummaryModal]  = useState(null);

  const [logStatusFilter, setLogStatusFilter] = useState(null);
  const [searchLog,       setSearchLog]       = useState('');
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [scanCode,        setScanCode]        = useState('');
  const scanInputRef = useRef(null);
  const [eventFilter,    setEventFilter]    = useState(null);
  const [mapEditMode,    setMapEditMode]    = useState(false);
  const [connectFrom,    setConnectFrom]    = useState(null);

  const [startForm]    = Form.useForm();
  const [zoneForm]     = Form.useForm();
  const [drillForm]    = Form.useForm();
  const [endForm]      = Form.useForm();
  const [templateForm] = Form.useForm();

  /* ── Queries ── */
  const { data: pobRaw } = useQuery({
    queryKey: ['muster-pob'], queryFn: () => apiService.get('/api/v1/pob-status/dashboard'), refetchInterval: 30000,
  });
  const { data: zonesRaw, isLoading: zonesLoading } = useQuery({
    queryKey: ['muster-zones'],
    queryFn:  () => apiService.get('/api/mustering/zones/'),
    refetchInterval: 30000,
  });
  const zones = Array.isArray(zonesRaw?.data) ? zonesRaw.data : [];

  const { data: activeRaw } = useQuery({
    queryKey: ['muster-active'],
    queryFn:  () => apiService.get('/api/mustering/events/?status=0'),
    refetchInterval: 8000,
  });
  const activeEvents = Array.isArray(activeRaw?.data) ? activeRaw.data : [];

  const evQP = eventFilter != null ? `?status=${eventFilter}` : '';
  const { data: eventsRaw, isLoading: eventsLoading } = useQuery({
    queryKey: ['muster-events', eventFilter],
    queryFn:  () => apiService.get(`/api/mustering/events/${evQP}`),
    refetchInterval: 15000,
  });
  const events = Array.isArray(eventsRaw?.data) ? eventsRaw.data : [];

  const { data: hcRaw } = useQuery({
    queryKey: ['muster-hc', selectedEventId],
    queryFn:  () => apiService.get(`/api/mustering/events/${selectedEventId}/headcount/`),
    enabled:  !!selectedEventId,
    refetchInterval: 8000,
  });
  const headcount = hcRaw?.data;

  const logQP = new URLSearchParams({ limit: 500 });
  if (logStatusFilter != null) logQP.set('status', logStatusFilter);
  const { data: logsRaw, isLoading: logsLoading } = useQuery({
    queryKey: ['muster-logs', selectedEventId, logStatusFilter],
    queryFn:  () => apiService.get(`/api/mustering/events/${selectedEventId}/logs/?${logQP}`),
    enabled:  !!selectedEventId,
    refetchInterval: 8000,
  });
  const allLogs = Array.isArray(logsRaw?.data?.logs) ? logsRaw.data.logs : [];

  const { data: drillsRaw } = useQuery({
    queryKey: ['muster-drills'],
    queryFn:  () => apiService.get('/api/mustering/drills/'),
    enabled:  activeTab === 'drills',
  });
  const drills = Array.isArray(drillsRaw?.data) ? drillsRaw.data : [];

  const { data: templatesRaw } = useQuery({
    queryKey: ['muster-templates'],
    queryFn:  () => apiService.get('/api/mustering/templates/'),
    enabled:  activeTab === 'drills',
  });
  const templates = Array.isArray(templatesRaw?.data) ? templatesRaw.data : [];

  /* ── Mustering event WebSocket ── */
  const wsRef = useRef(null);
  useEffect(() => {
    if (!selectedEventId) { wsRef.current?.close(); return; }
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('token') || localStorage.getItem('authToken') || localStorage.getItem('access_token') || '';
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/mustering/events/${selectedEventId}?token=${token}`);
    ws.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        if (['headcount_update', 'status_updated'].includes(d.type)) {
          qc.invalidateQueries(['muster-hc', selectedEventId]);
          qc.invalidateQueries(['muster-logs', selectedEventId]);
        } else if (['event_started', 'event_ended'].includes(d.type)) {
          qc.invalidateQueries(['muster-active']);
          qc.invalidateQueries(['muster-events']);
        }
      } catch (_) {}
    };
    wsRef.current = ws;
    return () => ws.close();
  }, [selectedEventId]);

  /* ── Zone occupancy WebSocket (real-time ADMS badge counts) ── */
  const [zoneLiveCounts, setZoneLiveCounts] = useState({});
  const zoneWsRef = useRef(null);
  useEffect(() => {
    let retryTimer = null;
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${proto}//${window.location.host}/api/v1/zones/ws`);
      zoneWsRef.current = ws;
      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data);
          if (Array.isArray(d)) {
            const m = {};
            d.forEach(i => { if (i.zone_id != null) m[i.zone_id] = i.count; });
            setZoneLiveCounts(m);
          } else if (d.type === 'zone_update' && d.zone_id != null) {
            setZoneLiveCounts(p => ({ ...p, [d.zone_id]: d.count }));
          }
        } catch (_) {}
      };
      ws.onclose = () => { retryTimer = setTimeout(connect, 5000); };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => { clearTimeout(retryTimer); zoneWsRef.current?.close(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Derived ── */
  const selectedEvent = events.find(e => e.id === selectedEventId) || activeEvents.find(e => e.id === selectedEventId);
  const elapsed = useElapsed(selectedEvent?.start_time, selectedEvent?.status === 0);

  // Live map/panel shows only the zones THIS event involves — its affected/source
  // zones plus the chosen target muster point — not every zone in the system.
  const eventScopeIds = (selectedEvent && selectedEvent.status === 0)
    ? new Set([...(selectedEvent.zone_ids || []), ...(selectedEvent.muster_zone_ids || [selectedEvent.muster_zone_id])].filter(v => v != null))
    : null;
  const mapZones = (eventScopeIds && eventScopeIds.size)
    ? zones.filter(z => eventScopeIds.has(z.id))
    : zones;

  const filteredLogs = allLogs
    .filter(l => {
      if (!searchLog) return true;
      const q = searchLog.toLowerCase();
      return (l.emp_name || '').toLowerCase().includes(q) || (l.emp_code || '').toLowerCase().includes(q);
    })
    .sort((a, b) => a.status - b.status);

  const deptRollup  = buildDeptRollup(allLogs);
  const totalPOB    = allLogs.length;
  const safeCount   = allLogs.filter(l => l.status === 1).length;
  const missingCount = allLogs.filter(l => l.status === 0).length;
  const injuredCount = allLogs.filter(l => l.status === 2).length;
  const accountedCount = safeCount + injuredCount;
  const safePercent = headcount?.completion_percentage != null
    ? Math.round(headcount.completion_percentage)
    : (totalPOB > 0 ? Math.round((accountedCount / totalPOB) * 100) : 0);
  const isActive    = activeEvents.length > 0;

  /* ── Mutations ── */
  const startMut = useMutation({
    mutationFn: (v) => apiService.post('/api/mustering/events/start/', v),
    onSuccess: (d) => {
      const data = d?.data || {};
      // Drill-readiness: warn if no muster reader is online, so the operator marks
      // Safe manually instead of trusting a silent 0% headcount.
      if (data.warning) {
        modal.warning({
          title: 'No muster reader online',
          content: data.warning,
          okText: 'Understood — I will mark Safe manually',
          width: 460,
        });
      } else {
        message.success(
          `Mustering event started${data.muster_readers_online ? ` · ${data.muster_readers_online} muster reader(s) online` : ''}`
        );
      }
      qc.invalidateQueries(['muster-active']); qc.invalidateQueries(['muster-events']);
      setStartModal(false); startForm.resetFields();
      const evId = data.event_id;
      if (evId) { setSelectedEventId(evId); setActiveTab('live'); }
    },
    onError: e => message.error(e?.message || 'Failed to start event'),
  });

  const endMut = useMutation({
    mutationFn: ({ id, reason }) => apiService.post(`/api/mustering/events/${id}/end/`, { reason }),
    onSuccess: (d, v) => {
      message.success('Event ended');
      qc.invalidateQueries(['muster-active']); qc.invalidateQueries(['muster-events']);
      setSummaryModal(d?.data ?? null);
      setEndModal(null); endForm.resetFields();
      if (selectedEventId === v.id) setSelectedEventId(null);
    },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const markMut = useMutation({
    mutationFn: ({ eventId, emp_code, status }) =>
      apiService.post(`/api/mustering/events/${eventId}/mark/`, { emp_code, status }),
    onSuccess: () => {
      qc.invalidateQueries(['muster-hc', selectedEventId]);
      qc.invalidateQueries(['muster-logs', selectedEventId]);
      setSelectedRowKeys([]);
    },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const bulkMarkMut = useMutation({
    mutationFn: ({ eventId, emp_codes, status }) =>
      Promise.all(emp_codes.map(ec => apiService.post(`/api/mustering/events/${eventId}/mark/`, { emp_code: ec, status }))),
    onSuccess: () => {
      message.success(`Marked ${selectedRowKeys.length} personnel`);
      qc.invalidateQueries(['muster-hc', selectedEventId]);
      qc.invalidateQueries(['muster-logs', selectedEventId]);
      setSelectedRowKeys([]);
    },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const createZoneMut = useMutation({
    mutationFn: (v) => apiService.post('/api/mustering/zones/', v),
    onSuccess: () => { message.success('Zone created'); qc.invalidateQueries(['muster-zones']); setZoneModal(null); zoneForm.resetFields(); },
    onError: e => message.error(e?.message || 'Failed'),
  });
  const updateZoneMut = useMutation({
    mutationFn: ({ id, ...v }) => apiService.put(`/api/mustering/zones/${id}/`, v),
    onSuccess: () => { message.success('Zone updated'); qc.invalidateQueries(['muster-zones']); setZoneModal(null); zoneForm.resetFields(); },
    onError: e => message.error(e?.message || 'Failed'),
  });
  const deleteZoneMut = useMutation({
    mutationFn: (id) => apiService.delete(`/api/mustering/zones/${id}`),
    onSuccess: () => { message.success('Zone deleted'); qc.invalidateQueries(['muster-zones']); },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const createDrillMut = useMutation({
    mutationFn: (v) => apiService.post('/api/mustering/drills/', v),
    onSuccess: () => { message.success('Drill scheduled'); qc.invalidateQueries(['muster-drills']); setDrillModal(false); drillForm.resetFields(); },
    onError: e => message.error(e?.message || 'Failed'),
  });
  const triggerDrillMut = useMutation({
    mutationFn: (id) => apiService.post(`/api/mustering/drills/${id}/trigger/`),
    onSuccess: (d) => {
      message.success('Drill triggered');
      qc.invalidateQueries(['muster-active']); qc.invalidateQueries(['muster-events']);
      const evId = d?.data?.event_id;
      if (evId) { setSelectedEventId(evId); setActiveTab('live'); }
    },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const createTemplateMut = useMutation({
    mutationFn: (v) => apiService.post('/api/mustering/templates/', v),
    onSuccess: () => { message.success('Template created'); qc.invalidateQueries(['muster-templates']); setTemplateModal(null); templateForm.resetFields(); },
    onError: e => message.error(e?.message || 'Failed'),
  });
  const deleteTemplateMut = useMutation({
    mutationFn: (id) => apiService.delete(`/api/mustering/templates/${id}`),
    onSuccess: () => { message.success('Template deleted'); qc.invalidateQueries(['muster-templates']); },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const lockdownMut = useMutation({
    mutationFn: ({ action }) => apiService.post('/emergency/api/lockdown/', { action }),
    onSuccess: (_, v) => message.success(v.action === 'lock_all' ? 'All terminals locked' : 'All terminals unlocked'),
    onError: e => message.error(e?.message || 'Lockdown failed'),
  });

  const saveZoneMapMut = useMutation({
    mutationFn: (updates) => Promise.all(
      updates.map(({ id, map_x, map_y, map_connections }) =>
        apiService.patch(`/api/mustering/zones/${id}/map-position/`, { map_x, map_y, map_connections })
      )
    ),
    onSuccess: () => {
      message.success('Map layout saved');
      qc.invalidateQueries(['muster-zones']);
      setMapEditMode(false);
      setConnectFrom(null);
    },
    onError: () => message.error('Failed to save map layout'),
  });

  /* ── Rapid scan ── */
  const handleScan = useCallback((e) => {
    if (e.key !== 'Enter') return;
    const code = scanCode.trim();
    if (!code || !selectedEventId) return;
    const log = allLogs.find(l => l.emp_code === code || (l.emp_name || '').toLowerCase() === code.toLowerCase());
    if (!log) { message.warning(`"${code}" not found in this event`); setScanCode(''); return; }
    if (log.status === 1) { message.info(`${log.emp_name} already marked safe`); setScanCode(''); return; }
    markMut.mutate({ eventId: selectedEventId, emp_code: log.emp_code, status: 1 });
    setScanCode('');
  }, [scanCode, selectedEventId, allLogs]);

  const openLive = (evId) => { setSelectedEventId(evId); setActiveTab('live'); };

  /* ════════════════════════════════════════════════════════════
     TAB 1 — DASHBOARD
  ════════════════════════════════════════════════════════════ */
  const dashboardTab = (
    <div style={{ padding: '24px 28px' }}>

      {/* Emergency alert strip */}
      {isActive && (
        <div style={{
          background: 'linear-gradient(135deg, #3b0000 0%, #7f1d1d 100%)',
          borderRadius: 12, padding: '16px 22px', marginBottom: 24,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12,
          boxShadow: '0 6px 28px rgba(239,68,68,0.25)', border: '1px solid rgba(239,68,68,0.3)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ position: 'relative', flexShrink: 0 }}>
              <div style={{ width: 48, height: 48, borderRadius: 12, background: 'rgba(239,68,68,0.2)', border: '1.5px solid rgba(239,68,68,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <AlertOutlined style={{ color: '#fca5a5', fontSize: 22 }} />
              </div>
              <span style={{ position: 'absolute', top: -3, right: -3, width: 13, height: 13, borderRadius: '50%', background: '#ef4444', animation: 'msPulse 1.1s infinite', boxShadow: '0 0 0 3px rgba(239,68,68,0.25)' }} />
            </div>
            <div>
              <div style={{ color: 'white', fontWeight: 800, fontSize: 17, letterSpacing: '-0.3px', marginBottom: 3 }}>MUSTERING EVENT IN PROGRESS</div>
              <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <span>{activeEvents.length} active event{activeEvents.length !== 1 ? 's' : ''}</span>
                <span style={{ color: '#fca5a5', fontWeight: 700 }}>{missingCount} not accounted</span>
                {safeCount > 0 && <span style={{ color: '#86efac', fontWeight: 700 }}>{safeCount} confirmed safe</span>}
                {totalPOB > 0 && <span style={{ color: 'rgba(255,255,255,0.7)', fontWeight: 700 }}>{safePercent}% accounted</span>}
              </div>
            </div>
          </div>
          <Button size="large" type="primary" danger icon={<PlayCircleOutlined />}
            onClick={() => { setSelectedEventId(activeEvents[0]?.id); setActiveTab('live'); }}
            style={{ fontWeight: 700, borderRadius: 8, background: '#dc2626', borderColor: '#dc2626' }}>
            Live Monitor
          </Button>
        </div>
      )}

      {/* KPI stats row */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        {[
          { label: 'Active Events',    value: activeEvents.length, icon: <AlertOutlined />,        color: '#ef4444', bg: '#fff1f0', sub: isActive ? 'In progress' : 'All clear',   onClick: () => setActiveTab('events') },
          { label: isActive ? 'Expected at Muster' : 'Personnel on Board', value: isActive ? totalPOB : (pobRaw?.total ?? '—'), icon: <TeamOutlined />, color: '#1890ff', bg: '#e6f4ff', sub: isActive ? 'on the muster list' : `${zones.length} zones configured` },
          { label: 'Confirmed Safe',    value: safeCount,           icon: <CheckCircleOutlined />,   color: '#52c41a', bg: '#f6ffed', sub: safePercent > 0 ? `${safePercent}% accounted` : 'No active event' },
          { label: 'Not Accounted',     value: missingCount,        icon: <CloseCircleOutlined />,   color: missingCount > 0 ? '#f5222d' : '#52c41a', bg: missingCount > 0 ? '#fff1f0' : '#f6ffed', sub: injuredCount > 0 ? `${injuredCount} injured` : 'No missing' },
        ].map(s => (
          <Col xs={12} sm={6} key={s.label}>
            <div onClick={s.onClick} style={{
              background: 'white', borderRadius: 12, padding: '18px 20px',
              border: `1px solid ${s.color}20`, borderTop: `3px solid ${s.color}`,
              boxShadow: '0 2px 10px rgba(0,0,0,0.05)', cursor: s.onClick ? 'pointer' : 'default',
              height: '100%', transition: 'box-shadow 0.2s',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
                <div style={{ width: 42, height: 42, borderRadius: 10, background: s.bg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {React.cloneElement(s.icon, { style: { fontSize: 19, color: s.color } })}
                </div>
                {s.onClick && <span style={{ fontSize: 10, color: s.color, fontWeight: 700, letterSpacing: 0.3 }}>VIEW →</span>}
              </div>
              <div style={{ fontSize: 34, fontWeight: 900, color: '#111827', lineHeight: 1, letterSpacing: '-1px', marginBottom: 4 }}>{s.value}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 2 }}>{s.label}</div>
              {s.sub && <div style={{ fontSize: 11, color: s.color, fontWeight: 600 }}>{s.sub}</div>}
            </div>
          </Col>
        ))}
      </Row>

      {/* Accountability bar — active only */}
      {isActive && totalPOB > 0 && (
        <div style={{
          background: 'white', borderRadius: 12, padding: '16px 22px', marginBottom: 20,
          boxShadow: '0 2px 10px rgba(0,0,0,0.05)', border: '1px solid #f0f0f0',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontWeight: 700, fontSize: 13, color: '#141414' }}>
              <TeamOutlined style={{ color: '#1890ff', marginRight: 7 }} />Accountability Progress
            </span>
            <span style={{ fontWeight: 900, fontSize: 24, color: safePercent >= 80 ? '#52c41a' : safePercent >= 50 ? '#faad14' : '#f5222d', letterSpacing: '-0.5px' }}>
              {safePercent}%
            </span>
          </div>
          <div style={{ background: '#f0f0f0', borderRadius: 8, height: 12, overflow: 'hidden', position: 'relative' }}>
            <div style={{
              width: `${safePercent}%`, height: '100%', borderRadius: 8, transition: 'width 0.8s ease',
              background: safePercent >= 80 ? 'linear-gradient(90deg,#52c41a,#73d13d)' : safePercent >= 50 ? 'linear-gradient(90deg,#faad14,#ffc53d)' : 'linear-gradient(90deg,#f5222d,#ff4d4f)',
              boxShadow: `0 2px 8px ${safePercent >= 80 ? 'rgba(82,196,26,0.35)' : safePercent >= 50 ? 'rgba(250,173,20,0.35)' : 'rgba(245,34,45,0.35)'}`,
            }} />
          </div>
          <div style={{ display: 'flex', gap: 20, marginTop: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: '#52c41a', fontWeight: 700 }}><CheckCircleOutlined style={{ marginRight: 4 }} />{safeCount} Safe</span>
            <span style={{ fontSize: 12, color: '#f5222d', fontWeight: 700 }}><CloseCircleOutlined style={{ marginRight: 4 }} />{missingCount} Missing</span>
            {injuredCount > 0 && <span style={{ fontSize: 12, color: '#fa8c16', fontWeight: 700 }}><WarningOutlined style={{ marginRight: 4 }} />{injuredCount} Injured</span>}
            <span style={{ fontSize: 11, color: '#bfbfbf', marginLeft: 'auto' }}>{totalPOB} total expected</span>
          </div>
        </div>
      )}

      {/* Quick actions + bottom panels */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {[
          { label: 'Start Muster',    sub: 'Initiate emergency headcount', icon: <AlertOutlined />,       color: '#f5222d', onClick: () => setStartModal(true) },
          { label: 'Schedule Drill',  sub: 'Plan a practice drill',        icon: <AimOutlined />,         color: '#1890ff', onClick: () => { drillForm.resetFields(); setDrillModal(true); } },
          { label: 'Manage Zones',    sub: 'Assembly points & safe rooms', icon: <EnvironmentOutlined />, color: '#52c41a', onClick: () => setActiveTab('zones') },
          { label: 'Emergency Panel', sub: 'Lockdown & rapid response',    icon: <ThunderboltOutlined />, color: '#722ed1', onClick: () => setActiveTab('emergency') },
        ].map(a => (
          <Col xs={24} sm={12} md={6} key={a.label}>
            <button onClick={a.onClick} style={{
              width: '100%', background: 'white', border: `1px solid ${a.color}20`,
              borderLeft: `3px solid ${a.color}`, borderRadius: '0 10px 10px 0',
              padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14,
              cursor: 'pointer', textAlign: 'left', boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
              transition: 'box-shadow 0.2s, transform 0.1s',
            }}>
              <div style={{ width: 38, height: 38, borderRadius: 9, background: `${a.color}12`, border: `1px solid ${a.color}20`, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {React.cloneElement(a.icon, { style: { color: a.color, fontSize: 16 } })}
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13, color: '#141414', marginBottom: 1 }}>{a.label}</div>
                <div style={{ fontSize: 11, color: '#9ca3af' }}>{a.sub}</div>
              </div>
            </button>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        {/* Active events panel */}
        <Col xs={24} lg={9}>
          <Card
            styles={{ body: { padding: 0 } }}
            style={{ borderRadius: 12, boxShadow: '0 2px 10px rgba(0,0,0,0.05)', height: '100%' }}
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: isActive ? '#f5222d' : '#52c41a', boxShadow: isActive ? '0 0 0 3px rgba(245,34,45,0.2)' : 'none', animation: isActive ? 'msPulse 1.4s infinite' : 'none' }} />
                <span style={{ fontSize: 13, fontWeight: 700 }}>Active Events</span>
                {isActive && <Tag color="error" style={{ borderRadius: 10, marginLeft: 2 }}>{activeEvents.length}</Tag>}
              </div>
            }
          >
            {activeEvents.length === 0 ? (
              <div style={{ padding: '40px 20px', textAlign: 'center' }}>
                <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#f6ffed', border: '2px solid #b7eb8f', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                  <CheckCircleOutlined style={{ fontSize: 24, color: '#52c41a' }} />
                </div>
                <div style={{ color: '#262626', fontSize: 14, fontWeight: 700, marginBottom: 4 }}>All Clear</div>
                <div style={{ color: '#9ca3af', fontSize: 12 }}>No active mustering events</div>
              </div>
            ) : (
              <div>
                {activeEvents.map((ev, i) => {
                  const meta = evTypeMeta(ev.event_type);
                  return (
                    <div key={ev.id} style={{
                      padding: '14px 20px', borderBottom: i < activeEvents.length - 1 ? '1px solid #f5f5f5' : 'none',
                      display: 'flex', alignItems: 'center', gap: 14, background: '#fffafa',
                    }}>
                      <span style={{ width: 9, height: 9, borderRadius: '50%', background: '#f5222d', flexShrink: 0, boxShadow: '0 0 0 3px rgba(245,34,45,0.2)', animation: 'msPulse 1.4s infinite' }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 700, fontSize: 13, color: '#111827', marginBottom: 2 }}>{meta.label}</div>
                        <div style={{ fontSize: 11, color: '#9ca3af' }}>{(ev.zone_names?.join(', ') || ev.zone_name) || 'No zone'} · {dayjs(ev.start_time).fromNow()}</div>
                      </div>
                      <Button size="small" danger ghost onClick={() => openLive(ev.id)} style={{ fontWeight: 600 }}>Monitor</Button>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </Col>

        {/* Recent events table */}
        <Col xs={24} lg={15}>
          <Card
            styles={{ body: { padding: 0 } }}
            style={{ borderRadius: 12, boxShadow: '0 2px 10px rgba(0,0,0,0.05)' }}
            title={<span style={{ fontSize: 13, fontWeight: 700 }}><FileTextOutlined style={{ color: '#1890ff', marginRight: 8 }} />Recent Events</span>}
            extra={<Button size="small" icon={<ReloadOutlined />} type="text" onClick={() => qc.invalidateQueries(['muster-events'])} loading={eventsLoading} />}
          >
            <Table
              dataSource={events.slice(0, 8)} rowKey="id" size="small"
              loading={eventsLoading} pagination={false} scroll={{ x: 480 }}
              locale={{ emptyText: <div style={{ padding: '28px 0', color: '#bfbfbf', textAlign: 'center' }}>No events recorded yet</div> }}
              columns={[
                { title: 'Type',    dataIndex: 'event_type', width: 150, render: v => <EvTypeBadge type={v} /> },
                { title: 'Zones',   dataIndex: 'zone_names', ellipsis: true, render: (names, r) => {
                  const list = names?.length ? names : (r.zone_name ? [r.zone_name] : []);
                  if (!list.length) return <span style={{ color: '#bfbfbf' }}>—</span>;
                  if (list.length === 1) return <span style={{ fontSize: 12, color: '#595959' }}>{list[0]}</span>;
                  return <Tooltip title={list.join(', ')}><span style={{ fontSize: 12, color: '#595959' }}>{list[0]} <Tag style={{ marginLeft: 2, fontSize: 10 }}>+{list.length - 1}</Tag></span></Tooltip>;
                }},
                { title: 'Status',  dataIndex: 'status',     width: 110, render: v => <EvStatusBadge status={v} /> },
                { title: 'Started', dataIndex: 'start_time', width: 130, render: v => <span style={{ fontSize: 11, color: '#8c8c8c', fontFamily: 'monospace' }}>{fmtTime(v)}</span> },
                { title: '', key: 'act', width: 80, render: (_, r) => (
                  <Button size="small" type="link" style={{ padding: 0 }} onClick={() => openLive(r.id)}>
                    {r.status === 0 ? 'Monitor' : 'View'}
                  </Button>
                )},
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );

  /* ════════════════════════════════════════════════════════════
     TAB 2 — LIVE HEADCOUNT
  ════════════════════════════════════════════════════════════ */
  const liveTab = (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 128px)', minHeight: 520 }}>

      {/* ── Selector bar ── */}
      <div style={{ padding: '8px 16px', background: 'white', borderBottom: '1px solid #f0f0f0', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', flexShrink: 0 }}>
        <Select
          placeholder="Select an event to monitor..."
          value={selectedEventId}
          onChange={setSelectedEventId}
          style={{ minWidth: 280, flex: 1, maxWidth: 440 }}
          showSearch optionFilterProp="label" allowClear
        >
          {[...activeEvents, ...events.filter(e => e.status !== 0)]
            .filter((e, i, arr) => arr.findIndex(x => x.id === e.id) === i)
            .map(ev => {
              const meta = evTypeMeta(ev.event_type);
              return (
                <Select.Option key={ev.id} value={ev.id} label={`${meta.label} ${ev.zone_names?.join(', ') || ev.zone_name}`}>
                  <Space size={6}>
                    {meta.icon}
                    <span style={{ fontWeight: 600 }}>{meta.label}</span>
                    <span style={{ color: '#8c8c8c', fontSize: 11 }}>— {(ev.zone_names?.join(', ') || ev.zone_name) || 'No zone'}</span>
                    <EvStatusBadge status={ev.status} />
                  </Space>
                </Select.Option>
              );
            })}
        </Select>
        <Button type="primary" danger icon={<PlayCircleOutlined />} onClick={() => setStartModal(true)}>
          Start New Event
        </Button>
      </div>

      {!selectedEventId ? (
        /* ── Empty state ── */
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #f8fafc 0%, #f0f4ff 100%)' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ width: 96, height: 96, borderRadius: '50%', background: 'white', boxShadow: '0 8px 32px rgba(0,0,0,0.10)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px' }}>
              <TeamOutlined style={{ fontSize: 40, color: '#d9d9d9' }} />
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, color: '#262626', marginBottom: 8 }}>No Event Selected</div>
            <div style={{ fontSize: 13, color: '#8c8c8c', marginBottom: 28, maxWidth: 320 }}>
              Select an active mustering event above to begin live headcount monitoring
            </div>
            <Button size="large" type="primary" danger icon={<AlertOutlined />} onClick={() => setStartModal(true)}>
              Start Mustering Now
            </Button>
          </div>
        </div>
      ) : (
        <>
          {/* ── Alert ribbon (active + missing) ── */}
          {selectedEvent?.status === 0 && missingCount > 0 && (
            <div style={{ background: 'linear-gradient(90deg, #450a0a, #7f1d1d)', padding: '7px 20px', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#fca5a5', display: 'inline-block', flexShrink: 0, animation: 'msPulse 0.9s infinite' }} />
              <span style={{ fontWeight: 800, color: '#fca5a5', fontSize: 12, letterSpacing: 0.4 }}>
                ALERT — {missingCount} personnel unaccounted for
              </span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                {selectedRowKeys.length > 0 && (
                  <>
                    <Button size="small" icon={<CheckCircleOutlined />}
                      style={{ background: '#16a34a', borderColor: '#16a34a', color: 'white', fontSize: 11, fontWeight: 700 }}
                      loading={bulkMarkMut.isPending}
                      onClick={() => bulkMarkMut.mutate({ eventId: selectedEventId, emp_codes: selectedRowKeys, status: 1 })}>
                      Mark Found ({selectedRowKeys.length})
                    </Button>
                    <Button size="small" icon={<WarningOutlined />}
                      style={{ background: '#ea580c', borderColor: '#ea580c', color: 'white', fontSize: 11 }}
                      loading={bulkMarkMut.isPending}
                      onClick={() => bulkMarkMut.mutate({ eventId: selectedEventId, emp_codes: selectedRowKeys, status: 2 })}>
                      Injured
                    </Button>
                    <Button size="small" type="text" onClick={() => setSelectedRowKeys([])} style={{ color: 'rgba(255,255,255,0.5)', fontSize: 11 }}>Clear</Button>
                  </>
                )}
              </div>
            </div>
          )}

          {/* ── Hero command header (dark navy) ── */}
          <div style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', flexShrink: 0, padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>

            {/* Event identity */}
            <div style={{ minWidth: 170, borderRight: '1px solid rgba(255,255,255,0.08)', paddingRight: 16, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 5 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {selectedEvent?.status === 0 && (
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f87171', flexShrink: 0, animation: 'msPulse 1.2s infinite', boxShadow: '0 0 0 3px rgba(248,113,113,0.2)' }} />
                )}
                <span style={{ fontWeight: 800, fontSize: 14, color: 'white', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {selectedEvent?.zone_names?.join(', ') || selectedEvent?.zone_name || 'Muster Event'}
                </span>
              </div>
              <div>
                <EvTypeBadge type={selectedEvent?.event_type} />
                &nbsp;
                <EvStatusBadge status={selectedEvent?.status} />
              </div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', fontFamily: 'monospace' }}>
                {fmtTime(selectedEvent?.start_time)}
              </div>
            </div>

            {/* 4 big stat blocks */}
            <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
              {[
                { label: 'Expected',  val: headcount?.total_expected ?? totalPOB, color: '#93c5fd', accent: 'rgba(147,197,253,0.08)' },
                { label: 'Safe',      val: safeCount,     color: '#86efac', accent: 'rgba(134,239,172,0.08)' },
                { label: 'Missing',   val: missingCount,  color: missingCount > 0 ? '#f87171' : '#86efac', accent: missingCount > 0 ? 'rgba(248,113,113,0.12)' : 'rgba(134,239,172,0.08)' },
                { label: 'Injured',   val: injuredCount,  color: injuredCount > 0 ? '#fb923c' : 'rgba(255,255,255,0.2)', accent: injuredCount > 0 ? 'rgba(251,146,60,0.1)' : 'transparent' },
                { label: 'Left site', val: allLogs.filter(l => l.status === 3).length, color: '#7dd3fc', accent: 'rgba(125,211,252,0.08)' },
              ].map(s => (
                <div key={s.label} style={{ textAlign: 'center', padding: '10px 6px', background: s.accent, borderRadius: 10, border: '1px solid rgba(255,255,255,0.05)' }}>
                  <div style={{ fontSize: 52, fontWeight: 900, color: s.color, lineHeight: 1, letterSpacing: '-2px', fontFamily: '"SF Pro Display",system-ui,sans-serif' }}>
                    {s.val}
                  </div>
                  <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginTop: 4 }}>
                    {s.label}
                  </div>
                </div>
              ))}
            </div>

            {/* Progress ring + timer + actions */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, borderLeft: '1px solid rgba(255,255,255,0.08)', paddingLeft: 16 }}>
              <div style={{ position: 'relative', width: 84, height: 84 }}>
                <CircleProgress percent={safePercent} size={84} />
                <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 17, fontWeight: 900, color: 'white', lineHeight: 1 }}>{safePercent}%</span>
                  <span style={{ fontSize: 8, color: 'rgba(255,255,255,0.35)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>acctd</span>
                </div>
              </div>
              {selectedEvent?.status === 0 ? (
                <>
                  <div style={{ fontFamily: 'monospace', fontSize: 15, fontWeight: 900, color: '#f87171', letterSpacing: '0.12em' }}>{elapsed}</div>
                  <Button danger size="small" icon={<StopOutlined />} onClick={() => setEndModal(selectedEventId)} style={{ fontWeight: 700, fontSize: 11 }}>
                    End Event
                  </Button>
                </>
              ) : (
                <Space direction="vertical" size={4} style={{ alignItems: 'center' }}>
                  <Button size="small" icon={<DownloadOutlined />} onClick={() => downloadEventReport(selectedEventId, 'excel')}
                    style={{ background: 'rgba(24,144,255,0.15)', border: '1px solid rgba(24,144,255,0.3)', color: '#93c5fd', fontSize: 11 }}>
                    Report
                  </Button>
                  <Button size="small" icon={<ReloadOutlined />} onClick={() => setSelectedEventId(null)} type="text" style={{ color: 'rgba(255,255,255,0.35)', fontSize: 10 }}>
                    Change
                  </Button>
                </Space>
              )}
            </div>
          </div>

          {/* ── Toolbar ── */}
          <div style={{ background: '#f8fafc', borderBottom: '1px solid #e5e7eb', padding: '6px 14px', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', flexShrink: 0 }}>
            {selectedEvent?.status === 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#0f172a', borderRadius: 7, padding: '4px 12px 4px 10px' }}>
                <ScanOutlined style={{ color: '#34d399', fontSize: 13 }} />
                <Input ref={scanInputRef} value={scanCode} onChange={e => setScanCode(e.target.value)} onKeyDown={handleScan}
                  placeholder="Scan badge or ID..."
                  style={{ background: 'transparent', border: 'none', color: 'white', width: 155, fontSize: 12 }} size="small" />
              </div>
            )}
            {selectedEvent?.status !== 0 && selectedRowKeys.length > 0 && (
              <Space size={4}>
                <Button size="small" icon={<CheckCircleOutlined />}
                  style={{ background: '#52c41a', borderColor: '#52c41a', color: 'white', fontSize: 11, fontWeight: 700 }}
                  loading={bulkMarkMut.isPending}
                  onClick={() => bulkMarkMut.mutate({ eventId: selectedEventId, emp_codes: selectedRowKeys, status: 1 })}>
                  Mark Found ({selectedRowKeys.length})
                </Button>
                <Button size="small" icon={<WarningOutlined />}
                  style={{ color: '#fa8c16', borderColor: '#fa8c16', fontSize: 11 }}
                  loading={bulkMarkMut.isPending}
                  onClick={() => bulkMarkMut.mutate({ eventId: selectedEventId, emp_codes: selectedRowKeys, status: 2 })}>
                  Injured
                </Button>
                <Button size="small" type="text" onClick={() => setSelectedRowKeys([])}>Clear</Button>
              </Space>
            )}
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
              <Button size="small" icon={<ReloadOutlined />} type="text" style={{ color: '#8c8c8c' }}
                onClick={() => { qc.invalidateQueries(['muster-hc', selectedEventId]); qc.invalidateQueries(['muster-logs', selectedEventId]); }}>
                Refresh
              </Button>
              {!mapEditMode ? (
                <Button size="small" icon={<EditOutlined />} onClick={() => setMapEditMode(true)}>Edit Map</Button>
              ) : (
                <>
                  <Button size="small"
                    style={{ background: connectFrom ? '#1890ff' : undefined, borderColor: connectFrom ? '#1890ff' : undefined, color: connectFrom ? 'white' : undefined }}
                    onClick={() => setConnectFrom(connectFrom ? null : -1)}>
                    {connectFrom ? '● Click to connect' : 'Connect Zones'}
                  </Button>
                  <Button size="small" type="primary" loading={saveZoneMapMut.isPending}
                    onClick={() => saveZoneMapMut.mutate(zones.map(z => ({ id: z.id, map_x: z.map_x, map_y: z.map_y, map_connections: z.map_connections })))}>
                    Save Layout
                  </Button>
                  <Button size="small" onClick={() => { setMapEditMode(false); setConnectFrom(null); qc.invalidateQueries(['muster-zones']); }}>Cancel</Button>
                </>
              )}
            </div>
          </div>

          {/* ── Zone Breakdown ── */}
          {headcount?.zone_breakdown?.length > 0 && (
            <div style={{ padding: '8px 14px', background: '#f8fafc', borderBottom: '1px solid #e5e7eb', flexShrink: 0 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#374151', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Zone Headcount
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {headcount.zone_breakdown.map(z => (
                  <div key={z.zone_name} style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    background: 'white', border: `1px solid ${z.missing > 0 ? '#fca5a5' : '#e5e7eb'}`,
                    borderLeft: `4px solid ${z.missing > 0 ? '#ef4444' : z.safe > 0 ? '#22c55e' : '#d1d5db'}`,
                    borderRadius: 8, padding: '5px 10px', minWidth: 140,
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {z.zone_name}
                      </div>
                      <div style={{ fontSize: 10, color: '#6b7280', marginTop: 1 }}>
                        {z.safe > 0 && <span style={{ color: '#16a34a', marginRight: 6 }}>✓ {z.safe} safe</span>}
                        {z.missing > 0 && <span style={{ color: '#dc2626', marginRight: 6 }}>✗ {z.missing} missing</span>}
                        {z.injured > 0 && <span style={{ color: '#ea580c' }}>⚠ {z.injured} injured</span>}
                      </div>
                    </div>
                    <div style={{ fontSize: 20, fontWeight: 900, color: z.missing > 0 ? '#ef4444' : '#374151', flexShrink: 0 }}>
                      {z.total}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Rescue Intelligence: zone-based search guide for missing personnel ── */}
          {selectedEvent?.status === 0 && missingCount > 0 && (() => {
            const missingWithZone = allLogs.filter(l => l.status === 0 && (l.last_known_zone || l.last_punch_area));
            if (!missingWithZone.length) return null;

            const zoneGroups = {};
            for (const l of missingWithZone) {
              const key = l.last_known_zone || l.last_punch_area;
              if (!zoneGroups[key]) zoneGroups[key] = { zone: key, code: l.last_known_zone_code, count: 0 };
              zoneGroups[key].count++;
            }
            const sortedGroups = Object.values(zoneGroups).sort((a, b) => b.count - a.count);
            const noZoneCount = missingCount - missingWithZone.length;

            return (
              <div style={{ padding: '8px 14px', background: '#fff1f0', borderBottom: '2px solid #f5222d', flexShrink: 0 }}>
                <div style={{ fontSize: 11, fontWeight: 800, color: '#dc2626', marginBottom: 7,
                  display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                    background: '#f5222d', animation: 'msPulse 1.4s infinite' }} />
                  RESCUE SEARCH — Last known locations
                  <span style={{ fontWeight: 400, color: '#9ca3af', fontSize: 10, textTransform: 'none' }}>
                    ({missingWithZone.length} of {missingCount} missing have zone data)
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {sortedGroups.map(g => (
                    <Tooltip key={g.zone} title={`${g.count} missing person${g.count > 1 ? 's' : ''} last seen in ${g.zone} — dispatch rescue here`}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 7,
                        background: 'white', border: '2px solid #f5222d', borderRadius: 8, padding: '5px 10px',
                        cursor: 'default', boxShadow: '0 1px 4px rgba(220,38,38,0.15)' }}>
                        <EnvironmentOutlined style={{ color: '#f5222d', fontSize: 13 }} />
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 700, color: '#111827', lineHeight: 1.2 }}>{g.zone}</div>
                          {g.code && <div style={{ fontSize: 9, color: '#9ca3af', fontFamily: 'monospace', letterSpacing: '0.04em' }}>{g.code}</div>}
                        </div>
                        <div style={{ background: '#f5222d', color: 'white', borderRadius: '50%',
                          width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 11, fontWeight: 900, flexShrink: 0, marginLeft: 2 }}>{g.count}</div>
                      </div>
                    </Tooltip>
                  ))}
                  {noZoneCount > 0 && (
                    <Tooltip title="These personnel had no active zone badge when the event started (e.g. just arrived or on break)">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6,
                        background: '#fafafa', border: '1px dashed #d1d5db', borderRadius: 8, padding: '5px 10px' }}>
                        <span style={{ fontSize: 11, color: '#6b7280', fontWeight: 600 }}>
                          + {noZoneCount} with no zone record
                        </span>
                      </div>
                    </Tooltip>
                  )}
                </div>
              </div>
            );
          })()}

          {/* ── Split pane ── */}
          <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>

            {/* Left: Person roster */}
            <div style={{ width: 316, flexShrink: 0, borderRight: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column', background: 'white' }}>
              {/* Search + filter pills */}
              <div style={{ padding: '8px 10px', borderBottom: '1px solid #f0f0f0', flexShrink: 0 }}>
                <Input.Search placeholder="Search name or ID..." value={searchLog} onChange={e => setSearchLog(e.target.value)} size="small" allowClear style={{ marginBottom: 7 }} />
                <div style={{ display: 'flex', gap: 4 }}>
                  {[
                    { v: null, l: 'All',                    c: '#1890ff' },
                    { v: 0,    l: `Missing (${missingCount})`, c: '#f5222d' },
                    { v: 1,    l: `Safe (${safeCount})`,       c: '#22c55e' },
                    { v: 2,    l: `Injured (${injuredCount})`, c: '#f97316' },
                  ].map(f => (
                    <button key={String(f.v)} onClick={() => setLogStatusFilter(logStatusFilter === f.v ? null : f.v)}
                      style={{
                        flex: 1, padding: '3px 2px', borderRadius: 5,
                        border: `1px solid ${logStatusFilter === f.v ? f.c : '#e5e7eb'}`,
                        background: logStatusFilter === f.v ? `${f.c}15` : 'white',
                        color: logStatusFilter === f.v ? f.c : '#9ca3af',
                        fontSize: 10, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap',
                      }}>
                      {f.l}
                    </button>
                  ))}
                </div>
              </div>

              {/* Rows */}
              <div style={{ flex: 1, overflowY: 'auto' }}>
                {logsLoading ? (
                  <div style={{ padding: 32, textAlign: 'center' }}><Spin size="small" /></div>
                ) : filteredLogs.length === 0 ? (
                  <div style={{ padding: '44px 0', textAlign: 'center', color: '#d1d5db' }}>
                    <UserOutlined style={{ fontSize: 28, display: 'block', marginBottom: 8 }} />
                    <div style={{ fontSize: 12 }}>No personnel data</div>
                  </div>
                ) : filteredLogs.map(p => {
                  const sc = {
                    0: { border: '#f87171', bg: '#fff1f0', label: 'MISSING', lc: '#dc2626' },
                    1: { border: '#4ade80', bg: 'white',   label: 'SAFE',    lc: '#16a34a' },
                    2: { border: '#fb923c', bg: '#fff7ed', label: 'INJURED', lc: '#ea580c' },
                    3: { border: '#38bdf8', bg: '#f0f9ff', label: 'LEFT SITE', lc: '#0284c7' },
                  }[p.status] ?? { border: '#f87171', bg: '#fff1f0', label: 'MISSING', lc: '#dc2626' };
                  const deptColor = DEPT_COLORS[(p.dept_name || '').length % DEPT_COLORS.length];
                  const initials = (p.emp_name || p.emp_code || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
                  return (
                    <div key={p.emp_code} style={{
                      display: 'flex', alignItems: 'center', padding: '8px 10px 8px 0',
                      borderBottom: '1px solid #f5f5f5',
                      borderLeft: `3px solid ${sc.border}`,
                      background: sc.bg,
                    }}>
                      {/* Avatar */}
                      <div style={{
                        width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
                        background: `${deptColor}18`, border: `1.5px solid ${deptColor}35`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, fontWeight: 800, color: deptColor, marginLeft: 8, marginRight: 9,
                      }}>{initials}</div>
                      {/* Info */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 700, fontSize: 12, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {p.emp_name || p.emp_code}
                        </div>
                        <div style={{ fontSize: 10, color: '#9ca3af', display: 'flex', gap: 4, marginTop: 1 }}>
                          <span style={{ fontFamily: 'monospace' }}>{p.emp_code}</span>
                          {p.dept_name && <><span>·</span><span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 80 }}>{p.dept_name}</span></>}
                        </div>
                        {/* Last known zone — rescue intelligence for MISSING personnel */}
                        {p.status === 0 && (p.last_known_zone || p.last_punch_area) && (
                          <div style={{ fontSize: 10, color: '#dc2626', marginTop: 2, fontWeight: 700,
                            display: 'flex', alignItems: 'center', gap: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            <EnvironmentOutlined style={{ fontSize: 9, flexShrink: 0 }} />
                            {p.last_known_zone || p.last_punch_area}
                          </div>
                        )}
                      </div>
                      {/* Status + action */}
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3, flexShrink: 0, marginLeft: 6 }}>
                        <span style={{ fontSize: 9, fontWeight: 800, color: sc.lc, letterSpacing: 0.3 }}>{sc.label}</span>
                        {p.status !== 1 && selectedEvent?.status === 0 && (
                          <button
                            onClick={() => markMut.mutate({ eventId: selectedEventId, emp_code: p.emp_code, status: 1 })}
                            style={{ fontSize: 9, padding: '2px 8px', background: '#16a34a', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 800 }}>
                            Found
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Footer summary */}
              <div style={{ padding: '7px 12px', borderTop: '1px solid #f0f0f0', background: '#fafafa', flexShrink: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 10, color: '#6b7280', fontWeight: 600 }}>{filteredLogs.length} shown</span>
                <div style={{ display: 'flex', gap: 8 }}>
                  <span style={{ fontSize: 10, color: '#dc2626', fontWeight: 700 }}>{missingCount} missing</span>
                  <span style={{ fontSize: 10, color: '#16a34a', fontWeight: 700 }}>{safeCount} safe</span>
                  {injuredCount > 0 && <span style={{ fontSize: 10, color: '#ea580c', fontWeight: 700 }}>{injuredCount} injured</span>}
                </div>
              </div>
            </div>

            {/* Right: Live Leaflet map */}
            <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
              <MusteringLiveMap
                zones={mapZones}
                activeZoneId={selectedEvent?.muster_zone_ids?.[0] ?? selectedEvent?.muster_zone_id ?? selectedEvent?.zone_id ?? null}
                allLogs={allLogs}
                isEventActive={selectedEvent?.status === 0}
                zoneLiveCounts={zoneLiveCounts}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );


  /* ════════════════════════════════════════════════════════════
     TAB 3 — ZONES
  ════════════════════════════════════════════════════════════ */
  const zonesTab = (
    <div style={{ padding: '24px 28px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: 18, color: '#141414', marginBottom: 2 }}>Muster Zones</div>
          <div style={{ fontSize: 12, color: '#8c8c8c' }}>
            {zones.length} zone{zones.length !== 1 ? 's' : ''} configured · Assembly points &amp; safe rooms
          </div>
        </div>
        <Button type="primary" icon={<PlusOutlined />}
          style={{ background: '#52c41a', borderColor: '#52c41a', borderRadius: 8 }}
          onClick={() => { zoneForm.resetFields(); setZoneModal({}); }}>
          Add Zone
        </Button>
      </div>

      {zonesLoading ? (
        <div style={{ textAlign: 'center', padding: '60px 0' }}><Spin size="large" /></div>
      ) : zones.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '64px 0', background: 'white', borderRadius: 12,
          border: '2px dashed #f0f0f0', boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
        }}>
          <EnvironmentOutlined style={{ fontSize: 40, color: '#d9d9d9', display: 'block', marginBottom: 12 }} />
          <div style={{ color: '#595959', fontWeight: 700, fontSize: 16, marginBottom: 6 }}>No Zones Configured</div>
          <div style={{ color: '#bfbfbf', fontSize: 12, marginBottom: 24 }}>Add assembly points, safe rooms, and muster stations</div>
          <Button type="primary" icon={<PlusOutlined />}
            style={{ background: '#52c41a', borderColor: '#52c41a' }}
            onClick={() => { zoneForm.resetFields(); setZoneModal({}); }}>
            Add First Zone
          </Button>
        </div>
      ) : (
        <Row gutter={[16, 16]}>
          {zones.map(zone => {
            const zt = ZONE_TYPES.find(t => t.value === zone.zone_type);
            const typeColors = { 0: '#1890ff', 1: '#52c41a', 2: '#f5222d' };
            const typeIconMap = [<TeamOutlined />, <CheckCircleOutlined />, <WarningOutlined />];
            const color = typeColors[zone.zone_type] ?? '#8c8c8c';
            const iconEl = typeIconMap[zone.zone_type] ?? <EnvironmentOutlined />;
            return (
              <Col xs={24} sm={12} lg={8} xl={6} key={zone.id}>
                <Card
                  styles={{ body: { padding: 0 } }}
                  style={{ borderRadius: 12, overflow: 'hidden', border: '1px solid #f0f0f0', boxShadow: '0 2px 10px rgba(0,0,0,0.06)', height: '100%' }}
                >
                  <div style={{
                    background: `linear-gradient(135deg, ${color}18 0%, ${color}08 100%)`,
                    borderBottom: `2px solid ${color}25`,
                    padding: '16px 18px',
                    display: 'flex', alignItems: 'flex-start', gap: 12,
                  }}>
                    <div style={{
                      width: 46, height: 46, borderRadius: 11,
                      background: `${color}18`, border: `1.5px solid ${color}30`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    }}>
                      {React.cloneElement(iconEl, { style: { fontSize: 20, color } })}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: 14, color: '#141414', marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {zone.name}
                      </div>
                      <Tag color={zone.zone_type === 0 ? 'blue' : zone.zone_type === 1 ? 'green' : 'red'} style={{ borderRadius: 6, fontSize: 10, lineHeight: '16px' }}>
                        {zt?.label || 'Zone'}
                      </Tag>
                    </div>
                    <Space size={2}>
                      <Button size="small" icon={<EditOutlined />} type="text"
                        onClick={() => { zoneForm.setFieldsValue({ name: zone.name, zone_type: zone.zone_type, capacity: zone.capacity, reader_sn: zone.reader_sn, description: zone.description, latitude: zone.latitude, longitude: zone.longitude }); setZoneModal(zone); }} />
                      <Popconfirm title="Delete this zone?" onConfirm={() => deleteZoneMut.mutate(zone.id)} okText="Delete" okButtonProps={{ danger: true }}>
                        <Button size="small" icon={<DeleteOutlined />} type="text" danger />
                      </Popconfirm>
                    </Space>
                  </div>
                  <div style={{ padding: '14px 18px' }}>
                    {zone.description && (
                      <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 12, lineHeight: 1.5 }}>{zone.description}</div>
                    )}
                    <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                      <div>
                        <div style={{ fontSize: 10, color: '#bfbfbf', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600, marginBottom: 2 }}>Capacity</div>
                        <div style={{ fontSize: 20, fontWeight: 800, color, lineHeight: 1 }}>{zone.capacity || '—'}</div>
                      </div>
                      {zone.reader_sn && (
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 10, color: '#bfbfbf', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600, marginBottom: 2 }}>Reader SN</div>
                          <div style={{ fontSize: 11, fontWeight: 700, color: '#595959', fontFamily: 'monospace', lineHeight: 1.4, wordBreak: 'break-all' }}>{zone.reader_sn}</div>
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              </Col>
            );
          })}
        </Row>
      )}
    </div>
  );

  /* ════════════════════════════════════════════════════════════
     TAB 4 — EVENTS
  ════════════════════════════════════════════════════════════ */
  const eventsTab = (
    <div style={{ padding: '24px 28px' }}>
      {/* Summary stat cards */}
      <Row gutter={[14, 14]} style={{ marginBottom: 22 }}>
        {[
          { label: 'Total Events', v: events.length,                             color: '#1890ff', icon: <FileTextOutlined /> },
          { label: 'Active',       v: events.filter(e => e.status === 0).length, color: '#f5222d', icon: <AlertOutlined /> },
          { label: 'Completed',    v: events.filter(e => e.status === 1).length, color: '#52c41a', icon: <CheckCircleOutlined /> },
          { label: 'Cancelled',    v: events.filter(e => e.status === 2).length, color: '#8c8c8c', icon: <CloseCircleOutlined /> },
        ].map(s => (
          <Col key={s.label} xs={12} sm={6}>
            <div style={{
              background: 'white', borderRadius: 12, padding: '16px 20px',
              border: `1px solid ${s.color}18`, borderTop: `3px solid ${s.color}`,
              boxShadow: '0 2px 8px rgba(0,0,0,0.05)', display: 'flex', alignItems: 'center', gap: 14,
            }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: `${s.color}12`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                {React.cloneElement(s.icon, { style: { fontSize: 18, color: s.color } })}
              </div>
              <div>
                <div style={{ fontSize: 30, fontWeight: 900, color: s.color, lineHeight: 1, letterSpacing: '-1px' }}>{s.v}</div>
                <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.4, marginTop: 2 }}>{s.label}</div>
              </div>
            </div>
          </Col>
        ))}
      </Row>

      <Card
        styles={{ body: { padding: 0 } }}
        style={{ borderRadius: 12, boxShadow: '0 2px 10px rgba(0,0,0,0.05)' }}
        title={<span style={{ fontWeight: 700, fontSize: 13 }}><FileTextOutlined style={{ color: '#1890ff', marginRight: 8 }} />All Events</span>}
        extra={
          <Space size={8}>
            <Select size="small" placeholder="Filter status" value={eventFilter} onChange={setEventFilter} style={{ width: 130 }} allowClear>
              <Select.Option value={0}><span style={{ color: '#f5222d', fontWeight: 600 }}>● Active</span></Select.Option>
              <Select.Option value={1}><span style={{ color: '#52c41a', fontWeight: 600 }}>✓ Completed</span></Select.Option>
              <Select.Option value={2}><span style={{ color: '#8c8c8c', fontWeight: 600 }}>○ Cancelled</span></Select.Option>
            </Select>
            <Button type="primary" danger size="small" icon={<PlayCircleOutlined />} onClick={() => setStartModal(true)} style={{ fontWeight: 700 }}>
              Start Event
            </Button>
          </Space>
        }
      >
        <Table
          dataSource={events} rowKey="id" loading={eventsLoading} size="small"
          rowClassName={r => r.status === 0 ? 'ms-ev-active' : ''}
          scroll={{ x: 700 }} pagination={{ pageSize: 15, size: 'small', showSizeChanger: false }}
          locale={{ emptyText: (
            <div style={{ padding: '40px 0', textAlign: 'center' }}>
              <FileTextOutlined style={{ fontSize: 30, color: '#d9d9d9', display: 'block', marginBottom: 10 }} />
              <div style={{ color: '#bfbfbf', fontSize: 13 }}>No events found</div>
            </div>
          )}}
          columns={[
            { title: 'Type',      dataIndex: 'event_type', width: 155, render: v => <EvTypeBadge type={v} /> },
            { title: 'Zones',     dataIndex: 'zone_names', ellipsis: true, render: (names, r) => {
              const list = names?.length ? names : (r.zone_name ? [r.zone_name] : []);
              if (!list.length) return <span style={{ color: '#bfbfbf' }}>—</span>;
              if (list.length === 1) return <span style={{ fontSize: 12, color: '#374151' }}>{list[0]}</span>;
              return <Tooltip title={list.join(', ')}><span style={{ fontSize: 12, color: '#374151' }}>{list[0]} <Tag style={{ marginLeft: 2, fontSize: 10 }}>+{list.length - 1}</Tag></span></Tooltip>;
            }},
            { title: 'Status',    dataIndex: 'status',     width: 115, render: v => <EvStatusBadge status={v} /> },
            { title: 'Safe / POB', key: 'hc', width: 105, render: (_, r) => {
                const safe = r.total_safe ?? r.headcount?.total_safe;
                const exp  = r.total_expected ?? r.headcount?.total_expected;
                return safe != null
                  ? <span style={{ fontWeight: 700, fontSize: 12 }}>
                      <span style={{ color: '#52c41a' }}>{safe}</span>
                      <span style={{ color: '#d1d5db' }}>/</span>
                      <span style={{ color: '#374151' }}>{exp ?? '?'}</span>
                    </span>
                  : <span style={{ color: '#d1d5db' }}>—</span>;
              }
            },
            { title: 'Started', dataIndex: 'start_time', width: 145, render: v => <span style={{ fontSize: 11, color: '#6b7280', fontFamily: 'monospace' }}>{fmtTime(v)}</span> },
            { title: 'Ended',   dataIndex: 'end_time',   width: 145, render: v => <span style={{ fontSize: 11, color: '#9ca3af', fontFamily: 'monospace' }}>{v ? fmtTime(v) : '—'}</span> },
            { title: '', key: 'act', width: 155, fixed: 'right', render: (_, r) => (
              <Space size={4}>
                <Button size="small" type="link" style={{ padding: '0 4px', fontWeight: 600 }} onClick={() => openLive(r.id)}>
                  {r.status === 0 ? 'Monitor' : 'View'}
                </Button>
                {r.status === 0 && <Button size="small" danger type="text" style={{ padding: '0 4px' }} onClick={() => setEndModal(r.id)}>End</Button>}
                {r.status === 1 && (
                  <Tooltip title="Download Excel report">
                    <Button size="small" type="text" icon={<DownloadOutlined />} style={{ padding: '0 4px', color: '#1890ff' }} onClick={() => downloadEventReport(r.id, 'excel')} />
                  </Tooltip>
                )}
              </Space>
            )},
          ]}
        />
      </Card>
    </div>
  );

  /* ════════════════════════════════════════════════════════════
     TAB 5 — DRILLS & TEMPLATES
  ════════════════════════════════════════════════════════════ */
  const drillsTab = (
    <div style={{ padding: '24px 28px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: 18, color: '#111827', marginBottom: 3 }}>Drills & Templates</div>
          <div style={{ fontSize: 12, color: '#9ca3af' }}>Plan practice musters, schedule drills, and save reusable event templates</div>
        </div>
        <Space>
          <Button icon={<PlusOutlined />} style={{ color: '#722ed1', borderColor: '#722ed1', fontWeight: 600 }}
            onClick={() => { drillForm.resetFields(); setDrillModal(true); }}>
            Schedule Drill
          </Button>
          <Button type="primary" icon={<PlusOutlined />}
            style={{ background: '#52c41a', borderColor: '#52c41a', fontWeight: 600 }}
            onClick={() => setTemplateModal({})}>
            New Template
          </Button>
        </Space>
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={15}>
          <Card
            styles={{ body: { padding: 0 } }}
            style={{ borderRadius: 12, boxShadow: '0 2px 10px rgba(0,0,0,0.05)', marginBottom: 0 }}
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 30, height: 30, borderRadius: 8, background: '#722ed115', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <CalendarOutlined style={{ color: '#722ed1', fontSize: 14 }} />
                </div>
                <span style={{ fontSize: 13, fontWeight: 700 }}>Scheduled Drills</span>
                {drills.length > 0 && <Tag style={{ borderRadius: 10, background: '#722ed115', borderColor: '#722ed1', color: '#722ed1' }}>{drills.length}</Tag>}
              </div>
            }
          >
            <Table
              dataSource={drills} rowKey="id" size="small"
              pagination={{ pageSize: 10, size: 'small', showSizeChanger: false }}
              locale={{ emptyText: (
                <div style={{ padding: '48px 0', textAlign: 'center' }}>
                  <CalendarOutlined style={{ fontSize: 30, color: '#d9d9d9', display: 'block', marginBottom: 10 }} />
                  <div style={{ color: '#bfbfbf', fontSize: 13 }}>No drills scheduled yet</div>
                  <Button size="small" style={{ marginTop: 12, color: '#722ed1', borderColor: '#722ed1' }}
                    icon={<PlusOutlined />} onClick={() => { drillForm.resetFields(); setDrillModal(true); }}>
                    Schedule First Drill
                  </Button>
                </div>
              )}}
              columns={[
                { title: 'Type',      dataIndex: 'event_type',     width: 145, render: v => <EvTypeBadge type={v} /> },
                { title: 'Zone',      dataIndex: 'zone_name',      ellipsis: true, render: v => <span style={{ fontSize: 12, color: '#374151' }}>{v || '—'}</span> },
                { title: 'Scheduled', dataIndex: 'scheduled_time', width: 145, render: v => <span style={{ fontSize: 11, color: '#6b7280', fontFamily: 'monospace' }}>{fmtTime(v)}</span> },
                { title: 'Mode', dataIndex: 'auto_start', width: 90, render: v => (
                  <Tag color={v ? 'blue' : 'default'} style={{ borderRadius: 6, fontWeight: 600, fontSize: 10 }}>
                    {v ? 'Auto' : 'Manual'}
                  </Tag>
                )},
                { title: 'Status', key: 'status', width: 110, render: (_, r) => {
                  const now = Date.now();
                  const due = r.scheduled_time && new Date(r.scheduled_time) <= now;
                  const status = r.status || 'PENDING';
                  // Past-due but not yet processed = zone was busy, scheduler is retrying
                  const isDeferred = !r.processed && due && status === 'PENDING';
                  const cfg = {
                    PENDING:   { color: 'purple',  label: 'Scheduled' },
                    TRIGGERED: { color: 'success', label: 'Triggered' },
                    COMPLETED: { color: 'success', label: 'Completed' },
                    SKIPPED:   { color: 'warning', label: 'Skipped'   },
                    EXPIRED:   { color: 'default', label: 'Expired'   },
                  };
                  if (isDeferred) return (
                    <Tooltip title="Zone has an active event — will trigger automatically when it clears">
                      <Tag color="orange" style={{ borderRadius: 6, fontWeight: 600 }}>Deferred</Tag>
                    </Tooltip>
                  );
                  const c = cfg[status] ?? cfg.PENDING;
                  return <Tag color={c.color} style={{ borderRadius: 6, fontWeight: 600 }}>{c.label}</Tag>;
                }},
                { title: '', key: 'act', width: 90, render: (_, r) => !r.processed && (
                  <Tooltip title={r.auto_start ? 'Auto-trigger is on — will fire automatically' : 'Manual trigger required'}>
                    <Popconfirm title="Trigger this drill now?" description="This will start a live mustering event immediately." onConfirm={() => triggerDrillMut.mutate(r.id)} okText="Trigger Now" okButtonProps={{ style: { background: '#722ed1', borderColor: '#722ed1' } }}>
                      <Button size="small" icon={<PlayCircleOutlined />} style={{ color: '#722ed1', borderColor: '#722ed1', fontWeight: 600 }}>Trigger</Button>
                    </Popconfirm>
                  </Tooltip>
                )},
              ]}
            />
          </Card>
        </Col>

        <Col xs={24} lg={9}>
          <Card
            styles={{ body: { padding: 0 } }}
            style={{ borderRadius: 12, boxShadow: '0 2px 10px rgba(0,0,0,0.05)' }}
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 30, height: 30, borderRadius: 8, background: '#52c41a15', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <FileTextOutlined style={{ color: '#52c41a', fontSize: 14 }} />
                </div>
                <span style={{ fontSize: 13, fontWeight: 700 }}>Event Templates</span>
                {templates.length > 0 && <Tag style={{ borderRadius: 10, background: '#52c41a15', borderColor: '#52c41a', color: '#52c41a' }}>{templates.length}</Tag>}
              </div>
            }
            extra={
              <Button size="small" icon={<PlusOutlined />} style={{ color: '#52c41a', borderColor: '#52c41a', fontWeight: 600 }}
                onClick={() => setTemplateModal({})}>New</Button>
            }
          >
            {templates.length === 0 ? (
              <div style={{ padding: '44px 20px', textAlign: 'center' }}>
                <div style={{ width: 52, height: 52, borderRadius: '50%', background: '#f9fafb', border: '2px dashed #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                  <FileTextOutlined style={{ fontSize: 22, color: '#d1d5db' }} />
                </div>
                <div style={{ color: '#6b7280', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>No templates yet</div>
                <div style={{ color: '#9ca3af', fontSize: 11 }}>Save reusable event configurations</div>
              </div>
            ) : (
              <div>
                {templates.map((t, i) => {
                  const meta = evTypeMeta(t.event_type ?? 1);
                  return (
                    <div key={t.id} style={{
                      padding: '13px 18px', display: 'flex', alignItems: 'center', gap: 12,
                      borderBottom: i < templates.length - 1 ? '1px solid #f5f5f5' : 'none',
                      transition: 'background 0.15s',
                    }}>
                      <div style={{ width: 36, height: 36, borderRadius: 8, background: '#52c41a10', border: '1px solid #52c41a20', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <FileTextOutlined style={{ color: '#52c41a', fontSize: 14 }} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 700, fontSize: 13, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.template_name}</div>
                        <Tag icon={meta.icon} color={meta.tag} style={{ borderRadius: 4, fontSize: 10, marginTop: 3 }}>{meta.label}</Tag>
                      </div>
                      <Popconfirm title="Delete this template?" onConfirm={() => deleteTemplateMut.mutate(t.id)} okText="Delete" okButtonProps={{ danger: true }}>
                        <Button size="small" icon={<DeleteOutlined />} type="text" danger />
                      </Popconfirm>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );

  /* ════════════════════════════════════════════════════════════
     TAB 6 — EMERGENCY
  ════════════════════════════════════════════════════════════ */
  const emergencyTab = (
    <div style={{ padding: '24px 28px' }}>
      {/* Emergency Header */}
      <div style={{
        background: 'linear-gradient(135deg, #1a0505 0%, #3b0000 50%, #1a0505 100%)',
        borderRadius: 12, padding: '20px 24px', marginBottom: 20,
        display: 'flex', alignItems: 'center', gap: 16,
        border: '1px solid rgba(239,68,68,0.25)',
        boxShadow: '0 4px 24px rgba(239,68,68,0.12)',
      }}>
        <div style={{
          width: 58, height: 58, borderRadius: 14,
          background: 'rgba(239,68,68,0.18)', border: '1.5px solid rgba(239,68,68,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <AlertOutlined style={{ color: '#f87171', fontSize: 28 }} />
        </div>
        <div>
          <div style={{ color: 'white', fontWeight: 800, fontSize: 18, letterSpacing: '-0.3px', marginBottom: 4 }}>
            Emergency Response Center
          </div>
          <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>
            Initiate mustering, lockdown terminals, or manage emergency protocols
          </div>
        </div>
      </div>

      {/* Rapid Response */}
      <Card styles={{ body: { padding: 0 } }} style={{ marginBottom: 20, border: '1px solid #f0f0f0', borderRadius: 12 }}>
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid #f5f5f5',
          background: 'linear-gradient(90deg, #fff1f0 0%, #fff7f5 100%)',
          borderRadius: '12px 12px 0 0',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: '#f5222d15', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ThunderboltOutlined style={{ color: '#f5222d', fontSize: 16 }} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#141414' }}>Rapid Emergency Response</div>
            <div style={{ fontSize: 11, color: '#8c8c8c' }}>Start a mustering event immediately for the selected emergency type</div>
          </div>
        </div>
        <div style={{ padding: '16px 20px' }}>
          <Row gutter={[12, 12]}>
            {EVENT_TYPES.map(et => {
              const typeColors = { 0: '#f5222d', 1: '#1890ff', 2: '#fa541c', 3: '#faad14', 4: '#722ed1' };
              const c = typeColors[et.value] ?? '#1890ff';
              return (
                <Col xs={24} sm={12} md={8} key={et.value}>
                  <button
                    onClick={() => { startForm.setFieldsValue({ event_type: et.value }); setStartModal(true); }}
                    style={{
                      width: '100%',
                      background: `linear-gradient(135deg, ${c}10 0%, ${c}05 100%)`,
                      border: `1.5px solid ${c}30`,
                      borderRadius: 10, padding: '16px 16px',
                      cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 14,
                      textAlign: 'left', transition: 'all 0.15s',
                    }}>
                    <div style={{
                      width: 44, height: 44, borderRadius: 10,
                      background: `${c}18`, border: `1px solid ${c}30`, flexShrink: 0,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {React.cloneElement(et.icon, { style: { fontSize: 20, color: c } })}
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 13, color: '#141414', marginBottom: 2 }}>{et.label}</div>
                      <div style={{ fontSize: 10, color: c, fontWeight: 700, letterSpacing: 0.2 }}>Start Immediately →</div>
                    </div>
                  </button>
                </Col>
              );
            })}
          </Row>
        </div>
      </Card>

      {/* Terminal Lockdown */}
      <Card styles={{ body: { padding: 0 } }} style={{ border: '1px solid #f0f0f0', borderRadius: 12 }}>
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid #f5f5f5',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: '#f5222d15', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <LockOutlined style={{ color: '#f5222d', fontSize: 16 }} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#141414' }}>Terminal Lockdown</div>
            <div style={{ fontSize: 11, color: '#8c8c8c' }}>Immediately lock or unlock all access control terminals</div>
          </div>
        </div>
        <div style={{ padding: '16px 20px' }}>
          <Row gutter={14}>
            <Col span={12}>
              <button
                onClick={() => modal.confirm({
                  title: 'Lock All Terminals?',
                  icon: <LockOutlined style={{ color: '#f5222d' }} />,
                  content: 'All access control readers will be locked immediately. Personnel will be unable to pass.',
                  okText: 'LOCK ALL', okButtonProps: { danger: true },
                  onOk: () => lockdownMut.mutate({ action: 'lock_all' }),
                })}
                style={{
                  width: '100%', background: 'linear-gradient(135deg, #fff1f0 0%, #fff5f5 100%)',
                  border: '1.5px solid #ffa39e', borderRadius: 10, padding: '18px 16px',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 14, textAlign: 'left',
                }}>
                <div style={{
                  width: 46, height: 46, borderRadius: 11, background: '#f5222d15',
                  flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  border: '1px solid #ffa39e',
                }}>
                  <LockOutlined style={{ color: '#f5222d', fontSize: 20 }} />
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14, color: '#a8071a' }}>Lock All Terminals</div>
                  <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2 }}>Immediately deny all access</div>
                </div>
              </button>
            </Col>
            <Col span={12}>
              <button
                onClick={() => modal.confirm({
                  title: 'Unlock All Terminals?',
                  icon: <UnlockOutlined style={{ color: '#52c41a' }} />,
                  content: 'All access control readers will be unlocked. Normal operation will resume.',
                  okText: 'UNLOCK ALL',
                  okButtonProps: { style: { background: '#52c41a', borderColor: '#52c41a' } },
                  onOk: () => lockdownMut.mutate({ action: 'unlock_all' }),
                })}
                style={{
                  width: '100%', background: 'linear-gradient(135deg, #f6ffed 0%, #f0fff4 100%)',
                  border: '1.5px solid #b7eb8f', borderRadius: 10, padding: '18px 16px',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 14, textAlign: 'left',
                }}>
                <div style={{
                  width: 46, height: 46, borderRadius: 11, background: '#52c41a15',
                  flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  border: '1px solid #b7eb8f',
                }}>
                  <UnlockOutlined style={{ color: '#52c41a', fontSize: 20 }} />
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14, color: '#135200' }}>Unlock All Terminals</div>
                  <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2 }}>Resume normal access control</div>
                </div>
              </button>
            </Col>
          </Row>
        </div>
      </Card>
    </div>
  );

  /* ════════════════════════════════════════════════════════════
     RENDER
  ════════════════════════════════════════════════════════════ */
  const tabItems = [
    { key: 'dashboard', label: <span><DashboardOutlined style={{ marginRight: 5 }} />Dashboard</span>, children: dashboardTab },
    {
      key: 'live',
      label: (
        <span>
          {isActive && <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', background: '#f5222d', marginRight: 6, animation: 'msPulse 1.4s infinite', boxShadow: '0 0 0 2px rgba(245,34,45,0.25)', verticalAlign: 'middle' }} />}
          Live Headcount
          {isActive && <span style={{ marginLeft: 6, fontSize: 10, background: 'rgba(245,34,45,0.15)', color: '#f5222d', borderRadius: 8, padding: '1px 6px', fontWeight: 700 }}>{activeEvents.length}</span>}
        </span>
      ),
      children: liveTab,
    },
    { key: 'zones',     label: <span><EnvironmentOutlined style={{ marginRight: 5 }} />Zones</span>,            children: zonesTab },
    { key: 'events',    label: <span><FileTextOutlined style={{ marginRight: 5 }} />Events</span>,              children: eventsTab },
    { key: 'drills',    label: <span><CalendarOutlined style={{ marginRight: 5 }} />Drills & Templates</span>, children: drillsTab },
    { key: 'emergency', label: <span><ThunderboltOutlined style={{ marginRight: 5 }} />Emergency</span>,        children: emergencyTab },
  ];

  return (
    <div className="mustering-mgmt-module">
      <Card
        title={!embedded ? (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', overflow: 'visible' }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>Mustering &amp; Headcount</div>
              <div style={{ fontSize: 12, color: '#94a3b8', fontWeight: 400, marginTop: 1 }}>
                Personnel accountability and emergency response
              </div>
            </div>
            <Space size={10} style={{ overflow: 'visible' }}>
              <Space size={12} split={<span style={{ color: '#e2e8f0' }}>|</span>} style={{ fontSize: 11, color: '#94a3b8' }}>
                <span style={{ color: isActive ? '#dc2626' : '#94a3b8', fontWeight: isActive ? 600 : 400 }}>
                  {isActive ? `${activeEvents.length} Active` : 'Normal'}
                </span>
              </Space>
              <Button icon={<ReloadOutlined />} size="small"
                onClick={() => { qc.invalidateQueries(['muster-active']); qc.invalidateQueries(['muster-events']); }}>
                Refresh
              </Button>
              <Button icon={<PlayCircleOutlined />} size="small" danger={isActive}
                onClick={() => setStartModal(true)}>
                Start Muster
              </Button>
            </Space>
          </div>
        ) : undefined}
        bordered={!embedded}
        styles={{ header: { overflow: 'visible' }, body: { padding: 0 } }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          size="middle"
          className="ms-tabs-light"
          style={{ paddingLeft: 24, paddingRight: 24 }}
          tabBarStyle={{ marginBottom: 0 }}
        />
      </Card>

      {/* ════════════════ MODALS ════════════════ */}

      <Modal
        open={startModal}
        title={<ModalHeader icon={<AlertOutlined />} title="Start Mustering Event" sub="Initiate personnel accountability check" color="#f5222d" />}
        onCancel={() => { setStartModal(false); startForm.resetFields(); }}
        onOk={() => startForm.validateFields().then(v => startMut.mutate(v))}
        confirmLoading={startMut.isPending}
        okText="Start Event" okButtonProps={{ danger: true }}
        width={460}
      >
        <Form form={startForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="zone_ids"
            label="Coverage Areas (Work Zones)"
            rules={[{ required: true, type: 'array', min: 1, message: 'Select at least one work zone' }]}
            extra={<span>Pick the affected areas, or <a onClick={() => startForm.setFieldsValue({ zone_ids: zones.filter(z => z.zone_kind !== 'MUSTER_POINT').map(z => z.id) })}>select the whole site</a> — a whole-site muster lists everyone on board. People on board whose location is unknown are always included.</span>}
          >
            <Select
              mode="multiple"
              placeholder="Select the affected work zones"
              showSearch
              optionFilterProp="label"
              size="large"
              maxTagCount="responsive"
            >
              {zones
                .filter(z => z.zone_kind !== 'MUSTER_POINT')
                .map(z => (
                  <Select.Option key={z.id} value={z.id} label={z.name}>
                    <span>{z.name}</span>
                    {z.zone_kind && (
                      <span style={{ marginLeft: 6, fontSize: 11, color: '#8c8c8c' }}>
                        [{z.zone_kind}]
                      </span>
                    )}
                  </Select.Option>
                ))
              }
            </Select>
          </Form.Item>
          <Form.Item
            name="muster_zone_ids"
            label="Assembly Points (where personnel report)"
            extra="Pick one or more muster points — personnel go to whichever is nearest and scan in at that point's Horus H1 reader. Leave blank to allow check-in at any muster point."
          >
            <Select
              mode="multiple"
              allowClear
              showSearch
              optionFilterProp="label"
              size="large"
              maxTagCount="responsive"
              placeholder="Select the muster point(s) people evacuate to"
            >
              {zones
                .filter(z => z.zone_kind === 'MUSTER_POINT')
                .map(z => (
                  <Select.Option key={z.id} value={z.id} label={z.name}>{z.name}</Select.Option>
                ))
              }
            </Select>
          </Form.Item>
          <Form.Item name="event_type" label="Emergency Type" rules={[{ required: true }]}>
            <Select size="large">
              {EVENT_TYPES.map(t => (
                <Select.Option key={t.value} value={t.value}>
                  <Space>{t.icon}{t.label}</Space>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="notes" label="Notes / Reason">
            <TextArea rows={2} placeholder="Optional — reason for this event" />
          </Form.Item>
          <Form.Item label="Alert by" extra="Everyone expected gets the instruction; the response team (Settings → WhatsApp & Alerts) gets the situation. An all-clear goes out the same way when you end the event." style={{ marginBottom: 0 }}>
            <Space size={16}>
              <Form.Item name="notify_whatsapp" valuePropName="checked" initialValue noStyle><Checkbox>WhatsApp</Checkbox></Form.Item>
              <Form.Item name="notify_email" valuePropName="checked" initialValue noStyle><Checkbox>Email</Checkbox></Form.Item>
              <Form.Item name="notify_sms" valuePropName="checked" initialValue={false} noStyle><Checkbox>SMS</Checkbox></Form.Item>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={!!endModal}
        title={<ModalHeader icon={<StopOutlined />} title="End Mustering Event" sub="Mark event as complete and record outcome" color="#fa8c16" />}
        onCancel={() => { setEndModal(null); endForm.resetFields(); }}
        onOk={() => endForm.validateFields().then(v => endMut.mutate({ id: endModal, reason: v.reason }))}
        confirmLoading={endMut.isPending}
        okText="End Event" okButtonProps={{ style: { background: '#fa8c16', borderColor: '#fa8c16' } }}
        width={420}
      >
        <Form form={endForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="reason" label="Reason for Ending">
            <TextArea rows={3} placeholder="e.g. All personnel accounted for. Drill complete." />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={!!zoneModal}
        title={<ModalHeader icon={<EnvironmentOutlined />} title={zoneModal?.id ? 'Edit Zone' : 'Add Muster Zone'} sub="Configure assembly point or safe station" color="#52c41a" />}
        onCancel={() => { setZoneModal(null); zoneForm.resetFields(); }}
        onOk={() => zoneForm.validateFields().then(v => zoneModal?.id ? updateZoneMut.mutate({ id: zoneModal.id, ...v }) : createZoneMut.mutate(v))}
        confirmLoading={createZoneMut.isPending || updateZoneMut.isPending}
        okText={zoneModal?.id ? 'Update Zone' : 'Create Zone'}
        width={460}
      >
        <Form form={zoneForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="Zone Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. Muster Station Alpha" size="large" />
          </Form.Item>
          <Row gutter={14}>
            <Col span={12}>
              <Form.Item name="zone_type" label="Zone Type" initialValue={0}>
                <Select size="large">
                  {ZONE_TYPES.map(t => <Select.Option key={t.value} value={t.value}>{t.label}</Select.Option>)}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="capacity" label="Max Capacity">
                <InputNumber style={{ width: '100%' }} min={1} placeholder="e.g. 200" size="large" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="reader_sn" label="Reader Serial No." tooltip="ZKTeco reader SN for auto check-in">
            <Input placeholder="e.g. ABC123456789" />
          </Form.Item>
          <Row gutter={14}>
            <Col span={12}>
              <Form.Item name="latitude" label="Latitude" tooltip="GPS latitude for live map marker">
                <InputNumber style={{ width: '100%' }} placeholder="e.g. 51.5074" step={0.0001} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="longitude" label="Longitude" tooltip="GPS longitude for live map marker">
                <InputNumber style={{ width: '100%' }} placeholder="e.g. -0.1278" step={0.0001} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="Description">
            <TextArea rows={2} placeholder="Location details or instructions..." />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={drillModal}
        title={<ModalHeader icon={<CalendarOutlined />} title="Schedule a Drill" sub="Plan a practice mustering drill" color="#722ed1" />}
        onCancel={() => { setDrillModal(false); drillForm.resetFields(); }}
        onOk={() => drillForm.validateFields().then(v => createDrillMut.mutate({ ...v, scheduled_time: v.scheduled_time.toISOString() }))}
        confirmLoading={createDrillMut.isPending}
        okText="Schedule Drill"
        width={460}
      >
        <Form form={drillForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="zone_id" label="Zone" rules={[{ required: true }]}>
            <Select placeholder="Select zone" showSearch optionFilterProp="label" size="large">
              {zones.map(z => <Select.Option key={z.id} value={z.id} label={z.name}>{z.name}</Select.Option>)}
            </Select>
          </Form.Item>
          <Row gutter={14}>
            <Col span={12}>
              <Form.Item name="event_type" label="Drill Type" initialValue={1}>
                <Select size="large">
                  {EVENT_TYPES.map(t => <Select.Option key={t.value} value={t.value}>{t.label}</Select.Option>)}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="scheduled_time" label="Date & Time" rules={[{ required: true }]}>
                <DatePicker showTime style={{ width: '100%' }} size="large" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="auto_start" label="Trigger Mode" initialValue={true}>
            <Radio.Group>
              <Radio.Button value={true} style={{ height: 'auto', paddingTop: 8, paddingBottom: 8 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 12 }}>Automatic</div>
                  <div style={{ fontSize: 10, color: '#8c8c8c', fontWeight: 400 }}>Starts automatically at scheduled time</div>
                </div>
              </Radio.Button>
              <Radio.Button value={false} style={{ height: 'auto', paddingTop: 8, paddingBottom: 8 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 12 }}>Manual</div>
                  <div style={{ fontSize: 10, color: '#8c8c8c', fontWeight: 400 }}>Requires manual trigger via the Trigger button</div>
                </div>
              </Radio.Button>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={!!templateModal}
        title={<ModalHeader icon={<FileTextOutlined />} title="New Event Template" sub="Save a reusable event configuration" color="#52c41a" />}
        onCancel={() => { setTemplateModal(null); templateForm.resetFields(); }}
        onOk={() => templateForm.validateFields().then(v => createTemplateMut.mutate(v))}
        confirmLoading={createTemplateMut.isPending}
        okText="Create Template"
        width={420}
      >
        <Form form={templateForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="template_name" label="Template Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. Fire Drill — Platform A" size="large" />
          </Form.Item>
          <Form.Item name="event_type" label="Default Event Type" initialValue={1}>
            <Select size="large">
              {EVENT_TYPES.map(t => <Select.Option key={t.value} value={t.value}>{t.label}</Select.Option>)}
            </Select>
          </Form.Item>
          <Space>
            <Form.Item name="notify_sms"   valuePropName="checked" style={{ marginBottom: 0 }}><Checkbox>SMS</Checkbox></Form.Item>
            <Form.Item name="notify_email" valuePropName="checked" style={{ marginBottom: 0 }}><Checkbox>Email</Checkbox></Form.Item>
          </Space>
        </Form>
      </Modal>

      <Modal
        open={!!summaryModal}
        title={<ModalHeader icon={<BarChartOutlined />} title="Event Summary" sub="Final headcount result" color="#1890ff" />}
        onCancel={() => setSummaryModal(null)}
        footer={
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <Space>
              <Button icon={<DownloadOutlined />} onClick={() => downloadEventReport(summaryModal?.event_id, 'excel')}>
                Excel
              </Button>
              <Button icon={<DownloadOutlined />} onClick={() => downloadEventReport(summaryModal?.event_id, 'csv')}>
                CSV
              </Button>
            </Space>
            <Button type="primary" onClick={() => setSummaryModal(null)}>Close</Button>
          </Space>
        }
        width={460}
      >
        {summaryModal && (() => {
          const hc  = summaryModal.final_headcount ?? {};
          const pct = hc.completion_percentage != null ? Math.round(hc.completion_percentage) : null;
          const dur = summaryModal.duration != null
            ? `${Math.floor(summaryModal.duration / 60)}m ${Math.round(summaryModal.duration % 60)}s`
            : null;
          const pctColor = pct == null ? '#1890ff' : pct >= 80 ? '#52c41a' : pct >= 50 ? '#faad14' : '#f5222d';
          return (
            <div style={{ paddingTop: 8 }}>
              {pct != null && (
                <div style={{ textAlign: 'center', padding: '16px 0 20px', borderBottom: '1px solid #f0f0f0', marginBottom: 4 }}>
                  <div style={{ fontSize: 56, fontWeight: 900, color: pctColor, lineHeight: 1, letterSpacing: '-2px' }}>{pct}%</div>
                  <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 4, fontWeight: 600 }}>accounted for</div>
                  {dur && <div style={{ fontSize: 11, color: '#bfbfbf', marginTop: 6, fontFamily: 'monospace' }}>Duration: {dur}</div>}
                </div>
              )}
              {[
                { label: 'Total Expected', v: hc.total_expected ?? '—', color: '#1890ff' },
                { label: 'Confirmed Safe', v: hc.total_safe     ?? '—', color: '#52c41a' },
                { label: 'Missing',        v: hc.total_missing  ?? '—', color: '#f5222d' },
                { label: 'Injured',        v: hc.total_injured  ?? '—', color: '#fa8c16' },
              ].map(s => (
                <div key={s.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '11px 0', borderBottom: '1px solid #f5f5f5' }}>
                  <span style={{ fontSize: 13, color: '#595959' }}>{s.label}</span>
                  <span style={{ fontSize: 24, fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.v}</span>
                </div>
              ))}
            </div>
          );
        })()}
      </Modal>

      <style>{`
        /* Tab bar on white header (embedded mode) */
        .ms-tabs-light .ant-tabs-nav { background: transparent !important; padding: 0 !important; }
        .ms-tabs-light .ant-tabs-nav::before { border-color: #f0f0f0 !important; }
        .ms-tabs-light .ant-tabs-tab { color: rgba(0,0,0,0.45) !important; font-weight: 500 !important; font-size: 13px !important; padding: 10px 16px !important; margin: 0 2px !important; border-radius: 8px 8px 0 0 !important; transition: all 0.18s !important; }
        .ms-tabs-light .ant-tabs-tab:hover { color: rgba(0,0,0,0.75) !important; background: rgba(0,0,0,0.03) !important; }
        .ms-tabs-light .ant-tabs-tab-active { color: #1890ff !important; background: rgba(24,144,255,0.05) !important; font-weight: 700 !important; }
        .ms-tabs-light .ant-tabs-tab-active .ant-tabs-tab-btn { color: #1890ff !important; }
        .ms-tabs-light .ant-tabs-ink-bar { background: #1890ff !important; height: 2.5px !important; border-radius: 2px !important; }
        .ms-tabs-light .ant-tabs-content-holder { background: #f0f2f5 !important; }
        .ms-root-tabs .ant-tabs-nav { background: transparent !important; padding: 0 !important; }
        .ms-root-tabs .ant-tabs-nav::before { border-color: rgba(255,255,255,0.08) !important; }
        .ms-root-tabs .ant-tabs-tab { color: rgba(255,255,255,0.4) !important; font-weight: 500 !important; font-size: 13px !important; padding: 10px 16px !important; margin: 0 2px !important; border-radius: 8px 8px 0 0 !important; transition: all 0.18s !important; }
        .ms-root-tabs .ant-tabs-tab:hover { color: rgba(255,255,255,0.85) !important; background: rgba(255,255,255,0.07) !important; }
        .ms-root-tabs .ant-tabs-tab-active { color: white !important; background: rgba(255,255,255,0.12) !important; font-weight: 700 !important; }
        .ms-root-tabs .ant-tabs-tab-active .ant-tabs-tab-btn { color: white !important; text-shadow: 0 0 20px rgba(255,255,255,0.3); }
        .ms-root-tabs .ant-tabs-ink-bar { background: linear-gradient(90deg,#ef4444,#f97316) !important; height: 2.5px !important; border-radius: 2px !important; }
        .ms-root-tabs .ant-tabs-content-holder { background: #f0f2f5 !important; }
        .ms-row-missing td { background: rgba(245,34,45,0.07) !important; }
        .ms-row-found   td { background: rgba(82,196,26,0.06)  !important; }
        .ms-row-injured td { background: rgba(250,140,22,0.08) !important; }
        .ms-row-missing:hover td { background: rgba(245,34,45,0.14) !important; }
        .ms-row-found:hover   td { background: rgba(82,196,26,0.12)  !important; }
        .ms-row-injured:hover td { background: rgba(250,140,22,0.14) !important; }
        .ms-ev-active td { background: rgba(245,34,45,0.05) !important; border-left: 3px solid #f5222d !important; }
        .ms-ev-active:hover td { background: rgba(245,34,45,0.1) !important; }
        .ms-action-btn:hover { background: rgba(255,255,255,0.06) !important; }
        @keyframes msPulse { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:0.55; transform:scale(1.3); } }
        @keyframes msFadeIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
      `}</style>
    </div>
  );
};

export default MusteringManagement;
