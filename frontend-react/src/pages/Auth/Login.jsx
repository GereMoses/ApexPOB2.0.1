import React, { useState } from 'react';
import { Form, Input, Button, App } from 'antd';
import {
  UserOutlined, LockOutlined, SafetyOutlined, TeamOutlined,
  ApartmentOutlined, AlertOutlined, DashboardOutlined,
  EyeInvisibleOutlined, EyeOutlined, RightOutlined, MobileOutlined, CheckCircleOutlined,
} from '@ant-design/icons';

/* Right-hand sign-in column: card-less, large inputs (left hero panel unchanged). */
const C = {
  bg: '#f4f5f7', ink: '#111827', muted: '#6b7280', label: '#4b5563', line: '#e5e7eb',
  blue: '#3b74e8', blueLight: '#5b8ff5', green: '#16a34a',
};
const labelStyle = {
  display: 'block', fontSize: 12, fontWeight: 600, color: C.label,
  letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8,
};

/* ─── Feature list shown in the left panel ─────────────── */
const FEATURES = [
  { icon: <TeamOutlined />,      label: 'Personnel On Board Management' },
  { icon: <SafetyOutlined />,    label: 'Access Control & Biometrics'   },
  { icon: <AlertOutlined />,     label: 'Emergency Response System'      },
  { icon: <ApartmentOutlined />, label: 'Department & Role Management'   },
  { icon: <DashboardOutlined />, label: 'Real-time Analytics Dashboard'  },
];

/* ─── Animated floating orbs (pure CSS, no library) ────── */
const ORB_DEFS = [
  { size: 420, top: '-12%', left: '-8%',   delay: '0s',    dur: '18s', opacity: 0.07 },
  { size: 280, top: '55%',  left: '-5%',   delay: '-6s',   dur: '22s', opacity: 0.06 },
  { size: 360, top: '20%',  left: '65%',   delay: '-3s',   dur: '20s', opacity: 0.05 },
  { size: 200, top: '75%',  left: '72%',   delay: '-9s',   dur: '16s', opacity: 0.08 },
  { size: 140, top: '40%',  left: '30%',   delay: '-12s',  dur: '14s', opacity: 0.04 },
];

