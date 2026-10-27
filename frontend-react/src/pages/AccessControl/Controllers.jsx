import React, { useState } from 'react';
import {
  Button, Input, Select, Switch, Tag, Tooltip, Popconfirm, Form, InputNumber,
  Space, Spin, App, Empty, Modal, Card, Collapse, Badge, Radio, Drawer,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ApiOutlined,
  SyncOutlined, WifiOutlined, DisconnectOutlined,
  ReloadOutlined, UnlockOutlined, LoginOutlined, LogoutOutlined,
  ClusterOutlined, AimOutlined, BulbOutlined, FireOutlined, SoundOutlined, CreditCardOutlined, TeamOutlined, UploadOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService from '../../services/api';

const { Option } = Select;
const BASE = '/api/v1/access-controllers';
// ZKTeco datasheet specs
const C3_MODELS = {
  'C3-100': { doors: 1, readerPorts: 2, inputs: 2, outputs: 2 },
  'C3-200': { doors: 2, readerPorts: 4, inputs: 6, outputs: 4 },
  'C3-400': { doors: 4, readerPorts: 4, inputs: 12, outputs: 8 },
};
const IPV4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/;

// Build the reader ports for a controller from its model + chosen layout.
// C3-400 has only 4 reader ports: either 4 doors (entry-only) OR 2 doors (in+out).
const buildReaders = (model, doorCount, mode) => {
  const rows = [];
  if (model === 'C3-400' && mode === 'entry_only') {
    for (let d = 1; d <= 4; d++) rows.push({ door_no: d, direction: 'ENTRY', name: `Door ${d} Entry` });
    return rows;
  }
  const doors = model === 'C3-400' ? 2 : (C3_MODELS[model]?.doors || doorCount || 1);
  for (let d = 1; d <= doors; d++) {
    rows.push({ door_no: d, direction: 'ENTRY', name: `Door ${d} Entry` });
    rows.push({ door_no: d, direction: 'EXIT', name: `Door ${d} Exit` });
  }
  return rows;
};

// A small illustration of a ZKTeco C3 access-control board (green PCB with
// terminal strips, relays, an RJ45 jack) — looks like the real panel.
const C3Board = ({ size = 34 }) => (
  <svg width={size} height={size * 40 / 48} viewBox="0 0 48 40" xmlns="http://www.w3.org/2000/svg">
    {/* PCB */}
    <rect x="1" y="1" width="46" height="38" rx="3" fill="#0e7a3a" stroke="#0a5a2b" strokeWidth="1" />
    {/* mounting holes */}
    {[[5, 5], [43, 5], [5, 35], [43, 35]].map(([cx, cy], i) => (
      <circle key={i} cx={cx} cy={cy} r="1.5" fill="#063b1c" />
    ))}
    {/* top + bottom terminal strips with screw terminals */}
    {[3.5, 34.5].map((y, si) => (
      <g key={si}>
        <rect x="8" y={y} width="32" height="4.5" rx="1" fill="#0a5626" />
        {[10, 14, 18, 22, 26, 30, 34, 38].map(x => (
          <circle key={x} cx={x} cy={y + 2.25} r="0.95" fill="#e6e07a" />
        ))}
      </g>
    ))}
    {/* relays (lock outputs) */}
    <rect x="9" y="12" width="8.5" height="7.5" rx="1" fill="#2158b0" />
    <rect x="19.5" y="12" width="8.5" height="7.5" rx="1" fill="#2158b0" />
    {/* microcontroller chip */}
    <rect x="31" y="11.5" width="8.5" height="8.5" rx="1" fill="#141414" />
    {/* RJ45 ethernet jack */}
    <rect x="9" y="23" width="9.5" height="6.5" rx="0.8" fill="#d0d4d8" stroke="#868c92" strokeWidth="0.6" />
    <rect x="12.5" y="22.2" width="2.5" height="1.4" fill="#868c92" />
    {/* silkscreen label */}
    <text x="24.5" y="28.5" fontSize="5.5" fontFamily="Arial, sans-serif" fontWeight="700" fill="#d8f0df">C3</text>
  </svg>
);

const STATUS = {
  online:  { color: '#52c41a', icon: <WifiOutlined />,       label: 'Online'  },
  offline: { color: '#8c8c8c', icon: <DisconnectOutlined />, label: 'Offline' },
  error:   { color: '#ff4d4f', icon: <DisconnectOutlined />, label: 'Error'   },
};

const fmtLastSeen = ts => {
  if (!ts) return 'Never';
  const secs = Math.floor((Date.now() - new Date(ts)) / 1000);
  if (secs < 60)  return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
};

/* ── Reader row: assign the zone this door port controls ──────────────────── */
const ReaderRow = ({ reader, zones, onSave, onDelete, onOpen, saving }) => {
  const isEntry = reader.direction === 'ENTRY';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
      borderBottom: '1px solid #f5f5f5',
    }}>
      <Tag color={isEntry ? 'green' : 'orange'} style={{ minWidth: 92, textAlign: 'center', margin: 0 }}>
        {isEntry ? <LoginOutlined /> : <LogoutOutlined />}{' '}Door {reader.door_no} {reader.direction}
      </Tag>
      <span style={{ flex: '0 0 150px', fontSize: 12, color: '#595959' }}>
        {reader.name || '—'}
      </span>
      <Select
        size="small"
        style={{ flex: 1, minWidth: 180 }}
        placeholder="— Assign zone —"
        allowClear
        showSearch
        optionFilterProp="children"
        value={reader.zone_id || undefined}
        loading={saving}
        onChange={zid => onSave(reader, { zone_id: zid || 0 })}
      >
        {zones.map(z => <Option key={z.id} value={z.id}>{z.name}</Option>)}
      </Select>
      <Tooltip title="What a tap here means">
        <Select size="small" style={{ width: 168 }} value={reader.purpose || 'ACCESS'} loading={saving}
          onChange={v => onSave(reader, { purpose: v })}
          options={[
            { value: 'ATTENDANCE', label: '🕘 Clock in / out' },
            { value: 'ACCESS', label: '🚪 Door access only' },
            { value: 'MUSTERING', label: '🟢 Muster point' },
          ]} />
      </Tooltip>
      <Tooltip title="Pulse-open this door">
        <Button size="small" icon={<UnlockOutlined />} onClick={() => onOpen(reader.door_no)} />
      </Tooltip>
      <Popconfirm title="Remove this reader port?" onConfirm={() => onDelete(reader.id)}>
        <Button size="small" danger icon={<DeleteOutlined />} />
      </Popconfirm>
    </div>
  );
};

