import React, { useState, useMemo } from 'react';
import {
  Tabs, Card, Table, Button, Space, Tag, App, Form, Modal, Drawer,
  Input, Select, Switch, Row, Col, Divider, Badge, Alert,
  Checkbox, Popconfirm, Typography, Statistic, Tooltip, Empty, Spin, Progress,
  Avatar, Segmented, Dropdown, Upload,
} from 'antd';
import {
  UserOutlined, TeamOutlined, LockOutlined, AuditOutlined,
  PlusOutlined, EditOutlined, DeleteOutlined, KeyOutlined,
  SafetyOutlined, BankOutlined, ReloadOutlined, CheckOutlined,
  CloseOutlined, SettingOutlined, ClockCircleOutlined,
  DatabaseOutlined, CloudServerOutlined, DownloadOutlined,
  CheckCircleOutlined, WarningOutlined, SyncOutlined,
  ApiOutlined, LinkOutlined,
  FilterOutlined, EyeOutlined, CopyOutlined, IdcardOutlined,
  InfoCircleOutlined, ThunderboltOutlined,
  MailOutlined, MoreOutlined, StopOutlined,
  SearchOutlined, DesktopOutlined, FileTextOutlined,
  BarChartOutlined, AlertOutlined, RightOutlined, GlobalOutlined,
  UploadOutlined, RollbackOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService from '../../services/api';
import EmailSetup from '../Emergency/EmailSetup';
import DatabaseTab from './DatabaseTab';
import AttendanceIdsDrawer from './AttendanceIdsDrawer';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
dayjs.extend(relativeTime);

const { Title, Text } = Typography;
const { Option } = Select;
const { Search } = Input;
const { Password } = Input;

// ── Permission module ordering / labels ──────────────────────────────────────
const MODULE_ORDER = [
  'personnel','attendance','devices','access_control',
  'visitors','reports','pob','emergency','mustering','settings',
];
const MODULE_LABEL = {
  personnel: 'Personnel', attendance: 'Attendance', devices: 'Devices',
  access_control: 'Access Control', visitors: 'Visitors', reports: 'Reports',
  pob: 'POB Status', emergency: 'Emergency', mustering: 'Mustering', settings: 'Settings',
};

// ── User helper utilities ─────────────────────────────────────────────────────
const USER_AVATAR_COLORS = [
  '#3B82F6','#10B981','#F59E0B','#EF4444','#8B5CF6',
  '#EC4899','#06B6D4','#84CC16','#F97316','#6366F1',
];
const userAvatarColor = (str = '') =>
  USER_AVATAR_COLORS[str.split('').reduce((a, c) => a + c.charCodeAt(0), 0) % USER_AVATAR_COLORS.length];

const userInitials = (u) => {
  if (u.first_name || u.last_name)
    return `${u.first_name?.[0] || ''}${u.last_name?.[0] || ''}`.toUpperCase();
  return u.username?.slice(0, 2).toUpperCase() || '??';
};

const activityBadge = (lastLogin) => {
  if (!lastLogin) return { color: '#9CA3AF', dot: '#9CA3AF', label: 'Never logged in', relative: 'Never' };
  const d = dayjs().diff(dayjs(lastLogin), 'day');
  if (d < 1)  return { color: '#22C55E', dot: '#22C55E', label: 'Active today',     relative: 'Today' };
  if (d < 7)  return { color: '#84CC16', dot: '#84CC16', label: `${d} days ago`,    relative: `${d}d ago` };
  if (d < 30) return { color: '#F59E0B', dot: '#F59E0B', label: `${d} days ago`,    relative: `${d}d ago` };
  return               { color: '#EF4444', dot: '#EF4444', label: `${d} days ago`,  relative: `${d}d ago` };
};

const pwStrength = (pw = '') => {
  let s = 0;
  if (pw.length >= 8)           s++;
  if (pw.length >= 12)          s++;
  if (/[A-Z]/.test(pw))         s++;
  if (/[0-9]/.test(pw))         s++;
  if (/[^A-Za-z0-9]/.test(pw))  s++;
  const map = [
    { label: '',            color: '#e5e7eb', pct: 0   },
    { label: 'Weak',        color: '#EF4444', pct: 20  },
    { label: 'Fair',        color: '#F59E0B', pct: 40  },
    { label: 'Moderate',    color: '#84CC16', pct: 60  },
    { label: 'Strong',      color: '#22C55E', pct: 80  },
    { label: 'Very Strong', color: '#0EA5E9', pct: 100 },
  ];
  return map[Math.min(s, 5)];
};

const genPassword = () => {
  const pool = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%^&*';
  return Array.from({ length: 14 }, () => pool[Math.floor(Math.random() * pool.length)]).join('');
};

const exportUsersCSV = (users) => {
  const header = ['Username','Full Name','Email','Roles','Status','Last Login','Joined'];
  const rows = users.map(u => [
    u.username,
    `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.username,
    u.email || '',
    (u.is_superuser ? ['Superuser'] : []).concat((u.roles || []).map(r => r.name)).join('; '),
    u.is_active ? 'Active' : 'Inactive',
    u.last_login ? dayjs(u.last_login).format('YYYY-MM-DD HH:mm') : 'Never',
    u.created_at ? dayjs(u.created_at).format('YYYY-MM-DD') : '',
  ]);
  const csv = [header, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
  const a = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
    download: `users_${dayjs().format('YYYYMMDD_HHmm')}.csv`,
  });
  a.click(); URL.revokeObjectURL(a.href);
};

// ════════════════════════════════════════════════════════════════════════════
// USERS TAB
// ════════════════════════════════════════════════════════════════════════════
const UsersTab = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();

  // ── State ─────────────────────────────────────────────────────────────────
  const [search,       setSearch]       = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [roleFilter,   setRoleFilter]   = useState(null);
  const [selectedKeys, setSelectedKeys] = useState([]);
  const [drawerOpen,   setDrawerOpen]   = useState(false);
  const [editUser,     setEditUser]     = useState(null);
  const [profileUser,  setProfileUser]  = useState(null); // side profile panel
  const [pwOpen,       setPwOpen]       = useState(false);
  const [pwUser,       setPwUser]       = useState(null);
  const [pwVal,        setPwVal]        = useState('');
  const [rolesOpen,    setRolesOpen]    = useState(false);
  const [rolesUser,    setRolesUser]    = useState(null);
  const [form]   = Form.useForm();
  const [pwForm] = Form.useForm();

  // ── Queries ───────────────────────────────────────────────────────────────
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['settings-users'],
    queryFn: () => apiService.get('/api/v1/settings/users', { page: 1, page_size: 100 }),
    staleTime: 30000,
  });
  const users = data?.data ?? data ?? [];
  const total = data?.total ?? users.length;

  const { data: rolesData } = useQuery({
    queryKey: ['settings-roles-list'],
    queryFn: () => apiService.get('/api/v1/settings/roles'),
  });
  const allRoles = rolesData || [];

  // ── Filtered data ─────────────────────────────────────────────────────────
  const filteredUsers = useMemo(() => {
    let list = [...users];
    const q = search.toLowerCase().trim();
    if (q) list = list.filter(u =>
      u.username?.toLowerCase().includes(q) ||
      u.email?.toLowerCase().includes(q) ||
      u.first_name?.toLowerCase().includes(q) ||
      u.last_name?.toLowerCase().includes(q)
    );
    if (statusFilter === 'active')   list = list.filter(u => u.is_active);
    if (statusFilter === 'inactive') list = list.filter(u => !u.is_active);
    if (statusFilter === 'super')    list = list.filter(u => u.is_superuser);
    if (statusFilter === 'norole')   list = list.filter(u => !u.is_superuser && !u.roles?.length);
    if (roleFilter) list = list.filter(u => u.roles?.some(r => r.id === roleFilter));
    return list;
  }, [users, search, statusFilter, roleFilter]);

  // ── Mutations ─────────────────────────────────────────────────────────────
  const createM = useMutation({
    mutationFn: (body) => apiService.post('/api/v1/settings/users', body),
    onSuccess: () => { message.success('User created'); qc.invalidateQueries(['settings-users']); setDrawerOpen(false); form.resetFields(); },
    onError: (e) => message.error(e?.message || 'Failed to create user'),
  });
  const updateM = useMutation({
    mutationFn: ({ id, body }) => apiService.put(`/api/v1/settings/users/${id}`, body),
    onSuccess: () => { message.success('User updated'); qc.invalidateQueries(['settings-users']); setDrawerOpen(false); },
    onError: (e) => message.error(e?.message || 'Failed to update user'),
  });
  const toggleM = useMutation({
    mutationFn: ({ id, is_active }) => apiService.put(`/api/v1/settings/users/${id}`, { is_active }),
    onSuccess: () => qc.invalidateQueries(['settings-users']),
    onError: (e) => message.error(e?.message || 'Failed'),
  });
  const deleteM = useMutation({
    mutationFn: (id) => apiService.delete(`/api/v1/settings/users/${id}`),
    onSuccess: () => { message.success('User deleted'); qc.invalidateQueries(['settings-users']); },
    onError: (e) => message.error(e?.message || 'Cannot delete user'),
  });
  const pwM = useMutation({
    mutationFn: ({ id, body }) => apiService.put(`/api/v1/settings/users/${id}/password`, body),
    onSuccess: () => { message.success('Password changed'); setPwOpen(false); pwForm.resetFields(); setPwVal(''); },
    onError: (e) => message.error(e?.message || 'Failed to change password'),
  });
  const rolesM = useMutation({
    mutationFn: ({ id, role_ids }) => apiService.put(`/api/v1/settings/users/${id}/roles`, { role_ids }),
    onSuccess: () => { message.success('Roles updated'); qc.invalidateQueries(['settings-users']); setRolesOpen(false); },
    onError: (e) => message.error(e?.message || 'Failed to update roles'),
  });

  // ── Bulk actions ──────────────────────────────────────────────────────────
  const bulkToggle = async (is_active) => {
    await Promise.all(selectedKeys.map(id => apiService.put(`/api/v1/settings/users/${id}`, { is_active })));
    qc.invalidateQueries(['settings-users']);
    setSelectedKeys([]);
    message.success(`${selectedKeys.length} user(s) ${is_active ? 'activated' : 'deactivated'}`);
  };
  const bulkDelete = async () => {
    await Promise.all(selectedKeys.map(id => apiService.delete(`/api/v1/settings/users/${id}`)));
    qc.invalidateQueries(['settings-users']);
    setSelectedKeys([]);
    message.success(`${selectedKeys.length} user(s) deleted`);
  };

  // ── Handlers ──────────────────────────────────────────────────────────────
  const openCreate = () => { setEditUser(null); form.resetFields(); setDrawerOpen(true); };
  const openEdit   = (u) => {
    setEditUser(u);
    form.setFieldsValue({ first_name: u.first_name, last_name: u.last_name, email: u.email, is_active: u.is_active, is_superuser: u.is_superuser });
    setDrawerOpen(true);
  };
  const openPw     = (u) => { setPwUser(u); pwForm.resetFields(); setPwVal(''); setPwOpen(true); };
  const openRoles  = (u) => { setRolesUser(u); setRolesOpen(true); };
  const onSave     = (vals) => editUser ? updateM.mutate({ id: editUser.id, body: vals }) : createM.mutate(vals);

  // ── Stats ─────────────────────────────────────────────────────────────────
  const activeCount  = users.filter(u => u.is_active).length;
  const superCount   = users.filter(u => u.is_superuser).length;
  const noRoleCount  = users.filter(u => !u.is_superuser && !u.roles?.length).length;
  const neverCount   = users.filter(u => !u.last_login).length;
  const recentCount  = users.filter(u => u.last_login && dayjs().diff(dayjs(u.last_login), 'day') < 7).length;

  // ── Table columns ─────────────────────────────────────────────────────────
  const cols = [
    {
      title: 'User', key: 'user', ellipsis: true, minWidth: 200,
      render: (_, r) => {
        const act = activityBadge(r.last_login);
        const color = userAvatarColor(r.username);
        const initials = userInitials(r);
        return (
          <Space
            style={{ cursor: 'pointer' }}
            onClick={() => setProfileUser(r)}
          >
            <div style={{ position: 'relative', flexShrink: 0 }}>
              <Avatar
                size={36}
                style={{ background: color, fontSize: 13, fontWeight: 700, flexShrink: 0 }}
              >
                {initials}
              </Avatar>
              <Tooltip title={act.label}>
                <div style={{
                  position: 'absolute', bottom: 0, right: 0,
                  width: 10, height: 10, borderRadius: '50%',
                  background: act.dot, border: '2px solid #fff',
                }} />
              </Tooltip>
            </div>
            <Space direction="vertical" size={0}>
              <Text strong style={{ fontSize: 13, color: '#1F2937' }}>
                {r.first_name || r.last_name ? `${r.first_name || ''} ${r.last_name || ''}`.trim() : r.username}
              </Text>
              <Text type="secondary" style={{ fontSize: 11 }}>@{r.username}</Text>
            </Space>
          </Space>
        );
      },
    },
    {
      title: 'Email', dataIndex: 'email', key: 'email', ellipsis: true,
      render: (v) => v ? (
        <Space size={4}>
          <Text style={{ fontSize: 12 }}>{v}</Text>
          <CopyOutlined
            style={{ fontSize: 10, color: '#9CA3AF', cursor: 'pointer' }}
            onClick={() => { navigator.clipboard?.writeText(v); message.success('Email copied'); }}
          />
        </Space>
      ) : <Text type="secondary">—</Text>,
    },
    {
      title: 'Roles', key: 'roles',
      render: (_, r) => (
        <Space wrap size={4}>
          {r.is_superuser && (
            <Tag color="red" style={{ fontSize: 11 }}>
              <SafetyOutlined /> Superuser
            </Tag>
          )}
          {(r.roles || []).map(rl => (
            <Tag key={rl.id} color="blue" style={{ fontSize: 11 }}>{rl.name}</Tag>
          ))}
          {!r.is_superuser && !r.roles?.length && (
            <Tooltip title="No roles assigned — this user has limited or no access">
              <Tag color="warning" icon={<WarningOutlined />} style={{ fontSize: 11 }}>
                No roles
              </Tag>
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: 'Status', key: 'status', width: 100,
      render: (_, r) => (
        <Tooltip title={r.is_superuser ? 'Cannot deactivate superuser' : (r.is_active ? 'Click to deactivate' : 'Click to activate')}>
          <Switch
            size="small"
            checked={r.is_active}
            disabled={r.is_superuser || toggleM.isPending}
            onChange={(val) => toggleM.mutate({ id: r.id, is_active: val })}
            checkedChildren="Active"
            unCheckedChildren="Off"
          />
        </Tooltip>
      ),
    },
    {
      title: 'Last Login', dataIndex: 'last_login', key: 'last_login', width: 110,
      render: (v) => {
        const act = activityBadge(v);
        return (
          <Tooltip title={v ? dayjs(v).format('DD MMM YYYY HH:mm') : 'Never logged in'}>
            <Space size={4}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: act.dot, flexShrink: 0 }} />
              <Text style={{ fontSize: 12, color: act.color }}>{act.relative}</Text>
            </Space>
          </Tooltip>
        );
      },
      sorter: (a, b) => dayjs(a.last_login || 0).unix() - dayjs(b.last_login || 0).unix(),
    },
    {
      title: 'Joined', dataIndex: 'created_at', key: 'created_at', width: 90,
      render: (v) => (
        <Tooltip title={v ? dayjs(v).format('DD MMM YYYY') : '—'}>
          <Text style={{ fontSize: 12, color: '#6B7A8D' }}>
            {v ? dayjs(v).fromNow(true) + ' ago' : '—'}
          </Text>
        </Tooltip>
      ),
      sorter: (a, b) => dayjs(a.created_at || 0).unix() - dayjs(b.created_at || 0).unix(),
    },
    {
      title: '', key: 'act', fixed: 'right', width: 120,
      render: (_, r) => (
        <Space size={4}>
          <Tooltip title="View Profile">
            <Button size="small" icon={<EyeOutlined />} onClick={() => setProfileUser(r)} />
          </Tooltip>
          <Tooltip title="Edit">
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          </Tooltip>
          <Tooltip title="Change Password">
            <Button size="small" icon={<KeyOutlined />} onClick={() => openPw(r)} />
          </Tooltip>
          <Dropdown
            trigger={['click']}
            menu={{
              items: [
                { key: 'roles',  label: 'Manage Roles',  icon: <TeamOutlined /> },
                { key: 'copy',   label: 'Copy Username', icon: <CopyOutlined /> },
                { type: 'divider' },
                { key: 'delete', label: 'Delete User', icon: <DeleteOutlined />, danger: true, disabled: r.is_superuser },
              ],
              onClick: ({ key }) => {
                if (key === 'roles')  openRoles(r);
                if (key === 'copy')   { navigator.clipboard?.writeText(r.username); message.success('Username copied'); }
                if (key === 'delete') {
                  Modal.confirm({
                    title: `Delete "${r.username}"?`,
                    content: 'This action cannot be undone.',
                    okText: 'Delete', okType: 'danger',
                    onOk: () => deleteM.mutate(r.id),
                  });
                }
              },
            }}
          >
            <Button size="small" icon={<MoreOutlined />} />
          </Dropdown>
        </Space>
      ),
    },
  ];

  const pwInfo = pwStrength(pwVal);

  return (
    <div style={{ padding: 24 }}>

      {/* ── Stats cards ─────────────────────────────────────────────────── */}
      <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
        {[
          { title: 'Total Users',      value: total,       color: '#3B82F6', bg: '#EFF6FF', icon: <UserOutlined />,       filter: 'all' },
          { title: 'Active',           value: activeCount, color: '#10B981', bg: '#F0FDF4', icon: <CheckCircleOutlined />, filter: 'active' },
          { title: 'Superusers',       value: superCount,  color: '#EF4444', bg: '#FFF1F2', icon: <SafetyOutlined />,      filter: 'super' },
          { title: 'No Role Assigned', value: noRoleCount, color: '#F59E0B', bg: '#FFFBEB', icon: <WarningOutlined />,     filter: 'norole' },
          { title: 'Never Logged In',  value: neverCount,  color: '#9CA3AF', bg: '#F9FAFB', icon: <ClockCircleOutlined />, filter: 'all' },
        ].map(s => (
          <Col xs={12} sm={12} md={8} lg={24/5} key={s.title} style={{ minWidth: 140 }}>
            <Card
              size="small"
              hoverable
              onClick={() => setStatusFilter(s.filter)}
              style={{
                borderTop: `3px solid ${s.color}`,
                cursor: 'pointer',
                background: statusFilter === s.filter ? s.bg : undefined,
                transition: 'all 0.2s',
              }}
              styles={{ body: { padding: '12px 16px' } }}
            >
              <Statistic
                title={<Text style={{ fontSize: 12 }}>{s.title}</Text>}
                value={s.value}
                prefix={s.icon}
                valueStyle={{ color: s.color, fontSize: 22 }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* ── Filter + action bar ──────────────────────────────────────────── */}
      <Card size="small" styles={{ body: { padding: '10px 14px' } }} style={{ marginBottom: 12 }}>
        <Row gutter={[10, 8]} align="middle" wrap>
          <Col>
            <Input.Search
              placeholder="Search name, username, email…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              allowClear
              style={{ width: 260 }}
              size="middle"
            />
          </Col>
          <Col>
            <Segmented
              size="middle"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { label: 'All',      value: 'all' },
                { label: 'Active',   value: 'active' },
                { label: 'Inactive', value: 'inactive' },
                { label: 'Super',    value: 'super' },
                { label: 'No Role',  value: 'norole' },
              ]}
            />
          </Col>
          <Col>
            <Select
              placeholder={<><FilterOutlined /> Filter by role</>}
              value={roleFilter}
              onChange={setRoleFilter}
              allowClear
              style={{ width: 180 }}
              options={(allRoles || []).map(r => ({ value: r.id, label: r.name }))}
            />
          </Col>
          <Col flex={1} />
          <Col>
            <Space>
              <Tooltip title="Export CSV">
                <Button icon={<DownloadOutlined />} onClick={() => exportUsersCSV(filteredUsers)}>
                  Export
                </Button>
              </Tooltip>
              <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading} />
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>New User</Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* ── Bulk action bar ──────────────────────────────────────────────── */}
      {selectedKeys.length > 0 && (
        <Card
          size="small"
          style={{ marginBottom: 12, background: '#EFF6FF', border: '1px solid #BAE0FF' }}
          styles={{ body: { padding: '8px 14px' } }}
        >
          <Row align="middle" gutter={8}>
            <Col>
              <Text strong style={{ color: '#1677ff' }}>{selectedKeys.length} user(s) selected</Text>
            </Col>
            <Col>
              <Space>
                <Button size="small" icon={<CheckCircleOutlined />} onClick={() => bulkToggle(true)}>
                  Activate
                </Button>
                <Button size="small" icon={<StopOutlined />} onClick={() => bulkToggle(false)}>
                  Deactivate
                </Button>
                <Popconfirm title={`Delete ${selectedKeys.length} user(s)?`} onConfirm={bulkDelete} okType="danger" okText="Delete All">
                  <Button size="small" danger icon={<DeleteOutlined />}>Delete</Button>
                </Popconfirm>
                <Button size="small" onClick={() => setSelectedKeys([])}>Clear</Button>
              </Space>
            </Col>
          </Row>
        </Card>
      )}

      {/* ── Users table ──────────────────────────────────────────────────── */}
      <Card styles={{ body: { padding: 0 } }}>
        <Table
          columns={cols}
          dataSource={filteredUsers}
          loading={isLoading}
          rowKey="id"
          size="middle"
          scroll={{ x: 960 }}
          rowSelection={{
            selectedRowKeys: selectedKeys,
            onChange: setSelectedKeys,
            getCheckboxProps: (r) => ({ disabled: r.is_superuser }),
          }}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showTotal: (t, [f, l]) => (
              <Text type="secondary" style={{ fontSize: 12 }}>
                Showing {f}–{l} of <strong>{t}</strong> users
                {filteredUsers.length !== users.length && ` (filtered from ${users.length})`}
              </Text>
            ),
          }}
          locale={{ emptyText: <Empty description="No users found" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        />
      </Card>

      {/* ── Create / Edit Drawer ─────────────────────────────────────────── */}
      <Drawer
        title={
          <Space>
            {editUser
              ? <><EditOutlined /> Edit User</>
              : <><PlusOutlined /> New User</>
            }
          </Space>
        }
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setEditUser(null); form.resetFields(); }}
        width={480}
        destroyOnHidden
        footer={
          <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
            <Button onClick={() => { setDrawerOpen(false); setEditUser(null); form.resetFields(); }}>
              Cancel
            </Button>
            <Button type="primary" onClick={() => form.submit()} loading={createM.isPending || updateM.isPending}>
              {editUser ? 'Save Changes' : 'Create User'}
            </Button>
          </Space>
        }
      >
        {/* Avatar preview header */}
        {(editUser || form.getFieldValue('first_name')) && (
          <div style={{ textAlign: 'center', padding: '0 0 20px' }}>
            <Avatar
              size={64}
              style={{
                background: userAvatarColor(editUser?.username || ''),
                fontSize: 24, fontWeight: 700,
              }}
            >
              {editUser ? userInitials(editUser) : '?'}
            </Avatar>
            {editUser && <div style={{ marginTop: 8, color: '#6B7A8D', fontSize: 12 }}>@{editUser.username}</div>}
          </div>
        )}

        <Form
          key={editUser ? `edit-${editUser.id}` : 'create'}
          form={form}
          layout="vertical"
          onFinish={onSave}
          initialValues={{ is_active: true, is_superuser: false }}
        >
          {/* Personal info */}
          <Divider orientation="left" orientationMargin={0} style={{ fontSize: 12, color: '#9CA3AF' }}>Personal Info</Divider>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="first_name" label="First Name">
                <Input placeholder="John" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="last_name" label="Last Name">
                <Input placeholder="Doe" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="email" label="Email" rules={[{ type: 'email', message: 'Invalid email' }]}>
            <Input prefix={<MailOutlined />} placeholder="john.doe@company.com" />
          </Form.Item>

          {/* Account */}
          <Divider orientation="left" orientationMargin={0} style={{ fontSize: 12, color: '#9CA3AF' }}>Account</Divider>
          <Form.Item
            name="username"
            label="Username"
            rules={[{ required: !editUser, message: 'Username is required' }]}
            extra={editUser ? 'Username cannot be changed after creation.' : undefined}
          >
            <Input prefix={<UserOutlined />} disabled={!!editUser} placeholder="johndoe" />
          </Form.Item>

          {!editUser && (
            <Form.Item
              name="password"
              label={
                <Space>
                  Password
                  {pwVal && (
                    <Tag color={pwInfo.pct >= 80 ? 'success' : pwInfo.pct >= 60 ? 'warning' : 'error'} style={{ fontSize: 10 }}>
                      {pwInfo.label}
                    </Tag>
                  )}
                </Space>
              }
              rules={[{ required: true, message: 'Required' }, { min: 6, message: 'Min 6 characters' }]}
            >
              <Space.Compact style={{ width: '100%' }}>
                <Input.Password
                  prefix={<LockOutlined />}
                  placeholder="Min. 6 characters"
                  value={pwVal}
                  onChange={e => { setPwVal(e.target.value); form.setFieldValue('password', e.target.value); }}
                  style={{ flex: 1 }}
                />
                <Tooltip title="Generate secure password">
                  <Button
                    icon={<ThunderboltOutlined />}
                    onClick={() => {
                      const p = genPassword();
                      setPwVal(p);
                      form.setFieldValue('password', p);
                    }}
                  />
                </Tooltip>
              </Space.Compact>
            </Form.Item>
          )}

          {!editUser && pwVal && (
            <div style={{ marginTop: -16, marginBottom: 16 }}>
              <Progress
                percent={pwInfo.pct}
                showInfo={false}
                strokeColor={pwInfo.color}
                trailColor="#e5e7eb"
                size="small"
              />
            </div>
          )}

          {/* Roles */}
          <Form.Item name="role_ids" label="Assign Roles">
            <Select
              mode="multiple"
              placeholder="Select roles (optional)"
              optionFilterProp="label"
              options={(allRoles || []).map(r => ({ value: r.id, label: r.name }))}
              allowClear
            />
          </Form.Item>

          {/* Settings */}
          <Divider orientation="left" orientationMargin={0} style={{ fontSize: 12, color: '#9CA3AF' }}>Settings</Divider>
          <Row gutter={24}>
            <Col span={12}>
              <Form.Item name="is_active" label="Account Status" valuePropName="checked">
                <Switch checkedChildren="Active" unCheckedChildren="Inactive" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="is_superuser"
                label={<Space>Superuser <Tooltip title="Superusers bypass all permission checks"><InfoCircleOutlined style={{ color: '#9CA3AF' }} /></Tooltip></Space>}
                valuePropName="checked"
              >
                <Switch checkedChildren="Yes" unCheckedChildren="No" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Drawer>

      {/* ── User Profile Side Panel ───────────────────────────────────────── */}
      <Drawer
        title={
          <Space>
            <IdcardOutlined />
            User Profile
          </Space>
        }
        open={!!profileUser}
        onClose={() => setProfileUser(null)}
        width={400}
        footer={
          profileUser && (
            <Space>
              <Button icon={<EditOutlined />} onClick={() => { openEdit(profileUser); setProfileUser(null); }}>
                Edit
              </Button>
              <Button icon={<KeyOutlined />} onClick={() => { openPw(profileUser); setProfileUser(null); }}>
                Password
              </Button>
              <Button icon={<TeamOutlined />} onClick={() => { openRoles(profileUser); setProfileUser(null); }}>
                Roles
              </Button>
            </Space>
          )
        }
      >
        {profileUser && (() => {
          const u = profileUser;
          const color = userAvatarColor(u.username);
          const act = activityBadge(u.last_login);
          return (
            <>
              {/* Profile header */}
              <div style={{ textAlign: 'center', padding: '8px 0 24px' }}>
                <div style={{ position: 'relative', display: 'inline-block' }}>
                  <Avatar size={72} style={{ background: color, fontSize: 28, fontWeight: 800 }}>
                    {userInitials(u)}
                  </Avatar>
                  <div style={{
                    position: 'absolute', bottom: 2, right: 2,
                    width: 14, height: 14, borderRadius: '50%',
                    background: act.dot, border: '2.5px solid #fff',
                  }} />
                </div>
                <div style={{ marginTop: 12, fontWeight: 700, fontSize: 17, color: '#1F2937' }}>
                  {u.first_name || u.last_name ? `${u.first_name || ''} ${u.last_name || ''}`.trim() : u.username}
                </div>
                <div style={{ color: '#9CA3AF', fontSize: 12, marginTop: 2 }}>@{u.username}</div>
                <div style={{ marginTop: 10, display: 'flex', justifyContent: 'center', gap: 6, flexWrap: 'wrap' }}>
                  {u.is_superuser && <Tag color="red" icon={<SafetyOutlined />}>Superuser</Tag>}
                  {(u.roles || []).map(r => <Tag key={r.id} color="blue">{r.name}</Tag>)}
                  {!u.is_superuser && !u.roles?.length && <Tag color="warning" icon={<WarningOutlined />}>No roles</Tag>}
                </div>
              </div>

              <Divider style={{ margin: '0 0 16px' }} />

              {/* Details */}
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', color: '#9CA3AF', textTransform: 'uppercase', marginBottom: 10 }}>Contact</div>
                {[
                  { label: 'Email', value: u.email || '—', extra: u.email && <CopyOutlined style={{ cursor: 'pointer', color: '#9CA3AF' }} onClick={() => { navigator.clipboard?.writeText(u.email); message.success('Copied'); }} /> },
                  { label: 'Username', value: `@${u.username}` },
                  { label: 'User ID', value: `#${u.id}` },
                ].map(row => (
                  <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid #f0f0f0', alignItems: 'center' }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>{row.label}</Text>
                    <Space size={6}>
                      <Text style={{ fontSize: 12, fontWeight: 500 }}>{row.value}</Text>
                      {row.extra}
                    </Space>
                  </div>
                ))}
              </div>

              {/* Security */}
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', color: '#9CA3AF', textTransform: 'uppercase', marginBottom: 10 }}>Security & Activity</div>
                {[
                  { label: 'Status',      value: u.is_active ? <Badge status="success" text="Active" /> : <Badge status="default" text="Inactive" /> },
                  { label: 'Last Login',  value: <span style={{ color: act.color }}>{act.relative === 'Never' ? 'Never logged in' : dayjs(u.last_login).format('DD MMM YYYY HH:mm')}</span> },
                  { label: 'Joined',      value: u.created_at ? dayjs(u.created_at).format('DD MMM YYYY') : '—' },
                  { label: 'Superuser',   value: u.is_superuser ? <Tag color="red">Yes</Tag> : <Tag>No</Tag> },
                ].map(row => (
                  <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid #f0f0f0', alignItems: 'center' }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>{row.label}</Text>
                    <span style={{ fontSize: 12, fontWeight: 500 }}>{row.value}</span>
                  </div>
                ))}
              </div>

              {/* Permissions summary */}
              {(u.roles?.length > 0 || u.is_superuser) && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', color: '#9CA3AF', textTransform: 'uppercase', marginBottom: 10 }}>Access</div>
                  {u.is_superuser ? (
                    <Alert type="warning" showIcon icon={<SafetyOutlined />}
                      message="Superuser — full system access, all permission checks bypassed."
                      style={{ fontSize: 12 }}
                    />
                  ) : (
                    <Space wrap size={4}>
                      {(u.roles || []).map(r => (
                        <Tag key={r.id} color="blue" style={{ fontSize: 11 }}>{r.name}</Tag>
                      ))}
                    </Space>
                  )}
                </div>
              )}
            </>
          );
        })()}
      </Drawer>

      {/* ── Change Password Modal ─────────────────────────────────────────── */}
      <Modal
        title={<Space><KeyOutlined />Change Password — <Text code>{pwUser?.username}</Text></Space>}
        open={pwOpen}
        onCancel={() => { setPwOpen(false); pwForm.resetFields(); setPwVal(''); }}
        footer={null}
        destroyOnHidden
        width={420}
      >
        <Form
          form={pwForm}
          layout="vertical"
          onFinish={v => pwM.mutate({ id: pwUser.id, body: { new_password: v.new_password } })}
        >
          <Form.Item
            name="new_password"
            label={
              <Space>
                New Password
                {pwVal && (
                  <Tag color={pwInfo.pct >= 80 ? 'success' : pwInfo.pct >= 60 ? 'warning' : 'error'} style={{ fontSize: 10 }}>
                    {pwInfo.label}
                  </Tag>
                )}
              </Space>
            }
            rules={[{ required: true, message: 'Required' }, { min: 6, message: 'Min 6 characters' }]}
          >
            <Space.Compact style={{ width: '100%' }}>
              <Input.Password
                prefix={<LockOutlined />}
                value={pwVal}
                onChange={e => { setPwVal(e.target.value); pwForm.setFieldValue('new_password', e.target.value); }}
                placeholder="Enter new password"
                style={{ flex: 1 }}
              />
              <Tooltip title="Generate password">
                <Button
                  icon={<ThunderboltOutlined />}
                  onClick={() => {
                    const p = genPassword();
                    setPwVal(p);
                    pwForm.setFieldValue('new_password', p);
                  }}
                />
              </Tooltip>
            </Space.Compact>
          </Form.Item>

          {pwVal && (
            <div style={{ marginTop: -12, marginBottom: 16 }}>
              <Progress
                percent={pwInfo.pct}
                showInfo={false}
                strokeColor={pwInfo.color}
                trailColor="#e5e7eb"
                size="small"
                style={{ marginBottom: 4 }}
              />
              <Text style={{ fontSize: 11, color: pwInfo.color }}>{pwInfo.label} password</Text>
            </div>
          )}

          <Form.Item
            name="confirm"
            label="Confirm Password"
            dependencies={['new_password']}
            rules={[
              { required: true, message: 'Please confirm' },
              ({ getFieldValue }) => ({
                validator(_, v) {
                  if (!v || getFieldValue('new_password') === v) return Promise.resolve();
                  return Promise.reject(new Error('Passwords do not match'));
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="Repeat password" />
          </Form.Item>

          <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
            <Button onClick={() => { setPwOpen(false); pwForm.resetFields(); setPwVal(''); }}>Cancel</Button>
            <Button type="primary" htmlType="submit" loading={pwM.isPending} icon={<CheckOutlined />}>
              Change Password
            </Button>
          </Space>
        </Form>
      </Modal>

      {/* ── Assign Roles Modal ────────────────────────────────────────────── */}
      <Modal
        title={<Space><TeamOutlined />Manage Roles — <Text code>{rolesUser?.username}</Text></Space>}
        open={rolesOpen}
        onCancel={() => setRolesOpen(false)}
        footer={null}
        destroyOnHidden
        width={440}
      >
        {rolesUser && (
          <RolesSelector
            allRoles={allRoles}
            currentRoles={(rolesUser.roles || []).map(r => r.id)}
            onSave={(role_ids) => rolesM.mutate({ id: rolesUser.id, role_ids })}
            onCancel={() => setRolesOpen(false)}
            loading={rolesM.isPending}
          />
        )}
      </Modal>
    </div>
  );
};

const RolesSelector = ({ allRoles, currentRoles, onSave, onCancel, loading }) => {
  const [selected, setSelected] = useState(currentRoles);
  return (
    <div>
      <Checkbox.Group value={selected} onChange={setSelected} style={{ width: '100%' }}>
        <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
          {allRoles.map(r => (
            <Checkbox key={r.id} value={r.id}>
              <Space>
                <Text strong>{r.name}</Text>
                {r.description && <Text type="secondary" style={{ fontSize: 12 }}>— {r.description}</Text>}
              </Space>
            </Checkbox>
          ))}
        </Space>
      </Checkbox.Group>
      <Divider style={{ margin: '12px 0' }} />
      <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
        <Button onClick={onCancel}>Cancel</Button>
        <Button type="primary" onClick={() => onSave(selected)} loading={loading}>Save Roles</Button>
      </Space>
    </div>
  );
};


// ── Role helpers ──────────────────────────────────────────────────────────────
const ROLE_COLORS = [
  '#3B82F6','#10B981','#8B5CF6','#EF4444','#F59E0B',
  '#EC4899','#14B8A6','#6366F1','#84CC16','#F97316',
];
const roleColor = (name = '') =>
  ROLE_COLORS[name.split('').reduce((a, c) => a + c.charCodeAt(0), 0) % ROLE_COLORS.length];

const MODULE_CONFIG = {
  personnel:      { label: 'Personnel',      color: '#3B82F6', icon: <TeamOutlined /> },
  attendance:     { label: 'Attendance',      color: '#10B981', icon: <ClockCircleOutlined /> },
  devices:        { label: 'Devices',         color: '#8B5CF6', icon: <DesktopOutlined /> },
  access_control: { label: 'Access Control',  color: '#EF4444', icon: <LockOutlined /> },
  visitors:       { label: 'Visitors',        color: '#F59E0B', icon: <IdcardOutlined /> },
  reports:        { label: 'Reports',         color: '#EC4899', icon: <FileTextOutlined /> },
  pob:            { label: 'POB Status',      color: '#14B8A6', icon: <BarChartOutlined /> },
  emergency:      { label: 'Emergency',       color: '#DC2626', icon: <AlertOutlined /> },
  mustering:      { label: 'Mustering',       color: '#6366F1', icon: <SafetyOutlined /> },
  settings:       { label: 'Settings',        color: '#64748B', icon: <SettingOutlined /> },
};

// ════════════════════════════════════════════════════════════════════════════
// ROLES & PERMISSIONS TAB
// ════════════════════════════════════════════════════════════════════════════
const RolesTab = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();

  // ── State ─────────────────────────────────────────────────────────────────
  const [selectedRole,    setSelectedRole]    = useState(null);
  const [drawerOpen,      setDrawerOpen]      = useState(false);
  const [editRole,        setEditRole]        = useState(null);
  const [roleSearch,      setRoleSearch]      = useState('');
  const [permSearch,      setPermSearch]      = useState('');
  const [expandedModules, setExpandedModules] = useState(() => new Set(MODULE_ORDER));
  const [form] = Form.useForm();

  // ── Queries ───────────────────────────────────────────────────────────────
  const { data: rolesData, isLoading: rolesLoading, refetch } = useQuery({
    queryKey: ['settings-roles'],
    queryFn: () => apiService.get('/api/v1/settings/roles'),
  });
  const roles = Array.isArray(rolesData) ? rolesData : (rolesData?.data ?? []);

  const { data: permsData, isLoading: permsLoading } = useQuery({
    queryKey: ['settings-permissions'],
    queryFn: () => apiService.get('/api/v1/settings/permissions'),
  });
  const allPerms = Array.isArray(permsData) ? permsData : (permsData?.data ?? []);

  const { data: roleDetailData, isLoading: detailLoading } = useQuery({
    queryKey: ['settings-role-detail', selectedRole],
    queryFn: () => apiService.get(`/api/v1/settings/roles/${selectedRole}`),
    enabled: !!selectedRole,
  });
  const roleDetail = roleDetailData?.data ?? roleDetailData;

  // ── Mutations ─────────────────────────────────────────────────────────────
  const createM = useMutation({
    mutationFn: (body) => apiService.post('/api/v1/settings/roles', body),
    onSuccess: () => {
      message.success('Role created');
      qc.invalidateQueries(['settings-roles']);
      setDrawerOpen(false);
      form.resetFields();
    },
    onError: (e) => {
      const msg = e?.message || 'Failed to create role';
      msg.toLowerCase().includes('already exists')
        ? form.setFields([{ name: 'name', errors: [msg] }])
        : message.error(msg);
    },
  });
  const updateM = useMutation({
    mutationFn: ({ id, body }) => apiService.put(`/api/v1/settings/roles/${id}`, body),
    onSuccess: () => {
      message.success('Role updated');
      qc.invalidateQueries(['settings-roles']);
      qc.invalidateQueries(['settings-role-detail']);
      setDrawerOpen(false);
    },
    onError: (e) => {
      const msg = e?.message || 'Failed to update role';
      msg.toLowerCase().includes('already exists')
        ? form.setFields([{ name: 'name', errors: [msg] }])
        : message.error(msg);
    },
  });
  const deleteM = useMutation({
    mutationFn: (id) => apiService.delete(`/api/v1/settings/roles/${id}`),
    onSuccess: () => { message.success('Role deleted'); qc.invalidateQueries(['settings-roles']); setSelectedRole(null); },
    onError: (e) => message.error(e?.message || 'Cannot delete role (has assigned users)'),
  });
  const permsM = useMutation({
    mutationFn: ({ id, permission_ids }) =>
      apiService.put(`/api/v1/settings/roles/${id}/permissions`, { permission_ids }),
    onSuccess: () => {
      qc.invalidateQueries(['settings-role-detail', selectedRole]);
      qc.invalidateQueries(['settings-roles']);
    },
    onError: (e) => message.error(e?.message || 'Failed to save permissions'),
  });
  const cloneM = useMutation({
    mutationFn: async ({ sourceName, permIds }) => {
      const res  = await apiService.post('/api/v1/settings/roles', {
        name: `Copy of ${sourceName}`,
        description: `Cloned from "${sourceName}"`,
      });
      const newId = res?.data?.id ?? res?.id;
      if (newId && permIds.length > 0) {
        await apiService.put(`/api/v1/settings/roles/${newId}/permissions`, { permission_ids: permIds });
      }
      return newId;
    },
    onSuccess: (newId) => {
      message.success('Role cloned');
      qc.invalidateQueries(['settings-roles']);
      if (newId) setSelectedRole(newId);
    },
    onError: (e) => message.error(e?.message || 'Clone failed'),
  });

  // ── Derived data ──────────────────────────────────────────────────────────
  const openCreate = () => { setEditRole(null); form.resetFields(); setDrawerOpen(true); };
  const openEdit   = (r) => {
    setEditRole(r);
    form.setFieldsValue({ name: r.name, description: r.description, is_active: r.is_active ?? true });
    setDrawerOpen(true);
  };

  const onSave = (v) => {
    const trimmed = v.name?.trim() ?? '';
    const conflict = roles.find(r => r.name.toLowerCase() === trimmed.toLowerCase() && r.id !== editRole?.id);
    if (conflict) { form.setFields([{ name: 'name', errors: [`"${conflict.name}" already exists`] }]); return; }
    editRole ? updateM.mutate({ id: editRole.id, body: v }) : createM.mutate(v);
  };

  const permsByModule = useMemo(() => {
    const map = {};
    allPerms.forEach(p => {
      const mod = p.module ?? p.codename?.split('.')?.[0] ?? 'other';
      if (!map[mod]) map[mod] = [];
      map[mod].push(p);
    });
    return map;
  }, [allPerms]);

  const rolePermIds = useMemo(
    () => new Set((roleDetail?.permissions || []).map(p => p.id)),
    [roleDetail],
  );

  const filteredPermsByModule = useMemo(() => {
    if (!permSearch.trim()) return permsByModule;
    const q = permSearch.toLowerCase();
    const out = {};
    Object.entries(permsByModule).forEach(([mod, perms]) => {
      const matched = perms.filter(p =>
        p.name?.toLowerCase().includes(q) ||
        p.codename?.toLowerCase().includes(q) ||
        p.description?.toLowerCase().includes(q)
      );
      if (matched.length) out[mod] = matched;
    });
    return out;
  }, [permsByModule, permSearch]);

  const grantedCount = rolePermIds.size;
  const totalPerms   = allPerms.length;
  const grantPct     = totalPerms ? Math.round((grantedCount / totalPerms) * 100) : 0;

  const togglePerm = (permId) => {
    const next = new Set(rolePermIds);
    next.has(permId) ? next.delete(permId) : next.add(permId);
    permsM.mutate({ id: selectedRole, permission_ids: [...next] });
  };

  const toggleModule = (module) => {
    const ids     = (permsByModule[module] || []).map(p => p.id);
    const allOn   = ids.every(id => rolePermIds.has(id));
    const next    = new Set(rolePermIds);
    ids.forEach(id => (allOn ? next.delete(id) : next.add(id)));
    permsM.mutate({ id: selectedRole, permission_ids: [...next] });
  };

  const toggleExpandModule = (mod) => {
    setExpandedModules(prev => {
      const s = new Set(prev);
      s.has(mod) ? s.delete(mod) : s.add(mod);
      return s;
    });
  };

  const filteredRoles = roleSearch.trim()
    ? roles.filter(r =>
        r.name.toLowerCase().includes(roleSearch.toLowerCase()) ||
        r.description?.toLowerCase().includes(roleSearch.toLowerCase())
      )
    : roles;

  // stats
  const unassignedRoles = roles.filter(r => !r.user_count).length;
  const emptyRoles      = roles.filter(r => !r.permission_count).length;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{ padding: 24 }}>

      {/* ── Stats mini row ──────────────────────────────────────────────── */}
      <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
        {[
          { label: 'Total Roles',        value: roles.length,     color: '#3B82F6', icon: <TeamOutlined /> },
          { label: 'Total Permissions',  value: totalPerms,       color: '#10B981', icon: <LockOutlined /> },
          { label: 'No Users Assigned',  value: unassignedRoles,  color: '#F59E0B', icon: <WarningOutlined /> },
          { label: 'No Permissions Set', value: emptyRoles,       color: '#EF4444', icon: <StopOutlined /> },
        ].map(s => (
          <Col xs={12} md={6} key={s.label}>
            <Card size="small" styles={{ body: { padding: '10px 16px' } }} style={{ borderTop: `3px solid ${s.color}` }}>
              <Statistic
                title={<Text style={{ fontSize: 12 }}>{s.label}</Text>}
                value={s.value}
                prefix={<span style={{ color: s.color }}>{s.icon}</span>}
                valueStyle={{ color: s.color, fontSize: 22 }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16}>
        {/* ── Left: Role list ───────────────────────────────────────────── */}
        <Col xs={24} lg={8}>
          <Card
            styles={{ body: { padding: 0 } }}
            title={
              <Space>
                <TeamOutlined />
                <span>Roles</span>
                <Tag>{roles.length}</Tag>
              </Space>
            }
            extra={
              <Button type="primary" size="small" icon={<PlusOutlined />} onClick={openCreate}>
                New Role
              </Button>
            }
          >
            {/* Search */}
            <div style={{ padding: '10px 12px', borderBottom: '1px solid #f0f0f0' }}>
              <Input
                prefix={<SearchOutlined style={{ color: '#9CA3AF' }} />}
                placeholder="Search roles…"
                value={roleSearch}
                onChange={e => setRoleSearch(e.target.value)}
                allowClear
                size="small"
              />
            </div>

            {/* Role cards */}
            <div style={{ maxHeight: 560, overflowY: 'auto' }}>
              {rolesLoading ? (
                <div style={{ padding: 32, textAlign: 'center' }}><Spin /></div>
              ) : filteredRoles.length === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No roles found" style={{ padding: 24 }} />
              ) : (
                filteredRoles.map(r => {
                  const color    = roleColor(r.name);
                  const isActive = selectedRole === r.id;
                  return (
                    <div
                      key={r.id}
                      onClick={() => setSelectedRole(r.id)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '11px 14px',
                        borderLeft: `4px solid ${isActive ? color : 'transparent'}`,
                        background: isActive ? `${color}0e` : 'transparent',
                        borderBottom: '1px solid #f5f5f5',
                        cursor: 'pointer', transition: 'all 0.15s',
                      }}
                      onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = '#fafafa'; }}
                      onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
                    >
                      <Avatar
                        size={36}
                        style={{ background: color, fontSize: 13, fontWeight: 800, flexShrink: 0 }}
                      >
                        {r.name.slice(0, 2).toUpperCase()}
                      </Avatar>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontWeight: 600, fontSize: 13,
                          color: isActive ? color : '#1F2937',
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        }}>
                          {r.name}
                          {r.is_active === false && (
                            <Tag color="default" style={{ marginLeft: 6, fontSize: 9 }}>INACTIVE</Tag>
                          )}
                        </div>
                        <div style={{
                          fontSize: 11, color: '#9CA3AF', marginTop: 2,
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        }}>
                          {r.description || 'No description'}
                        </div>
                        <Space size={4} style={{ marginTop: 5 }}>
                          <Tag style={{ fontSize: 10, padding: '0 5px' }}>
                            <UserOutlined /> {r.user_count ?? 0} users
                          </Tag>
                          <Tag color="blue" style={{ fontSize: 10, padding: '0 5px' }}>
                            <LockOutlined /> {r.permission_count ?? 0} perms
                          </Tag>
                        </Space>
                      </div>
                      <Dropdown
                        trigger={['click']}
                        menu={{
                          items: [
                            { key: 'edit',   label: 'Edit',        icon: <EditOutlined /> },
                            { key: 'clone',  label: 'Clone Role',  icon: <CopyOutlined />, disabled: cloneM.isPending },
                            { type: 'divider' },
                            {
                              key: 'delete', label: 'Delete', icon: <DeleteOutlined />, danger: true,
                              disabled: (r.user_count ?? 0) > 0,
                            },
                          ],
                          onClick: ({ key, domEvent }) => {
                            domEvent.stopPropagation();
                            if (key === 'edit') openEdit(r);
                            if (key === 'clone') {
                              setSelectedRole(r.id);
                              cloneM.mutate({ sourceName: r.name, permIds: Array.from(rolePermIds) });
                            }
                            if (key === 'delete') {
                              Modal.confirm({
                                title: `Delete role "${r.name}"?`,
                                content: (r.user_count ?? 0) > 0
                                  ? 'This role has assigned users and cannot be deleted.'
                                  : 'This action cannot be undone.',
                                okText: 'Delete', okType: 'danger',
                                onOk: () => deleteM.mutate(r.id),
                              });
                            }
                          },
                        }}
                      >
                        <Button
                          type="text"
                          size="small"
                          icon={<MoreOutlined />}
                          onClick={e => e.stopPropagation()}
                          style={{ flexShrink: 0 }}
                        />
                      </Dropdown>
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        </Col>

        {/* ── Right: Permission matrix ───────────────────────────────────── */}
        <Col xs={24} lg={16}>
          <Card styles={{ body: { padding: '16px 18px' } }}>
            {!selectedRole ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <Space direction="vertical" size={4}>
                    <Text>Click a role on the left to view and manage its permissions</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      Or create a new role using the "New Role" button
                    </Text>
                  </Space>
                }
                style={{ padding: '60px 0' }}
              />
            ) : detailLoading || permsLoading ? (
              <div style={{ textAlign: 'center', padding: 48 }}><Spin size="large" /></div>
            ) : (
              <>
                {/* Role header */}
                {roleDetail && (() => {
                  const rc = roleColor(roleDetail.name);
                  return (
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 14,
                      padding: '0 0 14px', marginBottom: 14,
                      borderBottom: '1px solid #f0f0f0',
                    }}>
                      <Avatar size={48} style={{ background: rc, fontSize: 18, fontWeight: 800, flexShrink: 0 }}>
                        {roleDetail.name?.slice(0, 2).toUpperCase()}
                      </Avatar>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 700, fontSize: 16, color: '#1F2937' }}>{roleDetail.name}</div>
                        {roleDetail.description && (
                          <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 2 }}>{roleDetail.description}</div>
                        )}
                        <Space size={6} style={{ marginTop: 6 }}>
                          <Tag icon={<UserOutlined />}>{roleDetail.user_count ?? 0} users</Tag>
                          <Tag icon={<LockOutlined />} color="blue">{grantedCount} / {totalPerms} permissions</Tag>
                          <Tag color={grantPct >= 80 ? 'success' : grantPct >= 40 ? 'warning' : 'default'}>
                            {grantPct}% access
                          </Tag>
                        </Space>
                      </div>
                      <Space>
                        <Tooltip title="Clone this role with all its permissions">
                          <Button
                            size="small"
                            icon={<CopyOutlined />}
                            loading={cloneM.isPending}
                            onClick={() => cloneM.mutate({ sourceName: roleDetail.name, permIds: [...rolePermIds] })}
                          >
                            Clone
                          </Button>
                        </Tooltip>
                        <Button
                          size="small"
                          icon={<EditOutlined />}
                          onClick={() => openEdit(roles.find(r => r.id === selectedRole) || roleDetail)}
                        >
                          Edit
                        </Button>
                      </Space>
                    </div>
                  );
                })()}

                {/* Overall progress */}
                <div style={{ marginBottom: 14 }}>
                  <Progress
                    percent={grantPct}
                    format={p => <Text style={{ fontSize: 11 }}>{grantedCount}/{totalPerms} granted</Text>}
                    strokeColor={{ '0%': '#3B82F6', '100%': '#10B981' }}
                    size="small"
                    status={permsM.isPending ? 'active' : undefined}
                  />
                </div>

                {/* Search + bulk controls */}
                <Row gutter={8} style={{ marginBottom: 14 }} align="middle">
                  <Col flex={1}>
                    <Input
                      prefix={<SearchOutlined style={{ color: '#9CA3AF' }} />}
                      placeholder="Search permissions…"
                      value={permSearch}
                      onChange={e => setPermSearch(e.target.value)}
                      allowClear
                      size="small"
                    />
                  </Col>
                  <Col>
                    <Space>
                      <Button
                        size="small"
                        icon={<CheckCircleOutlined />}
                        onClick={() => permsM.mutate({ id: selectedRole, permission_ids: allPerms.map(p => p.id) })}
                        loading={permsM.isPending}
                      >
                        All
                      </Button>
                      <Button
                        size="small"
                        icon={<CloseOutlined />}
                        onClick={() => permsM.mutate({ id: selectedRole, permission_ids: [] })}
                        loading={permsM.isPending}
                      >
                        None
                      </Button>
                      <Button
                        size="small"
                        onClick={() => setExpandedModules(new Set(MODULE_ORDER))}
                      >
                        Expand All
                      </Button>
                      <Button
                        size="small"
                        onClick={() => setExpandedModules(new Set())}
                      >
                        Collapse
                      </Button>
                    </Space>
                  </Col>
                </Row>

                {/* Module sections */}
                {allPerms.length === 0 ? (
                  <Empty description="No permissions configured in the system." />
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {MODULE_ORDER.map(mod => {
                      const cfg      = MODULE_CONFIG[mod] || { label: mod, color: '#9CA3AF', icon: <GlobalOutlined /> };
                      const perms    = filteredPermsByModule[mod];
                      if (!perms || perms.length === 0) return null;
                      const modGranted  = perms.filter(p => rolePermIds.has(p.id)).length;
                      const allOn       = modGranted === perms.length;
                      const someOn      = modGranted > 0 && !allOn;
                      const modPct      = Math.round((modGranted / perms.length) * 100);
                      const isExpanded  = expandedModules.has(mod);

                      return (
                        <div
                          key={mod}
                          style={{
                            border: '1px solid #f0f0f0', borderRadius: 8,
                            overflow: 'hidden',
                          }}
                        >
                          {/* Module header */}
                          <div
                            onClick={() => toggleExpandModule(mod)}
                            style={{
                              display: 'flex', alignItems: 'center', gap: 10,
                              padding: '10px 14px',
                              background: isExpanded ? `${cfg.color}0a` : '#fafafa',
                              borderLeft: `4px solid ${cfg.color}`,
                              cursor: 'pointer',
                              userSelect: 'none',
                            }}
                          >
                            <span style={{ color: cfg.color, fontSize: 16 }}>{cfg.icon}</span>
                            <span style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>{cfg.label}</span>
                            <Tag
                              color={allOn ? 'success' : someOn ? 'warning' : 'default'}
                              style={{ fontSize: 10 }}
                            >
                              {modGranted}/{perms.length}
                            </Tag>
                            <div style={{ width: 56 }}>
                              <Progress
                                percent={modPct}
                                showInfo={false}
                                size="small"
                                strokeColor={cfg.color}
                              />
                            </div>
                            <Checkbox
                              checked={allOn}
                              indeterminate={someOn}
                              onClick={e => e.stopPropagation()}
                              onChange={() => toggleModule(mod)}
                              style={{ flexShrink: 0 }}
                            />
                            <RightOutlined
                              style={{
                                fontSize: 10, color: '#9CA3AF',
                                transform: isExpanded ? 'rotate(90deg)' : 'rotate(0)',
                                transition: 'transform 0.2s',
                                flexShrink: 0,
                              }}
                            />
                          </div>

                          {/* Permission list */}
                          {isExpanded && (
                            <div style={{ padding: '10px 14px 12px', borderTop: '1px solid #f0f0f0' }}>
                              <Row gutter={[8, 6]}>
                                {perms.map(p => (
                                  <Col xs={24} sm={12} key={p.id}>
                                    <div style={{
                                      display: 'flex', alignItems: 'flex-start', gap: 8,
                                      padding: '6px 8px', borderRadius: 6,
                                      background: rolePermIds.has(p.id) ? `${cfg.color}0a` : 'transparent',
                                      border: `1px solid ${rolePermIds.has(p.id) ? cfg.color + '30' : 'transparent'}`,
                                      transition: 'all 0.15s',
                                    }}>
                                      <Checkbox
                                        checked={rolePermIds.has(p.id)}
                                        onChange={() => togglePerm(p.id)}
                                        disabled={permsM.isPending}
                                        style={{ marginTop: 1, flexShrink: 0 }}
                                      />
                                      <div style={{ minWidth: 0 }}>
                                        <div style={{ fontSize: 12, fontWeight: 500, color: '#1F2937', lineHeight: 1.3 }}>
                                          {p.name}
                                        </div>
                                        <div style={{ fontSize: 10, color: '#9CA3AF', fontFamily: 'monospace', marginTop: 1 }}>
                                          {p.codename}
                                        </div>
                                        {p.description && (
                                          <div style={{ fontSize: 10, color: '#B8BCC5', marginTop: 2, lineHeight: 1.4 }}>
                                            {p.description}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  </Col>
                                ))}
                              </Row>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </Card>
        </Col>
      </Row>

      {/* ── Create / Edit Drawer ─────────────────────────────────────────── */}
      <Drawer
        title={
          <Space>
            {editRole ? <EditOutlined /> : <PlusOutlined />}
            {editRole ? `Edit Role — ${editRole.name}` : 'New Role'}
          </Space>
        }
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setEditRole(null); form.resetFields(); }}
        width={420}
        destroyOnHidden
        footer={
          <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
            <Button onClick={() => { setDrawerOpen(false); setEditRole(null); form.resetFields(); }}>
              Cancel
            </Button>
            <Button type="primary" onClick={() => form.submit()} loading={createM.isPending || updateM.isPending}>
              {editRole ? 'Save Changes' : 'Create Role'}
            </Button>
          </Space>
        }
      >
        {/* Avatar preview */}
        <div style={{ textAlign: 'center', padding: '4px 0 20px' }}>
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.name !== cur.name}>
            {({ getFieldValue }) => {
              const name = editRole?.name || getFieldValue('name') || '';
              const rc   = roleColor(name);
              return (
                <Avatar size={56} style={{ background: rc, fontSize: 20, fontWeight: 800 }}>
                  {name ? name.slice(0, 2).toUpperCase() : '?'}
                </Avatar>
              );
            }}
          </Form.Item>
        </div>

        <Form
          key={editRole ? `edit-${editRole.id}` : 'create'}
          form={form}
          layout="vertical"
          onFinish={onSave}
          initialValues={{ is_active: true }}
        >
          <Form.Item
            name="name"
            label="Role Name"
            rules={[{ required: true, message: 'Role name is required' }]}
          >
            <Input
              prefix={<TeamOutlined style={{ color: '#9CA3AF' }} />}
              placeholder="e.g. Site Manager, HR Officer"
              onChange={() => form.validateFields(['name'])}
            />
          </Form.Item>

          <Form.Item name="description" label="Description">
            <Input.TextArea
              rows={3}
              placeholder="Describe the responsibilities and scope of this role…"
              showCount
              maxLength={255}
            />
          </Form.Item>

          <Divider orientation="left" orientationMargin={0} style={{ fontSize: 12, color: '#9CA3AF' }}>Settings</Divider>
          <Form.Item
            name="is_active"
            label={
              <Space>
                Status
                <Tooltip title="Inactive roles cannot be assigned to new users">
                  <InfoCircleOutlined style={{ color: '#9CA3AF' }} />
                </Tooltip>
              </Space>
            }
            valuePropName="checked"
          >
            <Switch checkedChildren="Active" unCheckedChildren="Inactive" />
          </Form.Item>

          {editRole && (
            <Alert
              type="info"
              showIcon
              message={`${editRole.user_count ?? 0} user(s) currently have this role.`}
              style={{ marginTop: 8 }}
            />
          )}
        </Form>
      </Drawer>
    </div>
  );
};


// ════════════════════════════════════════════════════════════════════════════
// COMPANY TAB
// ════════════════════════════════════════════════════════════════════════════
const CompanyTab = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [editing, setEditing] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['settings-company'],
    queryFn: () => apiService.get('/api/v1/settings/company'),
  });
  const company = data || {};

  React.useEffect(() => {
    if (company.id) form.setFieldsValue(company);
  }, [company.id]);

  const updateM = useMutation({
    mutationFn: (body) => apiService.put('/api/v1/settings/company', body),
    onSuccess: () => {
      message.success('Company settings saved');
      qc.invalidateQueries(['settings-company']);
      setEditing(false);
    },
    onError: (e) => message.error(e?.message ||'Failed to save'),
  });

  return (
    <div style={{ padding: 24, maxWidth: 800 }}>
      <Card
        title={<Space><BankOutlined />Company Information</Space>}
        extra={
          editing
            ? <Space>
                <Button icon={<CloseOutlined />} onClick={() => { setEditing(false); form.setFieldsValue(company); }}>Cancel</Button>
                <Button type="primary" icon={<CheckOutlined />} loading={updateM.isPending} onClick={() => form.submit()}>Save</Button>
              </Space>
            : <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>Edit</Button>
        }
        loading={isLoading}
      >
        <Form form={form} layout="vertical" onFinish={v => updateM.mutate(v)}>
          <Row gutter={16}>
            <Col xs={24} sm={16}>
              <Form.Item name="name" label="Company Name" rules={[{ required: true }]}>
                <Input disabled={!editing} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item name="short_name" label="Short Name">
                <Input disabled={!editing} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item name="industry" label="Industry">
                <Input disabled={!editing} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item name="country" label="Country">
                <Input disabled={!editing} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item name="city" label="City">
                <Input disabled={!editing} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item name="state" label="State / Province">
                <Input disabled={!editing} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item name="phone" label="Phone">
                <Input disabled={!editing} />
              </Form.Item>
            </Col>
            <Col xs={24}>
              <Form.Item name="address" label="Address">
                <Input.TextArea rows={2} disabled={!editing} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item name="email" label="Email">
                <Input disabled={!editing} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item name="website" label="Website">
                <Input disabled={!editing} />
              </Form.Item>
            </Col>
          </Row>
          <Divider orientation="left" style={{ fontSize: 13 }}>System Preferences</Divider>
          <Row gutter={16}>
            <Col xs={24} sm={8}>
              <Form.Item name="timezone" label="Timezone">
                <Select disabled={!editing} showSearch>
                  {['Africa/Lagos','UTC','Africa/Nairobi','Europe/London','America/New_York','Asia/Dubai'].map(tz => (
                    <Option key={tz} value={tz}>{tz}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item name="date_format" label="Date Format">
                <Select disabled={!editing}>
                  <Option value="DD/MM/YYYY">DD/MM/YYYY</Option>
                  <Option value="MM/DD/YYYY">MM/DD/YYYY</Option>
                  <Option value="YYYY-MM-DD">YYYY-MM-DD</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item name="time_format" label="Time Format">
                <Select disabled={!editing}>
                  <Option value="24h">24-hour</Option>
                  <Option value="12h">12-hour</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Card>
    </div>
  );
};


// ════════════════════════════════════════════════════════════════════════════
// AUDIT LOG TAB
// ════════════════════════════════════════════════════════════════════════════
const AuditLogTab = () => {
  const [search, setSearch] = useState('');
  const [page, setPage]     = useState(1);
  const pageSize = 50;

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['settings-audit', search, page],
    queryFn: () => {
      const p = new URLSearchParams({ page, page_size: pageSize });
      if (search) p.append('search', search);
      return apiService.get(`/api/v1/settings/audit-log?${p}`);
    },
  });
  const rows  = data?.data  || [];
  const total = data?.total || 0;

  const ACTION_COLOR = { CREATE: 'green', UPDATE: 'blue', DELETE: 'red', LOGIN: 'cyan', LOGOUT: 'default' };

  const cols = [
    {
      title: 'Time', dataIndex: 'created_at', key: 'time', width: 160,
      render: v => v ? dayjs(v).format('DD MMM YYYY HH:mm:ss') : '—',
    },
    {
      title: 'User', key: 'user', width: 140,
      render: (_, r) => r.username
        ? <Space direction="vertical" size={0}>
            <Text strong style={{ fontSize: 12 }}>
              {r.first_name || r.last_name ? `${r.first_name||''} ${r.last_name||''}`.trim() : r.username}
            </Text>
            <Text type="secondary" style={{ fontSize: 10 }}>@{r.username}</Text>
          </Space>
        : '—',
    },
    {
      title: 'Action', dataIndex: 'action', key: 'action', width: 90,
      render: v => <Tag color={ACTION_COLOR[v?.toUpperCase()] || 'default'}>{v}</Tag>,
    },
    { title: 'Table',      dataIndex: 'table_name', key: 'table', width: 140, render: v => v || '—' },
    { title: 'Record ID',  dataIndex: 'record_id',  key: 'rec',   width: 90 },
    { title: 'IP Address', dataIndex: 'ip_address', key: 'ip',    width: 120, render: v => v || '—' },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card styles={{ body: { padding: '12px 16px' } }} style={{ marginBottom: 16 }}>
        <Row gutter={[12, 8]} align="middle">
          <Col flex={1}>
            <Search placeholder="Search by user, action, table…" value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              onSearch={v => { setSearch(v); setPage(1); }} allowClear style={{ maxWidth: 360 }} />
          </Col>
          <Col><Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading}>Refresh</Button></Col>
        </Row>
      </Card>
      <Card styles={{ body: { padding: 0 } }}>
        <Table columns={cols} dataSource={rows} loading={isLoading} rowKey="id" size="small"
          scroll={{ x: 900 }}
          pagination={{ current: page, pageSize, total, onChange: setPage, showTotal: (t, r) => `${r[0]}–${r[1]} of ${t}` }} />
      </Card>
    </div>
  );
};


// ════════════════════════════════════════════════════════════════════════════
// MAIN SETTINGS PAGE
// ════════════════════════════════════════════════════════════════════════════
// ════════════════════════════════════════════════════════════════════════════
// SECURITY TAB
// ════════════════════════════════════════════════════════════════════════════

const TIMEOUT_PRESETS = [
  { label: '30 minutes',  value: 30 },
  { label: '1 hour',      value: 60 },
  { label: '4 hours',     value: 240 },
  { label: '8 hours',     value: 480 },
  { label: '12 hours',    value: 720 },
  { label: '24 hours',    value: 1440 },
  { label: '7 days',      value: 10080 },
  { label: '30 days',     value: 43200 },
  { label: 'Never (monitoring / 24-7 dashboards)', value: 0 },
];

const SecurityTab = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [customMode, setCustomMode] = useState(false);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['settings-security'],
    queryFn: () => apiService.get('/api/v1/settings/security'),
  });

  React.useEffect(() => {
    if (data) {
      const mins = data?.session_timeout_minutes ?? 480;
      const isPreset = TIMEOUT_PRESETS.some(p => p.value === mins);
      setCustomMode(!isPreset);
      form.setFieldsValue({ timeout_preset: isPreset ? mins : '__custom__', timeout_custom: isPreset ? undefined : mins });
    }
  }, [data]);

  const saveM = useMutation({
    mutationFn: (mins) => apiService.put('/api/v1/settings/security', { session_timeout_minutes: mins }),
    onSuccess: (_, mins) => {
      const label = mins === 0 ? 'Never' : mins >= 1440
        ? `${Math.round(mins / 1440)} day(s)`
        : mins >= 60 ? `${Math.round(mins / 60)} hour(s)` : `${mins} minute(s)`;
      message.success(`Session timeout set to: ${label}. Users must log in again for the new timeout to take effect.`);
      qc.invalidateQueries(['settings-security']);
    },
    onError: (e) => message.error(e?.message || 'Failed to save'),
  });

  const submit = () => form.validateFields().then((v) => {
    const mins = v.timeout_preset === '__custom__' ? Number(v.timeout_custom) : Number(v.timeout_preset);
    saveM.mutate(mins);
  }).catch(() => {});

  const currentMins = data?.session_timeout_minutes ?? 480;
  const currentLabel = currentMins === 0
    ? 'Never expires'
    : currentMins >= 43200 ? `${Math.round(currentMins / 1440)} days`
    : currentMins >= 1440 ? `${Math.round(currentMins / 1440)} day(s)`
    : currentMins >= 60 ? `${Math.round(currentMins / 60)} hour(s)`
    : `${currentMins} minutes`;

  return (
    <div style={{ padding: 24, maxWidth: 720 }}>
      <Card
        styles={{ body: { padding: '12px 16px' } }}
        style={{ marginBottom: 16 }}
      >
        <Row align="middle" justify="space-between">
          <Col>
            <Space>
              <ClockCircleOutlined style={{ color: '#722ed1', fontSize: 16 }} />
              <span style={{ fontWeight: 600, fontSize: 15 }}>Session Timeout</span>
              <Tag color={currentMins === 0 ? 'green' : 'blue'} style={{ marginLeft: 8 }}>
                Current: {currentLabel}
              </Tag>
            </Space>
          </Col>
          <Col>
            <Button icon={<ReloadOutlined />} size="small" onClick={() => qc.invalidateQueries(['settings-security'])} loading={isLoading}>
              Reload
            </Button>
          </Col>
        </Row>
      </Card>

      <Card styles={{ body: { padding: '20px 24px' } }}>
        <Divider orientation="left" style={{ marginTop: 0 }}>
          <Space><ClockCircleOutlined />Configure Session Timeout</Space>
        </Divider>

        <div style={{ background: '#f6f8fa', border: '1px solid #e8ecf0', borderRadius: 8, padding: '12px 16px', marginBottom: 20, fontSize: 13, color: '#555' }}>
          This setting controls how long a user stays logged in before the system requires them to log in again.
          Set to <strong>Never</strong> for 24/7 monitoring stations or dashboards that must stay active indefinitely.
          Changes apply to the <em>next login</em> — existing sessions are not affected.
        </div>

        <Form form={form} layout="vertical">
          <Form.Item name="timeout_preset" label="Session Timeout Duration">
            <Select
              size="middle"
              style={{ width: 380 }}
              onChange={(v) => setCustomMode(v === '__custom__')}
              placeholder="Select a timeout duration"
            >
              {TIMEOUT_PRESETS.map(p => (
                <Option key={p.value} value={p.value}>{p.label}</Option>
              ))}
              <Option value="__custom__">Custom (enter minutes)</Option>
            </Select>
          </Form.Item>

          {customMode && (
            <Form.Item
              name="timeout_custom"
              label="Custom Timeout (minutes)"
              rules={[{ required: true, message: 'Enter number of minutes' }, { type: 'number', min: 1, max: 525960, message: 'Must be between 1 and 525960' }]}
            >
              <Input type="number" min={1} max={525960} style={{ width: 200 }} addonAfter="min" placeholder="e.g. 360 for 6 hours" />
            </Form.Item>
          )}

          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" onClick={submit} loading={saveM.isPending} icon={<CheckOutlined />}>
              Save Timeout Setting
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <MFAPanel />
    </div>
  );
};


