import React, { useState } from 'react';
import { Tabs, Card, Button, Space, Badge, message } from 'antd';
import {
  AppstoreOutlined, DatabaseOutlined, ThunderboltOutlined,
  MonitorOutlined, SettingOutlined,
  WifiOutlined, ReloadOutlined, SafetyOutlined, ToolOutlined,
  CalendarOutlined, BarChartOutlined, SyncOutlined,
} from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import DeviceList         from './tabs/DeviceList';
import AreaManagement     from './tabs/AreaManagement';
import DeviceCommands     from './tabs/DeviceCommands';
import RealTimeMonitor    from './tabs/RealTimeMonitor';
import AutoRegisterSettings from './tabs/AutoRegisterSettings';
import BiometricEnrollment  from './tabs/BiometricEnrollment';
import DeviceSchedules      from './tabs/DeviceSchedules';
import MaintenanceTracking  from './tabs/MaintenanceTracking';
import BiotimeAnalytics     from './tabs/BiotimeAnalytics';
import TemplateSyncTab      from './tabs/TemplateSyncTab';

import deviceAPI from '../../services/deviceAPI';

const Device = () => {
  const qc = useQueryClient();
  const [activeTab, setActiveTab]           = useState('1');
  const [autoRegisterEnabled, setAutoReg]   = useState(true);

  // Central terminal list — shared across tabs
  const { data: termData, isLoading: termLoading, refetch: refetchTerms } = useQuery({
    queryKey: ['device-terminals'],
    queryFn:  () => deviceAPI.getTerminals(),
    staleTime: 60000,
  });
  const terminals = Array.isArray(termData) ? termData : (termData?.data ?? termData?.terminals ?? []);

  // Health / badge stats
  const { data: healthData, refetch: refetchHealth } = useQuery({
    queryKey: ['device-health'],
    queryFn:  () => deviceAPI.getHealth(),
    staleTime: 30000,
    retry: false,
  });

  const deviceStats = {
    total:    healthData?.total_devices    ?? terminals.length,
    online:   healthData?.online_devices   ?? 0,
    offline:  healthData?.offline_devices  ?? 0,
    pending:  healthData?.pending_commands ?? 0,
  };

  const refresh = () => {
    refetchTerms();
    refetchHealth();
    qc.invalidateQueries({ queryKey: ['realtime-devices'] });
    qc.invalidateQueries({ queryKey: ['device-commands'] });
  };

  const renderBadge = (count, color = 'blue') =>
    count > 0 ? <Badge count={count} size="small" style={{ backgroundColor: color, marginLeft: 4 }} /> : null;

  const tabItems = [
    {
      key: '1',
      label: <span><AppstoreOutlined />Devices{renderBadge(deviceStats.total)}</span>,
      children: <DeviceList onDeviceSelect={() => {}} refreshTrigger={activeTab === '1'} />,
    },
    {
      key: '2',
      label: <span><DatabaseOutlined />Areas</span>,
      children: <AreaManagement />,
    },
    {
      key: '3',
      label: <span><ThunderboltOutlined />Commands{renderBadge(deviceStats.pending, '#fa8c16')}</span>,
      children: <DeviceCommands />,
    },
    {
      key: '4',
      label: <span><MonitorOutlined />Real-time Monitor</span>,
      children: <RealTimeMonitor />,
    },
    {
      key: '5',
      label: <span><SafetyOutlined />Biometric Enrollment</span>,
      children: <BiometricEnrollment terminals={terminals} />,
    },
    {
      key: '7',
      label: <span><CalendarOutlined />Schedules</span>,
      children: <DeviceSchedules terminals={terminals} />,
    },
    {
      key: '8',
      label: (
        <span>
          <ToolOutlined />Maintenance
          {renderBadge(
            (termData?.data ?? []).length > 0 ? undefined : undefined,
            '#ff4d4f'
          )}
        </span>
      ),
      children: <MaintenanceTracking terminals={terminals} />,
    },
    {
      key: '10',
      label: (
        <span>
          <SettingOutlined />Auto-Register
          {autoRegisterEnabled && renderBadge(1, '#52c41a')}
        </span>
      ),
      children: <AutoRegisterSettings onSettingsChange={setAutoReg} />,
    },
    {
      key: '11',
      label: <span><BarChartOutlined />Analytics</span>,
      children: <BiotimeAnalytics />,
    },
    {
      key: '12',
      label: <span><SyncOutlined />Template Sync</span>,
      children: <TemplateSyncTab terminals={terminals} />,
    },
  ];

  return (
    <div className="device-module">
      <Card
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', overflow: 'visible' }}>
            <span style={{ fontWeight: 700, fontSize: 16 }}>Device Management</span>
            <Space size="middle" style={{ overflow: 'visible' }}>
              <Badge count={deviceStats.online} showZero color="#52c41a">
                <WifiOutlined style={{ fontSize: 16 }} />
              </Badge>
              <Badge count={deviceStats.offline} showZero color="#ff4d4f">
                <WifiOutlined style={{ fontSize: 16, color: '#ff4d4f' }} />
              </Badge>
              <Badge count={deviceStats.pending} showZero color="#fa8c16">
                <ThunderboltOutlined style={{ fontSize: 16 }} />
              </Badge>
              <Button icon={<ReloadOutlined />} onClick={refresh} size="small">
                Refresh
              </Button>
            </Space>
          </div>
        }
        styles={{ header: { overflow: 'visible' } }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          size="small"
          items={tabItems}
          tabBarStyle={{ overflow: 'visible', paddingTop: 6 }}
        />
      </Card>
    </div>
  );
};

export default Device;
