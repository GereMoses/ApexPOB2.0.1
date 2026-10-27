import React, { useState, useEffect, useRef } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, Select, Tag, Popconfirm,
  Row, Col, Card, Badge, App, Tabs, Switch, Alert, DatePicker,
  Descriptions, Empty, Spin, Divider, Timeline, Progress, Tooltip,
} from 'antd';
import {
  AlertOutlined, LockOutlined, UnlockOutlined, FireOutlined,
  BellOutlined, ApiOutlined, ThunderboltOutlined, FileTextOutlined,
  AuditOutlined, ReloadOutlined, ExclamationCircleOutlined,
  WarningOutlined, CheckCircleOutlined, UserOutlined, DownloadOutlined,
  CloseCircleOutlined, TeamOutlined, PlusOutlined, DeleteOutlined,
  EyeOutlined, GlobalOutlined, SafetyOutlined, ClockCircleOutlined,
  EnvironmentOutlined, SoundOutlined, ControlOutlined, InfoCircleOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService from '../../services/api';

const { Option } = Select;
const { TextArea } = Input;
const { RangePicker } = DatePicker;

/* ─── constants ─────────────────────────────────────────────── */
const EVENT_TYPE_MAP = {
  0: { label: 'LOCKDOWN', color: '#cf1322', bg: 'rgba(207,19,34,0.08)',  border: 'rgba(207,19,34,0.25)', icon: <LockOutlined /> },
  1: { label: 'FIRE',     color: '#d4380d', bg: 'rgba(212,56,13,0.08)',  border: 'rgba(212,56,13,0.25)', icon: <FireOutlined /> },
  2: { label: 'GAS',      color: '#d48806', bg: 'rgba(212,136,6,0.08)',  border: 'rgba(212,136,6,0.25)', icon: <WarningOutlined /> },
  3: { label: 'INTRUDER', color: '#531dab', bg: 'rgba(83,29,171,0.08)',  border: 'rgba(83,29,171,0.25)', icon: <ExclamationCircleOutlined /> },
  4: { label: 'MEDICAL',  color: '#096dd9', bg: 'rgba(9,109,217,0.08)',  border: 'rgba(9,109,217,0.25)', icon: <SafetyOutlined /> },
  5: { label: 'ALL CLEAR',color: '#389e0d', bg: 'rgba(56,158,13,0.08)',  border: 'rgba(56,158,13,0.25)', icon: <CheckCircleOutlined /> },
};

const STATUS_CFG = {
  ACTIVE:    { color: '#cf1322', bg: 'rgba(207,19,34,0.08)',  border: 'rgba(207,19,34,0.3)',  dot: '#f5222d' },
  RESOLVED:  { color: '#389e0d', bg: 'rgba(56,158,13,0.08)',  border: 'rgba(56,158,13,0.3)',  dot: '#52c41a' },
  CANCELLED: { color: '#595959', bg: 'rgba(89,89,89,0.06)',   border: 'rgba(89,89,89,0.2)',   dot: '#8c8c8c' },
};

const DEVICE_CFG = {
  1: { label: 'Siren',        icon: <SoundOutlined />,       from: '#cf1322', to: '#820014' },
  2: { label: 'Strobe',       icon: <ThunderboltOutlined />, from: '#d48806', to: '#874d00' },
  3: { label: 'Lock',         icon: <LockOutlined />,        from: '#096dd9', to: '#003a8c' },
  4: { label: 'Speaker',      icon: <SoundOutlined />,       from: '#531dab', to: '#22075e' },
  5: { label: 'Panic Button', icon: <AlertOutlined />,       from: '#c41d7f', to: '#780650' },
};

const CHANNEL_CFG = {
  sms:      { label: 'SMS',      color: '#1890ff', bg: '#e6f7ff', border: '#91d5ff' },
  email:    { label: 'Email',    color: '#52c41a', bg: '#f6ffed', border: '#b7eb8f' },
  whatsapp: { label: 'WhatsApp', color: '#25d366', bg: '#f0fff4', border: '#95de64' },
  push:     { label: 'Push',     color: '#722ed1', bg: '#f9f0ff', border: '#d3adf7' },
  pa:       { label: 'PA System',color: '#fa8c16', bg: '#fff7e6', border: '#ffd591' },
};

/* ─── shared primitives ──────────────────────────────────────── */
const GradStat = ({ label, value, icon, from, to, sub }) => (
  <div style={{
    borderRadius: 16, padding: '18px 20px',
    background: `linear-gradient(135deg, ${from} 0%, ${to} 100%)`,
    boxShadow: `0 6px 24px ${from}40`,
    position: 'relative', overflow: 'hidden',
  }}>
    <div style={{
      position: 'absolute', right: -8, top: -8, width: 80, height: 80,
      borderRadius: '50%', background: 'rgba(255,255,255,0.08)',
    }} />
    <div style={{
      position: 'absolute', right: 12, bottom: -16, width: 56, height: 56,
      borderRadius: '50%', background: 'rgba(255,255,255,0.05)',
    }} />
    <div style={{ color: 'rgba(255,255,255,0.65)', fontSize: 12, fontWeight: 500, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
      {label}
    </div>
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
      <div style={{ color: 'white', fontSize: 32, fontWeight: 800, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12, paddingBottom: 4 }}>{sub}</div>}
    </div>
    {icon && (
      <div style={{
        position: 'absolute', right: 18, top: '50%', transform: 'translateY(-50%)',
        fontSize: 28, color: 'rgba(255,255,255,0.2)',
      }}>
        {icon}
      </div>
    )}
  </div>
);

const EventBadge = ({ type }) => {
  const t = EVENT_TYPE_MAP[type] ?? { label: 'UNKNOWN', color: '#595959', bg: 'rgba(0,0,0,0.04)', border: 'rgba(0,0,0,0.12)', icon: <InfoCircleOutlined /> };
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: t.bg, border: `1px solid ${t.border}`,
      borderRadius: 20, padding: '3px 12px',
      color: t.color, fontWeight: 700, fontSize: 11, letterSpacing: '0.04em',
    }}>
      <span style={{ fontSize: 11 }}>{t.icon}</span>
      {t.label}
    </div>
  );
};

const StatusBadge = ({ name }) => {
  const s = STATUS_CFG[name] ?? STATUS_CFG.CANCELLED;
  const isActive = name === 'ACTIVE';
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: s.bg, border: `1px solid ${s.border}`,
      borderRadius: 20, padding: '3px 12px',
      color: s.color, fontWeight: 700, fontSize: 11,
    }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%', background: s.dot, flexShrink: 0,
        boxShadow: isActive ? `0 0 0 3px ${s.dot}30` : 'none',
        animation: isActive ? 'dotPulse 1.4s infinite' : 'none',
      }} />
      {name}
    </div>
  );
};

