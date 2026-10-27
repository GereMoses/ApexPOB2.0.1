/**
 * Reports — a curated library grouped by purpose; opening a report gives one clean,
 * full-width page (filters → key figures → table, chart on demand, one Export menu).
 * The catalogue lives in ./reportCatalog.js.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Input, Button, Table, Tag, Select, DatePicker, Segmented, Dropdown, Empty, App,
  Tooltip, Drawer, Skeleton, Modal, Form, TimePicker, Popconfirm, Switch,
} from 'antd';
import {
  SearchOutlined, StarOutlined, StarFilled, ArrowLeftOutlined, DownloadOutlined,
  ReloadOutlined, BarChartOutlined, FilePdfOutlined, FileExcelOutlined, FileTextOutlined,
  ToolOutlined, RightOutlined, ClockCircleOutlined, ScheduleOutlined, PlayCircleOutlined,
  DeleteOutlined, LockOutlined,
} from '@ant-design/icons';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
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

const humanize = (k) => k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
const fmtNum = (v) => (typeof v === 'number' ? (Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 1 })) : v);

const STATUS_COLORS = [
  [/present|safe|online|completed|success|approved|boarded|valid|on site|active|fit|mobili[sz]e|arriving/i, 'green'],
  [/late|early|warning|expiring|medium|pending|submitted|in transit|in progress|manifested/i, 'orange'],
  [/absent|missing|offline|expired|failed|overdue|high|no-?show|rejected|cancel|unfit|blocked|demobili[sz]e|leaving/i, 'red'],
];
const statusColor = (v) => (STATUS_COLORS.find(([re]) => re.test(String(v))) || [null, 'default'])[1];

/* ═══════════════════════════════════════════════════════════════════════════ */

