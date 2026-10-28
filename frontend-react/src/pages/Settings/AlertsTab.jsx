/**
 * Settings → WhatsApp & Alerts
 *
 * WhatsApp provider (Meta Cloud API recommended), the emergency response team who
 * receive every muster / emergency / escalation alert, a test send per channel, and
 * the log of every alert message. Backed by /api/v1/settings/alerts.
 */
import React, { useEffect, useState } from 'react';
import {
  Form, Input, Button, Switch, Segmented, Table, Tag, App, Tooltip, Select, Skeleton, Alert, Checkbox, Modal, Popconfirm,
} from 'antd';
import {
  WhatsAppOutlined, MailOutlined, MessageOutlined, SaveOutlined, SendOutlined, PlusOutlined,
  DeleteOutlined, TeamOutlined, CheckCircleFilled, CloseCircleFilled, ReloadOutlined, CopyOutlined, LinkOutlined,
} from '@ant-design/icons';
import apiService from '../../services/api';

const TEMPLATE_TEXT = '🚨 ApexPOB alert: {{1}}';

export default function AlertsTab() {
  const { message } = App.useApp();
  const [data, setData] = useState(null);
  const [form] = Form.useForm();
  const provider = Form.useWatch('provider', form);
  const [saving, setSaving] = useState(false);
  const [team, setTeam] = useState([]);
  const [teamSaving, setTeamSaving] = useState(false);
  const [test, setTest] = useState({ channel: 'whatsapp', address: '' });
  const [testing, setTesting] = useState(false);
  const [log, setLog] = useState([]);
  const [logLoading, setLogLoading] = useState(false);

  const load = async () => {
    const r = await apiService.get('/api/v1/settings/alerts');
    setData(r.data);
    setTeam((r.data.responders || []).map((x, i) => ({ ...x, key: i })));
    form.setFieldsValue({ ...r.data.whatsapp, meta_access_token: '', termii_api_key: '', twilio_token: '' });
  };
  const loadLog = async () => {
    setLogLoading(true);
    try { setLog((await apiService.get('/api/v1/settings/alerts/deliveries', { limit: 100 }))?.data || []); }
    finally { setLogLoading(false); }
  };
  useEffect(() => { load().catch(e => message.error(e.message)); loadLog(); }, []); // eslint-disable-line

  const saveWa = async () => {
    setSaving(true);
    try {
      await apiService.put('/api/v1/settings/alerts/whatsapp', form.getFieldsValue());
      message.success('WhatsApp settings saved');
      await load();
    } catch (e) { message.error(e.message); } finally { setSaving(false); }
  };
  const saveTeam = async () => {
    setTeamSaving(true);
    try {
      const r = await apiService.put('/api/v1/settings/alerts/responders', team.map(({ key, ...x }) => x));
      setTeam((r.data || []).map((x, i) => ({ ...x, key: i })));
      message.success('Response team saved');
    } catch (e) { message.error(e.message); } finally { setTeamSaving(false); }
  };
  const sendTest = async () => {
    setTesting(true);
    try {
      const r = await apiService.post('/api/v1/settings/alerts/test', test);
      (r.success ? message.success : message.warning)(r.message, 8);
      loadLog();
    } catch (e) { message.error(e.message); } finally { setTesting(false); }
  };
  const showLink = async (body, who) => {
    try {
      const r = await apiService.post('/api/v1/settings/alerts/telegram/link', body);
      Modal.info({
        title: `Telegram link for ${who}`, width: 520,
        content: <div>
          <p>Send this to {who}. They open it on their phone and press <b>Start</b> — alerts then come to their Telegram.</p>
          <Input.TextArea value={r.url} autoSize readOnly />
          <Button style={{ marginTop: 8 }} icon={<CopyOutlined />} onClick={() => { navigator.clipboard?.writeText(r.url); message.success('Copied'); }}>Copy link</Button>
        </div>,
      });
    } catch (e) { message.error(e.message); }
  };
  const editTeam = (key, field, value) => setTeam(t => t.map(r => (r.key === key ? { ...r, [field]: value } : r)));

  if (!data) return <Skeleton active paragraph={{ rows: 10 }} />;
  const ch = data.channels || {};
  const wa = data.whatsapp || {};

  return (
    <div className="al-root">
      <style>{CSS}</style>
      <div className="al-hero">
        <div>
          <div className="al-title"><WhatsAppOutlined /> WhatsApp &amp; Alerts</div>
          <div className="al-sub">Musters, emergencies, panic alarms, escalations and the all-clear go out on every channel set up here.</div>
        </div>
        <div className="al-chips">
          {[['whatsapp', 'WhatsApp', <WhatsAppOutlined />], ['telegram', 'Telegram', <SendOutlined />], ['email', 'Email', <MailOutlined />], ['sms', 'SMS', <MessageOutlined />]].map(([k, l, i]) => (
            <span key={k} className={`al-chip ${ch[k] ? 'on' : ''}`}>
              {i} {l} {ch[k] ? <CheckCircleFilled /> : <CloseCircleFilled />}
              <small>{ch[k] ? 'Ready' : 'Not set up'}</small>
            </span>
          ))}
        </div>
      </div>

      {!ch.email && (
        <Alert type="warning" showIcon style={{ marginBottom: 16, borderRadius: 12 }}
          message="Email is not set up" description="Add your mail server under Settings → Email so alerts and scheduled reports can be emailed." />
      )}

      <div className="al-grid">
        <section className="al-card">
          <div className="al-card-h">
            <span><WhatsAppOutlined style={{ color: '#25d366' }} /> WhatsApp</span>
            <Form form={form} component={false}><Form.Item name="enabled" valuePropName="checked" noStyle>
              <Switch checkedChildren="On" unCheckedChildren="Off" />
            </Form.Item></Form>
          </div>
          <Form form={form} layout="vertical" requiredMark={false}>
            <Form.Item name="provider" label="Provider">
              <Segmented block options={[
                { label: 'Meta Cloud API (recommended)', value: 'meta' },
                { label: 'Termii', value: 'termii' }, { label: 'Twilio', value: 'twilio' }]} />
            </Form.Item>

            {provider === 'meta' && (
              <>
                <div className="al-two">
                  <Form.Item name="meta_phone_number_id" label="Phone number ID" tooltip="Meta Business → WhatsApp → API setup → Phone number ID">
                    <Input placeholder="e.g. 109876543210987" />
                  </Form.Item>
                  <Form.Item name="meta_access_token" label="Access token" tooltip="Use a permanent System User token">
                    <Input.Password placeholder={wa.has_meta_token ? '•••••••• saved — leave blank to keep' : 'EAAG…'} />
                  </Form.Item>
                  <Form.Item name="meta_template" label="Approved template name" tooltip="Needed to message people who haven't messaged you in the last 24 h">
                    <Input placeholder="e.g. pob_alert" />
                  </Form.Item>
                  <Form.Item name="meta_template_lang" label="Template language"><Input placeholder="en" /></Form.Item>
                </div>
                <div className="al-hint">
                  Create a <b>Utility</b> template in Meta with one variable, for example:
                  <code>{TEMPLATE_TEXT}</code>
                  <Tooltip title="Copy"><CopyOutlined onClick={() => { navigator.clipboard?.writeText(TEMPLATE_TEXT); message.success('Copied'); }} /></Tooltip>
                  — ApexPOB puts the alert text in <code>{'{{1}}'}</code>.
                  <br />Just testing? Use Meta's free test number with template <code>hello_world</code> (it can't carry the alert text, but proves delivery).
                </div>
              </>
            )}
            {provider === 'termii' && (
              <div className="al-two">
                <Form.Item name="termii_api_key" label="API key">
                  <Input.Password placeholder={wa.has_termii_key ? '•••••••• saved — leave blank to keep' : ''} />
                </Form.Item>
                <Form.Item name="termii_sender" label="WhatsApp sender (approved)"><Input /></Form.Item>
              </div>
            )}
            {provider === 'twilio' && (
              <div className="al-two">
                <Form.Item name="twilio_sid" label="Account SID"><Input /></Form.Item>
                <Form.Item name="twilio_token" label="Auth token">
                  <Input.Password placeholder={wa.has_twilio_token ? '•••••••• saved — leave blank to keep' : ''} />
                </Form.Item>
                <Form.Item name="twilio_from" label="WhatsApp number"><Input placeholder="+14155238886" /></Form.Item>
              </div>
            )}
            <Form.Item name="country_code" label="Country code for local numbers" tooltip="0803… becomes 234803…" style={{ maxWidth: 220 }}>
              <Input prefix="+" />
            </Form.Item>
          </Form>
          <div className="al-foot">
            <span className={`al-state ${wa.ready ? 'ok' : ''}`}>{wa.ready ? <><CheckCircleFilled /> Ready to send</> : 'Not complete or switched off'}</span>
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={saveWa}>Save</Button>
          </div>
        </section>

        <section className="al-card">
          <div className="al-card-h"><span><SendOutlined style={{ color: '#2563eb' }} /> Send a test</span></div>
          <div className="al-sub2">Check a channel end to end before you rely on it.</div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <Select value={test.channel} style={{ width: 130 }} onChange={(v) => setTest({ ...test, channel: v })}
              options={[{ value: 'whatsapp', label: 'WhatsApp' }, { value: 'telegram', label: 'Telegram' }, { value: 'email', label: 'Email' }, { value: 'sms', label: 'SMS' }]} />
            {test.channel === 'telegram' ? (
              <Select style={{ flex: 1 }} placeholder="Choose a linked chat" value={test.address || undefined}
                onChange={(v) => setTest({ ...test, address: v })}
                options={[
                  ...((data.telegram?.groups) || []).map(g => ({ value: String(g.chat_id), label: `Group: ${g.title}` })),
                  ...team.filter(r => r.telegram_chat_id).map(r => ({ value: String(r.telegram_chat_id), label: `${r.name} (team)` })),
                ]} notFoundContent="Nobody linked yet" />
            ) : (
            <Input placeholder={test.channel === 'email' ? 'name@company.com' : '0803 123 4567'} value={test.address}
              onChange={(e) => setTest({ ...test, address: e.target.value })} onPressEnter={sendTest} />
            )}
            <Button type="primary" loading={testing} disabled={!test.address.trim()} onClick={sendTest}>Send</Button>
          </div>

          <div className="al-card-h" style={{ marginTop: 26 }}>
            <span><TeamOutlined style={{ color: '#dc2626' }} /> Emergency response team</span>
            <Button size="small" icon={<PlusOutlined />} onClick={() => setTeam(t => [...t, { key: Date.now(), name: '', role: '', email: '', phone: '' }])}>Add</Button>
          </div>
          <div className="al-sub2">Always alerted — every muster, emergency, panic alarm, escalation and all-clear, wherever they are.</div>
          <div className="al-team">
            {team.length === 0 && <div className="al-empty">No one yet — add the OIM, HSE lead, control room and medic.</div>}
            {team.map(r => (
              <div key={r.key} className="al-team-row">
                <Input placeholder="Name" value={r.name} onChange={e => editTeam(r.key, 'name', e.target.value)} />
                <Input placeholder="Role" value={r.role} onChange={e => editTeam(r.key, 'role', e.target.value)} />
                <Input placeholder="Phone (WhatsApp)" value={r.phone} onChange={e => editTeam(r.key, 'phone', e.target.value)} />
                <Input placeholder="Email" value={r.email} onChange={e => editTeam(r.key, 'email', e.target.value)} />
                <Tooltip title={r.telegram_chat_id ? 'Telegram linked' : 'Get their personal Telegram link (save the team first)'}>
                  <Button type="text" icon={<SendOutlined style={{ color: r.telegram_chat_id ? '#16a34a' : '#94a3b8' }} />}
                    disabled={!data.telegram?.ready || typeof r.key !== 'number' || r.key >= team.length}
                    onClick={() => showLink({ responder_index: team.indexOf(r) }, r.name)} />
                </Tooltip>
                <Button type="text" danger icon={<DeleteOutlined />} onClick={() => setTeam(t => t.filter(x => x.key !== r.key))} />
              </div>
            ))}
          </div>
          <div className="al-foot">
            <span />
            <Button type="primary" icon={<SaveOutlined />} loading={teamSaving} onClick={saveTeam}>Save team</Button>
          </div>
        </section>
      </div>

      <TelegramCard data={data.telegram || {}} reload={load} showLink={showLink} />

      <section className="al-card" style={{ marginTop: 16 }}>
        <div className="al-card-h">
          <span>Alert log</span>
          <Button size="small" icon={<ReloadOutlined />} loading={logLoading} onClick={loadLog} />
        </div>
        <Table size="small" rowKey="id" dataSource={log} pagination={{ pageSize: 10 }} scroll={{ x: 900 }}
          columns={[
            { title: 'Time', dataIndex: 'created_at', width: 140, render: v => String(v).slice(0, 16) },
            { title: 'Alert', dataIndex: 'source_type', width: 120, render: v => <Tag>{v.replace(/_/g, ' ')}</Tag> },
            { title: 'Channel', dataIndex: 'channel', width: 100, render: v => v.toUpperCase() },
            { title: 'To', key: 'to', render: (_, r) => <span><b>{r.recipient_name}</b> · {r.address}</span> },
            { title: 'Status', dataIndex: 'status', width: 100,
              render: v => <Tag color={{ SENT: 'green', FAILED: 'red', SKIPPED: 'default' }[v]}>{v}</Tag> },
            { title: 'Reason', dataIndex: 'error', ellipsis: true, render: v => <span style={{ color: '#b45309' }}>{v}</span> },
          ]} />
      </section>
    </div>
  );
}