// ════════════════════════════════════════════════════════════════════════════
// MFA PANEL — rendered inside SecurityTab
// ════════════════════════════════════════════════════════════════════════════
const MFAPanel = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [step, setStep] = useState('idle'); // idle | setup | verify | enabled
  const [qrData, setQrData] = useState(null);
  const [secret, setSecret] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);

  const { data: mfaStatus, isLoading: statusLoading } = useQuery({
    queryKey: ['mfa-status'],
    queryFn: () => apiService.get('/api/v1/mfa/status'),
    staleTime: 60000,
  });
  const isEnabled = mfaStatus?.mfa_enabled ?? false;

  const beginSetup = async () => {
    setLoading(true);
    try {
      const res = await apiService.post('/api/v1/mfa/setup/begin', {});
      setQrData(res.qr_code);
      setSecret(res.secret);
      setStep('setup');
    } catch (e) { message.error(e?.message || 'Failed to start MFA setup'); }
    finally { setLoading(false); }
  };

  const verifyCode = async () => {
    setLoading(true);
    try {
      await apiService.post('/api/v1/mfa/setup/verify', { code });
      message.success('2FA activated!');
      qc.invalidateQueries(['mfa-status']);
      setStep('idle'); setCode('');
    } catch (e) { message.error(e?.message || 'Invalid code'); }
    finally { setLoading(false); }
  };

  const disableMFA = async () => {
    setLoading(true);
    try {
      await apiService.delete('/api/v1/mfa/disable', { data: { code } });
      message.success('2FA disabled');
      qc.invalidateQueries(['mfa-status']);
      setStep('idle'); setCode('');
    } catch (e) { message.error(e?.message || 'Invalid code'); }
    finally { setLoading(false); }
  };

  if (statusLoading) return <Spin />;

  return (
    <Card
      title={<Space><SafetyOutlined style={{ color: '#7C3AED' }} />Two-Factor Authentication (TOTP)</Space>}
      styles={{ body: { padding: '20px 24px' } }}
      style={{ marginTop: 16, borderTop: '3px solid #7C3AED' }}
    >
      {isEnabled ? (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Alert
            type="success" showIcon
            message="2FA is active"
            description="Your account is protected by a TOTP authenticator app."
          />
          {step === 'idle' ? (
            <Button danger icon={<StopOutlined />} onClick={() => setStep('disable')}>
              Disable 2FA
            </Button>
          ) : (
            <Space direction="vertical" style={{ maxWidth: 360 }}>
              <Text>Enter your authenticator code to confirm disabling 2FA:</Text>
              <Space.Compact>
                <Input
                  value={code} onChange={e => setCode(e.target.value)}
                  placeholder="6-digit code" maxLength={6}
                  onPressEnter={disableMFA}
                  style={{ width: 180 }}
                />
                <Button danger loading={loading} onClick={disableMFA}>Confirm Disable</Button>
              </Space.Compact>
              <Button size="small" onClick={() => { setStep('idle'); setCode(''); }}>Cancel</Button>
            </Space>
          )}
        </Space>
      ) : step === 'idle' ? (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Alert
            type="warning" showIcon
            message="2FA not enabled"
            description="Enable two-factor authentication to add an extra layer of security to your account."
          />
          <Button type="primary" icon={<SafetyOutlined />} loading={loading} onClick={beginSetup}>
            Set Up 2FA
          </Button>
        </Space>
      ) : step === 'setup' ? (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Alert type="info" showIcon
            message="Scan the QR code with your authenticator app (Google Authenticator, Authy, etc.), then enter the code below."
          />
          {qrData && (
            <img src={qrData} alt="TOTP QR Code"
              style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 8, maxWidth: 200 }} />
          )}
          <div>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              Manual key (if QR doesn't work):
            </Text>
            <Text code style={{ fontSize: 11 }}>{secret}</Text>
          </div>
          <Space.Compact>
            <Input
              value={code} onChange={e => setCode(e.target.value)}
              placeholder="Enter 6-digit code" maxLength={6}
              onPressEnter={verifyCode}
              style={{ width: 200 }}
            />
            <Button type="primary" loading={loading} onClick={verifyCode} icon={<CheckOutlined />}>
              Activate
            </Button>
          </Space.Compact>
          <Button size="small" onClick={() => { setStep('idle'); setCode(''); }}>Cancel</Button>
        </Space>
      ) : null}
    </Card>
  );
};