/* ── Issue cards: tap a new card on any reader, give it to a person ─────────── */
const PersonSearch = ({ value, onChange }) => {
  const [opts, setOpts] = useState([]);
  const search = async (q) => {
    if (!q || q.length < 2) return;
    try {
      const r = await apiService.get('/api/v1/personnel/', { search: q, page_size: 20 });
      setOpts((r?.results || []).map(p => ({ value: p.emp_code, label: `${p.full_name || p.first_name} · ${p.emp_code}` })));
    } catch { /* best effort */ }
  };
  return <Select showSearch allowClear filterOption={false} placeholder="Type a name…" style={{ width: 260 }}
    onSearch={search} options={opts} value={value} onChange={onChange} notFoundContent="Type 2+ letters" />;
};

const CardImport = () => {
  const { message } = App.useApp();
  const [txt, setTxt] = useState('');
  const [res, setRes] = useState(null);
  const rows = txt.split(/\r?\n/).map(l => l.split(/\t|,|;/).map(x => x.trim())).filter(r => r[0] && r[1] && /\d/.test(r[1]));
  const go = useMutation({
    mutationFn: () => apiService.post(`${BASE}/cards/import`, rows.map(([key, card_no]) => ({ key, card_no: card_no.replace(/\D/g, '') }))),
    onSuccess: r => { setRes(r); message.success(`${r.updated} card(s) saved`); },
    onError: e => message.error(e.message),
  });
  return (
    <div>
      <div style={{ fontSize: 12.5, color: '#64748b', marginBottom: 6 }}>
        Copy two columns from Excel and paste: <b>employee code or Attendance ID</b>, then <b>card number</b>.
      </div>
      <Input.TextArea rows={5} value={txt} onChange={e => setTxt(e.target.value)} placeholder={'MARC 14256\t0012345678\n14257\t0012345679'} />
      <Space style={{ marginTop: 8 }}>
        <Button type="primary" disabled={!rows.length} loading={go.isPending} onClick={() => go.mutate()}>Import {rows.length || ''} row(s)</Button>
        {res && <span style={{ fontSize: 12.5 }}>{res.updated} saved · {res.problems.length} problem(s). {res.next}</span>}
      </Space>
      {res?.problems?.length > 0 && (
        <div style={{ marginTop: 8, maxHeight: 160, overflow: 'auto', fontSize: 12, color: '#b45309' }}>
          {res.problems.map(p => <div key={p.row}>Row {p.row} ({p.key} → {p.card_no}): {p.error}</div>)}
        </div>
      )}
    </div>
  );
};

const CardsDrawer = ({ open, onClose }) => {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [who, setWho] = useState({});
  const { data: cards = [], isFetching } = useQuery({
    queryKey: ['ac-unknown-cards'], enabled: open, refetchInterval: open ? 3000 : false,
    queryFn: () => apiService.get(`${BASE}/cards/unknown`),
  });
  const assign = useMutation({
    mutationFn: ({ card_no, emp_code }) => apiService.post(`${BASE}/cards/assign`, { card_no, emp_code }),
    onSuccess: (r) => {
      const failed = (r?.controllers || []).filter(c => !c.ok);
      if (r?.note) message.warning(r.note, 8);
      else if (failed.length) message.warning(`Card saved, but ${failed.length} controller(s) did not accept it — check they are online`, 8);
      else message.success(`Card ${r.card_no} issued to ${r.emp_code}${r?.controllers?.length ? ' and loaded onto the controllers' : ''}`);
      qc.invalidateQueries(['ac-unknown-cards']);
    },
    onError: e => message.error(e.message),
  });
  return (
    <Drawer open={open} onClose={onClose} width={640} title={<span><CreditCardOutlined /> Issue cards</span>}
      extra={isFetching ? <Spin size="small" /> : null}>
      <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 10, padding: '10px 12px', marginBottom: 14, fontSize: 13 }}>
        Tap a new card on <b>any reader</b>. It is refused (it belongs to nobody yet) and appears below within a few
        seconds — pick the person and press <b>Issue</b>. The card is saved on their record and loaded onto every controller.
      </div>
      <Collapse size="small" style={{ marginBottom: 14 }} items={[{
        key: 'imp', label: <span><UploadOutlined /> Import card numbers from Excel</span>,
        children: <CardImport />,
      }]} />
      {cards.length === 0 && <Empty description="Waiting for a card tap…" />}
      {cards.map(c => (
        <div key={c.card_no} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #f0f0f0' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 15 }}>{c.card_no}</div>
            <div style={{ fontSize: 12, color: '#8c8c8c' }}>{c.reader_name} · {String(c.last_seen).slice(11, 19)} · {c.taps} tap(s)</div>
          </div>
          <PersonSearch value={who[c.card_no]} onChange={v => setWho({ ...who, [c.card_no]: v })} />
          <Button type="primary" disabled={!who[c.card_no]} loading={assign.isPending && assign.variables?.card_no === c.card_no}
            onClick={() => assign.mutate({ card_no: c.card_no, emp_code: who[c.card_no] })}>Issue</Button>
        </div>
      ))}
    </Drawer>
  );
};

