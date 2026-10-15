/**
 * Land Journey Management (JMP) — road-transport journey plans with risk
 * assessment, an approval workflow, and check-in-call tracking with overdue
 * escalation. Backed by /api/v1/journeys.
 */

import React, { useState } from 'react';
import {
  Table, Button, Tag, Space, Modal, Form, Input, InputNumber, Select, DatePicker,
  Drawer, Descriptions, Alert, App, Timeline, Empty, Tooltip, Checkbox,
} from 'antd';
import {
  PlusOutlined, CarOutlined, WarningOutlined, CheckCircleOutlined, CloseCircleOutlined,
  SendOutlined, PlayCircleOutlined, FlagOutlined, EnvironmentOutlined, PhoneOutlined,
  ReloadOutlined, StopOutlined, ClockCircleOutlined, EditOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService from '../../services/api';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
dayjs.extend(relativeTime);

const RISK = {
  LOW:    { color: 'green',  label: 'Low' },
  MEDIUM: { color: 'orange', label: 'Medium' },
  HIGH:   { color: 'red',    label: 'High' },
};
const STATUS = {
  DRAFT:       { color: 'default',    label: 'Draft' },
  SUBMITTED:   { color: 'blue',       label: 'Pending approval' },
  APPROVED:    { color: 'cyan',       label: 'Approved' },
  REJECTED:    { color: 'red',        label: 'Rejected' },
  IN_PROGRESS: { color: 'purple',     label: 'In progress' },
  COMPLETED:   { color: 'green',      label: 'Completed' },
  CANCELLED:   { color: 'default',    label: 'Cancelled' },
};

// Pre-trip vehicle inspection — every item must pass before a journey can start.
const VEHICLE_CHECKS = [
  ['tyres', 'Tyres & spare'], ['brakes', 'Brakes'], ['lights', 'Lights & indicators'],
  ['fluids', 'Fuel, oil & coolant'], ['seatbelts', 'Seat belts'], ['first_aid', 'First-aid kit'],
  ['extinguisher', 'Fire extinguisher'], ['documents', 'Vehicle documents'], ['comms', 'Phone / radio charged'],
];

const StatTile = ({ label, value, color }) => (
  <div style={{ flex: 1, background: '#fff', border: '1px solid #f0f0f0', borderTop: `3px solid ${color}`,
    borderRadius: 8, padding: '12px 16px' }}>
    <div style={{ fontSize: 12, color: '#64748b' }}>{label}</div>
    <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
  </div>
);

export default function LandJourneys() {
  const { message, modal } = App.useApp();
  const qc = useQueryClient();
  const [createForm] = Form.useForm();
  const [checkinForm] = Form.useForm();
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState(null);  // null = new plan
  const [selected, setSelected] = useState(null);   // journey id for drawer
  const [paxOptions, setPaxOptions] = useState([]);  // staff search results
  const [paxStaff, setPaxStaff] = useState({});      // emp_code -> {name, emp_code}

  const searchPax = async (q) => {
    if (!q || q.length < 2) return;
    try {
      const res = await apiService.get('/api/v1/transport/personnel-search', { q });
      const list = Array.isArray(res) ? res : [];
      setPaxStaff(prev => ({ ...prev, ...Object.fromEntries(list.map(p => [p.emp_code, { name: p.name, emp_code: p.emp_code }])) }));
      setPaxOptions(list.map(p => ({ value: p.emp_code, label: `${p.name} (${p.emp_code})` })));
    } catch (_) { /* search is best-effort */ }
  };

  const { data: statsData } = useQuery({
    queryKey: ['journey-stats'],
    queryFn: () => apiService.get('/api/v1/journeys/stats'),
    refetchInterval: 30_000,
  });
  const stats = statsData || {};

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['journeys'],
    queryFn: () => apiService.get('/api/v1/journeys'),
    refetchInterval: 30_000,
  });
  const journeys = data?.journeys ?? [];

  const { data: detail } = useQuery({
    queryKey: ['journey', selected],
    queryFn: () => apiService.get(`/api/v1/journeys/${selected}`),
    enabled: !!selected,
    refetchInterval: selected ? 20_000 : false,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['journeys'] });
    qc.invalidateQueries({ queryKey: ['journey-stats'] });
    if (selected) qc.invalidateQueries({ queryKey: ['journey', selected] });
  };
  // Plain (non-hook) option factory so useMutation stays at the top level.
  const opts = (ok) => ({
    onSuccess: () => { if (ok) message.success(ok); invalidate(); },
    onError: (e) => message.error(e?.response?.data?.detail || e.message || 'Action failed'),
  });

  const toBody = (v) => {
    const { vehicle_checks, passenger_codes, ...rest } = v;
    const done = new Set(vehicle_checks || []);
    return {
      ...rest,
      planned_departure: v.planned_departure.toISOString(),
      planned_arrival: v.planned_arrival ? v.planned_arrival.toISOString() : null,
      // Staff picked from search keep their code (links them to personnel); anything
      // typed in is a guest name.
      passengers: (passenger_codes || []).map(c => paxStaff[c] || { name: c }),
      vehicle_check: Object.fromEntries(VEHICLE_CHECKS.map(([k]) => [k, done.has(k)])),
    };
  };
  const createM = useMutation({
    mutationFn: (v) => editingId
      ? apiService.put(`/api/v1/journeys/${editingId}`, toBody(v))
      : apiService.post('/api/v1/journeys', toBody(v)),
    onSuccess: () => {
      message.success(editingId ? 'Journey updated' : 'Journey created');
      setShowCreate(false); setEditingId(null); createForm.resetFields(); invalidate();
    },
    onError: (e) => message.error(e?.response?.data?.detail || e.message || 'Failed to save journey'),
  });

  const openEdit = (jj) => {
    setEditingId(jj.id);
    const staff = Object.fromEntries((jj.passengers || []).filter(p => p.emp_code).map(p => [p.emp_code, p]));
    setPaxStaff(prev => ({ ...prev, ...staff }));
    setPaxOptions((jj.passengers || []).filter(p => p.emp_code).map(p => ({ value: p.emp_code, label: `${p.name} (${p.emp_code})` })));
    createForm.setFieldsValue({
      origin: jj.origin, destination: jj.destination, distance_km: jj.distance_km, purpose: jj.purpose,
      driver_name: jj.driver_name, driver_license: jj.driver_license,
      vehicle_reg: jj.vehicle_reg, vehicle_type: jj.vehicle_type,
      planned_departure: jj.planned_departure ? dayjs(jj.planned_departure) : null,
      planned_arrival: jj.planned_arrival ? dayjs(jj.planned_arrival) : null,
      checkin_interval_min: jj.checkin_interval_min,
      risk_factors: jj.risk_manual_factors || [],
      notes: jj.notes,
      passenger_codes: (jj.passengers || []).map(p => p.emp_code || p.name),
      vehicle_checks: Object.entries(jj.vehicle_check || {}).filter(([, ok]) => ok).map(([k]) => k),
    });
    setShowCreate(true);
  };
  const vcheckM   = useMutation({
    mutationFn: ({ id, checks }) => apiService.post(`/api/v1/journeys/${id}/vehicle-check`, {
      vehicle_check: Object.fromEntries(VEHICLE_CHECKS.map(([k]) => [k, checks.includes(k)])),
    }),
    ...opts('Vehicle check recorded'),
  });
  const recordVehicleCheck = (jj) => {
    let checks = Object.entries(jj.vehicle_check || {}).filter(([, ok]) => ok).map(([k]) => k);
    modal.confirm({
      title: 'Pre-trip vehicle check', okText: 'Save', icon: <CarOutlined />, width: 520,
      content: (
        <Checkbox.Group defaultValue={checks} onChange={(v) => { checks = v; }}
          options={VEHICLE_CHECKS.map(([value, label]) => ({ value, label }))}
          style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', rowGap: 6, marginTop: 8 }} />
      ),
      onOk: () => vcheckM.mutate({ id: jj.id, checks }),
    });
  };
  const submitM   = useMutation({ mutationFn: (id) => apiService.post(`/api/v1/journeys/${id}/submit`), ...opts('Submitted for approval') });
  const approveM  = useMutation({ mutationFn: (id) => apiService.post(`/api/v1/journeys/${id}/approve`), ...opts('Journey approved') });
  const startM    = useMutation({ mutationFn: (id) => apiService.post(`/api/v1/journeys/${id}/start`), ...opts('Journey started') });
  const completeM = useMutation({ mutationFn: (id) => apiService.post(`/api/v1/journeys/${id}/complete`), ...opts('Journey completed') });
  const cancelM   = useMutation({ mutationFn: (id) => apiService.post(`/api/v1/journeys/${id}/cancel`), ...opts('Journey cancelled') });
  const rejectM   = useMutation({ mutationFn: ({ id, reason }) => apiService.post(`/api/v1/journeys/${id}/reject`, { reason }), ...opts('Journey rejected') });
  const checkinM  = useMutation({
    mutationFn: ({ id, body }) => apiService.post(`/api/v1/journeys/${id}/checkin`, body),
    onSuccess: () => { message.success('Check-in logged'); checkinForm.resetFields(); invalidate(); },
    onError: (e) => message.error(e.message || 'Check-in failed'),
  });

  const doCreate = () => createForm.validateFields().then((v) => createM.mutate(v));

  const reject = (id) => {
    let reason = '';
    modal.confirm({
      title: 'Reject journey', okType: 'danger', okText: 'Reject',
      content: <Input.TextArea rows={3} placeholder="Reason (optional)" onChange={(e) => { reason = e.target.value; }} />,
      onOk: () => rejectM.mutate({ id, reason }),
    });
  };

  const cols = [
    { title: 'Ref', dataIndex: 'reference', width: 92, render: (r) => <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{r}</span> },
    { title: 'Route', render: (_, r) => (
      <div>
        <div style={{ fontWeight: 600 }}>{r.origin} → {r.destination}</div>
        <div style={{ fontSize: 11, color: '#64748b' }}>
          {r.driver_name || 'No driver'}{r.vehicle_reg ? ` · ${r.vehicle_reg}` : ''}{r.distance_km ? ` · ${r.distance_km} km` : ''}
        </div>
      </div>
    ) },
    { title: 'Departs', dataIndex: 'planned_departure', width: 140,
      render: (v) => v ? <Tooltip title={dayjs(v).format('DD MMM YYYY HH:mm')}><span style={{ fontSize: 12 }}>{dayjs(v).format('DD MMM HH:mm')}</span></Tooltip> : '—' },
    { title: 'Risk', dataIndex: 'risk_level', width: 80, render: (r) => <Tag color={RISK[r]?.color}>{RISK[r]?.label || r}</Tag> },
    { title: 'Status', width: 150, render: (_, r) => (
      r.overdue
        ? <Tag color="red" icon={<WarningOutlined />}>Overdue {r.minutes_overdue}m</Tag>
        : <Tag color={STATUS[r.status]?.color}>{STATUS[r.status]?.label || r.status}</Tag>
    ) },
    { title: '', width: 90, render: (_, r) => <Button size="small" onClick={() => setSelected(r.id)}>Open</Button> },
  ];

  const j = detail;   // selected journey detail

  return (
    <div>
      {stats.overdue > 0 && (
        <Alert type="error" showIcon icon={<WarningOutlined />} style={{ marginBottom: 14 }}
          message={`${stats.overdue} journey(s) OVERDUE — a check-in call is late. Escalate to the driver / control room.`} />
      )}

      <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
        <StatTile label="Pending approval" value={stats.pending_approval ?? 0} color="#2563eb" />
        <StatTile label="Approved" value={stats.approved ?? 0} color="#0891b2" />
        <StatTile label="In progress" value={stats.in_progress ?? 0} color="#7c3aed" />
        <StatTile label="Overdue" value={stats.overdue ?? 0} color={stats.overdue > 0 ? '#dc2626' : '#94a3b8'} />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <Space><CarOutlined /><span style={{ fontWeight: 600 }}>Journey plans</span></Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading} size="small">Refresh</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingId(null); createForm.resetFields(); setShowCreate(true); }}>New Journey Plan</Button>
        </Space>
      </div>

      <Table
        rowKey="id" columns={cols} dataSource={journeys} loading={isLoading} size="small"
        pagination={{ pageSize: 12, hideOnSinglePage: true }}
        rowClassName={(r) => r.overdue ? 'row-journey-overdue' : ''}
        locale={{ emptyText: <Empty description="No journey plans yet" /> }}
      />

      {/* Create modal */}
      <Modal title={editingId ? 'Edit Journey Plan' : 'New Journey Plan'} open={showCreate}
        onCancel={() => { setShowCreate(false); setEditingId(null); }}
        onOk={doCreate} confirmLoading={createM.isPending} width={680}>
        <Form form={createForm} layout="vertical">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
            <Form.Item name="origin" label="Origin" rules={[{ required: true }]}><Input placeholder="Port Harcourt" /></Form.Item>
            <Form.Item name="destination" label="Destination" rules={[{ required: true }]}><Input placeholder="Warri" /></Form.Item>
            <Form.Item name="distance_km" label="Distance (km)"><InputNumber min={0} style={{ width: '100%' }} placeholder="Auto-scores risk" /></Form.Item>
            <Form.Item name="purpose" label="Purpose"><Input placeholder="Crew change" /></Form.Item>
            <Form.Item name="driver_name" label="Driver"><Input /></Form.Item>
            <Form.Item name="driver_license" label="Driver license"><Input /></Form.Item>
            <Form.Item name="vehicle_reg" label="Vehicle reg."><Input placeholder="ABC-123-XY" /></Form.Item>
            <Form.Item name="vehicle_type" label="Vehicle type"><Input placeholder="Toyota Hilux" /></Form.Item>
            <Form.Item name="planned_departure" label="Planned departure" rules={[{ required: true }]}>
              <DatePicker showTime style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="planned_arrival" label="Planned arrival (ETA)">
              <DatePicker showTime style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="checkin_interval_min" label="Check-in every (min)" initialValue={60}>
              <InputNumber min={15} max={240} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="risk_factors" label="Extra risk factors">
              <Select mode="tags" placeholder="e.g. poor road, security" style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <Form.Item name="passenger_codes" label="Passengers"
            tooltip="Search staff by name or code; type a name and press Enter for a guest">
            <Select mode="tags" showSearch filterOption={false} onSearch={searchPax}
              options={paxOptions} placeholder="Search staff…" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="vehicle_checks" label="Pre-trip vehicle check (all must pass before the journey can start)">
            <Checkbox.Group options={VEHICLE_CHECKS.map(([value, label]) => ({ value, label }))}
              style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', rowGap: 4 }} />
          </Form.Item>
          <Form.Item name="notes" label="Notes"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      {/* Detail drawer */}
      <Drawer open={!!selected} onClose={() => setSelected(null)} width={620}
        title={j ? <Space><CarOutlined />{j.reference} — {j.origin} → {j.destination}
          <Tag color={STATUS[j.status]?.color}>{STATUS[j.status]?.label}</Tag></Space> : 'Journey'}>
        {j && (
          <>
            {j.overdue && (
              <Alert type="error" showIcon style={{ marginBottom: 14 }}
                message={`OVERDUE by ${j.minutes_overdue} min — last check-in ${j.last_checkin_at ? dayjs(j.last_checkin_at).fromNow() : 'n/a'}. Contact the driver.`} />
            )}
            {j.status === 'REJECTED' && j.rejection_reason && (
              <Alert type="warning" showIcon style={{ marginBottom: 14 }} message={`Rejected: ${j.rejection_reason}`} />
            )}

            <Descriptions size="small" column={2} bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label="Risk"><Tag color={RISK[j.risk_level]?.color}>{RISK[j.risk_level]?.label}</Tag>
                {(j.risk_factors || []).length > 0 && <span style={{ fontSize: 11, color: '#64748b' }}> {j.risk_factors.join(', ')}</span>}</Descriptions.Item>
              <Descriptions.Item label="Distance">{j.distance_km ? `${j.distance_km} km` : '—'}</Descriptions.Item>
              <Descriptions.Item label="Driver">{j.driver_name || '—'}{j.driver_license ? ` (${j.driver_license})` : ''}</Descriptions.Item>
              <Descriptions.Item label="Vehicle">{j.vehicle_reg || '—'}{j.vehicle_type ? ` · ${j.vehicle_type}` : ''}</Descriptions.Item>
              <Descriptions.Item label="Planned dep.">{j.planned_departure ? dayjs(j.planned_departure).format('DD MMM HH:mm') : '—'}</Descriptions.Item>
              <Descriptions.Item label="ETA">{j.planned_arrival ? dayjs(j.planned_arrival).format('DD MMM HH:mm') : '—'}</Descriptions.Item>
              <Descriptions.Item label="Check-in every">{j.checkin_interval_min} min</Descriptions.Item>
              <Descriptions.Item label="Next check-in">{j.next_checkin_due ? dayjs(j.next_checkin_due).format('DD MMM HH:mm') : '—'}</Descriptions.Item>
              <Descriptions.Item label="Passengers" span={2}>
                {(j.passengers || []).length ? j.passengers.map(p => p.emp_code ? `${p.name} (${p.emp_code})` : `${p.name} (guest)`).join(', ') : `${j.passenger_count || 0}`}</Descriptions.Item>
              <Descriptions.Item label="Vehicle check">
                {j.vehicle_check_ok ? <Tag color="green">Passed</Tag> : <Tag color="red">Not complete</Tag>}</Descriptions.Item>
              <Descriptions.Item label="Approvals">
                {j.approvals_given || 0} / {j.approvals_required || 1}{j.approvals_required === 2 ? ' (HIGH risk: two approvers)' : ''}</Descriptions.Item>
            </Descriptions>

            {/* Workflow actions */}
            <Space wrap style={{ marginBottom: 18 }}>
              {['DRAFT', 'REJECTED', 'SUBMITTED'].includes(j.status) &&
                <Button icon={<EditOutlined />} onClick={() => openEdit(j)}>Edit</Button>}
              {j.status === 'DRAFT' && <Button type="primary" icon={<SendOutlined />} loading={submitM.isPending} onClick={() => submitM.mutate(j.id)}>Submit for approval</Button>}
              {j.status === 'REJECTED' && <Button type="primary" icon={<SendOutlined />} onClick={() => submitM.mutate(j.id)}>Re-submit</Button>}
              {j.status === 'SUBMITTED' && <>
                <Button type="primary" icon={<CheckCircleOutlined />} loading={approveM.isPending} onClick={() => approveM.mutate(j.id)}>
                  {j.approvals_required === 2 && j.approvals_given === 1 ? 'Second approval' : 'Approve'}</Button>
                <Button danger icon={<CloseCircleOutlined />} onClick={() => reject(j.id)}>Reject</Button>
              </>}
              {['DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED'].includes(j.status) &&
                <Button icon={<CarOutlined />} onClick={() => recordVehicleCheck(j)}>Vehicle check</Button>}
              {j.status === 'APPROVED' && (
                <Tooltip title={j.vehicle_check_ok ? '' : 'Record a passed pre-trip vehicle check first'}>
                  <Button type="primary" icon={<PlayCircleOutlined />} loading={startM.isPending}
                    disabled={!j.vehicle_check_ok} onClick={() => startM.mutate(j.id)}>Start journey</Button>
                </Tooltip>
              )}
              {j.status === 'IN_PROGRESS' && <Button type="primary" icon={<FlagOutlined />} loading={completeM.isPending} onClick={() => completeM.mutate(j.id)}>Complete</Button>}
              {!['COMPLETED', 'CANCELLED'].includes(j.status) &&
                <Button icon={<StopOutlined />} onClick={() => modal.confirm({ title: 'Cancel this journey?', okType: 'danger', onOk: () => cancelM.mutate(j.id) })}>Cancel</Button>}
            </Space>

            {/* Check-in call form (in-progress only) */}
            {j.status === 'IN_PROGRESS' && (
              <div style={{ background: '#f8fafc', border: '1px solid #f0f0f0', borderRadius: 8, padding: 14, marginBottom: 18 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}><PhoneOutlined /> Log a check-in call</div>
                <Form form={checkinForm} layout="inline" onFinish={(v) => checkinM.mutate({ id: j.id, body: v })}>
                  <Form.Item name="location"><Input prefix={<EnvironmentOutlined />} placeholder="Location / km marker" /></Form.Item>
                  <Form.Item name="status" initialValue="OK">
                    <Select style={{ width: 120 }} options={[{ value: 'OK', label: 'All OK' }, { value: 'CONCERN', label: 'Concern' }]} />
                  </Form.Item>
                  <Form.Item name="notes"><Input placeholder="Notes" /></Form.Item>
                  <Button type="primary" htmlType="submit" loading={checkinM.isPending} icon={<CheckCircleOutlined />}>Log</Button>
                </Form>
              </div>
            )}

            {/* Check-in log */}
            <div style={{ fontWeight: 600, marginBottom: 10 }}><ClockCircleOutlined /> Check-in log</div>
            {(j.checkins || []).length === 0
              ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No check-ins yet" />
              : <Timeline items={(j.checkins || []).map(c => ({
                  color: c.status === 'CONCERN' ? 'red' : 'green',
                  children: (
                    <div>
                      <span style={{ fontWeight: 600 }}>{dayjs(c.checkin_time).format('DD MMM HH:mm')}</span>
                      {c.location ? <span style={{ color: '#64748b' }}> · {c.location}</span> : ''}
                      {c.status === 'CONCERN' && <Tag color="red" style={{ marginLeft: 8 }}>Concern</Tag>}
                      {c.notes && <div style={{ fontSize: 12, color: '#64748b' }}>{c.notes}</div>}
                      {c.reported_by && <div style={{ fontSize: 11, color: '#94a3b8' }}>by {c.reported_by}</div>}
                    </div>
                  ),
                }))} />}
          </>
        )}
      </Drawer>

      <style>{`.row-journey-overdue > td { background: rgba(220,38,38,0.05) !important; }`}</style>
    </div>
  );
}