// ════════════════════════════════════════════════════════════════════════════
// BACKUP TAB
// ════════════════════════════════════════════════════════════════════════════
const BackupTab = () => {
  const { message: msg, modal } = App.useApp();
  const queryClient = useQueryClient();
  const [triggering, setTriggering] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [uploading, setUploading] = useState(false);

  const { data: statusRaw, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
    queryKey: ['backup-status'],
    queryFn:  () => apiService.get('/api/v1/backup/status'),
    refetchInterval: 30_000,
  });

  const { data: listRaw, isLoading: listLoading, refetch: refetchList } = useQuery({
    queryKey: ['backup-list'],
    queryFn:  () => apiService.get('/api/v1/backup/list'),
    refetchInterval: 60_000,
  });

  const status  = statusRaw  || {};
  const backups = listRaw?.backups || [];

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      const data = await apiService.post('/api/v1/backup/trigger');
      msg.success(`Backup completed: ${data.filename} (${data.size})`);
      queryClient.invalidateQueries({ queryKey: ['backup-list'] });
      queryClient.invalidateQueries({ queryKey: ['backup-status'] });
    } catch (e) {
      msg.error(e.message);
    } finally {
      setTriggering(false);
    }
  };

  const handleDownload = async (filename) => {
    let objectUrl = null;
    try {
      const blob = await apiService.downloadFile(`/api/v1/backup/download/${encodeURIComponent(filename)}`);
      objectUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl; a.download = filename; a.click();
    } catch (e) {
      msg.error(e.message || 'Download failed');
    } finally {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    }
  };

  const handleRestore = (filename) => {
    modal.confirm({
      title: 'Restore this backup?',
      icon: <ExclamationCircleOutlined style={{ color: '#cf1322' }} />,
      width: 540,
      content: (
        <div>
          <Alert
            type="error"
            showIcon
            style={{ margin: '12px 0' }}
            message="This replaces ALL current data"
            description={
              <span>
                The database will be overwritten with the contents of{' '}
                <Text code>{filename}</Text>. Current users, personnel, attendance and
                every other record are replaced.
              </span>
            }
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            A safety backup of the current database is taken automatically first
            (<Text code>pob_pre_restore_*</Text>), so this can be undone. You may need
            to sign in again afterwards.
          </Text>
        </div>
      ),
      okText: 'Overwrite & Restore',
      okButtonProps: { danger: true },
      cancelText: 'Cancel',
      onOk: async () => {
        setRestoring(true);
        try {
          const data = await apiService.post('/api/v1/backup/restore', { filename, confirm: true });
          msg.success(data.message || 'Database restored successfully');
          queryClient.invalidateQueries({ queryKey: ['backup-list'] });
          queryClient.invalidateQueries({ queryKey: ['backup-status'] });
        } catch (e) {
          msg.error(e.message || 'Restore failed');
        } finally {
          setRestoring(false);
        }
      },
    });
  };

  const uploadProps = {
    accept: '.sql,.gz,.dump,.backup',
    showUploadList: false,
    maxCount: 1,
    customRequest: async ({ file, onSuccess, onError }) => {
      setUploading(true);
      try {
        const data = await apiService.upload('/api/v1/backup/upload', file);
        msg.success(data.message || 'Backup uploaded');
        queryClient.invalidateQueries({ queryKey: ['backup-list'] });
        queryClient.invalidateQueries({ queryKey: ['backup-status'] });
        onSuccess?.(data);
      } catch (e) {
        msg.error(e.message || 'Upload failed');
        onError?.(e);
      } finally {
        setUploading(false);
      }
    },
  };

  const deleteMutation = useMutation({
    mutationFn: (filename) => apiService.delete(`/api/v1/backup/${encodeURIComponent(filename)}`),
    onSuccess: () => {
      msg.success('Backup deleted');
      queryClient.invalidateQueries({ queryKey: ['backup-list'] });
      queryClient.invalidateQueries({ queryKey: ['backup-status'] });
    },
    onError: (e) => msg.error(e.message),
  });

  const TYPE_COLOR = { manual: 'blue', daily: 'green', weekly: 'orange', monthly: 'purple', uploaded: 'cyan' };

  const cols = [
    {
      title: 'Filename', dataIndex: 'filename', key: 'filename',
      render: (v, r) => (
        <Space>
          <DatabaseOutlined style={{ color: '#6B7A8D' }} />
          <Text style={{ fontFamily: 'monospace', fontSize: 12 }}>{v}</Text>
          <Tag color={TYPE_COLOR[r.type] || 'default'} style={{ fontSize: 10 }}>{r.type}</Tag>
        </Space>
      ),
    },
    {
      title: 'Size', dataIndex: 'size_human', key: 'size', width: 90,
      render: v => <Text strong>{v}</Text>,
    },
    {
      title: 'Created', dataIndex: 'created_at', key: 'created', width: 170,
      render: v => <Text style={{ fontSize: 12 }}>{dayjs(v).format('DD MMM YYYY HH:mm')}</Text>,
      sorter: (a, b) => new Date(b.created_at) - new Date(a.created_at),
      defaultSortOrder: 'ascend',
    },
    {
      title: 'Actions', key: 'actions', width: 170, fixed: 'right',
      render: (_, r) => (
        <Space>
          <Tooltip title="Restore (overwrites current data)">
            <Button
              size="small" icon={<RollbackOutlined />} type="link"
              style={{ color: '#cf1322' }}
              loading={restoring}
              onClick={() => handleRestore(r.filename)}
            />
          </Tooltip>
          <Tooltip title="Download">
            <Button
              size="small" icon={<DownloadOutlined />} type="link"
              onClick={() => handleDownload(r.filename)}
            />
          </Tooltip>
          <Popconfirm
            title="Delete this backup?"
            description="This cannot be undone."
            onConfirm={() => deleteMutation.mutate(r.filename)}
            okText="Delete" okButtonProps={{ danger: true }}
          >
            <Tooltip title="Delete">
              <Button size="small" icon={<DeleteOutlined />} type="link" danger />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      {/* ── Status cards ── */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="NAS / Storage"
              value={status.nas_connected ? 'Connected' : 'Not connected'}
              prefix={status.nas_connected
                ? <CheckCircleOutlined style={{ color: '#52c41a' }} />
                : <WarningOutlined    style={{ color: '#faad14' }} />}
              valueStyle={{ color: status.nas_connected ? '#52c41a' : '#faad14', fontSize: 16 }}
            />
            <Text type="secondary" style={{ fontSize: 11 }}>{status.backup_directory}</Text>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="Total Backups"
              value={status.total_backups || 0}
              prefix={<DatabaseOutlined />}
            />
            <Text type="secondary" style={{ fontSize: 11 }}>{status.total_size || '0 B'} used</Text>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="Last Backup"
              value={status.last_backup ? dayjs(status.last_backup.created_at).fromNow() : 'Never'}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ fontSize: 14 }}
            />
            <Text type="secondary" style={{ fontSize: 11 }}>
              {status.last_backup ? dayjs(status.last_backup.created_at).format('DD MMM YYYY HH:mm') : '—'}
            </Text>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="Schedule"
              value="Daily 02:00 UTC"
              prefix={<SyncOutlined />}
              valueStyle={{ fontSize: 14 }}
            />
            <Text type="secondary" style={{ fontSize: 11 }}>
              {status.daily_count || 0} daily · {status.manual_count || 0} manual
            </Text>
          </Card>
        </Col>
      </Row>

      {/* ── NAS warning ── */}
      {!status.nas_connected && !statusLoading && (
        <Alert
          type="warning"
          showIcon
          icon={<CloudServerOutlined />}
          message="NAS storage not connected"
          description="Backups are stored on the local server disk. Connect a NAS drive and set BACKUP_DIR in .env.prod to point to the NAS mount path for off-server backup storage."
          style={{ marginBottom: 16 }}
        />
      )}

      {/* ── Actions row ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Text strong>Backup Files</Text>
          <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
            {backups.length} files · {listRaw?.total_size || '0 B'} total
          </Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => { refetchStatus(); refetchList(); }}>
            Refresh
          </Button>
          <Upload {...uploadProps}>
            <Tooltip title="Upload an off-site backup file (.sql / .sql.gz) for disaster recovery">
              <Button icon={<UploadOutlined />} loading={uploading}>
                Upload Backup
              </Button>
            </Tooltip>
          </Upload>
          <Button
            type="primary"
            icon={triggering ? <SyncOutlined spin /> : <DatabaseOutlined />}
            loading={triggering}
            onClick={handleTrigger}
          >
            Backup Now
          </Button>
        </Space>
      </div>

      {/* ── Backup table ── */}
      <Table
        columns={cols}
        dataSource={backups.map((b, i) => ({ ...b, key: i }))}
        loading={listLoading}
        size="small"
        pagination={{ pageSize: 15, showSizeChanger: true, showTotal: t => `${t} backups` }}
        scroll={{ x: 700 }}
        locale={{ emptyText: <Empty description="No backups yet — click 'Backup Now' to create the first one" /> }}
      />

      {/* ── NAS setup guide ── */}
      <Divider />
      <Card size="small" title={<Space><CloudServerOutlined />NAS Configuration Guide</Space>} style={{ background: '#FAFAFA' }}>
        <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
          To store backups on a NAS drive, mount it on the host server and set the path in your environment file:
        </Text>
        <pre style={{ background: '#1F2937', color: '#E5E7EB', padding: '12px 16px', borderRadius: 8, fontSize: 12, overflow: 'auto' }}>
{`# 1. Mount your NAS on the host server (run on the server, not in Docker):
#    NFS:
sudo mount -t nfs 192.168.1.100:/nas/pob-backups /mnt/nas-backups

#    SMB/CIFS (Windows NAS / Synology):
sudo mount -t cifs //192.168.1.100/pob-backups /mnt/nas-backups \\
  -o username=nasuser,password=naspass,uid=1000

# 2. Make it permanent — add to /etc/fstab:
192.168.1.100:/nas/pob-backups  /mnt/nas-backups  nfs  defaults,_netdev  0 0

# 3. Set the backup path in .env.prod:
BACKUP_DIR=/mnt/nas-backups

# 4. In docker-compose.prod.yml, change the db-backup volume to a bind mount:
#    volumes:
#      - \${BACKUP_DIR:-/backups}:/backups

# 5. Restart the backup container:
docker compose -f docker-compose.prod.yml up -d --no-deps db-backup`}
        </pre>
      </Card>
    </div>
  );
};


