import React, { useState, useMemo } from 'react';
import {
  Table, Button, Space, Tag, App, Modal, Drawer,
  Select, Row, Col, Divider, Descriptions, Tooltip, Badge,
  Input, DatePicker, Form, InputNumber, TimePicker,
  Popover, Popconfirm, Alert,
} from 'antd';
import {
  PlusOutlined, CheckOutlined, CloseOutlined, EyeOutlined,
  ReloadOutlined, SearchOutlined, ClockCircleOutlined,
  CheckCircleOutlined, CloseCircleOutlined, EditOutlined,
  StopOutlined, SettingOutlined, HistoryOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService from '../../../services/api';
import dayjs from 'dayjs';
import { fmtT, ColTogglePopover, EmployeeCell, tableContainerStyle } from './shared';

const { Option } = Select;
const { RangePicker } = DatePicker;

const STATUS_CFG = {
  pending:   { label: 'Pending',   badge: 'warning',    tag: 'orange'  },
  approved:  { label: 'Approved',  badge: 'success',    tag: 'green'   },
  rejected:  { label: 'Rejected',  badge: 'error',      tag: 'red'     },
  cancelled: { label: 'Cancelled', badge: 'default',    tag: 'default' },
  processed: { label: 'Processed', badge: 'processing', tag: 'blue'    },
};
const stCfg = (s) => STATUS_CFG[s] || { label: s || 'Unknown', badge: 'default', tag: 'default' };

const OT_TYPE_COLOR = {
  daily:   'blue',
  weekly:  'purple',
  weekend: 'cyan',
  holiday: 'volcano',
  special: 'magenta',
};
const fmtHrs = (h) => h != null ? `${Number(h).toFixed(1)}h` : '—';

const OvertimeTab = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();

  const [search,     setSearch]     = useState('');
  const [filterSt,   setFilterSt]   = useState(null);
  const [filterType, setFilterType] = useState(null);
  const [dateRange,  setDateRange]  = useState(null);
  const [selected,   setSelected]   = useState([]);
  const [hiddenCols, setHiddenCols] = useState(new Set());
  const [colPopOpen, setColPopOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailId,   setDetailId]   = useState(null);
  const [formOpen,   setFormOpen]   = useState(false);
  const [editing,    setEditing]    = useState(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectRec,  setRejectRec]  = useState(null);
  const [rejectNote, setRejectNote] = useState('');
  const [form] = Form.useForm();

  const { data: personnelRaw } = useQuery({
    queryKey: ['personnel-dropdown-ot'],
    queryFn: () => apiService.get('/api/v1/personnel/?page_size=500'),
    staleTime: 60000,
  });
  const employees = useMemo(() => {
    const raw = personnelRaw?.results || personnelRaw?.data || personnelRaw || [];
    return Array.isArray(raw) ? raw : [];
  }, [personnelRaw]);

  const { data: summaryRaw } = useQuery({
    queryKey: ['ot-summary-att'],
    queryFn: () => apiService.get('/api/v1/attendance/overtime/summary'),
    staleTime: 60000,
  });
  const summary = summaryRaw?.data || summaryRaw || {};

  const startDate = dateRange?.[0]?.format('YYYY-MM-DD');
  const endDate   = dateRange?.[1]?.format('YYYY-MM-DD');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['att-overtime', filterSt, filterType, startDate, endDate],
    queryFn: () => {
      const p = {};
      if (filterSt)   p.status        = filterSt;
      if (filterType) p.overtime_type = filterType;
      if (startDate)  p.start_date    = startDate;
      if (endDate)    p.end_date      = endDate;
      return apiService.get('/api/v1/attendance/overtime', p);
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
      (r.reason             || '').toLowerCase().includes(q)
    );
  }, [rawRows, search]);

  const detailRec = useMemo(() => rows.find(r => r.id === detailId) ?? null, [rows, detailId]);

  const pending  = summary.pending  ?? rawRows.filter(r => r.status === 'pending').length;
  const approved = summary.approved ?? rawRows.filter(r => r.status === 'approved').length;
  const totalOTH = summary.total_overtime_hours != null
    ? Number(summary.total_overtime_hours).toFixed(1)
    : rawRows.filter(r => r.status === 'approved').reduce((s,r) => s + Number(r.overtime_hours||0), 0).toFixed(1);

  const onTimesChange = () => {
    setTimeout(() => {
      const s = form.getFieldValue('start_time');
      const e = form.getFieldValue('end_time');
      if (s && e && dayjs.isDayjs(s) && dayjs.isDayjs(e)) {
        const diff = e.diff(s, 'minute');
        if (diff > 0) {
          form.setFieldsValue({ hours_worked: Math.round((diff / 60) * 100) / 100 });
        }
      }
    }, 0);
  };

  const invalidate = () => {
    qc.invalidateQueries(['att-overtime']);
    qc.invalidateQueries(['ot-summary-att']);
  };

  const createM = useMutation({
    mutationFn: (d) => editing
      ? apiService.put(`/api/v1/attendance/overtime/${editing.id}`, d)
      : apiService.post('/api/v1/attendance/overtime', d),
    onSuccess: () => {
      message.success(editing ? 'Overtime updated' : 'Overtime request submitted');
      setFormOpen(false); setEditing(null); form.resetFields();
      invalidate();
    },
    onError: (e) => message.error(e?.message || 'Failed to submit overtime'),
  });

  const approveM = useMutation({
    mutationFn: (id) => apiService.put(`/api/v1/attendance/overtime/${id}/approve`),
    onSuccess: () => { message.success('Overtime approved'); invalidate(); },
    onError: (e) => message.error(e?.message || 'Failed to approve'),
  });

  const rejectM = useMutation({
    mutationFn: ({ id, rejection_reason }) =>
      apiService.put(`/api/v1/attendance/overtime/${id}/reject`, { rejection_reason }),
    onSuccess: () => {
      message.success('Overtime rejected');
      setRejectOpen(false); setRejectRec(null); setRejectNote('');
      invalidate();
    },
    onError: (e) => message.error(e?.message || 'Failed to reject'),
  });

  const cancelM = useMutation({
    mutationFn: (id) => apiService.put(`/api/v1/attendance/overtime/${id}/cancel`),
    onSuccess: () => { message.success('Overtime cancelled'); invalidate(); },
    onError: (e) => message.error(e?.message || 'Failed to cancel'),
  });

  const deleteM = useMutation({
    mutationFn: (id) => apiService.delete(`/api/v1/attendance/overtime/${id}`),
    onSuccess: () => { message.success('Overtime deleted'); invalidate(); },
    onError: (e) => message.error(e?.message || 'Failed to delete'),
  });

  const bulkApproveM = useMutation({
    mutationFn: (ids) => Promise.all(ids.map(id => apiService.put(`/api/v1/attendance/overtime/${id}/approve`))),
    onSuccess: (_, ids) => {
      message.success(`${ids.length} overtime(s) approved`);
      setSelected([]); invalidate();
    },
    onError: (e) => message.error(e?.message || 'Bulk approve failed'),
  });

  const openForm = (rec = null) => {
    setEditing(rec);
    setFormOpen(true);
    setTimeout(() => {
      form.resetFields();
      if (rec) {
        form.setFieldsValue({
          ...rec,
          date:       rec.date       ? dayjs(rec.date) : null,
          start_time: rec.start_time ? dayjs(rec.start_time, 'HH:mm:ss') : null,
          end_time:   rec.end_time   ? dayjs(rec.end_time,   'HH:mm:ss') : null,
        });
      }
    }, 0);
  };

  const submit = () => form.validateFields().then(v =>
    createM.mutate({
      ...v,
      date:       v.date?.format('YYYY-MM-DD') || null,
      start_time: v.start_time?.format('HH:mm:ss') || null,
      end_time:   v.end_time?.format('HH:mm:ss')   || null,
    })
  ).catch(() => {});

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
      title: 'Type', key: 'type', dataIndex: 'overtime_type', width: 100,
      render: t => <Tag color={OT_TYPE_COLOR[t] || 'default'}>{(t || '—').toUpperCase()}</Tag>,
    },
    {
      title: 'Date', key: 'date', dataIndex: 'date', width: 120,
      render: d => d ? dayjs(d).format('DD MMM YYYY') : '—',
    },
    { title: 'Start', key: 'start', dataIndex: 'start_time', width: 70, render: fmtT },
    { title: 'End',   key: 'end',   dataIndex: 'end_time',   width: 70, render: fmtT },
    {
      title: 'OT Hrs', key: 'ot_hrs', dataIndex: 'overtime_hours', width: 80,
      render: h => <Tag color="orange">{fmtHrs(h)}</Tag>,
    },
    {
      title: 'Compensation', key: 'comp', dataIndex: 'compensation_type', width: 110,
      render: t => t ? <Tag color="purple">{t.replace('_', ' ')}</Tag> : '—',
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
      title: 'Actions', key: 'act', fixed: 'right', width: 150,
      render: (_, r) => (
        <Space size={4} wrap>
          <Tooltip title="View">
            <Button size="small" icon={<EyeOutlined />} onClick={() => { setDetailId(r.id); setDetailOpen(true); }} />
          </Tooltip>
          {r.status === 'pending' && (
            <>
              <Popconfirm title="Approve this overtime?" onConfirm={() => approveM.mutate(r.id)} okText="Approve">
                <Tooltip title="Approve">
                  <Button size="small" type="primary" icon={<CheckOutlined />}
                    loading={approveM.isPending && approveM.variables === r.id} />
                </Tooltip>
              </Popconfirm>
              <Tooltip title="Reject">
                <Button size="small" danger icon={<CloseOutlined />}
                  onClick={() => { setRejectRec(r); setRejectNote(''); setRejectOpen(true); }} />
              </Tooltip>
              <Tooltip title="Edit">
                <Button size="small" icon={<EditOutlined />} onClick={() => openForm(r)} />
              </Tooltip>
            </>
          )}
          {r.status === 'approved' && (
            <Popconfirm title="Cancel this overtime?" onConfirm={() => cancelM.mutate(r.id)} okText="Cancel" okButtonProps={{ danger: true }}>
              <Tooltip title="Cancel"><Button size="small" danger icon={<StopOutlined />} /></Tooltip>
            </Popconfirm>
          )}
          {r.status !== 'approved' && (
            <Popconfirm title="Delete this overtime?" onConfirm={() => deleteM.mutate(r.id)} okText="Delete" okButtonProps={{ danger: true }}>
              <Tooltip title="Delete"><Button size="small" danger icon={<DeleteOutlined />} /></Tooltip>
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
      disabled: r.status === 'approved',
      title: r.status === 'approved' ? 'Approved requests cannot be selected' : '',
    }),
  };

  return (
    <div style={{ padding: 24 }}>
      <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message="SeamlessHR staff request overtime in SeamlessHR"
        description="SeamlessHR is the system of record for staff overtime — raise and approve it there and ApexPOB picks it up automatically. Use this screen only for contractors and others who are not in SeamlessHR." />
      <style>{`
        .ot-mod-table .ant-table-thead .ant-table-cell {
          background: #f8fafc !important; color: #64748b !important;
          font-size: 11px !important; font-weight: 700 !important;
          text-transform: uppercase !important; letter-spacing: 0.5px !important;
          border-bottom: 2px solid #e2e8f0 !important;
        }
      `}</style>

      {/* ── Stat cards ── */}
      <Row gutter={[14, 14]} style={{ marginBottom: 20 }}>
        {[
          { title: 'Total Requests',  value: summary.total ?? rawRows.length, icon: <HistoryOutlined />,     color: '#1890ff' },
          { title: 'Pending',         value: pending,                          icon: <ClockCircleOutlined />, color: '#fa8c16' },
          { title: 'Approved',        value: approved,                         icon: <CheckCircleOutlined />, color: '#52c41a' },
          { title: 'Approved OT Hrs', value: `${totalOTH}h`,                  icon: <ClockCircleOutlined />, color: '#722ed1' },
        ].map(s => (
          <Col xs={12} sm={6} key={s.title}>
            <div style={{ background:'#fff', borderRadius:12, border:'1px solid #e2e8f0', padding:'16px 18px', display:'flex', alignItems:'center', gap:14, boxShadow:'0 1px 3px rgba(0,0,0,0.06)', height:'100%' }}>
              <div style={{ width:44, height:44, borderRadius:10, flexShrink:0, background:`${s.color}18`, display:'flex', alignItems:'center', justifyContent:'center' }}>
                {React.cloneElement(s.icon, { style:{ fontSize:20, color:s.color } })}
              </div>
              <div>
                <div style={{ color:'#8c8c8c', fontSize:12, fontWeight:500 }}>{s.title}</div>
                <div style={{ fontSize: typeof s.value === 'string' ? 18 : 22, fontWeight:700, color:'#1f1f1f', lineHeight:1.2, marginTop:2 }}>{s.value}</div>
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
          <Col xs={12} sm={4} md={4}>
            <Select placeholder="Status" style={{ width: '100%' }} value={filterSt} onChange={setFilterSt} allowClear>
              {Object.entries(STATUS_CFG).map(([k, v]) => <Option key={k} value={k}>{v.label}</Option>)}
            </Select>
          </Col>
          <Col xs={12} sm={4} md={3}>
            <Select placeholder="OT Type" style={{ width: '100%' }} value={filterType} onChange={setFilterType} allowClear>
              {Object.entries(OT_TYPE_COLOR).map(([k]) => (
                <Option key={k} value={k}><Tag color={OT_TYPE_COLOR[k]}>{k.charAt(0).toUpperCase() + k.slice(1)}</Tag></Option>
              ))}
            </Select>
          </Col>
          <Col xs={24} sm={8} md={6}>
            <RangePicker style={{ width: '100%' }} value={dateRange} onChange={setDateRange} format="DD MMM YYYY" allowClear />
          </Col>
          <Col>
            <Space>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => openForm()}>New OT</Button>
              <Button icon={<ReloadOutlined />} onClick={() => { refetch(); invalidate(); }} loading={isLoading}>Refresh</Button>
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
            {selected.length} overtime{selected.length !== 1 ? 's' : ''} selected
            {pendingSelected.length < selected.length && (
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
          className="ot-mod-table"
          columns={cols}
          dataSource={rows}
          loading={isLoading}
          rowKey="id"
          size="middle"
          scroll={{ x: 1100 }}
          rowSelection={rowSelection}
          onRow={r => ({
            onMouseEnter: e => { e.currentTarget.style.background = '#f8fafc'; },
            onMouseLeave: e => { e.currentTarget.style.background = ''; },
          })}
          pagination={{ pageSize: 30, showSizeChanger: true, showTotal: (t, r) => `${r[0]}–${r[1]} of ${t}` }}
        />
      </div>

      {/* ── New / Edit Overtime Drawer ── */}
      <Drawer
        title={<Space><HistoryOutlined style={{ color: '#fa8c16' }} />{editing ? 'Edit Overtime' : 'New Overtime Request'}</Space>}
        open={formOpen} onClose={() => { setFormOpen(false); setEditing(null); form.resetFields(); }}
        width={680} destroyOnHidden
        footer={<Space style={{ float: 'right' }}>
          <Button onClick={() => { setFormOpen(false); setEditing(null); form.resetFields(); }}>Cancel</Button>
          <Button type="primary" onClick={submit} loading={createM.isPending}>{editing ? 'Update' : 'Submit'}</Button>
        </Space>}>
        <Form form={form} layout="vertical" size="small">
          <Divider orientation="left" style={{ fontSize: 12 }}>Employee & Type</Divider>
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
              <Form.Item name="overtime_type" label="OT Type *" rules={[{ required: true }]}>
                <Select size="middle" placeholder="Select type">
                  {Object.entries(OT_TYPE_COLOR).map(([k]) => (
                    <Option key={k} value={k}><Tag color={OT_TYPE_COLOR[k]}>{k.charAt(0).toUpperCase() + k.slice(1)}</Tag></Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Divider orientation="left" style={{ fontSize: 12 }}>Date & Time</Divider>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="date" label="Date *" rules={[{ required: true }]}>
                <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" size="middle" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="start_time" label="Start Time">
                <TimePicker format="HH:mm" style={{ width: '100%' }} size="middle" onChange={onTimesChange} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="end_time" label="End Time">
                <TimePicker format="HH:mm" style={{ width: '100%' }} size="middle" onChange={onTimesChange} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="hours_worked" label="Hrs Worked (auto)">
                <InputNumber min={0} step={0.25} style={{ width: '100%' }} size="middle" precision={2} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="overtime_hours" label="OT Hours">
                <InputNumber min={0} step={0.25} style={{ width: '100%' }} size="middle" precision={2} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="compensation_type" label="Compensation">
                <Select size="middle" placeholder="Select" allowClear>
                  <Option value="pay">Pay</Option>
                  <Option value="time_off">Time Off</Option>
                  <Option value="mixed">Mixed</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="reason" label="Reason">
            <Input.TextArea rows={3} size="middle" placeholder="Reason for overtime…" maxLength={500} showCount />
          </Form.Item>
        </Form>
      </Drawer>

      {/* ── Reject Modal ── */}
      <Modal title={<Space><CloseOutlined style={{ color: '#f5222d' }} />Reject Overtime Request</Space>}
        open={rejectOpen}
        onOk={() => rejectM.mutate({ id: rejectRec?.id, rejection_reason: rejectNote })}
        onCancel={() => { setRejectOpen(false); setRejectRec(null); setRejectNote(''); }}
        confirmLoading={rejectM.isPending} okButtonProps={{ danger: true }} okText="Reject" destroyOnHidden>
        {rejectRec && (
          <Descriptions size="small" column={1} bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="Employee">{rejectRec.personnel_name || `#${rejectRec.personnel_id}`}</Descriptions.Item>
            <Descriptions.Item label="Type"><Tag color={OT_TYPE_COLOR[rejectRec.overtime_type] || 'default'}>{rejectRec.overtime_type?.toUpperCase()}</Tag></Descriptions.Item>
            <Descriptions.Item label="Date">{rejectRec.date ? dayjs(rejectRec.date).format('DD MMM YYYY') : '—'}</Descriptions.Item>
            <Descriptions.Item label="OT Hours">{fmtHrs(rejectRec.overtime_hours)}</Descriptions.Item>
          </Descriptions>
        )}
        <Input.TextArea rows={3} placeholder="Rejection reason (required)"
          value={rejectNote} onChange={e => setRejectNote(e.target.value)} maxLength={500} showCount />
      </Modal>

      {/* ── Detail Drawer ── */}
      <Drawer title={<Space><EyeOutlined />Overtime Details</Space>}
        open={detailOpen} onClose={() => setDetailOpen(false)} width={480} destroyOnHidden>
        {detailRec && (
          <>
            <Divider orientation="left" style={{ fontSize: 12 }}>Employee</Divider>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Name" span={2}>
                <strong>{detailRec.personnel_name || `#${detailRec.personnel_id}`}</strong>
              </Descriptions.Item>
              <Descriptions.Item label="Emp Code">{detailRec.personnel_emp_code || '—'}</Descriptions.Item>
              <Descriptions.Item label="Status">
                {(() => { const c = stCfg(detailRec.status); return <Badge status={c.badge} text={c.label} />; })()}
              </Descriptions.Item>
            </Descriptions>
            <Divider orientation="left" style={{ fontSize: 12, marginTop: 14 }}>Overtime Details</Divider>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Type">
                <Tag color={OT_TYPE_COLOR[detailRec.overtime_type] || 'default'}>{detailRec.overtime_type?.toUpperCase()}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Date">{detailRec.date ? dayjs(detailRec.date).format('DD MMM YYYY') : '—'}</Descriptions.Item>
              <Descriptions.Item label="Start">{fmtT(detailRec.start_time)}</Descriptions.Item>
              <Descriptions.Item label="End">{fmtT(detailRec.end_time)}</Descriptions.Item>
              <Descriptions.Item label="Hrs Worked">{fmtHrs(detailRec.hours_worked)}</Descriptions.Item>
              <Descriptions.Item label="OT Hours"><Tag color="orange">{fmtHrs(detailRec.overtime_hours)}</Tag></Descriptions.Item>
              <Descriptions.Item label="Compensation">{detailRec.compensation_type ? <Tag color="purple">{detailRec.compensation_type.replace('_', ' ')}</Tag> : '—'}</Descriptions.Item>
              <Descriptions.Item label="Approved At">{detailRec.approved_at ? dayjs(detailRec.approved_at).format('DD MMM YYYY HH:mm') : '—'}</Descriptions.Item>
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
                  <Col span={8}>
                    <Popconfirm title="Approve?" onConfirm={() => { setDetailOpen(false); approveM.mutate(detailRec.id); }} okText="Approve">
                      <Button type="primary" icon={<CheckOutlined />} block>Approve</Button>
                    </Popconfirm>
                  </Col>
                  <Col span={8}>
                    <Button danger icon={<CloseOutlined />} block
                      onClick={() => { setDetailOpen(false); setRejectRec(detailRec); setRejectNote(''); setRejectOpen(true); }}>
                      Reject
                    </Button>
                  </Col>
                  <Col span={8}>
                    <Button icon={<EditOutlined />} block onClick={() => { setDetailOpen(false); openForm(detailRec); }}>
                      Edit
                    </Button>
                  </Col>
                </Row>
              </div>
            )}
            {detailRec.status === 'approved' && (
              <div style={{ marginTop: 16 }}>
                <Popconfirm title="Cancel this overtime?" onConfirm={() => { setDetailOpen(false); cancelM.mutate(detailRec.id); }} okText="Cancel" okButtonProps={{ danger: true }}>
                  <Button danger icon={<StopOutlined />} block>Cancel Overtime</Button>
                </Popconfirm>
              </div>
            )}
          </>
        )}
      </Drawer>
    </div>
  );
};
export default OvertimeTab;
