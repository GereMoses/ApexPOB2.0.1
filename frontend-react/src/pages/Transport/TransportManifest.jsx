import React, { useState, useCallback } from 'react';
import {
  Table, Button, Select, DatePicker, Drawer, Descriptions,
  Form, Input, InputNumber, AutoComplete, Modal, Alert, App, Tabs, Dropdown, Card, Space, Tooltip, Tag, Checkbox,
} from 'antd';
import {
  PlusOutlined, CheckCircleOutlined, CloseCircleOutlined, SyncOutlined,
  ArrowUpOutlined, ArrowDownOutlined, ExclamationCircleOutlined,
  AuditOutlined, ReloadOutlined, DeleteOutlined, MoreOutlined,
  SearchOutlined, WarningOutlined, SafetyCertificateOutlined, QrcodeOutlined,
  TeamOutlined, InboxOutlined, CarOutlined, BellOutlined, DownloadOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import apiService from '../../services/api';
import LandJourneys from './LandJourneys';

// Shown as the first format; any of them can be typed (the reschedule box only took
// "DD MMM YYYY HH:mm" — a typed 2026-10-30 13:20 was silently ignored).
const DT_FORMATS = ['DD MMM YYYY HH:mm', 'YYYY-MM-DD HH:mm', 'YYYY-MM-DD HH:mm:ss', 'DD/MM/YYYY HH:mm'];

const TRANSPORT_TYPES = [
  { value: 3, label: 'Helicopter' },
  { value: 4, label: 'Vessel' },
  { value: 1, label: 'Fixed Wing' },
  { value: 2, label: 'Vehicle' },
];

const FLIGHT_STATUS_CFG = {
  SCHEDULED:  { color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe', label: 'Scheduled'  },
  CONFIRMED:  { color: '#0891b2', bg: '#ecfeff', border: '#a5f3fc', label: 'Confirmed'  },
  IN_TRANSIT: { color: '#d97706', bg: '#fffbeb', border: '#fde68a', label: 'In Transit' },
  COMPLETED:  { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', label: 'Completed'  },
  CANCELLED:  { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: 'Cancelled'  },
};

const ENTRY_STATUS_CFG = {
  MANIFESTED: { color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe', label: 'Manifested' },
  CONFIRMED:  { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', label: 'Confirmed'  },
  NO_SHOW:    { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: 'No Show'    },
  OFFLOADED:  { color: '#d97706', bg: '#fffbeb', border: '#fde68a', label: 'Offloaded'  },
};

const DIRECTION_CFG = {
  INBOUND:  { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', label: 'Inbound'  },
  OUTBOUND: { color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe', label: 'Outbound' },
};

const TRANSPORT_TYPE_CFG = {
  3: { color: '#7c3aed', bg: '#ede9fe', border: '#ddd6fe', label: 'Helicopter' },
  4: { color: '#0891b2', bg: '#ecfeff', border: '#a5f3fc', label: 'Vessel'     },
  1: { color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe', label: 'Fixed Wing' },
  2: { color: '#64748b', bg: '#f8fafc', border: '#e2e8f0', label: 'Vehicle'    },
};

const StatusPill = ({ status, cfg }) => {
  const c = cfg?.[status] || { color: '#64748b', bg: '#f8fafc', border: '#e2e8f0', label: status };
  return (
    <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600, color: c.color, background: c.bg, border: `1px solid ${c.border}` }}>
      {c.label}
    </span>
  );
};

const TransportPill = ({ type }) => {
  const c = TRANSPORT_TYPE_CFG[type] || { color: '#64748b', bg: '#f8fafc', border: '#e2e8f0', label: `Type ${type}` };
  return (
    <span style={{ display: 'inline-block', padding: '1px 7px', borderRadius: 999, fontSize: 11, fontWeight: 600, color: c.color, background: c.bg, border: `1px solid ${c.border}` }}>
      {c.label}
    </span>
  );
};

const StatCard = ({ label, value, color, icon }) => (
  <div style={{ flex: 1, background: '#fff', borderRadius: 8, padding: '14px 16px', borderTop: `3px solid ${color}`, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
      <span style={{ fontSize: 12, color: '#64748b' }}>{label}</span>
      {icon && <span style={{ color, fontSize: 14, background: `${color}18`, borderRadius: 6, padding: '3px 6px', display: 'flex' }}>{icon}</span>}
    </div>
    <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
  </div>
);

// Fitness-to-travel indicator (medical + safety training/cert validity)
const COMPLIANCE_CFG = {
  ok:      { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', label: 'Fit' },
  warning: { color: '#d97706', bg: '#fffbeb', border: '#fde68a', label: 'Check' },
  blocked: { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: 'Unfit' },
  unknown: { color: '#64748b', bg: '#f8fafc', border: '#e2e8f0', label: 'No records' },
};

// Allowed flight status changes (mirrors the server). POB moves on DEPARTED
// (outbound off) and ARRIVED/Completed (inbound on); cancelling in transit undoes it.
const FLIGHT_NEXT = {
  SCHEDULED:  ['CONFIRMED', 'IN_TRANSIT', 'COMPLETED', 'CANCELLED'],
  CONFIRMED:  ['SCHEDULED', 'IN_TRANSIT', 'COMPLETED', 'CANCELLED'],
  IN_TRANSIT: ['COMPLETED', 'CANCELLED'],
  CANCELLED:  ['SCHEDULED'],
  COMPLETED:  [],
};
const ComplianceTag = ({ c }) => {
  if (!c) return null;
  const cfg = COMPLIANCE_CFG[c.status] || COMPLIANCE_CFG.warning;
  return (
    <Tooltip title={c.issues?.length ? c.issues.join(' · ') : 'All travel records valid'}>
      <span style={{ padding: '0 7px', borderRadius: 999, fontSize: 10, fontWeight: 700, whiteSpace: 'nowrap',
        color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}` }}>
        {cfg.label}
      </span>
    </Tooltip>
  );
};

// ─── Flight list ──────────────────────────────────────────────────────────────

function FlightList({ onSelectFlight }) {
  const { message } = App.useApp();
  const [flightForm] = Form.useForm();
  const [showCreate, setShowCreate] = useState(false);
  const [dateRange, setDateRange] = useState([dayjs().subtract(7, 'day'), dayjs().add(7, 'day')]);
  const [statusFilter, setStatusFilter] = useState(null);
  const qc = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['transport-flights', dateRange, statusFilter],
    queryFn: () => apiService.get('/api/v1/transport/flights', {
      date_from: dateRange[0].format('YYYY-MM-DD'),
      date_to:   dateRange[1].format('YYYY-MM-DD'),
      ...(statusFilter ? { status: statusFilter } : {}),
    }),
  });

  const { data: analytics } = useQuery({
    queryKey: ['transport-analytics'],
    queryFn: () => apiService.get('/api/v1/transport/analytics'),
    refetchInterval: 60_000,
  });

  const createFlight = useMutation({
    mutationFn: (values) => apiService.post('/api/v1/transport/flights', {
      transport_identifier: values.transport_identifier,
      transport_type: values.transport_type,
      transport_operator: values.transport_operator,
      transport_capacity: values.transport_capacity || 12,
      transport_max_payload_kg: values.transport_max_payload_kg || undefined,
      schedule_type: values.schedule_type || 'CHARTER',
      departure_location: values.departure_location,
      arrival_location: values.arrival_location,
      departure_time: values.departure_time.toISOString(),
      arrival_time: values.arrival_time ? values.arrival_time.toISOString() : undefined,
      notes: values.notes,
      repeat_frequency: values.repeat_frequency || undefined,
      repeat_count: values.repeat_frequency ? (values.repeat_count || 1) : 1,
    }),
    onSuccess: (res) => {
      const n = res?.occurrences_created || 1;
      message.success(n > 1 ? `${n} journeys created` : 'Journey created');
      qc.invalidateQueries({ queryKey: ['transport-flights'] });
      flightForm.resetFields();
      setShowCreate(false);
    },
    onError: (e) => message.error(e.message || 'Failed to create flight'),
  });

  const flights = data?.flights ?? [];
  // Known locations for the From/To combo boxes (from existing journeys); free text still allowed.
  const locOpts = [...new Set(flights.flatMap(f => [f.departure_location, f.arrival_location]).filter(Boolean))].map(v => ({ value: v }));

  const columns = [
    {
      title: 'Journey',
      render: (_, row) => (
        <div>
          <div style={{ fontWeight: 700, color: '#1e293b' }}>{row.transport?.identifier ?? '—'}</div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 3 }}>
            <TransportPill type={row.transport?.type} />
            {row.transport?.operator && <span style={{ fontSize: 11, color: '#64748b' }}>{row.transport.operator}</span>}
          </div>
        </div>
      ),
    },
    {
      title: 'Route',
      render: (_, row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontWeight: 500 }}>{row.departure_location}</span>
          <span style={{ color: '#94a3b8', fontSize: 11 }}>→</span>
          <span style={{ fontWeight: 500 }}>{row.arrival_location}</span>
        </div>
      ),
    },
    {
      title: 'Departure',
      dataIndex: 'departure_time',
      render: (v) => v ? dayjs(v).format('DD MMM HH:mm') : '—',
      sorter: (a, b) => new Date(a.departure_time) - new Date(b.departure_time),
      defaultSortOrder: 'ascend',
    },
    {
      title: 'PAX',
      render: (_, row) => (
        <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
          <span title="Confirmed" style={{ padding: '1px 7px', borderRadius: 999, fontSize: 11, fontWeight: 700, color: '#16a34a', background: '#f0fdf4', border: '1px solid #bbf7d0' }}>
            {row.pax_confirmed}
          </span>
          <span title="Manifested" style={{ padding: '1px 7px', borderRadius: 999, fontSize: 11, fontWeight: 700, color: '#2563eb', background: '#eff6ff', border: '1px solid #bfdbfe' }}>
            {row.pax_manifested}
          </span>
          {row.pax_no_show > 0 && (
            <span title="No Show" style={{ padding: '1px 7px', borderRadius: 999, fontSize: 11, fontWeight: 700, color: '#dc2626', background: '#fef2f2', border: '1px solid #fecaca' }}>
              {row.pax_no_show}
            </span>
          )}
          <span style={{ fontSize: 11, color: '#94a3b8' }}>/ {row.transport?.capacity ?? '?'}</span>
        </div>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 110,
      render: (s) => <StatusPill status={s} cfg={FLIGHT_STATUS_CFG} />,
    },
    {
      title: '',
      width: 70,
      render: (_, row) => (
        <Button
          size="small"
          type="primary"
          ghost
          onClick={(e) => { e.stopPropagation(); onSelectFlight(row); }}
        >
          Open
        </Button>
      ),
    },
  ];

  return (
    <>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 14 }}>
        <DatePicker.RangePicker
          value={dateRange}
          onChange={(v) => v && setDateRange(v)}
          format="DD MMM"
          size="small"
        />
        <Select
          placeholder="All statuses"
          allowClear
          size="small"
          style={{ width: 140 }}
          value={statusFilter}
          onChange={setStatusFilter}
          options={Object.entries(FLIGHT_STATUS_CFG).map(([v, c]) => ({ value: v, label: c.label }))}
        />
        <Button icon={<ReloadOutlined />} size="small" onClick={() => refetch()} />
        <div style={{ marginLeft: 'auto' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowCreate(true)}>
            New Journey
          </Button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
        <StatCard label="Total Journeys" value={flights.length} color="#64748b" />
        <StatCard label="Scheduled" value={flights.filter(f => f.status === 'SCHEDULED').length} color="#2563eb" icon={<AuditOutlined />} />
        <StatCard label="In Transit" value={flights.filter(f => f.status === 'IN_TRANSIT').length} color="#d97706" icon={<SyncOutlined />} />
        <StatCard label="Completed" value={flights.filter(f => f.status === 'COMPLETED').length} color="#16a34a" icon={<CheckCircleOutlined />} />
        <StatCard label="Flights Today" value={analytics?.flights_today ?? 0} color="#0ea5e9" />
        <StatCard label="PAX Moved Today" value={analytics?.pax_moved_today ?? 0} color="#7c3aed" />
        <StatCard label="On-time" value={analytics?.on_time_pct != null ? `${analytics.on_time_pct}%` : '—'} color="#16a34a" />
      </div>

      <div style={{ background: '#fff', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', overflow: 'hidden' }}>
        <Table
          dataSource={flights}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          pagination={{ pageSize: 15 }}
          size="small"
          rowClassName={(r) => {
            if (r.status === 'CANCELLED') return 'row-flight-cancelled';
            if (r.status === 'IN_TRANSIT') return 'row-flight-transit';
            if (r.status === 'COMPLETED')  return 'row-flight-completed';
            return '';
          }}
          onRow={(row) => ({ onClick: () => onSelectFlight(row), style: { cursor: 'pointer' } })}
        />
      </div>

      <Modal
        title="New Journey"
        open={showCreate}
        onCancel={() => setShowCreate(false)}
        onOk={() => flightForm.submit()}
        confirmLoading={createFlight.isPending}
        width={600}
      >
        <Form form={flightForm} layout="vertical" onFinish={(v) => createFlight.mutate(v)}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
            <Form.Item name="transport_identifier" label="Transport ID / Tail No." rules={[{ required: true }]}>
              <Input placeholder="e.g. ZS-HEL1" />
            </Form.Item>
            <Form.Item name="transport_type" label="Type" initialValue={3}>
              <Select options={TRANSPORT_TYPES} />
            </Form.Item>
            <Form.Item name="transport_operator" label="Operator">
              <Input placeholder="e.g. Offshore Air" />
            </Form.Item>
            <Form.Item name="transport_capacity" label="Capacity" initialValue={12}>
              <Input type="number" min={1} />
            </Form.Item>
            <Form.Item name="transport_max_payload_kg" label="Max payload (kg)"
              tooltip="Weight-and-balance limit — boarding is blocked above this (with override)">
              <InputNumber min={0} style={{ width: '100%' }} placeholder="optional" />
            </Form.Item>
            <Form.Item name="departure_location" label="From" rules={[{ required: true }]}>
              <AutoComplete options={locOpts} placeholder="Select or type a location"
                filterOption={(i, o) => (o?.value ?? '').toLowerCase().includes(i.toLowerCase())} />
            </Form.Item>
            <Form.Item name="arrival_location" label="To" rules={[{ required: true }]}>
              <AutoComplete options={locOpts} placeholder="Select or type a location"
                filterOption={(i, o) => (o?.value ?? '').toLowerCase().includes(i.toLowerCase())} />
            </Form.Item>
            <Form.Item name="departure_time" label="Departure Time" rules={[{ required: true }]}>
              <DatePicker showTime format={DT_FORMATS} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="arrival_time" label="ETA (optional)" dependencies={['departure_time']}
              rules={[({ getFieldValue }) => ({
                validator: (_, v) => (!v || !getFieldValue('departure_time') || v.isAfter(getFieldValue('departure_time'))
                  ? Promise.resolve() : Promise.reject(new Error('ETA must be after departure'))),
              })]}>
              <DatePicker showTime format={DT_FORMATS} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
            <Form.Item name="schedule_type" label="Schedule Type" initialValue="CHARTER">
              <Select options={[
                { value: 'REGULAR', label: 'Regular' },
                { value: 'CHARTER', label: 'Charter' },
                { value: 'STANDBY', label: 'Standby' },
              ]} />
            </Form.Item>
            <Form.Item name="repeat_frequency" label="Repeat"
              tooltip="Generate a recurring series (e.g. weekly crew changes)">
              <Select allowClear placeholder="One-off" options={[
                { value: 'DAILY', label: 'Daily' },
                { value: 'WEEKLY', label: 'Weekly' },
              ]} />
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(p, c) => p.repeat_frequency !== c.repeat_frequency}>
              {({ getFieldValue }) => getFieldValue('repeat_frequency') ? (
                <Form.Item name="repeat_count" label="Occurrences" initialValue={4}>
                  <InputNumber min={1} max={60} style={{ width: '100%' }} />
                </Form.Item>
              ) : null}
            </Form.Item>
          </div>
          <Form.Item name="notes" label="Notes">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

// ─── Manifest drawer ──────────────────────────────────────────────────────────

// What the passengers were told, in one line ("WhatsApp 3 · Email 2 · 1 guest has no contact on file").
const notifySummary = (r) => {
  if (!r) return { ok: false, text: 'Nothing sent' };
  const NAMES = { whatsapp: 'WhatsApp', telegram: 'Telegram', email: 'Email', sms: 'SMS' };
  const parts = Object.entries(r.channels || {})
    .filter(([, v]) => (v.sent || 0) > 0 || (v.failed || 0) > 0)
    .map(([k, v]) => `${NAMES[k] || k} ${v.sent || 0}${v.failed ? ` (${v.failed} failed)` : ''}`);
  const gaps = [];
  if (r.guests) gaps.push(`${r.guests} guest(s) have no contact on file`);
  if (r.unreachable) gaps.push(`${r.unreachable} staff have no phone/email`);
  if (!r.registered && !r.guests) gaps.push('no passengers to tell');
  return { ok: !!r.sent_any, text: [parts.join(' · ') || 'Nothing sent', ...gaps].join(' — ') };
};

function ManifestDrawer({ flight: picked, onClose }) {
  const { message, modal } = App.useApp();
  const [addForm] = Form.useForm();
  const [crewForm] = Form.useForm();
  const [cargoForm] = Form.useForm();
  const [notifyForm] = Form.useForm();
  const [showAdd, setShowAdd] = useState(false);
  const [showCrew, setShowCrew] = useState(false);
  const [showCargo, setShowCargo] = useState(false);
  const [showNotify, setShowNotify] = useState(false);
  const [paxOptions, setPaxOptions] = useState([]);
  const [reconcileResult, setReconcileResult] = useState(null);
  const [reconciling, setReconciling] = useState(false);
  const [badgeCode, setBadgeCode] = useState('');
  const [showEdit, setShowEdit] = useState(false);
  const [editForm] = Form.useForm();
  const [paxEdit, setPaxEdit] = useState(null);          // manifest entry being weighed / corrected
  const [paxForm] = Form.useForm();
  const openPaxEdit = (row) => {
    setPaxEdit(row);
    paxForm.setFieldsValue({ body_weight: row.body_weight, baggage_weight: row.baggage_weight, direction: row.direction,
                             company: row.company, id_number: row.id_number, remarks: row.remarks });
  };
  const qc = useQueryClient();

  const editFlight = useMutation({
    mutationFn: (v) => apiService.put(`/api/v1/transport/flights/${flight.id}`, {
      departure_location: v.departure_location, arrival_location: v.arrival_location,
      departure_time: v.departure_time?.toISOString(),
      arrival_time: v.arrival_time ? v.arrival_time.toISOString() : null,
      notes: v.notes, notify: v.notify !== false,
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['transport-flights'] });
      qc.invalidateQueries({ queryKey: ['manifest', flight.id] });
      if (res?.notified) {
        const n = notifySummary(res.notified);
        (n.ok ? message.success : message.warning)(`Flight updated — passengers: ${n.text}`, 8);
      } else message.success('Flight updated');
      setShowEdit(false);
    },
    onError: (e) => message.error(e?.response?.data?.detail || e.message || 'Failed to update flight'),
  });

  const { data, isLoading } = useQuery({
    queryKey: ['manifest', picked?.id],
    queryFn: () => apiService.get(`/api/v1/transport/flights/${picked.id}/manifest`),
    enabled: !!picked,
  });
  // The row clicked in the list is a snapshot — after a status change or reschedule the
  // drawer kept showing the old status/time and offering the wrong next steps. Use the
  // live copy returned with the manifest.
  const flight = picked ? { ...picked, ...(data?.summary || {}) } : null;

  const searchPersonnel = useCallback(async (term) => {
    if (term.length < 2) return;
    try {
      const res = await apiService.get('/api/v1/transport/personnel-search', { q: term });
      setPaxOptions((res || []).map(p => ({
        value: p.name,
        label: `${p.name} (${p.emp_code})`,
        emp_code: p.emp_code,
        company: p.company,
      })));
    } catch (_) {}
  }, []);

  const addEntry = useMutation({
    mutationFn: (values) => apiService.post(`/api/v1/transport/flights/${flight.id}/manifest`, {
      passenger_name: values.passenger_name,
      direction: values.direction,
      emp_code: values.emp_code,
      company: values.company,
      id_number: values.id_number,
      body_weight: values.body_weight,
      baggage_weight: values.baggage_weight,
      remarks: values.remarks,
    }),
    onSuccess: (res) => {
      const c = res?.compliance;
      if (c?.status === 'blocked') message.error(`Added — NOT fit to travel: ${c.issues.join('; ')}`, 6);
      else if (c?.status === 'warning') message.warning(`Added — ${c.issues.join('; ')}`, 5);
      else message.success('Passenger added');
      if (res?.pob_note) message.warning(res.pob_note, 6);
      qc.invalidateQueries({ queryKey: ['manifest', flight.id] });
      qc.invalidateQueries({ queryKey: ['transport-flights'] });
      addForm.resetFields();
      setShowAdd(false);
    },
    onError: (e) => message.error(e.message || 'Failed to add passenger'),
  });

  const checkinBadge = useMutation({
    mutationFn: (emp_code) => apiService.post(`/api/v1/transport/flights/${flight.id}/checkin`, { emp_code }),
    onSuccess: (res) => {
      message.success(res?.already_checked_in ? `${res?.passenger_name || res?.emp_code} is already checked in`
        : `${res?.passenger_name || res?.emp_code || 'Passenger'} checked in`);
      setBadgeCode('');
      qc.invalidateQueries({ queryKey: ['manifest', flight.id] });
      qc.invalidateQueries({ queryKey: ['transport-flights'] });
      qc.invalidateQueries({ queryKey: ['pob-summary'] });
    },
    onError: (e) => message.error(e?.response?.data?.detail || e.message || 'Check-in failed'),
  });

  const updateEntry = useMutation({
    mutationFn: ({ entryId, status, override_capacity, override_compliance, override_weight, remarks }) =>
      apiService.patch(`/api/v1/transport/flights/${flight.id}/manifest/${entryId}`,
        { status, override_capacity, override_compliance, override_weight, remarks }),
    onSuccess: (r, v) => {
      message.success({ CONFIRMED: `${r?.passenger_name || 'Passenger'} checked in`, NO_SHOW: `${r?.passenger_name || 'Passenger'} marked no-show`,
        MANIFESTED: `${r?.passenger_name || 'Passenger'} reset to manifested`, OFFLOADED: `${r?.passenger_name || 'Passenger'} offloaded` }[v.status] || 'Updated');
      qc.invalidateQueries({ queryKey: ['manifest', flight.id] });
      qc.invalidateQueries({ queryKey: ['transport-flights'] });
      qc.invalidateQueries({ queryKey: ['pob-summary'] });
    },
    onError: (e, vars) => {
      const alreadyOverridden = vars?.override_capacity && vars?.override_compliance && vars?.override_weight;
      // Any safety hard-block (capacity / fitness-to-travel / weight-and-balance)
      // comes back as 409 — surface the reason and require an explicit override.
      if (e?.status === 409 && vars?.status === 'CONFIRMED' && /weight missing/i.test(e.message || '')) {
        // Missing weight is a data gap, not a judgement call: weigh them in.
        const row = (data?.entries || []).find(x => x.id === vars.entryId);
        modal.confirm({
          title: 'Weight needed before boarding',
          icon: <WarningOutlined style={{ color: '#d97706' }} />,
          content: e.message,
          okText: 'Enter weight', cancelText: 'Cancel',
          onOk: () => { if (row) openPaxEdit(row); },
        });
      } else if (e?.status === 409 && vars?.status === 'CONFIRMED' && !alreadyOverridden) {
        // An override is an accountable decision: a reason is required and recorded
        // on the passenger (and needs the transport.override permission).
        let reason = '';
        // Override stays disabled until a reason is typed (an accountable decision).
        const dlg = modal.confirm({
          title: 'Boarding blocked',
          icon: <WarningOutlined style={{ color: '#dc2626' }} />,
          content: (
            <div>
              <div style={{ marginBottom: 6 }}>Overriding boards this passenger despite <b>every</b> problem below:</div>
              <ul style={{ margin: '0 0 10px 18px', padding: 0, color: '#b91c1c' }}>
                {(e.message || '').replace(/\. Fix it, or override with a reason\.?$/, '').split('. ').filter(Boolean).map((t, i) => <li key={i}>{t}</li>)}
              </ul>
              <Input.TextArea rows={2} placeholder="Reason for overriding (required)"
                onChange={(ev) => { reason = ev.target.value; dlg.update({ okButtonProps: { danger: true, disabled: !reason.trim() } }); }} />
            </div>
          ),
          okType: 'danger', okText: 'Override & confirm', okButtonProps: { danger: true, disabled: true },
          onOk: () => {
            updateEntry.mutate({
              ...vars, override_capacity: true, override_compliance: true, override_weight: true,
              remarks: reason.trim(),
            });
            return undefined;
          },
        });
      } else {
        message.error(e.message || 'Failed to update');
      }
    },
  });

  const setCrew = useMutation({
    mutationFn: (crew) => apiService.put(`/api/v1/transport/flights/${flight.id}/crew`, { crew }),
    onSuccess: () => {
      message.success('Crew updated');
      qc.invalidateQueries({ queryKey: ['manifest', flight.id] });
      setShowCrew(false);
    },
    onError: (e) => message.error(e.message || 'Failed to update crew'),
  });

  const setCargo = useMutation({
    mutationFn: (items) => apiService.put(`/api/v1/transport/flights/${flight.id}/cargo`, { items }),
    onSuccess: (r) => {
      if (r?.warning) message.warning(`Cargo saved — ${r.warning}`, 10); else message.success('Cargo updated');
      qc.invalidateQueries({ queryKey: ['manifest', flight.id] });
      setShowCargo(false);
    },
    onError: (e) => message.error(e.message || 'Failed to update cargo'),
  });

  const notifyPax = useMutation({
    mutationFn: (v) => apiService.post(`/api/v1/transport/flights/${flight.id}/notify`, v),
    onSuccess: (res) => {
      const n = notifySummary(res?.result);
      (n.ok ? message.success : message.warning)(`Passengers: ${n.text}`, 8);
      setShowNotify(false);
    },
    onError: (e) => message.error(e.message || 'Failed to notify'),
  });

  const downloadManifest = async () => {
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('authToken');
      const res = await fetch(`/api/v1/transport/flights/${flight.id}/manifest.xlsx`,
        { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `manifest_${flight?.transport?.identifier || flight.id}.xlsx`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      message.error('Export failed');
    }
  };

  const savePax = useMutation({
    mutationFn: (v) => apiService.put(`/api/v1/transport/flights/${flight.id}/manifest/${paxEdit.id}`, v),
    onSuccess: () => {
      message.success('Passenger details saved');
      qc.invalidateQueries({ queryKey: ['manifest', flight.id] });
      qc.invalidateQueries({ queryKey: ['transport-flights'] });
      setPaxEdit(null);
    },
    onError: (e) => message.error(e.message || 'Could not save'),
  });

  const deleteFlight = useMutation({
    mutationFn: () => apiService.delete(`/api/v1/transport/flights/${flight.id}`),
    onSuccess: () => {
      message.success('Journey deleted');
      qc.invalidateQueries({ queryKey: ['transport-flights'] });
      qc.invalidateQueries({ queryKey: ['transport-analytics'] });
      onClose();
    },
    onError: (e) => message.error(e.message || 'Could not delete'),
  });

  const deleteEntry = useMutation({
    mutationFn: (entryId) =>
      apiService.delete(`/api/v1/transport/flights/${flight.id}/manifest/${entryId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['manifest', flight.id] });
      qc.invalidateQueries({ queryKey: ['transport-flights'] });
    },
    onError: (e) => message.error(e.message || 'Failed to delete'),
  });

  const updateFlightStatus = useMutation({
    mutationFn: (newStatus) =>
      apiService.patch(`/api/v1/transport/flights/${flight.id}/status`, { status: newStatus }),
    onSuccess: (r, newStatus) => {
      qc.invalidateQueries({ queryKey: ['transport-flights'] });
      qc.invalidateQueries({ queryKey: ['pob-summary'] });
      qc.invalidateQueries({ queryKey: ['manifest', flight.id] });
      qc.invalidateQueries({ queryKey: ['transport-analytics'] });
      const told = r?.notified ? ` Passengers: ${notifySummary(r.notified).text}.` : '';
      message.success(
        (newStatus === 'IN_TRANSIT' ? 'Departed — outbound passengers taken off POB.'
        : newStatus === 'COMPLETED' ? 'Completed — inbound passengers added to POB.'
        : newStatus === 'CANCELLED' ? 'Cancelled — any POB changes undone.'
        : 'Flight status updated.') + told, 8);
    },
    onError: (e) => message.error(e?.response?.data?.detail || e.message || 'Failed to update flight status'),
  });

  const runReconcile = async () => {
    setReconciling(true);
    try {
      const result = await apiService.get(`/api/v1/transport/flights/${flight.id}/reconcile`);
      setReconcileResult(result);
    } catch (e) {
      message.error(e.message || 'Reconciliation failed');
    } finally {
      setReconciling(false);
    }
  };

  const confirmDelete = (entryId) => modal.confirm({
    title: 'Remove from manifest?',
    content: 'This passenger will be removed from this flight.',
    okType: 'danger',
    okText: 'Remove',
    onOk: () => deleteEntry.mutateAsync(entryId).catch(() => {}),
  });

  const entries = data?.entries ?? [];
  const summary = data?.summary ?? {};
  const inbound  = entries.filter(e => e.direction === 'INBOUND');
  const outbound = entries.filter(e => e.direction === 'OUTBOUND');
  const confirmedInbound  = inbound.filter(e => e.status === 'CONFIRMED').length;
  const confirmedOutbound = outbound.filter(e => e.status === 'CONFIRMED').length;
  const outstanding = entries.filter(e => e.status === 'MANIFESTED').length;
  const noShows    = entries.filter(e => e.status === 'NO_SHOW').length;

  // Server enforces the safety gates (fitness-to-travel, capacity, weight & balance)
  // and returns 409 with the reason; the updateEntry 409 handler drives the override.
  const confirmPax = (row) => updateEntry.mutate({ entryId: row.id, status: 'CONFIRMED' });

  const makeEntryMenuItems = (row) => [
    row.status !== 'CONFIRMED' && {
      key: 'confirm',
      icon: <CheckCircleOutlined style={{ color: '#16a34a' }} />,
      label: 'Confirm',
      onClick: () => confirmPax(row),
    },
    row.status !== 'NO_SHOW' && {
      key: 'noshow',
      icon: <CloseCircleOutlined style={{ color: '#dc2626' }} />,
      label: 'Mark No Show',
      onClick: () => updateEntry.mutate({ entryId: row.id, status: 'NO_SHOW' }),
    },
    row.status !== 'MANIFESTED' && {
      key: 'reset',
      icon: <SyncOutlined />,
      label: 'Reset to Manifested',
      onClick: () => updateEntry.mutate({ entryId: row.id, status: 'MANIFESTED' }),
    },
    !['IN_TRANSIT', 'COMPLETED', 'CANCELLED'].includes(flight?.status) && {
      key: 'edit',
      icon: <AuditOutlined />,
      label: 'Edit details / weigh-in',
      onClick: () => openPaxEdit(row),
    },
    { type: 'divider' },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: 'Remove',
      danger: true,
      onClick: () => confirmDelete(row.id),
    },
  ].filter(Boolean);

  const entryColumns = [
    {
      title: 'Passenger',
      dataIndex: 'passenger_name',
      render: (name, row) => (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontWeight: 600 }}>{name}</span>
            <ComplianceTag c={row.compliance} />
          </div>
          {row.emp_code && (
            <div style={{ fontSize: 11, color: '#64748b' }}>
              {row.emp_code}{row.company ? ` · ${row.company}` : ''}
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Weight',
      width: 92,
      align: 'right',
      render: (_, r) => {
        if (r.body_weight == null && r.baggage_weight == null) return <span style={{ color: '#cbd5e1' }}>—</span>;
        return (
          <span style={{ fontSize: 12 }}>
            {r.body_weight || 0}
            <span style={{ color: '#94a3b8' }}> +{r.baggage_weight || 0}kg</span>
          </span>
        );
      },
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 115,
      render: (s) => <StatusPill status={s} cfg={ENTRY_STATUS_CFG} />,
    },
    {
      title: '',
      width: 50,
      render: (_, row) => (
        <Dropdown trigger={['click']} menu={{ items: makeEntryMenuItems(row) }}>
          <Button size="small" type="text" icon={<MoreOutlined />} />
        </Dropdown>
      ),
    },
  ];

  const sectionHeader = (label, count, color) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '16px 0 8px', borderBottom: '1px solid #f0f0f0', paddingBottom: 8 }}>
      {label === 'Inbound'
        ? <ArrowDownOutlined style={{ color }} />
        : <ArrowUpOutlined style={{ color }} />}
      <span style={{ fontWeight: 600, color }}>{label}</span>
      <span style={{ padding: '0 8px', borderRadius: 999, fontSize: 12, fontWeight: 600, color, background: `${color}18`, border: `1px solid ${color}40` }}>
        {count}
      </span>
    </div>
  );

  return (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <AuditOutlined />
          <span>Manifest — {flight?.transport?.identifier ?? `#${flight?.id}`}</span>
          {flight?.status && <StatusPill status={flight.status} cfg={FLIGHT_STATUS_CFG} />}
        </div>
      }
      width={720}
      open={!!flight}
      onClose={onClose}
      extra={
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Button size="small" icon={<BellOutlined />} onClick={() => setShowNotify(true)}>
            Notify
          </Button>
          <Button size="small" icon={<DownloadOutlined />} onClick={downloadManifest}>
            Export
          </Button>
          <Button
            size="small"
            icon={<SafetyCertificateOutlined />}
            loading={reconciling}
            onClick={runReconcile}
          >
            Reconcile
          </Button>
          {['SCHEDULED', 'CONFIRMED'].includes(flight?.status) && (
            <Button size="small" onClick={() => {
              editForm.setFieldsValue({
                departure_location: flight.departure_location, arrival_location: flight.arrival_location,
                departure_time: flight.departure_time ? dayjs(flight.departure_time) : null,
                arrival_time: flight.arrival_time ? dayjs(flight.arrival_time) : null,
                notify: true,
              });
              setShowEdit(true);
            }}>Reschedule</Button>
          )}
          <Select
            size="small"
            value={flight?.status}
            style={{ width: 130 }}
            onChange={(v) => {
              if (v === 'IN_TRANSIT' || v === 'COMPLETED' || v === 'CANCELLED') {
                // Before it moves: everything still wrong with this flight, in one place.
                const issues = (v === 'IN_TRANSIT' || v === 'COMPLETED') ? [
                  summary.over_payload && `Over the payload limit (${summary.total_weight_kg} / ${summary.max_payload_kg} kg)`,
                  summary.overbooked && `Overbooked (${summary.seats_taken} / ${summary.capacity} seats)`,
                  (summary.cargo || []).some(c => c.dangerous_goods && !c.un_number) && 'Dangerous goods without a UN number',
                  outstanding > 0 && `${outstanding} passenger(s) not checked in yet`,
                  !(summary.crew || []).length && 'No crew recorded',
                ].filter(Boolean) : [];
                modal.confirm({
                  title: `Mark flight ${FLIGHT_STATUS_CFG[v]?.label}?`,
                  okText: issues.length ? 'Depart anyway' : 'OK',
                  okButtonProps: issues.length ? { danger: true } : undefined,
                  content: <div>{issues.length > 0 && (
                    <Alert type="warning" showIcon style={{ marginBottom: 10 }} message="Check before it moves"
                      description={<ul style={{ margin: 0, paddingLeft: 18 }}>{issues.map(i => <li key={i}>{i}</li>)}</ul>} />)}
                    {v === 'IN_TRANSIT'
                    ? 'Boarded OUTBOUND passengers will be taken off POB.'
                    : v === 'COMPLETED'
                      ? 'Boarded INBOUND passengers will be added to POB (and outbound taken off if not already).'
                      : 'Any POB changes already made for this flight will be undone, and the passengers are told it is cancelled.'}</div>,
                  onOk: () => updateFlightStatus.mutate(v),
                });
              } else {
                updateFlightStatus.mutate(v);
              }
            }}
            options={[flight?.status, ...(FLIGHT_NEXT[flight?.status] || [])].filter(Boolean)
              .map(v => ({ value: v, label: FLIGHT_STATUS_CFG[v]?.label || v }))}
          />
          {['SCHEDULED', 'CONFIRMED', 'CANCELLED'].includes(flight?.status) && (
            <Tooltip title="Delete a journey created by mistake (only before anyone has checked in)">
              <Button size="small" danger icon={<DeleteOutlined />} loading={deleteFlight.isPending}
                onClick={() => modal.confirm({
                  title: 'Delete this journey?', okType: 'danger', okText: 'Delete',
                  content: 'The journey and its passenger list are removed. Use Cancelled instead if it was a real booking.',
                  onOk: () => deleteFlight.mutateAsync().catch(() => {}),   // error shown by onError
                })} />
            </Tooltip>
          )}
          {!['COMPLETED', 'CANCELLED'].includes(flight?.status) && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowAdd(true)}>
              Add PAX
            </Button>
          )}
        </div>
      }
    >
      {flight && (
        <>
          <Descriptions size="small" column={2} style={{ marginBottom: 12 }}>
            <Descriptions.Item label="Route">
              {flight.departure_location} → {flight.arrival_location}
            </Descriptions.Item>
            <Descriptions.Item label="Departure">
              {flight.departure_time ? dayjs(flight.departure_time).format('DD MMM YYYY HH:mm') : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="Seats">
              <span style={{ fontWeight: 600 }}>{summary.seats_taken ?? 0}</span>
              <span style={{ color: '#94a3b8' }}> / {summary.capacity ?? '—'}</span>
              {summary.overbooked && <Tag color="red" style={{ marginLeft: 8 }}>Overbooked</Tag>}
              {!summary.overbooked && summary.seats_available != null && (
                <span style={{ color: '#16a34a', marginLeft: 8, fontSize: 12 }}>{summary.seats_available} free</span>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Weight & Balance">
              <Tooltip title={`Pax ${summary.body_weight_kg ?? 0} + baggage ${summary.baggage_weight_kg ?? 0} + cargo ${summary.cargo_weight_kg ?? 0} kg`}>
                <span style={{ fontWeight: 600, color: summary.over_payload ? '#dc2626' : '#7c3aed' }}>{summary.total_weight_kg ?? 0} kg</span>
              </Tooltip>
              {summary.max_payload_kg ? <span style={{ color: '#94a3b8' }}> / {summary.max_payload_kg} kg</span> : null}
              {summary.over_payload && <Tag color="red" style={{ marginLeft: 8 }}>Over limit</Tag>}
            </Descriptions.Item>
            {summary.actual_departure_time && (
              <Descriptions.Item label="Actual Departure">
                {dayjs(summary.actual_departure_time).format('DD MMM HH:mm')}
                {summary.departure_delay_min != null && summary.departure_delay_min !== 0 && (
                  <Tag color={summary.departure_delay_min > 0 ? 'red' : 'green'} style={{ marginLeft: 8 }}>
                    {summary.departure_delay_min > 0
                      ? `+${summary.departure_delay_min}m late`
                      : `${Math.abs(summary.departure_delay_min)}m early`}
                  </Tag>
                )}
              </Descriptions.Item>
            )}
          </Descriptions>

          {/* Badge / QR check-in at the helideck / gangway */}
          <Space.Compact style={{ marginBottom: 16, width: '100%', maxWidth: 380 }}>
            <Input
              value={badgeCode}
              onChange={(e) => setBadgeCode(e.target.value)}
              onPressEnter={() => badgeCode.trim() && checkinBadge.mutate(badgeCode.trim())}
              prefix={<QrcodeOutlined style={{ color: '#94a3b8' }} />}
              placeholder="Scan badge / enter emp code to check in"
              allowClear
            />
            <Button type="primary" icon={<CheckCircleOutlined />} loading={checkinBadge.isPending}
              onClick={() => badgeCode.trim() && checkinBadge.mutate(badgeCode.trim())}>
              Check in
            </Button>
          </Space.Compact>

          {/* Crew & cargo */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
            <Button size="small" icon={<TeamOutlined />}
              onClick={() => { crewForm.setFieldsValue({ crew: summary.crew || [] }); setShowCrew(true); }}>
              Crew ({summary.crew_count ?? 0})
            </Button>
            <Button size="small" icon={<InboxOutlined />}
              onClick={() => { cargoForm.setFieldsValue({ items: summary.cargo || [] }); setShowCargo(true); }}>
              Cargo ({summary.cargo_count ?? 0}{summary.cargo_weight_kg ? ` · ${summary.cargo_weight_kg}kg` : ''})
            </Button>
            {summary.has_dangerous_goods && (
              <Tag color="red" icon={<WarningOutlined />} style={{ margin: 0, alignSelf: 'center' }}>Dangerous goods</Tag>
            )}
            {summary.crew?.length > 0 && (
              <span style={{ alignSelf: 'center', fontSize: 12, color: '#64748b' }}>
                {summary.crew.map(c => `${c.name}${c.role ? ` (${c.role})` : ''}`).join(', ')}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
            <StatCard label="Arrivals Confirmed" value={confirmedInbound} color="#16a34a" icon={<ArrowDownOutlined />} />
            <StatCard label="Departures Confirmed" value={confirmedOutbound} color="#2563eb" icon={<ArrowUpOutlined />} />
            <StatCard label="Outstanding" value={outstanding} color={outstanding > 0 ? '#d97706' : '#94a3b8'} icon={<SyncOutlined />} />
            <StatCard label="No Shows" value={noShows} color={noShows > 0 ? '#dc2626' : '#94a3b8'} icon={<CloseCircleOutlined />} />
          </div>

          {outstanding > 0 && flight?.status === 'COMPLETED' && (
            <Alert
              type="warning"
              showIcon
              message={`${outstanding} passenger(s) not yet reconciled on a completed flight`}
              style={{ marginBottom: 16 }}
            />
          )}

          {inbound.length > 0 && (
            <>
              {sectionHeader('Inbound', inbound.length, '#16a34a')}
              <Table
                dataSource={inbound}
                columns={entryColumns}
                rowKey="id"
                pagination={false}
                size="small"
                loading={isLoading}
                rowClassName={(r) => r.status === 'NO_SHOW' ? 'row-entry-noshow' : r.status === 'CONFIRMED' ? 'row-entry-confirmed' : ''}
              />
            </>
          )}

          {outbound.length > 0 && (
            <>
              {sectionHeader('Outbound', outbound.length, '#2563eb')}
              <Table
                dataSource={outbound}
                columns={entryColumns}
                rowKey="id"
                pagination={false}
                size="small"
                loading={isLoading}
                rowClassName={(r) => r.status === 'NO_SHOW' ? 'row-entry-noshow' : r.status === 'CONFIRMED' ? 'row-entry-confirmed' : ''}
              />
            </>
          )}

          {entries.length === 0 && !isLoading && (
            <Alert type="info" showIcon message="No passengers on manifest yet. Click 'Add PAX' to start." />
          )}
        </>
      )}

      {/* Add passenger modal */}
      <Modal
        title="Add Passenger to Manifest"
        open={showAdd}
        onCancel={() => { setShowAdd(false); addForm.resetFields(); }}
        onOk={() => addForm.submit()}
        confirmLoading={addEntry.isPending}
      >
        <Form form={addForm} layout="vertical" onFinish={(v) => addEntry.mutate(v)}>
          <Form.Item name="passenger_name" label="Passenger Name" rules={[{ required: true }]}>
            <AutoComplete
              options={paxOptions}
              onSearch={(v) => searchPersonnel(v)}
              onSelect={(val, opt) => {
                addForm.setFieldsValue({ passenger_name: val, emp_code: opt.emp_code, company: opt.company });
              }}
              placeholder="Type name or emp code to search..."
            >
              <Input prefix={<SearchOutlined />} />
            </AutoComplete>
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
            <Form.Item name="direction" label="Direction" initialValue="INBOUND" rules={[{ required: true }]}>
              <Select options={[
                { value: 'INBOUND',  label: '↓ Inbound (arriving)' },
                { value: 'OUTBOUND', label: '↑ Outbound (departing)' },
              ]} />
            </Form.Item>
            <Form.Item name="emp_code" label="Emp Code">
              <Input placeholder="EMP001" />
            </Form.Item>
            <Form.Item name="company" label="Company">
              <Input />
            </Form.Item>
            <Form.Item name="id_number" label="Passport / ID No.">
              <Input />
            </Form.Item>
            <Form.Item name="body_weight" label="Body Weight (kg)">
              <InputNumber min={0} max={400} style={{ width: '100%' }} placeholder="e.g. 85" />
            </Form.Item>
            <Form.Item name="baggage_weight" label="Baggage (kg)">
              <InputNumber min={0} max={200} style={{ width: '100%' }} placeholder="e.g. 15" />
            </Form.Item>
          </div>
          <Form.Item name="remarks" label="Remarks" style={{ marginTop: 4 }}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* Crew modal */}
      <Modal title="Flight Crew" open={showCrew} onCancel={() => setShowCrew(false)}
        onOk={() => crewForm.submit()} confirmLoading={setCrew.isPending} width={560}>
        <Form form={crewForm} onFinish={(v) => setCrew.mutate((v.crew || []).filter(c => c && c.name))}>
          <Form.List name="crew">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...rest }) => (
                  <Space key={key} align="baseline" style={{ display: 'flex', marginBottom: 8 }}>
                    <Form.Item {...rest} name={[name, 'name']} rules={[{ required: true, message: 'Name' }]} style={{ marginBottom: 0 }}>
                      <Input placeholder="Name" style={{ width: 180 }} />
                    </Form.Item>
                    <Form.Item {...rest} name={[name, 'role']} initialValue="PILOT" style={{ marginBottom: 0 }}>
                      <Select style={{ width: 130 }} options={['CAPTAIN', 'PILOT', 'CO_PILOT', 'DRIVER', 'CREW'].map(r => ({ value: r, label: r }))} />
                    </Form.Item>
                    <Form.Item {...rest} name={[name, 'license_no']} style={{ marginBottom: 0 }}>
                      <Input placeholder="License no." style={{ width: 120 }} />
                    </Form.Item>
                    <DeleteOutlined onClick={() => remove(name)} style={{ color: '#dc2626' }} />
                  </Space>
                ))}
                <Button type="dashed" onClick={() => add({ role: 'PILOT' })} block icon={<PlusOutlined />}>
                  Add crew member
                </Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>

      {/* Cargo modal */}
      <Modal title="Cargo Manifest" open={showCargo} onCancel={() => setShowCargo(false)}
        onOk={() => cargoForm.submit()} confirmLoading={setCargo.isPending} width={660}>
        <Form form={cargoForm} onFinish={(v) => setCargo.mutate((v.items || []).filter(i => i && i.description))}>
          <Form.List name="items">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...rest }) => (
                  <Space key={key} align="baseline" style={{ display: 'flex', marginBottom: 8 }}>
                    <Form.Item {...rest} name={[name, 'description']} rules={[{ required: true, message: 'Description' }]} style={{ marginBottom: 0 }}>
                      <Input placeholder="Description" style={{ width: 190 }} />
                    </Form.Item>
                    <Form.Item {...rest} name={[name, 'weight_kg']} style={{ marginBottom: 0 }}>
                      <InputNumber placeholder="kg" min={0} style={{ width: 80 }} />
                    </Form.Item>
                    <Form.Item {...rest} name={[name, 'dangerous_goods']} valuePropName="checked" style={{ marginBottom: 0 }}>
                      <Checkbox>DG</Checkbox>
                    </Form.Item>
                    <Form.Item {...rest} name={[name, 'un_number']} style={{ marginBottom: 0 }}>
                      <Input placeholder="UN no." style={{ width: 90 }} />
                    </Form.Item>
                    <DeleteOutlined onClick={() => remove(name)} style={{ color: '#dc2626' }} />
                  </Space>
                ))}
                <Button type="dashed" onClick={() => add({ weight_kg: 0, dangerous_goods: false })} block icon={<PlusOutlined />}>
                  Add cargo item
                </Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>

      {/* Notify passengers modal */}
      <Modal title="Notify passengers" open={showNotify} onCancel={() => setShowNotify(false)}
        onOk={() => notifyForm.submit()} confirmLoading={notifyPax.isPending} okText="Send">
        <p style={{ color: '#64748b', fontSize: 13, marginTop: 0 }}>
          Sends to the passengers on this manifest who are registered staff, on their own
          WhatsApp / Telegram / email / phone (channels set up under Settings → WhatsApp &amp; Alerts).
          Guests have no contact on file. Every message is in the alert log.
        </p>
        <Form form={notifyForm} layout="vertical"
          initialValues={{ whatsapp: true, telegram: true, email: true, sms: false }}
          onFinish={(v) => notifyPax.mutate(v)}>
          <Form.Item name="subject" label="Subject (optional)">
            <Input placeholder="Auto: Transport <id>: route" />
          </Form.Item>
          <Form.Item name="message" label="Message (optional)">
            <Input.TextArea rows={3} placeholder="Auto: booking + departure details" />
          </Form.Item>
          <Space size="large">
            <Form.Item name="whatsapp" valuePropName="checked" noStyle><Checkbox>WhatsApp</Checkbox></Form.Item>
            <Form.Item name="telegram" valuePropName="checked" noStyle><Checkbox>Telegram</Checkbox></Form.Item>
            <Form.Item name="email" valuePropName="checked" noStyle><Checkbox>Email</Checkbox></Form.Item>
            <Form.Item name="sms" valuePropName="checked" noStyle><Checkbox>SMS</Checkbox></Form.Item>
          </Space>
        </Form>
      </Modal>

      {/* Reconcile result modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <SafetyCertificateOutlined style={{ color: reconcileResult?.reconciled ? '#16a34a' : '#dc2626' }} />
            <span>Muster Reconciliation</span>
            {reconcileResult && (reconcileResult.summary?.manifest_total ?? 0) > 0 && (
              <span style={{
                padding: '2px 8px', borderRadius: 999, fontSize: 12, fontWeight: 600,
                color: reconcileResult.reconciled ? '#16a34a' : '#dc2626',
                background: reconcileResult.reconciled ? '#f0fdf4' : '#fef2f2',
                border: `1px solid ${reconcileResult.reconciled ? '#bbf7d0' : '#fecaca'}`,
              }}>
                {reconcileResult.reconciled ? 'All Clear' : 'Discrepancies Found'}
              </span>
            )}
          </div>
        }
        open={!!reconcileResult}
        onCancel={() => setReconcileResult(null)}
        footer={<Button onClick={() => setReconcileResult(null)}>Close</Button>}
        width={560}
      >
        {reconcileResult && (
          <>
            <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
              {[
                { label: 'Manifest Total',    value: reconcileResult.summary?.manifest_total    ?? 0, color: '#64748b' },
                { label: 'Verified',          value: reconcileResult.summary?.verified          ?? 0, color: '#16a34a' },
                { label: reconcileResult.headcount_source === 'active_muster' ? 'Missing in Muster' : 'Not on board', value: reconcileResult.summary?.missing_in_muster ?? 0, color: '#dc2626' },
                { label: 'Extra on Platform', value: reconcileResult.summary?.extra_on_platform ?? 0, color: '#d97706' },
              ].map(s => (
                <div key={s.label} style={{ flex: 1, textAlign: 'center', padding: '10px 0', borderRadius: 8, background: `${s.color}0d`, border: `1px solid ${s.color}30` }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: s.color }}>{s.value}</div>
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>{s.label}</div>
                </div>
              ))}
            </div>

            <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 12 }}>
              Checked against: {reconcileResult.headcount_source === 'active_muster' ? 'the running muster (people counted safe)' : 'who is on board now (no muster running)'}
              &nbsp;·&nbsp;Generated {dayjs(reconcileResult.generated_at).format('HH:mm')}
            </div>

            {reconcileResult.missing_in_muster?.length > 0 && (
              <>
                <div style={{ fontWeight: 600, color: '#dc2626', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <WarningOutlined /> {reconcileResult.headcount_source === 'active_muster' ? 'Missing in Muster' : 'Booked to fly out but not on board'} ({reconcileResult.missing_in_muster.length})
                </div>
                <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 6, padding: '8px 12px', marginBottom: 12 }}>
                  {reconcileResult.missing_in_muster.map(p => (
                    <div key={p.emp_code} style={{ fontSize: 13, padding: '2px 0' }}>
                      <span style={{ fontWeight: 600 }}>{p.name}</span>
                      <span style={{ color: '#94a3b8', marginLeft: 8, fontSize: 12 }}>{p.emp_code}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {reconcileResult.extra_on_platform?.length > 0 && (
              <>
                <div style={{ fontWeight: 600, color: '#d97706', marginBottom: 6 }}>
                  Extra on Platform ({reconcileResult.extra_on_platform.length})
                </div>
                <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6, padding: '8px 12px', marginBottom: 12 }}>
                  {reconcileResult.extra_on_platform.map(p => (
                    <div key={p.emp_code} style={{ fontSize: 13, padding: '2px 0' }}>
                      <span style={{ fontWeight: 600 }}>{p.name}</span>
                      <span style={{ color: '#94a3b8', marginLeft: 8, fontSize: 12 }}>{p.emp_code}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {reconcileResult.reconciled && (reconcileResult.summary?.manifest_total ?? 0) > 0 && (
              <Alert type="success" showIcon message={reconcileResult.headcount_source === 'active_muster'
                ? 'All outbound passengers are accounted for in the muster. Safe to proceed.'
                : 'All outbound passengers are on board. Safe to proceed.'} />
            )}
            {(reconcileResult.summary?.manifest_total ?? 0) === 0 && (
              <Alert type="info" showIcon message="No outbound staff on this manifest — nothing to reconcile (inbound passengers are not on site yet)." />
            )}
          </>
        )}
      </Modal>
      <Modal
        title={`Passenger details — ${paxEdit?.passenger_name || ''}`}
        open={!!paxEdit}
        onCancel={() => setPaxEdit(null)}
        onOk={() => paxForm.validateFields().then(v => savePax.mutate(v)).catch(() => {})}
        confirmLoading={savePax.isPending}
        okText="Save"
      >
        <Form form={paxForm} layout="vertical">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
            <Form.Item name="body_weight" label="Body Weight (kg)" rules={[{ type: 'number', min: 0, max: 400 }]}>
              <InputNumber min={0} max={400} style={{ width: '100%' }} autoFocus />
            </Form.Item>
            <Form.Item name="baggage_weight" label="Baggage (kg)" rules={[{ type: 'number', min: 0, max: 200 }]}>
              <InputNumber min={0} max={200} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="direction" label="Direction">
              <Select disabled={paxEdit?.status === 'CONFIRMED'} options={[
                { value: 'INBOUND', label: '↓ Inbound (arriving)' }, { value: 'OUTBOUND', label: '↑ Outbound (departing)' }]} />
            </Form.Item>
            <Form.Item name="company" label="Company"><Input /></Form.Item>
            <Form.Item name="id_number" label="Passport / ID No."><Input /></Form.Item>
            <Form.Item name="remarks" label="Remarks"><Input /></Form.Item>
          </div>
        </Form>
      </Modal>
      <Modal
        title="Reschedule / edit flight"
        open={showEdit}
        onCancel={() => setShowEdit(false)}
        onOk={() => editForm.validateFields().then(v => editFlight.mutate(v)).catch(() => {})}
        confirmLoading={editFlight.isPending}
        okText="Save"
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="departure_location" label="From" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="arrival_location" label="To" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="departure_time" label="Departure" rules={[{ required: true }]}>
            <DatePicker showTime format={DT_FORMATS} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="arrival_time" label="Arrival (optional)" dependencies={['departure_time']}
            rules={[({ getFieldValue }) => ({
              validator: (_, v) => (!v || !getFieldValue('departure_time') || v.isAfter(getFieldValue('departure_time'))
                ? Promise.resolve() : Promise.reject(new Error('Arrival must be after departure'))),
            })]}>
            <DatePicker showTime format={DT_FORMATS} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="notify" valuePropName="checked">
            <Checkbox>Tell passengers if the departure time changes (email / SMS when configured)</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </Drawer>
  );
}

// ─── POB Summary tab ──────────────────────────────────────────────────────────

function POBSummary() {
  const [summaryDate, setSummaryDate] = useState(dayjs());

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['pob-summary', summaryDate.format('YYYY-MM-DD')],
    queryFn: () => apiService.get('/api/v1/transport/pob-summary', {
      summary_date: summaryDate.format('YYYY-MM-DD'),
    }),
    refetchInterval: 60_000,
  });

  const discrepancies = data?.discrepancies ?? [];
  const pobDelta = data?.pob_delta ?? 0;

  return (
    <>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 14 }}>
        <DatePicker
          value={summaryDate}
          onChange={(v) => v && setSummaryDate(v)}
          format="DD MMM YYYY"
          size="small"
          allowClear={false}
        />
        <Button icon={<ReloadOutlined />} size="small" onClick={() => refetch()} />
        <span style={{ fontSize: 12, color: '#94a3b8' }}>
          {data?.flights_today ?? 0} flight(s) on this day
        </span>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <StatCard
          label="Confirmed Arrivals"
          value={isLoading ? '—' : data?.confirmed_arrivals ?? 0}
          color="#16a34a"
          icon={<ArrowDownOutlined />}
        />
        <StatCard
          label="Confirmed Departures"
          value={isLoading ? '—' : data?.confirmed_departures ?? 0}
          color="#2563eb"
          icon={<ArrowUpOutlined />}
        />
        <StatCard
          label="Net POB Change"
          value={isLoading ? '—' : pobDelta > 0 ? `+${pobDelta}` : pobDelta}
          color={pobDelta > 0 ? '#16a34a' : pobDelta < 0 ? '#dc2626' : '#94a3b8'}
          icon={pobDelta >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
        />
        <StatCard
          label="No Shows"
          value={isLoading ? '—' : data?.no_shows ?? 0}
          color={(data?.no_shows ?? 0) > 0 ? '#dc2626' : '#94a3b8'}
          icon={<ExclamationCircleOutlined />}
        />
      </div>

      {discrepancies.length > 0 ? (
        <>
          <Alert
            type="warning"
            showIcon
            message={`${discrepancies.length} unreconciled passenger(s) on completed flights`}
            style={{ marginBottom: 12 }}
          />
          <div style={{ background: '#fff', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', overflow: 'hidden' }}>
            <Table
              dataSource={discrepancies}
              rowKey={(r, i) => `${r.flight_id}-${i}`}
              size="small"
              pagination={false}
              columns={[
                { title: 'Passenger', dataIndex: 'passenger_name', render: v => <span style={{ fontWeight: 600 }}>{v}</span> },
                { title: 'Emp Code', dataIndex: 'emp_code', render: v => v || '—' },
                {
                  title: 'Direction', dataIndex: 'direction',
                  render: v => <StatusPill status={v} cfg={DIRECTION_CFG} />,
                },
                { title: 'Flight', dataIndex: 'flight_ref', render: (v, r) => v || `#${r.flight_id}` },
              ]}
            />
          </div>
        </>
      ) : !isLoading && (
        <Alert type="success" showIcon message="No unreconciled passengers. All completed flights are fully reconciled." />
      )}
    </>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function TransportManifest() {
  const [selectedFlight, setSelectedFlight] = useState(null);

  return (
    <div className="transport-module">
      <Card
        title={
          <div>
            <div style={{ fontWeight: 700, fontSize: 16 }}>Journey Management &amp; Reconciliation</div>
            <div style={{ fontSize: 12, color: '#64748b', fontWeight: 400, marginTop: 2 }}>
              Helideck / gangway check-in — maintain accurate POB count
            </div>
          </div>
        }
      >
        <Tabs
          defaultActiveKey="flights"
          size="middle"
          type="card"
          items={[
            {
              key: 'flights',
              label: <Space size={5}><AuditOutlined />Flights</Space>,
              children: <FlightList onSelectFlight={setSelectedFlight} />,
            },
            {
              key: 'journeys',
              label: <Space size={5}><CarOutlined />Land Journeys</Space>,
              children: <LandJourneys />,
            },
            {
              key: 'pob',
              label: <Space size={5}><ExclamationCircleOutlined />POB Impact</Space>,
              children: <POBSummary />,
            },
          ]}
        />

        <ManifestDrawer
          flight={selectedFlight}
          onClose={() => setSelectedFlight(null)}
        />

        <style>{`
          .row-flight-cancelled > td { background: rgba(220,38,38,0.03) !important; }
          .row-flight-transit > td   { background: rgba(217,119,6,0.03) !important; }
          .row-flight-completed > td { background: rgba(22,163,74,0.03) !important; }
          .row-entry-noshow > td     { background: rgba(220,38,38,0.04) !important; }
          .row-entry-confirmed > td  { background: rgba(22,163,74,0.03) !important; }
        `}</style>
      </Card>
    </div>
  );
}