const CSS = `
.al-root { padding-bottom: 24px; }
.al-hero { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; padding: 22px 26px; border-radius: 18px;
  color: #fff; margin-bottom: 16px; background: radial-gradient(420px 200px at 90% -30%, rgba(37,211,102,.45), transparent 60%), linear-gradient(135deg, #0b1b36, #12305e 60%, #134e4a); }
.al-title { font-size: 21px; font-weight: 750; display: flex; gap: 10px; align-items: center; }
.al-sub { opacity: .8; font-size: 13.5px; margin-top: 4px; max-width: 560px; }
.al-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.al-chip { display: inline-flex; align-items: center; gap: 7px; padding: 7px 12px; border-radius: 12px; background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.16); font-weight: 600; font-size: 13px; color: #fca5a5; }
.al-chip.on { color: #86efac; }
.al-chip small { color: rgba(255,255,255,.65); font-weight: 500; }
.al-grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 16px; }
.al-card { background: #fff; border: 1px solid #e7eaf0; border-radius: 16px; padding: 18px 20px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
.al-card-h { display: flex; justify-content: space-between; align-items: center; font-weight: 700; font-size: 15px; margin-bottom: 12px; }
.al-card-h > span { display: inline-flex; gap: 8px; align-items: center; }
.al-sub2 { color: #64748b; font-size: 13px; margin-top: -6px; }
.al-two { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }
.al-hint { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; padding: 10px 12px; font-size: 12.5px; color: #166534; margin-bottom: 14px; line-height: 1.7; }
.al-hint code { background: #fff; border: 1px solid #bbf7d0; border-radius: 6px; padding: 1px 6px; margin: 0 6px; }
.al-foot { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #f0f2f6; padding-top: 12px; margin-top: 4px; }
.al-state { font-size: 13px; color: #94a3b8; display: inline-flex; gap: 6px; align-items: center; }
.al-state.ok { color: #16a34a; font-weight: 600; }
.al-team { display: flex; flex-direction: column; gap: 8px; margin: 12px 0; }
.al-team-row { display: grid; grid-template-columns: 1.1fr .9fr 1fr 1.2fr 32px 32px; gap: 6px; }
.al-tg-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 14px; }
.al-tg-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 8px; }
.al-empty { color: #94a3b8; font-size: 13px; padding: 14px; border: 1px dashed #e2e8f0; border-radius: 10px; text-align: center; }
@media (max-width: 1100px) { .al-grid { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .al-two, .al-team-row { grid-template-columns: 1fr; } }
`;