// ════════════════════════════════════════════════════════════════════════════
// HR INTEGRATION TAB — SeamlessHR connector
// ════════════════════════════════════════════════════════════════════════════
const HRIntegrationTab = () => {
  const { message: msg } = App.useApp();
  const queryClient = useQueryClient();
  const [syncing,     setSyncing]     = useState(false);
  const [testing,     setTesting]     = useState(false);
  const [pulling,     setPulling]     = useState(false);
  const [idsOpen,     setIdsOpen]     = useState(false);
  const [saving,      setSaving]      = useState(false);
  const [previewDate, setPreviewDate] = useState('');
  const [previewData, setPreviewData] = useState(null);
  const [apiKeyEditing, setApiKeyEditing] = useState(false);
  const [advOpen, setAdvOpen] = useState(false);
  const [optionsText, setOptionsText] = useState('');
  const [optionsErr, setOptionsErr] = useState('');

  const [form] = Form.useForm();

  const token   = localStorage.getItem('token') || localStorage.getItem('authToken');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const { data: cfgRaw, isLoading: cfgLoading, refetch: refetchCfg } = useQuery({
    queryKey: ['hr-config'],
    queryFn:  () => apiService.get('/api/v1/hr-integration/config'),
  });

  const { data: statusRaw, refetch: refetchStatus } = useQuery({
    queryKey: ['hr-status'],
    queryFn:  () => apiService.get('/api/v1/hr-integration/sync/status'),
    refetchInterval: 60_000,
  });

  const { data: histRaw, isLoading: histLoading, refetch: refetchHist } = useQuery({
    queryKey: ['hr-history'],
    queryFn:  () => apiService.get('/api/v1/hr-integration/sync/history?limit=30'),
    refetchInterval: 60_000,
  });

  // Populate form when config loads
  React.useEffect(() => {
    if (cfgRaw) {
      form.setFieldsValue({
        api_base_url:        cfgRaw.api_base_url        || 'https://api-sandbox.seamlesshr.app',
        api_key:             cfgRaw.configured ? cfgRaw.api_key_masked : '',
        client_id:           cfgRaw.client_id           || '',
        org_id:              cfgRaw.org_id              || '',
        auth_header_name:    cfgRaw.auth_header_name    || 'Authorization',
        attendance_endpoint: cfgRaw.attendance_endpoint || '/biometric/process',
        employee_endpoint:   cfgRaw.employee_endpoint   || '/v1/employees',
        is_enabled:          cfgRaw.is_enabled           || false,
        sync_time:           cfgRaw.sync_time            || '00:00',
        // Field-mapping shortcuts (stored inside options)
        map_emp_code:        cfgRaw.options?.employee_field_map?.emp_code   || 'staff_id',
        map_last_name:       cfgRaw.options?.employee_field_map?.last_name  || 'staff_name',
        map_first_name:      cfgRaw.options?.employee_field_map?.first_name || 'staff_other_names',
        clock_in_type:       cfgRaw.options?.clock_in_type     || 'CLOCK_IN',
        clock_out_type:      cfgRaw.options?.clock_out_type    || 'CLOCK_OUT',
        default_device_sn:   cfgRaw.options?.default_device_sn || 'POB-MANUAL',
        datetime_style:      cfgRaw.options?.datetime_style    || 'local_naive',
        time_zone:           cfgRaw.options?.time_zone         || 'Africa/Lagos',
      });
      if (cfgRaw.options) setOptionsText(JSON.stringify(cfgRaw.options, null, 2));
    }
  }, [cfgRaw, form]);

  const handleSave = async (values) => {
    const payload = { ...values };
    if (cfgRaw?.configured && !apiKeyEditing) {
      delete payload.api_key;
    }
    // Attach advanced connector options (auth/payload/field mapping) if edited.
    if (optionsText.trim()) {
      try {
        payload.options = JSON.parse(optionsText);
        setOptionsErr('');
      } catch (e) {
        setOptionsErr('Invalid JSON in advanced options'); return;
      }
    }

    // Fold the field-mapping shortcuts back into options. They are applied AFTER
    // the advanced JSON so the visible form fields always win over a stale blob.
    const opts = { ...(payload.options || {}) };
    const empMap = { ...(opts.employee_field_map || {}) };
    if (values.map_emp_code)   empMap.emp_code   = values.map_emp_code.trim();
    if (values.map_last_name)  empMap.last_name  = values.map_last_name.trim();
    if (values.map_first_name) empMap.first_name = values.map_first_name.trim();
    opts.employee_field_map = empMap;
    if (values.clock_in_type)     opts.clock_in_type     = values.clock_in_type.trim();
    if (values.clock_out_type)    opts.clock_out_type    = values.clock_out_type.trim();
    if (values.default_device_sn) opts.default_device_sn = values.default_device_sn.trim();
    if (values.datetime_style)    opts.datetime_style    = values.datetime_style;
    if (values.time_zone)         opts.time_zone         = values.time_zone.trim();
    payload.options = opts;
    ['map_emp_code', 'map_last_name', 'map_first_name', 'clock_in_type',
     'clock_out_type', 'default_device_sn', 'datetime_style',
     'time_zone'].forEach(k => delete payload[k]);

    setSaving(true);
    try {
      await apiService.put('/api/v1/hr-integration/config', payload);
      msg.success('Configuration saved');
      setApiKeyEditing(false);
      queryClient.invalidateQueries({ queryKey: ['hr-config'] });
      queryClient.invalidateQueries({ queryKey: ['hr-status'] });
    } catch (e) { msg.error(e.message); }
    finally { setSaving(false); }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const data = await apiService.post('/api/v1/hr-integration/test-connection');
      if (data.success) msg.success(`✓ ${data.message}`);
      else              msg.error(`✗ ${data.message}`);
    } catch (e) { msg.error(e.message); }
    finally { setTesting(false); }
  };

  const handleSync = async (syncDate, force = false) => {
    setSyncing(true);
    try {
      const data = await apiService.post('/api/v1/hr-integration/sync', { sync_date: syncDate || null, force });
      const level = data.status === 'success' ? 'success' : data.status === 'partial' ? 'warning' : 'error';
      msg[level](`${data.message}`);
      queryClient.invalidateQueries({ queryKey: ['hr-history'] });
      queryClient.invalidateQueries({ queryKey: ['hr-status'] });
    } catch (e) { msg.error(e.message); }
    finally { setSyncing(false); }
  };

  const handlePreview = async () => {
    if (!previewDate) return;
    try {
      const data = await apiService.get(`/api/v1/hr-integration/preview/${previewDate}`);
      setPreviewData(data);
    } catch (e) { msg.error(e.message); }
  };

  const handlePullEmployees = async () => {
    setPulling(true);
    try {
      const data = await apiService.post('/api/v1/hr-integration/pull-employees');
      msg.success(`Employee pull complete — ${data.created} created, ${data.updated} updated${data.skipped ? `, ${data.skipped} skipped` : ''}`);
      queryClient.invalidateQueries({ queryKey: ['hr-history'] });
      queryClient.invalidateQueries({ queryKey: ['hr-status'] });
    } catch (e) { msg.error(e.message || 'Employee pull failed'); }
    finally { setPulling(false); }
  };

  const status  = statusRaw  || {};
  const history = histRaw?.history || [];

  const STATUS_COLOR = { success: 'success', partial: 'warning', failed: 'error', skipped: 'default' };
  const STATUS_TAG   = { success: 'green', partial: 'orange', failed: 'red', skipped: 'default' };

  const histCols = [
    { title: 'Date', dataIndex: 'sync_date', key: 'date', width: 110,
      render: v => <Text style={{ fontSize: 12 }}>{v || '—'}</Text> },
    { title: 'Status', dataIndex: 'status', key: 'status', width: 90,
      render: s => <Tag color={STATUS_TAG[s] || 'default'}>{(s || '').toUpperCase()}</Tag> },
    { title: 'Sent', dataIndex: 'records_sent', key: 'sent', width: 70,
      render: v => <Text strong style={{ color: '#52c41a' }}>{v}</Text> },
    { title: 'Failed', dataIndex: 'records_failed', key: 'failed', width: 70,
      render: v => <Text strong style={{ color: v > 0 ? '#f5222d' : '#9CA3AF' }}>{v}</Text> },
    { title: 'Triggered by', dataIndex: 'triggered_by', key: 'by', width: 120,
      render: v => <Text style={{ fontSize: 11 }}>{v}</Text> },
    { title: 'Message', dataIndex: 'message', key: 'msg',
      render: v => <Text type="secondary" style={{ fontSize: 11 }}>{v}</Text> },
    { title: 'Time', dataIndex: 'created_at', key: 'time', width: 145,
      render: v => <Text style={{ fontSize: 11 }}>{v ? dayjs(v).format('DD MMM YYYY HH:mm') : '—'}</Text> },
  ];

  const previewCols = [
    { title: 'Employee ID',   dataIndex: 'employee_id',   key: 'emp', width: 120 },
    { title: 'Date',          dataIndex: 'date',           key: 'date', width: 110 },
    { title: 'Clock In',      dataIndex: 'clock_in',       key: 'in',  width: 90 },
    { title: 'Clock Out',     dataIndex: 'clock_out',      key: 'out', width: 90, render: v => v || '—' },
    { title: 'Total (mins)',  dataIndex: 'total_minutes',  key: 'mins', width: 110, render: v => v ?? '—' },
  ];

  return (
    <div style={{ padding: 24 }}>

      {/* ── Connection status banner ── */}
      {status.configured && (
        <Alert
          type={status.enabled ? 'success' : 'warning'}
          showIcon
          message={
            status.enabled
              ? `SeamlessHR sync is active — runs daily at ${status.sync_time} UTC`
              : 'SeamlessHR integration is configured but disabled — enable it below'
          }
          description={status.last_sync
            ? `Last sync: ${status.last_sync.status?.toUpperCase()} · ${status.last_sync.records_sent} records sent · ${dayjs(status.last_sync.created_at).fromNow()}`
            : 'No syncs have run yet'}
          style={{ marginBottom: 20 }}
          action={
            <Space>
              <Button size="small" loading={syncing} onClick={() => handleSync(null)}>
                Sync Yesterday
              </Button>
              <Popconfirm
                title="Force re-sync?"
                description="Re-sends records even if already sent — may create duplicates in SeamlessHR. Use only to fix a failed/partial sync."
                okText="Force re-sync" okButtonProps={{ danger: true }}
                onConfirm={() => handleSync(null, true)}
              >
                <Button size="small" danger ghost loading={syncing}>Force re-sync</Button>
              </Popconfirm>
            </Space>
          }
        />
      )}

      {!status.configured && (
        <Alert
          type="info" showIcon
          message="Configure your SeamlessHR API credentials below to enable attendance sync"
          description="Once configured, attendance records will be pushed to SeamlessHR automatically every night so HR can process payroll."
          style={{ marginBottom: 20 }}
        />
      )}

      <Row gutter={[16, 16]}>

        {/* ── Config form ── */}
        <Col xs={24} lg={14}>
          <Card
            title={<Space><ApiOutlined />SeamlessHR API Settings</Space>}
            extra={
              <Space>
                <Button size="small" loading={testing} onClick={handleTest}
                  disabled={!cfgRaw?.configured}>
                  Test Connection
                </Button>
              </Space>
            }
          >
            <Form form={form} layout="vertical" onFinish={handleSave}>

              <Form.Item label="API Base URL" name="api_base_url"
                rules={[{ required: true, message: 'Enter the SeamlessHR API base URL' }]}
                extra="Sandbox: https://api-sandbox.seamlesshr.app — SeamlessHR give you the live host with your production credentials">
                <Input placeholder="https://api-sandbox.seamlesshr.app" />
              </Form.Item>

              <Alert type="info" showIcon style={{ marginBottom: 14 }}
                message="SeamlessHR issues two credentials"
                description={
                  <span>
                    Request them from <b>support@seamlesshr.com</b>. Enter the pair below —
                    they are sent as the <code>x-client-id</code> and <code>x-client-secret</code>
                    {' '}headers on every request. Nothing else needs changing.
                  </span>
                }
              />

              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="Client ID  (x-client-id)" name="client_id"
                    rules={[{ required: true, message: 'Enter the Client ID from SeamlessHR' }]}
                    extra="Not secret — shown in full so you can check the pairing">
                    <Input placeholder="e.g. marconi-ng-prod" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label={
                      <Space>
                        Client Secret  (x-client-secret)
                        {cfgRaw?.configured && !apiKeyEditing && (
                          <Button type="link" size="small" style={{ padding: 0, fontSize: 11 }}
                            onClick={() => { setApiKeyEditing(true); form.setFieldValue('api_key', ''); }}>
                            Change
                          </Button>
                        )}
                      </Space>
                    }
                    name="api_key"
                    rules={[{ required: !cfgRaw?.configured || apiKeyEditing, message: 'Enter your SeamlessHR client secret' }]}
                    extra="Stored encrypted; only the last 6 characters are ever shown again">
                    <Input.Password
                      placeholder={cfgRaw?.configured && !apiKeyEditing ? cfgRaw.api_key_masked : 'Enter client secret'}
                      disabled={cfgRaw?.configured && !apiKeyEditing}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="Organisation ID" name="org_id"
                    extra="Your company ID in SeamlessHR (if required)">
                    <Input placeholder="e.g. marconi-nigeria" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Auth Header" name="auth_header_name"
                    extra="Not used by SeamlessHR (it authenticates via the two headers above) — leave as is">
                    <Input placeholder="Authorization" />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={12}>
                <Col span={14}>
                  <Form.Item label="Attendance Endpoint" name="attendance_endpoint"
                    extra="SeamlessHR's bulk biometric sync — /biometric/process">
                    <Input placeholder="/biometric/process" />
                  </Form.Item>
                </Col>
                <Col span={10}>
                  <Form.Item label="Employee Endpoint" name="employee_endpoint"
                    extra="Path used for connection test">
                    <Input placeholder="/v1/employees" />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={12}>
                <Col span={10}>
                  <Form.Item label="Daily Sync Time (UTC)" name="sync_time"
                    extra="Time to run the nightly sync (HH:MM). UTC — for 03:30 Lagos enter 02:30">
                    <Input placeholder="00:00" maxLength={5} />
                  </Form.Item>
                </Col>
              </Row>

              {/* The four settings most likely to need correcting on the first live
                  connection. They live in the options JSON, but are surfaced here so
                  nobody has to hand-edit JSON to fix a field name. */}
              <Divider orientation="left" plain style={{ marginTop: 4 }}>
                Field mapping — adjust if SeamlessHR's response differs
              </Divider>
              <Alert type="warning" showIcon style={{ marginBottom: 12 }}
                message="Check these against your first Test Connection"
                description="Defaults follow SeamlessHR's published documentation. If names come through swapped or employees are skipped, correct them here — no code change needed."
              />

              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item label="Employee key" name="map_emp_code"
                    extra="SeamlessHR field holding the employee code">
                    <Input placeholder="staff_id" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="Surname field" name="map_last_name"
                    extra="Maps to Last name in ApexPOB">
                    <Input placeholder="staff_name" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="First-name field" name="map_first_name"
                    extra="Maps to First name in ApexPOB">
                    <Input placeholder="staff_other_names" />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item label="Timestamp format" name="datetime_style"
                    extra="How punch times are written">
                    <Select
                      options={[
                        { value: 'offset',      label: 'UTC with offset  (…T06:15:00+00:00)' },
                        { value: 'local_naive', label: 'Site local, no offset  (…T07:15:00)' },
                        { value: 'utc_naive',   label: 'UTC, no offset  (…T06:15:00)' },
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="Site time zone" name="time_zone"
                    extra="Used only by 'Site local, no offset'">
                    <Input placeholder="Africa/Lagos" />
                  </Form.Item>
                </Col>
              </Row>

              <Alert type="warning" showIcon style={{ marginBottom: 12 }}
                message="Confirm the timestamp format with SeamlessHR before the first payroll run"
                description={
                  <span>
                    Apex POB stores UTC and Lagos is UTC+1, so a <b>07:15</b> punch is
                    {' '}<code>06:15Z</code>. SeamlessHR's docs are inconsistent — their request
                    {' '}example has no offset, their schema default has one, and their own
                    {' '}<code>GET /v1/attendances</code> returns actual punch times as naive local
                    {' '}(<code>2024-11-20 09:43:05</code>). If they read an offset-bearing value as
                    {' '}local time, every punch lands an hour early. One sandbox day settles it.
                  </span>
                }
              />

              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item label="Clock-in event value" name="clock_in_type"
                    extra="Sent as 'type' on a clock-in">
                    <Input placeholder="CLOCK_IN" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="Clock-out event value" name="clock_out_type"
                    extra="Sent as 'type' on a clock-out">
                    <Input placeholder="CLOCK_OUT" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="Fallback device serial" name="default_device_sn"
                    extra="Used when no reader backs the punch">
                    <Input placeholder="POB-MANUAL" />
                  </Form.Item>
                </Col>
              </Row>

              {/* Advanced connector mapping — lets a new HR API be wired with no code change */}
              <div style={{ margin: '4px 0 14px' }}>
                <Button type="link" size="small" style={{ padding: 0 }}
                  onClick={() => setAdvOpen(o => !o)}>
                  {advOpen ? '▾' : '▸'} Advanced connector mapping (auth scheme, payload shape, field names)
                </Button>
                {advOpen && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 6 }}>
                      Defaults already match SeamlessHR — you should not need to touch this.
                      {' '}JSON keys: <code>auth_type</code> (dual_header|bearer|api_key|basic|oauth2),
                      {' '}<code>client_id</code>, <code>payload_style</code> (punch_events|daily_summary),
                      {' '}<code>clock_in_type</code>, <code>clock_out_type</code>, <code>default_device_sn</code>,
                      {' '}<code>payload_wrapper_key</code> ("" = bare array), <code>employee_id_source</code>
                      {' '}(emp_code|badge_id|biotime_employee_id), <code>time_format</code> (iso|hms),
                      {' '}<code>org_header_name</code>, <code>batch_size</code>, <code>http_method</code>,
                      {' '}<code>field_map</code>, <code>employee_field_map</code>, <code>extra_headers</code>,
                      {' '}<code>oauth_token_url</code>, <code>oauth_client_id</code>, <code>oauth_scope</code>,
                      {' '}<code>basic_user</code>.
                    </div>
                    <Input.TextArea rows={10} value={optionsText} spellCheck={false}
                      style={{ fontFamily: 'monospace', fontSize: 12 }}
                      onChange={e => { setOptionsText(e.target.value); setOptionsErr(''); }}
                      placeholder='{ "auth_type": "bearer", "payload_wrapper_key": "records", "field_map": {} }' />
                    {optionsErr && <div style={{ color: '#cf1322', fontSize: 12, marginTop: 4 }}>{optionsErr}</div>}
                  </div>
                )}
              </div>

              <Form.Item name="is_enabled" valuePropName="checked">
                <Switch checkedChildren="Sync Enabled" unCheckedChildren="Sync Disabled" />
              </Form.Item>

              <Form.Item style={{ marginBottom: 0 }}>
                <Space>
                  <Button type="primary" htmlType="submit" loading={saving}>
                    Save Configuration
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        {/* ── Right panel: manual sync + preview ── */}
        <Col xs={24} lg={10}>
          <Space direction="vertical" style={{ width: '100%' }} size={16}>

            <Card title="Manual Sync" size="small">
              <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 12 }}>
                Manually push attendance records for a specific date to SeamlessHR.
              </Text>
              <Space.Compact style={{ width: '100%' }}>
                <Input
                  type="date"
                  value={previewDate}
                  onChange={e => setPreviewDate(e.target.value)}
                  style={{ flex: 1 }}
                />
                <Button
                  type="primary" loading={syncing}
                  onClick={() => handleSync(previewDate || null)}
                  disabled={syncing || !status.configured}
                >
                  Sync
                </Button>
              </Space.Compact>
              <Button
                block style={{ marginTop: 8 }} size="small"
                onClick={() => handleSync(null)} loading={syncing}
                disabled={syncing || !status.configured}
              >
                Sync Yesterday (default)
              </Button>
            </Card>

            <Card title={<Space><TeamOutlined />Employee Master (SeamlessHR → ApexPOB)</Space>} size="small">
              <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 12 }}>
                Pull the employee master from SeamlessHR into ApexPOB. Pulled staff become
                <b> read-only here</b> — SeamlessHR remains the system of record for their details.
              </Text>
              <Button
                block type="primary" icon={<SyncOutlined />}
                loading={pulling} disabled={pulling || !status.configured}
                onClick={handlePullEmployees}
              >
                Pull Employees from SeamlessHR
              </Button>
              <Button
                block icon={<IdcardOutlined />} style={{ marginTop: 8 }}
                onClick={() => setIdsOpen(true)}
              >
                Attendance IDs (reader PINs)
              </Button>
              <AttendanceIdsDrawer
                open={idsOpen} onClose={() => setIdsOpen(false)} configured={!!status.configured}
              />
              <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 11 }}>
                For automatic, real-time updates, register the webhook below with SeamlessHR
                instead of pulling manually.
              </Text>
            </Card>

            <Card title={<Space><ApiOutlined />Real-time Sync (Webhook)</Space>} size="small">
              <Text type="secondary" style={{ display: 'block', marginBottom: 8, fontSize: 12 }}>
                Give this URL to SeamlessHR so employee create / update / exit events flow in
                automatically. Set the matching <code>webhook_secret</code> in Advanced connector mapping.
              </Text>
              <Space.Compact style={{ width: '100%' }}>
                <Input readOnly value={`${window.location.origin}/api/v1/hr-integration/webhook`} />
                <Button
                  icon={<CopyOutlined />}
                  onClick={() => { navigator.clipboard?.writeText(`${window.location.origin}/api/v1/hr-integration/webhook`); msg.success('Webhook URL copied'); }}
                >
                  Copy
                </Button>
              </Space.Compact>
            </Card>

            <Card title="Preview Records" size="small">
              <Text type="secondary" style={{ display: 'block', marginBottom: 8, fontSize: 12 }}>
                See exactly which records would be sent for a date before syncing.
              </Text>
              <Space.Compact style={{ width: '100%' }}>
                <Input type="date" value={previewDate} onChange={e => setPreviewDate(e.target.value)} />
                <Button onClick={handlePreview} disabled={!previewDate}>Preview</Button>
              </Space.Compact>
              {previewData && (
                <div style={{ marginTop: 12 }}>
                  <Text strong style={{ fontSize: 12 }}>{previewData.total} records for {previewData.sync_date}</Text>
                  {previewData.truncated && <Text type="secondary" style={{ fontSize: 11 }}> (showing first 100)</Text>}
                  <Table
                    columns={previewCols} size="small"
                    dataSource={previewData.records.map((r, i) => ({ ...r, key: i }))}
                    pagination={{ pageSize: 5, size: 'small' }}
                    style={{ marginTop: 8 }}
                  />
                </div>
              )}
            </Card>

          </Space>
        </Col>
      </Row>

      {/* ── Sync History ── */}
      <Card
        title={<Space><SyncOutlined />Sync History</Space>}
        extra={<Button size="small" icon={<ReloadOutlined />} onClick={() => { refetchHist(); refetchStatus(); }}>Refresh</Button>}
        style={{ marginTop: 16 }}
      >
        <Table
          columns={histCols}
          dataSource={history.map((h, i) => ({ ...h, key: i }))}
          loading={histLoading}
          size="small"
          pagination={{ pageSize: 10, showTotal: t => `${t} sync runs` }}
          scroll={{ x: 800 }}
          locale={{ emptyText: <Empty description="No sync history yet" /> }}
        />
      </Card>

      {/* ── Data format note ── */}
      <Card size="small" style={{ marginTop: 16, background: '#F9FAFB' }}
        title="Data sent to SeamlessHR (per employee per day)">
        <pre style={{ background: '#1F2937', color: '#E5E7EB', padding: '12px 16px', borderRadius: 8, fontSize: 12, margin: 0 }}>
{`{
  "records": [
    {
      "employee_id":   "EMP001",      // same as emp_code in POB
      "date":          "2026-06-06",
      "clock_in":      "08:02:14",    // first biometric check-in of the day
      "clock_out":     "17:45:00",    // last biometric check-out of the day
      "total_minutes": 583,
      "source":        "POB_BIOMETRIC"
    }
  ]
}`}
        </pre>
        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 8 }}>
          Update the Attendance Endpoint above once SeamlessHR shares their API documentation.
        </Text>
      </Card>
    </div>
  );
};