const SectionHeader = ({ icon, title, subtitle, accent = '#f5222d', extra }) => (
  <div style={{
    display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
    marginBottom: 20,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      <div style={{
        width: 44, height: 44, borderRadius: 12, flexShrink: 0,
        background: `linear-gradient(135deg, ${accent}, ${accent}cc)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: `0 4px 12px ${accent}50`, fontSize: 18, color: 'white',
      }}>
        {icon}
      </div>
      <div>
        <div style={{ fontWeight: 700, fontSize: 16, color: '#141414', lineHeight: 1.2 }}>{title}</div>
        {subtitle && <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 3 }}>{subtitle}</div>}
      </div>
    </div>
    {extra}
  </div>
);

/* ═══════════════════════════════════════════════════════════════
   TAB 1 — DASHBOARD
═══════════════════════════════════════════════════════════════ */
const Dashboard = ({ statusData, isLoading, refetch }) => {
  const { message, modal } = App.useApp();
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [lockdownOpen, setLockdownOpen] = useState(false);
  const [fireOpen, setFireOpen]         = useState(false);

  const lockdownM = useMutation({
    mutationFn: (body) => apiService.post('/api/emergency/lockdown/', body),
    onSuccess: () => {
      message.success('Lockdown executed');
      qc.invalidateQueries(['emergency-status']);
      setLockdownOpen(false); form.resetFields();
    },
    onError: (e) => message.error(e?.message || 'Lockdown failed'),
  });

  const fireModeM = useMutation({
    mutationFn: (body) => apiService.post('/api/emergency/fire-mode/', body),
    onSuccess: () => {
      message.success('Fire mode updated');
      qc.invalidateQueries(['emergency-status']);
      setFireOpen(false);
    },
    onError: (e) => message.error(e?.message || 'Fire mode failed'),
  });

  const d = statusData || {};
  const isEmergency = d.system_status === 'EMERGENCY';

  const actions = [
    { key: 'lock',    label: 'Emergency Lockdown', sub: 'Lock all doors instantly',    icon: <LockOutlined />,        from: '#cf1322', to: '#820014', onClick: () => setLockdownOpen(true) },
    { key: 'fire',    label: 'Fire Mode',           sub: 'Evacuate & unlock fire exits', icon: <FireOutlined />,        from: '#d4380d', to: '#871400', onClick: () => setFireOpen(true) },
    { key: 'clear',   label: 'All Clear',           sub: 'End all emergencies',         icon: <CheckCircleOutlined />, from: '#389e0d', to: '#135200', onClick: () => modal.confirm({
        title: 'Issue All Clear?',
        icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
        content: 'This will deactivate all emergency systems and restore normal operation.',
        okText: 'ISSUE ALL CLEAR',
        okButtonProps: { style: { background: '#389e0d', borderColor: '#389e0d' } },
        onOk: () => fireModeM.mutate({ action: 'clear', reason: 'All Clear from Dashboard' }),
      }),
      disabled: !isEmergency,
    },
    { key: 'muster',  label: 'Start Mustering',     sub: 'Personnel headcount',         icon: <TeamOutlined />,        from: '#096dd9', to: '#003a8c', onClick: () => message.info('Navigate to the Mustering module to start a headcount event.') },
  ];

  const recentCols = [
    { title: 'Time', dataIndex: 'start_time', width: 150, fixed: 'left',
      render: v => <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#595959' }}>{v ? new Date(v).toLocaleString() : '—'}</span> },
    { title: 'Type', dataIndex: 'event_type', width: 130, render: v => <EventBadge type={v} /> },
    { title: 'Status', dataIndex: 'status_name', width: 120, render: v => <StatusBadge name={v} /> },
    { title: 'Trigger', dataIndex: 'trigger_source', ellipsis: true,
      render: v => <span style={{ fontSize: 12 }}>{v || '—'}</span> },
    { title: 'Reason', dataIndex: 'reason', ellipsis: true,
      render: v => <span style={{ fontSize: 12, color: '#8c8c8c' }}>{v || '—'}</span> },
  ];

  return (
    <div style={{ padding: '24px 28px' }}>
      {/* Emergency Banner */}
      {isEmergency && (
        <div style={{
          background: 'linear-gradient(135deg, #820014, #cf1322)',
          borderRadius: 14, padding: '16px 22px', marginBottom: 24,
          display: 'flex', alignItems: 'center', gap: 14,
          boxShadow: '0 4px 24px rgba(207,19,34,0.45)',
          animation: 'bannerGlow 1.8s ease-in-out infinite',
        }}>
          <div style={{
            width: 46, height: 46, borderRadius: 12,
            background: 'rgba(255,255,255,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            backdropFilter: 'blur(4px)',
          }}>
            <WarningOutlined style={{ color: 'white', fontSize: 22 }} />
          </div>
          <div>
            <div style={{ color: 'white', fontWeight: 800, fontSize: 15, letterSpacing: '0.04em' }}>
              ⚠ EMERGENCY SYSTEM ACTIVE
            </div>
            <div style={{ color: 'rgba(255,255,255,0.75)', fontSize: 12, marginTop: 2 }}>
              {d.total_emergencies || 0} active emergency events — all systems on high alert
            </div>
          </div>
        </div>
      )}

      {/* Stats */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        {[
          { label: 'Active Emergencies', value: d.total_emergencies || 0, icon: <AlertOutlined />, from: '#cf1322', to: '#820014' },
          { label: 'Doors Locked',       value: d.doors_locked || 0,      icon: <LockOutlined />, from: '#d4380d', to: '#871400' },
          { label: 'Sirens Active',      value: d.sirens_on || 0,         icon: <SoundOutlined />, from: '#d48806', to: '#874d00' },
          { label: 'Zones Monitored',    value: (d.zone_status || []).length, icon: <GlobalOutlined />, from: '#096dd9', to: '#003a8c' },
        ].map(s => (
          <Col key={s.label} xs={12} sm={6}>
            <GradStat {...s} />
          </Col>
        ))}
      </Row>

      {/* Action Buttons */}
      <div style={{
        background: 'white', borderRadius: 16, padding: 20, marginBottom: 24,
        boxShadow: '0 2px 16px rgba(0,0,0,0.06)', border: '1px solid #f0f0f0',
      }}>
        <div style={{ fontWeight: 700, fontSize: 14, color: '#141414', marginBottom: 4 }}>Emergency Actions</div>
        <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 16 }}>
          Immediate response controls — all actions require confirmation
        </div>
        <Row gutter={12}>
          {actions.map(a => (
            <Col key={a.key} xs={12} sm={6}>
              <button
                onClick={a.onClick}
                disabled={a.disabled}
                style={{
                  width: '100%', border: 'none', cursor: a.disabled ? 'not-allowed' : 'pointer',
                  borderRadius: 14, padding: '18px 10px',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
                  background: a.disabled
                    ? 'linear-gradient(135deg, #f5f5f5, #e8e8e8)'
                    : `linear-gradient(145deg, ${a.from}, ${a.to})`,
                  boxShadow: a.disabled ? 'none' : `0 6px 20px ${a.from}45`,
                  color: a.disabled ? '#bfbfbf' : 'white',
                  transition: 'all 0.2s ease',
                  position: 'relative', overflow: 'hidden',
                }}
              >
                <div style={{
                  position: 'absolute', top: -10, right: -10,
                  width: 60, height: 60, borderRadius: '50%',
                  background: 'rgba(255,255,255,0.07)',
                }} />
                <div style={{
                  width: 48, height: 48, borderRadius: 12,
                  background: a.disabled ? '#e8e8e8' : 'rgba(255,255,255,0.18)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 22, backdropFilter: 'blur(4px)',
                }}>
                  {a.icon}
                </div>
                <div style={{ fontWeight: 700, fontSize: 12, textAlign: 'center', lineHeight: 1.3 }}>{a.label}</div>
                <div style={{ fontSize: 10, opacity: 0.75, textAlign: 'center', fontWeight: 400 }}>{a.sub}</div>
              </button>
            </Col>
          ))}
        </Row>
      </div>

      <Row gutter={20}>
        {/* Zone Status */}
        <Col xs={24} lg={10}>
          <div style={{
            background: 'white', borderRadius: 16, padding: 20,
            boxShadow: '0 2px 16px rgba(0,0,0,0.06)', border: '1px solid #f0f0f0',
            marginBottom: 20,
          }}>
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 14 }}>
              <GlobalOutlined style={{ marginRight: 8, color: '#1890ff' }} />Zone Status
            </div>
            {(d.zone_status || []).length === 0 ? (
              <Empty description="No zones configured" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ margin: '12px 0' }} />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {(d.zone_status || []).map(z => {
                  const zCol = z.status === 'ACTIVE' ? '#cf1322' : z.status === 'WARNING' ? '#d48806' : '#389e0d';
                  return (
                    <div key={z.id} style={{
                      display: 'flex', alignItems: 'center', gap: 12,
                      background: `${zCol}06`, border: `1px solid ${zCol}20`,
                      borderRadius: 10, padding: '10px 14px',
                    }}>
                      <div style={{
                        width: 10, height: 10, borderRadius: '50%', background: zCol, flexShrink: 0,
                        boxShadow: `0 0 0 3px ${zCol}25`,
                        animation: z.status === 'ACTIVE' ? 'dotPulse 1.4s infinite' : 'none',
                      }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: 13, color: '#141414' }}>{z.name}</div>
                        <div style={{ fontSize: 11, color: '#8c8c8c' }}>Cap: {z.capacity || '—'} · Evac: {z.evac_point || 'N/A'}</div>
                      </div>
                      <div style={{ fontWeight: 700, fontSize: 11, color: zCol }}>{z.status}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </Col>

        {/* Recent Events */}
        <Col xs={24} lg={14}>
          <div style={{
            background: 'white', borderRadius: 16,
            boxShadow: '0 2px 16px rgba(0,0,0,0.06)', border: '1px solid #f0f0f0',
            overflow: 'hidden', marginBottom: 20,
          }}>
            <div style={{ padding: '16px 20px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>
                <ClockCircleOutlined style={{ marginRight: 8, color: '#fa8c16' }} />Recent Events
              </div>
              <Button size="small" icon={<ReloadOutlined />} type="text" onClick={refetch} loading={isLoading} />
            </div>
            <Table columns={recentCols} dataSource={d.recent_events || []}
              rowKey={(r, i) => r.id ?? i} size="small"
              loading={isLoading} pagination={{ pageSize: 8, size: 'small' }}
              scroll={{ x: 600 }}
              rowClassName={r => r.status_name === 'ACTIVE' ? 'em-row-active' : ''}
              locale={{ emptyText: <div style={{ padding: '24px 0', color: '#8c8c8c', textAlign: 'center' }}>No recent events</div> }}
            />
          </div>
        </Col>
      </Row>

      {/* Modals */}
      <Modal open={lockdownOpen}
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'linear-gradient(135deg,#cf1322,#820014)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <LockOutlined style={{ color: 'white', fontSize: 16 }} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Emergency Lockdown</div>
              <div style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 400 }}>Immediate door lock action</div>
            </div>
          </div>
        }
        onCancel={() => { setLockdownOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        confirmLoading={lockdownM.isPending}
        okText="EXECUTE LOCKDOWN" okButtonProps={{ danger: true }}
        width={500}>
        <div style={{ background: 'rgba(207,19,34,0.05)', border: '1px solid rgba(207,19,34,0.2)', borderRadius: 10, padding: '12px 16px', marginBottom: 20 }}>
          <Space>
            <ExclamationCircleOutlined style={{ color: '#cf1322' }} />
            <span style={{ fontSize: 13, color: '#cf1322', fontWeight: 600 }}>All selected doors will be locked immediately. Personnel will be unable to pass.</span>
          </Space>
        </div>
        <Form form={form} layout="vertical"
          onFinish={v => lockdownM.mutate({ scope: v.scope || 'global', action: 'lock', reason: v.reason })}>
          <Form.Item name="scope" label="Lockdown Scope" initialValue="global">
            <Select size="large">
              <Option value="global"><Space><GlobalOutlined />Global — All Doors</Space></Option>
              <Option value="zone"><Space><ApiOutlined />Zone — Specific Zone(s)</Space></Option>
            </Select>
          </Form.Item>
          <Form.Item name="reason" label="Reason for Lockdown" rules={[{ required: true, message: 'A reason is mandatory for audit purposes' }]}>
            <TextArea rows={3} placeholder="e.g. Intruder detected on Platform A — security threat confirmed by CCTV…" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal open={fireOpen}
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'linear-gradient(135deg,#d4380d,#871400)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FireOutlined style={{ color: 'white', fontSize: 16 }} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Activate Fire Mode</div>
              <div style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 400 }}>Fire evacuation protocol</div>
            </div>
          </div>
        }
        onCancel={() => setFireOpen(false)}
        onOk={() => fireModeM.mutate({ action: 'activate', reason: 'Fire mode activated from Dashboard' })}
        confirmLoading={fireModeM.isPending}
        okText="ACTIVATE FIRE MODE"
        okButtonProps={{ style: { background: 'linear-gradient(135deg,#d4380d,#871400)', border: 'none' } }}
        width={480}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[
            { icon: <UnlockOutlined />, text: 'All fire exit doors will be UNLOCKED for evacuation', col: '#389e0d' },
            { icon: <SoundOutlined />,  text: 'Emergency sirens will be ACTIVATED', col: '#d4380d' },
            { icon: <TeamOutlined />,   text: 'Personnel mustering will START automatically', col: '#096dd9' },
            { icon: <LockOutlined />,   text: 'Danger zone doors will LOCK to contain hazard', col: '#d48806' },
          ].map((item, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              background: `${item.col}08`, borderRadius: 8, padding: '10px 14px',
              border: `1px solid ${item.col}20`,
            }}>
              <span style={{ color: item.col, fontSize: 15 }}>{item.icon}</span>
              <span style={{ fontSize: 13, color: '#141414' }}>{item.text}</span>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════
   TAB 2 — LOCKDOWN
═══════════════════════════════════════════════════════════════ */
const Lockdown = () => {
  const { message, modal } = App.useApp();
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [scopeVal, setScopeVal] = useState('global');

  const { data: doorsData } = useQuery({ queryKey: ['em-doors'], queryFn: () => apiService.get('/api/access-control/doors/') });
  const doors = doorsData?.data || [];
  const { data: zonesData } = useQuery({ queryKey: ['em-zones'], queryFn: () => apiService.get('/api/mustering/zones/') });
  const zones = zonesData?.data || zonesData?.results || [];

  const doLockdown = useMutation({
    mutationFn: (body) => apiService.post('/api/emergency/lockdown/', body),
    onSuccess: (_, v) => {
      message.success(`${v.action === 'lock' ? 'Lockdown' : 'Unlock'} executed`);
      qc.invalidateQueries(['emergency-status']);
      form.resetFields(); setScopeVal('global');
    },
    onError: (e) => message.error(e?.message || 'Action failed'),
  });

  const handleSubmit = (values) => {
    const isLock = values.action === 'lock';
    modal.confirm({
      title: isLock ? 'Confirm Emergency Lockdown' : 'Confirm Emergency Unlock',
      icon: <ExclamationCircleOutlined style={{ color: isLock ? '#cf1322' : '#389e0d' }} />,
      content: (
        <div>
          <p style={{ marginBottom: 8 }}>You are about to <strong>{isLock ? 'LOCK' : 'UNLOCK'}</strong> all doors in the <strong>{values.scope}</strong> scope.</p>
          <p style={{ color: '#8c8c8c', fontSize: 13 }}>Reason: <em>{values.reason}</em></p>
        </div>
      ),
      okType: isLock ? 'danger' : 'primary',
      okText: isLock ? 'LOCKDOWN NOW' : 'UNLOCK NOW',
      onOk: () => doLockdown.mutate({
        scope: values.scope,
        action: values.action,
        reason: values.reason,
        zone_ids: values.scope === 'zone' ? values.zone_ids : undefined,
        door_ids: values.scope === 'door' ? values.door_ids : undefined,
      }),
    });
  };

  const scopeDefs = [
    { v: 'global', l: 'Global', desc: 'Every door in the facility', icon: <GlobalOutlined />, from: '#cf1322', to: '#820014' },
    { v: 'zone',   l: 'Zone',   desc: 'All doors in selected zone(s)', icon: <EnvironmentOutlined />, from: '#d4380d', to: '#ad2102' },
    { v: 'door',   l: 'Door',   desc: 'Specific individual doors', icon: <LockOutlined />, from: '#096dd9', to: '#003a8c' },
  ];

  return (
    <div style={{ padding: '24px 28px' }}>
      <SectionHeader icon={<LockOutlined />} accent="#cf1322"
        title="Lockdown Control"
        subtitle="Execute emergency lockdown or controlled unlock across any scope"
        extra={
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#fff1f0', border: '1px solid #ffa39e', borderRadius: 8, padding: '6px 12px' }}>
            <ExclamationCircleOutlined style={{ color: '#cf1322' }} />
            <span style={{ fontSize: 12, color: '#cf1322', fontWeight: 600 }}>Reason required for audit</span>
          </div>
        }
      />

      {/* Scope cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        {scopeDefs.map(s => (
          <Col key={s.v} xs={8}>
            <div
              onClick={() => { setScopeVal(s.v); form.setFieldValue('scope', s.v); }}
              style={{
                borderRadius: 14, padding: '16px 18px', cursor: 'pointer',
                background: scopeVal === s.v ? `linear-gradient(135deg, ${s.from}, ${s.to})` : 'white',
                border: scopeVal === s.v ? 'none' : '1px solid #f0f0f0',
                boxShadow: scopeVal === s.v ? `0 6px 20px ${s.from}40` : '0 2px 8px rgba(0,0,0,0.04)',
                transition: 'all 0.2s ease',
              }}
            >
              <div style={{ fontSize: 22, marginBottom: 8, color: scopeVal === s.v ? 'white' : s.from }}>{s.icon}</div>
              <div style={{ fontWeight: 700, fontSize: 14, color: scopeVal === s.v ? 'white' : '#141414' }}>{s.l}</div>
              <div style={{ fontSize: 11, marginTop: 3, color: scopeVal === s.v ? 'rgba(255,255,255,0.7)' : '#8c8c8c' }}>{s.desc}</div>
            </div>
          </Col>
        ))}
      </Row>

      <div style={{ background: 'white', borderRadius: 16, padding: 24, boxShadow: '0 2px 16px rgba(0,0,0,0.06)', border: '1px solid #f0f0f0' }}>
        <Form form={form} layout="vertical" onFinish={handleSubmit} initialValues={{ action: 'lock', scope: 'global' }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="action" label={<span style={{ fontWeight: 600 }}>Action</span>} rules={[{ required: true }]}>
                <Select size="large">
                  <Option value="lock">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <LockOutlined style={{ color: '#cf1322' }} />
                      <div>
                        <div style={{ fontWeight: 600, lineHeight: 1.2 }}>Lock — Lockdown</div>
                        <div style={{ fontSize: 11, color: '#8c8c8c' }}>Restrict access immediately</div>
                      </div>
                    </div>
                  </Option>
                  <Option value="unlock">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <UnlockOutlined style={{ color: '#389e0d' }} />
                      <div>
                        <div style={{ fontWeight: 600, lineHeight: 1.2 }}>Unlock — Release</div>
                        <div style={{ fontSize: 11, color: '#8c8c8c' }}>Restore normal access</div>
                      </div>
                    </div>
                  </Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="scope" label={<span style={{ fontWeight: 600 }}>Scope</span>} rules={[{ required: true }]}>
                <Select size="large" value={scopeVal} onChange={v => setScopeVal(v)}>
                  <Option value="global">Global — All Doors</Option>
                  <Option value="zone">Zone</Option>
                  <Option value="door">Specific Doors</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          {scopeVal === 'zone' && (
            <Form.Item name="zone_ids" label={<span style={{ fontWeight: 600 }}>Target Zones</span>}>
              <Select mode="multiple" placeholder="Select one or more zones…" size="large">
                {zones.map(z => <Option key={z.id} value={z.id}>{z.name || z.zone_name}</Option>)}
              </Select>
            </Form.Item>
          )}

          {scopeVal === 'door' && (
            <Form.Item name="door_ids" label={<span style={{ fontWeight: 600 }}>Target Doors</span>}>
              <Select mode="multiple" placeholder="Select specific doors…" size="large" showSearch optionFilterProp="children">
                {doors.map(d => <Option key={d.id} value={d.id}>{d.door_name}</Option>)}
              </Select>
            </Form.Item>
          )}

          <Form.Item name="reason" label={<span style={{ fontWeight: 600 }}>Reason <span style={{ color: '#cf1322' }}>*</span></span>}
            rules={[{ required: true, message: 'Reason is mandatory for audit trail purposes' }]}>
            <TextArea rows={3} placeholder="Describe the security situation requiring this action…" size="large" />
          </Form.Item>

          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item noStyle shouldUpdate={(p, c) => p.action !== c.action}>
              {({ getFieldValue }) => {
                const isLock = getFieldValue('action') === 'lock';
                return (
                  <Button
                    htmlType="submit" size="large" loading={doLockdown.isPending}
                    icon={isLock ? <LockOutlined /> : <UnlockOutlined />}
                    style={{
                      background: isLock
                        ? 'linear-gradient(135deg, #cf1322, #820014)'
                        : 'linear-gradient(135deg, #389e0d, #135200)',
                      border: 'none', color: 'white', fontWeight: 700, height: 46, paddingInline: 28,
                      boxShadow: isLock ? '0 4px 16px rgba(207,19,34,0.4)' : '0 4px 16px rgba(56,158,13,0.4)',
                      borderRadius: 10,
                    }}>
                    {isLock ? 'Execute Lockdown' : 'Execute Unlock'}
                  </Button>
                );
              }}
            </Form.Item>
            <Button size="large" onClick={() => { form.resetFields(); setScopeVal('global'); }}
              style={{ height: 46, borderRadius: 10 }}>
              Reset
            </Button>
          </div>
        </Form>
      </div>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════
   TAB 3 — FIRE MODE
═══════════════════════════════════════════════════════════════ */
const FireMode = () => {
  const { message, modal } = App.useApp();
  const qc = useQueryClient();

  const { data: zonesData } = useQuery({ queryKey: ['em-zones'], queryFn: () => apiService.get('/api/mustering/zones/') });
  const zones = zonesData?.data || zonesData?.results || [];

  const fireModeM = useMutation({
    mutationFn: (body) => apiService.post('/api/emergency/fire-mode/', body),
    onSuccess: (_, v) => {
      message.success(v.action === 'activate' ? 'Fire mode activated — evacuation in progress' : 'All Clear issued — fire mode deactivated');
      qc.invalidateQueries(['emergency-status']);
    },
    onError: (e) => message.error(e?.message || 'Action failed'),
  });

  const confirmFire = (zoneId, zoneName) => {
    modal.confirm({
      title: 'Activate Fire Mode',
      icon: <FireOutlined style={{ color: '#d4380d' }} />,
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: '#141414' }}>
            Target: {zoneName || 'Global — All Zones'}
          </div>
          {[
            '🔓 Fire exit doors will UNLOCK for evacuation',
            '🔔 Emergency sirens will ACTIVATE',
            '🏃 Personnel mustering will START automatically',
          ].map((t, i) => (
            <div key={i} style={{ fontSize: 13, color: '#595959' }}>{t}</div>
          ))}
        </div>
      ),
      okText: 'ACTIVATE FIRE MODE',
      okButtonProps: { style: { background: 'linear-gradient(135deg,#d4380d,#871400)', border: 'none', fontWeight: 700 } },
      onOk: () => fireModeM.mutate({ zone_id: zoneId, action: 'activate', reason: `Fire mode activated${zoneName ? ` — zone ${zoneName}` : ' globally'}` }),
    });
  };

  const steps = [
    { step: 1, label: 'Alert Triggered',   desc: 'System detects or receives fire alarm signal', icon: <AlertOutlined />, color: '#d4380d' },
    { step: 2, label: 'Doors React',       desc: 'Fire exits unlock, danger zones lock', icon: <LockOutlined />, color: '#cf1322' },
    { step: 3, label: 'Sirens Activate',   desc: 'Emergency sirens sound across facility', icon: <SoundOutlined />, color: '#d48806' },
    { step: 4, label: 'Mustering Starts',  desc: 'Personnel report to designated muster points', icon: <TeamOutlined />, color: '#096dd9' },
    { step: 5, label: 'Headcount Done',    desc: 'All personnel accounted for — issue All Clear', icon: <CheckCircleOutlined />, color: '#389e0d' },
  ];

  return (
    <div style={{ padding: '24px 28px' }}>
      <SectionHeader icon={<FireOutlined />} accent="#d4380d"
        title="Fire Mode Control"
        subtitle="Activate fire evacuation protocol — global or per-zone"
      />

      <Row gutter={20}>
        <Col xs={24} lg={15}>
          <Row gutter={16} style={{ marginBottom: 20 }}>
            {/* Global card */}
            <Col xs={24} sm={12}>
              <div style={{
                borderRadius: 16, padding: 22, textAlign: 'center',
                background: 'linear-gradient(145deg, #fff2e8, #fff8f3)',
                border: '2px solid #d4380d',
                boxShadow: '0 8px 24px rgba(212,56,13,0.12)',
              }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>🔥</div>
                <div style={{ fontWeight: 800, fontSize: 17, marginBottom: 4, color: '#141414' }}>Global Fire Mode</div>
                <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 18 }}>Activates across all zones & doors</div>
                <Button block size="large" loading={fireModeM.isPending} onClick={() => confirmFire(null, null)}
                  style={{
                    background: 'linear-gradient(135deg, #d4380d, #871400)',
                    border: 'none', color: 'white', fontWeight: 700, height: 48, borderRadius: 10,
                    boxShadow: '0 4px 16px rgba(212,56,13,0.4)',
                  }}>
                  <FireOutlined /> ACTIVATE GLOBAL
                </Button>
              </div>
            </Col>

            {/* All Clear card */}
            <Col xs={24} sm={12}>
              <div style={{
                borderRadius: 16, padding: 22, textAlign: 'center',
                background: 'linear-gradient(145deg, #f6ffed, #f0fff4)',
                border: '2px solid #389e0d',
                boxShadow: '0 8px 24px rgba(56,158,13,0.12)',
              }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
                <div style={{ fontWeight: 800, fontSize: 17, marginBottom: 4, color: '#141414' }}>All Clear</div>
                <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 18 }}>End emergency — restore all systems</div>
                <Button block size="large" loading={fireModeM.isPending}
                  onClick={() => fireModeM.mutate({ action: 'clear', reason: 'All Clear issued from Fire Mode tab' })}
                  style={{
                    background: 'linear-gradient(135deg, #389e0d, #135200)',
                    border: 'none', color: 'white', fontWeight: 700, height: 48, borderRadius: 10,
                    boxShadow: '0 4px 16px rgba(56,158,13,0.4)',
                  }}>
                  <CheckCircleOutlined /> ISSUE ALL CLEAR
                </Button>
              </div>
            </Col>
          </Row>

          {/* Zone cards */}
          {zones.length > 0 && (
            <div style={{ background: 'white', borderRadius: 16, padding: 20, boxShadow: '0 2px 16px rgba(0,0,0,0.06)', border: '1px solid #f0f0f0' }}>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 14, color: '#141414' }}>
                <EnvironmentOutlined style={{ marginRight: 8, color: '#fa8c16' }} />Fire Mode by Zone
              </div>
              <Row gutter={[12, 12]}>
                {zones.map(z => (
                  <Col key={z.id} xs={24} sm={12}>
                    <div style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      background: '#fff7e6', border: '1px solid #ffd591',
                      borderRadius: 10, padding: '12px 16px',
                    }}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{z.name || z.zone_name}</div>
                        <div style={{ fontSize: 11, color: '#8c8c8c' }}>Cap: {z.capacity || '—'}</div>
                      </div>
                      <Button size="small" icon={<FireOutlined />}
                        onClick={() => confirmFire(z.id, z.name || z.zone_name)}
                        style={{ background: '#fa8c16', border: 'none', color: 'white', fontWeight: 600 }}>
                        Zone Fire
                      </Button>
                    </div>
                  </Col>
                ))}
              </Row>
            </div>
          )}
        </Col>

        {/* Protocol steps */}
        <Col xs={24} lg={9}>
          <div style={{ background: 'white', borderRadius: 16, padding: 20, boxShadow: '0 2px 16px rgba(0,0,0,0.06)', border: '1px solid #f0f0f0' }}>
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16, color: '#141414' }}>
              <InfoCircleOutlined style={{ marginRight: 8, color: '#1890ff' }} />Fire Response Protocol
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {steps.map((s, i) => (
                <div key={i} style={{ display: 'flex', gap: 12, paddingBottom: i < steps.length - 1 ? 16 : 0 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0 }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                      background: `${s.color}15`, border: `2px solid ${s.color}40`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 13, color: s.color,
                    }}>
                      {s.icon}
                    </div>
                    {i < steps.length - 1 && (
                      <div style={{ width: 2, flex: 1, minHeight: 16, background: '#f0f0f0', marginTop: 4 }} />
                    )}
                  </div>
                  <div style={{ paddingBottom: i < steps.length - 1 ? 4 : 0, paddingTop: 4 }}>
                    <div style={{ fontWeight: 700, fontSize: 12, color: s.color }}>Step {s.step}: {s.label}</div>
                    <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2 }}>{s.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Col>
      </Row>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════
   TAB 4 — NOTIFICATIONS
═══════════════════════════════════════════════════════════════ */
const Notifications = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [sendOpen, setSendOpen] = useState(false);
  const [activeChannels, setActiveChannels] = useState({ whatsapp: true, email: true });

  const { data: notifData, isLoading, refetch } = useQuery({
    queryKey: ['emergency-notifications'],
    queryFn: () => apiService.get('/api/emergency/notifications/'),
  });
  const notifications = notifData?.data || [];

  const sendM = useMutation({
    mutationFn: (body) => apiService.post('/api/emergency/notify/', body),
    onSuccess: (r) => {
      message.success(r?.data?.message || 'Alert sent', 8);
      qc.invalidateQueries(['emergency-notifications']);
      setSendOpen(false); form.resetFields(); setActiveChannels({ whatsapp: true, email: true });
    },
    onError: (e) => message.error(e?.message || 'Send failed'),
  });

  const NOTIF_STATUS = {
    PENDING:   { color: '#d48806', bg: '#fffbe6', border: '#ffe58f' },
    SENT:      { color: '#096dd9', bg: '#e6f7ff', border: '#91d5ff' },
    DELIVERED: { color: '#389e0d', bg: '#f6ffed', border: '#b7eb8f' },
    FAILED:    { color: '#cf1322', bg: '#fff1f0', border: '#ffa39e' },
    SKIPPED:   { color: '#8c8c8c', bg: '#fafafa', border: '#d9d9d9' },
  };
  const SOURCE = { emergency: 'Emergency', muster: 'Muster', muster_all_clear: 'All clear',
    muster_escalation: 'Escalation', panic: 'Panic', test: 'Test' };

  const cols = [
    { title: 'Time', dataIndex: 'created_at', width: 150,
      render: v => <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#595959' }}>{v ? String(v).slice(0, 16) : '—'}</span> },
    { title: 'Alert', dataIndex: 'source_type', width: 110,
      render: v => <Tag style={{ marginInlineEnd: 0 }}>{SOURCE[v] || v}</Tag> },
    { title: 'Channel', dataIndex: 'channel_name', width: 110,
      render: v => {
        const ch = Object.values(CHANNEL_CFG).find(c => c.label.toUpperCase() === String(v).toUpperCase()) || { color: '#595959', bg: '#f5f5f5', border: '#d9d9d9' };
        return (
          <div style={{ display: 'inline-flex', background: ch.bg, border: `1px solid ${ch.border}`, borderRadius: 16, padding: '2px 10px', color: ch.color, fontWeight: 700, fontSize: 11 }}>
            {v}
          </div>
        );
      }},
    { title: 'Status', dataIndex: 'status_name', width: 110,
      render: (v, r) => {
        const s = NOTIF_STATUS[v] || { color: '#595959', bg: '#f5f5f5', border: '#d9d9d9' };
        return (
          <Tooltip title={r.error_msg || ''}>
            <div style={{ display: 'inline-flex', background: s.bg, border: `1px solid ${s.border}`, borderRadius: 16, padding: '2px 10px', color: s.color, fontWeight: 700, fontSize: 11 }}>{v}</div>
          </Tooltip>
        );
      }},
    { title: 'Recipient', dataIndex: 'recipient_addr', ellipsis: true,
      render: (v, r) => <span style={{ fontSize: 12 }}><b>{r.recipient_name}</b>{r.recipient_name ? ' · ' : ''}{v || '—'}</span> },
    { title: 'Why not sent', dataIndex: 'error_msg', ellipsis: true,
      render: v => <span style={{ fontSize: 12, color: '#b45309' }}>{v || ''}</span> },
    { title: 'Message', dataIndex: 'message', ellipsis: true,
      render: v => <span style={{ fontSize: 12, color: '#595959' }}>{v}</span> },
  ];

  const sent = notifications.filter(n => ['SENT', 'DELIVERED'].includes(n.status_name)).length;
  const failed = notifications.filter(n => n.status_name === 'FAILED').length;
  const pending = notifications.filter(n => n.status_name === 'SKIPPED').length;

  return (
    <div style={{ padding: '24px 28px' }}>
      <SectionHeader icon={<BellOutlined />} accent="#d48806"
        title="Mass Notifications"
        subtitle="Broadcast emergency alerts across all communication channels"
        extra={
          <Button type="primary" icon={<BellOutlined />} size="large"
            onClick={() => setSendOpen(true)}
            style={{ background: 'linear-gradient(135deg,#d48806,#874d00)', border: 'none', borderRadius: 10, fontWeight: 700 }}>
            Send Alert
          </Button>
        }
      />

      <Row gutter={16} style={{ marginBottom: 24 }}>
        {[
          { label: 'Messages', value: notifications.length, from: '#096dd9', to: '#003a8c' },
          { label: 'Sent', value: sent, from: '#389e0d', to: '#135200' },
          { label: 'Skipped (channel not set up)', value: pending, from: '#8c8c8c', to: '#434343' },
          { label: 'Failed', value: failed, from: '#cf1322', to: '#820014' },
        ].map(s => (
          <Col key={s.label} xs={12} sm={6}><GradStat {...s} /></Col>
        ))}
      </Row>

      <div style={{ background: 'white', borderRadius: 16, overflow: 'hidden', boxShadow: '0 2px 16px rgba(0,0,0,0.06)', border: '1px solid #f0f0f0' }}>
        <div style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f0f0f0' }}>
          <div style={{ fontWeight: 700, fontSize: 14 }}>Notification History</div>
          <Button icon={<ReloadOutlined />} size="small" type="text" onClick={refetch} loading={isLoading} />
        </div>
        <Table columns={cols} dataSource={notifications} rowKey="id"
          loading={isLoading} size="small" pagination={{ pageSize: 20 }}
          scroll={{ x: 800 }} />
      </div>

      <Modal open={sendOpen}
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'linear-gradient(135deg,#d48806,#874d00)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <BellOutlined style={{ color: 'white', fontSize: 16 }} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Send Emergency Notification</div>
              <div style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 400 }}>Everyone on board + the emergency response team</div>
            </div>
          </div>
        }
        onCancel={() => { setSendOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        confirmLoading={sendM.isPending}
        okText="BROADCAST NOW"
        okButtonProps={{ style: { background: 'linear-gradient(135deg,#d48806,#874d00)', border: 'none', fontWeight: 700 } }}
        width={540}>
        <Form form={form} layout="vertical"
          onFinish={v => sendM.mutate({ event_type: v.event_type, message: v.message, channels: activeChannels, recipients: { all_employees: true } })}>
          <Form.Item name="event_type" label={<span style={{ fontWeight: 600 }}>Alert Type</span>}>
            <Select placeholder="Select emergency type…" size="large">
              {Object.entries(EVENT_TYPE_MAP).map(([k, t]) => (
                <Option key={k} value={+k}>
                  <Space>
                    <span style={{ color: t.color }}>{t.icon}</span>
                    <span style={{ color: t.color, fontWeight: 700 }}>{t.label}</span>
                  </Space>
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="message" label={<span style={{ fontWeight: 600 }}>Message</span>} rules={[{ required: true }]}>
            <TextArea rows={3} placeholder="Emergency notification message for all personnel…" />
          </Form.Item>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12, color: '#141414' }}>Channels</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 8 }}>
            {Object.entries(CHANNEL_CFG).filter(([key]) => ['whatsapp', 'email', 'sms'].includes(key)).map(([key, ch]) => (
              <div
                key={key}
                onClick={() => setActiveChannels(p => ({ ...p, [key]: !p[key] }))}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
                  border: `2px solid ${activeChannels[key] ? ch.color : '#e8e8e8'}`,
                  background: activeChannels[key] ? ch.bg : '#fafafa',
                  borderRadius: 10, padding: '8px 14px',
                  transition: 'all 0.2s',
                }}
              >
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: activeChannels[key] ? ch.color : '#d9d9d9',
                }} />
                <span style={{ fontWeight: 600, fontSize: 12, color: activeChannels[key] ? ch.color : '#8c8c8c' }}>{ch.label}</span>
              </div>
            ))}
          </div>
        </Form>
      </Modal>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════
   TAB 5 — DEVICES
═══════════════════════════════════════════════════════════════ */
const Devices = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['emergency-devices'],
    queryFn: () => apiService.get('/api/emergency/devices/'),
  });
  const devices = data?.data || [];

  const toggleM = useMutation({
    mutationFn: ({ id, status }) => apiService.post(`/api/emergency/devices/${id}/toggle/?status=${status}`),
    onSuccess: () => { message.success('Device updated'); qc.invalidateQueries(['emergency-devices']); },
    onError: (e) => message.error(e?.message || 'Toggle failed'),
  });

  const testAllM = useMutation({
    mutationFn: () => apiService.post('/api/emergency/devices/test-all/'),
    onSuccess: (r) => {
      const d = r?.data;
      message.success(`Test complete — ${d?.successful_tests}/${d?.total_devices} devices responded`);
    },
    onError: (e) => message.error(e?.message || 'Test failed'),
  });

  const on = devices.filter(d => d.status === 1).length;
  const fault = devices.filter(d => d.status === 2).length;
  const off = devices.filter(d => d.status === 0).length;

  return (
    <div style={{ padding: '24px 28px' }}>
      <SectionHeader icon={<ControlOutlined />} accent="#531dab"
        title="Emergency Devices"
        subtitle="Sirens, strobes, locks and panic buttons — real-time control"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={refetch} loading={isLoading}>Refresh</Button>
            <Button icon={<ThunderboltOutlined />} loading={testAllM.isPending} onClick={() => testAllM.mutate()}
              style={{ background: 'linear-gradient(135deg,#d48806,#874d00)', border: 'none', color: 'white', fontWeight: 700, borderRadius: 8 }}>
              Test All Devices
            </Button>
          </Space>
        }
      />

      <Row gutter={16} style={{ marginBottom: 24 }}>
        {[
          { label: 'Total Devices', value: devices.length, from: '#434343', to: '#1f1f1f' },
          { label: 'Active (ON)',   value: on,             from: '#cf1322', to: '#820014' },
          { label: 'Standby (OFF)', value: off,            from: '#096dd9', to: '#003a8c' },
          { label: 'Fault',         value: fault,          from: '#d48806', to: '#874d00' },
        ].map(s => (
          <Col key={s.label} xs={12} sm={6}><GradStat {...s} /></Col>
        ))}
      </Row>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spin size="large" /></div>
      ) : devices.length === 0 ? (
        <div style={{ background: 'white', borderRadius: 16, padding: 48, textAlign: 'center', boxShadow: '0 2px 16px rgba(0,0,0,0.06)' }}>
          <ApiOutlined style={{ fontSize: 48, color: '#d9d9d9', display: 'block', marginBottom: 12 }} />
          <div style={{ color: '#8c8c8c', fontSize: 15 }}>No emergency devices registered</div>
          <div style={{ color: '#bfbfbf', fontSize: 12, marginTop: 4 }}>Register devices in the hardware management panel</div>
        </div>
      ) : (
        <Row gutter={[16, 16]}>
          {devices.map(dev => {
            const cfg = DEVICE_CFG[dev.device_type] || { label: 'Unknown', icon: <ApiOutlined />, from: '#434343', to: '#1f1f1f' };
            const isOn = dev.status === 1;
            const isFault = dev.status === 2;
            return (
              <Col key={dev.id} xs={24} sm={12} md={8} lg={6}>
                <div style={{
                  background: 'white', borderRadius: 16, padding: 18,
                  boxShadow: isOn ? `0 6px 24px ${cfg.from}30` : '0 2px 12px rgba(0,0,0,0.06)',
                  border: isOn ? `1px solid ${cfg.from}40` : '1px solid #f0f0f0',
                  transition: 'all 0.3s ease',
                }}>
                  {/* Device Icon */}
                  <div style={{
                    width: 52, height: 52, borderRadius: 14, marginBottom: 12,
                    background: isOn
                      ? `linear-gradient(135deg, ${cfg.from}, ${cfg.to})`
                      : isFault ? 'linear-gradient(135deg,#d48806,#874d00)' : '#f5f5f5',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 22, color: (isOn || isFault) ? 'white' : '#bfbfbf',
                    boxShadow: isOn ? `0 4px 14px ${cfg.from}50` : 'none',
                  }}>
                    {cfg.icon}
                  </div>

                  <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 2, color: '#141414' }}>{cfg.label}</div>
                  <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#8c8c8c', marginBottom: 10 }}>{dev.terminal_sn}</div>

                  {dev.location_description && (
                    <div style={{ fontSize: 11, color: '#595959', marginBottom: 10 }}>
                      <EnvironmentOutlined style={{ marginRight: 4 }} />{dev.location_description}
                    </div>
                  )}

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{
                      display: 'inline-flex', alignItems: 'center', gap: 5,
                      background: isOn ? `${cfg.from}12` : isFault ? '#fffbe6' : '#f5f5f5',
                      border: `1px solid ${isOn ? `${cfg.from}30` : isFault ? '#ffe58f' : '#e8e8e8'}`,
                      borderRadius: 16, padding: '2px 8px',
                      color: isOn ? cfg.from : isFault ? '#d48806' : '#8c8c8c',
                      fontSize: 11, fontWeight: 700,
                    }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: isOn ? cfg.from : isFault ? '#d48806' : '#bfbfbf', animation: isOn ? 'dotPulse 1.4s infinite' : 'none' }} />
                      {dev.status_name}
                    </div>
                    <Switch
                      checked={isOn}
                      disabled={isFault}
                      checkedChildren="ON" unCheckedChildren="OFF"
                      onChange={v => toggleM.mutate({ id: dev.id, status: v ? 1 : 0 })}
                      style={{ background: isOn ? cfg.from : undefined }}
                    />
                  </div>

                  {dev.last_heartbeat && (
                    <div style={{ fontSize: 10, color: '#bfbfbf', marginTop: 10, borderTop: '1px solid #f5f5f5', paddingTop: 8 }}>
                      <ClockCircleOutlined style={{ marginRight: 4 }} />
                      {new Date(dev.last_heartbeat).toLocaleString()}
                    </div>
                  )}
                </div>
              </Col>
            );
          })}
        </Row>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════
   TAB 6 — TRIGGERS
═══════════════════════════════════════════════════════════════ */
const Triggers = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [panicOpen, setPanicOpen] = useState(false);

  const panicM = useMutation({
    mutationFn: (body) => apiService.post('/api/emergency/panic/', body),
    onSuccess: () => {
      message.success('Panic alert dispatched — emergency response initiated');
      qc.invalidateQueries(['emergency-status', 'em-triggers-audit']);
      setPanicOpen(false); form.resetFields();
    },
    onError: (e) => message.error(e?.message || 'Panic trigger failed'),
  });

  const { data: auditData } = useQuery({
    queryKey: ['em-triggers-audit'],
    queryFn: () => apiService.get('/api/emergency/audit/?limit=20'),
  });
  const recentTriggers = auditData?.data || [];

  return (
    <div style={{ padding: '24px 28px' }}>
      <SectionHeader icon={<ThunderboltOutlined />} accent="#cf1322"
        title="Emergency Triggers"
        subtitle="Panic button and recent emergency event history"
      />

      <Row gutter={20}>
        {/* Panic Button */}
        <Col xs={24} md={9}>
          <div style={{
            background: 'white', borderRadius: 20, padding: 28, textAlign: 'center',
            boxShadow: '0 8px 32px rgba(207,19,34,0.12)',
            border: '2px solid rgba(207,19,34,0.15)',
          }}>
            <div style={{
              width: 96, height: 96, borderRadius: '50%', margin: '0 auto 20px',
              background: 'linear-gradient(135deg, #cf1322, #820014)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 8px 32px rgba(207,19,34,0.4), 0 0 0 12px rgba(207,19,34,0.08), 0 0 0 24px rgba(207,19,34,0.04)',
              fontSize: 36, color: 'white',
            }}>
              <AlertOutlined />
            </div>

            <div style={{ fontWeight: 800, fontSize: 20, marginBottom: 6, letterSpacing: '-0.3px' }}>Panic Alert</div>
            <div style={{ color: '#8c8c8c', fontSize: 13, marginBottom: 24, lineHeight: 1.5 }}>
              Immediately triggers emergency response protocols. <strong style={{ color: '#cf1322' }}>Use only in real emergencies.</strong>
            </div>

            <Button block size="large" danger onClick={() => setPanicOpen(true)}
              style={{
                background: 'linear-gradient(135deg, #cf1322, #820014)',
                border: 'none', color: 'white', fontWeight: 800, fontSize: 16,
                height: 56, borderRadius: 14,
                boxShadow: '0 6px 20px rgba(207,19,34,0.45)',
                letterSpacing: '0.05em',
              }}>
              🚨 PANIC ALERT
            </Button>

            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'center', gap: 16 }}>
              {['Intruder Alert', 'Medical Emergency', 'Gas Leak'].map(t => (
                <div key={t} style={{ fontSize: 10, color: '#bfbfbf', textAlign: 'center' }}>{t}</div>
              ))}
            </div>
          </div>
        </Col>

        {/* Recent Triggers */}
        <Col xs={24} md={15}>
          <div style={{
            background: 'white', borderRadius: 16, padding: 20,
            boxShadow: '0 2px 16px rgba(0,0,0,0.06)', border: '1px solid #f0f0f0',
          }}>
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16, color: '#141414' }}>
              <ClockCircleOutlined style={{ marginRight: 8, color: '#fa8c16' }} />Recent Emergency Events
            </div>
            {recentTriggers.length === 0 ? (
              <Empty description="No recent events" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ padding: '20px 0' }} />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {recentTriggers.slice(0, 8).map((t, i) => (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '12px 14px', borderRadius: 10,
                    background: t.status_name === 'ACTIVE' ? 'rgba(207,19,34,0.04)' : '#fafafa',
                    border: t.status_name === 'ACTIVE' ? '1px solid rgba(207,19,34,0.15)' : '1px solid #f0f0f0',
                  }}>
                    <Space size={10}>
                      <EventBadge type={t.event_type} />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13, color: '#141414' }}>{t.trigger_source || 'System trigger'}</div>
                        <div style={{ fontSize: 11, color: '#8c8c8c' }}>{t.reason || '—'}</div>
                      </div>
                    </Space>
                    <div style={{ textAlign: 'right' }}>
                      <StatusBadge name={t.status_name} />
                      <div style={{ fontSize: 10, color: '#bfbfbf', marginTop: 4 }}>
                        {t.start_time ? new Date(t.start_time).toLocaleString() : '—'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Col>
      </Row>

      <Modal open={panicOpen}
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'linear-gradient(135deg,#cf1322,#820014)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <AlertOutlined style={{ color: 'white', fontSize: 16 }} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Confirm Panic Alert</div>
              <div style={{ fontSize: 11, color: '#cf1322', fontWeight: 600 }}>This will immediately trigger emergency response</div>
            </div>
          </div>
        }
        onCancel={() => { setPanicOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        confirmLoading={panicM.isPending}
        okText="🚨 TRIGGER PANIC NOW"
        okButtonProps={{ danger: true, size: 'large', style: { fontWeight: 700 } }}
        width={460}>
        <div style={{ background: 'rgba(207,19,34,0.04)', border: '1px solid rgba(207,19,34,0.2)', borderRadius: 10, padding: '12px 16px', marginBottom: 20 }}>
          <Space>
            <ExclamationCircleOutlined style={{ color: '#cf1322' }} />
            <span style={{ fontSize: 13, color: '#cf1322' }}>Immediate emergency response will be dispatched. Only trigger in a real emergency.</span>
          </Space>
        </div>
        <Form form={form} layout="vertical"
          onFinish={v => panicM.mutate({ location: v.location, reason: v.reason })}>
          <Form.Item name="location" label={<span style={{ fontWeight: 600 }}>Your Current Location</span>} rules={[{ required: true }]}>
            <Input size="large" placeholder="e.g. Platform A — Engine Room — Deck 3 Corridor" prefix={<EnvironmentOutlined />} />
          </Form.Item>
          <Form.Item name="reason" label={<span style={{ fontWeight: 600 }}>Nature of Emergency</span>}>
            <TextArea rows={2} placeholder="Briefly describe the emergency situation…" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════
   TAB 7 — PLANS
═══════════════════════════════════════════════════════════════ */
const Plans = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [viewPlan, setViewPlan] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['emergency-plans'],
    queryFn: () => apiService.get('/api/emergency/plans/'),
  });
  const plans = data?.data || [];

  const createM = useMutation({
    mutationFn: (body) => apiService.post('/api/emergency/plans/', body),
    onSuccess: () => { message.success('Emergency plan created'); qc.invalidateQueries(['emergency-plans']); setCreateOpen(false); form.resetFields(); },
    onError: (e) => message.error(e?.message || 'Create failed'),
  });

  const deleteM = useMutation({
    mutationFn: (id) => apiService.delete(`/api/emergency/plans/${id}`),
    onSuccess: () => { message.success('Plan removed'); qc.invalidateQueries(['emergency-plans']); },
    onError: (e) => message.error(e?.message || 'Delete failed'),
  });

  const planColors = [
    { from: '#cf1322', to: '#820014' },
    { from: '#d4380d', to: '#871400' },
    { from: '#d48806', to: '#874d00' },
    { from: '#531dab', to: '#22075e' },
    { from: '#096dd9', to: '#003a8c' },
    { from: '#389e0d', to: '#135200' },
  ];

  return (
    <div style={{ padding: '24px 28px' }}>
      <SectionHeader icon={<FileTextOutlined />} accent="#096dd9"
        title="Emergency Response Plans"
        subtitle="Documented procedures, contacts and step-by-step guides"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={refetch} loading={isLoading}>Refresh</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}
              style={{ background: 'linear-gradient(135deg,#096dd9,#003a8c)', border: 'none', borderRadius: 8, fontWeight: 700 }}>
              New Plan
            </Button>
          </Space>
        }
      />

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spin size="large" /></div>
      ) : plans.length === 0 ? (
        <div style={{ background: 'white', borderRadius: 16, padding: 56, textAlign: 'center', boxShadow: '0 2px 16px rgba(0,0,0,0.06)' }}>
          <FileTextOutlined style={{ fontSize: 52, color: '#d9d9d9', display: 'block', marginBottom: 14 }} />
          <div style={{ color: '#595959', fontSize: 16, fontWeight: 600 }}>No emergency plans yet</div>
          <div style={{ color: '#bfbfbf', fontSize: 13, marginTop: 6 }}>Create detailed response procedures for different emergency types</div>
          <Button type="primary" icon={<PlusOutlined />} style={{ marginTop: 20 }} onClick={() => setCreateOpen(true)}>
            Create First Plan
          </Button>
        </div>
      ) : (
        <Row gutter={[16, 16]}>
          {plans.map((p, i) => {
            const pal = planColors[i % planColors.length];
            const evtCfg = EVENT_TYPE_MAP[p.event_type];
            return (
              <Col key={p.id} xs={24} sm={12} md={8}>
                <div style={{
                  background: 'white', borderRadius: 16, overflow: 'hidden',
                  boxShadow: '0 2px 16px rgba(0,0,0,0.06)', border: '1px solid #f0f0f0',
                  cursor: 'pointer', transition: 'all 0.2s',
                }}
                  onClick={() => setViewPlan(p)}
                >
                  <div style={{
                    height: 6,
                    background: `linear-gradient(90deg, ${pal.from}, ${pal.to})`,
                  }} />
                  <div style={{ padding: '18px 18px 14px' }}>
                    <div style={{ fontWeight: 700, fontSize: 15, color: '#141414', marginBottom: 8 }}>{p.plan_name}</div>
                    <Space style={{ marginBottom: 12 }}>
                      {evtCfg ? <EventBadge type={p.event_type} /> : <Tag style={{ borderRadius: 8 }}>General</Tag>}
                    </Space>
                    <div style={{ fontSize: 12, color: '#8c8c8c', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {p.steps ? p.steps.substring(0, 100) + (p.steps.length > 100 ? '…' : '') : 'No steps defined.'}
                    </div>
                    <Divider style={{ margin: '12px 0' }} />
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontSize: 11, color: '#8c8c8c' }}>
                        <UserOutlined style={{ marginRight: 4 }} />{(p.contacts || []).length} contacts
                      </div>
                      <Space size={4} onClick={e => e.stopPropagation()}>
                        <Button size="small" icon={<EyeOutlined />} type="text" onClick={() => setViewPlan(p)} />
                        <Popconfirm title="Delete this plan?" okType="danger" onConfirm={() => deleteM.mutate(p.id)}>
                          <Button size="small" icon={<DeleteOutlined />} type="text" danger />
                        </Popconfirm>
                      </Space>
                    </div>
                  </div>
                </div>
              </Col>
            );
          })}
        </Row>
      )}

      {/* View Modal */}
      <Modal open={!!viewPlan}
        title={
          <Space>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg,#096dd9,#003a8c)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FileTextOutlined style={{ color: 'white', fontSize: 14 }} />
            </div>
            {viewPlan?.plan_name}
          </Space>
        }
        onCancel={() => setViewPlan(null)} footer={null} width={640}>
        {viewPlan && (
          <div>
            <Row gutter={12} style={{ marginBottom: 16 }}>
              <Col span={12}>
                <div style={{ background: '#f5f5f5', borderRadius: 8, padding: '10px 14px' }}>
                  <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 4 }}>Event Type</div>
                  {viewPlan.event_type != null ? <EventBadge type={viewPlan.event_type} /> : <Tag>General</Tag>}
                </div>
              </Col>
              <Col span={12}>
                <div style={{ background: '#f5f5f5', borderRadius: 8, padding: '10px 14px' }}>
                  <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 4 }}>Contacts</div>
                  <div style={{ fontWeight: 700 }}>{(viewPlan.contacts || []).length} emergency contacts</div>
                </div>
              </Col>
            </Row>
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10 }}>Procedure / Steps</div>
            <div style={{ background: '#fafafa', border: '1px solid #f0f0f0', borderRadius: 10, padding: 16, fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap', maxHeight: 280, overflow: 'auto' }}>
              {viewPlan.steps || 'No steps defined.'}
            </div>
            {(viewPlan.contacts || []).length > 0 && (
              <>
                <div style={{ fontWeight: 700, fontSize: 13, marginTop: 16, marginBottom: 10 }}>Emergency Contacts</div>
                {viewPlan.contacts.map((c, i) => (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '10px 14px', background: i % 2 ? '#fafafa' : 'white',
                    borderRadius: 8, border: '1px solid #f0f0f0', marginBottom: 6,
                  }}>
                    <Space>
                      <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg,#096dd9,#003a8c)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <UserOutlined style={{ color: 'white', fontSize: 13 }} />
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{c.name}</div>
                        <div style={{ fontSize: 11, color: '#8c8c8c' }}>{c.role}</div>
                      </div>
                    </Space>
                    <span style={{ fontSize: 12, fontFamily: 'monospace', color: '#096dd9', fontWeight: 600 }}>{c.phone}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </Modal>

      {/* Create Modal */}
      <Modal open={createOpen}
        title={
          <Space>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg,#096dd9,#003a8c)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <PlusOutlined style={{ color: 'white', fontSize: 13 }} />
            </div>
            New Emergency Plan
          </Space>
        }
        onCancel={() => { setCreateOpen(false); form.resetFields(); }}
        onOk={() => form.submit()} confirmLoading={createM.isPending} width={560}>
        <Form form={form} layout="vertical" onFinish={v => createM.mutate({ ...v, contacts: [] })}>
          <Form.Item name="plan_name" label={<span style={{ fontWeight: 600 }}>Plan Name</span>} rules={[{ required: true }]}>
            <Input size="large" placeholder="e.g. Platform A Fire Evacuation Procedure" />
          </Form.Item>
          <Form.Item name="event_type" label={<span style={{ fontWeight: 600 }}>Associated Emergency Type</span>}>
            <Select allowClear placeholder="Any / General" size="large">
              {Object.entries(EVENT_TYPE_MAP).map(([k, t]) => (
                <Option key={k} value={+k}><span style={{ color: t.color, fontWeight: 600 }}>{t.label}</span></Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="steps" label={<span style={{ fontWeight: 600 }}>Response Procedure</span>} rules={[{ required: true }]}>
            <TextArea rows={7} placeholder={'Step 1: Sound the alarm and alert all personnel\nStep 2: Activate fire suppression systems\nStep 3: Guide personnel to muster points\n...'} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════
   TAB 8 — AUDIT TRAIL
═══════════════════════════════════════════════════════════════ */
const AuditTrail = () => {
  const [range, setRange]     = useState(null);
  const [evtType, setEvtType] = useState(null);
  const [search, setSearch]   = useState('');
  const [applied, setApplied] = useState({});
  const [detail, setDetail]   = useState(null);

  const qParams = new URLSearchParams();
  qParams.append('limit', '100');
  if (applied.range?.[0]) qParams.append('start_time', applied.range[0]);
  if (applied.range?.[1]) qParams.append('end_time',   applied.range[1]);
  if (applied.evtType != null) qParams.append('event_type', applied.evtType);
  if (applied.search)  qParams.append('search', applied.search);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['em-audit', qParams.toString()],
    queryFn: () => apiService.get(`/api/emergency/audit/?${qParams}`),
  });
  const rows = data?.data || [];

  const exportCSV = () => {
    const hdr = ['Event ID','Type','Status','Start','End','Initiated By','Trigger','Reason','Scope'];
    const csv = [hdr, ...rows.map(r => [
      r.event_id, EVENT_TYPE_MAP[r.event_type]?.label || r.event_type,
      r.status_name, r.start_time, r.end_time || '',
      r.initiated_by || 'System', r.trigger_source || '', r.reason || '', r.scope,
    ])].map(row => row.join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    Object.assign(document.createElement('a'), { href: url, download: `em_audit_${new Date().toISOString().split('T')[0]}.csv` }).click();
    URL.revokeObjectURL(url);
  };

  const active    = rows.filter(r => r.status_name === 'ACTIVE').length;
  const resolved  = rows.filter(r => r.status_name === 'RESOLVED').length;
  const cancelled = rows.filter(r => r.status_name === 'CANCELLED').length;

  const durStr = (r) => {
    const ms = r.end_time ? new Date(r.end_time) - new Date(r.start_time) : r.start_time ? Date.now() - new Date(r.start_time) : 0;
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  };

  const cols = [
    { title: 'Start Time', dataIndex: 'start_time', width: 150, fixed: 'left',
      render: v => <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#595959' }}>{v ? new Date(v).toLocaleString() : '—'}</span> },
    { title: 'Type',   dataIndex: 'event_type', width: 130, render: v => <EventBadge type={v} /> },
    { title: 'Status', dataIndex: 'status_name', width: 115, render: v => <StatusBadge name={v} /> },
    { title: 'Initiated By', dataIndex: 'initiated_by', width: 130,
      render: v => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'linear-gradient(135deg,#096dd9,#003a8c)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <UserOutlined style={{ color: 'white', fontSize: 10 }} />
          </div>
          <span style={{ fontSize: 12, fontWeight: 500 }}>{v || 'System'}</span>
        </div>
      )},
    { title: 'Trigger', dataIndex: 'trigger_source', ellipsis: true, render: v => <span style={{ fontSize: 12 }}>{v || '—'}</span> },
    { title: 'Duration', key: 'dur', width: 100,
      render: (_, r) => <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#595959' }}>{durStr(r)}</span> },
    { title: '', key: 'action', width: 46,
      render: (_, r) => (
        <Tooltip title="View details">
          <Button size="small" type="text" icon={<EyeOutlined />}
            style={{ color: '#096dd9' }}
            onClick={() => setDetail(r)} />
        </Tooltip>
      )},
  ];

  return (
    <div style={{ padding: '24px 28px' }}>
      <SectionHeader icon={<AuditOutlined />} accent="#531dab"
        title="Audit Trail"
        subtitle="Complete immutable record of all emergency system activities"
        extra={
          <Space>
            <Button icon={<DownloadOutlined />} onClick={exportCSV}
              style={{ background: 'linear-gradient(135deg,#389e0d,#135200)', border: 'none', color: 'white', fontWeight: 700, borderRadius: 8 }}>
              Export CSV
            </Button>
            <Button icon={<ReloadOutlined />} onClick={refetch} loading={isLoading}>Refresh</Button>
          </Space>
        }
      />

      <Row gutter={16} style={{ marginBottom: 24 }}>
        {[
          { label: 'Total Records', value: rows.length, from: '#531dab', to: '#22075e' },
          { label: 'Active Now',    value: active,       from: '#cf1322', to: '#820014' },
          { label: 'Resolved',      value: resolved,     from: '#389e0d', to: '#135200' },
          { label: 'Cancelled',     value: cancelled,    from: '#595959', to: '#1f1f1f' },
        ].map(s => (
          <Col key={s.label} xs={12} sm={6}><GradStat {...s} /></Col>
        ))}
      </Row>

      {/* Filters */}
      <div style={{ background: 'white', borderRadius: 12, padding: '14px 18px', marginBottom: 16, boxShadow: '0 1px 8px rgba(0,0,0,0.04)', border: '1px solid #f0f0f0' }}>
        <Row gutter={[10, 10]} align="middle">
          <Col xs={24} sm={7}>
            <RangePicker showTime style={{ width: '100%' }} size="small"
              onChange={v => setRange(v ? [v[0], v[1]] : null)} />
          </Col>
          <Col xs={12} sm={4}>
            <Select allowClear placeholder="Event type" size="small" style={{ width: '100%' }} value={evtType} onChange={setEvtType}>
              {Object.entries(EVENT_TYPE_MAP).map(([k, t]) => (
                <Option key={k} value={+k}><span style={{ color: t.color, fontWeight: 600 }}>{t.label}</span></Option>
              ))}
            </Select>
          </Col>
          <Col xs={12} sm={4}>
            <Input placeholder="Search trigger / reason…" value={search} size="small"
              onChange={e => setSearch(e.target.value)} allowClear prefix={<span style={{ color: '#bfbfbf', fontSize: 10 }}>🔍</span>} />
          </Col>
          <Col>
            <Button type="primary" size="small" style={{ borderRadius: 6 }}
              onClick={() => setApplied({ range: range ? [range[0].toISOString(), range[1].toISOString()] : null, evtType, search })}>
              Apply
            </Button>
          </Col>
          <Col>
            <Button size="small" icon={<CloseCircleOutlined />} style={{ borderRadius: 6 }}
              onClick={() => { setRange(null); setEvtType(null); setSearch(''); setApplied({}); }}>
              Clear
            </Button>
          </Col>
        </Row>
      </div>

      <div style={{ background: 'white', borderRadius: 16, overflow: 'hidden', boxShadow: '0 2px 16px rgba(0,0,0,0.06)', border: '1px solid #f0f0f0' }}>
        <Table columns={cols} dataSource={rows} rowKey={(r, i) => r.event_id ?? i}
          loading={isLoading} size="small" pagination={{ pageSize: 20, showTotal: (t, r) => `${r[0]}–${r[1]} of ${t}` }}
          scroll={{ x: 900 }}
          rowClassName={r => r.status_name === 'ACTIVE' ? 'em-row-active' : ''}
        />
      </div>

      {/* Detail Modal */}
      <Modal open={!!detail}
        title={
          <Space>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg,#531dab,#22075e)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <AuditOutlined style={{ color: 'white', fontSize: 14 }} />
            </div>
            Emergency Event Detail
          </Space>
        }
        onCancel={() => setDetail(null)} footer={null} width={680}>
        {detail && (
          <div>
            <Row gutter={12} style={{ marginBottom: 16 }}>
              {[
                { label: 'Event ID', value: detail.event_id },
                { label: 'Type', value: <EventBadge type={detail.event_type} /> },
                { label: 'Status', value: <StatusBadge name={detail.status_name} /> },
                { label: 'Scope', value: <Tag style={{ borderRadius: 8 }}>{detail.scope}</Tag> },
                { label: 'Start', value: detail.start_time ? new Date(detail.start_time).toLocaleString() : '—' },
                { label: 'End', value: detail.end_time ? new Date(detail.end_time).toLocaleString() : <span style={{ color: '#cf1322', fontWeight: 600 }}>Still Active</span> },
                { label: 'Duration', value: durStr(detail) },
                { label: 'Initiated By', value: detail.initiated_by || 'System' },
              ].map((f, i) => (
                <Col key={i} span={12} style={{ marginBottom: 10 }}>
                  <div style={{ background: '#fafafa', borderRadius: 8, padding: '8px 12px' }}>
                    <div style={{ fontSize: 10, color: '#8c8c8c', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{f.label}</div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{f.value}</div>
                  </div>
                </Col>
              ))}
            </Row>

            {detail.reason && (
              <div style={{ background: '#f5f5f5', borderRadius: 10, padding: '10px 14px', marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 4 }}>REASON</div>
                <div style={{ fontSize: 13, color: '#141414' }}>{detail.reason}</div>
              </div>
            )}

            {detail.trigger_source && (
              <div style={{ background: '#f5f5f5', borderRadius: 10, padding: '10px 14px', marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 4 }}>TRIGGER SOURCE</div>
                <div style={{ fontSize: 13 }}>{detail.trigger_source}</div>
              </div>
            )}

            {(detail.actions || []).length > 0 && (
              <>
                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10 }}>Actions Executed</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 220, overflow: 'auto' }}>
                  {detail.actions.map((a, i) => (
                    <div key={i} style={{ background: '#fafafa', border: '1px solid #f0f0f0', borderRadius: 10, padding: '10px 14px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <Tag style={{ borderRadius: 8, fontWeight: 700 }}>{a.type}</Tag>
                        <span style={{ fontSize: 11, color: '#8c8c8c' }}>{a.timestamp ? new Date(a.timestamp).toLocaleString() : ''}</span>
                      </div>
                      {a.action && <div style={{ fontSize: 12 }}><b>Action:</b> {a.action}</div>}
                      {a.doors && <div style={{ fontSize: 12 }}><b>Doors:</b> {JSON.stringify(a.doors)}</div>}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════
   ROOT COMPONENT
═══════════════════════════════════════════════════════════════ */
const EmergencyManagement = ({ embedded = false }) => {
  const [wsStatus, setWsStatus] = useState('disconnected');
  const wsRef = useRef(null);

  const { data: statusData, isLoading, refetch } = useQuery({
    queryKey: ['emergency-status'],
    queryFn: () => apiService.get('/api/emergency/status/'),
    refetchInterval: 30000,
  });
  const d = statusData?.data || {};
  const isEmergency = d.system_status === 'EMERGENCY';

  useEffect(() => {
    const token = localStorage.getItem('token') || '';
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${window.location.host}/api/emergency/ws/emergency/?token=${token}`);
    wsRef.current = ws;
    ws.onopen  = () => setWsStatus('connected');
    ws.onclose = () => setWsStatus('disconnected');
    ws.onerror = () => setWsStatus('error');
    return () => { ws.close(); wsRef.current = null; };
  }, []);

  const wsColor = wsStatus === 'connected' ? '#52c41a' : wsStatus === 'error' ? '#f5222d' : '#8c8c8c';

  const tabItems = [
    { key: 'dashboard',      label: <span><AlertOutlined style={{ marginRight: 6 }} />Dashboard</span>,     children: <Dashboard statusData={d} isLoading={isLoading} refetch={refetch} /> },
    { key: 'lockdown',       label: <span><LockOutlined style={{ marginRight: 6 }} />Lockdown</span>,       children: <Lockdown /> },
    { key: 'fire-mode',      label: <span><FireOutlined style={{ marginRight: 6 }} />Fire Mode</span>,      children: <FireMode /> },
    { key: 'notifications',  label: <span><BellOutlined style={{ marginRight: 6 }} />Notifications</span>,  children: <Notifications /> },
    { key: 'devices',        label: <span><ApiOutlined style={{ marginRight: 6 }} />Devices</span>,         children: <Devices /> },
    { key: 'triggers',       label: <span><ThunderboltOutlined style={{ marginRight: 6 }} />Triggers</span>, children: <Triggers /> },
    { key: 'plans',          label: <span><FileTextOutlined style={{ marginRight: 6 }} />Plans</span>,      children: <Plans /> },
    { key: 'audit',          label: <span><AuditOutlined style={{ marginRight: 6 }} />Audit Trail</span>,   children: <AuditTrail /> },
  ];

  return (
    <div className={embedded ? undefined : 'emergency-module'}>
      <Card
        title={!embedded ? (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', overflow: 'visible' }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>Emergency Management</div>
              <div style={{ fontSize: 12, color: '#64748b', fontWeight: 400, marginTop: 2 }}>
                Real-time emergency response, lockdown and incident control
              </div>
            </div>
            <Space size="middle" style={{ overflow: 'visible' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 10px', borderRadius: 8, background: isEmergency ? '#fff1f0' : '#f6ffed', border: `1px solid ${isEmergency ? '#ffa39e' : '#b7eb8f'}` }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: isEmergency ? '#ff4d4f' : '#52c41a', animation: isEmergency ? 'emDotPulse 1s infinite' : 'none' }} />
                <span style={{ fontSize: 11, fontWeight: 700, color: isEmergency ? '#cf1322' : '#389e0d' }}>{d.system_status || 'NORMAL'}</span>
              </div>
              {(d.total_emergencies || 0) > 0 && (
                <Badge count={d.total_emergencies} color="#cf1322">
                  <WarningOutlined style={{ fontSize: 16 }} />
                </Badge>
              )}
              <Tooltip title={`WebSocket: ${wsStatus}`}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: wsColor, animation: wsStatus === 'connected' ? 'emDotPulse 2s infinite' : 'none' }} />
                  <span style={{ fontSize: 11, color: '#64748b' }}>{wsStatus === 'connected' ? 'Live' : wsStatus === 'error' ? 'Error' : 'Offline'}</span>
                </div>
              </Tooltip>
              <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading} size="small">Refresh</Button>
            </Space>
          </div>
        ) : undefined}
        bordered={!embedded}
        styles={!embedded ? { header: { overflow: 'visible' } } : { body: { padding: 0 } }}
      >
        <Tabs
          items={tabItems}
          className="em-tabs-light"
          size="middle"
          tabBarStyle={{ marginBottom: 0 }}
        />
      </Card>

      <style>{`
        .em-tabs-light .ant-tabs-nav { background: transparent !important; }
        .em-tabs-light .ant-tabs-nav::before { border-color: #f0f0f0 !important; }
        .em-tabs-light .ant-tabs-tab { color: rgba(0,0,0,0.45) !important; font-weight: 500 !important; padding: 10px 16px !important; margin: 0 1px !important; border-radius: 8px 8px 0 0 !important; transition: all 0.2s !important; }
        .em-tabs-light .ant-tabs-tab:hover { color: rgba(0,0,0,0.75) !important; background: rgba(0,0,0,0.03) !important; }
        .em-tabs-light .ant-tabs-tab-active { color: #cf1322 !important; background: rgba(207,19,34,0.04) !important; font-weight: 700 !important; }
        .em-tabs-light .ant-tabs-tab-active .ant-tabs-tab-btn { color: #cf1322 !important; }
        .em-tabs-light .ant-tabs-ink-bar { background: #cf1322 !important; height: 3px !important; border-radius: 2px 2px 0 0 !important; }
        .em-row-active td { background: rgba(207,19,34,0.03) !important; }
        .em-row-active:hover td { background: rgba(207,19,34,0.07) !important; }
        @keyframes emDotPulse {
          0%,100% { opacity: 1; transform: scale(1); }
          50%      { opacity: 0.6; transform: scale(1.3); }
        }
      `}</style>
    </div>
  );
};

export default EmergencyManagement;
