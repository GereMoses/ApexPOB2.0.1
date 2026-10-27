/**
 * Reports — a curated library grouped by purpose; opening a report gives one clean,
 * full-width page (filters → key figures → table, chart on demand, one Export menu).
 * The catalogue lives in ./reportCatalog.js.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Input, Button, Table, Tag, Select, DatePicker, Segmented, Dropdown, Empty, App,
  Tooltip, Drawer, Skeleton,
} from 'antd';
import {
  SearchOutlined, StarOutlined, StarFilled, ArrowLeftOutlined, DownloadOutlined,
  ReloadOutlined, BarChartOutlined, FilePdfOutlined, FileExcelOutlined, FileTextOutlined,
  ToolOutlined, RightOutlined, ClockCircleOutlined,
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
  const [pins, setPins] = useState(() => store.get(PINS, []));

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
      {report
        ? <ReportView key={report.code} report={report} pinned={pins.includes(report.code)}
            onPin={() => togglePin(report.code)} onBack={() => setParams({})} />
        : <Library pins={pins} onPin={togglePin} onOpen={open} onBuilder={() => setBuilderOpen(true)} />}

      <Drawer title="Custom report" width={1100} open={builderOpen} onClose={() => setBuilderOpen(false)} destroyOnClose>
        <CustomReportBuilder />
      </Drawer>

      <style>{CSS}</style>
    </div>
  );
}

/* ── Library ──────────────────────────────────────────────────────────────── */

function Library({ pins, onPin, onOpen, onBuilder }) {
  const [q, setQ] = useState('');
  const recent = store.get(RECENT, []).map(findReport).filter(Boolean);
  const pinned = pins.map(findReport).filter(Boolean);
  const term = q.trim().toLowerCase();
  const groups = REPORT_GROUPS.map(g => ({
    ...g,
    reports: g.reports.filter(r => !term || `${r.title} ${r.desc} ${g.title}`.toLowerCase().includes(term)),
  })).filter(g => g.reports.length);

  return (
    <div style={{ maxWidth: 1240, margin: '0 auto' }}>
      <div className="apx-lib-head">
        <div>
          <h1 className="apx-h1">Reports</h1>
          <div className="apx-sub">{ALL_REPORTS.length} reports · times shown in site time (Lagos)</div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <Input allowClear size="large" prefix={<SearchOutlined style={{ color: T.faint }} />}
            placeholder="Search reports…" value={q} onChange={e => setQ(e.target.value)} style={{ width: 300 }} />
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
  if (f.date === 'range') return { _preset: '7d', _range: PRESETS['7d']() };
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
    flightStatus: 'status', journeyStatus: 'status', direction: 'direction', musterEvent: 'event_id', changeType: 'change_type' };
  Object.entries(map).forEach(([k, api]) => { if (s[k] !== undefined && s[k] !== null && s[k] !== '') out[api] = s[k]; });
  return out;
}

function ReportView({ report, pinned, onPin, onBack }) {
  const { message } = App.useApp();
  const [filters, setFilters] = useState(() => initialFilters(report));
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showChart, setShowChart] = useState(false);
  const [exporting, setExporting] = useState(null);

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
          <Dropdown menu={{
            items: [
              { key: 'xlsx', icon: <FileExcelOutlined style={{ color: '#16a34a' }} />, label: 'Excel (.xlsx)' },
              { key: 'pdf', icon: <FilePdfOutlined style={{ color: '#dc2626' }} />, label: 'PDF' },
              { key: 'csv', icon: <FileTextOutlined style={{ color: T.muted }} />, label: 'CSV' },
            ],
            onClick: ({ key }) => exportAs(key),
          }}>
            <Button type="primary" icon={<DownloadOutlined />} loading={!!exporting}>Export</Button>
          </Dropdown>
        </div>
      </div>

      <FilterBar report={report} filters={filters} set={set} setFilters={(f) => { setPage(1); setFilters(f); }} />

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
      {extra.includes('musterEvent') && (
        <Select allowClear placeholder="Muster event" style={{ width: 300 }} value={filters.musterEvent}
          onChange={(v) => set('musterEvent', v)} options={events} notFoundContent="No muster events yet" />
      )}
    </div>
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