/* ── Emergency: what each door does in a fire + sirens on AUX outputs ───────── */
const ROLES = [
  { value: 0, label: 'No change' },
  { value: 2, label: 'Fire exit — unlock in a fire' },
  { value: 1, label: 'Lock in a fire' },
];

const EmergencyOutputs = ({ ctrl }) => {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [aux, setAux] = useState({ aux_no: 1, name: 'Siren', device_type: 1 });
  const { data: doors = [], isLoading } = useQuery({
    queryKey: ['ctrl-doors', ctrl.id], queryFn: () => apiService.get(`${BASE}/${ctrl.id}/doors`),
  });
  const { data: sirens = [] } = useQuery({
    queryKey: ['ctrl-sirens', ctrl.id], queryFn: () => apiService.get(`${BASE}/${ctrl.id}/sirens`),
  });
  const saveDoor = useMutation({
    mutationFn: ({ id, patch }) => apiService.put(`${BASE}/doors/${id}`, patch),
    onSuccess: () => { qc.invalidateQueries(['ctrl-doors', ctrl.id]); message.success('Saved'); },
    onError: e => message.error(e.message),
  });
  const addSiren = useMutation({
    mutationFn: () => apiService.post(`${BASE}/${ctrl.id}/sirens`, aux),
    onSuccess: () => { qc.invalidateQueries(['ctrl-sirens', ctrl.id]); message.success('Added — it sounds when fire mode is activated'); },
    onError: e => message.error(e.message),
  });
  const delSiren = useMutation({
    mutationFn: id => apiService.delete(`${BASE}/sirens/${id}`),
    onSuccess: () => qc.invalidateQueries(['ctrl-sirens', ctrl.id]),
  });
  const test = useMutation({
    mutationFn: n => apiService.post(`${BASE}/${ctrl.id}/aux/${n}/test?seconds=3`),
    onSuccess: r => (r?.success ? message.success(r.message) : message.error(r?.error || 'Panel did not respond')),
  });
  const outputs = Math.max(1, ctrl.door_count || 1);   // C3 / inBio: one AUX output per door

  return (
    <div style={{ border: '1px solid #f0f0f0', borderRadius: 8, padding: 12 }}>
      <div style={{ fontSize: 12.5, color: '#64748b', marginBottom: 10 }}>
        Fire mode holds every <b>fire exit</b> open and switches the sirens on; clearing fire mode locks them again and silences the sirens.
      </div>
      {isLoading ? <Spin /> : doors.map(d => (
        <div key={d.id} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '6px 0', borderBottom: '1px dashed #f0f0f0' }}>
          <Tag style={{ minWidth: 58, textAlign: 'center' }}>Door {d.port}</Tag>
          <Input size="small" defaultValue={d.name} style={{ maxWidth: 260 }}
            onBlur={e => e.target.value !== d.name && saveDoor.mutate({ id: d.id, patch: { name: e.target.value } })} />
          <Select size="small" value={d.emergency_action} style={{ width: 230 }} options={ROLES}
            onChange={v => saveDoor.mutate({ id: d.id, patch: { emergency_action: v } })} />
          {d.emergency_action === 2 && <Tag color="green" icon={<FireOutlined />}>fire exit</Tag>}
        </div>
      ))}

      <div style={{ fontWeight: 600, fontSize: 13, margin: '14px 0 8px' }}><SoundOutlined /> Sirens / strobes on AUX outputs</div>
      {sirens.length === 0 && <div style={{ fontSize: 12.5, color: '#94a3b8', marginBottom: 8 }}>None yet — add the AUX output each siren or strobe is wired to.</div>}
      {sirens.map(sv => (
        <div key={sv.id} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '4px 0' }}>
          <Tag color="orange">AUX {sv.aux_no}</Tag>
          <span style={{ flex: 1 }}>{sv.name} <span style={{ color: '#94a3b8' }}>· {sv.device_type === 2 ? 'strobe' : 'siren'}</span></span>
          <Button size="small" loading={test.isPending && test.variables === sv.aux_no} onClick={() => test.mutate(sv.aux_no)}>Test 3 s</Button>
          <Popconfirm title="Remove this siren?" onConfirm={() => delSiren.mutate(sv.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </div>
      ))}
      <Space wrap style={{ marginTop: 8 }}>
        <Select size="small" value={aux.aux_no} style={{ width: 100 }} onChange={v => setAux({ ...aux, aux_no: v })}
          options={Array.from({ length: outputs }, (_, i) => ({ value: i + 1, label: `AUX ${i + 1}` }))} />
        <Input size="small" value={aux.name} style={{ width: 180 }} onChange={e => setAux({ ...aux, name: e.target.value })} />
        <Select size="small" value={aux.device_type} style={{ width: 100 }} onChange={v => setAux({ ...aux, device_type: v })}
          options={[{ value: 1, label: 'Siren' }, { value: 2, label: 'Strobe' }]} />
        <Button size="small" type="dashed" icon={<PlusOutlined />} loading={addSiren.isPending} onClick={() => addSiren.mutate()}>Add</Button>
      </Space>
    </div>
  );
};