// ════════════════════════════════════════════════════════════════════════════
// BUSINESS CENTRAL INTEGRATION TAB
// ════════════════════════════════════════════════════════════════════════════
const BCIntegrationTab = () => {
  const { message: msg } = App.useApp();
  const queryClient = useQueryClient();
  const [syncing,        setSyncing]        = useState(false);
  const [testing,        setTesting]        = useState(false);
  const [saving,         setSaving]         = useState(false);
  const [companies,      setCompanies]      = useState([]);
  const [secretEditing,  setSecretEditing]  = useState(false);
  const [previewDate,    setPreviewDate]    = useState('');
  const [previewData,    setPreviewData]    = useState(null);
  const [bcAdvOpen,      setBcAdvOpen]      = useState(false);
  const [bcOptionsText,  setBcOptionsText]  = useState('');
  const [bcOptionsErr,   setBcOptionsErr]   = useState('');
  const [form] = Form.useForm();

  const token   = localStorage.getItem('token') || localStorage.getItem('authToken');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const { data: cfgRaw,    isLoading: cfgLoading, refetch: refetchCfg }    = useQuery({ queryKey: ['bc-config'],  queryFn: () => apiService.get('/api/v1/bc-integration/config') });
  const { data: statusRaw, refetch: refetchStatus } = useQuery({ queryKey: ['bc-status'], queryFn: () => apiService.get('/api/v1/bc-integration/sync/status'), refetchInterval: 60_000 });
  const { data: histRaw,   isLoading: histLoading,  refetch: refetchHist }  = useQuery({ queryKey: ['bc-history'], queryFn: () => apiService.get('/api/v1/bc-integration/sync/history?limit=30'), refetchInterval: 60_000 });

  React.useEffect(() => {
    if (cfgRaw) {
      form.setFieldsValue({
        tenant_id:     cfgRaw.tenant_id     || '',
        client_id:     cfgRaw.client_id     || '',
        client_secret: cfgRaw.configured    ? cfgRaw.client_secret_masked : '',
        environment:   cfgRaw.environment   || 'Production',
        company_id:    cfgRaw.company_id    || '',
        is_enabled:    cfgRaw.is_enabled    || false,
        sync_time:     cfgRaw.sync_time     || '01:00',
      });
      if (cfgRaw.options) setBcOptionsText(JSON.stringify(cfgRaw.options, null, 2));
    }
  }, [cfgRaw, form]);

  const handleTest = async () => {
    setTesting(true);
    try {
      const data = await apiService.post('/api/v1/bc-integration/test-connection');
      if (data.success) {
        msg.success(`✓ ${data.message}`);
        if (data.companies?.length) setCompanies(data.companies);
      } else {
        msg.error(`✗ ${data.message}`);
      }
    } catch (e) { msg.error(e.message); }
    finally { setTesting(false); }
  };

  const handleSave = async (values) => {
    const payload = { ...values };
    if (cfgRaw?.configured && !secretEditing) delete payload.client_secret;
    const selected = companies.find(c => c.id === values.company_id);
    if (selected) payload.company_name = selected.name;
    if (bcOptionsText.trim()) {
      try { payload.options = JSON.parse(bcOptionsText); setBcOptionsErr(''); }
      catch { setBcOptionsErr('Invalid JSON in advanced options'); return; }
    }
    setSaving(true);
    try {
      await apiService.put('/api/v1/bc-integration/config', payload);
      msg.success('Configuration saved');
      setSecretEditing(false);
      queryClient.invalidateQueries({ queryKey: ['bc-config'] });
      queryClient.invalidateQueries({ queryKey: ['bc-status'] });
    } catch (e) { msg.error(e.message); }
    finally { setSaving(false); }
  };

  const handleSync = async (syncDate, force = false) => {
    setSyncing(true);
    try {
      const data = await apiService.post('/api/v1/bc-integration/sync', { sync_date: syncDate || null, force });
      const level = data.status === 'success' ? 'success' : data.status === 'partial' ? 'warning' : 'error';
      msg[level](data.message);
      queryClient.invalidateQueries({ queryKey: ['bc-history'] });
      queryClient.invalidateQueries({ queryKey: ['bc-status'] });
    } catch (e) { msg.error(e.message); }
    finally { setSyncing(false); }
  };

  const handlePreview = async () => {
    if (!previewDate) return;
    try {
      const data = await apiService.get(`/api/v1/bc-integration/preview/${previewDate}`);
      setPreviewData(data);
    } catch (e) { msg.error(e.message); }
  };

  const status  = statusRaw  || {};
  const history = histRaw?.history || [];
  const STATUS_TAG = { success: 'green', partial: 'orange', failed: 'red', skipped: 'default' };

  const histCols = [
    { title: 'Date',    dataIndex: 'sync_date',       key: 'date',   width: 110, render: v => <Text style={{ fontSize: 12 }}>{v || '—'}</Text> },
    { title: 'Status',  dataIndex: 'status',          key: 'status', width: 90,  render: s => <Tag color={STATUS_TAG[s] || 'default'}>{(s||'').toUpperCase()}</Tag> },
    { title: 'Sent',    dataIndex: 'records_sent',    key: 'sent',   width: 70,  render: v => <Text strong style={{ color: '#52c41a' }}>{v}</Text> },
    { title: 'Failed',  dataIndex: 'records_failed',  key: 'fail',   width: 70,  render: v => <Text strong style={{ color: v > 0 ? '#f5222d' : '#9CA3AF' }}>{v}</Text> },
    { title: 'By',      dataIndex: 'triggered_by',    key: 'by',     width: 120, render: v => <Text style={{ fontSize: 11 }}>{v}</Text> },
    { title: 'Message', dataIndex: 'message',         key: 'msg',               render: v => <Text type="secondary" style={{ fontSize: 11 }}>{v}</Text> },
    { title: 'Time',    dataIndex: 'created_at',      key: 'time',   width: 145, render: v => <Text style={{ fontSize: 11 }}>{v ? dayjs(v).format('DD MMM YYYY HH:mm') : '—'}</Text> },
  ];

  const previewCols = [
    { title: 'Employee No.',  dataIndex: 'employee_number', key: 'emp',  width: 120 },
    { title: 'Date',          dataIndex: 'date',            key: 'date', width: 110 },
    { title: 'Clock In',      dataIndex: 'clock_in',        key: 'in',   width: 90  },
    { title: 'Clock Out',     dataIndex: 'clock_out',       key: 'out',  width: 90, render: v => v || '—' },
    { title: 'Hours',         dataIndex: 'hours',           key: 'hrs',  width: 80, render: v => v != null ? <Text strong>{v}</Text> : '—' },
  ];

  return (
    <div style={{ padding: 24 }}>

      {status.configured && (
        <Alert
          type={status.enabled ? 'success' : 'warning'}
          showIcon
          message={
            status.enabled
              ? `Business Central sync active — ${status.company_name || ''} (${status.environment}) · runs daily at ${status.sync_time} UTC`
              : 'Business Central integration configured but disabled'
          }
          description={status.last_sync
            ? `Last sync: ${status.last_sync.status?.toUpperCase()} · ${status.last_sync.records_sent} entries sent · ${dayjs(status.last_sync.created_at).fromNow()}`
            : 'No syncs have run yet'}
          style={{ marginBottom: 20 }}
          action={
            <Space>
              <Button size="small" loading={syncing} disabled={syncing} onClick={() => handleSync(null)}>Sync Yesterday</Button>
              <Popconfirm
                title="Force re-sync?"
                description="Re-sends entries even if already sent — may create duplicates in Business Central. Use only to fix a failed/partial sync."
                okText="Force re-sync" okButtonProps={{ danger: true }}
                onConfirm={() => handleSync(null, true)}
              >
                <Button size="small" danger ghost loading={syncing} disabled={syncing}>Force re-sync</Button>
              </Popconfirm>
            </Space>
          }
        />
      )}
      {!status.configured && (
        <Alert type="info" showIcon
          message="Configure your Azure AD app credentials below to enable Business Central attendance sync"
          description="Attendance hours are posted as Time Registration Entries in BC so Finance/HR can run payroll."
          style={{ marginBottom: 20 }}
        />
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card
            title={<Space><ApiOutlined />Azure AD + Business Central Settings</Space>}
            extra={<Button size="small" loading={testing} onClick={handleTest} disabled={!cfgRaw?.configured}>Test Connection</Button>}
          >
            {/* Azure AD setup guide */}
            <Alert type="info" showIcon style={{ marginBottom: 16, fontSize: 12 }}
              message="Azure AD App Registration required"
              description={
                <span>
                  In the Azure Portal: <strong>App Registrations → New → API Permissions → Dynamics 365 BC → Financials.ReadWrite.All</strong>.
                  Copy the Tenant ID, Client ID, and create a Client Secret.
                </span>
              }
            />

            <Form form={form} layout="vertical" onFinish={handleSave}>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="Tenant ID (Directory ID)" name="tenant_id" rules={[{ required: true }]}
                    extra="From Azure Portal → Azure Active Directory → Overview">
                    <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" style={{ fontFamily: 'monospace', fontSize: 12 }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Client ID (Application ID)" name="client_id" rules={[{ required: true }]}
                    extra="From App Registration → Overview">
                    <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" style={{ fontFamily: 'monospace', fontSize: 12 }} />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                label={
                  <Space>Client Secret
                    {cfgRaw?.configured && !secretEditing && (
                      <Button type="link" size="small" style={{ padding: 0, fontSize: 11 }}
                        onClick={() => { setSecretEditing(true); form.setFieldValue('client_secret', ''); }}>
                        Change
                      </Button>
                    )}
                  </Space>
                }
                name="client_secret"
                rules={[{ required: !cfgRaw?.configured || secretEditing }]}
                extra="From App Registration → Certificates & Secrets">
                <Input.Password
                  placeholder={cfgRaw?.configured && !secretEditing ? cfgRaw.client_secret_masked : 'Enter client secret'}
                  disabled={cfgRaw?.configured && !secretEditing}
                />
              </Form.Item>

              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item label="Environment" name="environment" extra="Usually 'Production' or 'Sandbox'">
                    <Select options={[{ label: 'Production', value: 'Production' }, { label: 'Sandbox', value: 'Sandbox' }]} />
                  </Form.Item>
                </Col>
                <Col span={10}>
                  <Form.Item label="Company" name="company_id" extra="Click Test Connection first to load companies">
                    <Select
                      placeholder="Test connection first to load companies"
                      options={[
                        ...(cfgRaw?.company_id ? [{ label: cfgRaw.company_name || cfgRaw.company_id, value: cfgRaw.company_id }] : []),
                        ...companies.filter(c => c.id !== cfgRaw?.company_id).map(c => ({ label: c.name, value: c.id })),
                      ]}
                      allowClear
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="Sync Time (UTC)" name="sync_time" extra="Daily sync time">
                    <Input placeholder="01:00" maxLength={5} />
                  </Form.Item>
                </Col>
              </Row>

              {/* Advanced BC surface mapping — standard API / custom partner API / OData V4 */}
              <div style={{ margin: '4px 0 14px' }}>
                <Button type="link" size="small" style={{ padding: 0 }}
                  onClick={() => setBcAdvOpen(o => !o)}>
                  {bcAdvOpen ? '▾' : '▸'} Advanced connector mapping (API route, target entity, field mapping)
                </Button>
                {bcAdvOpen && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 6 }}>
                      JSON — real Business Central surfaces. <code>api_route</code>: <code>api/v2.0</code> (standard),
                      {' '}<code>api/{'{publisher}/{group}/{version}'}</code> (custom/partner API), or <code>ODataV4</code>.
                      {' '}<code>company_path</code>: <code>companies({'{company_id}'})</code> or <code>Company('{'{company_name}'}')</code> (OData).
                      {' '}<code>target_entity</code> (e.g. <code>timeRegistrationEntries</code>, <code>journalLines</code>, or a custom page).
                      {' '}<code>field_map</code> (rename to the target's fields, ""=omit), <code>static_fields</code> (e.g. <code>jobNumber</code>, <code>unitOfMeasureCode</code>).
                    </div>
                    <Input.TextArea rows={9} value={bcOptionsText} spellCheck={false}
                      style={{ fontFamily: 'monospace', fontSize: 12 }}
                      onChange={e => { setBcOptionsText(e.target.value); setBcOptionsErr(''); }}
                      placeholder='{ "api_route": "api/v2.0", "target_entity": "timeRegistrationEntries", "field_map": {}, "static_fields": {} }' />
                    {bcOptionsErr && <div style={{ color: '#cf1322', fontSize: 12, marginTop: 4 }}>{bcOptionsErr}</div>}
                  </div>
                )}
              </div>

              <Form.Item name="is_enabled" valuePropName="checked">
                <Switch checkedChildren="Sync Enabled" unCheckedChildren="Sync Disabled" />
              </Form.Item>

              <Button type="primary" htmlType="submit" loading={saving}>Save Configuration</Button>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Space direction="vertical" style={{ width: '100%' }} size={16}>
            <Card title="Manual Sync" size="small">
              <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 12 }}>
                Push time entries for a specific date to Business Central.
              </Text>
              <Space.Compact style={{ width: '100%' }}>
                <Input type="date" value={previewDate} onChange={e => setPreviewDate(e.target.value)} style={{ flex: 1 }} />
                <Button type="primary" loading={syncing} onClick={() => handleSync(previewDate || null)} disabled={syncing || !status.configured}>Sync</Button>
              </Space.Compact>
              <Space style={{ marginTop: 8, width: '100%' }} direction="vertical">
                <Button block size="small" onClick={() => handleSync(null)} loading={syncing} disabled={syncing || !status.configured}>
                  Sync Yesterday (default)
                </Button>
                <Button
                  block size="small" type="primary" ghost
                  disabled={syncing || !status.configured}
                  loading={syncing}
                  icon={<ThunderboltOutlined />}
                  onClick={async () => {
                    setSyncing(true);
                    try {
                      const d = await apiService.post('/api/v1/bc-integration/sync/trigger-today');
                      msg.success(`Today synced: ${d.records_sent ?? 0} records sent`);
                    } catch (e) { msg.error(e.message); }
                    finally { setSyncing(false); }
                  }}
                >
                  Sync Today (Real-time)
                </Button>
              </Space>
            </Card>

            <Card title="Preview Entries" size="small">
              <Space.Compact style={{ width: '100%' }}>
                <Input type="date" value={previewDate} onChange={e => setPreviewDate(e.target.value)} />
                <Button onClick={handlePreview} disabled={!previewDate}>Preview</Button>
              </Space.Compact>
              {previewData && (
                <div style={{ marginTop: 12 }}>
                  <Text strong style={{ fontSize: 12 }}>{previewData.total} entries for {previewData.sync_date}</Text>
                  <Table columns={previewCols} size="small"
                    dataSource={previewData.entries.map((r, i) => ({ ...r, key: i }))}
                    pagination={{ pageSize: 5, size: 'small' }} style={{ marginTop: 8 }} />
                </div>
              )}
            </Card>

            <Card size="small" title="Payload sent to Business Central" style={{ background: '#F9FAFB' }}>
              <pre style={{ background: '#1F2937', color: '#E5E7EB', padding: '10px 14px', borderRadius: 8, fontSize: 11, margin: 0 }}>
{`POST /companies({id})/timeRegistrationEntries

{
  "employeeNumber": "EMP001",
  "date":           "2026-06-06",
  "quantity":       8.72,   // hours worked
  "status":         "Open"
}`}
              </pre>
            </Card>
          </Space>
        </Col>
      </Row>

      <Card title={<Space><SyncOutlined />Sync History</Space>}
        extra={<Button size="small" icon={<ReloadOutlined />} onClick={() => { refetchHist(); refetchStatus(); }}>Refresh</Button>}
        style={{ marginTop: 16 }}>
        <Table columns={histCols} dataSource={history.map((h, i) => ({ ...h, key: i }))}
          loading={histLoading} size="small"
          pagination={{ pageSize: 10, showTotal: t => `${t} sync runs` }}
          scroll={{ x: 800 }}
          locale={{ emptyText: <Empty description="No sync history yet" /> }} />
      </Card>
    </div>
  );
};


