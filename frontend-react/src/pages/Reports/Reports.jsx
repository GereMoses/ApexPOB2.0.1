/**
 * Reports — a curated library grouped by purpose; opening a report gives a full-screen
 * page (report list rail, filters + saved views, key figures, table that fills the
 * screen with column chooser / find / page totals / row details, chart, Export).
 * The catalogue lives in ./reportCatalog.js.
 */
import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Input, Button, Table, Tag, Select, DatePicker, Segmented, Dropdown, Empty, App,
  Tooltip, Drawer, Skeleton, Modal, Form, TimePicker, Popconfirm, Switch, Checkbox, Popover,
} from 'antd';
import {
  SearchOutlined, StarOutlined, StarFilled, ArrowLeftOutlined, DownloadOutlined,
  ReloadOutlined, BarChartOutlined, FilePdfOutlined, FileExcelOutlined, FileTextOutlined,
  ToolOutlined, RightOutlined, ScheduleOutlined, PlayCircleOutlined,
  DeleteOutlined, LockOutlined, AppstoreOutlined, UnorderedListOutlined, MenuFoldOutlined, MenuUnfoldOutlined,
  FullscreenOutlined, FullscreenExitOutlined, FilterOutlined, FileSearchOutlined, HistoryOutlined, ArrowRightOutlined,
  TeamOutlined, FieldTimeOutlined, AimOutlined, SafetyCertificateOutlined, SendOutlined, IdcardOutlined, UserSwitchOutlined,
  AuditOutlined, CalendarOutlined, CheckCircleOutlined, CloseCircleOutlined, NumberOutlined, RiseOutlined, WarningOutlined, LinkOutlined, SaveOutlined, SettingOutlined, SyncOutlined, LineChartOutlined,
} from '@ant-design/icons';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import dayjs from 'dayjs';
import apiService from '../../services/api';
import { REPORT_GROUPS, ALL_REPORTS, findReport } from './reportCatalog';
import CustomReportBuilder from './components/CustomReportBuilder';

const T = {
  bg: '#f6f7f9', card: '#ffffff', ink: '#0f172a', muted: '#64748b', faint: '#94a3b8',
  line: '#e7eaf0', accent: '#2563eb',
};

/* ── per-viewer conveniences (pins + recents) ─────────────────────────────── */
const store = {
  get(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } },
  set(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* private mode */ } },
};
const PINS = 'apx.reports.pins';
const RECENT = 'apx.reports.recent';
const LAYOUT = 'apx.reports.layout';
const DENSITY = 'apx.reports.density';
const PAGESIZE = 'apx.reports.pagesize';
const RAIL = 'apx.reports.rail';
const COLS = 'apx.reports.cols';     // + .<code>: hidden columns
const VIEWS = 'apx.reports.views';   // + .<code>: saved filter sets

const humanize = (k) => k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
const fmtNum = (v) => (typeof v === 'number' ? (Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 1 })) : v);

const STATUS_COLORS = [
  [/present|safe|online|completed|success|approved|boarded|valid|on site|active|fit|mobili[sz]e|arriving/i, 'green'],
  [/late|early|warning|expiring|medium|pending|submitted|in transit|in progress|manifested/i, 'orange'],
  [/absent|missing|offline|expired|failed|overdue|high|no-?show|rejected|cancel|unfit|blocked|demobili[sz]e|leaving/i, 'red'],
];
const statusColor = (v) => (STATUS_COLORS.find(([re]) => re.test(String(v))) || [null, 'default'])[1];

/* ═══════════════════════════════════════════════════════════════════════════ */

// Filters <-> plain JSON (for saved views and shareable links). Preset ranges are
// stored by name so "Last 7 days" stays relative when the view is reopened later.
function serializeFilters(f) {
  const out = { ...f };
  if (f._range) out._range = f._preset && f._preset !== 'custom' ? undefined : f._range.map(d => d.format('YYYY-MM-DD'));
  if (f._date) out._date = f._date.format('YYYY-MM-DD');
  if (f._month) out._month = f._month.format('YYYY-MM');
  return out;
}
function deserializeFilters(o, report) {
  if (!o || typeof o !== 'object') return null;
  const f = { ...initialFilters(report), ...o };
  if (o._preset && o._preset !== 'custom' && PRESETS[o._preset]) f._range = PRESETS[o._preset]();
  else if (Array.isArray(o._range)) f._range = o._range.map(d => dayjs(d));
  if (o._date) f._date = dayjs(o._date);
  if (o._month) f._month = dayjs(o._month + '-01');
  return f;
}

export default function Reports() {
  const [params, setParams] = useSearchParams();
  const code = params.get('r');
  const report = code ? findReport(code) : null;
  const linked = useMemo(() => {
    try { return report && params.get('f') ? deserializeFilters(JSON.parse(params.get('f')), report) : null; } catch { return null; }
  }, [report, params]);
  const [builderOpen, setBuilderOpen] = useState(false);
  const [schedOpen, setSchedOpen] = useState(false);
  const [pins, setPins] = useState(() => store.get(PINS, []));
  // Which reports this user may open / export (null until known = show all).
  const [access, setAccess] = useState(null);
  useEffect(() => {
    apiService.get('/api/v1/report/allowed')
      .then(r => setAccess({ view: new Set(r?.codes || []), exp: new Set(r?.can_export || []) }))
      .catch(() => setAccess(null));
  }, []);
  const canView = (c) => !access || access.view.has(c);
  const canExport = (c) => !access || access.exp.has(c);

  const togglePin = (c) => setPins(prev => {
    const next = prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c];
    store.set(PINS, next);
    return next;
  });
  const open = (c) => {
    store.set(RECENT, [c, ...store.get(RECENT, []).filter(x => x !== c)].slice(0, 6));
    setParams({ r: c });
    window.scrollTo(0, 0);
  };

  return (
    <div className="apx-reports">
      {report && !canView(report.code) ? (
        <div style={{ maxWidth: 640, margin: '80px auto', textAlign: 'center' }}>
          <LockOutlined style={{ fontSize: 34, color: T.faint }} />
          <h2 style={{ marginTop: 12 }}>You don’t have access to this report</h2>
          <div className="apx-sub">Ask an administrator for the matching report permission.</div>
          <Button style={{ marginTop: 18 }} onClick={() => setParams({})}>Back to reports</Button>
        </div>
      ) : report
        ? <ReportView key={report.code + (params.get('f') || '')} report={report} initial={linked}
            pinned={pins.includes(report.code)} canExport={canExport(report.code)} canView={canView}
            onPin={() => togglePin(report.code)} onBack={() => setParams({})} onOpen={open} />
        : <Library pins={pins} onPin={togglePin} onOpen={open} onBuilder={() => setBuilderOpen(true)}
            onScheduled={() => setSchedOpen(true)} canView={canView} />}

      <ScheduledDrawer open={schedOpen} onClose={() => setSchedOpen(false)} onOpenReport={(c) => { setSchedOpen(false); open(c); }} />

      <Drawer title="Custom report" width={1100} open={builderOpen} onClose={() => setBuilderOpen(false)} destroyOnClose>
        <CustomReportBuilder />
      </Drawer>

      <style>{CSS}</style>
    </div>
  );
}

/* ── Library ──────────────────────────────────────────────────────────────── */

