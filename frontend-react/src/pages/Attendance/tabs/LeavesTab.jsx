import React, { useState, useMemo } from 'react';
import {
  Table, Button, Space, Tag, App, Modal, Drawer,
  Select, Row, Col, Divider, Descriptions, Tooltip, Badge,
  Input, DatePicker, Form, InputNumber,
  Popover, Popconfirm, Alert,
} from 'antd';
import {
  PlusOutlined, CheckOutlined, CloseOutlined, EyeOutlined,
  ReloadOutlined, SearchOutlined, ClockCircleOutlined,
  CheckCircleOutlined, CloseCircleOutlined, CalendarOutlined,
  StopOutlined, SettingOutlined, UserOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService from '../../../services/api';
import dayjs from 'dayjs';
import { ColTogglePopover, EmployeeCell, tableContainerStyle } from './shared';

const { Option } = Select;
const { RangePicker } = DatePicker;

const STATUS_CFG = {
  pending:   { label: 'Pending',   badge: 'warning',    tag: 'orange' },
  approved:  { label: 'Approved',  badge: 'success',    tag: 'green'  },
  on_leave:  { label: 'On Leave',  badge: 'processing', tag: 'blue'   },
  rejected:  { label: 'Rejected',  badge: 'error',      tag: 'red'    },
  cancelled: { label: 'Cancelled', badge: 'default',    tag: 'default'},
};
const stCfg = (s) => STATUS_CFG[s] || { label: s || 'Unknown', badge: 'default', tag: 'default' };

const LeavesTab = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();

  const [search,      setSearch]      = useState('');
  const [filterSt,    setFilterSt]    = useState(null);
  const [filterType,  setFilterType]  = useState(null);
  const [dateRange,   setDateRange]   = useState(null);
  const [selected,    setSelected]    = useState([]);
  const [hiddenCols,  setHiddenCols]  = useState(new Set());
  const [colPopOpen,  setColPopOpen]  = useState(false);
  const [detailOpen,  setDetailOpen]  = useState(false);
  const [detailId,    setDetailId]    = useState(null);
  const [submitOpen,  setSubmitOpen]  = useState(false);
  const [rejectOpen,  setRejectOpen]  = useState(false);
  const [rejectRec,   setRejectRec]   = useState(null);
  const [rejectNote,  setRejectNote]  = useState('');
  const [form] = Form.useForm();

  const { data: leaveTypesRaw } = useQuery({
    queryKey: ['personnel-leave-types'],
    queryFn: () => apiService.get('/api/v1/personnel/leave/types'),
    staleTime: Infinity,
  });
  const leaveTypes = Array.isArray(leaveTypesRaw) ? leaveTypesRaw : [];

  const { data: personnelRaw } = useQuery({
    queryKey: ['personnel-dropdown-leave'],
    queryFn: () => apiService.get('/api/v1/personnel/?page_size=500'),
    staleTime: 60000,
  });
  const employees = useMemo(() => {
    const raw = personnelRaw?.results || personnelRaw?.data || personnelRaw || [];
    return Array.isArray(raw) ? raw : [];
  }, [personnelRaw]);

  const startDate = dateRange?.[0]?.format('YYYY-MM-DD');
  const endDate   = dateRange?.[1]?.format('YYYY-MM-DD');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['personnel-leaves-att', filterSt, filterType, startDate, endDate],
    queryFn: () => {
      const p = {};
      if (filterSt)   p.status     = filterSt;
      if (filterType) p.leave_type = filterType;
      if (startDate)  p.start_date = startDate;
      if (endDate)    p.end_date   = endDate;
      return apiService.get('/api/v1/personnel/leave', p);
    },
    refetchInterval: 30000,
  });
  const rawRows = useMemo(() => {
    const r = data?.data || data || [];
    return Array.isArray(r) ? r : [];
  }, [data]);

  const rows = useMemo(() => {
    if (!search) return rawRows;
    const q = search.toLowerCase();
    return rawRows.filter(r =>
      (r.personnel_name     || '').toLowerCase().includes(q) ||
      (r.personnel_emp_code || '').toLowerCase().includes(q) ||
      (r.leave_type         || '').toLowerCase().includes(q) ||
      (r.reason             || '').toLowerCase().includes(q)
    );
  }, [rawRows, search]);

  const ltColor = (code) => leaveTypes.find(lt => lt.code === code)?.color || 'blue';
  const ltLabel = (code) => leaveTypes.find(lt => lt.code === code)?.name  || code;

  const autoCalcDays = () => {
    setTimeout(() => {
      const s = form.getFieldValue('start_date');
      const e = form.getFieldValue('end_date');
      if (s && e && dayjs.isDayjs(s) && dayjs.isDayjs(e)) {
        const d = e.diff(s, 'day') + 1;
        if (d > 0) form.setFieldValue('days_count', d);
      }
    }, 0);
  };

  const createM = useMutation({
    mutationFn: (d) => apiService.post('/api/v1/personnel/leave', d),
    onSuccess: () => {
      message.success('Leave request submitted');
      setSubmitOpen(false); form.resetFields();
      qc.invalidateQueries(['personnel-leaves-att']);
    },
    onError: (e) => message.error(e?.message || 'Failed to submit leave'),
  });

  const approveM = useMutation({
    mutationFn: (id) => apiService.put(`/api/v1/personnel/leave/${id}/approve`),
    onSuccess: () => { message.success('Leave approved'); qc.invalidateQueries(['personnel-leaves-att']); },
    onError: (e) => message.error(e?.message || 'Failed to approve'),
  });

  const rejectM = useMutation({
    mutationFn: ({ id, rejection_reason }) =>
      apiService.put(`/api/v1/personnel/leave/${id}/reject`, { rejection_reason }),
    onSuccess: () => {
      message.success('Leave rejected');
      setRejectOpen(false); setRejectRec(null); setRejectNote('');
      qc.invalidateQueries(['personnel-leaves-att']);
    },
    onError: (e) => message.error(e?.message || 'Failed to reject'),
  });

  const cancelM = useMutation({
    mutationFn: (id) => apiService.put(`/api/v1/personnel/leave/${id}/cancel`),
    onSuccess: () => { message.success('Leave cancelled'); qc.invalidateQueries(['personnel-leaves-att']); },
    onError: (e) => message.error(e?.message || 'Failed to cancel'),
  });

  const bulkApproveM = useMutation({
    mutationFn: (ids) => Promise.all(ids.map(id => apiService.put(`/api/v1/personnel/leave/${id}/approve`))),
    onSuccess: (_, ids) => {
      message.success(`${ids.length} leave(s) approved`);
      setSelected([]); qc.invalidateQueries(['personnel-leaves-att']);
    },
    onError: (e) => message.error(e?.message || 'Bulk approve failed'),
  });

  const submit = () => form.validateFields().then(v =>
    createM.mutate({
      ...v,
      start_date: v.start_date?.format('YYYY-MM-DD'),
      end_date:   v.end_date?.format('YYYY-MM-DD'),
    })
  ).catch(() => {});

  const detailRec = useMemo(() => rows.find(r => r.id === detailId) ?? null, [rows, detailId]);

  const pending  = rawRows.filter(r => r.status === 'pending').length;
  const approved = rawRows.filter(r => r.status === 'approved' || r.status === 'on_leave').length;
  const rejected = rawRows.filter(r => r.status === 'rejected').length;
  const total    = rawRows.length;

  const COL_DEFS = [
    {
      title: 'Employee', key: 'employee',
      render: (_, r) => (
        <EmployeeCell
          name={r.personnel_name || `Employee #${r.personnel_id}`}
          code={r.personnel_emp_code || ''}
          onClick={() => { setDetailId(r.id); setDetailOpen(true); }}
        />
      ),
    },
    {
      title: 'Leave Type', key: 'leave_type', dataIndex: 'leave_type', width: 150,
      render: code => <Tag color={ltColor(code)} style={{ borderRadius:5, fontWeight:600 }}>{ltLabel(code)}</Tag>,
    },
    {
      title: 'Start', key: 'start', dataIndex: 'start_date', width: 120,
      render: d => d ? dayjs(d).format('DD MMM YYYY') : '—',
    },
    {
      title: 'End', key: 'end', dataIndex: 'end_date', width: 120,
      render: d => d ? dayjs(d).format('DD MMM YYYY') : '—',
    },
    {
      title: 'Days', key: 'days', dataIndex: 'days_count', width: 70, align: 'center',
      render: v => v ?? '—',
    },
    { title: 'Reason', key: 'reason', dataIndex: 'reason', ellipsis: true },
    {
      title: 'Status', key: 'status', dataIndex: 'status', width: 110,
      render: s => { const c = stCfg(s); return <Badge status={c.badge} text={c.label} />; },
    },
  ];

  const toggleCol = (key) => setHiddenCols(prev => {
    const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n;
  });

  const cols = useMemo(() => {
    const visible = COL_DEFS.filter(c => !hiddenCols.has(c.key));
    return [...visible, {
      title: 'Actions', key: 'act', fixed: 'right', width: 140,
      render: (_, r) => (
        <Space size={4} wrap>
          <Tooltip title="View">
            <Button size="small" icon={<EyeOutlined />} onClick={() => { setDetailId(r.id); setDetailOpen(true); }} />
          </Tooltip>
          {r.status === 'pending' && (
            <>
              <Popconfirm title="Approve this leave?" onConfirm={() => approveM.mutate(r.id)} okText="Approve">
                <Tooltip title="Approve">
                  <Button size="small" type="primary" icon={<CheckOutlined />}
                    loading={approveM.isPending && approveM.variables === r.id} />
                </Tooltip>
              </Popconfirm>
              <Tooltip title="Reject">
                <Button size="small" danger icon={<CloseOutlined />}
                  onClick={() => { setRejectRec(r); setRejectNote(''); setRejectOpen(true); }} />
              </Tooltip>
            </>
          )}
          {(r.status === 'approved' || r.status === 'on_leave') && (
            <Popconfirm title="Cancel this leave?" onConfirm={() => cancelM.mutate(r.id)} okText="Cancel" okButtonProps={{ danger: true }}>
              <Tooltip title="Cancel"><Button size="small" danger icon={<StopOutlined />} /></Tooltip>
            </Popconfirm>
          )}
        </Space>
      ),
    }];
  }, [hiddenCols, approveM.variables]);

  const pendingSelected = selected.filter(id => rows.find(r => r.id === id)?.status === 'pending');

  const rowSelection = {
    selectedRowKeys: selected,
    onChange: setSelected,
    getCheckboxProps: (r) => ({
      disabled: r.status !== 'pending',
      title: r.status !== 'pending' ? 'Only pending leaves can be selected' : '',
    }),
  };

  return (
    <div style={{ padding: 24 }}>
      <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message="SeamlessHR staff request leave in SeamlessHR"
        description="SeamlessHR is the system of record for staff leave — raise and approve it there and ApexPOB picks it up automatically (nightly). Use this screen only for contractors and others who are not in SeamlessHR." />
      <SeamlessLeaveToday />
      <style>{`
        .lv-mod-table .ant-table-thead .ant-table-cell {
          background: #f8fafc !important; color: #64748b !important;
          font-size: 11px !important; font-weight: 700 !important;
          text-transform: uppercase !important; letter-spacing: 0.5px !important;
          border-bottom: 2px solid #e2e8f0 !important;
        }
      `}</style>

      {/* ── Stat cards ── */}
      <Row gutter={[14, 14]} style={{ marginBottom: 20 }}>
        {[
          { title: 'Total Requests',    value: total,    icon: <CalendarOutlined />,     color: '#1890ff' },
          { title: 'Pending',           value: pending,  icon: <ClockCircleOutlined />,  color: '#fa8c16' },
          { title: 'Approved / Active', value: approved, icon: <CheckCircleOutlined />,  color: '#52c41a' },
          { title: 'Rejected',          value: rejected, icon: <CloseCircleOutlined />,  color: '#f5222d' },
        ].map(s => (
          <Col xs={12} sm={6} key={s.title}>
            <div style={{ background:'#fff', borderRadius:12, border:'1px solid #e2e8f0', padding:'16px 18px', display:'flex', alignItems:'center', gap:14, boxShadow:'0 1px 3px rgba(0,0,0,0.06)', height:'100%' }}>
              <div style={{ width:44, height:44, borderRadius:10, flexShrink:0, background:`${s.color}18`, display:'flex', alignItems:'center', justifyContent:'center' }}>
                {React.cloneElement(s.icon, { style:{ fontSize:20, color:s.color } })}
              </div>
              <div>
                <div style={{ color:'#8c8c8c', fontSize:12, fontWeight:500 }}>{s.title}</div>
                <div style={{ fontSize:22, fontWeight:700, color:'#1f1f1f', lineHeight:1.2, marginTop:2 }}>{s.value}</div>
              </div>
            </div>
          </Col>
        ))}
      </Row>

      {/* ── Filter bar ── */}
      <div style={{ background:'#fff', border:'1px solid #e2e8f0', borderRadius:12, padding:'12px 16px', marginBottom:16 }}>
        <Row gutter={[12, 8]} align="middle">
          <Col xs={24} sm={8} md={6}>
            <Input placeholder="Search employee or reason…" prefix={<SearchOutlined style={{ color:'#94a3b8' }} />}
              value={search} onChange={e => setSearch(e.target.value)} allowClear />
          </Col>
          <Col xs={12} sm={5} md={4}>
            <Select placeholder="Status" style={{ width: '100%' }} value={filterSt} onChange={setFilterSt} allowClear>
              {Object.entries(STATUS_CFG).map(([k, v]) => <Option key={k} value={k}>{v.label}</Option>)}
            </Select>
          </Col>
          <Col xs={12} sm={5} md={4}>
            <Select placeholder="Leave Type" style={{ width: '100%' }} value={filterType} onChange={setFilterType} allowClear>
              {leaveTypes.map(lt => <Option key={lt.code} value={lt.code}><Tag color={lt.color}>{lt.name}</Tag></Option>)}
            </Select>
          </Col>
          <Col xs={24} sm={10} md={6}>
            <RangePicker style={{ width: '100%' }} value={dateRange} onChange={setDateRange} format="DD MMM YYYY" allowClear />
          </Col>
          <Col>
            <Space>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setSubmitOpen(true); }}>
                Submit Leave
              </Button>
              <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading}>Refresh</Button>
              <Popover title="Show / Hide Columns" trigger="click" open={colPopOpen} onOpenChange={setColPopOpen}
                content={<ColTogglePopover colDefs={COL_DEFS} hidden={hiddenCols} onToggle={toggleCol} />}>
                <Tooltip title="Adjust columns"><Button icon={<SettingOutlined />} /></Tooltip>
              </Popover>
            </Space>
          </Col>
        </Row>
      </div>

      {/* ── Bulk bar ── */}
      {selected.length > 0 && (
        <div style={{ background:'#1d4ed8', borderRadius:10, padding:'10px 16px', marginBottom:12, display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <span style={{ color:'#fff', fontWeight:600, fontSize:13 }}>
            {selected.length} leave{selected.length !== 1 ? 's' : ''} selected
            {pendingSelected.length > 0 && (
              <span style={{ color:'#93c5fd', marginLeft:8, fontWeight:400 }}>({pendingSelected.length} pending)</span>
            )}
          </span>
          <Space>
            {pendingSelected.length > 0 && (
              <Button size="small" icon={<CheckOutlined />}
                style={{ background:'rgba(255,255,255,0.15)', border:'1px solid rgba(255,255,255,0.3)', color:'#fff' }}
                onClick={() => bulkApproveM.mutate(pendingSelected)}
                loading={bulkApproveM.isPending}>
                Approve {pendingSelected.length} Pending
              </Button>
            )}
            <Button size="small" icon={<CloseOutlined />}
              style={{ background:'rgba(255,255,255,0.15)', border:'none', color:'#fff' }}
              onClick={() => setSelected([])}>
              Clear
            </Button>
          </Space>
        </div>
      )}

      {/* ── Table ── */}
      <div style={tableContainerStyle}>
        <Table
          className="lv-mod-table"
          columns={cols}
          dataSource={rows}
          loading={isLoading}
          rowKey="id"
          size="middle"
          scroll={{ x: 1050 }}
          rowSelection={rowSelection}
          onRow={r => ({
            onMouseEnter: e => { e.currentTarget.style.background = '#f8fafc'; },
            onMouseLeave: e => { e.currentTarget.style.background = ''; },
          })}
          pagination={{ pageSize: 30, showSizeChanger: true, showTotal: (t, r) => `${r[0]}–${r[1]} of ${t}` }}
        />
      </div>

      {/* ── Submit Leave Drawer ── */}
      <Drawer title={<Space><UserOutlined style={{ color: '#52c41a' }} />Submit Leave Request</Space>}
        open={submitOpen} onClose={() => setSubmitOpen(false)} width={620} destroyOnHidden
        footer={<Space style={{ float: 'right' }}>
          <Button onClick={() => setSubmitOpen(false)}>Cancel</Button>
          <Button type="primary" onClick={submit} loading={createM.isPending}>Submit</Button>
        </Space>}>
        <Form form={form} layout="vertical" size="small">
          <Divider orientation="left" style={{ fontSize: 12 }}>Employee & Leave Type</Divider>
          <Row gutter={12}>
            <Col span={14}>
              <Form.Item name="personnel_id" label="Employee *" rules={[{ required: true }]}>
                <Select showSearch optionFilterProp="label" size="middle" placeholder="Search employee"
                  options={employees.map(e => ({
                    value: e.id,
                    label: `${e.full_name || `${e.first_name || ''} ${e.last_name || ''}`.trim()} · ${e.badge_id || e.emp_code || ''}`,
                  }))} />
              </Form.Item>
            </Col>
            <Col span={10}>
              <Form.Item name="leave_type" label="Leave Type *" rules={[{ required: true }]}>
                <Select size="middle" placeholder="Select type">
                  {leaveTypes.map(lt => (
                    <Option key={lt.code} value={lt.code}>
                      <Tag color={lt.color} style={{ marginRight: 4 }}>{lt.name}</Tag>
                      {lt.paid ? '(Paid)' : '(Unpaid)'}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Divider orientation="left" style={{ fontSize: 12 }}>Dates</Divider>
          <Row gutter={12}>
            <Col span={9}>
              <Form.Item name="start_date" label="Start Date *" rules={[{ required: true }]}>
                <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" size="middle" onChange={autoCalcDays} />
              </Form.Item>
            </Col>
            <Col span={9}>
              <Form.Item name="end_date" label="End Date *" rules={[{ required: true }]}>
                <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" size="middle" onChange={autoCalcDays} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="days_count" label="Days" rules={[{ required: true }]}>
                <InputNumber min={0.5} step={0.5} style={{ width: '100%' }} size="middle" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="reason" label="Reason">
            <Input.TextArea rows={3} size="middle" placeholder="Reason for leave…" maxLength={500} showCount />
          </Form.Item>
        </Form>
      </Drawer>

      {/* ── Reject Modal ── */}
      <Modal title={<Space><CloseOutlined style={{ color: '#f5222d' }} />Reject Leave Request</Space>}
        open={rejectOpen}
        onOk={() => rejectM.mutate({ id: rejectRec?.id, rejection_reason: rejectNote })}
        onCancel={() => { setRejectOpen(false); setRejectRec(null); setRejectNote(''); }}
        confirmLoading={rejectM.isPending} okButtonProps={{ danger: true }} okText="Reject" destroyOnHidden>
        {rejectRec && (
          <Descriptions size="small" column={1} bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="Employee">{rejectRec.personnel_name || `#${rejectRec.personnel_id}`}</Descriptions.Item>
            <Descriptions.Item label="Leave Type"><Tag color={ltColor(rejectRec.leave_type)}>{ltLabel(rejectRec.leave_type)}</Tag></Descriptions.Item>
            <Descriptions.Item label="Period">
              {dayjs(rejectRec.start_date).format('DD MMM YYYY')} – {dayjs(rejectRec.end_date).format('DD MMM YYYY')}
              {rejectRec.days_count ? ` (${rejectRec.days_count} days)` : ''}
            </Descriptions.Item>
          </Descriptions>
        )}
        <Input.TextArea rows={3} placeholder="Rejection reason (optional)" value={rejectNote}
          onChange={e => setRejectNote(e.target.value)} maxLength={500} showCount />
      </Modal>

      {/* ── Detail Drawer ── */}
      <Drawer title={<Space><EyeOutlined />Leave Details</Space>}
        open={detailOpen} onClose={() => setDetailOpen(false)} width={480} destroyOnHidden>
        {detailRec && (
          <>
            <Divider orientation="left" style={{ fontSize: 12 }}>Employee</Divider>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Name" span={2}>
                <strong>{detailRec.personnel_name || `#${detailRec.personnel_id}`}</strong>
              </Descriptions.Item>
              <Descriptions.Item label="Emp Code">{detailRec.personnel_emp_code || '—'}</Descriptions.Item>
              <Descriptions.Item label="Leave Type">
                <Tag color={ltColor(detailRec.leave_type)}>{ltLabel(detailRec.leave_type)}</Tag>
              </Descriptions.Item>
            </Descriptions>
            <Divider orientation="left" style={{ fontSize: 12, marginTop: 14 }}>Request Details</Divider>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Status" span={2}>
                {(() => { const c = stCfg(detailRec.status); return <Badge status={c.badge} text={c.label} />; })()}
              </Descriptions.Item>
              <Descriptions.Item label="Start">{detailRec.start_date ? dayjs(detailRec.start_date).format('DD MMM YYYY') : '—'}</Descriptions.Item>
              <Descriptions.Item label="End">{detailRec.end_date ? dayjs(detailRec.end_date).format('DD MMM YYYY') : '—'}</Descriptions.Item>
              <Descriptions.Item label="Days">{detailRec.days_count ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="Approved At">
                {detailRec.approved_at ? dayjs(detailRec.approved_at).format('DD MMM YYYY HH:mm') : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Reason" span={2}>{detailRec.reason || '—'}</Descriptions.Item>
              {detailRec.rejection_reason && (
                <Descriptions.Item label="Rejection Reason" span={2} style={{ color: '#f5222d' }}>
                  {detailRec.rejection_reason}
                </Descriptions.Item>
              )}
            </Descriptions>
            {detailRec.status === 'pending' && (
              <div style={{ marginTop: 16 }}>
                <Row gutter={8}>
                  <Col span={12}>
                    <Popconfirm title="Approve this leave?" onConfirm={() => { setDetailOpen(false); approveM.mutate(detailRec.id); }} okText="Approve">
                      <Button type="primary" icon={<CheckOutlined />} block>Approve</Button>
                    </Popconfirm>
                  </Col>
                  <Col span={12}>
                    <Button danger icon={<CloseOutlined />} block
                      onClick={() => { setDetailOpen(false); setRejectRec(detailRec); setRejectNote(''); setRejectOpen(true); }}>
                      Reject
                    </Button>
                  </Col>
                </Row>
              </div>
            )}
            {(detailRec.status === 'approved' || detailRec.status === 'on_leave') && (
              <div style={{ marginTop: 16 }}>
                <Popconfirm title="Cancel this leave?" onConfirm={() => { setDetailOpen(false); cancelM.mutate(detailRec.id); }} okText="Cancel" okButtonProps={{ danger: true }}>
                  <Button danger icon={<StopOutlined />} block>Cancel Leave</Button>
                </Popconfirm>
              </div>
            )}
          </>
        )}
      </Drawer>
    </div>
  );
};
// Who SeamlessHR says is on leave today (read-only, pulled nightly).
function SeamlessLeaveToday() {
  const { data } = useQuery({ queryKey: ['shr-leave-today'], queryFn: () => apiService.get('/api/v1/attendance/leaves/seamlesshr') });
  const rows = data?.data || [];
  return (
    <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', marginBottom: 16 }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>
        On leave today — from SeamlessHR <Tag color="blue" style={{ marginLeft: 6 }}>{rows.length}</Tag>
        {data?.last_pull && <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 400 }}> · last pulled {dayjs(data.last_pull).format('DD MMM HH:mm')}</span>}
      </div>
      {rows.length === 0 ? <span style={{ fontSize: 12, color: '#94a3b8' }}>Nobody is on leave in SeamlessHR today.</span>
        : <Space wrap size={[6, 6]}>{rows.map(r => (
            <Tag key={r.emp_code}>{r.name} · {r.department || '—'}{r.until ? ` · until ${dayjs(r.until).format('DD MMM')}` : ''}</Tag>))}</Space>}
    </div>
  );
}

export default LeavesTab;