// ════════════════════════════════════════════════════════════════════════════
// SESSIONS TAB — view and revoke active login sessions
// ════════════════════════════════════════════════════════════════════════════
const SessionsTab = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['settings-sessions'],
    queryFn: () => apiService.get('/api/v1/sessions/'),
    refetchInterval: 30_000,
  });
  const sessions = data?.sessions ?? [];

  const revokeM = useMutation({
    mutationFn: (session_id) => apiService.delete(`/api/v1/sessions/${session_id}`),
    onSuccess: () => { message.success('Session revoked'); qc.invalidateQueries(['settings-sessions']); },
    onError: (e) => message.error(e?.message || 'Failed to revoke session'),
  });

  const revokeAllM = useMutation({
    mutationFn: () => apiService.delete('/api/v1/sessions/'),
    onSuccess: (res) => {
      message.success(`All sessions revoked (${res?.revoked ?? 0})`);
      qc.invalidateQueries(['settings-sessions']);
    },
    onError: (e) => message.error(e?.message || 'Failed'),
  });

  const uaIcon = (ua = '') => {
    if (/mobile|android|iphone/i.test(ua)) return '📱';
    if (/tablet|ipad/i.test(ua))           return '📟';
    return '💻';
  };

  const cols = [
    {
      title: 'Device / Browser', key: 'ua',
      render: (_, r) => (
        <Space>
          <span style={{ fontSize: 18 }}>{uaIcon(r.user_agent)}</span>
          <Space direction="vertical" size={0}>
            <Space size={6}>
              <Text style={{ fontSize: 12 }}>
                {r.user_agent ? r.user_agent.slice(0, 60) + (r.user_agent.length > 60 ? '…' : '') : 'Unknown'}
              </Text>
              {r.current && <Tag color="green" style={{ margin: 0, fontSize: 10, lineHeight: '16px' }}>This device</Tag>}
            </Space>
            <Text type="secondary" style={{ fontSize: 11 }}>
              IP: {r.ip_address || '—'}
            </Text>
          </Space>
        </Space>
      ),
    },
    {
      title: 'Started', dataIndex: 'created_at', key: 'started', width: 140,
      render: v => v ? (
        <Tooltip title={dayjs(v).format('DD MMM YYYY HH:mm:ss')}>
          <Text style={{ fontSize: 12 }}>{dayjs(v).fromNow()}</Text>
        </Tooltip>
      ) : '—',
    },
    {
      title: 'Last Active', dataIndex: 'last_active', key: 'active', width: 140,
      render: v => v ? (
        <Tooltip title={dayjs(v).format('DD MMM YYYY HH:mm:ss')}>
          <Text style={{ fontSize: 12, color: '#10B981' }}>{dayjs(v).fromNow()}</Text>
        </Tooltip>
      ) : '—',
    },
    {
      title: '', key: 'action', width: 80,
      render: (_, r) => (
        <Popconfirm
          title="Revoke this session?"
          description={r.current
            ? 'This is the device you are using — you will be logged out immediately.'
            : 'This device will be logged out on its next request.'}
          onConfirm={() => revokeM.mutate(r.session_id)}
          okText="Revoke" okType="danger"
        >
          <Button size="small" danger icon={<StopOutlined />} loading={revokeM.isPending}>
            {r.current ? 'Sign out' : 'Revoke'}
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Alert
        type="info"
        showIcon
        message="Active Sessions"
        description="These are your currently active login sessions. Revoking a session will log out that device immediately. Sessions shown here are stored in Redis and expire automatically when the session timeout is reached."
        style={{ marginBottom: 16 }}
      />

      <Card
        styles={{ body: { padding: '10px 14px' } }}
        style={{ marginBottom: 12 }}
      >
        <Row align="middle" justify="space-between">
          <Col>
            <Space>
              <DesktopOutlined style={{ color: '#3B82F6' }} />
              <Text strong>{sessions.length} active session{sessions.length !== 1 ? 's' : ''}</Text>
            </Space>
          </Col>
          <Col>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading} size="small">
                Refresh
              </Button>
              <Popconfirm
                title="Revoke ALL sessions?"
                description="You will be logged out of all devices including this one."
                onConfirm={() => revokeAllM.mutate()}
                okText="Revoke All" okType="danger"
              >
                <Button danger icon={<StopOutlined />} loading={revokeAllM.isPending} size="small">
                  Revoke All
                </Button>
              </Popconfirm>
            </Space>
          </Col>
        </Row>
      </Card>

      <Card styles={{ body: { padding: 0 } }}>
        {sessions.length === 0 && !isLoading ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Space direction="vertical" size={4}>
                <Text>No active sessions tracked in Redis.</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Sessions are recorded on login and visible here until they expire.
                </Text>
              </Space>
            }
            style={{ padding: 48 }}
          />
        ) : (
          <Table
            columns={cols}
            dataSource={sessions}
            loading={isLoading}
            rowKey="session_id"
            size="middle"
            pagination={false}
            locale={{ emptyText: <Empty description="No sessions" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          />
        )}
      </Card>
    </div>
  );
};