export default function Reports() {
  const [params, setParams] = useSearchParams();
  const code = params.get('r');
  const report = code ? findReport(code) : null;
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
    <div className="apx-reports" style={{ background: T.bg, minHeight: '100%', padding: '28px 32px 48px' }}>
      {report && !canView(report.code) ? (
        <div style={{ maxWidth: 640, margin: '80px auto', textAlign: 'center' }}>
          <LockOutlined style={{ fontSize: 34, color: T.faint }} />
          <h2 style={{ marginTop: 12 }}>You don’t have access to this report</h2>
          <div className="apx-sub">Ask an administrator for the matching report permission.</div>
          <Button style={{ marginTop: 18 }} onClick={() => setParams({})}>Back to reports</Button>
        </div>
      ) : report
        ? <ReportView key={report.code} report={report} pinned={pins.includes(report.code)} canExport={canExport(report.code)}
            onPin={() => togglePin(report.code)} onBack={() => setParams({})} />
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
  const recent = store.get(RECENT, []).map(findReport).filter(r => r && canView(r.code));
  const pinned = pins.map(findReport).filter(r => r && canView(r.code));
  const term = q.trim().toLowerCase();
  const visible = ALL_REPORTS.filter(r => canView(r.code)).length;
  const groups = REPORT_GROUPS.map(g => ({
    ...g,
    reports: g.reports.filter(r => canView(r.code) && (!term || `${r.title} ${r.desc} ${g.title}`.toLowerCase().includes(term))),
  })).filter(g => g.reports.length);

  return (
    <div style={{ maxWidth: 1240, margin: '0 auto' }}>
      <div className="apx-lib-head">
        <div>
          <h1 className="apx-h1">Reports</h1>
          <div className="apx-sub">{visible} reports · times shown in site time (Lagos)</div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <Input allowClear size="large" prefix={<SearchOutlined style={{ color: T.faint }} />}
            placeholder="Search reports…" value={q} onChange={e => setQ(e.target.value)} style={{ width: 300 }} />
          <Button size="large" icon={<ScheduleOutlined />} onClick={onScheduled}>Scheduled</Button>
          <Button size="large" icon={<ToolOutlined />} onClick={onBuilder}>Custom report</Button>
        </div>
      </div>

      {!term && (pinned.length > 0 || recent.length > 0) && (
        <div className="apx-quick">
          {pinned.length > 0 && <QuickRow label="Pinned" items={pinned} onOpen={onOpen} icon={<StarFilled style={{ color: '#f59e0b' }} />} />}
          {recent.length > 0 && <QuickRow label="Recent" items={recent} onOpen={onOpen} icon={<ClockCircleOutlined style={{ color: T.faint }} />} />}
        </div>
      )}

      {groups.length === 0 && <Empty style={{ marginTop: 80 }} description={`No report matches “${q}”`} />}

      {groups.map(g => (
        <section key={g.key} className="apx-group">
          <div className="apx-group-head">
            <span className="apx-dot" style={{ background: g.color }} />
            <h2>{g.title}</h2>
            <span className="apx-blurb">{g.blurb}</span>
          </div>
          <div className="apx-grid">
            {g.reports.map(r => (
              <div key={r.code} className="apx-card" role="button" tabIndex={0}
                onClick={() => onOpen(r.code)} onKeyDown={e => e.key === 'Enter' && onOpen(r.code)}
                style={{ '--accent': g.color }}>
                <div className="apx-card-top">
                  <span className="apx-card-title">{r.title}</span>
                  <span className="apx-pin" onClick={e => { e.stopPropagation(); onPin(r.code); }}
                    title={pins.includes(r.code) ? 'Unpin' : 'Pin'}>
                    {pins.includes(r.code) ? <StarFilled style={{ color: '#f59e0b' }} /> : <StarOutlined />}
                  </span>
                </div>
                <div className="apx-card-desc">{r.desc}</div>
                <div className="apx-card-go">Open <RightOutlined style={{ fontSize: 10 }} /></div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
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

function ReportView({ report, pinned, onPin, onBack, canExport = true }) {
  const { message } = App.useApp();
  const [filters, setFilters] = useState(() => initialFilters(report));
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showChart, setShowChart] = useState(false);
  const [exporting, setExporting] = useState(null);
  const [scheduleOpen, setScheduleOpen] = useState(false);

  const missing = (report.filters?.required || []).filter(k => !filters[k]);
  const apiFilters = useMemo(() => toApiFilters(report, filters), [report, filters]);

  const load = useCallback(async () => {
    if (missing.length) { setData(null); return; }
    setLoading(true); setError(null);
    try {
      const res = await apiService.post('/api/v1/report/data', {
        report_code: report.code, filters: apiFilters, page, page_size: pageSize,
      });
      setData(res);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'Could not load this report');
    } finally {
      setLoading(false);
    }
  }, [report.code, apiFilters, page, pageSize, missing.length]);

  useEffect(() => { load(); }, [load]);

  const set = (k, v) => { setPage(1); setFilters(prev => ({ ...prev, [k]: v })); };

  const exportAs = async (format) => {
    setExporting(format);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('/api/v1/report/export/file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ report_code: report.code, filters: apiFilters, format }),
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

  const columns = useMemo(() => (data?.columns || []).map(c => ({
    title: c.label, dataIndex: c.field, key: c.field, ellipsis: true,
    align: ['number', 'currency', 'percentage', 'integer'].includes(c.type) ? 'right' : 'left',
    sorter: (a, b) => {
      const x = a[c.field], y = b[c.field];
      return typeof x === 'number' && typeof y === 'number' ? x - y : String(x ?? '').localeCompare(String(y ?? ''));
    },
    render: (v) => renderCell(v, c.type),
  })), [data]);

  const kpis = useMemo(() => {
    const s = data?.summary || {};
    const spec = report.kpis;
    const entries = spec
      ? Object.entries(spec).filter(([k]) => s[k] !== undefined && s[k] !== null).map(([k, label]) => [label, s[k]])
      : Object.entries(s).filter(([, v]) => typeof v === 'number').slice(0, 4).map(([k, v]) => [humanize(k), v]);
    return [['Rows', data?.total ?? 0], ...entries].slice(0, 5);
  }, [data, report.kpis]);

  const chart = data?.chart_data?.labels?.length && data?.chart_data?.datasets?.[0]
    ? data.chart_data.labels.map((l, i) => ({ name: String(l), value: Number(data.chart_data.datasets[0].data?.[i] ?? 0) }))
    : null;

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      <button className="apx-back" onClick={onBack}><ArrowLeftOutlined /> Reports <span style={{ color: T.faint }}>/</span> {report.group.title}</button>

      <div className="apx-report-head">
        <div style={{ minWidth: 0 }}>
          <h1 className="apx-h1" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className="apx-bar" style={{ background: report.group.color }} />
            {report.title}
          </h1>
          <div className="apx-sub">{report.desc}</div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <Tooltip title={pinned ? 'Unpin' : 'Pin to the library'}>
            <Button icon={pinned ? <StarFilled style={{ color: '#f59e0b' }} /> : <StarOutlined />} onClick={onPin} />
          </Tooltip>
          <Tooltip title="Refresh"><Button icon={<ReloadOutlined />} onClick={load} loading={loading} /></Tooltip>
          {chart && <Button icon={<BarChartOutlined />} type={showChart ? 'primary' : 'default'} ghost={showChart}
            onClick={() => setShowChart(v => !v)}>Chart</Button>}
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
              <Button type="primary" icon={<DownloadOutlined />} loading={!!exporting}>Export</Button>
            </Dropdown>
          )}
        </div>
      </div>

      <FilterBar report={report} filters={filters} set={set} setFilters={(f) => { setPage(1); setFilters(f); }} />
      <ScheduleModal open={scheduleOpen} onClose={() => setScheduleOpen(false)} report={report} filters={filters} />

      {missing.length > 0 ? (
        <div className="apx-panel" style={{ padding: 56 }}>
          <Empty description={`Choose ${missing.map(k => ({ person: 'a person', musterEvent: 'a muster event' }[k] || k)).join(' and ')} above to run this report.`} />
        </div>
      ) : (
        <>
          <div className="apx-kpis">
            {kpis.map(([label, v]) => (
              <div key={label} className="apx-kpi">
                <div className="apx-kpi-v">{loading && !data ? <Skeleton.Input size="small" active /> : (fmtNum(v) ?? '—')}</div>
                <div className="apx-kpi-l">{label}</div>
              </div>
            ))}
          </div>

          {showChart && chart && (
            <div className="apx-panel" style={{ padding: '18px 18px 6px', marginBottom: 16 }}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chart} margin={{ top: 4, right: 8, left: -12, bottom: 4 }}>
                  <CartesianGrid vertical={false} stroke={T.line} />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: T.muted }} interval={0} angle={chart.length > 8 ? -30 : 0}
                    textAnchor={chart.length > 8 ? 'end' : 'middle'} height={chart.length > 8 ? 60 : 30} />
                  <YAxis tick={{ fontSize: 12, fill: T.muted }} allowDecimals={false} />
                  <RTooltip cursor={{ fill: 'rgba(37,99,235,0.06)' }} />
                  <Bar dataKey="value" fill={report.group.color} radius={[4, 4, 0, 0]} maxBarSize={44} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="apx-panel">
            {error ? (
              <div style={{ padding: 48 }}><Empty description={<span style={{ color: '#dc2626' }}>{error}</span>} /></div>
            ) : (
              <Table
                rowKey={(r, i) => r.id ?? r.emp_code ?? i}
                size="middle"
                columns={columns}
                dataSource={data?.data || []}
                loading={loading}
                scroll={{ x: 'max-content' }}
                sticky
                locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Nothing for these filters" /> }}
                pagination={{
                  current: page, pageSize, total: data?.total || 0, showSizeChanger: true,
                  pageSizeOptions: [25, 50, 100, 200],
                  showTotal: (t, r) => `${r[0]}–${r[1]} of ${t.toLocaleString()}`,
                  onChange: (p, s) => { setPage(p); setPageSize(s); },
                }}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}

function renderCell(v, type) {
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
      return String(v);
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
  if (f.date === 'none' && extra.length === 0) return null;

  return (
    <div className="apx-filters">
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
.apx-reports { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: ${T.ink}; }
.apx-h1 { font-size: 26px; font-weight: 750; letter-spacing: -0.4px; margin: 0; color: ${T.ink}; }
.apx-sub { color: ${T.muted}; font-size: 14px; margin-top: 4px; }
.apx-lib-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; margin-bottom: 22px; }

.apx-quick { display: flex; flex-direction: column; gap: 10px; margin-bottom: 30px; }
.apx-quick-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.apx-quick-label { font-size: 12px; font-weight: 600; color: ${T.muted}; text-transform: uppercase; letter-spacing: .06em; width: 92px; display: inline-flex; gap: 6px; align-items: center; }
.apx-chip { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px;
  background: ${T.card}; border: 1px solid ${T.line}; border-radius: 999px; font-size: 13px; color: ${T.ink}; transition: all .15s; }
.apx-chip:hover { border-color: ${T.accent}; color: ${T.accent}; }
.apx-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }

.apx-group { margin-bottom: 34px; }
.apx-group-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.apx-group-head h2 { font-size: 16px; font-weight: 700; margin: 0; color: ${T.ink}; }
.apx-group-head .apx-dot { transform: translateY(-1px); }
.apx-blurb { color: ${T.muted}; font-size: 13px; }
.apx-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 12px; }
.apx-card { position: relative; background: ${T.card}; border: 1px solid ${T.line}; border-radius: 12px; padding: 16px 16px 14px;
  cursor: pointer; transition: transform .15s, box-shadow .15s, border-color .15s; display: flex; flex-direction: column; gap: 6px; min-height: 118px; outline: none; }
.apx-card::before { content: ''; position: absolute; left: 0; top: 14px; bottom: 14px; width: 3px; border-radius: 0 3px 3px 0; background: var(--accent); opacity: .0; transition: opacity .15s; }
.apx-card:hover, .apx-card:focus-visible { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(15,23,42,.07); border-color: #d6dbe5; }
.apx-card:hover::before, .apx-card:focus-visible::before { opacity: 1; }
.apx-card-top { display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; }
.apx-card-title { font-weight: 650; font-size: 15px; color: ${T.ink}; }
.apx-card-desc { color: ${T.muted}; font-size: 13px; line-height: 1.45; flex: 1; }
.apx-card-go { color: var(--accent); font-size: 12.5px; font-weight: 600; opacity: 0; transition: opacity .15s; display: inline-flex; gap: 6px; align-items: center; }
.apx-card:hover .apx-card-go, .apx-card:focus-visible .apx-card-go { opacity: 1; }
.apx-pin { color: ${T.faint}; padding: 2px; border-radius: 6px; line-height: 1; }
.apx-pin:hover { color: #f59e0b; background: #fff7e6; }

.apx-back { all: unset; cursor: pointer; color: ${T.muted}; font-size: 13px; display: inline-flex; gap: 8px; align-items: center; margin-bottom: 14px; }
.apx-back:hover { color: ${T.accent}; }
.apx-report-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 18px; flex-wrap: wrap; }
.apx-bar { width: 4px; height: 24px; border-radius: 3px; display: inline-block; }

.apx-filters { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; background: ${T.card}; border: 1px solid ${T.line};
  border-radius: 12px; padding: 12px; margin-bottom: 16px; }
.apx-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }
.apx-kpi { background: ${T.card}; border: 1px solid ${T.line}; border-radius: 12px; padding: 14px 16px; }
.apx-kpi-v { font-size: 26px; font-weight: 750; letter-spacing: -0.5px; color: ${T.ink}; line-height: 1.15; }
.apx-kpi-l { color: ${T.muted}; font-size: 12.5px; margin-top: 4px; }
.apx-panel { background: ${T.card}; border: 1px solid ${T.line}; border-radius: 12px; overflow: hidden; }
.apx-panel .ant-table-thead > tr > th { background: #f8fafc; color: ${T.muted}; font-weight: 600; font-size: 12.5px; text-transform: uppercase; letter-spacing: .03em; }
.apx-panel .ant-table-tbody > tr > td { font-size: 13.5px; }
.apx-panel .ant-pagination { padding: 0 16px; }
@media (max-width: 640px) {
  .apx-reports { padding: 20px 16px 40px !important; }
  .apx-lib-head .ant-input-affix-wrapper { width: 100% !important; }
}
`;
