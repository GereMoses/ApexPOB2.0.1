import React, { useState } from 'react';
import {
  Drawer, Table, Tag, Button, Space, Input, Segmented, Alert, Statistic,
  Row, Col, Typography, Upload, App, Tooltip, Divider,
} from 'antd';
import {
  IdcardOutlined, SyncOutlined, UploadOutlined, SearchOutlined, InfoCircleOutlined,
} from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import apiService from '../../services/api';

const { Text } = Typography;

// Mirrors the backend rule (device_pin.is_valid_pin): a ZKTeco reader PIN is digits only.
const PIN_RE = /^\d{1,9}$/;

// Parses "employee_code,attendance_id" rows from a CSV/TSV export. A header row is
// skipped; the first two columns are used so SeamlessHR's column titles don't matter.
export const parseAttendanceIdCsv = (text) => {
  const items = [];
  const bad = [];
  text.split(/\r?\n/).forEach((line, i) => {
    if (!line.trim()) return;
    const cells = line.split(/[,;\t]/).map(c => c.trim().replace(/^"|"$/g, ''));
    if (cells.length < 2 || !cells[0] || !cells[1]) { bad.push(i + 1); return; }
    if (i === 0 && !/\d/.test(cells[1])) return; // header row
    items.push({ employee_code: cells[0], attendance_id: cells[1] });
  });
  return { items, bad };
};

const ResultPanel = ({ result, onClose }) => {
  if (!result) return null;
  const { updated = 0, unchanged = 0, conflicts = [], invalid = [],
          unknown_employee = [], repin_required = [] } = result;
  const problems = conflicts.length + invalid.length + unknown_employee.length;
  return (
    <Alert
      style={{ marginBottom: 16 }} closable onClose={onClose}
      type={problems ? 'warning' : 'success'} showIcon
      message={`${updated} updated, ${unchanged} unchanged${problems ? `, ${problems} need attention` : ''}`}
      description={
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          {result.pairs_found !== undefined && (
            <Text type="secondary">Read {result.pairs_found} ID(s) from SeamlessHR ({result.pages_read} page(s)).</Text>
          )}
          {conflicts.length > 0 && (
            <Text>
              <b>Already used by someone else ({conflicts.length}):</b>{' '}
              {conflicts.map(c => `${c.emp_code} → ${c.attendance_id} (held by ${c.held_by})`).join('; ')}
            </Text>
          )}
          {invalid.length > 0 && (
            <Text>
              <b>Not a valid reader PIN — must be 1–9 digits ({invalid.length}):</b>{' '}
              {invalid.map(c => `${c.emp_code} → "${c.attendance_id}"`).join('; ')}
            </Text>
          )}
          {unknown_employee.length > 0 && (
            <Text>
              <b>Not in Apex POB — pull employees first ({unknown_employee.length}):</b>{' '}
              {unknown_employee.slice(0, 20).join(', ')}{unknown_employee.length > 20 ? ' …' : ''}
            </Text>
          )}
          {repin_required.length > 0 && (
            <Text type="warning">
              <b>Reader PIN changed for {repin_required.length} employee(s):</b> anyone already enrolled
              on a reader under their old PIN must be re-enrolled so the reader uses the new one:{' '}
              {repin_required.slice(0, 20).join(', ')}{repin_required.length > 20 ? ' …' : ''}
            </Text>
          )}
        </Space>
      }
    />
  );
};

