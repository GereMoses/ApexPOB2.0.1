/**
 * Email Setup — UI-managed, DB-backed email configuration.
 *
 * Each deployment configures its OWN sending domain + SMTP server here and sees the
 * SPF/DKIM/DMARC DNS records to publish — no backend env edits, no redeploy.
 * Backed by /api/v1/settings/email. Modern layout: gradient hero, progress stepper,
 * sticky status aside, code-block DNS records. Ant Design underneath for theming.
 */

import React, { useState, useEffect } from 'react';
import {
  Card, Form, Input, Button, Switch, Space, Typography, Tag, message,
  Skeleton, Tooltip, Collapse, Alert, theme as antdTheme,
} from 'antd';
import {
  MailOutlined, CloudServerOutlined, GlobalOutlined, SafetyCertificateOutlined,
  SendOutlined, KeyOutlined, SaveOutlined, CheckOutlined, CopyOutlined,
  ThunderboltOutlined, LockOutlined, CheckCircleFilled, LinkOutlined, SettingOutlined,
} from '@ant-design/icons';
import { api } from '../../services/api';

const { Text } = Typography;

const CSS = `
.es-root{ --r:18px; width:100%; padding-bottom:24px; }
.es-fields{ display:grid; grid-template-columns:1fr 1fr; gap:0 18px; }
.es-quick{ display:grid; grid-template-columns:minmax(0,1.7fr) minmax(0,1fr); gap:18px; margin-bottom:18px; align-items:start; }
.es-quick .es-fields{ grid-template-columns:1.3fr 1fr 1fr; gap:14px; }
.es-lbl{ font-size:12.5px; font-weight:600; color:var(--es-muted); margin-bottom:6px; }
.es-detect{ display:flex; gap:10px; align-items:center; margin-top:7px; font-size:12px; color:var(--es-muted); min-height:22px; }
.es-connected{ display:flex; gap:14px; align-items:center; padding:14px 16px; border-radius:14px; background:#f0fdf4; border:1px solid #bbf7d0; }
.es-ok{ font-size:28px; color:#16a34a; }
.es-adv{ background:var(--es-card); border:1px solid var(--es-bd); border-radius:18px; }
.es-adv .ant-collapse-content-box{ padding-top:4px !important; }
@media (max-width: 1100px){ .es-quick{ grid-template-columns:1fr; } .es-quick .es-fields{ grid-template-columns:1fr; } }
.es-hero{
  position:relative; overflow:hidden; border-radius:var(--r); padding:26px 28px;
  background:linear-gradient(120deg,#1e3a8a 0%,#4f46e5 48%,#7c3aed 100%);
  box-shadow:0 18px 40px -18px rgba(79,70,229,.55); color:#fff; margin-bottom:20px;
  display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;
}
.es-hero::before{ content:""; position:absolute; top:-60px; right:-30px; width:240px; height:240px;
  background:radial-gradient(circle,rgba(255,255,255,.22),transparent 70%); }
.es-hero-l{ display:flex; align-items:center; gap:16px; z-index:1; }
.es-hero-ico{ width:52px; height:52px; border-radius:14px; display:grid; place-items:center;
  font-size:24px; background:rgba(255,255,255,.16); backdrop-filter:blur(6px);
  border:1px solid rgba(255,255,255,.25); }
.es-hero-title{ font-size:22px; font-weight:700; line-height:1.1; letter-spacing:-.2px; }
.es-hero-sub{ font-size:13px; opacity:.85; margin-top:3px; max-width:440px; }
.es-hero-r{ display:flex; align-items:center; gap:10px; z-index:1; flex-wrap:wrap; }
.es-pill{ display:inline-flex; align-items:center; gap:7px; padding:6px 13px; border-radius:999px;
  font-size:12.5px; font-weight:600; background:rgba(255,255,255,.15);
  backdrop-filter:blur(6px); border:1px solid rgba(255,255,255,.25); }
.es-dot{ width:8px; height:8px; border-radius:50%; box-shadow:0 0 0 3px rgba(255,255,255,.15); }
.es-chip{ font-family:ui-monospace,Menlo,monospace; font-size:12px; padding:5px 11px; border-radius:999px;
  background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.22); }

.es-steps{ display:flex; align-items:center; margin:0 0 22px; padding:14px 18px; border-radius:14px;
  background:var(--es-card); border:1px solid var(--es-bd); overflow-x:auto; }
.es-step{ display:flex; align-items:center; gap:9px; white-space:nowrap; }
.es-sdot{ width:30px; height:30px; border-radius:9px; display:grid; place-items:center; font-size:14px;
  background:var(--es-muted-bg); color:var(--es-muted); border:1px solid var(--es-bd); transition:.25s; }
.es-step.done .es-sdot{ background:linear-gradient(135deg,#4f46e5,#7c3aed); color:#fff; border-color:transparent; }
.es-step.active .es-sdot{ box-shadow:0 0 0 4px rgba(124,58,237,.18); }
.es-slabel{ font-size:13px; font-weight:600; color:var(--es-muted); }
.es-step.done .es-slabel{ color:var(--es-text); }
.es-sline{ flex:1; height:2px; min-width:22px; margin:0 12px; border-radius:2px; background:var(--es-bd); }
.es-step.done + .es-sline, .es-sline.on{ background:linear-gradient(90deg,#4f46e5,#7c3aed); }

.es-grid{ display:grid; grid-template-columns:1fr 320px; gap:20px; align-items:start; }
.es-card{ background:var(--es-card); border:1px solid var(--es-bd); border-radius:var(--r);
  box-shadow:0 1px 2px rgba(0,0,0,.04); transition:box-shadow .2s, transform .2s; }
.es-card:hover{ box-shadow:0 10px 30px -18px rgba(30,41,120,.35); }
.es-card-h{ display:flex; align-items:center; gap:12px; padding:16px 20px; border-bottom:1px solid var(--es-bd); }
.es-tile{ width:38px; height:38px; border-radius:11px; display:grid; place-items:center; font-size:17px; flex-shrink:0; }
.es-card-t{ font-size:14.5px; font-weight:650; color:var(--es-text); line-height:1.15; }
.es-card-s{ font-size:12px; color:var(--es-muted); }
.es-card-b{ padding:18px 20px; }
.es-aside{ position:sticky; top:14px; display:flex; flex-direction:column; gap:16px; }

.es-check{ display:flex; align-items:center; gap:11px; padding:9px 0; }
.es-cbox{ width:22px; height:22px; border-radius:7px; display:grid; place-items:center; font-size:12px; flex-shrink:0;
  border:1px solid var(--es-bd); color:var(--es-muted); background:var(--es-muted-bg); }
.es-cbox.on{ background:linear-gradient(135deg,#16a34a,#22c55e); border-color:transparent; color:#fff; }
.es-clabel{ font-size:13px; color:var(--es-text); }
.es-clabel.off{ color:var(--es-muted); }

.es-dnsblk{ background:#0e1526; border:1px solid #1e293b; border-radius:14px; padding:14px 16px; margin-top:12px;
  display:flex; gap:14px; align-items:flex-start; }
.es-dnsblk:first-child{ margin-top:0; }
.es-dtag{ font-size:11px; font-weight:700; letter-spacing:.04em; padding:4px 9px; border-radius:7px; flex-shrink:0; color:#fff; }
.es-drow{ flex:1; min-width:0; }
.es-dmeta{ font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:.05em; }
.es-dhost{ font-family:ui-monospace,Menlo,monospace; font-size:12.5px; color:#93c5fd; margin:2px 0 8px; word-break:break-all; }
.es-dval{ position:relative; background:#070b16; border:1px solid #1e293b; border-radius:9px; padding:9px 40px 9px 11px;
  font-family:ui-monospace,Menlo,monospace; font-size:12px; color:#e2e8f0; word-break:break-all; line-height:1.5; }
.es-dcopy{ position:absolute; top:7px; right:7px; width:26px; height:26px; border-radius:7px; border:1px solid #1e293b;
  background:#0e1526; color:#94a3b8; cursor:pointer; display:grid; place-items:center; transition:.15s; }
.es-dcopy:hover{ background:#4f46e5; color:#fff; border-color:transparent; }
.es-dpurpose{ font-size:11.5px; color:#64748b; margin-top:7px; }

.es-save{ height:46px; border:none; border-radius:12px; font-weight:600; padding:0 26px;
  background:linear-gradient(120deg,#4f46e5,#7c3aed); box-shadow:0 10px 24px -12px rgba(79,70,229,.7); }
.es-save:hover{ filter:brightness(1.07); }

@media (max-width:900px){ .es-grid{ grid-template-columns:1fr; } .es-aside{ position:static; } }
@media (max-width:620px){ .es-fields{ grid-template-columns:1fr; } }
`;

