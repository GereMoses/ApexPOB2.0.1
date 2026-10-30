import { useState, useMemo, useRef } from 'react';
import {
  Table, Button, Space, Input, Select, Modal, Form, Card,
  Row, Col, Tag, Badge, message, Popconfirm, Tabs,
  Tooltip, Descriptions, Divider, Tree, Progress, Alert,
  Drawer, Switch, InputNumber, Checkbox, Popover, Dropdown,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined,
  EyeOutlined, SafetyOutlined, TeamOutlined, ApartmentOutlined,
  DollarOutlined, WarningOutlined, DownloadOutlined, FilterOutlined,
  CheckCircleOutlined, CloseCircleOutlined, UserOutlined, BranchesOutlined,
  SolutionOutlined, BarChartOutlined, InfoCircleOutlined,
  ExclamationCircleOutlined, CopyOutlined, SettingOutlined,
  CheckOutlined, CloseOutlined, PoweroffOutlined, CaretDownOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService from '../../../services/api';

const { Option } = Select;

// ── Colour maps ──────────────────────────────────────────────────────────────
const TYPE_COLOR = {
  executive: 'purple', manager: 'blue', supervisor: 'cyan',
  staff: 'green', contractor: 'orange',
};
const CAT_COLOR = {
  technical: 'geekblue', operations: 'blue', safety: 'red',
  admin: 'volcano', support: 'lime',
};
const TYPE_ICON = {
  executive: 'EX', manager: 'MG', supervisor: 'SV',
  staff: 'ST', contractor: 'CT',
};

// ── Helpers ──────────────────────────────────────────────────────────────────
const fmtSalary = (min, max, cur = 'USD') => {
  if (!min && !max) return null;
  const f = v => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v;
  if (min && max) return `${f(min)} – ${f(max)} ${cur}`;
  if (min) return `≥ ${f(min)} ${cur}`;
  return `≤ ${f(max)} ${cur}`;
};

const staffingStatus = (assigned, headcount) => {
  const hc = headcount || 1;
  if (assigned === 0)       return { label: 'Vacant',      color: '#ff4d4f', bg: '#fff1f0', pct: 0 };
  if (assigned < hc)        return { label: 'Understaffed', color: '#fa8c16', bg: '#fff7e6', pct: Math.round(assigned / hc * 100) };
  if (assigned === hc)      return { label: 'Fully Staffed', color: '#52c41a', bg: '#f6ffed', pct: 100 };
  return                           { label: 'Overstaffed',  color: '#1677ff', bg: '#e6f4ff', pct: 100 };
};

const exportCSV = (positions) => {
  const headers = ['Code', 'Name', 'Department', 'Type', 'Category', 'Grade',
    'Headcount', 'Assigned', 'Salary Min', 'Salary Max', 'Currency',
    'Safety Critical', 'Bg Check', 'Status'];
  const rows = positions.map(p => [
    p.position_code, p.position_name, p.department?.name || '',
    p.position_type || '', p.job_category || '', p.grade_level || '',
    p.headcount || 1, p.assigned_count || 0,
    p.salary_range_min || '', p.salary_range_max || '', p.currency || 'USD',
    p.is_safety_critical ? 'Yes' : 'No',
    p.requires_background_check ? 'Yes' : 'No',
    p.is_active ? 'Active' : 'Inactive',
  ].join(','));
  const csv = [headers.join(','), ...rows].join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  const a = document.createElement('a'); a.href = url;
  a.download = `positions_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click(); URL.revokeObjectURL(url);
};

// ── KPI card ─────────────────────────────────────────────────────────────────
const KpiCard = ({ label, value, color, bg, icon, tooltip }) => (
  <Tooltip title={tooltip}>
    <div style={{
      background: '#fff', borderRadius: 10, border: `1px solid ${color}20`,
      borderTop: `3px solid ${color}`, padding: '14px 18px',
      display: 'flex', alignItems: 'center', gap: 12, cursor: 'default',
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: 9, background: bg,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 18, color, flexShrink: 0,
      }}>{icon}</div>
      <div>
        <div style={{ fontSize: 22, fontWeight: 700, color: '#1f1f1f', lineHeight: 1.1 }}>{value ?? 0}</div>
        <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2 }}>{label}</div>
      </div>
    </div>
  </Tooltip>
);

// ── Staffing badge (assigned / headcount) ────────────────────────────────────
const StaffingBadge = ({ assigned, headcount }) => {
  const s = staffingStatus(assigned, headcount);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: s.color }}>{assigned}</span>
        <span style={{ color: '#bfbfbf', fontSize: 12 }}>/ {headcount || 1}</span>
        <Tag
          style={{ margin: 0, fontSize: 10, lineHeight: '16px', padding: '0 5px',
            color: s.color, background: s.bg, border: `1px solid ${s.color}40` }}>
          {s.label}
        </Tag>
      </div>
      <Progress
        percent={s.pct} size="small" showInfo={false}
        strokeColor={s.color}
        trailColor="#f0f0f0"
        style={{ margin: 0 }}
      />
    </div>
  );
};

// ── Position cell ─────────────────────────────────────────────────────────────
const PositionCell = ({ name, code, type, hr, onView }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span
        onClick={onView}
        style={{ fontWeight: 600, fontSize: 13, cursor: 'pointer', color: '#1677ff' }}
      >{name}</span>
    </div>
    <Space size={4}>
      <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#8c8c8c' }}>{code}</span>
      {type && <Tag color={TYPE_COLOR[type] || 'default'} style={{ margin: 0, fontSize: 10, padding: '0 4px' }}>{type}</Tag>}
      {hr && <Tag color="blue" style={{ margin: 0, fontSize: 10, padding: '0 4px' }}>SeamlessHR</Tag>}
    </Space>
  </div>
);

// ── Analytics tab ─────────────────────────────────────────────────────────────
const AnalyticsTab = ({ summary, vacancies, positions }) => {
  const byType = summary?.by_type || {};
  const byCategory = summary?.by_category || {};
  const byDept = summary?.by_department || {};
  const maxType = Math.max(...Object.values(byType), 1);
  const maxCat  = Math.max(...Object.values(byCategory), 1);
  const maxDept = Math.max(...Object.values(byDept), 1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Row gutter={[16, 16]}>
        {/* By Type */}
        <Col xs={24} md={8}>
          <Card size="small" title={<Space><ApartmentOutlined style={{ color: '#1677ff' }} />By Type</Space>}
            styles={{ body: { padding: '12px 16px' } }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(byType).length === 0
                ? <div style={{ color: '#bfbfbf', fontSize: 12, textAlign: 'center', padding: 16 }}>No data</div>
                : Object.entries(byType)
                    .sort((a, b) => b[1] - a[1])
                    .map(([type, count]) => (
                      <div key={type}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                          <Tag color={TYPE_COLOR[type] || 'default'} style={{ margin: 0, fontSize: 11 }}>
                            {TYPE_ICON[type]} {type}
                          </Tag>
                          <span style={{ fontWeight: 700, fontSize: 13 }}>{count}</span>
                        </div>
                        <Progress percent={Math.round(count / maxType * 100)} showInfo={false}
                          size="small" strokeColor={TYPE_COLOR[type] ? undefined : '#8c8c8c'} />
                      </div>
                    ))
              }
            </div>
          </Card>
        </Col>

        {/* By Category */}
        <Col xs={24} md={8}>
          <Card size="small" title={<Space><SolutionOutlined style={{ color: '#52c41a' }} />By Category</Space>}
            styles={{ body: { padding: '12px 16px' } }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(byCategory).length === 0
                ? <div style={{ color: '#bfbfbf', fontSize: 12, textAlign: 'center', padding: 16 }}>No data</div>
                : Object.entries(byCategory)
                    .sort((a, b) => b[1] - a[1])
                    .map(([cat, count]) => (
                      <div key={cat}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                          <Tag color={CAT_COLOR[cat] || 'default'} style={{ margin: 0, fontSize: 11 }}>{cat}</Tag>
                          <span style={{ fontWeight: 700, fontSize: 13 }}>{count}</span>
                        </div>
                        <Progress percent={Math.round(count / maxCat * 100)} showInfo={false} size="small" />
                      </div>
                    ))
              }
            </div>
          </Card>
        </Col>

        {/* By Department */}
        <Col xs={24} md={8}>
          <Card size="small" title={<Space><TeamOutlined style={{ color: '#722ed1' }} />By Department</Space>}
            styles={{ body: { padding: '12px 16px' } }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(byDept).length === 0
                ? <div style={{ color: '#bfbfbf', fontSize: 12, textAlign: 'center', padding: 16 }}>No data</div>
                : Object.entries(byDept)
                    .sort((a, b) => b[1] - a[1])
                    .map(([dept, count]) => (
                      <div key={dept}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                          <span style={{ fontSize: 12, color: '#595959', maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{dept}</span>
                          <span style={{ fontWeight: 700, fontSize: 13 }}>{count}</span>
                        </div>
                        <Progress percent={Math.round(count / maxDept * 100)} showInfo={false} size="small"
                          strokeColor="#722ed1" />
                      </div>
                    ))
              }
            </div>
          </Card>
        </Col>
      </Row>

      {/* Vacancies */}
      <Card
        size="small"
        title={
          <Space>
            <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />
            <span>Vacant Positions</span>
            <Tag color="error">{vacancies.length}</Tag>
          </Space>
        }
        styles={{ body: { padding: 0 } }}
      >
        {vacancies.length === 0
          ? <div style={{ textAlign: 'center', padding: 24, color: '#52c41a' }}>
              <CheckCircleOutlined style={{ fontSize: 24 }} />
              <div style={{ marginTop: 6, fontSize: 13 }}>All active positions are staffed</div>
            </div>
          : <Table
              size="small"
              dataSource={vacancies}
              rowKey="id"
              pagination={vacancies.length > 8 ? { pageSize: 8, size: 'small' } : false}
              columns={[
                { title: 'Position', key: 'pos', render: (_, r) => (
                  <div>
                    <div style={{ fontWeight: 500 }}>{r.position_name}</div>
                    <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#8c8c8c' }}>{r.position_code}</span>
                  </div>
                )},
                { title: 'Department', key: 'dept', width: 140, render: (_, r) => r.department?.name
                    ? <Tag color="default" style={{ fontSize: 11 }}>{r.department.name}</Tag>
                    : <span style={{ color: '#bfbfbf' }}>—</span> },
                { title: 'Type', dataIndex: 'position_type', width: 120,
                  render: t => t ? <Tag color={TYPE_COLOR[t] || 'default'} style={{ fontSize: 11 }}>{t}</Tag> : '—' },
                { title: 'Safety', key: 'safety', width: 70, align: 'center',
                  render: (_, r) => r.is_safety_critical
                    ? <Tooltip title="Safety Critical"><SafetyOutlined style={{ color: '#ff4d4f' }} /></Tooltip>
                    : <span style={{ color: '#d9d9d9' }}>—</span> },
              ]}
            />
        }
      </Card>

      {/* Staffing Overview */}
      <Card
        size="small"
        title={<Space><BarChartOutlined style={{ color: '#13c2c2' }} />Staffing Overview</Space>}
        styles={{ body: { padding: '12px 16px' } }}
      >
        <Row gutter={24}>
          {[
            { label: 'Fully Staffed', color: '#52c41a', count: positions.filter(p => p.assigned_count >= (p.headcount || 1) && p.assigned_count > 0).length },
            { label: 'Understaffed',  color: '#fa8c16', count: positions.filter(p => p.assigned_count > 0 && p.assigned_count < (p.headcount || 1)).length },
            { label: 'Vacant',        color: '#ff4d4f', count: positions.filter(p => p.assigned_count === 0).length },
            { label: 'Overstaffed',   color: '#1677ff', count: positions.filter(p => p.assigned_count > (p.headcount || 1)).length },
          ].map(({ label, color, count }) => (
            <Col key={label} span={6}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 28, fontWeight: 700, color }}>{count}</div>
                <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2 }}>{label}</div>
              </div>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  );
};

// ── Hierarchy tab ─────────────────────────────────────────────────────────────
const HierarchyTab = () => {
  const [includeInactive, setIncludeInactive] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ['positions-hierarchy', includeInactive],
    queryFn: () => apiService.get(`/api/v1/positions/hierarchy?include_inactive=${includeInactive}`),
    staleTime: 30000,
  });

  const toTreeData = (nodes) =>
    (nodes || []).map(n => ({
      key: String(n.id),
      title: (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 500 }}>{n.position_name}</span>
          <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#8c8c8c' }}>{n.position_code}</span>
          {n.position_type && <Tag color={TYPE_COLOR[n.position_type] || 'default'} style={{ margin: 0, fontSize: 10, padding: '0 4px' }}>{n.position_type}</Tag>}
          {n.department?.name && <Tag color="default" style={{ margin: 0, fontSize: 10, padding: '0 4px' }}>{n.department.name}</Tag>}
          <Tag
            style={{ margin: 0, fontSize: 10, padding: '0 4px',
              color: n.assigned_count === 0 ? '#ff4d4f' : '#52c41a',
              background: n.assigned_count === 0 ? '#fff1f0' : '#f6ffed',
              border: `1px solid ${n.assigned_count === 0 ? '#ffccc7' : '#b7eb8f'}`,
            }}>
            <TeamOutlined style={{ marginRight: 3 }} />{n.assigned_count} assigned
          </Tag>
          {n.is_safety_critical && <Tooltip title="Safety Critical"><SafetyOutlined style={{ color: '#ff4d4f' }} /></Tooltip>}
          {!n.is_active && <Tag color="default" style={{ fontSize: 10 }}>Inactive</Tag>}
        </div>
      ),
      children: toTreeData(n.children),
    }));

  const treeData = toTreeData(Array.isArray(data) ? data : []);

  return (
    <Card size="small" extra={
      <Space size={8}>
        <span style={{ fontSize: 12, color: '#8c8c8c' }}>Show inactive</span>
        <Switch size="small" checked={includeInactive} onChange={setIncludeInactive} />
      </Space>
    }>
      {treeData.length === 0 && !isLoading
        ? <div style={{ textAlign: 'center', padding: 32, color: '#bfbfbf' }}>
            <BranchesOutlined style={{ fontSize: 32 }} />
            <div style={{ marginTop: 8 }}>No hierarchy configured. Set parent positions to build the org tree.</div>
          </div>
        : <Tree
            treeData={treeData}
            defaultExpandAll
            showLine={{ showLeafIcon: false }}
            style={{ fontSize: 13 }}
          />
      }
    </Card>
  );
};

// ── Assignments tab ───────────────────────────────────────────────────────────
const AssignmentsTab = ({ positions }) => {
  const [filterPos,     setFilterPos]     = useState(null);
  const [filterType,    setFilterType]    = useState(null);
  const [filterCurrent, setFilterCurrent] = useState(true);

  const params = new URLSearchParams();
  if (filterPos)              params.append('position_id',     filterPos);
  if (filterType)             params.append('assignment_status', filterType);
  if (filterCurrent !== null) params.append('is_current',      String(filterCurrent));

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['position-assignments', filterPos, filterType, filterCurrent],
    queryFn: () => apiService.get(`/api/v1/positions/assignments?${params}`),
    staleTime: 20000,
  });

  const rows = Array.isArray(data) ? data : [];

  const cols = [
    { title: 'Personnel', key: 'person', render: (_, r) => (
      <div>
        <div style={{ fontWeight: 500, fontSize: 13 }}>{r.personnel_name || `ID ${r.personnel_id}`}</div>
        <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#8c8c8c' }}>{r.emp_code}</span>
      </div>
    )},
    { title: 'Position', key: 'position', render: (_, r) => (
      <div>
        <div style={{ fontWeight: 500, fontSize: 13 }}>{r.position_name}</div>
        <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#8c8c8c' }}>{r.position_code}</span>
      </div>
    )},
    { title: 'Type', dataIndex: 'assignment_type', width: 120,
      render: t => {
        const c = { primary: 'blue', secondary: 'cyan', acting: 'gold' };
        return <Tag color={c[t] || 'default'} style={{ textTransform: 'capitalize' }}>{t || '—'}</Tag>;
      }},
    { title: 'Since', dataIndex: 'start_date', width: 110,
      render: d => d ? new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '—' },
    { title: 'Until', dataIndex: 'end_date', width: 110,
      render: d => d ? new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
        : <span style={{ color: '#52c41a', fontSize: 12 }}>Ongoing</span> },
    { title: 'Status', key: 'status', width: 100,
      render: (_, r) => r.is_current
        ? <Badge status="processing" text={<span style={{ fontSize: 12 }}>Current</span>} />
        : <Badge status="default" text={<span style={{ fontSize: 12 }}>Past</span>} /> },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Card size="small">
        <Row gutter={12} align="middle">
          <Col flex="1">
            <Select
              placeholder="Filter by position"
              style={{ width: '100%' }}
              value={filterPos}
              onChange={setFilterPos}
              showSearch
              optionFilterProp="label"
              allowClear
            >
              {positions.map(p => (
                <Option key={p.id} value={p.id} label={p.position_name}>
                  {p.position_name} <span style={{ color: '#8c8c8c', fontSize: 11 }}>{p.position_code}</span>
                </Option>
              ))}
            </Select>
          </Col>
          <Col>
            <Select placeholder="Assignment type" style={{ width: 160 }} value={filterType} onChange={setFilterType} allowClear>
              <Option value="active">Active</Option>
              <Option value="inactive">Inactive</Option>
              <Option value="pending">Pending</Option>
              <Option value="completed">Completed</Option>
            </Select>
          </Col>
          <Col>
            <Select style={{ width: 140 }} value={filterCurrent} onChange={setFilterCurrent}>
              <Option value={true}>Current only</Option>
              <Option value={false}>Past only</Option>
              <Option value={null}>All</Option>
            </Select>
          </Col>
          <Col>
            <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading}>Refresh</Button>
          </Col>
        </Row>
      </Card>

      <Card size="small" styles={{ body: { padding: 0 } }}>
        <Table
          columns={cols}
          dataSource={rows}
          loading={isLoading}
          rowKey="id"
          size="small"
          scroll={{ x: 900 }}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t, r) => `${r[0]}–${r[1]} of ${t}` }}
          locale={{ emptyText: 'No assignments match the current filters' }}
        />
      </Card>
    </div>
  );
};

// ── Inline headcount editor ───────────────────────────────────────────────────
const InlineHc = ({ value, posId, onSaved }) => {
  const [editing, setEditing] = useState(false);
  const [val, setVal]         = useState(value);
  const inputRef              = useRef(null);

  const start = () => { setVal(value); setEditing(true); setTimeout(() => inputRef.current?.focus(), 50); };
  const cancel = () => setEditing(false);
  const save = async () => {
    if (val === value) { setEditing(false); return; }
    try {
      await apiService.put(`/api/v1/positions/${posId}/`, { headcount: val });
      onSaved();
      setEditing(false);
    } catch {
      message.error('Failed to update headcount');
    }
  };

  if (editing) return (
    <Space size={4}>
      <InputNumber
        ref={inputRef} size="small" min={1} max={999} value={val}
        onChange={v => setVal(v)} style={{ width: 60 }}
        onPressEnter={save} onBlur={save}
      />
      <Button size="small" type="text" icon={<CheckOutlined style={{ color: '#52c41a' }} />} onClick={save} />
      <Button size="small" type="text" icon={<CloseOutlined style={{ color: '#ff4d4f' }} />} onClick={cancel} />
    </Space>
  );
  return (
    <Tooltip title="Click to edit headcount">
      <span
        onClick={start}
        style={{ cursor: 'pointer', borderBottom: '1px dashed #d9d9d9', color: '#595959', fontSize: 13 }}
      >{value || 1}</span>
    </Tooltip>
  );
};

// ── Column visibility toggle ──────────────────────────────────────────────────
const ALL_COLS = [
  { key: 'department', label: 'Department' },
  { key: 'job_category', label: 'Category' },
  { key: 'grade_level', label: 'Grade' },
  { key: 'staffing', label: 'Staffing' },
  { key: 'salary', label: 'Salary Range' },
  { key: 'experience', label: 'Experience' },
  { key: 'flags', label: 'Flags' },
  { key: 'updated', label: 'Last Updated' },
  { key: 'is_active', label: 'Status' },
];

const ColToggle = ({ hidden, onChange }) => (
  <div style={{ width: 190 }}>
    <div style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 600, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
      Visible Columns
    </div>
    {ALL_COLS.map(c => (
      <div key={c.key}
        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', cursor: 'pointer' }}
        onClick={() => onChange(c.key)}>
        <Checkbox checked={!hidden.has(c.key)} />
        <span style={{ fontSize: 13 }}>{c.label}</span>
      </div>
    ))}
    <Divider style={{ margin: '8px 0' }} />
    <Space size={6}>
      <Button size="small" type="link" style={{ padding: 0, fontSize: 12 }}
        onClick={() => ALL_COLS.forEach(c => hidden.has(c.key) && onChange(c.key))}>Show all</Button>
      <Button size="small" type="link" style={{ padding: 0, fontSize: 12 }}
        onClick={() => ALL_COLS.forEach(c => !hidden.has(c.key) && onChange(c.key))}>Hide all</Button>
    </Space>
  </div>
);

// ── Main component ────────────────────────────────────────────────────────────
const PositionList = () => {
  const [activeTab,      setActiveTab]      = useState('positions');
  const [searchText,     setSearchText]     = useState('');
  const [selectedDept,   setSelectedDept]   = useState(null);
  const [selectedType,   setSelectedType]   = useState(null);
  const [selectedCat,    setSelectedCat]    = useState(null);
  const [selectedStatus, setSelectedStatus] = useState(null);
  const [safetyCritical, setSafetyCritical] = useState(null);
  const [page,           setPage]           = useState(1);
  const PAGE_SIZE = 50;

  // selection
  const [selected,    setSelected]    = useState([]);
  // column visibility
  const [hiddenCols,  setHiddenCols]  = useState(new Set());
  const [colPopOpen,  setColPopOpen]  = useState(false);
  // duplicate modal
  const [dupSrc,      setDupSrc]      = useState(null);
  const [dupForm]                     = Form.useForm();

  const [isModalOpen,     setIsModalOpen]     = useState(false);
  const [editingPosition, setEditingPosition] = useState(null);
  const [detailPos,       setDetailPos]       = useState(null);
  const [form] = Form.useForm();
  const qc = useQueryClient();

  const toggleCol = key => setHiddenCols(prev => {
    const n = new Set(prev);
    n.has(key) ? n.delete(key) : n.add(key);
    return n;
  });

  // ── Data fetches ──
  const skip = (page - 1) * PAGE_SIZE;
  const listParams = useMemo(() => {
    const p = new URLSearchParams();
    p.append('skip', skip); p.append('limit', PAGE_SIZE);
    if (searchText)    p.append('search',           searchText);
    if (selectedDept)  p.append('department_id',    selectedDept);
    if (selectedType)  p.append('position_type',    selectedType);
    if (selectedCat)   p.append('job_category',     selectedCat);
    if (selectedStatus !== null && selectedStatus !== undefined) p.append('is_active', selectedStatus);
    if (safetyCritical !== null && safetyCritical !== undefined) p.append('is_safety_critical', safetyCritical);
    return p.toString();
  }, [skip, searchText, selectedDept, selectedType, selectedCat, selectedStatus, safetyCritical]);

  const { data: posRes, isLoading, refetch } = useQuery({
    queryKey: ['positions', listParams],
    queryFn: () => apiService.get(`/api/v1/positions/?${listParams}`),
    refetchInterval: 30000,
  });

  const { data: summaryRes, refetch: refetchSummary } = useQuery({
    queryKey: ['positions-summary'],
    queryFn: () => apiService.get('/api/v1/positions/meta/summary'),
    refetchInterval: 60000,
  });

  const { data: vacanciesRes } = useQuery({
    queryKey: ['positions-vacancies'],
    queryFn: () => apiService.get('/api/v1/positions/vacancies'),
    refetchInterval: 60000,
  });

  const { data: deptRes } = useQuery({
    queryKey: ['departments'],
    queryFn: () => apiService.get('/api/v1/departments/'),
  });

  const positions    = posRes?.data || [];
  const posTotal     = posRes?.total || 0;
  const summary      = summaryRes || {};
  const vacancies    = vacanciesRes || [];
  const departments  = deptRes?.data || deptRes || [];

  // ── All positions (unfiltered, for hierarchy/assignments dropdowns) ──
  const { data: allPosRes } = useQuery({
    queryKey: ['positions-all'],
    queryFn: () => apiService.get('/api/v1/positions/?limit=500'),
    staleTime: 60000,
  });
  const allPositions = allPosRes?.data || [];

  // ── Mutations ──
  const invalidateAll = () => {
    qc.invalidateQueries(['positions']); qc.invalidateQueries(['positions-summary']);
    qc.invalidateQueries(['positions-vacancies']); qc.invalidateQueries(['positions-all']);
    refetchSummary();
  };

  const saveMutation = useMutation({
    mutationFn: (values) => editingPosition
      ? apiService.put(`/api/v1/positions/${editingPosition.id}/`, values)
      : apiService.post('/api/v1/positions/', values),
    onSuccess: () => {
      message.success(editingPosition ? 'Position updated' : 'Position created');
      setIsModalOpen(false); setEditingPosition(null); form.resetFields();
      invalidateAll();
    },
    onError: (err) => message.error(err?.response?.data?.detail || err.message || 'Operation failed'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => apiService.delete(`/api/v1/positions/${id}`),
    onSuccess: () => { message.success('Position deactivated'); invalidateAll(); },
    onError: (err) => message.error(err?.response?.data?.detail || err.message || 'Deactivate failed'),
  });

  const bulkMutation = useMutation({
    mutationFn: ({ action, ids }) => apiService.post('/api/v1/positions/bulk-action', { action, ids }),
    onSuccess: (res, { action }) => {
      const ok  = res?.success?.length ?? 0;
      const bad = res?.failed?.length  ?? 0;
      if (ok)  message.success(`${ok} position(s) ${action === 'activate' ? 'activated' : 'deactivated'}`);
      if (bad) message.warning(`${bad} position(s) skipped — ${res.failed.map(f => f.reason).join('; ')}`);
      setSelected([]);
      invalidateAll();
    },
    onError: (err) => message.error(err?.response?.data?.detail || err.message || 'Bulk action failed'),
  });

  const dupMutation = useMutation({
    mutationFn: ({ id, values }) => apiService.post(`/api/v1/positions/duplicate/${id}`, values),
    onSuccess: () => {
      message.success('Position duplicated');
      setDupSrc(null); dupForm.resetFields(); invalidateAll();
    },
    onError: (err) => message.error(err?.response?.data?.detail || err.message || 'Duplicate failed'),
  });

  const handleAdd = () => { setEditingPosition(null); form.resetFields(); setIsModalOpen(true); };
  const handleEdit = (record) => {
    setEditingPosition(record);
    form.setFieldsValue({
      ...record,
      position_type: record.position_type || undefined,
      job_category:  record.job_category  || undefined,
      parent_id:     record.parent_id     || undefined,
    });
    setIsModalOpen(true);
  };
  const handleSave    = () => form.validateFields().then(v => saveMutation.mutate(v)).catch(() => {});
  const handleDupSave = () => dupForm.validateFields().then(v => dupMutation.mutate({ id: dupSrc.id, values: v })).catch(() => {});

  const openDuplicate = (record) => {
    setDupSrc(record);
    dupForm.setFieldsValue({
      position_code: `${record.position_code}-COPY`,
      position_name: `${record.position_name} (Copy)`,
    });
  };

  const resetFilters = () => {
    setSearchText(''); setSelectedDept(null); setSelectedType(null);
    setSelectedCat(null); setSelectedStatus(null); setSafetyCritical(null); setPage(1);
  };
  const hasFilters = searchText || selectedDept || selectedType || selectedCat || selectedStatus !== null || safetyCritical !== null;

  const selectedActive   = positions.filter(p => selected.includes(p.id) && p.is_active);
  const selectedInactive = positions.filter(p => selected.includes(p.id) && !p.is_active);
  const selectedDeactivatable = selectedActive.filter(p => p.assigned_count === 0);

  // ── Table columns ──
  const allColDefs = useMemo(() => [
    {
      title: 'Position',
      key: 'position',
      fixed: 'left',
      width: 240,
      sorter: (a, b) => a.position_name.localeCompare(b.position_name),
      render: (_, r) => (
        <PositionCell name={r.position_name} code={r.position_code} type={r.position_type}
          hr={r.hr_managed} onView={() => setDetailPos(r)} />
      ),
    },
    {
      title: 'Department',
      key: 'department',
      width: 140,
      sorter: (a, b) => (a.department?.name || '').localeCompare(b.department?.name || ''),
      render: (_, r) => r.department?.name
        ? <Tag color="default" style={{ fontSize: 11 }}>{r.department.name}</Tag>
        : <span style={{ color: '#d9d9d9' }}>—</span>,
    },
    {
      title: 'Category',
      dataIndex: 'job_category',
      key: 'job_category',
      width: 120,
      sorter: (a, b) => (a.job_category || '').localeCompare(b.job_category || ''),
      render: c => c ? <Tag color={CAT_COLOR[c] || 'default'} style={{ fontSize: 11 }}>{c}</Tag> : <span style={{ color: '#d9d9d9' }}>—</span>,
    },
    {
      title: 'Grade',
      dataIndex: 'grade_level',
      key: 'grade_level',
      width: 75,
      sorter: (a, b) => (a.grade_level || '').localeCompare(b.grade_level || ''),
      render: g => g ? <Tag style={{ fontSize: 11, fontFamily: 'monospace' }}>{g}</Tag> : <span style={{ color: '#d9d9d9' }}>—</span>,
    },
    {
      title: 'Staffing',
      key: 'staffing',
      width: 175,
      sorter: (a, b) => (a.assigned_count / (a.headcount || 1)) - (b.assigned_count / (b.headcount || 1)),
      render: (_, r) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <InlineHc value={r.headcount || 1} posId={r.id} onSaved={invalidateAll} />
          <div style={{ flex: 1, minWidth: 80 }}>
            <StaffingBadge assigned={r.assigned_count} headcount={r.headcount} />
          </div>
        </div>
      ),
    },
    {
      title: 'Salary Range',
      key: 'salary',
      width: 165,
      sorter: (a, b) => (a.salary_range_min || 0) - (b.salary_range_min || 0),
      render: (_, r) => {
        const s = fmtSalary(r.salary_range_min, r.salary_range_max, r.currency);
        return s
          ? <Space size={4}><DollarOutlined style={{ color: '#52c41a', fontSize: 11 }} /><span style={{ fontSize: 12 }}>{s}</span></Space>
          : <span style={{ color: '#d9d9d9' }}>—</span>;
      },
    },
    {
      title: 'Experience',
      key: 'experience',
      width: 100,
      sorter: (a, b) => (a.min_experience_years || 0) - (b.min_experience_years || 0),
      render: (_, r) => r.min_experience_years
        ? <span style={{ fontSize: 12 }}>{r.min_experience_years} yr{r.min_experience_years !== 1 ? 's' : ''}</span>
        : <span style={{ color: '#d9d9d9' }}>—</span>,
    },
    {
      title: 'Flags',
      key: 'flags',
      width: 74,
      align: 'center',
      render: (_, r) => (
        <Space size={6}>
          {r.is_safety_critical && (
            <Tooltip title="Safety Critical"><SafetyOutlined style={{ color: '#ff4d4f', fontSize: 15 }} /></Tooltip>
          )}
          {r.requires_background_check && (
            <Tooltip title="Background Check Required"><CheckCircleOutlined style={{ color: '#fa8c16', fontSize: 15 }} /></Tooltip>
          )}
          {!r.is_safety_critical && !r.requires_background_check && <span style={{ color: '#e0e0e0' }}>—</span>}
        </Space>
      ),
    },
    {
      title: 'Updated',
      key: 'updated',
      width: 100,
      sorter: (a, b) => new Date(a.updated_at || 0) - new Date(b.updated_at || 0),
      render: (_, r) => r.updated_at
        ? <span style={{ fontSize: 11, color: '#8c8c8c' }}>
            {new Date(r.updated_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })}
          </span>
        : <span style={{ color: '#d9d9d9' }}>—</span>,
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 92,
      sorter: (a, b) => Number(b.is_active) - Number(a.is_active),
      render: active => (
        <Badge
          status={active ? 'success' : 'error'}
          text={<span style={{ fontSize: 12 }}>{active ? 'Active' : 'Inactive'}</span>}
        />
      ),
    },
    {
      title: '',
      key: 'actions',
      fixed: 'right',
      width: 130,
      render: (_, record) => (
        <Space size={3}>
          <Tooltip title="View"><Button size="small" icon={<EyeOutlined />} onClick={() => setDetailPos(record)} /></Tooltip>
          <Tooltip title="Edit"><Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} /></Tooltip>
          <Dropdown
            trigger={['click']}
            menu={{
              items: [
                {
                  key: 'dup',
                  icon: <CopyOutlined />,
                  label: 'Duplicate',
                  onClick: () => openDuplicate(record),
                },
                { type: 'divider' },
                record.is_active
                  ? {
                      key: 'deactivate',
                      icon: <PoweroffOutlined style={{ color: '#ff4d4f' }} />,
                      label: (
                        <Tooltip title={record.assigned_count > 0 ? `${record.assigned_count} active assignment(s) — reassign first` : ''}>
                          <span style={{ color: record.assigned_count > 0 ? '#bfbfbf' : '#ff4d4f' }}>Deactivate</span>
                        </Tooltip>
                      ),
                      disabled: record.assigned_count > 0 || record.hr_managed,
                      onClick: () => {
                        Modal.confirm({
                          title: 'Deactivate position?',
                          content: 'This removes it from active listings but keeps historical data.',
                          okText: 'Deactivate', okButtonProps: { danger: true },
                          onOk: () => deleteMutation.mutate(record.id),
                        });
                      },
                    }
                  : {
                      key: 'activate',
                      icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
                      label: <span style={{ color: '#52c41a' }}>Re-activate</span>,
                      onClick: () => {
                        apiService.put(`/api/v1/positions/${record.id}/`, { is_active: true })
                          .then(() => { message.success('Position re-activated'); invalidateAll(); })
                          .catch(e => message.error(e?.message || 'Failed'));
                      },
                    },
              ],
            }}
          >
            <Button size="small" icon={<CaretDownOutlined />} />
          </Dropdown>
        </Space>
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [positions, hiddenCols]);

  const columns = useMemo(
    () => allColDefs.filter(c => c.key === 'position' || c.key === 'actions' || !hiddenCols.has(c.key)),
    [allColDefs, hiddenCols],
  );

  // ── Expandable row renderer ──
  const expandedRowRender = (record) => {
    const skills = record.required_skills || [];
    const certs  = record.required_certifications || [];
    const hasExtra = record.description || record.notes || skills.length || certs.length || record.education_level;
    if (!hasExtra) return <div style={{ color: '#bfbfbf', fontSize: 12, padding: '4px 8px' }}>No additional details</div>;
    return (
      <div style={{ padding: '8px 24px 8px 48px', display: 'flex', flexWrap: 'wrap', gap: 24 }}>
        {record.description && (
          <div style={{ minWidth: 200, flex: 1 }}>
            <div style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Description</div>
            <div style={{ fontSize: 12, color: '#3c3c3c', lineHeight: 1.5 }}>{record.description}</div>
          </div>
        )}
        {(skills.length > 0 || certs.length > 0 || record.education_level) && (
          <div style={{ minWidth: 200, flex: 1 }}>
            {record.education_level && (
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Education</div>
                <Tag color="geekblue" style={{ fontSize: 11 }}>{record.education_level}</Tag>
              </div>
            )}
            {skills.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Required Skills</div>
                <Space size={4} wrap>{skills.map(s => <Tag key={s} style={{ fontSize: 11 }}>{s}</Tag>)}</Space>
              </div>
            )}
            {certs.length > 0 && (
              <div>
                <div style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Certifications</div>
                <Space size={4} wrap>{certs.map(c => <Tag key={c} color="blue" style={{ fontSize: 11 }}>{c}</Tag>)}</Space>
              </div>
            )}
          </div>
        )}
        {record.notes && (
          <div style={{ minWidth: 160, flex: 1 }}>
            <div style={{ fontSize: 11, color: '#8c8c8c', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Notes</div>
            <div style={{ fontSize: 12, color: '#595959', fontStyle: 'italic', lineHeight: 1.5 }}>{record.notes}</div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="personnel-module">
      <Card
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', overflow: 'visible' }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>Position Management</div>
              <div style={{ fontSize: 12, color: '#64748b', fontWeight: 400, marginTop: 2 }}>
                Define roles, manage headcount targets and org hierarchy
              </div>
            </div>
            <Space size="middle" style={{ overflow: 'visible' }}>
              <Button
                icon={<DownloadOutlined />} size="small"
                onClick={() => exportCSV(selected.length > 0 ? positions.filter(p => selected.includes(p.id)) : positions)}
                disabled={positions.length === 0}
              >
                {selected.length > 0 ? `Export (${selected.length})` : 'Export CSV'}
              </Button>
              <Popover
                open={colPopOpen}
                onOpenChange={setColPopOpen}
                trigger="click"
                placement="bottomRight"
                content={<ColToggle hidden={hiddenCols} onChange={toggleCol} />}
              >
                <Button icon={<SettingOutlined />} size="small">
                  Columns{hiddenCols.size > 0 ? ` (${ALL_COLS.length - hiddenCols.size}/${ALL_COLS.length})` : ''}
                </Button>
              </Popover>
              <Button icon={<ReloadOutlined />} size="small" onClick={() => { refetch(); refetchSummary(); }} loading={isLoading}>
                Refresh
              </Button>
              <Button type="primary" icon={<PlusOutlined />} size="small" onClick={handleAdd}
                style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', border: 'none' }}>
                New Position
              </Button>
            </Space>
          </div>
        }
        styles={{ header: { overflow: 'visible' } }}
      >

      {/* ── KPI strip ── */}
      <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
        <Col xs={12} sm={8} md={4} lg={4}>
          <KpiCard label="Total"         value={summary.total}          color="#1677ff" bg="#e6f4ff" icon={<ApartmentOutlined />} tooltip="All positions in the system" />
        </Col>
        <Col xs={12} sm={8} md={4} lg={4}>
          <KpiCard label="Active"         value={summary.active}         color="#52c41a" bg="#f6ffed" icon={<CheckCircleOutlined />} tooltip="Currently active positions" />
        </Col>
        <Col xs={12} sm={8} md={4} lg={4}>
          <KpiCard label="Vacant"         value={summary.vacant}         color="#ff4d4f" bg="#fff1f0" icon={<CloseCircleOutlined />} tooltip="Active positions with no current assignments" />
        </Col>
        <Col xs={12} sm={8} md={4} lg={4}>
          <KpiCard label="Understaffed"   value={summary.understaffed}   color="#fa8c16" bg="#fff7e6" icon={<WarningOutlined />} tooltip="Active positions with fewer assigned than headcount target" />
        </Col>
        <Col xs={12} sm={8} md={4} lg={4}>
          <KpiCard label="Safety Critical" value={summary.safety_critical} color="#f5222d" bg="#fff1f0" icon={<SafetyOutlined />} tooltip="Positions flagged as safety-critical" />
        </Col>
        <Col xs={12} sm={8} md={4} lg={4}>
          <KpiCard label="Inactive"        value={summary.inactive}        color="#8c8c8c" bg="#fafafa" icon={<CloseCircleOutlined />} tooltip="Deactivated positions" />
        </Col>
      </Row>

      {/* ── Tab panel ── */}
      <Card styles={{ body: { padding: 0 } }}>
        <Tabs
          activeKey={activeTab}
          onChange={k => setActiveTab(k)}
          type="card"
          size="small"
          style={{ padding: '8px 8px 0' }}
          items={[
            {
              key: 'positions',
              label: <Space size={5}><ApartmentOutlined />Positions</Space>,
              children: (
                <div style={{ padding: 16 }}>
                  {/* Filter bar */}
                  <div style={{ background: '#fafafa', border: '1px solid #f0f0f0', borderRadius: 10, padding: '12px 16px', marginBottom: 14 }}>
                    <Row gutter={[10, 8]} align="middle">
                      <Col xs={24} sm={12} md={5}>
                        <Input.Search
                          placeholder="Search name or code…"
                          value={searchText}
                          onChange={e => { setSearchText(e.target.value); setPage(1); }}
                          allowClear
                        />
                      </Col>
                      <Col xs={12} sm={6} md={4}>
                        <Select placeholder="Department" style={{ width: '100%' }}
                          value={selectedDept} onChange={v => { setSelectedDept(v); setPage(1); }} allowClear>
                          {departments.map(d => <Option key={d.id} value={d.id}>{d.name}</Option>)}
                        </Select>
                      </Col>
                      <Col xs={12} sm={6} md={3}>
                        <Select placeholder="Type" style={{ width: '100%' }}
                          value={selectedType} onChange={v => { setSelectedType(v); setPage(1); }} allowClear>
                          {['executive','manager','supervisor','staff','contractor'].map(t => (
                            <Option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</Option>
                          ))}
                        </Select>
                      </Col>
                      <Col xs={12} sm={6} md={3}>
                        <Select placeholder="Category" style={{ width: '100%' }}
                          value={selectedCat} onChange={v => { setSelectedCat(v); setPage(1); }} allowClear>
                          {['technical','operations','safety','admin','support'].map(c => (
                            <Option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</Option>
                          ))}
                        </Select>
                      </Col>
                      <Col xs={12} sm={6} md={3}>
                        <Select placeholder="Status" style={{ width: '100%' }}
                          value={selectedStatus} onChange={v => { setSelectedStatus(v ?? null); setPage(1); }} allowClear>
                          <Option value={true}>Active</Option>
                          <Option value={false}>Inactive</Option>
                        </Select>
                      </Col>
                      <Col xs={12} sm={6} md={3}>
                        <Select placeholder="Safety" style={{ width: '100%' }}
                          value={safetyCritical} onChange={v => { setSafetyCritical(v ?? null); setPage(1); }} allowClear>
                          <Option value={true}>Safety Critical</Option>
                          <Option value={false}>Non-Critical</Option>
                        </Select>
                      </Col>
                      {hasFilters && (
                        <Col>
                          <Button size="small" type="link" icon={<FilterOutlined />} onClick={resetFilters}>
                            Clear filters
                          </Button>
                        </Col>
                      )}
                    </Row>
                  </div>

                  {/* Bulk action bar */}
                  {selected.length > 0 && (
                    <div style={{
                      background: '#f0f5ff', border: '1px solid #adc6ff', borderRadius: 8,
                      padding: '8px 14px', marginBottom: 10,
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8,
                    }}>
                      <Space size={6}>
                        <CheckCircleOutlined style={{ color: '#1677ff' }} />
                        <span style={{ fontSize: 13, fontWeight: 600, color: '#1677ff' }}>
                          {selected.length} selected
                        </span>
                        <Button size="small" type="link" style={{ padding: 0, fontSize: 12 }} onClick={() => setSelected([])}>
                          Clear
                        </Button>
                      </Space>
                      <Space size={8} wrap>
                        <Button
                          size="small"
                          icon={<DownloadOutlined />}
                          onClick={() => exportCSV(positions.filter(p => selected.includes(p.id)))}
                        >
                          Export selected
                        </Button>
                        {selectedInactive.length > 0 && (
                          <Popconfirm
                            title={`Activate ${selectedInactive.length} position${selectedInactive.length !== 1 ? 's' : ''}?`}
                            onConfirm={() => bulkMutation.mutate({ action: 'activate', ids: selectedInactive.map(p => p.id) })}
                            okText="Activate" okButtonProps={{ style: { background: '#52c41a', borderColor: '#52c41a' } }}
                          >
                            <Button
                              size="small"
                              icon={<CheckCircleOutlined />}
                              style={{ color: '#52c41a', borderColor: '#52c41a' }}
                              loading={bulkMutation.isPending}
                            >
                              Activate ({selectedInactive.length})
                            </Button>
                          </Popconfirm>
                        )}
                        {selectedDeactivatable.length > 0 && (
                          <Popconfirm
                            title={`Deactivate ${selectedDeactivatable.length} position${selectedDeactivatable.length !== 1 ? 's' : ''}?`}
                            description="Only unassigned positions will be deactivated."
                            onConfirm={() => bulkMutation.mutate({ action: 'deactivate', ids: selectedDeactivatable.map(p => p.id) })}
                            okText="Deactivate" okButtonProps={{ danger: true }}
                          >
                            <Button
                              size="small" danger
                              icon={<PoweroffOutlined />}
                              loading={bulkMutation.isPending}
                            >
                              Deactivate ({selectedDeactivatable.length})
                            </Button>
                          </Popconfirm>
                        )}
                        {selectedActive.length > selectedDeactivatable.length && (
                          <Tooltip title={`${selectedActive.length - selectedDeactivatable.length} selected position(s) have active assignments and cannot be deactivated`}>
                            <InfoCircleOutlined style={{ color: '#fa8c16', fontSize: 14 }} />
                          </Tooltip>
                        )}
                      </Space>
                    </div>
                  )}

                  {/* Result count */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ fontSize: 12, color: '#8c8c8c' }}>
                      {posTotal.toLocaleString()} position{posTotal !== 1 ? 's' : ''}
                      {hasFilters && ' (filtered)'}
                    </span>
                    {hiddenCols.size > 0 && (
                      <span style={{ fontSize: 11, color: '#adb5bd' }}>
                        {hiddenCols.size} column{hiddenCols.size !== 1 ? 's' : ''} hidden
                      </span>
                    )}
                  </div>

                  <Table
                    columns={columns}
                    dataSource={positions}
                    loading={isLoading}
                    rowKey="id"
                    size="small"
                    scroll={{ x: 1280 }}
                    rowSelection={{
                      type: 'checkbox',
                      selectedRowKeys: selected,
                      onChange: keys => setSelected(keys),
                      preserveSelectedRowKeys: true,
                      getCheckboxProps: r => ({ name: r.position_code }),
                    }}
                    expandable={{
                      expandedRowRender,
                      rowExpandable: r => !!(r.description || r.notes || (r.required_skills || []).length || (r.required_certifications || []).length || r.education_level),
                      expandRowByClick: false,
                    }}
                    pagination={{
                      current: page,
                      pageSize: PAGE_SIZE,
                      total: posTotal,
                      onChange: p => setPage(p),
                      showSizeChanger: false,
                      showTotal: (t, r) => `${r[0]}–${r[1]} of ${t}`,
                      size: 'small',
                    }}
                    rowClassName={r => !r.is_active ? 'pos-inactive-row' : r.assigned_count === 0 ? 'pos-vacant-row' : ''}
                  />
                  <style>{`
                    .pos-inactive-row td { opacity: 0.55; }
                    .pos-vacant-row td   { background: #fff9f9 !important; }
                    .pos-vacant-row:hover td { background: #fff1f0 !important; }
                    .ant-table-expanded-row > td { background: #fafcff !important; padding: 0 !important; }
                  `}</style>
                </div>
              ),
            },
            {
              key: 'hierarchy',
              label: <Space size={5}><BranchesOutlined />Hierarchy</Space>,
              children: <div style={{ padding: 16 }}><HierarchyTab /></div>,
            },
            {
              key: 'assignments',
              label: <Space size={5}><UserOutlined />Assignments</Space>,
              children: <div style={{ padding: 16 }}><AssignmentsTab positions={allPositions} /></div>,
            },
            {
              key: 'analytics',
              label: <Space size={5}><BarChartOutlined />Analytics</Space>,
              children: (
                <div style={{ padding: 16 }}>
                  <AnalyticsTab summary={summary} vacancies={vacancies} positions={allPositions} />
                </div>
              ),
            },
          ]}
        />
      </Card>

      {/* ── Duplicate Modal ── */}
      <Modal
        title={
          <Space>
            <CopyOutlined style={{ color: '#667eea' }} />
            <span>Duplicate Position</span>
          </Space>
        }
        open={!!dupSrc}
        onCancel={() => { setDupSrc(null); dupForm.resetFields(); }}
        onOk={handleDupSave}
        okText="Create Copy"
        okButtonProps={{ loading: dupMutation.isPending, style: { background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', border: 'none' } }}
        destroyOnHidden
        width={440}
      >
        {dupSrc && (
          <>
            <Alert
              type="info"
              showIcon
              message={<span style={{ fontSize: 12 }}>Cloning all settings from <strong>{dupSrc.position_name}</strong> ({dupSrc.position_code}). Assignments are not copied.</span>}
              style={{ marginBottom: 16 }}
            />
            <Form form={dupForm} layout="vertical" size="small">
              <Form.Item
                name="position_code"
                label="New Position Code"
                rules={[
                  { required: true, message: 'Position code is required' },
                  { pattern: /^[A-Z0-9_-]{2,20}$/, message: 'Use 2–20 uppercase letters, numbers, underscores or hyphens' },
                ]}
              >
                <Input placeholder="e.g. ENG-002" style={{ fontFamily: 'monospace', textTransform: 'uppercase' }}
                  onChange={e => dupForm.setFieldValue('position_code', e.target.value.toUpperCase())} />
              </Form.Item>
              <Form.Item
                name="position_name"
                label="New Position Name"
                rules={[{ required: true, message: 'Position name is required' }]}
              >
                <Input placeholder="e.g. Senior Engineer II" />
              </Form.Item>
            </Form>
          </>
        )}
      </Modal>

      {/* ── Detail Drawer ── */}
      <Drawer
        title={
          detailPos && (
            <Space>
              <div style={{
                width: 34, height: 34, borderRadius: 8,
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <ApartmentOutlined style={{ color: '#fff', fontSize: 16 }} />
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 14, lineHeight: 1.2 }}>{detailPos.position_name}</div>
                <div style={{ fontFamily: 'monospace', fontSize: 11, color: '#8c8c8c', fontWeight: 400 }}>{detailPos.position_code}</div>
              </div>
            </Space>
          )
        }
        open={!!detailPos}
        onClose={() => setDetailPos(null)}
        width={520}
        extra={
          detailPos && (
            <Button type="primary" icon={<EditOutlined />}
              onClick={() => { handleEdit(detailPos); setDetailPos(null); }}>
              Edit
            </Button>
          )
        }
        destroyOnHidden
      >
        {detailPos && (
          <>
            {/* Staffing banner */}
            <div style={{
              background: staffingStatus(detailPos.assigned_count, detailPos.headcount).bg,
              border: `1px solid ${staffingStatus(detailPos.assigned_count, detailPos.headcount).color}30`,
              borderRadius: 8, padding: '12px 16px', marginBottom: 16,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div>
                <div style={{ fontSize: 24, fontWeight: 700, color: staffingStatus(detailPos.assigned_count, detailPos.headcount).color }}>
                  {detailPos.assigned_count} / {detailPos.headcount || 1}
                </div>
                <div style={{ fontSize: 12, color: '#595959' }}>Assigned / Headcount Target</div>
              </div>
              <Tag style={{
                fontSize: 13, padding: '4px 12px',
                color: staffingStatus(detailPos.assigned_count, detailPos.headcount).color,
                background: staffingStatus(detailPos.assigned_count, detailPos.headcount).bg,
                border: `1px solid ${staffingStatus(detailPos.assigned_count, detailPos.headcount).color}50`,
              }}>
                {staffingStatus(detailPos.assigned_count, detailPos.headcount).label}
              </Tag>
            </div>

            <Divider orientation="left" style={{ fontSize: 12, marginTop: 0 }}>Identity</Divider>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Code">{detailPos.position_code}</Descriptions.Item>
              <Descriptions.Item label="Name">{detailPos.position_name}</Descriptions.Item>
              <Descriptions.Item label="Department">{detailPos.department?.name || '—'}</Descriptions.Item>
              <Descriptions.Item label="Type">
                {detailPos.position_type
                  ? <Tag color={TYPE_COLOR[detailPos.position_type]}>{detailPos.position_type}</Tag>
                  : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Category">
                {detailPos.job_category
                  ? <Tag color={CAT_COLOR[detailPos.job_category]}>{detailPos.job_category}</Tag>
                  : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Grade">{detailPos.grade_level || '—'}</Descriptions.Item>
            </Descriptions>

            <Divider orientation="left" style={{ fontSize: 12 }}>Compliance & Safety</Divider>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Safety Critical">
                {detailPos.is_safety_critical ? <Tag color="red" icon={<SafetyOutlined />}>Yes</Tag> : <Tag>No</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="Background Check">
                {detailPos.requires_background_check ? <Tag color="orange">Required</Tag> : <Tag>Not Required</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="Min Experience">{detailPos.min_experience_years ?? 0} yrs</Descriptions.Item>
              <Descriptions.Item label="Education">{detailPos.education_level || '—'}</Descriptions.Item>
            </Descriptions>

            <Divider orientation="left" style={{ fontSize: 12 }}>Compensation</Divider>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Salary Range" span={2}>
                {fmtSalary(detailPos.salary_range_min, detailPos.salary_range_max, detailPos.currency) || '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Currency">{detailPos.currency || '—'}</Descriptions.Item>
              <Descriptions.Item label="Status">
                <Badge status={detailPos.is_active ? 'success' : 'error'}
                  text={detailPos.is_active ? 'Active' : 'Inactive'} />
              </Descriptions.Item>
            </Descriptions>

            {(detailPos.required_skills?.length > 0 || detailPos.required_certifications?.length > 0) && (
              <>
                <Divider orientation="left" style={{ fontSize: 12 }}>Requirements</Divider>
                {detailPos.required_skills?.length > 0 && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>Skills</div>
                    <Space size={4} wrap>
                      {detailPos.required_skills.map(s => <Tag key={s}>{s}</Tag>)}
                    </Space>
                  </div>
                )}
                {detailPos.required_certifications?.length > 0 && (
                  <div>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>Certifications</div>
                    <Space size={4} wrap>
                      {detailPos.required_certifications.map(c => <Tag key={c} color="blue">{c}</Tag>)}
                    </Space>
                  </div>
                )}
              </>
            )}

            {(detailPos.description || detailPos.notes) && (
              <>
                <Divider orientation="left" style={{ fontSize: 12 }}>Notes</Divider>
                {detailPos.description && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>Description</div>
                    <div style={{ fontSize: 13, color: '#3c3c3c', background: '#fafafa', borderRadius: 6, padding: '8px 12px' }}>
                      {detailPos.description}
                    </div>
                  </div>
                )}
                {detailPos.notes && (
                  <div>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>Notes</div>
                    <div style={{ fontSize: 13, color: '#3c3c3c', background: '#fafafa', borderRadius: 6, padding: '8px 12px' }}>
                      {detailPos.notes}
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </Drawer>

      {/* ── Create / Edit Modal ── */}
      <Modal
        title={
          <Space>
            <div style={{
              width: 30, height: 30, borderRadius: 7,
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <ApartmentOutlined style={{ color: '#fff', fontSize: 14 }} />
            </div>
            <span>{editingPosition ? `Edit — ${editingPosition.position_name}` : 'New Position'}</span>
          </Space>
        }
        open={isModalOpen}
        onOk={handleSave}
        onCancel={() => { setIsModalOpen(false); setEditingPosition(null); form.resetFields(); }}
        okText={editingPosition ? 'Save Changes' : 'Create Position'}
        confirmLoading={saveMutation.isPending}
        width={800}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" size="small" style={{ marginTop: 8 }}>
          {/* Code warning on edit */}
          {editingPosition && (editingPosition.hr_managed ? (
            <Alert
              type="warning" showIcon style={{ marginBottom: 14, fontSize: 12 }}
              message="This position comes from SeamlessHR — its name and code are changed there and sync here. Safety and certificate details below are ApexPOB's own and can be edited."
            />
          ) : (
            <Alert
              type="info" showIcon style={{ marginBottom: 14, fontSize: 12 }}
              message="Position code can be edited. Changes propagate to all linked records on save."
            />
          ))}

          <Divider orientation="left" style={{ fontSize: 12, marginTop: 4 }}>Identity</Divider>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="position_code" label="Position Code" rules={[{ required: true, message: 'Required' }]}>
                <Input placeholder="e.g. POS-001" disabled={!!editingPosition?.hr_managed} />
              </Form.Item>
            </Col>
            <Col span={16}>
              <Form.Item name="position_name" label="Position Name" rules={[{ required: true, message: 'Required' }]}>
                <Input placeholder="e.g. Senior Safety Engineer" disabled={!!editingPosition?.hr_managed} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="department_id" label="Department">
                <Select placeholder="Select department" allowClear showSearch optionFilterProp="children">
                  {departments.map(d => <Option key={d.id} value={d.id}>{d.name}</Option>)}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="parent_id" label={
                <Space size={4}>Parent Position
                  <Tooltip title="Set a parent to build the org hierarchy">
                    <InfoCircleOutlined style={{ color: '#8c8c8c', fontSize: 11 }} />
                  </Tooltip>
                </Space>
              }>
                <Select placeholder="Top-level (no parent)" allowClear showSearch optionFilterProp="label">
                  {allPositions
                    .filter(p => !editingPosition || p.id !== editingPosition.id)
                    .map(p => (
                      <Option key={p.id} value={p.id} label={p.position_name}>
                        {p.position_name} <span style={{ color: '#8c8c8c', fontSize: 11 }}>{p.position_code}</span>
                      </Option>
                    ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left" style={{ fontSize: 12 }}>Classification</Divider>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="position_type" label="Position Type">
                <Select placeholder="Select type" allowClear>
                  {['executive','manager','supervisor','staff','contractor'].map(t => (
                    <Option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="job_category" label="Job Category">
                <Select placeholder="Select category" allowClear>
                  {['technical','operations','safety','admin','support'].map(c => (
                    <Option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="grade_level" label="Grade Level">
                <Input placeholder="e.g. L3, G5, Band 4" />
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left" style={{ fontSize: 12 }}>Staffing Target</Divider>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="headcount" label={
                <Space size={4}>Headcount Target
                  <Tooltip title="Target number of people for this position. Used for vacancy and understaffing alerts.">
                    <InfoCircleOutlined style={{ color: '#8c8c8c', fontSize: 11 }} />
                  </Tooltip>
                </Space>
              } initialValue={1}>
                <InputNumber min={1} max={999} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="is_active" label="Status" initialValue={true}>
                <Select>
                  <Option value={true}>Active</Option>
                  <Option value={false}>Inactive</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left" style={{ fontSize: 12 }}>Compensation</Divider>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="salary_range_min" label="Salary Min">
                <InputNumber style={{ width: '100%' }} min={0} placeholder="Min" formatter={v => v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : ''} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="salary_range_max" label="Salary Max">
                <InputNumber style={{ width: '100%' }} min={0} placeholder="Max" formatter={v => v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : ''} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="currency" label="Currency" initialValue="USD">
                <Select showSearch>
                  {['USD','NGN','EUR','GBP','AED','ZAR','CAD','AUD','JPY','CNY'].map(c => (
                    <Option key={c} value={c}>{c}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left" style={{ fontSize: 12 }}>Requirements</Divider>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="min_experience_years" label="Min Experience (yrs)" initialValue={0}>
                <InputNumber min={0} max={50} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={16}>
              <Form.Item name="education_level" label="Education Level">
                <Input placeholder="e.g. Bachelor's in Engineering" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="required_skills" label={
                <Space size={4}>Required Skills
                  <Tooltip title={'Enter as a JSON array: ["Skill A", "Skill B"]'}>
                    <InfoCircleOutlined style={{ color: '#8c8c8c', fontSize: 11 }} />
                  </Tooltip>
                </Space>
              }>
                <Input.TextArea rows={2} placeholder='["Python", "Risk Assessment"]' />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="required_certifications" label={
                <Space size={4}>Required Certifications
                  <Tooltip title={'Enter as a JSON array: ["HUET", "BOSIET"]'}>
                    <InfoCircleOutlined style={{ color: '#8c8c8c', fontSize: 11 }} />
                  </Tooltip>
                </Space>
              }>
                <Input.TextArea rows={2} placeholder='["HUET", "BOSIET", "H2S"]' />
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left" style={{ fontSize: 12 }}>Compliance Flags</Divider>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="is_safety_critical" label="Safety Critical" initialValue={false}>
                <Select>
                  <Option value={false}>No</Option>
                  <Option value={true}>Yes — Safety Critical</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="requires_background_check" label="Background Check" initialValue={false}>
                <Select>
                  <Option value={false}>Not Required</Option>
                  <Option value={true}>Required</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left" style={{ fontSize: 12 }}>Notes</Divider>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} placeholder="Brief description of the position's responsibilities" />
          </Form.Item>
          <Form.Item name="notes" label="Internal Notes">
            <Input.TextArea rows={2} placeholder="Internal notes (not shown to employees)" />
          </Form.Item>
        </Form>
      </Modal>
      </Card>
    </div>
  );
};

export default PositionList;
