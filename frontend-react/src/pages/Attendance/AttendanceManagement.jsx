import React, { useState } from 'react';
import dayjs from 'dayjs';
import { Tabs, Card, App, Space, Badge } from 'antd';
import {
  ClockCircleOutlined, ExceptionOutlined,
  SettingOutlined, UserAddOutlined, HistoryOutlined,
  BarChartOutlined, LineChartOutlined, CarryOutOutlined,
  ThunderboltOutlined, GiftOutlined, TagsOutlined, RetweetOutlined,
  EditOutlined, SafetyCertificateOutlined, EnvironmentOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import apiService from '../../services/api';
import { usePunchStream } from '../../hooks/usePunchStream';

import TimetablesTab    from './tabs/TimetablesTab';
import ShiftsTab        from './tabs/ShiftsTab';
import SchedulesTab     from './tabs/SchedulesTab';
import HolidaysTab      from './tabs/HolidaysTab';
import LeaveTypesTab    from './tabs/LeaveTypesTab';
import LeavesTab        from './tabs/LeavesTab';
import OvertimeRulesTab from './tabs/OvertimeRulesTab';
import OvertimeTab      from './tabs/OvertimeTab';
import ManualLogsTab    from './tabs/ManualLogsTab';
import TransactionsTab    from './tabs/TransactionsTab';
import TimesheetTab       from './tabs/TimesheetTab';
import ExceptionsTab      from './tabs/ExceptionsTab';
import RulesTab           from './tabs/RulesTab';
import AnalyticsTab              from './tabs/AnalyticsTab';
import AreaAttendanceTab         from './tabs/AreaAttendanceTab';
import ContractorAttendanceTab   from './tabs/ContractorAttendanceTab';

const AttendanceManagement = () => {
  const { message } = App.useApp();
  const [activeTab, setActiveTab] = useState('transactions');

  // Real-time punch stream — invalidates query cache the instant a punch arrives
  usePunchStream();

  const { data: statsData } = useQuery({
    queryKey: ['attendance-dashboard-stats'],
    queryFn: () => apiService.get(`/api/v1/attendance/analytics/dashboard-stats?date=${dayjs().format('YYYY-MM-DD')}`),
    refetchInterval: 30000,
    staleTime:       20000,
  });

  const stats = statsData?.data || {};

  const tabItems = [
    {
      key: 'transactions',
      label: <Space size={5}><HistoryOutlined />Transactions</Space>,
      children: <TransactionsTab />,
    },
    {
      key: 'timesheet',
      label: <Space size={5}><BarChartOutlined />Timesheet</Space>,
      children: <TimesheetTab />,
    },
    {
      key: 'by-area',
      label: <Space size={5}><EnvironmentOutlined />By Area</Space>,
      children: <AreaAttendanceTab />,
    },
    {
      key: 'exceptions',
      label: (
        <Space size={5}>
          <ExceptionOutlined />
          Exceptions
          {(stats.exceptions_count ?? 0) > 0 && (
            <Badge count={stats.exceptions_count} style={{ background: '#f5222d', boxShadow: 'none' }} />
          )}
        </Space>
      ),
      children: <ExceptionsTab />,
    },
    {
      key: 'manual-logs',
      label: <Space size={5}><EditOutlined />Manual Logs</Space>,
      children: <ManualLogsTab />,
    },

    {
      key: 'leaves',
      label: (
        <Space size={5}>
          <UserAddOutlined />
          Leaves
          {(stats.pending_approvals ?? 0) > 0 && (
            <Badge count={stats.pending_approvals} style={{ background: '#fa8c16', boxShadow: 'none' }} />
          )}
        </Space>
      ),
      children: <LeavesTab />,
    },
    {
      key: 'overtime',
      label: <Space size={5}><ThunderboltOutlined />Overtime</Space>,
      children: <OvertimeTab />,
    },

    {
      key: 'timetables',
      label: <Space size={5}><ClockCircleOutlined />Timetables</Space>,
      children: <TimetablesTab />,
    },
    {
      key: 'shifts',
      label: <Space size={5}><RetweetOutlined />Shifts</Space>,
      children: <ShiftsTab />,
    },
    {
      key: 'schedules',
      label: <Space size={5}><CarryOutOutlined />Schedules</Space>,
      children: <SchedulesTab />,
    },

    {
      key: 'holidays',
      label: <Space size={5}><GiftOutlined />Holidays</Space>,
      children: <HolidaysTab />,
    },
    {
      key: 'leave-types',
      label: <Space size={5}><TagsOutlined />Leave Types</Space>,
      children: <LeaveTypesTab />,
    },
    {
      key: 'overtime-rules',
      label: <Space size={5}><SafetyCertificateOutlined />OT Rules</Space>,
      children: <OvertimeRulesTab />,
    },
    {
      key: 'rules',
      label: <Space size={5}><SettingOutlined />Rules</Space>,
      children: <RulesTab />,
    },

    {
      key: 'analytics',
      label: <Space size={5}><LineChartOutlined />Analytics</Space>,
      children: <AnalyticsTab />,
    },
    {
      key: 'contractors',
      label: (
        <Space size={5}>
          <TeamOutlined />
          Contractors
          {(stats.contractor_alerts ?? 0) > 0 && (
            <Badge count={stats.contractor_alerts} style={{ background: '#fa8c16', boxShadow: 'none' }} />
          )}
        </Space>
      ),
      children: <ContractorAttendanceTab />,
    },
  ];

  return (
    <div style={{ padding: 24 }}>

      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div style={{ marginBottom: 20 }}>
        <Space size={14} align="center">
          <div style={{
            width: 46, height: 46, borderRadius: 12, flexShrink: 0,
            background: 'linear-gradient(135deg, #1890ff 0%, #096dd9 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 12px #1890ff40',
          }}>
            <ClockCircleOutlined style={{ color: '#fff', fontSize: 22 }} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 20, lineHeight: 1.2, color: '#1f1f1f' }}>
              Attendance Management
            </div>
            <div style={{ color: '#8c8c8c', fontSize: 13, marginTop: 3 }}>
              Track punches, manage leave &amp; overtime, configure shifts and schedules
            </div>
          </div>
        </Space>
      </div>

      {/* ── Tab Panel ───────────────────────────────────────────────────── */}
      <Card styles={{ body: { padding: 0 } }}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          type="card"
          size="small"
          style={{ padding: '8px 8px 0' }}
          items={tabItems}
        />
      </Card>

    </div>
  );
};

export default AttendanceManagement;