const EmailSetup = () => {
  const { token } = antdTheme.useToken();
  const [form] = Form.useForm();
  const [meta, setMeta] = useState({ has_password: false, has_dkim: false, configured: false, sending_domain: '' });
  const [dns, setDns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [genning, setGenning] = useState(false);
  const [testAddr, setTestAddr] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [copied, setCopied] = useState('');
  const [quick, setQuick] = useState({ email: '', app_password: '', from_name: 'Apex POB' });
  const [detected, setDetected] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [connectErr, setConnectErr] = useState(null);
  const [editing, setEditing] = useState(false);

  // Show which provider the address belongs to while the admin types.
  useEffect(() => {
    const e = quick.email.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e)) { setDetected(null); return undefined; }
    const t = setTimeout(async () => {
      try { setDetected((await api.get(`/api/v1/settings/email/detect?email=${encodeURIComponent(e)}`)).data); }
      catch { setDetected(null); }
    }, 450);
    return () => clearTimeout(t);
  }, [quick.email]);

  const connect = async () => {
    setConnecting(true); setConnectErr(null);
    try {
      const res = await api.post('/api/v1/settings/email/quick-setup', quick);
      if (res.success) {
        message.success(res.message, 6);
        await load();
        setEditing(false);
        setQuick(q => ({ ...q, app_password: '' }));
      } else {
        setConnectErr({ text: res.message, help: res.data?.help_url });
      }
    } catch (e) { setConnectErr({ text: e.message }); }
    finally { setConnecting(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const load = async () => {
    try {
      const res = await api.get('/api/v1/settings/email');
      const d = res.data || {};
      form.setFieldsValue({
        smtp_host: d.smtp_host || '', smtp_port: d.smtp_port || '587',
        smtp_user: d.smtp_user || '', smtp_password: '',
        from_address: d.from_address || '', from_name: d.from_name || 'Apex POB',
        use_tls: d.use_tls !== false, enabled: !!d.enabled,
        sending_domain: d.sending_domain || '', dkim_selector: d.dkim_selector || 'pob',
      });
      applyResult(d);
      setQuick(q => ({ ...q, email: q.email || d.smtp_user || '', from_name: d.from_name || q.from_name }));
    } catch { message.error('Could not load email settings'); }
    finally { setLoading(false); }
  };

  const applyResult = (d) => {
    setMeta({
      has_password: !!d.has_password, has_dkim: !!d.has_dkim,
      configured: !!d.configured, sending_domain: d.sending_domain || '',
      smtp_user: d.smtp_user || '', smtp_host: d.smtp_host || '', smtp_port: d.smtp_port || '',
      from_address: d.from_address || '',
    });
    setDns(d.dns_records || []);
  };

  const save = async () => {
    let values;
    try { values = await form.validateFields(); } catch { return; }
    setSaving(true);
    try {
      const payload = { ...values };
      if (!payload.smtp_password) delete payload.smtp_password;
      const res = await api.put('/api/v1/settings/email', payload);
      applyResult(res.data || {});
      form.setFieldsValue({ smtp_password: '' });
      message.success('Email settings saved');
    } catch (e) { message.error('Save failed: ' + (e.message)); }
    finally { setSaving(false); }
  };

  const generateDkim = async () => {
    if (!form.getFieldValue('sending_domain')?.trim()) { message.warning('Enter and save a sending domain first'); return; }
    setGenning(true);
    try {
      const res = await api.post('/api/v1/settings/email/dkim/generate', {});
      applyResult(res.data || {});
      message.success('DKIM key generated — publish the DKIM record below');
    } catch (e) { message.error('DKIM generation failed: ' + (e.message)); }
    finally { setGenning(false); }
  };

  const sendTest = async () => {
    if (!testAddr.trim()) { message.warning('Enter an email address to test'); return; }
    setTesting(true); setTestResult(null);
    try {
      const res = await api.post('/api/v1/settings/email/test', { address: testAddr.trim() });
      setTestResult(res.data || {});
    } catch (e) { setTestResult({ sent: 0, error: e.message }); }
    finally { setTesting(false); }
  };

  const copy = (text, id) => {
    if (!text) return;
    navigator.clipboard?.writeText(text);
    setCopied(id); message.success('Copied'); setTimeout(() => setCopied(''), 1400);
  };

  const themeVars = {
    '--es-card': token.colorBgContainer,
    '--es-bd': token.colorBorderSecondary,
    '--es-text': token.colorText,
    '--es-muted': token.colorTextTertiary,
    '--es-muted-bg': token.colorFillTertiary,
  };

  if (loading) return <Card><Skeleton active paragraph={{ rows: 8 }} /></Card>;

  const current = !meta.configured ? 0 : (!meta.sending_domain ? 1 : (!meta.has_dkim ? 2 : 3));
  const steps = [
    { t: 'Mail server', i: <CloudServerOutlined /> },
    { t: 'Domain & DKIM', i: <GlobalOutlined /> },
    { t: 'Publish DNS', i: <SafetyCertificateOutlined /> },
    { t: 'Test', i: <SendOutlined /> },
  ];
  const checks = [
    { label: 'Mail server configured', done: meta.configured },
    { label: 'Password saved', done: meta.has_password },
    { label: 'Sending domain set', done: !!meta.sending_domain },
    { label: 'DKIM key generated', done: meta.has_dkim },
    { label: 'DNS records ready', done: dns.length > 0 && meta.has_dkim },
  ];
  const tagColors = { SPF: '#2563eb', DKIM: '#7c3aed', DMARC: '#16a34a' };
  const kindOf = (host) => host?.includes('_domainkey') ? 'DKIM' : host?.includes('_dmarc') ? 'DMARC' : 'SPF';

  const tile = (Icon, from, to) => (
    <div className="es-tile" style={{ background: `linear-gradient(135deg,${from},${to})`, color: '#fff' }}>
      <Icon />
    </div>
  );

  const fieldLabel = (t) => <span style={{ fontSize: 12.5, fontWeight: 600, color: token.colorTextSecondary }}>{t}</span>;

  return (
    <div className="es-root" style={themeVars}>
      <style>{CSS}</style>

      {/* Hero */}
      <div className="es-hero">
        <div className="es-hero-l">
          <div className="es-hero-ico"><MailOutlined /></div>
          <div>
            <div className="es-hero-title">Email Delivery</div>
            <div className="es-hero-sub">Send emergency &amp; muster alerts from your own domain — configured entirely here, no server access needed.</div>
          </div>
        </div>
        <div className="es-hero-r">
          {meta.sending_domain && <span className="es-chip">{meta.sending_domain}</span>}
          <span className="es-pill">
            <span className="es-dot" style={{ background: meta.configured ? '#4ade80' : '#fbbf24' }} />
            {meta.configured ? 'Configured' : 'Not configured'}
          </span>
        </div>
      </div>

      {/* Simple setup: address + app password */}
      <div className="es-quick">
        <div className="es-card">
          <div className="es-card-h">
            {tile(MailOutlined, '#2563eb', '#4f46e5')}
            <div style={{ flex: 1 }}>
              <div className="es-card-t">Connect your mailbox</div>
              <div className="es-card-s">Just the email address and an app password — ApexPOB finds the mail server.</div>
            </div>
          </div>
          <div className="es-card-b">
            {meta.configured && meta.has_password && !editing ? (
              <div className="es-connected">
                <CheckCircleFilled className="es-ok" />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 650, fontSize: 15 }}>Sending from {meta.from_address || meta.smtp_user}</div>
                  <div style={{ fontSize: 12.5, color: token.colorTextTertiary }}>via {meta.smtp_host}:{meta.smtp_port}</div>
                </div>
                <Button onClick={() => setEditing(true)}>Change</Button>
              </div>
            ) : (
              <>
                <div className="es-fields">
                  <div>
                    <div className="es-lbl">Email address</div>
                    <Input size="large" prefix={<MailOutlined style={{ color: token.colorTextTertiary }} />} placeholder="alerts@yourcompany.com"
                      value={quick.email} onChange={(e) => setQuick({ ...quick, email: e.target.value })} autoComplete="off" />
                    <div className="es-detect">
                      {detected ? <><Tag color="blue" bordered={false} style={{ margin: 0 }}>{detected.provider_name}</Tag>
                        {detected.help_url && <a href={detected.help_url} target="_blank" rel="noreferrer"><LinkOutlined /> Create an app password</a>}</>
                        : <span>We detect Gmail, Microsoft 365, Outlook, Yahoo, Zoho and company domains.</span>}
                    </div>
                  </div>
                  <div>
                    <div className="es-lbl">App password</div>
                    <Input.Password size="large" prefix={<LockOutlined style={{ color: token.colorTextTertiary }} />} placeholder="16-character app password"
                      value={quick.app_password} onChange={(e) => setQuick({ ...quick, app_password: e.target.value })} autoComplete="new-password"
                      onPressEnter={connect} />
                  </div>
                  <div>
                    <div className="es-lbl">Sender name</div>
                    <Input size="large" placeholder="Apex POB" value={quick.from_name} onChange={(e) => setQuick({ ...quick, from_name: e.target.value })} />
                  </div>
                </div>
                {detected?.provider === 'microsoft' && (
                  <Alert type="info" showIcon style={{ marginTop: 14, borderRadius: 10 }}
                    message="Microsoft 365 mailbox"
                    description="App passwords need multi-factor sign-in on the account, and an admin must allow “Authenticated SMTP” for this mailbox (Microsoft 365 admin centre → Users → the user → Mail → Manage email apps)." />
                )}
                {detected?.provider === 'google' && (
                  <Alert type="info" showIcon style={{ marginTop: 14, borderRadius: 10 }}
                    message="Gmail / Google Workspace"
                    description="Turn on 2-Step Verification, then create an app password at myaccount.google.com/apppasswords and paste the 16 characters here." />
                )}
                {connectErr && (
                  <Alert type="error" showIcon style={{ marginTop: 14, borderRadius: 10 }} message={connectErr.text}
                    description={connectErr.help ? <a href={connectErr.help} target="_blank" rel="noreferrer">Create an app password</a> : null} />
                )}
                <div style={{ display: 'flex', gap: 10, marginTop: 16, alignItems: 'center' }}>
                  <Button type="primary" size="large" icon={<LinkOutlined />} loading={connecting} onClick={connect}
                    disabled={!quick.email.includes('@') || quick.app_password.length < 4}>
                    {connecting ? 'Checking the login…' : 'Connect'}
                  </Button>
                  {editing && <Button size="large" onClick={() => setEditing(false)}>Cancel</Button>}
                  <span style={{ fontSize: 12.5, color: token.colorTextTertiary }}>We sign in once to prove it works before saving. The password is stored encrypted.</span>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="es-card">
          <div className="es-card-h">{tile(SendOutlined, '#10b981', '#0ea5e9')}
            <div><div className="es-card-t">Send a test</div><div className="es-card-s">Uses the saved mailbox</div></div>
          </div>
          <div className="es-card-b">
            <Input value={testAddr} onChange={(e) => setTestAddr(e.target.value)} onPressEnter={sendTest}
              placeholder="you@example.com" prefix={<MailOutlined style={{ color: token.colorTextTertiary }} />} style={{ marginBottom: 10 }} />
            <Button type="primary" icon={<ThunderboltOutlined />} onClick={sendTest} loading={testing} block disabled={!meta.configured}>Send test email</Button>
            {testResult && (
              <div style={{
                marginTop: 12, padding: '10px 12px', borderRadius: 10, fontSize: 12.5,
                background: testResult.sent ? token.colorSuccessBg : token.colorErrorBg,
                color: testResult.sent ? token.colorSuccessText : token.colorErrorText,
                border: `1px solid ${testResult.sent ? token.colorSuccessBorder : token.colorErrorBorder}`,
              }}>
                {testResult.sent ? `✓ Sent to ${testResult.address}. Check the inbox.` : `✕ ${testResult.error || 'Send failed'}`}
              </div>
            )}
          </div>
        </div>
      </div>

      <Collapse className="es-adv" bordered={false} items={[{
        key: 'adv',
        label: <span style={{ fontWeight: 650 }}><SettingOutlined /> Advanced — custom mail server, sending domain &amp; DKIM</span>,
        children: (
          <>
      {/* Stepper */}
      <div className="es-steps">
        {steps.map((s, i) => (
          <React.Fragment key={s.t}>
            <div className={`es-step ${i <= current ? 'done' : ''} ${i === current ? 'active' : ''}`}>
              <div className="es-sdot">{i < current ? <CheckOutlined /> : s.i}</div>
              <span className="es-slabel">{s.t}</span>
            </div>
            {i < steps.length - 1 && <div className={`es-sline ${i < current ? 'on' : ''}`} />}
          </React.Fragment>
        ))}
      </div>

      {/* Grid: main config + sticky aside */}
      <div className="es-grid">
        <div>
          <Form form={form} layout="vertical" requiredMark={false}>
            {/* Mail server */}
            <div className="es-card" style={{ marginBottom: 20 }}>
              <div className="es-card-h">
                {tile(CloudServerOutlined, '#4f46e5', '#7c3aed')}
                <div>
                  <div className="es-card-t">Mail server</div>
                  <div className="es-card-s">SMTP connection used to send mail</div>
                </div>
              </div>
              <div className="es-card-b">
                <div className="es-fields">
                  <Form.Item name="smtp_host" label={fieldLabel('SMTP host')} rules={[{ required: true, message: 'Enter your mail server hostname' }]}>
                    <Input prefix={<CloudServerOutlined style={{ color: token.colorTextTertiary }} />} placeholder="mail.yourcompany.com" />
                  </Form.Item>
                  <Form.Item name="smtp_port" label={fieldLabel('Port')}><Input placeholder="587" /></Form.Item>
                  <Form.Item name="smtp_user" label={fieldLabel('Username')}>
                    <Input placeholder="apps@yourcompany.com" autoComplete="off" />
                  </Form.Item>
                  <Form.Item name="smtp_password"
                    label={<Space size={6}>{fieldLabel('Password')}{meta.has_password && <Tag color="green" bordered={false} style={{ margin: 0, fontSize: 10 }}>saved</Tag>}</Space>}>
                    <Input.Password prefix={<LockOutlined style={{ color: token.colorTextTertiary }} />} autoComplete="new-password"
                      placeholder={meta.has_password ? 'Leave blank to keep current' : 'App password / SMTP key'} />
                  </Form.Item>
                  <Form.Item name="from_address" label={fieldLabel('From address')} rules={[{ type: 'email', message: 'Enter a valid email' }]}>
                    <Input prefix={<MailOutlined style={{ color: token.colorTextTertiary }} />} placeholder="alerts@yourcompany.com" />
                  </Form.Item>
                  <Form.Item name="from_name" label={fieldLabel('From name')}><Input placeholder="Company Safety" /></Form.Item>
                </div>
                <Space size="large" style={{ marginTop: 4 }}>
                  <Space size={8}><Form.Item name="use_tls" valuePropName="checked" noStyle><Switch size="small" /></Form.Item>
                    <Text type="secondary" style={{ fontSize: 13 }}>STARTTLS (port 587)</Text></Space>
                  <Space size={8}><Form.Item name="enabled" valuePropName="checked" noStyle><Switch size="small" /></Form.Item>
                    <Text type="secondary" style={{ fontSize: 13 }}>Enabled</Text></Space>
                </Space>
              </div>
            </div>

            {/* Domain & DKIM */}
            <div className="es-card" style={{ marginBottom: 20 }}>
              <div className="es-card-h">
                {tile(GlobalOutlined, '#0ea5e9', '#6366f1')}
                <div style={{ flex: 1 }}>
                  <div className="es-card-t">Sending domain &amp; authentication</div>
                  <div className="es-card-s">Prove the mail is really from you</div>
                </div>
                <Tag color={meta.has_dkim ? 'success' : 'default'} bordered={false}>
                  {meta.has_dkim ? 'DKIM key present' : 'No DKIM key'}
                </Tag>
              </div>
              <div className="es-card-b">
                <div className="es-fields">
                  <Form.Item name="sending_domain" label={fieldLabel('Sending domain')} extra="The domain your From address uses">
                    <Input prefix={<GlobalOutlined style={{ color: token.colorTextTertiary }} />} placeholder="alerts.yourcompany.com" />
                  </Form.Item>
                  <Form.Item name="dkim_selector" label={fieldLabel('DKIM selector')}><Input placeholder="pob" /></Form.Item>
                </div>
                <Space wrap>
                  <Button icon={<KeyOutlined />} onClick={generateDkim} loading={genning}>
                    {meta.has_dkim ? 'Regenerate DKIM key' : 'Generate DKIM key'}
                  </Button>
                  <Text type="secondary" style={{ fontSize: 12 }}>Save the domain first, then generate the key.</Text>
                </Space>
              </div>
            </div>

            <button type="button" className="es-save ant-btn ant-btn-primary" onClick={save} disabled={saving}
              style={{ color: '#fff', display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer', opacity: saving ? .7 : 1 }}>
              <SaveOutlined /> {saving ? 'Saving…' : 'Save settings'}
            </button>
          </Form>
        </div>

        {/* Aside */}
        <aside className="es-aside">
          <div className="es-card">
            <div className="es-card-h">{tile(ThunderboltOutlined, '#f59e0b', '#ef4444')}
              <div><div className="es-card-t">Setup status</div><div className="es-card-s">Complete every step</div></div>
            </div>
            <div className="es-card-b" style={{ paddingTop: 6, paddingBottom: 10 }}>
              {checks.map((c) => (
                <div className="es-check" key={c.label}>
                  <div className={`es-cbox ${c.done ? 'on' : ''}`}>{c.done ? <CheckOutlined /> : ''}</div>
                  <span className={`es-clabel ${c.done ? '' : 'off'}`}>{c.label}</span>
                </div>
              ))}
            </div>
          </div>

        </aside>
      </div>

      {/* DNS records — full width */}
      <div className="es-card" style={{ marginTop: 20 }}>
        <div className="es-card-h">
          {tile(SafetyCertificateOutlined, '#7c3aed', '#db2777')}
          <div style={{ flex: 1 }}>
            <div className="es-card-t">DNS records to publish</div>
            <div className="es-card-s">Add these TXT records at your DNS provider so mail isn't flagged as spam</div>
          </div>
        </div>
        <div className="es-card-b">
          {dns.length === 0 ? (
            <div style={{ padding: '18px 4px', textAlign: 'center', color: token.colorTextTertiary, fontSize: 13 }}>
              Set and save a sending domain, then generate a DKIM key to see the records here.
            </div>
          ) : dns.map((r, i) => {
            const kind = kindOf(r.host);
            return (
              <div className="es-dnsblk" key={r.host + i}>
                <span className="es-dtag" style={{ background: tagColors[kind] }}>{kind}</span>
                <div className="es-drow">
                  <div className="es-dmeta">TXT record · host</div>
                  <div className="es-dhost">{r.host}</div>
                  {r.value ? (
                    <div className="es-dval">
                      {r.value}
                      <Tooltip title={copied === `v${i}` ? 'Copied!' : 'Copy value'}>
                        <button className="es-dcopy" onClick={() => copy(r.value, `v${i}`)}>
                          {copied === `v${i}` ? <CheckOutlined /> : <CopyOutlined />}
                        </button>
                      </Tooltip>
                    </div>
                  ) : <Text type="warning" italic style={{ fontSize: 12 }}>Generate a DKIM key first</Text>}
                  <div className="es-dpurpose">{r.purpose}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
          </>
        ),
      }]} />
    </div>
  );
};

export default EmailSetup;
