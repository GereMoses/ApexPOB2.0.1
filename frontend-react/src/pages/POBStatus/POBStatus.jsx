import React, { useState, useCallback } from 'react';
import {
  Card, Row, Col, Table, Tag, Badge, Typography, Space, Progress,
  Alert, Button, Tooltip, Avatar, Input, Select, Tabs, Divider,
  Statistic, Empty, Spin, Modal,
} from 'antd';
import {
  TeamOutlined, EnvironmentOutlined, CarOutlined, ReloadOutlined,
  UserOutlined, ClockCircleOutlined, ArrowUpOutlined, ArrowDownOutlined,
  WarningOutlined, CheckCircleOutlined, ExportOutlined, SearchOutlined,
  SafetyOutlined, FireOutlined, RiseOutlined, FallOutlined, MinusOutlined,
  ApartmentOutlined, ThunderboltOutlined, EyeOutlined,
} from '@ant-design/icons';
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar,
  PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartTooltip, Legend,
} from 'recharts';
import { useQuery } from '@tanstack/react-query';
import apiService from '../../services/api';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);

const { Title, Text } = Typography;
const { Search } = Input;

// ── colour palette ────────────────────────────────────────────────────────────
const C = {
  offshore: '#0078D4',
  onshore:  '#22C55E',
  transit:  '#F59E0B',
  overdue:  '#EF4444',
  purple:   '#7C3AED',
  bg:       '#F3F4F8',
};

const PIE_COLORS = [C.offshore, C.onshore, C.transit, '#8B5CF6', '#EC4899', '#14B8A6'];

const VERIFY_COLORS = {
  Fingerprint: '#0078D4',
  Face:        '#7C3AED',
  Card:        '#22C55E',
  Password:    '#F59E0B',
};

const PUNCH_CONFIG = {
  ENTRY:      { color: '#22C55E', label: 'Entered',    icon: <ArrowDownOutlined /> },
  EXIT:       { color: '#EF4444', label: 'Exited',     icon: <ArrowUpOutlined /> },
  DENIED:     { color: '#B91C1C', label: 'Refused',    icon: <MinusOutlined /> },
  CHECK_IN:   { color: '#22C55E', label: 'Check In',   icon: <ArrowDownOutlined /> },
  CHECK_OUT:  { color: '#EF4444', label: 'Check Out',  icon: <ArrowUpOutlined /> },
  REPEAT_TAP: { color: '#94A3B8', label: 'Repeat tap', icon: <ArrowDownOutlined /> },
  BREAK_OUT:  { color: '#F59E0B', label: 'Break Out',  icon: <ArrowUpOutlined /> },
  BREAK_IN:   { color: '#0078D4', label: 'Break In',   icon: <ArrowDownOutlined /> },
  UNKNOWN:    { color: '#9CA3AF', label: 'Unknown',    icon: <MinusOutlined /> },
};

// ── helpers ───────────────────────────────────────────────────────────────────
const pct = (part, total) => (total > 0 ? Math.round((part / total) * 100) : 0);

const TrendArrow = ({ today, yesterday }) => {
  const delta = today - yesterday;
  if (delta > 0)  return <span style={{ color: C.onshore,  fontSize: 11 }}><RiseOutlined /> +{delta}</span>;
  if (delta < 0)  return <span style={{ color: C.overdue,  fontSize: 11 }}><FallOutlined /> {delta}</span>;
  return               <span style={{ color: '#9CA3AF', fontSize: 11 }}><MinusOutlined /> —</span>;
};

const CustomPieLabel = ({ cx, cy, label, value }) => (
  <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central">
    <tspan x={cx} dy="-0.4em" style={{ fontSize: 28, fontWeight: 800, fill: '#1F2937' }}>{value}</tspan>
    <tspan x={cx} dy="1.5em"  style={{ fontSize: 12, fill: '#6B7A8D' }}>{label}</tspan>
  </text>
);