const AttendanceIdsDrawer = ({ open, onClose, configured }) => {
  const { message: msg } = App.useApp();
  const queryClient = useQueryClient();
  const [status, setStatus]     = useState('all');
  const [search, setSearch]     = useState('');
  const [page, setPage]         = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [adopting, setAdopting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [result, setResult]     = useState(null);

  const qs = new URLSearchParams({ q: search, status, page, page_size: pageSize }).toString();
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['hr-attendance-ids', search, status, page, pageSize],
    queryFn:  () => apiService.get(`/api/v1/hr-integration/attendance-ids?${qs}`),
    enabled:  open,
    placeholderData: (prev) => prev,
  });
  const summary = data?.summary || { employees: 0, assigned: 0, missing: 0 };

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['hr-attendance-ids'] });
    refetch();
  };

  const handleAdopt = async () => {
    setAdopting(true);
    try {
      const res = await apiService.post('/api/v1/hr-integration/adopt-attendance-ids');
      setResult(res);
      refresh();
    } catch (e) {
      msg.error(e.message || 'Could not read Attendance IDs from SeamlessHR');
    } finally { setAdopting(false); }
  };

  const handleFile = async (file) => {
    setImporting(true);
    try {
      const { items, bad } = parseAttendanceIdCsv(await file.text());
      if (!items.length) { msg.error('No "employee code, attendance ID" rows found in that file'); return false; }
      if (bad.length) msg.warning(`Skipped ${bad.length} incomplete row(s): line ${bad.slice(0, 5).join(', ')}${bad.length > 5 ? ' …' : ''}`);
      const res = await apiService.post('/api/v1/hr-integration/import-attendance-ids', { items });
      setResult(res);
      refresh();
    } catch (e) {
      msg.error(e.message || 'Import failed');
    } finally { setImporting(false); }
    return false; // stop antd uploading the file itself
  };

  const columns = [
    { title: 'Employee code', dataIndex: 'emp_code', key: 'emp_code', width: 150,
      render: v => <Text code>{v}</Text> },
    { title: 'Name', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: 'Department', dataIndex: 'department', key: 'department', ellipsis: true,
      render: v => v || '—' },
    { title: 'Attendance ID (reader PIN)', dataIndex: 'attendance_id', key: 'attendance_id', width: 190,
      render: v => v
        ? (PIN_RE.test(v) ? <Text strong>{v}</Text> : <Tag color="red">{v} — invalid</Tag>)
        : <Text type="secondary">—</Text> },
    { title: 'Payroll sync', key: 'state', width: 150,
      render: (_, r) => r.attendance_id
        ? <Tag color="green">Ready</Tag>
        : <Tooltip title="Punches for this employee are held back from SeamlessHR until an Attendance ID is adopted">
            <Tag color="orange">Held back</Tag>
          </Tooltip> },
  ];

  return (
    <Drawer
      title={<Space><IdcardOutlined />Attendance IDs</Space>}
      open={open} onClose={onClose} width={Math.min(900, window.innerWidth)}
      destroyOnClose
    >
      <Alert
        type="info" showIcon style={{ marginBottom: 16 }} icon={<InfoCircleOutlined />}
        message="SeamlessHR decides each employee's Attendance ID; Apex POB adopts it"
        description={
          <span>
            The Attendance ID is the user ID (PIN) written to the ZKTeco readers, and the ID SeamlessHR
            matches each punch to. It must be <b>1–9 digits</b> and unique. IDs can't be edited here —
            change them in SeamlessHR, then adopt them again.
          </span>
        }
      />

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Statistic title="Employees from SeamlessHR" value={summary.employees} /></Col>
        <Col span={8}><Statistic title="With an Attendance ID" value={summary.assigned}
                                 valueStyle={{ color: '#52c41a' }} /></Col>
        <Col span={8}><Statistic title="Held back (no ID)" value={summary.missing}
                                 valueStyle={{ color: summary.missing ? '#fa8c16' : undefined }} /></Col>
      </Row>

      <Space wrap style={{ marginBottom: 16 }}>
        <Tooltip title={configured ? '' : 'Configure and save the SeamlessHR connection first'}>
          <Button type="primary" icon={<SyncOutlined />} loading={adopting}
                  disabled={!configured || adopting} onClick={handleAdopt}>
            Adopt from SeamlessHR
          </Button>
        </Tooltip>
        <Upload accept=".csv,.tsv,.txt" showUploadList={false} beforeUpload={handleFile}>
          <Button icon={<UploadOutlined />} loading={importing}>Import from SeamlessHR export (CSV)</Button>
        </Upload>
      </Space>
      <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 12 }}>
        Import expects two columns: <code>employee code, attendance ID</code>. If "Adopt" says
        access was refused, your SeamlessHR API key can't read attendance records — ask SeamlessHR to
        enable it, or import an export instead.
      </Text>

      <ResultPanel result={result} onClose={() => setResult(null)} />

      <Divider style={{ margin: '8px 0 16px' }} />

      <Space wrap style={{ marginBottom: 12 }}>
        <Segmented
          value={status}
          onChange={v => { setStatus(v); setPage(1); }}
          options={[
            { label: 'All', value: 'all' },
            { label: `Missing (${summary.missing})`, value: 'missing' },
            { label: `Assigned (${summary.assigned})`, value: 'assigned' },
          ]}
        />
        <Input.Search
          allowClear placeholder="Search code, name or ID" prefix={<SearchOutlined />}
          style={{ width: 260 }}
          onSearch={v => { setSearch(v); setPage(1); }}
        />
      </Space>

      <Table
        size="small" rowKey="emp_code" loading={isLoading}
        columns={columns} dataSource={data?.items || []}
        locale={{ emptyText: summary.employees
          ? 'No employees match this filter'
          : 'No SeamlessHR employees yet — pull employees first' }}
        pagination={{
          current: page, pageSize, total: data?.total || 0, showSizeChanger: true,
          pageSizeOptions: [25, 50, 100],
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
        scroll={{ x: 640 }}
      />
    </Drawer>
  );
};

export default AttendanceIdsDrawer;
