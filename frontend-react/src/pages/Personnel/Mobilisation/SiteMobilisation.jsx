import { useState } from 'react';
import {
  Table, Button, Space, Input, Select, DatePicker, Drawer, Form, Row, Col, Card, Statistic,
  Tag, Progress, Alert, App, Modal, Segmented, Tooltip, Descriptions, List, Typography, Popconfirm,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, CheckCircleFilled, CloseCircleFilled, ExclamationCircleFilled,
  MinusCircleOutlined, RocketOutlined, UndoOutlined, CheckOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import apiService from '../../../services/api';

const { Text } = Typography;
const DT_FORMATS = ['DD MMM YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD', 'D/M/YYYY'];
const API = '/api/v1/mobilisation';

const STATE_ICON = {
  pass: <CheckCircleFilled style={{ color: '#52c41a', fontSize: 18 }} />,
  warn: <ExclamationCircleFilled style={{ color: '#faad14', fontSize: 18 }} />,
  fail: <CloseCircleFilled style={{ color: '#f5222d', fontSize: 18 }} />,
  na:   <MinusCircleOutlined style={{ color: '#bfbfbf', fontSize: 18 }} />,
};
const FIX_HINT = {
  medical: 'Record the medical fitness date on the person (Personnel → edit).',
  certificates: 'Record certificates in Personnel → Training.',
  card: 'Add the access card number on the person.',
  card_loaded: 'Loaded automatically once the person has a card (Access Control → controller sync).',
  biometric: 'Enrol a fingerprint or face on a reader.',
  emergency_contact: 'Add the emergency contact on the person.',
  phone: 'Phone comes from SeamlessHR for staff; add it on the person for contractors.',
  travel: 'Book them on a flight (Transport Manifest) or a land journey.',
};

const personTag = p => p?.hr_source === 'SEAMLESSHR'
  ? <Tag color="blue">SeamlessHR</Tag> : <Tag>{p?.company || 'Contractor / other'}</Tag>;

const statusTag = r => {
  if (r.status === 'MOBILISED') return <Tag color="green">Mobilised {r.mobilised_at ? dayjs(r.mobilised_at).format('DD MMM') : ''}</Tag>;
  if (r.status === 'CANCELLED') return <Tag>Cancelled</Tag>;
  return r.ready
    ? <Tag color="success">Ready</Tag>
    : <Tooltip title={`Outstanding: ${(r.blocking || []).join(', ')}`}><Tag color="error">Not ready · {r.blocking?.length}</Tag></Tooltip>;
};

export default function SiteMobilisation() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [status, setStatus] = useState('PREPARING');
  const [search, setSearch] = useState('');
  const [addOpen, setAddOpen] = useState(false);
  const [openId, setOpenId] = useState(null);
  const [override, setOverride] = useState(null);       // {blocking} when mobilising with items outstanding
  const [reason, setReason] = useState('');
  const [tickFor, setTickFor] = useState(null);         // manual item being confirmed
  const [tickNote, setTickNote] = useState('');
  const [form] = Form.useForm();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['mobilisation', status, search],
    queryFn: () => apiService.get(`${API}?${new URLSearchParams({ ...(status !== 'ALL' && { status }), ...(search && { search }) })}`),
  });
  const rows = data?.data || [];
  const stats = data?.stats || {};

  const { data: people } = useQuery({
    queryKey: ['mob-people'],
    queryFn: () => apiService.get('/api/v1/personnel/?status=ACTIVE&page_size=500'),
    enabled: addOpen,
  });

  const { data: detail, isFetching: detailLoading } = useQuery({
    queryKey: ['mobilisation-detail', openId],
    queryFn: () => apiService.get(`${API}/${openId}`),
    enabled: !!openId,
  });

  const refresh = () => { qc.invalidateQueries(['mobilisation']); qc.invalidateQueries(['mobilisation-detail']); };
  const fail = e => message.error(e?.message || 'Failed');

  const createM = useMutation({
    mutationFn: v => apiService.post(API, {
      personnel_ids: v.personnel_ids, mobilise_date: v.mobilise_date.format('YYYY-MM-DD'), notes: v.notes,
    }),
    onSuccess: r => {
      const skipped = r?.skipped || [];
      message.success(`${r?.created?.length || 0} added to mobilisation`);
      if (skipped.length) message.warning(`Skipped: ${skipped.map(s => `${s.name || s.personnel_id} (${s.reason})`).join(', ')}`, 6);
      setAddOpen(false); form.resetFields(); refresh();
    },
    onError: fail,
  });
  const tickM = useMutation({
    mutationFn: ({ item, done, note }) => apiService.post(`${API}/${openId}/check`, { item, done, note }),
    onSuccess: (_, v) => { message.success(v.done ? 'Confirmed' : 'Confirmation removed'); setTickFor(null); setTickNote(''); refresh(); },
    onError: fail,
  });
  const dateM = useMutation({
    mutationFn: d => apiService.put(`${API}/${openId}`, { mobilise_date: d.format('YYYY-MM-DD') }),
    onSuccess: () => { message.success('Mobilisation date changed'); refresh(); },
    onError: fail,
  });
  const mobiliseM = useMutation({
    mutationFn: r => apiService.post(`${API}/${openId}/mobilise`, { override_reason: r || null }),
    onSuccess: () => { message.success('Marked as mobilised'); setOverride(null); setReason(''); setOpenId(null); refresh(); },
    onError: fail,
  });
  const cancelM = useMutation({
    mutationFn: () => apiService.post(`${API}/${openId}/cancel`, {}),
    onSuccess: () => { message.success('Mobilisation cancelled'); setOpenId(null); refresh(); },
    onError: fail,
  });

  const startMobilise = () => (detail?.ready ? mobiliseM.mutate(null) : setOverride({ blocking: detail?.blocking || [] }));

  const columns = [
    { title: 'Person', key: 'p', render: (_, r) => (
      <Space direction="vertical" size={0}>
        <a onClick={() => setOpenId(r.id)}><strong>{r.person?.name}</strong></a>
        <Text type="secondary" style={{ fontSize: 12 }}>{r.person?.emp_code} · {r.person?.department || 'No department'}</Text>
      </Space>) },
    { title: 'Source', key: 's', width: 160, render: (_, r) => personTag(r.person) },
    { title: 'Mobilise on', dataIndex: 'mobilise_date', width: 130, render: d => {
      const late = dayjs(d).isBefore(dayjs(), 'day');
      return <span style={{ color: late ? '#f5222d' : undefined }}>{dayjs(d).format('ddd DD MMM YYYY')}</span>;
    } },
    { title: 'Checklist', key: 'c', width: 200, render: (_, r) => r.status === 'PREPARING'
      ? <Progress percent={Math.round(100 * (r.done || 0) / (r.total || 1))} size="small"
          status={r.ready ? 'success' : 'active'} format={() => `${r.done}/${r.total}`} />
      : (r.override_reason ? <Tooltip title={r.override_reason}><Tag color="orange">With items outstanding</Tag></Tooltip> : '—') },
    { title: 'Status', key: 'st', width: 150, render: (_, r) => statusTag(r) },
    { title: '', key: 'a', width: 80, render: (_, r) => <Button size="small" onClick={() => setOpenId(r.id)}>Open</Button> },
  ];

  const items = detail?.items || [];
  const preparing = detail?.status === 'PREPARING';

  return (
    <div style={{ padding: 24 }}>
      <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message="Site mobilisation — is this person ready to go to site?"
        description="Who the person is comes from SeamlessHR. The checklist reads medical, certificates, access card, emergency contact and travel straight from the records, so fix the record and the item turns green; HSE confirms induction and PPE here. Mobilising does not put anyone on board — POB comes from the access readers and journeys." />
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {[['Being prepared', stats.preparing], ['Ready', stats.ready, '#52c41a'], ['Not ready', stats.not_ready, '#f5222d'],
          ['Due within 7 days, not ready', stats.due_7_days_not_ready, '#fa8c16'], ['Mobilised', stats.mobilised, '#1677ff']]
          .map(([t, v, c]) => (
            <Col xs={12} md={8} lg={4} key={t}><Card size="small"><Statistic title={t} value={v || 0} valueStyle={{ color: c }} /></Card></Col>
          ))}
      </Row>
      <Space wrap style={{ marginBottom: 12 }}>
        <Segmented value={status} onChange={setStatus}
          options={[{ label: 'Being prepared', value: 'PREPARING' }, { label: 'Mobilised', value: 'MOBILISED' },
            { label: 'Cancelled', value: 'CANCELLED' }, { label: 'All', value: 'ALL' }]} />
        <Input.Search allowClear placeholder="Search name / code" onSearch={setSearch} style={{ width: 240 }} />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>Add people</Button>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>Refresh</Button>
      </Space>
      <Table rowKey="id" size="middle" loading={isLoading} dataSource={rows} columns={columns}
        pagination={{ pageSize: 20 }} locale={{ emptyText: 'Nobody is being prepared for site — use “Add people”.' }} />

      <Modal title="Add people to mobilise" open={addOpen} onCancel={() => setAddOpen(false)}
        onOk={() => form.validateFields().then(v => createM.mutate(v)).catch(() => {})}
        okText="Add" confirmLoading={createM.isPending} destroyOnHidden>
        <Form form={form} layout="vertical" name="mobilise_add">
          <Form.Item name="personnel_ids" label="People" rules={[{ required: true, message: 'Pick at least one person' }]}>
            <Select mode="multiple" showSearch optionFilterProp="label" placeholder="Search staff / contractors"
              options={(people?.results || []).map(p => ({ value: p.id, label: `${p.full_name || `${p.first_name} ${p.last_name}`} · ${p.emp_code}` }))} />
          </Form.Item>
          <Form.Item name="mobilise_date" label="Mobilise on" rules={[{ required: true }]}>
            <DatePicker format={DT_FORMATS} style={{ width: '100%' }} disabledDate={d => d && d.isBefore(dayjs(), 'day')} />
          </Form.Item>
          <Form.Item name="notes" label="Notes (rotation, crew change…)"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      <Drawer width={620} open={!!openId} onClose={() => setOpenId(null)} destroyOnHidden
        title={detail ? <Space>{detail.person?.name} {personTag(detail.person)} {statusTag(detail)}</Space> : 'Mobilisation'}
        extra={preparing && (
          <Space>
            <Popconfirm title="Cancel this mobilisation?" onConfirm={() => cancelM.mutate()} okText="Cancel it" okButtonProps={{ danger: true }}>
              <Button danger>Cancel</Button>
            </Popconfirm>
            <Button type="primary" icon={<RocketOutlined />} loading={mobiliseM.isPending} onClick={startMobilise}>Mobilise</Button>
          </Space>)}>
        {detail && (
          <>
            <Descriptions size="small" column={2} bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label="Code">{detail.person?.emp_code}</Descriptions.Item>
              <Descriptions.Item label="Department">{detail.person?.department || '—'}</Descriptions.Item>
              <Descriptions.Item label="Position">{detail.person?.position || '—'}</Descriptions.Item>
              <Descriptions.Item label="On board now">{detail.person?.is_onboard ? 'Yes' : 'No'}</Descriptions.Item>
              <Descriptions.Item label="Mobilise on" span={2}>
                {preparing
                  ? <DatePicker value={dayjs(detail.mobilise_date)} format={DT_FORMATS} allowClear={false}
                      onChange={d => d && dateM.mutate(d)} />
                  : dayjs(detail.mobilise_date).format('ddd DD MMM YYYY')}
              </Descriptions.Item>
              {detail.notes && <Descriptions.Item label="Notes" span={2}>{detail.notes}</Descriptions.Item>}
              {detail.status === 'MOBILISED' && (
                <Descriptions.Item label="Mobilised" span={2}>
                  {dayjs(detail.mobilised_at).format('DD MMM YYYY HH:mm')} by {detail.mobilised_by}
                  {detail.override_reason && <div><Tag color="orange">Outstanding: {(detail.outstanding || []).join(', ')}</Tag> Reason: {detail.override_reason}</div>}
                </Descriptions.Item>)}
            </Descriptions>
            <List loading={detailLoading} dataSource={items} renderItem={it => (
              <List.Item
                actions={it.kind === 'manual' && preparing ? [
                  it.state === 'pass' && it.by
                    ? <Button size="small" icon={<UndoOutlined />} onClick={() => tickM.mutate({ item: it.code, done: false })}>Undo</Button>
                    : it.state !== 'pass' && <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => setTickFor(it)}>Confirm</Button>,
                ].filter(Boolean) : []}>
                <List.Item.Meta avatar={STATE_ICON[it.state]}
                  title={<Space>{it.label}{!it.required && <Text type="secondary" style={{ fontSize: 12 }}>(optional)</Text>}</Space>}
                  description={<>
                    <div>{it.detail}</div>
                    {it.kind === 'auto' && it.state !== 'pass' && it.state !== 'na' && FIX_HINT[it.code] &&
                      <Text type="secondary" style={{ fontSize: 12 }}>{FIX_HINT[it.code]}</Text>}
                  </>} />
              </List.Item>)} />
          </>
        )}
      </Drawer>

      <Modal title={`Confirm: ${tickFor?.label}`} open={!!tickFor} onCancel={() => setTickFor(null)}
        onOk={() => tickM.mutate({ item: tickFor.code, done: true, note: tickNote || null })}
        okText="Confirm" confirmLoading={tickM.isPending} destroyOnHidden>
        <Input.TextArea rows={2} value={tickNote} onChange={e => setTickNote(e.target.value)}
          placeholder="Note (optional) — e.g. coverall, boots, helmet; room B12" />
      </Modal>

      <Modal title="Not ready — mobilise anyway?" open={!!override} onCancel={() => setOverride(null)}
        onOk={() => mobiliseM.mutate(reason)} okText="Mobilise anyway" okButtonProps={{ danger: true, disabled: reason.trim().length < 5 }}
        confirmLoading={mobiliseM.isPending} destroyOnHidden>
        <Alert type="warning" showIcon style={{ marginBottom: 12 }} message="Still outstanding"
          description={<ul style={{ margin: 0, paddingLeft: 18 }}>{(override?.blocking || []).map(b => <li key={b}>{b}</li>)}</ul>} />
        <Input.TextArea rows={3} value={reason} onChange={e => setReason(e.target.value)}
          placeholder="Reason (required) — kept on record with what was outstanding" />
      </Modal>
    </div>
  );
}