function Library({ pins, onPin, onOpen, onBuilder, onScheduled, canView }) {
  const [q, setQ] = useState('');
  const [layout, setLayout] = useState(() => store.get(LAYOUT, 'grid'));
  const [active, setActive] = useState(null);
  const [scheduled, setScheduled] = useState(null);
  const searchRef = useRef(null);
  const recent = store.get(RECENT, []).map(findReport).filter(r => r && canView(r.code));
  const pinned = pins.map(findReport).filter(r => r && canView(r.code));
  const term = q.trim().toLowerCase();
  const visible = ALL_REPORTS.filter(r => canView(r.code)).length;
  const allGroups = REPORT_GROUPS.map(g => ({ ...g, reports: g.reports.filter(r => canView(r.code)) })).filter(g => g.reports.length);
  const groups = allGroups.map(g => ({
    ...g,
    reports: g.reports.filter(r => !term || `${r.title} ${r.desc} ${g.title}`.toLowerCase().includes(term)),
  })).filter(g => g.reports.length && (!active || term || g.key === active));

  useEffect(() => {
    apiService.get('/api/v1/report/scheduled').then(r => setScheduled((r || []).filter(s => s.is_active).length)).catch(() => {});
  }, []);
  // "/" jumps to search, like most dashboards.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === '/' && !/input|textarea/i.test(document.activeElement?.tagName || '')) { e.preventDefault(); searchRef.current?.focus(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  const setLayoutKeep = (v) => { setLayout(v); store.set(LAYOUT, v); };

  return (
    <div className="apx-lib">
      <header className="apx-hero">
        <div className="apx-hero-main">
          <div className="apx-eyebrow"><FileSearchOutlined /> Insights</div>
          <h1 className="apx-hero-title">Reports</h1>
          <div className="apx-hero-sub">Answers about your people, site and safety — all times in site time (Lagos).</div>
          <Input ref={searchRef} allowClear size="large" className="apx-hero-search"
            prefix={<SearchOutlined style={{ color: T.faint, fontSize: 17 }} />}
            suffix={!q && <kbd>/</kbd>}
            placeholder={`Search ${visible} reports — e.g. late, muster, flights…`} value={q} onChange={e => setQ(e.target.value)} />
        </div>
        <div className="apx-hero-side">
          <div className="apx-hero-stats">
            <div><b>{visible}</b><span>Reports</span></div>
            <div><b>{allGroups.length}</b><span>Categories</span></div>
            <div><b>{pinned.length}</b><span>Pinned</span></div>
            <div><b>{scheduled ?? '—'}</b><span>Scheduled</span></div>
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            <Button className="apx-glass" icon={<ScheduleOutlined />} onClick={onScheduled}>Scheduled reports</Button>
            <Button className="apx-light" icon={<ToolOutlined />} onClick={onBuilder}>Custom report</Button>
          </div>
        </div>
      </header>

      <div className="apx-cats">
        <button className={`apx-cat ${!active ? 'on' : ''}`} style={{ '--c': T.accent, '--t': hexA(T.accent, 0.1) }} onClick={() => setActive(null)}>
          <span className="apx-gicon" style={{ '--c': T.accent, '--t': hexA(T.accent, 0.12) }}><AppstoreOutlined /></span>
          <span className="apx-cat-t">All reports</span><span className="apx-cat-n">{visible}</span>
        </button>
        {allGroups.map(g => (
          <button key={g.key} className={`apx-cat ${active === g.key ? 'on' : ''}`} style={{ '--c': g.color, '--t': hexA(g.color, 0.1) }}
            onClick={() => setActive(active === g.key ? null : g.key)}>
            <GIcon g={g} />
            <span className="apx-cat-t">{g.title}</span><span className="apx-cat-n">{g.reports.length}</span>
          </button>
        ))}
      </div>

      <div className="apx-toolbar">
        <div className="apx-quick">
          {!term && pinned.length > 0 && <QuickRow label="Pinned" items={pinned} onOpen={onOpen} icon={<StarFilled style={{ color: '#f59e0b' }} />} />}
          {!term && recent.length > 0 && <QuickRow label="Recent" items={recent} onOpen={onOpen} icon={<HistoryOutlined style={{ color: T.muted }} />} />}
          {(term || (!pinned.length && !recent.length)) && (
            <span className="apx-sub" style={{ margin: 0 }}>
              {term ? `${groups.reduce((n, g) => n + g.reports.length, 0)} reports match “${q}”` : 'Tip: star a report to pin it here.'}
            </span>
          )}
        </div>
        <Segmented value={layout} onChange={setLayoutKeep}
          options={[{ value: 'grid', icon: <AppstoreOutlined /> }, { value: 'list', icon: <UnorderedListOutlined /> }]} />
      </div>

      {groups.length === 0 && <Empty style={{ marginTop: 80 }} description={`No report matches “${q}”`} />}

      {groups.map(g => (
        <section key={g.key} className="apx-group">
          <div className="apx-group-head">
            <GIcon g={g} size={30} />
            <h2>{g.title}</h2>
            <span className="apx-group-n">{g.reports.length}</span>
            <span className="apx-blurb">{g.blurb}</span>
          </div>
          {layout === 'grid' ? (
            <div className="apx-grid">
              {g.reports.map(r => (
                <div key={r.code} className="apx-card" role="button" tabIndex={0}
                  onClick={() => onOpen(r.code)} onKeyDown={e => e.key === 'Enter' && onOpen(r.code)}
                  style={{ '--accent': g.color, '--t': hexA(g.color, 0.08) }}>
                  <div className="apx-card-top">
                    <GIcon g={g} size={38} />
                    <PinStar on={pins.includes(r.code)} onClick={() => onPin(r.code)} />
                  </div>
                  <div className="apx-card-title">{r.title}</div>
                  <div className="apx-card-desc">{r.desc}</div>
                  <div className="apx-card-foot">
                    <span className="apx-meta"><MetaIcon r={r} /> {metaLabel(r)}</span>
                    <span className="apx-card-go">Open <ArrowRightOutlined /></span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="apx-panel">
              {g.reports.map(r => (
                <div key={r.code} className="apx-list-row" role="button" tabIndex={0} style={{ '--accent': g.color }}
                  onClick={() => onOpen(r.code)} onKeyDown={e => e.key === 'Enter' && onOpen(r.code)}>
                  <GIcon g={g} size={30} />
                  <span className="apx-card-title" style={{ width: 250, flexShrink: 0 }}>{r.title}</span>
                  <span className="apx-card-desc">{r.desc}</span>
                  <span className="apx-meta" style={{ width: 120 }}><MetaIcon r={r} /> {metaLabel(r)}</span>
                  <PinStar on={pins.includes(r.code)} onClick={() => onPin(r.code)} />
                  <ArrowRightOutlined style={{ fontSize: 12, color: T.faint }} />
                </div>
              ))}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

const GROUP_ICON = {
  onsite: TeamOutlined, attendance: FieldTimeOutlined, movement: AimOutlined, safety: SafetyCertificateOutlined,
  travel: SendOutlined, visitors: IdcardOutlined, people: UserSwitchOutlined, audit: AuditOutlined,
};
function hexA(hex, a) {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}
function GIcon({ g, size = 34 }) {
  const I = GROUP_ICON[g.key] || FileTextOutlined;
  return (
    <span className="apx-gicon" style={{ '--c': g.color, '--t': hexA(g.color, 0.12), width: size, height: size, fontSize: size * 0.46 }}>
      <I />
    </span>
  );
}
const metaLabel = (r) => ({ none: 'Live now', single: 'One day', range: 'Date range', month: 'Monthly', monthNumber: 'By month' }[r.filters?.date || 'none']);
function MetaIcon({ r }) {
  const d = r.filters?.date || 'none';
  if (d === 'none') return <span className="apx-live-dot" />;
  return <CalendarOutlined />;
}

function PinStar({ on, onClick }) {
  return (
    <span className="apx-pin" onClick={e => { e.stopPropagation(); onClick(); }} title={on ? 'Unpin' : 'Pin'}>
      {on ? <StarFilled style={{ color: '#f59e0b' }} /> : <StarOutlined />}
    </span>
  );
}

function QuickRow({ label, items, onOpen, icon }) {
  return (
    <div className="apx-quick-row">
      <span className="apx-quick-label">{icon} {label}</span>
      {items.map(r => (
        <button key={r.code} className="apx-chip" onClick={() => onOpen(r.code)}>
          <span className="apx-dot" style={{ background: r.group.color }} />{r.title}
        </button>
      ))}
    </div>
  );
}

/* ── Report page ──────────────────────────────────────────────────────────── */

const PRESETS = {
  today: () => [dayjs(), dayjs()],
  yesterday: () => [dayjs().subtract(1, 'day'), dayjs().subtract(1, 'day')],
  '7d': () => [dayjs().subtract(6, 'day'), dayjs()],
  '30d': () => [dayjs().subtract(29, 'day'), dayjs()],
  month: () => [dayjs().startOf('month'), dayjs()],
};

function initialFilters(report) {
  const f = report.filters || {};
  if (f.date === 'range') { const p = f.defaultPreset || '7d'; return { _preset: p, _range: PRESETS[p]() }; }
  if (f.date === 'single') return { _date: f.dateDefault === 'today' ? dayjs() : dayjs().subtract(1, 'day') };
  if (f.date === 'month') return { _month: dayjs() };
  if (f.date === 'monthNumber') return { _monthNo: dayjs().month() + 1 };
  return {};
}

function toApiFilters(report, s) {
  const f = report.filters || {};
  const out = {};
  if (f.date === 'range' && s._range) { out.date_from = s._range[0].format('YYYY-MM-DD'); out.date_to = s._range[1].format('YYYY-MM-DD'); }
  if (f.date === 'single' && s._date) out.date = s._date.format('YYYY-MM-DD');
  if (f.date === 'month' && s._month) out.month = s._month.format('YYYY-MM');
  if (f.date === 'monthNumber' && s._monthNo) out.month = s._monthNo;
  const map = { department: 'department', zone: 'zone_id', company: 'company', person: 'emp_code', search: 'search',
    flightStatus: 'status', journeyStatus: 'status', direction: 'direction', musterEvent: 'event_id', changeType: 'change_type',
    musterStatus: 'status' };
  Object.entries(map).forEach(([k, api]) => { if (s[k] !== undefined && s[k] !== null && s[k] !== '') out[api] = s[k]; });
  return out;
}

const NUMERIC = ['number', 'currency', 'integer'];
const NOT_SUMMABLE = /(^id$|_id$|year|month|^day|pct|percent|rate|age|days_on_board)/i;

function ReportView({ report, initial, pinned, onPin, onBack, onOpen, canView, canExport = true }) {
  const { message } = App.useApp();
  const code = report.code;
  const [filters, setFilters] = useState(() => initial || initialFilters(report));
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => store.get(PAGESIZE, 50));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showChart, setShowChart] = useState(false);
  const [chartType, setChartType] = useState('bar');
  const [exporting, setExporting] = useState(null);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [hidden, setHidden] = useState(() => store.get(`${COLS}.${code}`, []));
  const [density, setDensity] = useState(() => store.get(DENSITY, 'middle'));
  const [find, setFind] = useState('');
  const [detail, setDetail] = useState(null);
  const [focus, setFocus] = useState(false);
  const [railOpen, setRailOpen] = useState(() => store.get(RAIL, true));
  const [autoRefresh, setAutoRefresh] = useState(0);
  const [loadedAt, setLoadedAt] = useState(null);
  const [views, setViews] = useState(() => store.get(`${VIEWS}.${code}`, []));
  const [openGroups, setOpenGroups] = useState([report.group.key]);
  const tableBox = useRef(null);
  const [tableH, setTableH] = useState(480);

  const missing = (report.filters?.required || []).filter(k => !filters[k]);
  const apiFilters = useMemo(() => toApiFilters(report, filters), [report, filters]);

  const load = useCallback(async () => {
    if (missing.length) { setData(null); return; }
    setLoading(true); setError(null);
    try {
      const res = await apiService.post('/api/v1/report/data', {
        report_code: code, filters: apiFilters, page, page_size: pageSize,
      });
      setData(res);
      setLoadedAt(dayjs());
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'Could not load this report');
    } finally {
      setLoading(false);
    }
  }, [code, apiFilters, page, pageSize, missing.length]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!autoRefresh) return undefined;
    const t = setInterval(load, autoRefresh * 1000);
    return () => clearInterval(t);
  }, [autoRefresh, load]);

  // Table fills the rest of the screen (header stays put, rows scroll).
  useLayoutEffect(() => {
    const fit = () => {
      const el = tableBox.current;
      if (!el) return;
      const top = el.getBoundingClientRect().top;
      setTableH(Math.max(260, window.innerHeight - top - 128));
    };
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, [showChart, focus, data, railOpen, missing.length]);

  // Esc leaves full screen.
  useEffect(() => {
    if (!focus) return undefined;
    const onKey = (e) => e.key === 'Escape' && setFocus(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [focus]);

  const set = (k, v) => { setPage(1); setFilters(prev => ({ ...prev, [k]: v })); };

  const exportAs = async (format) => {
    setExporting(format);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('/api/v1/report/export/file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ report_code: code, filters: apiFilters, format }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${report.title.replace(/[^\w]+/g, '_')}_${dayjs().format('YYYYMMDD_HHmm')}.${format}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      message.error(`Export failed: ${e.message}`);
    } finally {
      setExporting(null);
    }
  };

  const copyLink = async () => {
    const url = `${window.location.origin}${window.location.pathname}?r=${encodeURIComponent(code)}`
      + `&f=${encodeURIComponent(JSON.stringify(serializeFilters(filters)))}`;
    try { await navigator.clipboard.writeText(url); message.success('Link copied — it opens this report with these filters'); }
    catch { Modal.info({ title: 'Link to this view', content: <Input.TextArea value={url} autoSize readOnly /> }); }
  };

  const saveView = () => {
    let name = '';
    Modal.confirm({
      title: 'Save these filters as a view',
      icon: <SaveOutlined />,
      content: <Input autoFocus placeholder="e.g. Drilling dept — last 30 days" onChange={e => { name = e.target.value; }} />,
      okText: 'Save',
      onOk: () => {
        if (!name.trim()) return Promise.reject();
        const next = [...views.filter(v => v.name !== name.trim()), { name: name.trim(), f: serializeFilters(filters) }];
        setViews(next); store.set(`${VIEWS}.${code}`, next);
        message.success('View saved');
        return undefined;
      },
    });
  };
  const applyView = (v) => { const f = deserializeFilters(v.f, report); if (f) { setPage(1); setFilters(f); } };
  const deleteView = (name) => { const next = views.filter(v => v.name !== name); setViews(next); store.set(`${VIEWS}.${code}`, next); };

  const allCols = useMemo(() => data?.columns || [], [data]);
  const columns = useMemo(() => allCols.filter(c => !hidden.includes(c.field)).map(c => ({
    title: c.label, dataIndex: c.field, key: c.field, ellipsis: true,
    align: [...NUMERIC, 'percentage'].includes(c.type) ? 'right' : 'left',
    sorter: (a, b) => {
      const x = a[c.field], y = b[c.field];
      return typeof x === 'number' && typeof y === 'number' ? x - y : String(x ?? '').localeCompare(String(y ?? ''));
    },
    render: (v) => renderCell(v, c.type, find),
  })), [allCols, hidden, find]); // eslint-disable-line

  const rows = useMemo(() => {
    const all = data?.data || [];
    const q = find.trim().toLowerCase();
    if (!q) return all;
    return all.filter(r => Object.values(r).some(v => v !== null && v !== undefined && String(v).toLowerCase().includes(q)));
  }, [data, find]);

  const sumCols = columns.filter(c => {
    const t = allCols.find(x => x.field === c.dataIndex)?.type;
    return NUMERIC.includes(t) && !NOT_SUMMABLE.test(c.dataIndex);
  }).map(c => c.dataIndex);

  const kpis = useMemo(() => {
    const s = data?.summary || {};
    const spec = report.kpis;
    const entries = spec
      ? Object.entries(spec).filter(([k]) => s[k] !== undefined && s[k] !== null).map(([k, label]) => [label, s[k]])
      : Object.entries(s).filter(([, v]) => typeof v === 'number').slice(0, 5).map(([k, v]) => [humanize(k), v]);
    const hasTotal = entries.some(([l]) => /total|records|^rows$/i.test(l));
    return [...(hasTotal ? [] : [['Rows', data?.total ?? 0]]), ...entries].slice(0, 6);
  }, [data, report.kpis]);

  const chart = data?.chart_data?.labels?.length && data?.chart_data?.datasets?.[0]
    ? data.chart_data.labels.map((l, i) => ({ name: String(l), value: Number(data.chart_data.datasets[0].data?.[i] ?? 0) }))
    : null;

  const toggleCol = (field, on) => {
    const next = on ? hidden.filter(f => f !== field) : [...hidden, field];
    setHidden(next); store.set(`${COLS}.${code}`, next);
  };
  const columnMenu = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 360, overflow: 'auto', minWidth: 200 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
        <b>Columns</b>
        <a onClick={() => { setHidden([]); store.set(`${COLS}.${code}`, []); }}>Show all</a>
      </div>
      {allCols.map(c => (
        <Checkbox key={c.field} checked={!hidden.includes(c.field)}
          disabled={!hidden.includes(c.field) && allCols.length - hidden.length <= 1}
          onChange={e => toggleCol(c.field, e.target.checked)}>{c.label}</Checkbox>
      ))}
      <div style={{ borderTop: `1px solid ${T.line}`, paddingTop: 8, marginTop: 4 }}>
        <b>Row height</b>
        <Segmented block size="small" style={{ marginTop: 6 }} value={density}
          onChange={(v) => { setDensity(v); store.set(DENSITY, v); }}
          options={[{ label: 'Compact', value: 'small' }, { label: 'Normal', value: 'middle' }, { label: 'Roomy', value: 'large' }]} />
      </div>
    </div>
  );

  const viewItems = [
    ...views.map(v => ({
      key: `v:${v.name}`,
      label: (
        <span style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
          {v.name}
          <DeleteOutlined style={{ color: T.faint }} onClick={(e) => { e.stopPropagation(); deleteView(v.name); }} />
        </span>
      ),
    })),
    ...(views.length ? [{ type: 'divider' }] : []),
    { key: 'save', icon: <SaveOutlined />, label: 'Save current filters…' },
    { key: 'reset', icon: <ReloadOutlined />, label: 'Reset filters' },
  ];

  return (
    <div className={`apx-report ${focus ? 'apx-focus' : ''} ${railOpen ? '' : 'apx-rail-closed'}`}>
      {railOpen && !focus && (
        <aside className="apx-rail">
          <button className="apx-rail-back" onClick={onBack}><ArrowLeftOutlined /> All reports</button>
          {REPORT_GROUPS.map(g => {
            const list = g.reports.filter(r => canView(r.code));
            if (!list.length) return null;
            const isOpen = openGroups.includes(g.key);
            return (
              <div key={g.key} className="apx-rail-group">
                <button className="apx-rail-head" onClick={() => setOpenGroups(isOpen ? openGroups.filter(k => k !== g.key) : [...openGroups, g.key])}>
                  <GIcon g={g} size={24} />
                  <span>{g.title}</span>
                  <RightOutlined className="apx-caret" style={{ transform: isOpen ? 'rotate(90deg)' : 'none' }} />
                </button>
                {isOpen && list.map(r => (
                  <button key={r.code} className={`apx-rail-item ${r.code === code ? 'on' : ''}`} style={{ '--c': g.color, '--t': hexA(g.color, 0.1) }}
                    onClick={() => onOpen(r.code)}>{r.title}</button>
                ))}
              </div>
            );
          })}
        </aside>
      )}

      <div className="apx-report-main">
        <header className="apx-rhero" style={{ '--c': report.group.color, '--glow': hexA(report.group.color, 0.55) }}>
          <div className="apx-rhero-top">
            <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start', minWidth: 0, flex: '1 1 380px' }}>
              {!focus && (
                <Tooltip title={railOpen ? 'Hide report list' : 'Show report list'}>
                  <Button className="apx-glass apx-icon-btn" icon={railOpen ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
                    onClick={() => { setRailOpen(!railOpen); store.set(RAIL, !railOpen); }} />
                </Tooltip>
              )}
              <span className="apx-rhero-icon">{React.createElement(GROUP_ICON[report.group.key] || FileTextOutlined)}</span>
              <div style={{ minWidth: 0 }}>
                <div className="apx-crumb">
                  <a onClick={onBack}>Reports</a> <RightOutlined style={{ fontSize: 9, opacity: .6 }} /> {report.group.title}
                </div>
                <h1 className="apx-rhero-title">{report.title}</h1>
                <div className="apx-rhero-sub">{report.desc}</div>
              </div>
            </div>
            <div className="apx-rhero-actions">
              {loadedAt && (
                <span className="apx-updated">
                  <span className={`apx-live-dot ${autoRefresh ? 'pulse' : ''}`} /> {autoRefresh ? 'Live · ' : ''}Updated {loadedAt.format('HH:mm:ss')}
                </span>
              )}
              <Dropdown menu={{
                selectable: true, selectedKeys: [String(autoRefresh)],
                items: [{ key: '0', label: 'Auto-refresh off' }, { key: '30', label: 'Every 30 seconds' },
                  { key: '60', label: 'Every minute' }, { key: '300', label: 'Every 5 minutes' }],
                onClick: ({ key }) => setAutoRefresh(Number(key)),
              }}>
                <Tooltip title="Auto-refresh">
                  <Button className={`apx-glass ${autoRefresh ? '' : 'apx-icon-btn'}`} icon={<SyncOutlined spin={!!autoRefresh && loading} />}>
                    {autoRefresh ? (autoRefresh < 60 ? `${autoRefresh}s` : `${autoRefresh / 60}m`) : null}
                  </Button>
                </Tooltip>
              </Dropdown>
              <Tooltip title="Refresh now"><Button className="apx-glass apx-icon-btn" icon={<ReloadOutlined />} onClick={load} loading={loading} /></Tooltip>
              <Tooltip title={pinned ? 'Unpin' : 'Pin to the library'}>
                <Button className="apx-glass apx-icon-btn" icon={pinned ? <StarFilled style={{ color: '#fbbf24' }} /> : <StarOutlined />} onClick={onPin} />
              </Tooltip>
              <Tooltip title="Copy a link to this report with these filters"><Button className="apx-glass apx-icon-btn" icon={<LinkOutlined />} onClick={copyLink} /></Tooltip>
              <Tooltip title={focus ? 'Exit full screen (Esc)' : 'Full screen'}>
                <Button className="apx-glass apx-icon-btn" icon={focus ? <FullscreenExitOutlined /> : <FullscreenOutlined />} onClick={() => setFocus(!focus)} />
              </Tooltip>
              {canExport && (
                <Dropdown menu={{
                  items: [
                    { key: 'xlsx', icon: <FileExcelOutlined style={{ color: '#16a34a' }} />, label: 'Excel (.xlsx)' },
                    { key: 'pdf', icon: <FilePdfOutlined style={{ color: '#dc2626' }} />, label: 'PDF' },
                    { key: 'csv', icon: <FileTextOutlined style={{ color: T.muted }} />, label: 'CSV' },
                    { type: 'divider' },
                    { key: 'schedule', icon: <ScheduleOutlined style={{ color: T.accent }} />, label: 'Schedule…' },
                  ],
                  onClick: ({ key }) => (key === 'schedule' ? setScheduleOpen(true) : exportAs(key)),
                }}>
                  <Button className="apx-light" icon={<DownloadOutlined />} loading={!!exporting}>Export</Button>
                </Dropdown>
              )}
            </div>
          </div>

          {missing.length === 0 && (
            <div className="apx-kpis">
              {kpis.map(([label, v], i) => {
                const k = kpiLook(label, i);
                return (
                  <div key={label} className="apx-kpi">
                    <span className="apx-kpi-i" style={{ color: k.color, background: hexA(k.color, 0.18) }}>{k.icon}</span>
                    <div>
                      <div className="apx-kpi-v">{loading && !data ? <Skeleton.Input size="small" active /> : (fmtNum(v) ?? '—')}</div>
                      <div className="apx-kpi-l">{label}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </header>

        <div className="apx-filter-row">
          <FilterBar report={report} filters={filters} set={set} setFilters={(f) => { setPage(1); setFilters(f); }} />
          <div className="apx-filter-actions">
            {chart && (
              <Button icon={<BarChartOutlined />} type={showChart ? 'primary' : 'default'} ghost={showChart}
                onClick={() => setShowChart(v => !v)}>Chart</Button>
            )}
            <Dropdown trigger={['click']} menu={{
              items: viewItems,
              onClick: ({ key }) => {
                if (key === 'save') saveView();
                else if (key === 'reset') { setPage(1); setFilters(initialFilters(report)); }
                else applyView(views.find(v => `v:${v.name}` === key));
              },
            }}>
              <Button icon={<SaveOutlined />}>Views{views.length ? ` (${views.length})` : ''}</Button>
            </Dropdown>
          </div>
        </div>
        <ScheduleModal open={scheduleOpen} onClose={() => setScheduleOpen(false)} report={report} filters={filters} />

        {missing.length > 0 ? (
          <div className="apx-panel" style={{ padding: 56 }}>
            <Empty description={`Choose ${missing.map(k => ({ person: 'a person', musterEvent: 'a muster event' }[k] || k)).join(' and ')} above to run this report.`} />
          </div>
        ) : (
          <>
            {showChart && chart && (
              <div className="apx-panel" style={{ padding: '12px 18px 6px', marginBottom: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
                  <Segmented size="small" value={chartType} onChange={setChartType}
                    options={[{ value: 'bar', icon: <BarChartOutlined /> }, { value: 'line', icon: <LineChartOutlined /> }]} />
                </div>
                <ResponsiveContainer width="100%" height={240}>
                  {chartType === 'line' ? (
                    <LineChart data={chart} margin={{ top: 4, right: 12, left: -12, bottom: 4 }}>
                      <CartesianGrid vertical={false} stroke={T.line} />
                      <XAxis dataKey="name" tick={{ fontSize: 12, fill: T.muted }} interval="preserveStartEnd" />
                      <YAxis tick={{ fontSize: 12, fill: T.muted }} allowDecimals={false} />
                      <RTooltip />
                      <Line type="monotone" dataKey="value" stroke={report.group.color} strokeWidth={2.5} dot={chart.length < 40} />
                    </LineChart>
                  ) : (
                    <BarChart data={chart} margin={{ top: 4, right: 8, left: -12, bottom: 4 }}>
                      <CartesianGrid vertical={false} stroke={T.line} />
                      <XAxis dataKey="name" tick={{ fontSize: 12, fill: T.muted }} interval={chart.length > 24 ? 'preserveStartEnd' : 0}
                        angle={chart.length > 8 ? -30 : 0} textAnchor={chart.length > 8 ? 'end' : 'middle'} height={chart.length > 8 ? 60 : 30} />
                      <YAxis tick={{ fontSize: 12, fill: T.muted }} allowDecimals={false} />
                      <RTooltip cursor={{ fill: 'rgba(37,99,235,0.06)' }} />
                      <Bar dataKey="value" fill={report.group.color} radius={[4, 4, 0, 0]} maxBarSize={44} />
                    </BarChart>
                  )}
                </ResponsiveContainer>
              </div>
            )}

            <div className="apx-panel">
              <div className="apx-table-bar">
                <Input allowClear size="small" prefix={<SearchOutlined style={{ color: T.faint }} />} style={{ width: 260 }}
                  placeholder="Find in these rows…" value={find} onChange={e => setFind(e.target.value)} />
                {find && <span className="apx-sub" style={{ margin: 0, fontSize: 12.5 }}>{rows.length} of {(data?.data || []).length} rows on this page match</span>}
                <span style={{ flex: 1 }} />
                <span className="apx-sub" style={{ margin: 0, fontSize: 12.5 }}>Click a row for details</span>
                <Popover trigger="click" placement="bottomRight" content={columnMenu}>
                  <Button size="small" icon={<SettingOutlined />}>
                    Columns{hidden.length ? ` (${allCols.length - hidden.filter(h => allCols.some(c => c.field === h)).length}/${allCols.length})` : ''}
                  </Button>
                </Popover>
              </div>
              <div ref={tableBox}>
                {error ? (
                  <div style={{ padding: 48 }}><Empty description={<span style={{ color: '#dc2626' }}>{error}</span>} /></div>
                ) : (
                  <Table
                    rowKey={(r, i) => r.id ?? r.emp_code ?? i}
                    size={density}
                    columns={columns}
                    dataSource={rows}
                    loading={loading}
                    scroll={{ x: 'max-content', y: tableH }}
                    onRow={(r) => ({ onClick: () => setDetail(r), style: { cursor: 'pointer' } })}
                    locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={find ? 'No row on this page matches' : 'Nothing for these filters'} /> }}
                    summary={sumCols.length && rows.length > 1 ? (pageRows) => (
                      <Table.Summary fixed>
                        <Table.Summary.Row className="apx-total">
                          {columns.map((c, i) => (
                            <Table.Summary.Cell key={c.key} index={i} align={c.align}>
                              {sumCols.includes(c.dataIndex)
                                ? fmtNum(pageRows.reduce((t, r) => t + (Number(r[c.dataIndex]) || 0), 0))
                                : i === 0 ? <b>Page total</b> : null}
                            </Table.Summary.Cell>
                          ))}
                        </Table.Summary.Row>
                      </Table.Summary>
                    ) : undefined}
                    pagination={{
                      current: page, pageSize, total: data?.total || 0, showSizeChanger: true,
                      pageSizeOptions: [25, 50, 100, 200, 500],
                      showTotal: (t, r) => `${r[0]}–${r[1]} of ${t.toLocaleString()}`,
                      onChange: (p, s) => { setPage(p); setPageSize(s); store.set(PAGESIZE, s); },
                    }}
                  />
                )}
              </div>
            </div>
          </>
        )}
      </div>

      <Drawer title={report.title} width={460} open={!!detail} onClose={() => setDetail(null)}>
        {detail && (
          <div className="apx-detail">
            {allCols.map(c => (
              <div key={c.field} className="apx-detail-row">
                <span>{c.label}</span>
                <div>{renderCell(detail[c.field], c.type)}</div>
              </div>
            ))}
          </div>
        )}
      </Drawer>
    </div>
  );
}

// Icon + colour for a key figure, from its label.
function kpiLook(label, i) {
  const l = label.toLowerCase();
  if (i === 0 || /rows|records|total/.test(l)) return { icon: <NumberOutlined />, color: '#60a5fa' };
  if (/present|safe|arriv|boarded|completed|coverage|runs$|sent|on time/.test(l)) return { icon: <CheckCircleOutlined />, color: '#34d399' };
  if (/absent|missing|fail|no-show|without|high risk|concern|offline/.test(l)) return { icon: <CloseCircleOutlined />, color: '#f87171' };
  if (/\blate\b|early|overtime|leave|\bleft\b|pending/.test(l)) return { icon: <WarningOutlined />, color: '#fbbf24' };
  return { icon: <RiseOutlined />, color: '#a78bfa' };
}

function Highlight({ text, q }) {
  const i = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (i < 0) return text;
  return <>{text.slice(0, i)}<mark className="apx-mark">{text.slice(i, i + q.length)}</mark>{text.slice(i + q.length)}</>;
}

function renderCell(v, type, find = '') {
  if (v === null || v === undefined || v === '') return <span style={{ color: T.faint }}>—</span>;
  switch (type) {
    case 'status': return <Tag color={statusColor(v)} style={{ marginInlineEnd: 0 }}>{String(v)}</Tag>;
    case 'boolean': return v ? 'Yes' : 'No';
    case 'percentage': return `${Number(v).toFixed(1)}%`;
    case 'currency': return `₦${Number(v).toLocaleString()}`;
    case 'number': case 'integer': return fmtNum(Number(v));
    case 'date': return String(v).slice(0, 10);
    case 'datetime': return String(v).replace('T', ' ').slice(0, 16);   // already site time
    default:
      if (typeof v === 'string' && STATUS_COLORS.some(([re]) => re.test(v)) && v.length <= 20 && /^[A-Za-z -]+$/.test(v)) {
        return <Tag color={statusColor(v)} style={{ marginInlineEnd: 0 }}>{v}</Tag>;
      }
      return find ? <Highlight text={String(v)} q={find} /> : String(v);
  }
}

/* ── Filters ──────────────────────────────────────────────────────────────── */

function useLookups(extra) {
  const [depts, setDepts] = useState([]);
  const [zones, setZones] = useState([]);
  const [events, setEvents] = useState([]);
  useEffect(() => {
    if (extra.includes('department')) apiService.get('/api/v1/departments/')
      .then(r => setDepts((Array.isArray(r) ? r : r?.data || []).filter(d => d.is_active !== false).map(d => d.name).sort())).catch(() => {});
    if (extra.includes('zone')) apiService.get('/api/v1/zones/')
      .then(r => setZones((Array.isArray(r) ? r : r?.data || []).map(z => ({ value: z.id, label: z.name })))).catch(() => {});
    if (extra.includes('musterEvent')) apiService.get('/api/mustering/events/')
      .then(r => setEvents((r?.data || []).map(e => ({
        value: e.id, label: `#${e.id} · ${dayjs(e.start_time).format('DD MMM YYYY HH:mm')}${e.zone_name ? ` · ${e.zone_name}` : ''}`,
      })))).catch(() => {});
  }, [extra.join(',')]); // eslint-disable-line
  return { depts, zones, events };
}

function PersonPicker({ value, onChange }) {
  const [opts, setOpts] = useState([]);
  const search = async (q) => {
    if (!q || q.length < 2) return;
    try {
      const r = await apiService.get('/api/v1/personnel/', { search: q, page_size: 20 });
      setOpts((r?.results || []).map(p => ({ value: p.emp_code, label: `${p.full_name || p.first_name} · ${p.emp_code}` })));
    } catch { /* best effort */ }
  };
  return <Select showSearch allowClear placeholder="Person…" style={{ width: 240 }} filterOption={false}
    onSearch={search} options={opts} value={value} onChange={onChange} notFoundContent="Type 2+ letters" />;
}

function FilterBar({ report, filters, set, setFilters }) {
  const f = report.filters || {};
  const extra = f.extra || [];
  const { depts, zones, events } = useLookups(extra);
  if (f.date === 'none' && extra.length === 0) return <div className="apx-filters apx-filters-empty">No filters — this report shows the current state.</div>;

  return (
    <div className="apx-filters">
      <FilterOutlined style={{ color: T.faint, marginLeft: 4 }} />
      {f.date === 'range' && (
        <>
          <Segmented value={filters._preset || 'custom'}
            options={[{ label: 'Today', value: 'today' }, { label: 'Yesterday', value: 'yesterday' },
              { label: '7 days', value: '7d' }, { label: '30 days', value: '30d' }, { label: 'This month', value: 'month' },
              { label: 'Custom', value: 'custom' }]}
            onChange={(p) => p !== 'custom' && setFilters({ ...filters, _preset: p, _range: PRESETS[p]() })} />
          <DatePicker.RangePicker value={filters._range} allowClear={false} format="DD MMM YYYY"
            onChange={(r) => r && setFilters({ ...filters, _preset: 'custom', _range: r })} />
        </>
      )}
      {f.date === 'single' && (
        <DatePicker value={filters._date} allowClear={false} format="ddd DD MMM YYYY" onChange={(d) => d && set('_date', d)} />
      )}
      {f.date === 'month' && (
        <DatePicker picker="month" value={filters._month} allowClear={false} format="MMMM YYYY" onChange={(d) => d && set('_month', d)} />
      )}
      {f.date === 'monthNumber' && (
        <Select value={filters._monthNo} style={{ width: 150 }} onChange={(v) => set('_monthNo', v)}
          options={Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: dayjs().month(i).format('MMMM') }))} />
      )}

      {extra.includes('department') && (
        <Select allowClear showSearch placeholder="Department" style={{ width: 220 }} value={filters.department}
          onChange={(v) => set('department', v)} options={depts.map(d => ({ value: d, label: d }))} />
      )}
      {extra.includes('zone') && (
        <Select allowClear showSearch optionFilterProp="label" placeholder="Zone" style={{ width: 180 }} value={filters.zone}
          onChange={(v) => set('zone', v)} options={zones} />
      )}
      {extra.includes('company') && (
        <Input allowClear placeholder="Company" style={{ width: 180 }} value={filters.company}
          onChange={(e) => set('company', e.target.value || undefined)} />
      )}
      {extra.includes('person') && <PersonPicker value={filters.person} onChange={(v) => set('person', v)} />}
      {extra.includes('search') && (
        <Input allowClear prefix={<SearchOutlined style={{ color: T.faint }} />} placeholder="Search…" style={{ width: 220 }}
          value={filters.search} onChange={(e) => set('search', e.target.value || undefined)} />
      )}
      {extra.includes('changeType') && (
        <Segmented value={filters.changeType || ''} onChange={(v) => set('changeType', v || undefined)}
          options={[{ label: 'All', value: '' }, { label: 'Arrived', value: 'MOBILIZE' }, { label: 'Left', value: 'DEMOBILIZE' }]} />
      )}
      {extra.includes('direction') && (
        <Segmented value={filters.direction || ''} onChange={(v) => set('direction', v || undefined)}
          options={[{ label: 'All', value: '' }, { label: 'Arriving', value: 'INBOUND' }, { label: 'Leaving', value: 'OUTBOUND' }]} />
      )}
      {extra.includes('flightStatus') && (
        <Select allowClear placeholder="Status" style={{ width: 160 }} value={filters.flightStatus}
          onChange={(v) => set('flightStatus', v)}
          options={['SCHEDULED', 'CONFIRMED', 'IN_TRANSIT', 'COMPLETED', 'CANCELLED'].map(s => ({ value: s, label: humanize(s.toLowerCase()) }))} />
      )}
      {extra.includes('journeyStatus') && (
        <Select allowClear placeholder="Status" style={{ width: 170 }} value={filters.journeyStatus}
          onChange={(v) => set('journeyStatus', v)}
          options={['DRAFT', 'SUBMITTED', 'APPROVED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'REJECTED'].map(s => ({ value: s, label: humanize(s.toLowerCase()) }))} />
      )}
      {extra.includes('musterStatus') && (
        <Segmented value={filters.musterStatus || ''} onChange={(v) => set('musterStatus', v || undefined)}
          options={[{ label: 'All', value: '' }, { label: 'Safe', value: 'safe' }, { label: 'Missing', value: 'missing' }]} />
      )}
      {extra.includes('musterEvent') && (
        <Select allowClear placeholder="Muster event" style={{ width: 300 }} value={filters.musterEvent}
          onChange={(v) => set('musterEvent', v)} options={events} notFoundContent="No muster events yet" />
      )}
    </div>
  );
}

/* ── Scheduling ───────────────────────────────────────────────────────────── */

const RELATIVE = {
  range: [['yesterday', 'Yesterday'], ['7d', 'Last 7 days'], ['30d', 'Last 30 days'], ['last_week', 'Last week (Mon–Sun)'],
          ['month', 'This month so far'], ['last_month', 'Last month']],
  single: [['yesterday', 'Yesterday'], ['today', 'Today']],
  month: [['month', 'This month'], ['last_month', 'Last month']],
  monthNumber: [['month', 'This month'], ['last_month', 'Last month']],
};

function ScheduleModal({ open, onClose, report, filters }) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const mode = report.filters?.date || 'none';
  const freq = Form.useWatch('frequency', form);
  useEffect(() => {
    if (open) form.setFieldsValue({
      name: report.title, frequency: 'daily', time: dayjs().hour(7).minute(0), weekday: 1, format: 'xlsx', emails: [],
      relative: mode === 'range' ? (filters._preset && filters._preset !== 'custom' ? filters._preset : '7d')
        : mode === 'single' ? 'yesterday' : 'month',
    });
  }, [open]); // eslint-disable-line

  const save = async () => {
    const v = await form.validateFields();
    const fixed = toApiFilters({ ...report, filters: { ...report.filters, date: 'none' } }, filters);
    setSaving(true);
    try {
      await apiService.post('/api/v1/report/scheduled', {
        report_code: report.code, name: v.name, frequency: v.frequency, time: v.time.format('HH:mm'),
        weekday: v.frequency === 'weekly' ? v.weekday : null, format: v.format, emails: v.emails || [],
        filters: fixed, date_mode: mode, relative: mode === 'none' ? null : v.relative,
      });
      message.success('Scheduled — find it under Reports → Scheduled');
      onClose();
    } catch (e) {
      message.error(e?.response?.data?.detail || e?.message || 'Could not schedule');
    } finally { setSaving(false); }
  };

  return (
    <Modal title={<span><ScheduleOutlined style={{ color: T.accent }} /> Schedule “{report.title}”</span>}
      open={open} onCancel={onClose} onOk={save} okText="Schedule" confirmLoading={saving} destroyOnClose>
      <Form form={form} layout="vertical" requiredMark={false} style={{ marginTop: 12 }}>
        <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Form.Item name="frequency" label="Every">
            <Segmented options={[{ label: 'Day', value: 'daily' }, { label: 'Week', value: 'weekly' }, { label: 'Month (1st)', value: 'monthly' }]} />
          </Form.Item>
          {freq === 'weekly' && (
            <Form.Item name="weekday" label="On">
              <Select style={{ width: 130 }} options={['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                .map((d, i) => ({ value: i + 1, label: d }))} />
            </Form.Item>
          )}
          <Form.Item name="time" label="At (site time)"><TimePicker format="HH:mm" minuteStep={5} allowClear={false} /></Form.Item>
        </div>
        {mode !== 'none' && (
          <Form.Item name="relative" label="Period covered by each run"
            tooltip="Saved relative to the run date, so each run reports a fresh period.">
            <Select options={(RELATIVE[mode] || []).map(([value, label]) => ({ value, label }))} />
          </Form.Item>
        )}
        <Form.Item name="format" label="Format">
          <Segmented options={[{ label: 'Excel', value: 'xlsx' }, { label: 'PDF', value: 'pdf' }, { label: 'CSV', value: 'csv' }]} />
        </Form.Item>
        <Form.Item name="emails" label="Email to" extra="Type an address and press Enter. Leave empty to only keep the file for download.">
          <Select mode="tags" tokenSeparators={[',', ' ', ';']} placeholder="name@company.com" open={false} />
        </Form.Item>
        <div className="apx-sub" style={{ fontSize: 12.5 }}>Other filters currently set on this report (department, zone…) are kept.</div>
      </Form>
    </Modal>
  );
}

function ScheduledDrawer({ open, onClose, onOpenReport }) {
  const { message } = App.useApp();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(null);
  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await apiService.get('/api/v1/report/scheduled') || []); }
    catch { setRows([]); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { if (open) load(); }, [open, load]);

  const act = async (id, fn) => {
    setBusy(id);
    try { await fn(); await load(); } catch (e) { message.error(e?.response?.data?.detail || e?.message || 'Failed'); }
    finally { setBusy(null); }
  };
  const download = async (s) => {
    const res = await fetch(`/api/v1/report/scheduled/${s.id}/file`, { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });
    if (!res.ok) { message.error('No file yet — run it first'); return; }
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${s.name.replace(/[^\w]+/g, '_')}.${s.format}`;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
  };
  const statusTag = (s) => {
    if (!s.last_run) return <Tag>Not run yet</Tag>;
    const c = { ok: 'green', emailed: 'green', email_failed: 'orange', failed: 'red' }[s.last_status] || 'default';
    const l = { ok: 'Ran', emailed: 'Emailed', email_failed: 'Email failed', failed: 'Failed' }[s.last_status] || s.last_status;
    return <Tooltip title={s.last_error || ''}><Tag color={c}>{l}</Tag></Tooltip>;
  };

  return (
    <Drawer title={<span><ScheduleOutlined /> Scheduled reports</span>} width={760} open={open} onClose={onClose}
      extra={<Button icon={<ReloadOutlined />} onClick={load} loading={loading} />}>
      {rows.length === 0 && !loading && (
        <Empty description={<span>No scheduled reports yet.<br />Open a report and choose <b>Export → Schedule…</b></span>} />
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {rows.map(s => {
          const r = findReport(s.report_code);
          return (
            <div key={s.id} className="apx-panel" style={{ padding: 14, opacity: s.is_active ? 1 : 0.6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 650, fontSize: 15 }}>{s.name} {statusTag(s)}</div>
                  <div className="apx-sub" style={{ fontSize: 13 }}>
                    <a onClick={() => onOpenReport(s.report_code)}>{r?.title || s.report_code}</a>
                    {' · '}{s.schedule}{' · '}{s.format.toUpperCase()}
                    {s.emails?.length ? ` · to ${s.emails.join(', ')}` : ' · download only'}
                  </div>
                  <div className="apx-sub" style={{ fontSize: 12.5 }}>
                    {s.last_run ? `Last run ${dayjs(s.last_run + 'Z').format('DD MMM HH:mm')}${s.last_rows != null ? ` · ${s.last_rows} rows` : ''}` : 'Never run'}
                    {s.is_active && s.next_run ? ` · next ${dayjs(s.next_run + 'Z').format('ddd DD MMM HH:mm')}` : ''}
                  </div>
                  {s.last_error && <div style={{ color: '#b45309', fontSize: 12.5, marginTop: 4 }}>{s.last_error}</div>}
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                  <Tooltip title={s.is_active ? 'Active' : 'Paused'}>
                    <Switch size="small" checked={s.is_active} loading={busy === s.id}
                      onChange={(v) => act(s.id, () => apiService.patch(`/api/v1/report/scheduled/${s.id}`, { is_active: v }))} />
                  </Tooltip>
                  <Tooltip title="Run now"><Button size="small" icon={<PlayCircleOutlined />} loading={busy === s.id}
                    onClick={() => act(s.id, () => apiService.post(`/api/v1/report/scheduled/${s.id}/run`))} /></Tooltip>
                  <Tooltip title="Download last file"><Button size="small" icon={<DownloadOutlined />} disabled={!s.has_file}
                    onClick={() => download(s)} /></Tooltip>
                  <Popconfirm title="Delete this schedule?" onConfirm={() => act(s.id, () => apiService.delete(`/api/v1/report/scheduled/${s.id}`))}>
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Drawer>
  );
}

/* ── Styles ───────────────────────────────────────────────────────────────── */

const CSS = `
.apx-reports { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: ${T.ink};
  min-height: calc(100vh - 56px); padding: 20px 24px 32px;
  background: radial-gradient(1200px 400px at 100% 0%, rgba(37,99,235,.07), transparent 60%), linear-gradient(180deg, #eef2f8 0%, #f5f7fb 320px); }
.apx-reports kbd { font-family: inherit; font-size: 11px; background: #f1f5f9; color: ${T.muted}; border: 1px solid ${T.line}; border-bottom-width: 2px; border-radius: 5px; padding: 0 6px; }
.apx-sub { color: ${T.muted}; font-size: 14px; margin-top: 4px; }
.apx-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.apx-gicon { display: inline-grid; place-items: center; flex-shrink: 0; border-radius: 10px; color: var(--c); background: var(--t); }

/* hero (library) */
.apx-hero { position: relative; overflow: hidden; display: flex; justify-content: space-between; gap: 28px; flex-wrap: wrap;
  padding: 30px 34px; border-radius: 20px; color: #fff; margin-bottom: 18px;
  background: radial-gradient(600px 260px at 88% -30%, rgba(56,189,248,.45), transparent 60%),
              radial-gradient(500px 240px at 10% 130%, rgba(99,102,241,.35), transparent 60%),
              linear-gradient(135deg, #0b1b36 0%, #12305e 55%, #174a8b 100%);
  box-shadow: 0 18px 40px -18px rgba(15,35,80,.55); }
.apx-hero::after { content: ''; position: absolute; inset: 0; pointer-events: none;
  background-image: linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
  background-size: 28px 28px; mask-image: linear-gradient(90deg, transparent, #000 60%); -webkit-mask-image: linear-gradient(90deg, transparent, #000 60%); }
.apx-hero-main { flex: 1 1 460px; position: relative; z-index: 1; }
.apx-hero-side { position: relative; z-index: 1; display: flex; flex-direction: column; justify-content: space-between; gap: 18px; }
.apx-eyebrow { display: inline-flex; gap: 8px; align-items: center; font-size: 12px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
  color: #7dd3fc; background: rgba(125,211,252,.12); border: 1px solid rgba(125,211,252,.25); padding: 4px 10px; border-radius: 999px; }
.apx-hero-title { font-size: 34px; font-weight: 800; letter-spacing: -0.8px; margin: 12px 0 4px; color: #fff; }
.apx-hero-sub { color: rgba(226,232,240,.8); font-size: 14.5px; margin-bottom: 20px; }
.apx-hero-search.ant-input-affix-wrapper { max-width: 560px; height: 50px; border-radius: 14px; border: 0; padding: 0 16px;
  box-shadow: 0 10px 30px -10px rgba(0,0,0,.45); font-size: 15px; }
.apx-hero-stats { display: grid; grid-template-columns: repeat(4, minmax(84px, 1fr)); gap: 10px; }
.apx-hero-stats > div { background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.12); border-radius: 14px; padding: 12px 14px; backdrop-filter: blur(6px); }
.apx-hero-stats b { display: block; font-size: 24px; font-weight: 800; letter-spacing: -0.5px; color: #fff; line-height: 1.1; }
.apx-hero-stats span { font-size: 12px; color: rgba(226,232,240,.7); }
.apx-glass.ant-btn { background: rgba(255,255,255,.1) !important; border: 1px solid rgba(255,255,255,.2) !important; color: #fff !important; border-radius: 10px; }
.apx-glass.ant-btn:hover { background: rgba(255,255,255,.2) !important; }
.apx-icon-btn.ant-btn { width: 36px; padding: 0; }
.apx-light.ant-btn { background: #fff !important; border: 0 !important; color: #0b1b36 !important; font-weight: 600; border-radius: 10px;
  box-shadow: 0 6px 18px -6px rgba(0,0,0,.4); }
.apx-light.ant-btn:hover { background: #e8f1ff !important; }

/* categories */
.apx-cats { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
.apx-cat { all: unset; box-sizing: border-box; cursor: pointer; display: inline-flex; align-items: center; gap: 9px; padding: 6px 10px 6px 6px; white-space: nowrap;
  background: #fff; border: 1px solid ${T.line}; border-radius: 999px; transition: all .15s; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
.apx-cat .apx-gicon { width: 30px !important; height: 30px !important; font-size: 14px !important; border-radius: 50%; }
.apx-cat:hover { border-color: var(--c); transform: translateY(-1px); box-shadow: 0 8px 20px -10px rgba(15,23,42,.25); }
.apx-cat.on { border-color: var(--c); background: var(--t); box-shadow: 0 0 0 3px var(--t); }
.apx-cat-t { font-size: 13.5px; font-weight: 600; color: ${T.ink}; }
.apx-cat-n { font-size: 12px; font-weight: 700; color: var(--c); background: var(--t); border-radius: 999px; padding: 1px 8px; }

.apx-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 18px; flex-wrap: wrap; }
.apx-quick { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.apx-quick-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.apx-quick-label { font-size: 11.5px; font-weight: 650; color: ${T.muted}; text-transform: uppercase; letter-spacing: .08em; width: 84px; display: inline-flex; gap: 6px; align-items: center; }
.apx-chip { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; padding: 5px 12px;
  background: #fff; border: 1px solid ${T.line}; border-radius: 999px; font-size: 13px; color: ${T.ink}; transition: all .15s; }
.apx-chip:hover { border-color: ${T.accent}; color: ${T.accent}; box-shadow: 0 4px 12px -6px rgba(37,99,235,.5); }

/* groups + cards */
.apx-group { margin-bottom: 30px; }
.apx-group-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.apx-group-head h2 { font-size: 17px; font-weight: 750; margin: 0; color: ${T.ink}; letter-spacing: -0.2px; }
.apx-group-n { font-size: 12px; font-weight: 700; color: ${T.muted}; background: #e9edf3; border-radius: 999px; padding: 1px 8px; }
.apx-blurb { color: ${T.muted}; font-size: 13px; }
.apx-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: 14px; }
.apx-card { position: relative; overflow: hidden; background: #fff; border: 1px solid ${T.line}; border-radius: 16px; padding: 16px 16px 14px;
  cursor: pointer; transition: transform .18s, box-shadow .18s, border-color .18s; display: flex; flex-direction: column; gap: 6px; outline: none;
  box-shadow: 0 1px 2px rgba(15,23,42,.04); }
.apx-card::before { content: ''; position: absolute; inset: 0 0 auto 0; height: 3px; background: var(--accent); transform: scaleX(0); transform-origin: left; transition: transform .25s; }
.apx-card::after { content: ''; position: absolute; right: -36px; bottom: -36px; width: 96px; height: 96px; border-radius: 50%; background: var(--t); opacity: 0; transition: opacity .25s, transform .3s; }
.apx-card:hover, .apx-card:focus-visible { transform: translateY(-3px); box-shadow: 0 16px 32px -14px rgba(15,23,42,.22); border-color: transparent; }
.apx-card:hover::before, .apx-card:focus-visible::before { transform: scaleX(1); }
.apx-card:hover::after { opacity: 1; transform: scale(1.4); }
.apx-card > * { position: relative; z-index: 1; }
.apx-card-top { display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; margin-bottom: 4px; }
.apx-card-title { font-weight: 700; font-size: 15px; color: ${T.ink}; letter-spacing: -0.1px; }
.apx-card-desc { color: ${T.muted}; font-size: 13px; line-height: 1.5; flex: 1; }
.apx-card-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; padding-top: 10px; border-top: 1px dashed ${T.line}; }
.apx-meta { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: ${T.muted}; }
.apx-card-go { color: var(--accent); font-size: 12.5px; font-weight: 650; display: inline-flex; gap: 6px; align-items: center; opacity: 0; transform: translateX(-4px); transition: all .18s; }
.apx-card:hover .apx-card-go, .apx-card:focus-visible .apx-card-go { opacity: 1; transform: none; }
.apx-pin { color: ${T.faint}; padding: 4px; border-radius: 8px; line-height: 1; }
.apx-pin:hover { color: #f59e0b; background: #fff7e6; }
.apx-live-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; display: inline-block; box-shadow: 0 0 0 3px rgba(34,197,94,.18); }
.apx-live-dot.pulse { animation: apxPulse 1.6s infinite; }
@keyframes apxPulse { 0% { box-shadow: 0 0 0 0 rgba(34,197,94,.6); } 70% { box-shadow: 0 0 0 8px rgba(34,197,94,0); } 100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); } }
.apx-list-row { display: flex; align-items: center; gap: 14px; padding: 11px 16px; border-bottom: 1px solid ${T.line}; cursor: pointer; outline: none; transition: background .12s; }
.apx-list-row:last-child { border-bottom: 0; }
.apx-list-row:hover, .apx-list-row:focus-visible { background: #f6f9ff; }
.apx-list-row .apx-card-desc { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* report page */
.apx-report { display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 18px; align-items: start; }
.apx-report.apx-rail-closed, .apx-report.apx-focus { grid-template-columns: minmax(0, 1fr); }
.apx-focus { position: fixed; inset: 0; z-index: 1000; padding: 16px 20px; overflow: auto;
  background: linear-gradient(180deg, #eef2f8 0%, #f5f7fb 320px); }
.apx-rail { position: sticky; top: 12px; max-height: calc(100vh - 92px); overflow: auto; background: #fff; border: 1px solid ${T.line};
  border-radius: 16px; padding: 10px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
.apx-rail-back { all: unset; box-sizing: border-box; cursor: pointer; width: 100%; display: flex; gap: 8px; align-items: center; padding: 8px 10px; margin-bottom: 6px;
  border-radius: 10px; font-size: 13px; font-weight: 600; color: ${T.muted}; background: #f4f6fa; }
.apx-rail-back:hover { color: ${T.accent}; background: #eaf1ff; }
.apx-rail-group { margin-bottom: 2px; }
.apx-rail-head { all: unset; box-sizing: border-box; cursor: pointer; width: 100%; display: flex; gap: 10px; align-items: center; padding: 7px 8px;
  border-radius: 10px; font-size: 13px; font-weight: 650; color: ${T.ink}; }
.apx-rail-head:hover { background: #f4f6fa; }
.apx-rail-head > span:nth-child(2) { flex: 1; }
.apx-caret { font-size: 10px; color: ${T.faint}; transition: transform .15s; }
.apx-rail-item { all: unset; box-sizing: border-box; cursor: pointer; width: 100%; display: block; padding: 6px 10px 6px 42px; border-radius: 8px;
  font-size: 13px; color: #475569; position: relative; transition: background .12s; }
.apx-rail-item:hover { background: #f4f6fa; color: ${T.ink}; }
.apx-rail-item.on { background: var(--t); color: var(--c); font-weight: 650; }
.apx-rail-item.on::before { content: ''; position: absolute; left: 30px; top: 50%; width: 5px; height: 5px; margin-top: -2.5px; border-radius: 50%; background: var(--c); }

.apx-rhero { position: relative; overflow: hidden; border-radius: 20px; padding: 20px 22px 18px; color: #fff; margin-bottom: 14px;
  background: radial-gradient(520px 240px at 92% -40%, var(--glow), transparent 65%), linear-gradient(135deg, #0b1b36 0%, #12305e 60%, #163f78 100%);
  box-shadow: 0 18px 40px -20px rgba(15,35,80,.6); }
.apx-rhero-top { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: flex-start; }
.apx-rhero-icon { width: 46px; height: 46px; border-radius: 14px; display: grid; place-items: center; font-size: 21px; color: #fff; flex-shrink: 0;
  background: var(--c); box-shadow: 0 8px 20px -6px var(--glow); }
.apx-crumb { font-size: 12.5px; color: rgba(226,232,240,.7); display: flex; gap: 7px; align-items: center; }
.apx-crumb a { color: rgba(226,232,240,.85); }
.apx-crumb a:hover { color: #fff; text-decoration: underline; }
.apx-rhero-title { font-size: 25px; font-weight: 800; letter-spacing: -0.5px; margin: 2px 0 2px; color: #fff; }
.apx-rhero-sub { color: rgba(226,232,240,.78); font-size: 13.5px; }
.apx-rhero-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.apx-updated { font-size: 12px; color: rgba(226,232,240,.75); display: inline-flex; gap: 8px; align-items: center; margin-right: 4px; }
.apx-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-top: 18px; }
.apx-kpi { display: flex; align-items: center; gap: 12px; background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.12);
  border-radius: 14px; padding: 12px 14px; backdrop-filter: blur(6px); }
.apx-kpi-i { width: 38px; height: 38px; border-radius: 11px; display: grid; place-items: center; font-size: 18px; flex-shrink: 0; }
.apx-kpi-v { font-size: 24px; font-weight: 800; letter-spacing: -0.5px; color: #fff; line-height: 1.1; }
.apx-kpi-l { color: rgba(226,232,240,.72); font-size: 12px; margin-top: 2px; }
.apx-kpi .ant-skeleton-input { background: rgba(255,255,255,.15) !important; }

.apx-filter-row { display: flex; gap: 10px; align-items: flex-start; margin-bottom: 14px; background: #fff; border: 1px solid ${T.line};
  border-radius: 16px; padding: 10px 12px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
.apx-filters { flex: 1; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; min-width: 0; }
.apx-filter-actions { display: flex; gap: 8px; margin-left: auto; flex-shrink: 0; }
.apx-filters-empty { color: ${T.faint}; font-size: 13px; padding-left: 4px; }
.apx-filters .ant-segmented { background: #eef1f6; }

.apx-panel { background: #fff; border: 1px solid ${T.line}; border-radius: 16px; overflow: hidden; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
.apx-table-bar { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-bottom: 1px solid ${T.line}; flex-wrap: wrap; background: #fcfdfe; }
.apx-panel .ant-table-thead > tr > th { background: #f6f8fb !important; color: #64748b; font-weight: 650; font-size: 11.5px; text-transform: uppercase; letter-spacing: .05em; }
.apx-panel .ant-table-thead > tr > th::before { display: none; }
.apx-panel .ant-table-tbody > tr > td { font-size: 13.5px; border-bottom-color: #f0f2f6; }
.apx-panel .ant-table-tbody > tr:nth-child(even) > td { background: #fbfcfe; }
.apx-panel .ant-table-tbody > tr:hover > td { background: #eef4ff !important; }
.apx-panel .ant-pagination { padding: 0 16px; }
.apx-total td { background: #f1f5fb !important; font-weight: 700; border-top: 1px solid ${T.line}; }
.apx-mark { background: #fde68a; padding: 0 1px; border-radius: 2px; }
.apx-detail { display: flex; flex-direction: column; }
.apx-detail-row { display: grid; grid-template-columns: 150px 1fr; gap: 12px; padding: 10px 0; border-bottom: 1px solid ${T.line}; font-size: 13.5px; }
.apx-detail-row > span { color: ${T.muted}; }
.apx-detail-row > div { word-break: break-word; font-weight: 500; }

@media (max-width: 1100px) {
  .apx-report { grid-template-columns: minmax(0, 1fr); }
  .apx-rail { display: none; }
  .apx-hero-stats { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .apx-reports { padding: 12px 12px 28px; }
  .apx-hero { padding: 22px 18px; }
  .apx-hero-title { font-size: 28px; }
  .apx-rhero-actions { width: 100%; }
  .apx-filter-row { flex-direction: column; }
}
`;
