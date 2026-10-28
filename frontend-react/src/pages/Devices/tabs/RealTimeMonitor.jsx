import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Card, Row, Col, Tag, Button, Space, Badge, Tooltip, Drawer, message,
  Statistic, Alert, Typography, Switch, Select, Input, Table, Divider,
} from 'antd';
import {
  WifiOutlined, DisconnectOutlined, ThunderboltOutlined, EyeOutlined,
  ReloadOutlined, PlayCircleOutlined, PauseCircleOutlined, AlertOutlined,
  SearchOutlined, UserOutlined, FullscreenOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import deviceAPI from '../../../services/deviceAPI';

dayjs.extend(relativeTime);

const { Text } = Typography;

// punch_state_label and verify_type_label come pre-built from the backend
const PUNCH_COLORS = { 0: '#52c41a', 1: '#1890ff', 2: '#fa8c16', 3: '#13c2c2', 4: '#722ed1', 5: '#eb2f96' };

const getDeviceTypeName = t => ({ 0: 'Attendance', 1: 'Access Control', 2: 'Mustering', 3: 'Emergency' }[t] ?? 'Unknown');
const getDeviceTypeColor = t => ({ 0: '#1890ff', 1: '#52c41a', 2: '#faad14', 3: '#ff4d4f' }[t] ?? '#d9d9d9');
// Today's taps show the time; older ones the date too (a 15 Oct tap must not look like today's).
const fmtTime = dt => !dt ? '—' : (dayjs(dt).isSame(dayjs(), 'day') ? dayjs(dt).format('HH:mm:ss') : dayjs(dt).format('DD MMM HH:mm:ss'));
const fmtDt   = dt => dt ? dayjs(dt).format('DD MMM HH:mm') : 'Never';

// ─── Live Transaction Feed ────────────────────────────────────────────────────

const LiveFeed = ({ terminals }) => {
  const [snFilter, setSnFilter]  = useState(null);
  const [paused, setPaused]      = useState(false);
  const [limit, setLimit]        = useState(50);

  const terminalOptions = (terminals ?? []).map(t => ({ value: t.sn, label: t.alias || t.sn }));

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['live-transactions', snFilter, limit],
    queryFn: () => deviceAPI.getLiveTransactions({ ...(snFilter && { terminal_sn: snFilter }), limit }),
    staleTime: 0,
    refetchInterval: paused ? false : 8000,
  });

  const punches = data?.data ?? [];

  const columns = [
    {
      title: 'Time',
      dataIndex: 'punch_time',
      width: 150,
      render: v => <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{fmtTime(v)}</span>,
    },
    {
      title: 'Employee',
      dataIndex: 'emp_name',
      ellipsis: true,
      render: (v, r) => (
        <Space size={4}>
          <UserOutlined style={{ color: '#8c8c8c', fontSize: 11 }} />
          <span style={{ fontWeight: 600, fontSize: 13 }}>{v}</span>
          <span style={{ color: '#bfbfbf', fontSize: 11 }}>({r.emp_code})</span>
        </Space>
      ),
    },
    {
      title: 'State',
      dataIndex: 'punch_state',
      width: 110,
      render: (v, r) => (
        <Tag color={PUNCH_COLORS[v] ?? '#d9d9d9'} style={{ fontWeight: 600 }}>
          {r.punch_state_label ?? `State ${v}`}
        </Tag>
      ),
    },
    {
      title: 'Verify',
      dataIndex: 'verify_type',
      width: 90,
      render: (v, r) => <Tag style={{ fontSize: 11 }}>{r.verify_type_label ?? `V${v}`}</Tag>,
    },
    {
      title: 'Device',
      dataIndex: 'device_alias',
      width: 140,
      render: (v, r) => <span style={{ fontSize: 12 }}>{v || r.terminal_sn}</span>,
    },
    {
      title: 'Area',
      dataIndex: 'area_alias',
      width: 120,
      render: v => v ? <span style={{ fontSize: 11, color: '#595959' }}>{v}</span> : <span style={{ color: '#d9d9d9' }}>—</span>,
    },
  ];

  return (
    <Card
      size="small"
      title={
        <Space>
          <span style={{ fontWeight: 700 }}>Live Punch Feed</span>
          <Badge status={paused ? 'default' : 'processing'} text={paused ? 'Paused' : 'Live'} />
        </Space>
      }
      extra={
        <Space>
          <Select
            allowClear placeholder="All devices" options={terminalOptions}
            value={snFilter} onChange={setSnFilter} style={{ width: 160 }} size="small"
          />
          <Select
            value={limit}
            onChange={setLimit}
            size="small"
            style={{ width: 80 }}
            options={[{ value: 20, label: '20' }, { value: 50, label: '50' }, { value: 100, label: '100' }]}
          />
          <Tooltip title={paused ? 'Resume auto-refresh' : 'Pause auto-refresh'}>
            <Button size="small" icon={paused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
              onClick={() => setPaused(p => !p)} type={paused ? 'primary' : 'default'} />
          </Tooltip>
          <Button size="small" icon={<ReloadOutlined />} onClick={refetch} loading={isLoading} />
        </Space>
      }
    >
      <Table
        dataSource={punches}
        columns={columns}
        rowKey="id"
        size="small"
        loading={isLoading}
        pagination={false}
        scroll={{ y: 300, x: 600 }}
        rowClassName={r => r.punch_state === 0 ? 'feed-checkin' : r.punch_state === 1 ? 'feed-checkout' : ''}
      />
    </Card>
  );
};