/* ── One controller card ──────────────────────────────────────────────────── */
const ControllerCard = ({ ctrl, zones, api, qc }) => {
  const { message } = App.useApp();
  const st = STATUS[ctrl.status] || STATUS.offline;

  const saveReader = useMutation({
    mutationFn: ({ id, patch }) => apiService.put(`${BASE}/readers/${id}`, patch),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['ac-controllers'] }); },
    onError: e => message.error(e.message || 'Failed to update reader'),
  });
  const delReader = useMutation({
    mutationFn: id => apiService.delete(`${BASE}/readers/${id}`),
    onSuccess: () => { message.success('Reader removed'); qc.invalidateQueries({ queryKey: ['ac-controllers'] }); },
  });
  const poll = useMutation({
    mutationFn: () => apiService.post(`${BASE}/${ctrl.id}/poll`),
    onSuccess: r => { message.success(`Polled — ${r?.events ?? 0} event(s)`); qc.invalidateQueries({ queryKey: ['ac-controllers'] }); },
    onError: e => message.error(e.message || 'Poll failed'),
  });
  const openDoor = useMutation({
    mutationFn: door => apiService.post(`${BASE}/${ctrl.id}/doors/${door}/open`),
    onSuccess: r => r?.success ? message.success(r.message) : message.warning(r?.error || 'Open failed'),
  });
  const [probeResult, setProbeResult] = React.useState(null);
  const syncUsers = useMutation({
    mutationFn: () => apiService.post(`${BASE}/${ctrl.id}/sync-users`),
    onSuccess: r => {
      const failed = (r?.load?.failed?.length || 0) + (r?.remove?.failed?.length || 0);
      const msg = `Loaded ${r?.load?.pushed ?? 0}, removed ${r?.remove?.removed ?? 0}` +
        (r?.skipped_no_attendance_id ? ` · ${r.skipped_no_attendance_id} staff skipped (no Attendance ID)` : '');
      (failed ? message.warning : message.success)(failed ? `${msg} · ${failed} failed — see Probe` : msg, 8);
    },
    onError: e => message.error(e.message || 'Sync failed'),
  });

  const probe = useMutation({
    mutationFn: () => apiService.post(`${BASE}/${ctrl.id}/probe`),
    onSuccess: r => setProbeResult(r),
    onError: e => message.error(e.message || 'Probe failed'),
  });

  const unassigned = ctrl.readers.filter(r => !r.zone_id).length;

  return (
    <Card
      size="small"
      style={{ marginBottom: 14, borderRadius: 10 }}
      styles={{ body: { padding: 0 } }}
    >
      {/* header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 16px' }}>
        <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
          <C3Board size={64} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14 }}>
            {ctrl.name}{' '}
            <span style={{ color: '#8c8c8c', fontWeight: 400, fontSize: 12 }}>
              {ctrl.model || 'controller'} · {ctrl.ip_address}:{ctrl.port}
            </span>
          </div>
          <div style={{ fontSize: 12, color: '#8c8c8c' }}>
            {ctrl.door_count} door(s) · {ctrl.readers.length} reader port(s)
            {ctrl.location && <span> · {ctrl.location}</span>}
            {unassigned > 0 && <Tag color="warning" style={{ marginLeft: 8 }}>{unassigned} unassigned</Tag>}
          </div>
        </div>
        <Tag color={st.color === '#52c41a' ? 'success' : st.color === '#ff4d4f' ? 'error' : 'default'}>
          {st.icon} {st.label}
        </Tag>
        <span style={{ fontSize: 11, color: '#bfbfbf' }}>seen {fmtLastSeen(ctrl.last_seen)}</span>
        <Space>
          <Tooltip title="Diagnose the panel: TCP → C3 driver → connect → event sample">
            <Button size="small" icon={<ApiOutlined />} loading={probe.isPending} onClick={() => probe.mutate()}>Probe</Button>
          </Tooltip>
          <Tooltip title="Poll buffered events now → zone occupancy">
            <Button size="small" icon={<SyncOutlined />} loading={poll.isPending} onClick={() => poll.mutate()} />
          </Tooltip>
          <Tooltip title="Load every active person (Attendance ID + card) onto this panel and remove leavers. Also runs nightly.">
            <Button size="small" icon={<TeamOutlined />} loading={syncUsers.isPending} onClick={() => syncUsers.mutate()}>Sync users</Button>
          </Tooltip>
          <Tooltip title="Learn mode — badge at each reader to discover & map its port">
            <Button size="small" icon={<AimOutlined />} onClick={() => api.learn(ctrl)}>Learn</Button>
          </Tooltip>
          <Tooltip title="Edit controller"><Button size="small" icon={<EditOutlined />} onClick={() => api.edit(ctrl)} /></Tooltip>
          <Popconfirm title="Delete this controller and all its readers?" onConfirm={() => api.remove(ctrl.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      </div>

      {ctrl.last_error && (
        <div style={{ padding: '0 16px 8px', color: '#ff4d4f', fontSize: 12 }}>⚠ {ctrl.last_error}</div>
      )}

      {/* readers */}
      <Collapse
        ghost
        items={[{
          key: 'readers',
          label: <span style={{ fontWeight: 600, fontSize: 13 }}>Reader ports & zone assignment</span>,
          children: (
            <div style={{ border: '1px solid #f0f0f0', borderRadius: 8 }}>
              {ctrl.readers.length === 0
                ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No reader ports" />
                : ctrl.readers.map(r => (
                  <ReaderRow
                    key={r.id}
                    reader={r}
                    zones={zones}
                    saving={saveReader.isPending}
                    onSave={(reader, patch) => saveReader.mutate({ id: reader.id, patch })}
                    onDelete={id => delReader.mutate(id)}
                    onOpen={door => openDoor.mutate(door)}
                  />
                ))}
              <div style={{ padding: 10 }}>
                <Button size="small" type="dashed" icon={<PlusOutlined />} onClick={() => api.addReader(ctrl)}>
                  Add reader port
                </Button>
              </div>
            </div>
          ),
        }, {
          key: 'emergency',
          label: <span style={{ fontWeight: 600, fontSize: 13 }}><FireOutlined style={{ color: '#f97316' }} /> In an emergency — fire exits &amp; sirens</span>,
          children: <EmergencyOutputs ctrl={ctrl} />,
        }]}
      />

      <Modal
        open={!!probeResult}
        title={<span><ApiOutlined /> Probe — {ctrl.name}</span>}
        onCancel={() => setProbeResult(null)}
        footer={<Button onClick={() => setProbeResult(null)}>Close</Button>}
        width={640}
      >
        {probeResult && (
          <div>
            <div style={{ marginBottom: 12 }}>
              {(probeResult.steps || []).map((s, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 0' }}>
                  <Tag color={s.ok ? 'success' : 'error'}>{s.ok ? '✓' : '✗'}</Tag>
                  <b style={{ minWidth: 110 }}>{s.step}</b>
                  <span style={{ color: '#8c8c8c', fontSize: 12 }}>{s.detail}</span>
                </div>
              ))}
            </div>
            <div style={{ background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6, padding: '8px 12px', fontSize: 13 }}>
              {probeResult.summary}
            </div>
            {probeResult.rtlog_raw && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>
                  Raw realtime-log sample{probeResult.rtlog_provisional ? ' (positional — confirm field order)' : ''}:
                </div>
                <pre style={{ background: '#0d1117', color: '#c9d1d9', padding: 10, borderRadius: 6, fontSize: 11, maxHeight: 200, overflow: 'auto' }}>
                  {probeResult.rtlog_raw}
                </pre>
              </div>
            )}
          </div>
        )}
      </Modal>
    </Card>
  );
};