const Settings = () => {
  const [activeTab, setActiveTab] = useState('users');

  const tabItems = [
    { key: 'users',     label: <Space><UserOutlined />Users</Space>,               children: <UsersTab /> },
    { key: 'roles',     label: <Space><LockOutlined />Roles & Permissions</Space>, children: <RolesTab /> },
    { key: 'company',   label: <Space><BankOutlined />Company</Space>,             children: <CompanyTab /> },
    { key: 'email',     label: <Space><MailOutlined />Email</Space>,               children: <EmailSetup /> },
    { key: 'security',  label: <Space><ClockCircleOutlined />Security</Space>,     children: <SecurityTab /> },
    { key: 'sessions',  label: <Space><DesktopOutlined />Active Sessions</Space>,  children: <SessionsTab /> },
    { key: 'audit-log', label: <Space><AuditOutlined />Audit Log</Space>,          children: <AuditLogTab /> },
    { key: 'database',       label: <Space><DatabaseOutlined />Database</Space>,           children: <DatabaseTab /> },
    { key: 'backup',         label: <Space><DatabaseOutlined />Database Backup</Space>,    children: <BackupTab /> },
    { key: 'hr-integration', label: <Space><ApiOutlined />HR Integration</Space>,          children: <HRIntegrationTab /> },
    { key: 'bc-integration', label: <Space><LinkOutlined />Business Central</Space>,       children: <BCIntegrationTab /> },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0 }}>
          <Space><SettingOutlined />System Settings</Space>
        </Title>
        <Text type="secondary">Manage users, roles, permissions and company configuration</Text>
      </div>

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

export default Settings;
