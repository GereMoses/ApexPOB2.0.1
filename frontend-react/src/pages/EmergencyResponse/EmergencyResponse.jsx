import React, { useState, useEffect, useRef } from 'react';
import { Space, Button, Tooltip, Card, Badge, Tabs } from 'antd';
import { DesktopOutlined,
  AlertOutlined, TeamOutlined, ReloadOutlined, WarningOutlined,
} from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import apiService from '../../services/api';
import EmergencyManagement from '../Emergency/EmergencyManagement';
import MusteringManagement from '../Mustering/MusteringManagement';

/* ─── Root component ─────────────────────────────────────────── */
const EmergencyResponse = () => {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [section, setSection] = useState('emergency');
  const [startRequest, setStartRequest] = useState(0);   // bumped → Personnel Accountability opens Start Muster
  useEffect(() => {
    const go = () => { setSection('mustering'); setStartRequest(n => n + 1); };
    window.addEventListener('apexpob:start-muster', go);
    return () => window.removeEventListener('apexpob:start-muster', go);
  }, []);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const wsRef = useRef(null);

  const { data: statusData, isLoading, refetch: refetchEmergency } = useQuery({
    queryKey: ['emergency-status'],
    queryFn:  () => apiService.get('/api/emergency/status/'),
    refetchInterval: 30000,
  });
  const d = statusData?.data || {};
  const isEmergency = d.system_status === 'EMERGENCY';

  const { data: musterRaw, refetch: refetchMuster } = useQuery({
    queryKey: ['muster-active'],
    queryFn:  () => apiService.get('/api/mustering/events/?status=0'),
    refetchInterval: 15000,
  });
  const activeEvents = Array.isArray(musterRaw?.data) ? musterRaw.data : [];
  const missingTotal = activeEvents.reduce((s, e) => s + (e.total_missing ?? 0), 0);
  const wsColor = wsStatus === 'connected' ? '#52c41a' : wsStatus === 'error' ? '#f5222d' : '#8c8c8c';

  useEffect(() => {
    const token = localStorage.getItem('token') || '';
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${window.location.host}/api/emergency/ws/emergency/?token=${token}`);
    wsRef.current = ws;
    ws.onopen  = () => setWsStatus('connected');
    ws.onclose = () => setWsStatus('disconnected');
    ws.onerror = () => setWsStatus('error');
    ws.onmessage = () => {
      qc.invalidateQueries(['emergency-status']);
      qc.invalidateQueries(['muster-active']);
    };
    return () => { ws.close(); wsRef.current = null; };
  }, []); // eslint-disable-line

  const handleRefresh = () => {
    refetchEmergency();
    refetchMuster();
    qc.invalidateQueries(['muster-zones']);
    qc.invalidateQueries(['muster-events']);
  };

  return (
    <div className="emergency-response-module">
      <Card
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', overflow: 'visible' }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>Emergency &amp; Mustering</div>
              <div style={{ fontSize: 12, color: '#94a3b8', fontWeight: 400, marginTop: 1 }}>
                Integrated response command &amp; personnel accountability
              </div>
            </div>
            <Space size={16} style={{ overflow: 'visible' }}>
              <Space size={12} split={<span style={{ color: '#e2e8f0' }}>|</span>} style={{ fontSize: 11, color: '#94a3b8' }}>
                <span style={{ color: isEmergency ? '#dc2626' : '#94a3b8', fontWeight: isEmergency ? 600 : 400 }}>
                  {isEmergency ? '⚠ EMERGENCY' : 'Normal'}
                </span>
                {activeEvents.length > 0 && (
                  <span style={{ color: missingTotal > 0 ? '#dc2626' : '#64748b' }}>
                    {activeEvents.length} muster{activeEvents.length !== 1 ? 's' : ''}
                    {missingTotal > 0 ? ` · ${missingTotal} missing` : ''}
                  </span>
                )}
                <Tooltip title={`WebSocket: ${wsStatus}`}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: wsColor, display: 'inline-block', flexShrink: 0 }} />
                    {wsStatus === 'connected' ? 'Live' : wsStatus === 'error' ? 'Error' : 'Offline'}
                  </span>
                </Tooltip>
              </Space>
<Button type="primary" danger={activeEvents.length > 0} size="small" icon={<DesktopOutlined />}
                onClick={() => navigate('/mustering/board')}>
                Live muster board
              </Button>
              <Button icon={<ReloadOutlined />} size="small" onClick={handleRefresh} loading={isLoading}>
                Refresh
              </Button>
            </Space>
          </div>
        }
        styles={{ header: { overflow: 'visible' }, body: { padding: 0 } }}
      >
        <Tabs
          activeKey={section}
          onChange={setSection}
          size="middle"
          style={{ paddingLeft: 24, paddingRight: 24 }}
          items={[
            {
              key: 'emergency',
              label: (
                <Space size={5}>
                  <AlertOutlined />
                  Emergency Response
                  {isEmergency && <Badge dot color="#dc2626" />}
                </Space>
              ),
              children: <EmergencyManagement embedded />,
            },
            {
              key: 'mustering',
              label: (
                <Space size={5}>
                  <TeamOutlined />
                  Personnel Accountability
                  {activeEvents.length > 0 && <Badge count={activeEvents.length} size="small" color={missingTotal > 0 ? '#dc2626' : '#64748b'} />}
                </Space>
              ),
              children: <MusteringManagement embedded startRequest={startRequest} />,
            },
          ]}
        />
      </Card>
    </div>
  );
};

export default EmergencyResponse;