// ── export helper ─────────────────────────────────────────────────────────────
const downloadCSV = async () => {
  const token = localStorage.getItem('token') || localStorage.getItem('authToken');
  try {
    const res = await fetch('/api/v1/pob-status/export-csv', {
      headers: { Authorization: `Bearer ${token}` },
    });
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `POB_Report_${dayjs().format('YYYYMMDD_HHmm')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    console.error('Export failed', e);
  }
};

// ── KPI card ──────────────────────────────────────────────────────────────────
const KpiCard = ({ title, value, icon, color, subtitle, trend, onClick }) => (
  <Card
    size="small"
    hoverable={!!onClick}
    onClick={onClick}
    style={{
      borderRadius: 12, border: `1px solid ${color}22`,
      background: `linear-gradient(135deg, #fff 60%, ${color}08)`,
      cursor: onClick ? 'pointer' : 'default',
    }}
    bodyStyle={{ padding: '16px 20px' }}
  >
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
      <div>
        <div style={{ fontSize: 12, color: '#6B7A8D', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {title}
        </div>
        <div style={{ fontSize: 32, fontWeight: 800, color, lineHeight: 1.1 }}>{value}</div>
        <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
          {subtitle && <span style={{ fontSize: 11, color: '#9CA3AF' }}>{subtitle}</span>}
          {trend}
        </div>
      </div>
      <div style={{
        width: 44, height: 44, borderRadius: 10,
        background: `${color}15`, display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        color, fontSize: 20, flexShrink: 0,
      }}>{icon}</div>
    </div>
  </Card>
);

// ── main component ────────────────────────────────────────────────────────────
export default function POBStatus() {
  const [activeTab,    setActiveTab]    = useState('overview');
  const [searchVal,    setSearchVal]    = useState('');
  const [locFilter,    setLocFilter]    = useState(null);
  const [deptFilter,   setDeptFilter]   = useState(null);
  const [drillLoc,     setDrillLoc]     = useState(null); // location drill-down modal
  const [trendDays,    setTrendDays]    = useState(30);

  // ── queries ────────────────────────────────────────────────────────────
  const { data: dashRaw, isLoading: dashLoading, refetch: refetchDash, dataUpdatedAt } = useQuery({
    queryKey:       ['pob-dashboard'],
    queryFn:        () => apiService.get('/api/v1/pob-status/dashboard'),
    refetchInterval: 15_000,
    staleTime:       10_000,
  });

  const { data: trendRaw } = useQuery({
    queryKey:        ['pob-trend', trendDays],
    queryFn:         () => apiService.get(`/api/v1/pob-status/attendance-trend?days=${trendDays}`),
    refetchInterval:  5 * 60_000,
    staleTime:        60_000,
  });

  const { data: verifyRaw } = useQuery({
    queryKey:        ['pob-verify'],
    queryFn:         () => apiService.get('/api/v1/pob-status/verify-methods'),
    refetchInterval:  5 * 60_000,
    staleTime:        60_000,
  });

  const { data: deptRaw } = useQuery({
    queryKey:        ['pob-dept'],
    queryFn:         () => apiService.get('/api/v1/pob-status/department-breakdown'),
    refetchInterval:  2 * 60_000,
    staleTime:        60_000,
  });

  const { data: personnelRaw, isLoading: personnelLoading } = useQuery({
    queryKey:  ['pob-personnel', searchVal, locFilter, deptFilter],
    queryFn:   () => {
      const p = new URLSearchParams();
      if (searchVal)  p.set('search', searchVal);
      if (locFilter)  p.set('location', locFilter);
      if (deptFilter) p.set('department', deptFilter);
      return apiService.get(`/api/v1/pob-status/personnel-list?${p}`);
    },
    enabled:   activeTab === 'personnel' || !!drillLoc,
    staleTime: 30_000,
  });

  const { data: rotationRaw, isLoading: rotationLoading } = useQuery({
    queryKey:        ['pob-rotation'],
    queryFn:         () => apiService.get('/api/v1/pob-status/rotation-overdue'),
    refetchInterval:  2 * 60_000,
    enabled:          activeTab === 'rotations',
    staleTime:        60_000,
  });

  // drill-down modal query
  const { data: drillRaw, isLoading: drillLoading } = useQuery({
    queryKey:  ['pob-drill', drillLoc],
    queryFn:   () => apiService.get(`/api/v1/pob-status/personnel-list?location=${encodeURIComponent(drillLoc)}`),
    enabled:   !!drillLoc,
    staleTime: 20_000,
  });

  // ── derived data ────────────────────────────────────────────────────────
  const dash         = dashRaw   || {};
  const total        = dash.total              || 0;
  const offshore     = dash.offshore_count     || 0;
  const onshore      = dash.onshore_count      || 0;
  const transit      = dash.transit_count      || 0;
  const overdueCnt   = dash.rotation_overdue_count || 0;
  const byLocation   = dash.by_location        || {};
  const liveEvents   = dash.recent_events      || [];
  const transports   = dash.active_transports  || [];
  const ciToday      = dash.checkins_today     || 0;
  const ciYest       = dash.checkins_yesterday || 0;

  const trendData    = trendRaw?.trend   || [];
  const verifyData   = verifyRaw?.methods || [];
  const deptData     = (deptRaw?.data    || []).slice(0, 12);
  const personnel    = personnelRaw?.data || [];
  const rotOverdue   = rotationRaw?.data  || [];

  const locOptions = Object.keys(byLocation).map(l => ({ label: l, value: l }));

  const deptOptions = [...new Set(personnel.map(p => p.department).filter(Boolean))]
    .map(d => ({ label: d, value: d }));

  // ── distribution donut data ─────────────────────────────────────────────
  const donutData = [
    { name: 'Offshore', value: offshore, color: C.offshore },
    { name: 'Onshore',  value: onshore,  color: C.onshore  },
    { name: 'Transit',  value: transit,  color: C.transit  },
  ].filter(d => d.value > 0);

  // ── location cards ──────────────────────────────────────────────────────
  const locationCards = Object.entries(byLocation)
    .sort(([, a], [, b]) => b - a)
    .map(([loc, count]) => {
      const bucket = loc.toLowerCase();
      const color  =
        bucket.includes('offshore') || bucket.includes('platform') || bucket.includes('rig') ? C.offshore :
        bucket.includes('transit')  || bucket.includes('helicopter')                          ? C.transit  :
        C.onshore;
      return { loc, count, color, pct: pct(count, total) };
    });

  // ── personnel table columns ─────────────────────────────────────────────
  const personnelCols = [
    {
      title: 'Name', dataIndex: 'name', key: 'name',
      render: (n, r) => (
        <Space>
          <Avatar size={28} style={{ background: r.rotation_overdue ? C.overdue : C.offshore, fontSize: 11 }}>
            {(n || '?')[0].toUpperCase()}
          </Avatar>
          <span style={{ fontWeight: 500 }}>{n}</span>
          {r.rotation_overdue && <Tag color="error" style={{ fontSize: 10 }}>OVERDUE</Tag>}
        </Space>
      ),
    },
    { title: 'Emp Code',   dataIndex: 'emp_code',   key: 'emp_code',   width: 100, render: v => <Text code style={{ fontSize: 11 }}>{v}</Text> },
    { title: 'Department', dataIndex: 'department', key: 'department', width: 150 },
    { title: 'Position',   dataIndex: 'position',   key: 'position',   width: 150 },
    {
      title: 'Location', dataIndex: 'location', key: 'location',
      render: loc => {
        const b = loc.toLowerCase();
        const c = b.includes('platform') || b.includes('offshore') ? C.offshore :
                  b.includes('transit')  || b.includes('helicopter') ? C.transit  : C.onshore;
        return <Tag color={c === C.offshore ? 'blue' : c === C.transit ? 'orange' : 'green'}>{loc}</Tag>;
      },
    },
    {
      title: 'POB Since', dataIndex: 'pob_since', key: 'pob_since', width: 140,
      render: v => v ? dayjs(v).format('DD MMM YYYY') : '—',
      sorter: (a, b) => (a.pob_since || '').localeCompare(b.pob_since || ''),
    },
    {
      title: 'Days', dataIndex: 'days_onboard', key: 'days_onboard', width: 80,
      sorter: (a, b) => (a.days_onboard || 0) - (b.days_onboard || 0),
      render: (d, r) => (
        <span style={{ fontWeight: 700, color: r.rotation_overdue ? C.overdue : d > 21 ? C.transit : '#1F2937' }}>
          {d ?? '—'}
        </span>
      ),
    },
  ];

  // ── rotation overdue columns ────────────────────────────────────────────
  const rotCols = [
    {
      title: 'Name', dataIndex: 'name', key: 'name',
      render: (n, r) => (
        <Space>
          <Avatar size={26} style={{ background: C.overdue, fontSize: 11 }}>{(n || '?')[0]}</Avatar>
          <span style={{ fontWeight: 600 }}>{n}</span>
        </Space>
      ),
    },
    { title: 'Emp Code',   dataIndex: 'emp_code',     key: 'ec',   width: 100, render: v => <Text code style={{ fontSize: 11 }}>{v}</Text> },
    { title: 'Department', dataIndex: 'department',   key: 'dept', width: 140 },
    { title: 'Location',   dataIndex: 'location',     key: 'loc',  width: 140, render: v => <Tag color="blue">{v}</Tag> },
    {
      title: 'Days Onboard', dataIndex: 'days_onboard', key: 'days',
      sorter: (a, b) => b.days_onboard - a.days_onboard,
      render: d => <span style={{ fontWeight: 700, color: C.overdue }}>{d}</span>,
    },
    {
      title: 'Days Overdue', dataIndex: 'days_overdue', key: 'over',
      sorter: (a, b) => b.days_overdue - a.days_overdue,
      render: d => (
        <Tag color="error" style={{ fontWeight: 700 }}>+{d} days</Tag>
      ),
    },
    {
      title: 'POB Since', dataIndex: 'pob_since', key: 'since', width: 120,
      render: v => v ? dayjs(v).format('DD MMM YYYY') : '—',
    },
  ];

  // ── transport columns ───────────────────────────────────────────────────
  const transportCols = [
    { title: 'Type', dataIndex: 'type', key: 'type', render: v => <Tag color="blue">{v?.toUpperCase()}</Tag> },
    {
      title: 'Route', key: 'route',
      render: (_, r) => (
        <Space>
          <Text strong>{r.departure_location || '?'}</Text>
          <ArrowUpOutlined style={{ color: C.offshore }} />
          <Text strong>{r.arrival_location || '?'}</Text>
        </Space>
      ),
    },
    { title: 'Departure',  dataIndex: 'departure_time',   key: 'dep', render: v => v ? dayjs(v).format('DD MMM HH:mm') : '—' },
    { title: 'ETA',        dataIndex: 'estimated_arrival', key: 'eta', render: v => v ? dayjs(v).format('DD MMM HH:mm') : '—' },
    { title: 'PAX',        dataIndex: 'passenger_count',  key: 'pax', render: c => <Badge count={c || 0} showZero style={{ background: C.offshore }} /> },
    {
      title: 'Status', dataIndex: 'status', key: 'status',
      render: s => {
        const map = { SCHEDULED: 'blue', CONFIRMED: 'green', BOARDING: 'orange', CANCELLED: 'red' };
        return <Tag color={map[s] || 'default'}>{s}</Tag>;
      },
    },
  ];

  // ── recharts custom tooltip ─────────────────────────────────────────────
  const TrendTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{ background: '#fff', border: '1px solid #E5E7EB', borderRadius: 8, padding: '8px 12px', fontSize: 12 }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>{label}</div>
        {payload.map(p => (
          <div key={p.dataKey} style={{ color: p.color }}>
            {p.name}: <strong>{p.value}</strong>
          </div>
        ))}
      </div>
    );
  };

  // ── tab items ───────────────────────────────────────────────────────────

  const tabOverview = (
    <>
      {overdueCnt > 0 && (
        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          message={`${overdueCnt} personnel have exceeded the ${dash.rotation_max_days || 28}-day rotation limit`}
          action={<Button size="small" onClick={() => setActiveTab('rotations')}>View</Button>}
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={[16, 16]}>
        {/* Distribution donut */}
        <Col xs={24} md={10}>
          <Card title="POB Distribution" style={{ height: '100%' }}>
            {total === 0 ? (
              <Empty description="No personnel onboard" style={{ padding: '32px 0' }} />
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={donutData}
                    cx="50%" cy="50%"
                    innerRadius={72} outerRadius={108}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {donutData.map((d, i) => (
                      <Cell key={d.name} fill={d.color} stroke="none" />
                    ))}
                  </Pie>
                  <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central">
                    <tspan x="50%" dy="-0.4em" style={{ fontSize: 30, fontWeight: 800, fill: '#1F2937' }}>{total}</tspan>
                    <tspan x="50%" dy="1.6em"  style={{ fontSize: 12, fill: '#6B7A8D' }}>Total POB</tspan>
                  </text>
                  <Legend
                    formatter={(value, entry) => (
                      <span style={{ fontSize: 12, color: '#374151' }}>
                        {value} — <strong>{entry.payload.value}</strong> ({pct(entry.payload.value, total)}%)
                      </span>
                    )}
                  />
                  <RechartTooltip formatter={(v, n) => [`${v} (${pct(v, total)}%)`, n]} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Col>

        {/* Location breakdown */}
        <Col xs={24} md={14}>
          <Card
            title="Locations"
            extra={<Text type="secondary" style={{ fontSize: 12 }}>Click a location for personnel list</Text>}
            style={{ height: '100%' }}
          >
            {locationCards.length === 0 ? (
              <Empty description="No location data" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {locationCards.map(({ loc, count, color, pct: p }) => (
                  <div
                    key={loc}
                    onClick={() => setDrillLoc(loc)}
                    style={{
                      padding: '10px 14px', borderRadius: 8,
                      background: `${color}08`, border: `1px solid ${color}20`,
                      cursor: 'pointer', transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = `${color}14`}
                    onMouseLeave={e => e.currentTarget.style.background = `${color}08`}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Space size={6}>
                        <Badge color={color} />
                        <Text strong style={{ fontSize: 13 }}>{loc}</Text>
                        <EyeOutlined style={{ fontSize: 11, color: '#9CA3AF' }} />
                      </Space>
                      <Space>
                        <Text strong style={{ color, fontSize: 14 }}>{count}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>({p}%)</Text>
                      </Space>
                    </div>
                    <Progress percent={p} strokeColor={color} showInfo={false} size="small" />
                  </div>
                ))}
              </div>
            )}
          </Card>
        </Col>

        {/* Department chart */}
        <Col xs={24} md={12}>
          <Card title={<Space><ApartmentOutlined />Department Breakdown</Space>}>
            {deptData.length === 0 ? (
              <Empty description="No department data" style={{ padding: '24px 0' }} />
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(200, deptData.length * 30)}>
                <BarChart
                  data={deptData}
                  layout="vertical"
                  margin={{ top: 0, right: 30, left: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis
                    type="category" dataKey="department" width={120}
                    tick={{ fontSize: 11 }}
                    tickFormatter={v => v.length > 16 ? v.slice(0, 16) + '…' : v}
                  />
                  <RechartTooltip content={<TrendTooltip />} />
                  <Bar dataKey="count" name="Personnel" radius={[0, 4, 4, 0]}>
                    {deptData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Col>

        {/* Live activity feed */}
        <Col xs={24} md={12}>
          <Card
            title={<Space><ThunderboltOutlined style={{ color: C.offshore }} />Door Activity (Last 24h)</Space>}
            bodyStyle={{ padding: 0 }}
          >
            {liveEvents.length === 0 ? (
              <Empty description="No door taps in the last 24 h — this shows access-control readers only (T&A clock-ins are under Attendance)" style={{ padding: '32px 16px' }} />
            ) : (
              <div style={{ maxHeight: Math.max(200, deptData.length * 30) + 48, overflowY: 'auto' }}>
                {liveEvents.map(evt => {
                  const cfg = PUNCH_CONFIG[evt.type] || PUNCH_CONFIG.UNKNOWN;
                  return (
                    <div
                      key={evt.id}
                      style={{
                        display: 'flex', alignItems: 'flex-start', gap: 10,
                        padding: '9px 14px', borderBottom: '1px solid #F3F4F8',
                      }}
                    >
                      <div style={{
                        width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                        background: `${cfg.color}15`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: cfg.color, fontSize: 12,
                      }}>{cfg.icon}</div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Text strong style={{ fontSize: 12 }}>{evt.personnel}</Text>
                          <Tag
                            style={{ fontSize: 10, padding: '0 5px', margin: 0,
                              color: cfg.color, background: `${cfg.color}12`,
                              border: `1px solid ${cfg.color}30` }}
                          >
                            {cfg.label}
                          </Tag>
                          <Text style={{ fontSize: 10, color: '#9CA3AF' }}>{evt.verify_method}</Text>
                        </div>
                        <div style={{ fontSize: 11, color: '#6B7A8D', marginTop: 2 }}>
                          <EnvironmentOutlined style={{ marginRight: 3 }} />{evt.location}
                          {evt.department && <span style={{ marginLeft: 8, color: '#9CA3AF' }}>{evt.department}</span>}
                          {evt.reason && <span style={{ marginLeft: 8, color: '#B91C1C' }}>{evt.reason}</span>}
                        </div>
                      </div>
                      <div style={{ fontSize: 10, color: '#9CA3AF', flexShrink: 0, marginTop: 2 }}>
                        {evt.timestamp ? dayjs(evt.timestamp).fromNow() : '—'}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </>
  );

  const tabAnalytics = (
    <Row gutter={[16, 16]}>
      {/* Attendance trend */}
      <Col xs={24}>
        <Card
          title={<Space><RiseOutlined />Attendance Trend</Space>}
          extra={
            <Select
              value={trendDays}
              onChange={setTrendDays}
              size="small"
              style={{ width: 100 }}
              options={[
                { label: '7 days',  value: 7  },
                { label: '14 days', value: 14 },
                { label: '30 days', value: 30 },
                { label: '60 days', value: 60 },
                { label: '90 days', value: 90 },
              ]}
            />
          }
        >
          {trendData.length === 0 ? (
            <Empty description="No attendance data available" style={{ padding: '32px 0' }} />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={trendData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F0F0F0" vertical={false} />
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 11 }}
                  tickFormatter={v => dayjs(v).format('DD MMM')}
                  interval="preserveStartEnd"
                />
                <YAxis tick={{ fontSize: 11 }} />
                <RechartTooltip content={<TrendTooltip />} />
                <Legend />
                <Bar dataKey="check_ins"  name="Check Ins"  fill={C.onshore} radius={[3, 3, 0, 0]} maxBarSize={18} />
                <Bar dataKey="check_outs" name="Check Outs" fill={C.overdue} radius={[3, 3, 0, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </Col>

      {/* Verification methods */}
      <Col xs={24} md={10}>
        <Card title={<Space><SafetyOutlined />Verification Methods (Today)</Space>} style={{ height: '100%' }}>
          {verifyData.length === 0 ? (
            <Empty description="No biometric data for today" style={{ padding: '24px 0' }} />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={verifyData}
                    cx="50%" cy="50%"
                    innerRadius={55} outerRadius={80}
                    paddingAngle={4}
                    dataKey="count"
                    nameKey="type"
                  >
                    {verifyData.map(d => (
                      <Cell key={d.type} fill={VERIFY_COLORS[d.type] || '#9CA3AF'} stroke="none" />
                    ))}
                  </Pie>
                  <RechartTooltip formatter={(v, n) => [`${v} (${verifyData.find(x => x.type === n)?.pct || 0}%)`, n]} />
                </PieChart>
              </ResponsiveContainer>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
                {verifyData.map(d => (
                  <div key={d.type} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <div style={{ width: 10, height: 10, borderRadius: 2, background: VERIFY_COLORS[d.type] || '#9CA3AF' }} />
                    <Text style={{ fontSize: 12 }}>{d.type}: <strong>{d.count}</strong> ({d.pct}%)</Text>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </Col>

      {/* Today's stats strip */}
      <Col xs={24} md={14}>
        <Card title="Today at a Glance" style={{ height: '100%' }}>
          <Row gutter={[16, 16]}>
            <Col span={12}>
              <Statistic
                title="Check-ins Today"
                value={ciToday}
                prefix={<ArrowDownOutlined style={{ color: C.onshore }} />}
                valueStyle={{ color: C.onshore, fontSize: 28 }}
              />
              <TrendArrow today={ciToday} yesterday={ciYest} />
            </Col>
            <Col span={12}>
              <Statistic
                title="Yesterday Check-ins"
                value={ciYest}
                prefix={<ClockCircleOutlined style={{ color: '#9CA3AF' }} />}
                valueStyle={{ color: '#6B7A8D', fontSize: 28 }}
              />
            </Col>
            <Col span={24}><Divider style={{ margin: '8px 0' }} /></Col>
            <Col span={12}>
              <Statistic
                title="Total Onboard"
                value={total}
                prefix={<TeamOutlined style={{ color: C.offshore }} />}
                valueStyle={{ color: C.offshore, fontSize: 28 }}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="Rotation Overdue"
                value={overdueCnt}
                prefix={<WarningOutlined style={{ color: overdueCnt > 0 ? C.overdue : '#9CA3AF' }} />}
                valueStyle={{ color: overdueCnt > 0 ? C.overdue : '#6B7A8D', fontSize: 28 }}
              />
            </Col>
          </Row>
        </Card>
      </Col>
    </Row>
  );

  const tabPersonnel = (
    <>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <Search
          placeholder="Search by name or emp code…"
          value={searchVal}
          onChange={e => setSearchVal(e.target.value)}
          allowClear
          style={{ width: 260 }}
        />
        <Select
          placeholder="Filter by location"
          options={locOptions}
          value={locFilter}
          onChange={setLocFilter}
          allowClear
          style={{ width: 200 }}
        />
        <Select
          placeholder="Filter by department"
          options={deptOptions}
          value={deptFilter}
          onChange={setDeptFilter}
          allowClear
          style={{ width: 200 }}
        />
        <Text type="secondary" style={{ lineHeight: '32px', fontSize: 12 }}>
          {personnel.length} personnel found
        </Text>
      </div>
      <Table
        columns={personnelCols}
        dataSource={personnel.map(p => ({ ...p, key: p.id }))}
        loading={personnelLoading}
        size="small"
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: t => `${t} total` }}
        rowClassName={r => r.rotation_overdue ? 'pob-row-overdue' : ''}
        scroll={{ x: 900 }}
      />
    </>
  );

  const tabRotations = (
    <>
      {rotOverdue.length > 0 && (
        <Alert
          type="error"
          showIcon
          icon={<FireOutlined />}
          message={`${rotOverdue.length} personnel have exceeded the ${rotationRaw?.rotation_max_days || 28}-day rotation limit and require immediate relief.`}
          style={{ marginBottom: 16 }}
        />
      )}
      <Table
        columns={rotCols}
        dataSource={rotOverdue.map(r => ({ ...r, key: r.id }))}
        loading={rotationLoading}
        size="small"
        pagination={{ pageSize: 20, showSizeChanger: true }}
        locale={{ emptyText: <Empty description="No rotation overdue — all personnel within limits" /> }}
        rowClassName={() => 'pob-row-overdue'}
        scroll={{ x: 800 }}
      />
    </>
  );

  const tabTransports = (
    <>
      {transports.length === 0 ? (
        <Empty description="No active transports scheduled" style={{ padding: '48px 0' }} />
      ) : (
        <Table
          columns={transportCols}
          dataSource={transports.map((t, i) => ({ ...t, key: t.id || i }))}
          pagination={false}
          size="small"
        />
      )}
    </>
  );

  // ── render ─────────────────────────────────────────────────────────────
  if (dashLoading && !dash.total) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" tip="Loading POB Status…"><span /></Spin>
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>POB Status — Personnel On Board</Title>
          {dataUpdatedAt > 0 && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              <ClockCircleOutlined style={{ marginRight: 4 }} />
              Updated {dayjs(dataUpdatedAt).fromNow()}
            </Text>
          )}
        </div>
        <Space>
          <Button icon={<ExportOutlined />} onClick={downloadCSV}>Export CSV</Button>
          <Button icon={<ReloadOutlined />} onClick={() => refetchDash()}>Refresh</Button>
        </Space>
      </div>

      {/* ── KPI strip ── */}
      <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
        <Col xs={12} sm={8} md={8} lg={24 / 5}>
          <KpiCard
            title="Total POB"
            value={total}
            icon={<TeamOutlined />}
            color={C.offshore}
            subtitle="Personnel onboard"
            trend={<TrendArrow today={ciToday} yesterday={ciYest} />}
          />
        </Col>
        <Col xs={12} sm={8} md={8} lg={24 / 5}>
          <KpiCard
            title="Offshore"
            value={offshore}
            icon={<EnvironmentOutlined />}
            color="#0EA5E9"
            subtitle={`${pct(offshore, total)}% of total`}
            onClick={() => { setLocFilter(null); setActiveTab('personnel'); }}
          />
        </Col>
        <Col xs={12} sm={8} md={8} lg={24 / 5}>
          <KpiCard
            title="Onshore"
            value={onshore}
            icon={<EnvironmentOutlined />}
            color={C.onshore}
            subtitle={`${pct(onshore, total)}% of total`}
            onClick={() => { setLocFilter(null); setActiveTab('personnel'); }}
          />
        </Col>
        <Col xs={12} sm={8} md={8} lg={24 / 5}>
          <KpiCard
            title="In Transit"
            value={transit}
            icon={<CarOutlined />}
            color={C.transit}
            subtitle={`${pct(transit, total)}% of total`}
            onClick={() => setActiveTab('transports')}
          />
        </Col>
        <Col xs={12} sm={8} md={8} lg={24 / 5}>
          <KpiCard
            title="Rotation Overdue"
            value={overdueCnt}
            icon={<WarningOutlined />}
            color={overdueCnt > 0 ? C.overdue : '#9CA3AF'}
            subtitle={`>${dash.rotation_max_days || 28} days onboard`}
            onClick={overdueCnt > 0 ? () => setActiveTab('rotations') : null}
          />
        </Col>
      </Row>

      {/* ── Tabs ── */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="small"
        items={[
          {
            key: 'overview',
            label: <Space><EnvironmentOutlined />Overview</Space>,
            children: tabOverview,
          },
          {
            key: 'analytics',
            label: <Space><RiseOutlined />Analytics</Space>,
            children: tabAnalytics,
          },
          {
            key: 'personnel',
            label: (
              <Space>
                <TeamOutlined />
                Personnel Manifest
                <Badge count={total} overflowCount={9999} style={{ background: C.offshore }} />
              </Space>
            ),
            children: tabPersonnel,
          },
          {
            key: 'rotations',
            label: (
              <Space>
                <WarningOutlined />
                Rotations
                {overdueCnt > 0 && <Badge count={overdueCnt} style={{ background: C.overdue }} />}
              </Space>
            ),
            children: tabRotations,
          },
          {
            key: 'transports',
            label: (
              <Space>
                <CarOutlined />
                Transports
                {transports.length > 0 && <Badge count={transports.length} style={{ background: C.transit }} />}
              </Space>
            ),
            children: tabTransports,
          },
        ]}
      />

      {/* ── Location drill-down modal ── */}
      <Modal
        open={!!drillLoc}
        title={
          <Space>
            <EnvironmentOutlined style={{ color: C.offshore }} />
            Personnel at — {drillLoc}
          </Space>
        }
        onCancel={() => setDrillLoc(null)}
        footer={null}
        width={780}
        destroyOnHidden
      >
        {drillLoading ? (
          <div style={{ textAlign: 'center', padding: 32 }}><Spin /></div>
        ) : (
          <>
            <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
              {drillRaw?.total || 0} personnel currently at this location
            </Text>
            <Table
              columns={personnelCols.filter(c => c.key !== 'location')}
              dataSource={(drillRaw?.data || []).map(p => ({ ...p, key: p.id }))}
              size="small"
              pagination={{ pageSize: 10 }}
              scroll={{ x: 600 }}
            />
          </>
        )}
      </Modal>

      <style>{`
        .pob-row-overdue td { background: #FFF5F5 !important; }
        .pob-row-overdue:hover td { background: #FEE2E2 !important; }
      `}</style>
    </div>
  );
}