function TelegramCard({ data, reload, showLink }) {
  const { message } = App.useApp();
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(null);
  const [person, setPerson] = useState(null);
  const [opts, setOpts] = useState([]);
  const run = async (key, fn, ok) => {
    setBusy(key);
    try { const r = await fn(); if (ok) message.success(typeof ok === 'function' ? ok(r) : ok, 6); await reload(); }
    catch (e) { message.error(e.message, 8); } finally { setBusy(null); }
  };
  const search = async (q) => {
    if (!q || q.length < 2) return;
    try {
      const r = await apiService.get('/api/v1/personnel/', { search: q, page_size: 20 });
      setOpts((r?.results || []).map(p => ({ value: p.emp_code, label: `${p.full_name || p.first_name} · ${p.emp_code}` })));
    } catch { /* ignore */ }
  };
  const groups = data.groups || [];
  return (
    <section className="al-card" style={{ marginTop: 16 }}>
      <div className="al-card-h">
        <span><SendOutlined style={{ color: '#229ED9' }} /> Telegram</span>
        {data.has_token && (
          <Switch checked={data.enabled} checkedChildren="On" unCheckedChildren="Off" loading={busy === 'toggle'}
            onChange={(v) => run('toggle', () => apiService.put('/api/v1/settings/alerts/telegram', { enabled: v }), v ? 'Telegram alerts on' : 'Telegram alerts off')} />
        )}
      </div>
      {!data.has_token ? (
        <>
          <div className="al-hint" style={{ background: '#eff6ff', borderColor: '#bfdbfe', color: '#1e3a8a' }}>
            1. In Telegram, open <b>@BotFather</b> → <code>/newbot</code> → give it a name such as <i>Marconi Site Alerts</i>.<br />
            2. Paste the token it gives you below.<br />
            3. Staff press <b>Start</b> on the bot through their personal link; add the bot to your response-team group too.
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Input.Password placeholder="123456789:AA… (bot token from @BotFather)" value={token} onChange={e => setToken(e.target.value)} />
            <Button type="primary" disabled={!token.trim()} loading={busy === 'token'}
              onClick={() => run('token', () => apiService.put('/api/v1/settings/alerts/telegram', { bot_token: token.trim(), enabled: true }), 'Bot connected')}>Connect bot</Button>
          </div>
        </>
      ) : (
        <>
          <div className="al-tg-head">
            <div><span className="al-tg-dot" style={{ background: data.enabled ? '#16a34a' : '#94a3b8' }} />
              Bot <a href={`https://t.me/${data.bot_username}`} target="_blank" rel="noreferrer"><b>@{data.bot_username}</b></a>
              {' · '}<b>{data.linked_people}</b> staff linked</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button size="small" icon={<ReloadOutlined />} loading={busy === 'check'}
                onClick={() => run('check', () => apiService.post('/api/v1/settings/alerts/telegram/check'),
                  r => `Checked — ${r.data.linked || 0} new link(s), ${r.data.groups_added || 0} new group(s)`)}>Check now</Button>
              <Popconfirm title="Email every person on board who hasn't linked Telegram their personal link?"
                onConfirm={() => run('email', () => apiService.post('/api/v1/settings/alerts/telegram/email-links', { scope: 'onboard' }),
                  r => `Emailed ${r.data.emailed} of ${r.data.people} people`)}>
                <Button size="small" icon={<MailOutlined />} loading={busy === 'email'}>Email links to staff on board</Button>
              </Popconfirm>
            </div>
          </div>
          <div className="al-sub2" style={{ marginTop: 10 }}>Personal link for one person:</div>
          <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
            <Select showSearch filterOption={false} style={{ flex: 1 }} placeholder="Type a name…" value={person}
              onSearch={search} onChange={setPerson} options={opts} notFoundContent="Type 2+ letters" />
            <Button icon={<LinkOutlined />} disabled={!person} onClick={() => showLink({ emp_code: person }, opts.find(o => o.value === person)?.label || person)}>Get link</Button>
          </div>
          <div className="al-sub2" style={{ marginTop: 14 }}>Groups the bot is in — tick the response-team group(s); they get every team alert:</div>
          {groups.length === 0 ? (
            <div className="al-empty" style={{ marginTop: 6 }}>No groups yet — add <b>@{data.bot_username}</b> to your team's Telegram group, then press Check now.</div>
          ) : groups.map(g => (
            <div key={g.chat_id} style={{ padding: '6px 0' }}>
              <Checkbox checked={!!g.team}
                onChange={(e) => run('group', () => apiService.put('/api/v1/settings/alerts/telegram/groups',
                  groups.map(x => (x.chat_id === g.chat_id ? { ...x, team: e.target.checked } : x))), 'Saved')}>
                {g.title} {g.team && <Tag color="green" style={{ marginLeft: 6 }}>team group</Tag>}
              </Checkbox>
            </div>
          ))}
          <div className="al-foot" style={{ marginTop: 10 }}>
            <Input.Password size="small" placeholder="Replace bot token…" value={token} onChange={e => setToken(e.target.value)} style={{ maxWidth: 320 }} />
            <Button size="small" disabled={!token.trim()} loading={busy === 'token'}
              onClick={() => run('token', () => apiService.put('/api/v1/settings/alerts/telegram', { bot_token: token.trim() }), 'Bot token replaced')}>Replace</Button>
          </div>
        </>
      )}
    </section>
  );
}
