import React, { useState, useMemo } from 'react';
import {
  Table, Button, Space, Tag, App, Modal,
  Drawer, Select, Row, Col, Divider, Descriptions, Tooltip,
  Badge, Input, DatePicker, Popover,
} from 'antd';
import {
  ReloadOutlined, EyeOutlined, SettingOutlined,
  WarningOutlined, ClockCircleOutlined, CheckOutlined,
  StopOutlined, FilterOutlined, CloseOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService from '../../../services/api';
import dayjs from 'dayjs';
import { ColTogglePopover, EmployeeCell, tableContainerStyle } from './shared';

const { Option } = Select;
const { RangePicker } = DatePicker;

const EX_TYPE = {
  late_arrival:    { label:'Late Arrival',    color:'warning', tag:'orange'  },
  early_departure: { label:'Early Departure', color:'warning', tag:'gold'    },
  absent:          { label:'Absent',          color:'error',   tag:'red'     },
  missing_punch:   { label:'Missing Punch',   color:'error',   tag:'volcano' },
  overtime:        { label:'Overtime',        color:'processing', tag:'blue' },
  area_mismatch:   { label:'Area Mismatch',   color:'default', tag:'purple'  },
};
const HANDLED_LABEL = { approve:'Excused', ignore:'Dismissed', flag:'Flagged' };
const exCfg = (t) => EX_TYPE[t] || { label: t||'Unknown', color:'default', tag:'default' };

const HANDLE_OPT = [
  { value:'approve', label:'Approve / Excuse' },
  { value:'ignore',  label:'Ignore / Dismiss' },
  { value:'flag',    label:'Flag for Review'  },
];

const ExceptionsTab = () => {
  const { message } = App.useApp();
  const [filterType,   setFilterType]   = useState(null);
  const [filterDept,   setFilterDept]   = useState(null);
  const [search,       setSearch]       = useState('');
  const [dateRange,    setDateRange]    = useState([dayjs().startOf('month'), dayjs()]);
  const [detailOpen,   setDetailOpen]   = useState(false);
  const [detailId,     setDetailId]     = useState(null);
  const [selected,     setSelected]     = useState([]);
  const [handleOpen,   setHandleOpen]   = useState(false);
  const [handleAction, setHandleAction] = useState('approve');
  const [handleNote,   setHandleNote]   = useState('');
  const [hiddenCols,   setHiddenCols]   = useState(new Set());
  const [colPopOpen,   setColPopOpen]   = useState(false);
  const qc = useQueryClient();

  const startDate = dateRange?.[0]?.format('YYYY-MM-DD') ?? dayjs().format('YYYY-MM-DD');
  const endDate   = dateRange?.[1]?.format('YYYY-MM-DD') ?? dayjs().format('YYYY-MM-DD');

  const { data: deptData } = useQuery({
    queryKey: ['departments'],
    queryFn:  () => apiService.get('/api/v1/departments/'),
  });
  const departments = Array.isArray(deptData) ? deptData : (deptData?.data || []);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['att-exceptions', filterType, filterDept, search, startDate, endDate],
    queryFn: () => {
      const p = new URLSearchParams();
      p.append('start_date', startDate);
      p.append('end_date', endDate);
      if (filterType) p.append('type', filterType);
      if (filterDept) p.append('dept_id', filterDept);
      if (search)     p.append('search', search);
      return apiService.get(`/api/v1/attendance/exceptions?${p}`);
    },
    refetchInterval: 30000,
  });
  const rows = data?.data || [];
  const detailRec = useMemo(() => rows.find(r => r.id === detailId) ?? null, [rows, detailId]);

  const handleM = useMutation({
    mutationFn: ({ ids, action, note }) =>
      apiService.post('/api/v1/attendance/exceptions/handle', { ids, action, note }),
    onSuccess: (_, v) => {
      message.success(`${v.ids.length} exception(s) ${v.action}d`);
      setHandleOpen(false); setSelected([]); setHandleNote('');
      qc.invalidateQueries(['att-exceptions']);
    },
    onError: (e) => message.error(e?.message || 'Action failed'),
  });

  const openHandle = (ids) => { setSelected(ids); setHandleOpen(true); };

  const toggleCol = (key) => setHiddenCols(prev => {
    const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n;
  });

  const lateCount    = rows.filter(r => r.exception_type === 'late_arrival').length;
  const absentCount  = rows.filter(r => r.exception_type === 'absent').length;
  const missingCount = rows.filter(r => r.exception_type === 'missing_punch').length;
  const openCount    = rows.filter(r => !r.handled_at).length;

  const COL_DEFS = [
    { title:'Employee', key:'employee',
      render: (_,r) => (
        <EmployeeCell
          name={r.emp_name || `Employee #${r.emp_id}`}
          code={r.emp_code || ''}
          onClick={() => { setDetailId(r.id); setDetailOpen(true); }}
        />
      ),
    },
    { title:'Date',      key:'date',    dataIndex:'att_date', width:130,
      render: d => d ? dayjs(d).format('DD MMM YYYY') : '—' },
    { title:'Exception', key:'type',    dataIndex:'exception_type', width:150,
      render: t => { const c = exCfg(t); return <Tag color={c.tag}>{c.label}</Tag>; } },
    { title:'Deviation', key:'dev',     dataIndex:'deviation_minutes', width:110,
      render: m => m ? <Tag color={m > 60 ? 'red' : 'orange'}>{m} min</Tag> : '—' },
    { title:'Note',      key:'note',    dataIndex:'exception_note', ellipsis:true },
    { title:'Status',    key:'status',  dataIndex:'handled_at', width:110,
      render: (v, r) => v
        ? <Badge status={r.handle_action === 'flag' ? 'error' : 'success'} text={HANDLED_LABEL[r.handle_action] || 'Handled'} />
        : <Badge status="warning" text="Open" /> },
  ];

  const cols = useMemo(() => {
    const visible = COL_DEFS.filter(c => !hiddenCols.has(c.key));
    return [...visible, {
      title:'Actions', key:'act', fixed:'right', width:120,
      render: (_,r) => (
        <Space size={4}>
          <Tooltip title="View">
            <Button size="small" icon={<EyeOutlined />} onClick={() => { setDetailId(r.id); setDetailOpen(true); }} />
          </Tooltip>
          {!r.handled_at && (
            <Tooltip title="Handle">
              <Button size="small" type="primary" icon={<CheckOutlined />}
                onClick={() => openHandle([r.id])} />
            </Tooltip>
          )}
        </Space>
      ),
    }];
  }, [hiddenCols]);

  const rowSelection = {
    selectedRowKeys: selected,
    onChange: setSelected,
    getCheckboxProps: (r) => ({ disabled: !!r.handled_at }),
  };

  return (
    <div style={{ padding:24 }}>
      <style>{`
        .exc-mod-table .ant-table-thead .ant-table-cell {
          background: #f8fafc !important; color: #64748b !important;
          font-size: 11px !important; font-weight: 700 !important;
          text-transform: uppercase !important; letter-spacing: 0.5px !important;
          border-bottom: 2px solid #e2e8f0 !important;
        }
      `}</style>

      {/* ── Stat cards ── */}
      <Row gutter={[14,14]} style={{ marginBottom:20 }}>
        {[
          { title:'Open Exceptions', value:openCount,    icon:<WarningOutlined />,     color:'#fa8c16' },
          { title:'Late Arrivals',   value:lateCount,    icon:<ClockCircleOutlined />, color:'#faad14' },
          { title:'Absences',        value:absentCount,  icon:<StopOutlined />,        color:'#f5222d' },
          { title:'Missing Punches', value:missingCount, icon:<FilterOutlined />,      color:'#722ed1' },
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
        <Row gutter={[12,8]} align="middle">
          <Col xs={12} sm={5} md={4}>
            <Select placeholder="Exception type" style={{ width:'100%' }} value={filterType}
              onChange={setFilterType} allowClear>
              {Object.entries(EX_TYPE).map(([k,v]) => <Option key={k} value={k}>{v.label}</Option>)}
            </Select>
          </Col>
          <Col xs={12} sm={5} md={4}>
            <Select placeholder="Department" style={{ width:'100%' }} value={filterDept}
              onChange={setFilterDept} allowClear showSearch
              filterOption={(input, option) => option?.children?.toLowerCase().includes(input.toLowerCase())}>
              {departments.map(d => <Option key={d.id} value={d.id}>{d.name}</Option>)}
            </Select>
          </Col>
          <Col xs={24} sm={10} md={6}>
            <RangePicker style={{ width:'100%' }} value={dateRange} onChange={setDateRange}
              format="DD MMM YYYY" allowClear />
          </Col>
          <Col xs={24} sm={8} md={5}>
            <Input.Search placeholder="Search employee…" value={search}
              onChange={e => setSearch(e.target.value)} onSearch={setSearch} allowClear />
          </Col>
          <Col>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading}>Refresh</Button>
              <Popover
                title="Show / Hide Columns" trigger="click"
                open={colPopOpen} onOpenChange={setColPopOpen}
                content={<ColTogglePopover colDefs={COL_DEFS} hidden={hiddenCols} onToggle={toggleCol} />}>
                <Tooltip title="Adjust columns">
                  <Button icon={<SettingOutlined />} />
                </Tooltip>
              </Popover>
            </Space>
          </Col>
        </Row>
      </div>

      {/* ── Bulk bar ── */}
      {selected.length > 0 && (
        <div style={{ background:'#1d4ed8', borderRadius:10, padding:'10px 16px', marginBottom:12, display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <span style={{ color:'#fff', fontWeight:600, fontSize:13 }}>
            {selected.length} exception{selected.length !== 1 ? 's' : ''} selected
          </span>
          <Space>
            <Button type="primary" size="small" icon={<CheckOutlined />}
              style={{ background:'rgba(255,255,255,0.15)', border:'1px solid rgba(255,255,255,0.3)', color:'#fff' }}
              onClick={() => openHandle(selected)}>
              Handle {selected.length} Selected
            </Button>
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
          className="exc-mod-table"
          columns={cols}
          dataSource={rows}
          loading={isLoading}
          rowKey="id"
          size="middle"
          scroll={{ x:1000 }}
          rowSelection={rowSelection}
          onRow={r => ({
            onMouseEnter: e => { e.currentTarget.style.background = '#f8fafc'; },
            onMouseLeave: e => { e.currentTarget.style.background = ''; },
          })}
          pagination={{ pageSize:30, showSizeChanger:true, showTotal:(t,r)=>`${r[0]}–${r[1]} of ${t}` }}
        />
      </div>

      {/* ── Handle Modal ── */}
      <Modal title={<Space><CheckOutlined />Handle Exception(s)</Space>}
        open={handleOpen} onCancel={() => { setHandleOpen(false); setHandleNote(''); }}
        onOk={() => handleM.mutate({ ids:selected, action:handleAction, note:handleNote })}
        okText="Confirm" confirmLoading={handleM.isPending} destroyOnHidden>
        <div style={{ marginBottom:12 }}>
          <div style={{ fontWeight:600, marginBottom:8 }}>Action for {selected.length} exception(s):</div>
          <Select value={handleAction} onChange={setHandleAction} style={{ width:'100%' }} size="middle">
            {HANDLE_OPT.map(o => <Option key={o.value} value={o.value}>{o.label}</Option>)}
          </Select>
        </div>
        <div>
          <div style={{ fontWeight:600, marginBottom:8 }}>Note (optional):</div>
          <Input.TextArea rows={3} value={handleNote} onChange={e => setHandleNote(e.target.value)}
            placeholder="Add a note or reason…" />
        </div>
      </Modal>

      {/* ── Detail Drawer ── */}
      <Drawer title={<Space><EyeOutlined />Exception Details</Space>}
        open={detailOpen} onClose={() => setDetailOpen(false)} width={460} destroyOnHidden>
        {detailRec && (
          <>
            <Divider orientation="left" style={{ fontSize:12 }}>Employee</Divider>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Name" span={2}><strong>{detailRec.emp_name||`#${detailRec.emp_id}`}</strong></Descriptions.Item>
              <Descriptions.Item label="Code">{detailRec.emp_code||'—'}</Descriptions.Item>
              <Descriptions.Item label="Date">{detailRec.att_date ? dayjs(detailRec.att_date).format('DD MMM YYYY') : '—'}</Descriptions.Item>
            </Descriptions>
            <Divider orientation="left" style={{ fontSize:12, marginTop:14 }}>Exception</Divider>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Type" span={2}>
                {(() => { const c = exCfg(detailRec.exception_type); return <Tag color={c.tag}>{c.label}</Tag>; })()}
              </Descriptions.Item>
              <Descriptions.Item label="Deviation">{detailRec.deviation_minutes ? `${detailRec.deviation_minutes} min` : '—'}</Descriptions.Item>
              <Descriptions.Item label="Status">
                {detailRec.handled_at
                  ? <Badge status="success" text={HANDLED_LABEL[detailRec.handle_action] || 'Handled'} />
                  : <Badge status="warning" text="Open" />}
              </Descriptions.Item>
              <Descriptions.Item label="Note" span={2}>{detailRec.exception_note||'—'}</Descriptions.Item>
              <Descriptions.Item label="Handled At" span={2}>
                {detailRec.handled_at ? dayjs(detailRec.handled_at).format('DD MMM YYYY HH:mm') : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Handle Note" span={2}>{detailRec.handle_note||'—'}</Descriptions.Item>
            </Descriptions>
            {!detailRec.handled_at && (
              <div style={{ marginTop:16 }}>
                <Button type="primary" icon={<CheckOutlined />} block
                  onClick={() => { setDetailOpen(false); openHandle([detailRec.id]); }}>
                  Handle this Exception
                </Button>
              </div>
            )}
          </>
        )}
      </Drawer>
    </div>
  );
};
export default ExceptionsTab;