const Login = ({ onLogin }) => {
  const { message, modal } = App.useApp();
  const [loading, setLoading]       = useState(false);
  const [year]                      = useState(new Date().getFullYear());
  // MFA step state
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaPendingToken, setMfaPendingToken] = useState(null);
  const [mfaLoading, setMfaLoading] = useState(false);
  const [mfaForm] = Form.useForm();

  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      const formData = new URLSearchParams();
      formData.append('username', values.username);
      formData.append('password', values.password);

      const response = await fetch('/api/v1/auth/production-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString(),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Authentication failed');
      }

      const data = await response.json();

      // If backend requires MFA, show the TOTP step instead of logging in
      if (data.mfa_required) {
        setMfaPendingToken(data.access_token);
        setMfaRequired(true);
        message.info('Enter the code from your authenticator app to continue.');
        return;
      }

      localStorage.setItem('token', data.access_token);
      localStorage.removeItem('authToken');
      localStorage.removeItem('access_token');
      localStorage.setItem('user_info', JSON.stringify(data.user));
      onLogin(data.user, data.access_token);
      message.success('Welcome back — access granted');
    } catch (error) {
      message.error(error.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleMfaSubmit = async (values) => {
    setMfaLoading(true);
    try {
      const response = await fetch('/api/v1/mfa/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${mfaPendingToken}`,
        },
        body: JSON.stringify({ code: values.totp_code }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'MFA verification failed');
      }

      const data = await response.json();
      // Fetch full user profile with the real token
      const meRes = await fetch('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (!meRes.ok) {
        throw new Error('Failed to load your profile after MFA. Please try again.');
      }
      const userData = await meRes.json();

      localStorage.setItem('token', data.access_token);
      localStorage.removeItem('authToken');
      localStorage.removeItem('access_token');
      localStorage.setItem('user_info', JSON.stringify(userData));
      onLogin(userData, data.access_token);
      message.success('Welcome back — access granted');
    } catch (error) {
      message.error(error.message || 'Invalid code. Try again.');
    } finally {
      setMfaLoading(false);
    }
  };

  // There is no self-service password reset: say so instead of a dead link.
  const forgotPassword = () => modal.info({
    title: 'Reset your password',
    content: 'Ask your ApexPOB administrator to reset it (Settings → Users).',
  });

  const primaryButton = {
    height: 54, borderRadius: 14, border: 'none',
    background: `linear-gradient(90deg, ${C.blue} 0%, ${C.blueLight} 100%)`,
    boxShadow: '0 12px 28px rgba(59,116,232,0.28)', fontSize: 17, fontWeight: 600,
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      background: '#0a0f1e',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    }}>

      {/* ═══ LEFT PANEL — Branding ════════════════════════════ */}
      <div style={{
        flex: '0 0 52%',
        position: 'relative',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '52px 56px',
      }}>

        {/* Access control background photo */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: 'url(/logo/access-control-bg.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center center',
          backgroundRepeat: 'no-repeat',
        }} />

        {/* Dark overlay — top heavier so text stays readable, bottom lighter to show scene */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(180deg, rgba(5,12,30,0.82) 0%, rgba(5,14,36,0.60) 50%, rgba(5,12,30,0.75) 100%)',
        }} />

        {/* Subtle grid on top of photo */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          backgroundImage: `
            linear-gradient(rgba(79,142,247,0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(79,142,247,0.05) 1px, transparent 1px)
          `,
          backgroundSize: '48px 48px',
        }} />

        {/* Floating orbs */}
        {ORB_DEFS.map((o, i) => (
          <div key={i} style={{
            position: 'absolute',
            top: o.top, left: o.left,
            width: o.size, height: o.size,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(79,142,247,0.35) 0%, transparent 70%)',
            opacity: o.opacity,
            animation: `orbFloat ${o.dur} ease-in-out ${o.delay} infinite`,
            pointerEvents: 'none',
          }} />
        ))}

        {/* Top: Apex POB (application) logo */}
        <div style={{ position: 'relative', zIndex: 2 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 6 }}>
            <div style={{
              background: 'white',
              borderRadius: 14,
              padding: '8px 14px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.35)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <img
                src="/logo/apex-pob.png"
                alt="Apex POB"
                style={{ height: 44, width: 'auto', display: 'block' }}
              />
            </div>
            <div>
              <div style={{ color: 'white', fontSize: 18, fontWeight: 800, letterSpacing: '-0.2px', lineHeight: 1.2 }}>
                Apex POB
              </div>
              <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', marginTop: 3 }}>
                Personnel On Board
              </div>
            </div>
          </div>
        </div>

        {/* Middle: Hero text + features */}
        <div style={{ position: 'relative', zIndex: 2, flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', paddingTop: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: 'rgba(79,142,247,0.12)',
              border: '1px solid rgba(79,142,247,0.25)',
              borderRadius: 20, padding: '4px 12px',
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#4ade80',
                boxShadow: '0 0 6px #4ade80',
                display: 'inline-block',
                animation: 'pulse 2s infinite',
              }} />
              <span style={{
                color: 'rgba(255,255,255,0.55)', fontSize: 10, fontWeight: 700,
                letterSpacing: '0.18em', textTransform: 'uppercase',
              }}>
                Biometric Access Enabled
              </span>
            </div>
          </div>

          <div style={{
            color: 'rgba(255,255,255,0.18)', fontSize: 11, fontWeight: 700,
            letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: 16,
          }}>
            Personnel On Board Management
          </div>

          <h1 style={{
            color: 'white', fontSize: 38, fontWeight: 800,
            lineHeight: 1.15, letterSpacing: '-0.8px', margin: 0, marginBottom: 8,
          }}>
            Manage your<br />
            <span style={{ background: 'linear-gradient(90deg, #4f8ef7, #38bdf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              workforce
            </span>{' '}
            with<br />precision.
          </h1>

          <p style={{
            color: 'rgba(255,255,255,0.45)', fontSize: 14, lineHeight: 1.7,
            maxWidth: 380, margin: '16px 0 36px',
          }}>
            BioTime 9.5-compatible access control, biometric integration, emergency management and real-time personnel tracking — all in one platform.
          </p>

          {/* Feature list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {FEATURES.map((f, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                  background: 'rgba(79,142,247,0.1)',
                  border: '1px solid rgba(79,142,247,0.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#4f8ef7', fontSize: 14,
                }}>
                  {f.icon}
                </div>
                <span style={{ color: 'rgba(255,255,255,0.65)', fontSize: 13, fontWeight: 500 }}>
                  {f.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom: Stats row */}
        <div style={{
          position: 'relative', zIndex: 2,
          display: 'flex', gap: 32,
          paddingTop: 32,
          borderTop: '1px solid rgba(255,255,255,0.06)',
        }}>
          {[
            { value: '99.9%', label: 'Uptime SLA'   },
            { value: 'ISO',   label: 'Certified'     },
            { value: '24/7',  label: 'Monitoring'    },
          ].map((s, i) => (
            <div key={i}>
              <div style={{ color: 'white', fontSize: 18, fontWeight: 800 }}>{s.value}</div>
              <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: 11, marginTop: 2 }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ═══ RIGHT PANEL — card-less sign-in ═════════════════ */}
      <div className="apx-login" style={{
        flex: 1, background: C.bg,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        padding: '44px 32px 32px',
      }}>
        <div style={{ width: '100%', maxWidth: 460, flex: 1, display: 'flex', flexDirection: 'column' }}>

          <div style={{ textAlign: 'center', fontSize: 13, fontWeight: 600, color: C.muted,
            letterSpacing: '0.22em', textTransform: 'uppercase' }}>
            Apex POB
          </div>

          <div style={{ marginTop: 'auto' }} />
          <div style={{ textAlign: 'center', margin: '0 0 44px' }}>
            <h1 style={{ margin: 0, fontSize: 38, fontWeight: 800, color: C.ink, letterSpacing: '-1px' }}>
              {mfaRequired ? 'Two-step verification' : 'Welcome back'}
            </h1>
            <div style={{ marginTop: 10, fontSize: 17, color: C.muted }}>
              {mfaRequired ? 'Enter the 6-digit code from your authenticator app' : 'Sign in to your account'}
            </div>
          </div>

          {/* ── MFA step ── */}
          {mfaRequired && (
            <Form form={mfaForm} onFinish={handleMfaSubmit} layout="vertical" requiredMark={false}>
              <label style={labelStyle} htmlFor="totp_code">Authentication code</label>
              <Form.Item
                name="totp_code"
                rules={[
                  { required: true, message: 'Code is required' },
                  { len: 6, message: 'Code must be 6 digits' },
                  { pattern: /^\d+$/, message: 'Digits only' },
                ]}
                style={{ marginBottom: 32 }}
              >
                <Input id="totp_code" className="apx-input" prefix={<MobileOutlined className="apx-icon" />}
                  placeholder="000000" maxLength={6} autoFocus style={{ letterSpacing: 8 }} />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={mfaLoading} block style={primaryButton}>
                {mfaLoading ? 'Verifying…' : 'Verify code'}
              </Button>
              <div style={{ textAlign: 'center', marginTop: 16 }}>
                <Button type="link" onClick={() => { setMfaRequired(false); setMfaPendingToken(null); }}
                  style={{ color: C.blue }}>
                  ← Back to sign in
                </Button>
              </div>
            </Form>
          )}

          {/* ── Sign-in form ── */}
          {!mfaRequired && (
            <Form name="login" onFinish={handleSubmit} layout="vertical" requiredMark={false}>
              <label style={labelStyle} htmlFor="username">Username or email</label>
              <Form.Item name="username" rules={[{ required: true, message: 'Username is required' }]}
                style={{ marginBottom: 30 }}>
                <Input id="username" className="apx-input" autoComplete="username" autoFocus
                  prefix={<UserOutlined className="apx-icon" />} placeholder="Enter your username" />
              </Form.Item>

              <label style={labelStyle} htmlFor="password">Password</label>
              <Form.Item name="password" rules={[{ required: true, message: 'Password is required' }]}
                style={{ marginBottom: 12 }}>
                <Input.Password id="password" className="apx-input apx-password" autoComplete="current-password"
                  prefix={<LockOutlined className="apx-icon" />} placeholder="Enter your password"
                  iconRender={(visible) => (visible ? <EyeInvisibleOutlined /> : <EyeOutlined />)} />
              </Form.Item>

              <button type="button" onClick={forgotPassword} style={{
                all: 'unset', cursor: 'pointer', color: C.blueLight, fontSize: 15, fontWeight: 500,
              }}>
                Forgot Password?
              </button>

              <Button type="primary" htmlType="submit" loading={loading} block
                style={{ ...primaryButton, marginTop: 40 }}>
                {loading ? 'Signing in…' : (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12 }}>
                    Sign In <RightOutlined style={{ fontSize: 12 }} />
                  </span>
                )}
              </Button>
            </Form>
          )}
          <div style={{ marginBottom: 'auto' }} />

          {/* Trust row + footer */}
          <div style={{ paddingTop: 48 }}>
            <div style={{ borderTop: `1px solid ${C.line}`, paddingTop: 24,
              display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: '10px 32px' }}>
              {[
                { icon: <LockOutlined />,        label: 'TLS Encrypted'  },
                { icon: <CheckCircleOutlined />, label: 'Secure Session' },
                { icon: <SafetyOutlined />,      label: 'Audit Logged'   },
              ].map((t) => (
                <span key={t.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: C.muted, fontSize: 14 }}>
                  <span style={{ color: C.green }}>{t.icon}</span>{t.label}
                </span>
              ))}
            </div>
            <div style={{ textAlign: 'center', marginTop: 18, color: '#9ca3af', fontSize: 13 }}>
              © {year} Apex POB · All rights reserved
            </div>
            <div style={{ textAlign: 'center', marginTop: 4, color: '#cbd5e1', fontSize: 12 }}>
              Apex POB v2.0 · Deployed for Marconi.ng EPC Limited
            </div>
          </div>
        </div>
      </div>

      {/* ─── Global keyframes ─────────────────────────────── */}
      <style>{`
        @keyframes orbFloat {
          0%,100% { transform: translateY(0px) scale(1); }
          33%      { transform: translateY(-28px) scale(1.04); }
          66%      { transform: translateY(14px) scale(0.97); }
        }
        @keyframes pulse {
          0%,100% { opacity: 1; transform: scale(1); }
          50%      { opacity: 0.5; transform: scale(1.3); }
        }

        .apx-login .apx-input.ant-input-affix-wrapper {
          height: 60px; padding: 0 20px; border-radius: 14px;
          border: 1.5px solid #e5e7eb; background: #ffffff; font-size: 17px; box-shadow: none;
        }
        .apx-login .apx-input .ant-input { font-size: 17px; background: transparent; }
        .apx-login .apx-input .ant-input::placeholder { color: #111827; opacity: .8; }
        .apx-login .apx-input.ant-input-affix-wrapper-focused,
        .apx-login .apx-input.ant-input-affix-wrapper:hover {
          border-color: #3b74e8; box-shadow: 0 0 0 4px rgba(59,116,232,0.12);
        }
        .apx-login .apx-icon { color: #9ca3af; font-size: 18px; margin-right: 12px; }
        /* eye button in its own segment, as in the design */
        .apx-login .apx-password .ant-input-suffix {
          margin-right: -20px; height: 100%; padding: 0 24px;
          border-left: 1.5px solid #e5e7eb; display: flex; align-items: center;
        }
        .apx-login .apx-password .ant-input-suffix .anticon { font-size: 20px; color: #6b7280; }
        .apx-login .ant-btn-primary:not(:disabled):hover { filter: brightness(1.05); }

        /* Responsive: stack on small screens */
        @media (max-width: 820px) {
          div[style*="flex: 0 0 52%"] {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
};

export default Login;