/* ── Learn mode: badge at each reader, watch which port fires, map to zone ──── */
const firedAgo = ts => {
  if (!ts) return null;
  const s = Math.floor((Date.now() - new Date(ts)) / 1000);
  return s < 8;   // "just fired" window for the highlight
};

const LearnModal = ({ ctrl, zones, open, onClose, qc }) => {
  const { message } = App.useApp();
  const [feed, setFeed] = useState([]);   // newest-first live event feed

  // Poll the controller in learn mode while the modal is open.
  const learn = useQuery({
    queryKey: ['ac-learn', ctrl?.id],
    queryFn: () => apiService.post(`${BASE}/${ctrl.id}/learn`),
    enabled: open && !!ctrl,
    refetchInterval: 2000,
    refetchOnWindowFocus: false,
  });

  React.useEffect(() => {
    const r = learn.data;
    if (!r) return;
    if (r.error) return;
    if (Array.isArray(r.events) && r.events.length) {
      setFeed(prev => [...r.events.map(e => ({ ...e, _k: `${e.reader_id}-${e.time}` })), ...prev].slice(0, 25));
      qc.invalidateQueries({ queryKey: ['ac-controllers'] });   // refresh port list / last_event
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [learn.data]);

  const assign = useMutation({
    mutationFn: ({ id, zone_id }) => apiService.put(`${BASE}/readers/${id}`, { zone_id: zone_id || 0 }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ac-controllers'] }),
    onError: e => message.error(e.message || 'Failed to assign zone'),
  });

  const err = learn.data?.error;

  return (
    <Modal
      open={open}
      onCancel={() => { setFeed([]); onClose(); }}
      footer={<Button onClick={() => { setFeed([]); onClose(); }}>Done</Button>}
      width={680}
      title={<span><AimOutlined /> Learn Mode — {ctrl?.name}</span>}
      destroyOnClose
    >
      <div style={{
        background: '#e6f4ff', border: '1px solid #91caff', borderRadius: 8,
        padding: '10px 12px', marginBottom: 14, fontSize: 13, color: '#0958d9',
      }}>
        <BulbOutlined /> Badge a card at each physical reader. The port it's wired to
        will light up below — name it and assign its zone. New ports are added
        automatically as they fire. (This does not move anyone in/out of a zone.)
      </div>

      {err && (
        <div style={{ background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 8, padding: '8px 12px', marginBottom: 14, color: '#cf1322', fontSize: 12 }}>
          ⚠ {err} — the controller transport must be reachable & verified for learn mode to receive events.
        </div>
      )}

      {/* Live feed */}
      <div style={{ fontWeight: 600, fontSize: 12, color: '#8c8c8c', margin: '4px 0 6px' }}>
        LIVE {learn.isFetching && <SyncOutlined spin style={{ marginLeft: 6 }} />}
      </div>
      {feed.length === 0
        ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Waiting for a card to be presented…" />
        : (
          <div style={{ maxHeight: 150, overflowY: 'auto', border: '1px solid #f0f0f0', borderRadius: 8, marginBottom: 16 }}>
            {feed.map((e, i) => (
              <div key={e._k + i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 12px', borderBottom: '1px solid #fafafa' }}>
                <Tag color={e.direction === 'ENTRY' ? 'green' : 'orange'} style={{ margin: 0 }}>
                  Door {e.door_no} {e.direction}
                </Tag>
                <span style={{ fontSize: 12, color: '#595959' }}>card/ID: {e.identity || '—'}</span>
                {e.created && <Tag color="blue">new port</Tag>}
                <span style={{ marginLeft: 'auto', fontSize: 11, color: '#bfbfbf' }}>
                  {new Date(e.time).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        )}

      {/* Discovered ports — assign zones */}
      <div style={{ fontWeight: 600, fontSize: 12, color: '#8c8c8c', margin: '4px 0 6px' }}>
        PORTS ON THIS CONTROLLER — ASSIGN ZONES
      </div>
      <div style={{ border: '1px solid #f0f0f0', borderRadius: 8 }}>
        {(ctrl?.readers || []).length === 0
          ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No ports yet" />
          : ctrl.readers.map(r => {
            const hot = firedAgo(r.last_event_at);
            return (
              <div key={r.id} style={{
                display: 'flex', alignItems: 'center', gap: 12, padding: '9px 12px',
                borderBottom: '1px solid #f5f5f5',
                background: hot ? '#f6ffed' : 'transparent', transition: 'background 1s',
              }}>
                <Tag color={r.direction === 'ENTRY' ? 'green' : 'orange'} style={{ minWidth: 92, textAlign: 'center', margin: 0 }}>
                  {r.direction === 'ENTRY' ? <LoginOutlined /> : <LogoutOutlined />}{' '}Door {r.door_no} {r.direction}
                </Tag>
                {hot && <Badge status="processing" text="just fired" />}
                <Select
                  size="small" style={{ flex: 1, minWidth: 180 }} placeholder="— Assign zone —"
                  allowClear showSearch optionFilterProp="children"
                  value={r.zone_id || undefined}
                  onChange={zid => assign.mutate({ id: r.id, zone_id: zid })}
                >
                  {zones.map(z => <Option key={z.id} value={z.id}>{z.name}</Option>)}
                </Select>
              </div>
            );
          })}
      </div>
    </Modal>
  );
};

/* ── Page ─────────────────────────────────────────────────────────────────── */
const Controllers = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [modal, setModal] = useState(null);   // {mode:'create'|'edit', ctrl?} | {mode:'reader', ctrl}
  const [cardsOpen, setCardsOpen] = useState(false);
  const [learnId, setLearnId] = useState(null);
  const [readerMode, setReaderMode] = useState('entry_only');  // C3-400: entry_only | entry_exit
  const [form] = Form.useForm();
  const watchModel = Form.useWatch('model', form);
  const watchDoors = Form.useWatch('door_count', form);
  const previewReaders = buildReaders(watchModel, watchDoors, readerMode);

  const { data: controllers = [], isLoading } = useQuery({
    queryKey: ['ac-controllers'],
    queryFn: () => apiService.get(BASE),
    refetchInterval: 15000,
  });

  const { data: zonesRaw } = useQuery({
    queryKey: ['zones-list'],
    queryFn: () => apiService.get('/api/v1/zones/'),
  });
  const zones = Array.isArray(zonesRaw) ? zonesRaw : (zonesRaw?.zones || zonesRaw?.items || []);

  const { data: sdk } = useQuery({
    queryKey: ['ac-sdk-status'],
    queryFn: () => apiService.get(`${BASE}/sdk/status`),
  });
  const driverReady = sdk?.zkaccess_c3_available;

  const saveCtrl = useMutation({
    mutationFn: v => modal?.ctrl
      ? apiService.put(`${BASE}/${modal.ctrl.id}`, v)
      : apiService.post(BASE, v),
    onSuccess: () => {
      message.success(modal?.ctrl ? 'Controller updated' : 'Controller added');
      qc.invalidateQueries({ queryKey: ['ac-controllers'] });
      setModal(null); form.resetFields();
    },
    onError: e => message.error(e.message || 'Save failed'),
  });
  const removeCtrl = useMutation({
    mutationFn: id => apiService.delete(`${BASE}/${id}`),
    onSuccess: () => { message.success('Controller deleted'); qc.invalidateQueries({ queryKey: ['ac-controllers'] }); },
  });
  const addReader = useMutation({
    mutationFn: ({ ctrlId, v }) => apiService.post(`${BASE}/${ctrlId}/readers`, v),
    onSuccess: () => { message.success('Reader added'); qc.invalidateQueries({ queryKey: ['ac-controllers'] }); setModal(null); form.resetFields(); },
    onError: e => message.error(e.message || 'Add failed'),
  });

  const cardApi = {
    edit: ctrl => { setModal({ mode: 'edit', ctrl }); form.setFieldsValue(ctrl); },
    remove: id => removeCtrl.mutate(id),
    addReader: ctrl => { setModal({ mode: 'reader', ctrl }); form.resetFields(); form.setFieldsValue({ direction: 'ENTRY', door_no: 1 }); },
    learn: ctrl => setLearnId(ctrl.id),
  };

  const learnCtrl = controllers.find(c => c.id === learnId) || null;

  const submit = async () => {
    const v = await form.validateFields();
    if (modal.mode === 'reader') { addReader.mutate({ ctrlId: modal.ctrl.id, v }); return; }
    if (!modal.ctrl) {
      // Create: seed the exact reader ports shown in the preview.
      const readers = buildReaders(v.model, v.door_count, readerMode);
      v.readers = readers;
      v.door_count = Math.max(...readers.map(r => r.door_no), 1);
    }
    saveCtrl.mutate(v);
  };

  return (
    <div style={{ padding: 20, background: '#f0f2f5', minHeight: '100vh' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ margin: 0, fontSize: 20 }}>
            <ClusterOutlined /> Access Control Controllers{' '}
            <Tag color={driverReady ? 'success' : 'default'} style={{ fontSize: 11, verticalAlign: 'middle' }}>
              {driverReady ? 'C3 driver: ready' : 'C3 driver: n/a'}
            </Tag>
          </h2>
          <div style={{ color: '#8c8c8c', fontSize: 13 }}>
            LAN panels (ZKTeco C3 / inBio) with Wiegand readers. One IP per controller; assign each
            door's IN/OUT reader to a zone for entry/exit tracking.
          </div>
        </div>
        <Space>
          <Button icon={<CreditCardOutlined />} onClick={() => setCardsOpen(true)}>Issue cards</Button>
          <Button icon={<ReloadOutlined />} onClick={() => qc.invalidateQueries({ queryKey: ['ac-controllers'] })}>
            Refresh
          </Button>
          <Button type="primary" icon={<PlusOutlined />}
            onClick={() => { setReaderMode('entry_only'); setModal({ mode: 'create' }); form.resetFields(); form.setFieldsValue({ port: 4370, door_count: 2, poll_interval_sec: 5, poll_enabled: true }); }}>
            Add Controller
          </Button>
        </Space>
      </div>

      {isLoading
        ? <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
        : controllers.length === 0
          ? <Empty description="No access controllers yet. Add one to begin." style={{ padding: 60 }} />
          : controllers.map(c => <ControllerCard key={c.id} ctrl={c} zones={zones} api={cardApi} qc={qc} />)
      }

      <CardsDrawer open={cardsOpen} onClose={() => setCardsOpen(false)} />

      {/* Learn mode */}
      <LearnModal
        ctrl={learnCtrl}
        zones={zones}
        open={!!learnCtrl}
        onClose={() => setLearnId(null)}
        qc={qc}
      />

      {/* Create / edit controller, or add reader */}
      <Modal
        open={!!modal}
        title={modal?.mode === 'reader' ? `Add reader — ${modal?.ctrl?.name}`
          : modal?.ctrl ? 'Edit Controller' : 'Add Controller'}
        onCancel={() => { setModal(null); form.resetFields(); }}
        onOk={submit}
        confirmLoading={saveCtrl.isPending || addReader.isPending}
        okText="Save"
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 12 }}>
          {modal?.mode === 'reader' ? (
            <>
              <Form.Item name="door_no" label="Door number" rules={[{ required: true }]}>
                <InputNumber min={1} max={8} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="direction" label="Direction" rules={[{ required: true }]}>
                <Select>
                  <Option value="ENTRY">ENTRY (in reader)</Option>
                  <Option value="EXIT">EXIT (out reader)</Option>
                </Select>
              </Form.Item>
              <Form.Item name="name" label="Label"><Input placeholder="e.g. Gate 1 Entry" /></Form.Item>
              <Form.Item name="zone_id" label="Zone">
                <Select allowClear showSearch optionFilterProp="children" placeholder="— Assign zone —">
                  {zones.map(z => <Option key={z.id} value={z.id}>{z.name}</Option>)}
                </Select>
              </Form.Item>
            </>
          ) : (
            <>
              <Space style={{ display: 'flex' }} align="start">
                <Form.Item name="name" label="Name" rules={[{ required: true }]} style={{ flex: 1 }}>
                  <Input placeholder="e.g. Main Gate Controller" />
                </Form.Item>
                <Form.Item name="model" label="Model" rules={[{ required: true }]} style={{ width: 190 }}
                  tooltip="Sets door count + reader layout (ZKTeco datasheet)">
                  <Select placeholder="Select model" disabled={!!modal?.ctrl}
                    onChange={m => {
                      const s = C3_MODELS[m];
                      if (s) form.setFieldsValue({ door_count: s.doors });
                      setReaderMode('entry_only');
                    }}
                    options={[
                      { value: 'C3-100', label: 'ZKTeco C3-100 (1 door)' },
                      { value: 'C3-200', label: 'ZKTeco C3-200 (2 doors)' },
                      { value: 'C3-400', label: 'ZKTeco C3-400 (4 doors)' },
                    ]} />
                </Form.Item>
              </Space>

              {watchModel && C3_MODELS[watchModel] && (
                <div style={{ margin: '-4px 0 12px', fontSize: 12, color: '#8c8c8c' }}>
                  {watchModel}: {C3_MODELS[watchModel].doors} door(s) · {C3_MODELS[watchModel].readerPorts} reader ports ·
                  {' '}{C3_MODELS[watchModel].inputs} inputs · {C3_MODELS[watchModel].outputs} outputs · 30,000 cards
                </div>
              )}

              <Form.Item name="location" label="Location"
                tooltip="Where the panel is physically installed">
                <Input placeholder="e.g. Main gate — Building A, ground floor" />
              </Form.Item>

              <Space style={{ display: 'flex' }} align="start">
                <Form.Item name="ip_address" label="IP address" style={{ flex: 1 }}
                  rules={[{ required: true }, { pattern: IPV4, message: 'Enter a valid IPv4 address' }]}>
                  <Input placeholder="192.168.1.201" />
                </Form.Item>
                <Form.Item name="port" label="Port" tooltip="C3 default is 4370"><InputNumber min={1} max={65535} /></Form.Item>
              </Space>

              <Space style={{ display: 'flex' }} align="start">
                <Form.Item name="serial_number" label="Serial number" style={{ flex: 1 }}
                  tooltip="From the device label (optional; can auto-read on Test)">
                  <Input placeholder="e.g. AGKD204..." />
                </Form.Item>
                <Form.Item name="comm_password" label="Comm password"
                  tooltip="C3 communication password, if one is set on the panel">
                  <Input.Password autoComplete="new-password" />
                </Form.Item>
              </Space>

              {!modal?.ctrl && (
                <>
                  <Form.Item label="Reader layout"
                    tooltip="How the readers are wired. Zone exit tracking needs a reader on the exit side.">
                    {watchModel === 'C3-400' ? (
                      <Radio.Group value={readerMode} onChange={e => setReaderMode(e.target.value)}>
                        <Radio value="entry_only" style={{ display: 'block', marginBottom: 4 }}>
                          4 doors — entry reader only <span style={{ color: '#8c8c8c' }}>(exit by push-button; no card-exit)</span>
                        </Radio>
                        <Radio value="entry_exit" style={{ display: 'block' }}>
                          2 doors — entry + exit readers <span style={{ color: '#8c8c8c' }}>(full in/out zone tracking)</span>
                        </Radio>
                      </Radio.Group>
                    ) : (
                      <span style={{ color: '#595959' }}>IN + OUT reader per door — full entry/exit tracking</span>
                    )}
                  </Form.Item>

                  <div style={{ background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6, padding: '8px 12px', marginBottom: 14 }}>
                    <div style={{ fontSize: 12, color: '#389e0d', marginBottom: 6 }}>
                      Will create {previewReaders.length} reader port(s):
                    </div>
                    <Space size={[4, 4]} wrap>
                      {previewReaders.map((r, i) => (
                        <Tag key={i} color={r.direction === 'ENTRY' ? 'green' : 'orange'} style={{ margin: 0 }}>
                          {r.direction === 'ENTRY' ? <LoginOutlined /> : <LogoutOutlined />} Door {r.door_no} {r.direction}
                        </Tag>
                      ))}
                    </Space>
                    <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 6 }}>
                      You'll assign each port to a zone after creating (or use Learn mode).
                    </div>
                  </div>
                </>
              )}

              <Space>
                <Form.Item name="poll_enabled" label="Auto-poll" valuePropName="checked"
                  tooltip="Continuously read events from this panel into zones"><Switch /></Form.Item>
                <Form.Item name="poll_interval_sec" label="Poll interval (s)"><InputNumber min={1} max={3600} /></Form.Item>
              </Space>

              <Space align="start">
                <Form.Item name="fire_alarm_input" label="Fire alarm wired to"
                  tooltip="The fire alarm panel's dry contact on this controller's AUX input. When it trips, ApexPOB starts fire mode: fire exits open, sirens, site-wide muster and alerts.">
                  <Select allowClear placeholder="Not wired" style={{ width: 150 }}
                    options={[1, 2, 3, 4].map(n => ({ value: n, label: `AUX input ${n}` }))} />
                </Form.Item>
                <Form.Item name="fire_alarm_on" label="Alarm when the contact" initialValue="open">
                  <Select style={{ width: 200 }} options={[
                    { value: 'open', label: 'Opens (normally closed)' },
                    { value: 'close', label: 'Closes (normally open)' },
                  ]} />
                </Form.Item>
              </Space>

              <Form.Item name="notes" label="Notes">
                <Input.TextArea rows={2} placeholder="Install notes, contact, etc. (optional)" />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  );
};

export default Controllers;