// ─── Device Grid ──────────────────────────────────────────────────────────────

const DeviceCard = ({ device, onClick }) => {
  const isOnline = device.status === 'online';
  const isEmergency = device.device_type === 3;
  const emergencyOn = device.emergency_status === 'on' || device.emergency_status === 'active';

  return (
    <Card
      size="small"
      hoverable
      onClick={() => onClick(device)}
      style={{
        borderLeft: `4px solid ${getDeviceTypeColor(device.device_type)}`,
        cursor: 'pointer',
        transition: 'all 0.3s',
        boxShadow: emergencyOn ? '0 0 0 2px #ff4d4f' : undefined,
        animation: emergencyOn ? 'pulse 2s infinite' : undefined,
      }}
      bodyStyle={{ padding: 10 }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <Badge status={isOnline ? 'success' : 'error'} />
            <Text strong style={{ fontSize: 13 }} ellipsis>{device.alias || device.sn}</Text>
            {isEmergency && emergencyOn && <AlertOutlined style={{ color: '#ff4d4f' }} />}
          </div>
          <div style={{ fontSize: 11, color: '#8c8c8c' }}>{device.sn}</div>
          <div style={{ fontSize: 11, color: '#bfbfbf', marginBottom: 6 }}>
            {device.ip_address} · {getDeviceTypeName(device.device_type)}
          </div>
          <Space size={4} wrap>
            <Tag size="small" color={isOnline ? 'success' : 'default'} style={{ fontSize: 11 }}>
              {isOnline ? 'Online' : 'Offline'}
            </Tag>
            {device.user_count > 0 && <Tag size="small" color="blue" style={{ fontSize: 11 }}>{device.user_count} Users</Tag>}
            {(device.pending_commands ?? 0) > 0 && (
              <Tag size="small" color="orange" style={{ fontSize: 11 }}>{device.pending_commands} Cmd</Tag>
            )}
          </Space>
          {device.last_activity && (
            <div style={{ fontSize: 10, color: '#bfbfbf', marginTop: 4 }}>
              Last: {fmtDt(device.last_activity)}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};

// ─── Main Component ───────────────────────────────────────────────────────────

const RealTimeMonitor = () => {
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [drawerOpen, setDrawerOpen]         = useState(false);
  const [paused, setPaused]                 = useState(false);
  const [searchTerm, setSearchTerm]         = useState('');
  const [typeFilter, setTypeFilter]         = useState(null);
  const [offlineOnly, setOfflineOnly]       = useState(false);
  const wsRef                               = useRef(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['realtime-devices'],
    queryFn: () => deviceAPI.getRealTimeDevices(),
    staleTime: 0,
    refetchInterval: paused ? false : 15000,
  });

  const devices = data?.devices ?? [];
  const terminals = useMemo(() => devices.map(d => ({ sn: d.sn, alias: d.alias })), [devices]);

  const stats = useMemo(() => ({
    total:   devices.length,
    online:  devices.filter(d => d.status === 'online').length,
    offline: devices.filter(d => d.status === 'offline').length,
    pending: devices.reduce((s, d) => s + (d.pending_commands ?? 0), 0),
  }), [devices]);

  const filteredDevices = useMemo(() => {
    let out = devices;
    if (searchTerm) out = out.filter(d =>
      d.sn.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.alias?.toLowerCase().includes(searchTerm.toLowerCase())
    );
    if (typeFilter !== null) out = out.filter(d => d.device_type === typeFilter);
    if (offlineOnly) out = out.filter(d => d.status === 'offline');
    return out;
  }, [devices, searchTerm, typeFilter, offlineOnly]);

  const handleEmergencyToggle = async (device, action, e) => {
    e.stopPropagation();
    try {
      await deviceAPI.emergencyCommand(device.sn, action);
      message.success(`Emergency ${action} sent to ${device.alias || device.sn}`);
      refetch();
    } catch (err) {
      message.error(err.message);
    }
  };

  const openDeviceDrawer = d => { setSelectedDevice(d); setDrawerOpen(true); };

  return (
    <div>
      {/* Stats Bar */}
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col span={6}><Card size="small"><Statistic title="Total Devices" value={stats.total} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="Online" value={stats.online} valueStyle={{ color: '#52c41a' }} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="Offline" value={stats.offline} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="Pending Commands" value={stats.pending} valueStyle={{ color: '#fa8c16' }} /></Card></Col>
      </Row>

      {/* Filters */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Row gutter={12} align="middle">
          <Col flex="auto">
            <Space wrap>
              <Input
                prefix={<SearchOutlined />}
                placeholder="Search device…"
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                style={{ width: 200 }}
                allowClear
              />
              <Select
                allowClear placeholder="Type"
                options={[
                  { value: 0, label: 'Attendance' }, { value: 1, label: 'Access Control' },
                  { value: 2, label: 'Mustering' },  { value: 3, label: 'Emergency' },
                ]}
                value={typeFilter} onChange={setTypeFilter} style={{ width: 150 }}
              />
              <Space size={6}>
                <Switch size="small" checked={offlineOnly} onChange={setOfflineOnly} />
                <span style={{ fontSize: 12 }}>Offline only</span>
              </Space>
            </Space>
          </Col>
          <Col>
            <Space>
              <Tooltip title={paused ? 'Resume' : 'Pause'}>
                <Button size="small" icon={paused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
                  onClick={() => setPaused(p => !p)} type={paused ? 'primary' : 'default'} />
              </Tooltip>
              <Button size="small" icon={<ReloadOutlined />} onClick={refetch} loading={isLoading}>Refresh</Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* Device Grid */}
      <Card size="small" loading={isLoading} style={{ marginBottom: 16 }}
        title={<span>{filteredDevices.length} devices{searchTerm || typeFilter || offlineOnly ? ' (filtered)' : ''}</span>}>
        {filteredDevices.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#bfbfbf' }}>No devices found</div>
        ) : (
          <Row gutter={[12, 12]}>
            {filteredDevices.map(d => (
              <Col key={d.sn} xs={24} sm={12} md={8} lg={6} xl={4}>
                <DeviceCard device={d} onClick={openDeviceDrawer} />
              </Col>
            ))}
          </Row>
        )}
      </Card>

      {/* Live Punch Feed */}
      <LiveFeed terminals={terminals} />

      {/* Device Detail Drawer */}
      <Drawer
        title={selectedDevice ? `${selectedDevice.alias || selectedDevice.sn}` : 'Device Detail'}
        placement="right"
        width={480}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        destroyOnHidden
      >
        {selectedDevice && (
          <div>
            <Card size="small" style={{ marginBottom: 12 }}>
              <Row gutter={12}>
                <Col span={12}>
                  <div><strong>SN:</strong> {selectedDevice.sn}</div>
                  <div><strong>IP:</strong> {selectedDevice.ip_address}</div>
                  <div><strong>Type:</strong> {getDeviceTypeName(selectedDevice.device_type)}</div>
                </Col>
                <Col span={12}>
                  <div>
                    <strong>Status:</strong>&nbsp;
                    <Badge status={selectedDevice.status === 'online' ? 'success' : 'error'} text={selectedDevice.status} />
                  </div>
                  <div><strong>Firmware:</strong> {selectedDevice.fw_version || '—'}</div>
                  <div><strong>Last Activity:</strong> {fmtDt(selectedDevice.last_activity)}</div>
                </Col>
              </Row>
            </Card>

            <Row gutter={12} style={{ marginBottom: 12 }}>
              <Col span={8}><Card size="small"><Statistic title="Users" value={selectedDevice.user_count ?? 0} /></Card></Col>
              <Col span={8}><Card size="small"><Statistic title="FP" value={selectedDevice.fp_count ?? 0} /></Card></Col>
              <Col span={8}><Card size="small"><Statistic title="Face" value={selectedDevice.face_count ?? 0} /></Card></Col>
            </Row>

            {selectedDevice.device_type === 3 && (
              <Card size="small" title="Emergency Controls">
                <Space>
                  <Button type="primary" danger onClick={e => handleEmergencyToggle(selectedDevice, 'ON', e)}>
                    <ThunderboltOutlined /> Activate Siren
                  </Button>
                  <Button onClick={e => handleEmergencyToggle(selectedDevice, 'OFF', e)}>
                    Deactivate Siren
                  </Button>
                </Space>
              </Card>
            )}
          </div>
        )}
      </Drawer>

      <style>{`
        @keyframes pulse {
          0%   { box-shadow: 0 0 0 0 rgba(255,77,79,.7); }
          70%  { box-shadow: 0 0 0 8px rgba(255,77,79,0); }
          100% { box-shadow: 0 0 0 0 rgba(255,77,79,0); }
        }
        .feed-checkin  td { background: #f6ffed !important; }
        .feed-checkout td { background: #e6f7ff !important; }
      `}</style>
    </div>
  );
};

export default RealTimeMonitor;
