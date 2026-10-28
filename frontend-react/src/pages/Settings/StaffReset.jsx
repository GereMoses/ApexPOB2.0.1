/**
 * Settings → HR Integration → Danger zone (global administrator only).
 * Remove every staff record and pull them back from SeamlessHR.
 * Server: /api/v1/hr-integration/staff-reset (preview · start · progress).
 */
import React, { useEffect, useState } from 'react';
import { Alert, App, Button, Card, Checkbox, Input, Modal, Radio, Space, Spin, Steps, Tag } from 'antd';
import { DeleteOutlined, ReloadOutlined, WarningOutlined } from '@ant-design/icons';
import apiService from '../../services/api';

const STEP_LABEL = {
  readers_cleared: 'Taken off the readers', backup: 'Backup made', deleted: 'Staff removed', pulled: 'Pulled from SeamlessHR',
  restored: 'Cards, IDs and on-board status put back', leave: 'Leave refreshed', attendance_ids: 'Attendance IDs set',
  readers: 'Readers updated', pull_failed: 'Pull from SeamlessHR failed', leave_failed: 'Leave refresh failed',
};

export default function StaffReset() {
  const { message } = App.useApp();
  const me = (() => { try { return JSON.parse(localStorage.getItem('user_info') || '{}'); } catch { return {}; } })();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState('keep_history');
  const [repopulate, setRepopulate] = useState(true);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [confirm, setConfirm] = useState('');
  const [starting, setStarting] = useState(false);
  const [job, setJob] = useState(null);

  const loadPreview = async () => {
    setLoading(true);
    try { setPreview(await apiService.get('/api/v1/hr-integration/staff-reset/preview', { mode, repopulate })); }
    catch (e) { message.error(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { if (open) loadPreview(); }, [open, mode, repopulate]); // eslint-disable-line

  // follow a running job
  useEffect(() => {
    if (!job?.id || ['done', 'failed'].includes(job.state)) return undefined;
    const t = setInterval(async () => {
      try { setJob((await apiService.get(`/api/v1/hr-integration/staff-reset/${job.id}`)).data); } catch { /* keep polling */ }
    }, 3000);
    return () => clearInterval(t);
  }, [job]);

  if (!me?.is_global_admin) return null;

  const start = async () => {
    setStarting(true);
    try {
      const r = await apiService.post('/api/v1/hr-integration/staff-reset', { mode, repopulate, confirm });
      setJob({ id: r.job_id, state: 'queued', steps: [] });
      setConfirm('');
      message.info(r.message, 6);
    } catch (e) { message.error(e.message, 8); }
    finally { setStarting(false); }
  };

  const c = preview?.counts || {};
  const phrase = preview?.confirm_phrase || 'DELETE ALL STAFF';
  const problems = preview?.preflight?.problems || [];
  const steps = (job?.steps || []);

  return (
    <Card size="small" style={{ borderColor: '#fecaca', marginTop: 16 }}
      title={<Space><WarningOutlined style={{ color: '#dc2626' }} /><span style={{ color: '#b91c1c' }}>Danger zone — global administrator</span></Space>}>
      <div style={{ fontSize: 12.5, color: '#64748b', marginBottom: 10 }}>
        Remove every staff record from ApexPOB and pull them back from SeamlessHR — e.g. to clear bad data, or to switch from the
        sandbox to Marconi's live SeamlessHR.
      </div>
      <Button danger icon={<DeleteOutlined />} onClick={() => setOpen(true)}>Remove all staff…</Button>

      <Modal open={open} onCancel={() => setOpen(false)} width={640} footer={null}
        title={<Space><WarningOutlined style={{ color: '#dc2626' }} />Remove all staff</Space>}>
        {job ? (
          <div>
            <div style={{ marginBottom: 12 }}>
              Run #{job.id} — <Tag color={{ done: 'green', failed: 'red' }[job.state] || 'blue'}>{job.state}</Tag>
              {!['done', 'failed'].includes(job.state) && <Spin size="small" style={{ marginLeft: 8 }} />}
            </div>
            <Steps direction="vertical" size="small" current={steps.length}
              items={steps.map(s => ({
                title: STEP_LABEL[s.step] || s.step,
                status: s.step.endsWith('failed') ? 'error' : 'finish',
                description: <span style={{ fontSize: 12 }}>
                  {s.schema && `Backup: ${s.schema}`}{s.rows && `${Object.values(s.rows).reduce((a, b) => a + b, 0)} rows`}
                  {s.total != null && `${s.total} staff`}{s.people != null && `${s.people} people`}
                  {s.updated != null && s.rule && `${s.updated ?? 0} set (${s.rule})`}{s.error && <span style={{ color: '#b45309' }}> {s.error}</span>}
                </span>,
              }))} />
            {job.state === 'done' && job.result && (
              <Alert type="success" showIcon message="Done"
                description={`${job.result.active} staff · ${job.result.with_attendance_id} with an Attendance ID · ${job.result.with_card} with a card`} />
            )}
            {job.state === 'failed' && <Alert type="error" showIcon message="Stopped" description={job.error} />}
            {['done', 'failed'].includes(job.state) && <Button style={{ marginTop: 12 }} onClick={() => { setJob(null); setOpen(false); }}>Close</Button>}
          </div>
        ) : (
          <div>
            <Radio.Group value={mode} onChange={e => setMode(e.target.value)} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <Radio value="keep_history">
                <b>Remove staff, keep history</b> <Tag color="green">recommended</Tag>
                <div style={{ fontSize: 12.5, color: '#64748b', marginLeft: 24 }}>
                  Attendance history is kept and re-attaches when the same employee codes come back. Cards, Attendance IDs, door PINs
                  and who is on board are put back. Readers are not touched.
                </div>
              </Radio>
              <Radio value="everything">
                <b>Remove everything — clean start</b>
                <div style={{ fontSize: 12.5, color: '#64748b', marginLeft: 24 }}>
                  Also deletes all attendance history, punches, leave and overtime, and takes everyone off the door panels and T&amp;A
                  terminals (fingerprints/faces stored on terminals are deleted too). For switching to a different SeamlessHR tenant.
                </div>
              </Radio>
            </Radio.Group>
            <Checkbox checked={repopulate} onChange={e => setRepopulate(e.target.checked)} style={{ marginTop: 12 }}>
              Pull staff back from SeamlessHR straight away
            </Checkbox>

            <div style={{ margin: '14px 0', padding: '10px 12px', background: '#f8fafc', borderRadius: 10, fontSize: 13 }}>
              {loading ? <Spin size="small" /> : (
                <>
                  Will remove <b>{c.staff ?? '—'}</b> staff ({c.with_card ?? 0} with a card, {c.with_attendance_id ?? 0} with an Attendance ID,
                  {' '}{c.on_board ?? 0} on board){mode === 'everything' ? <> and <b>{c.daily_attendance_rows ?? 0}</b> days of attendance, <b>{c.punches ?? 0}</b> punches</> : ''}.
                  A backup of every affected table is made first.
                  <Button size="small" type="link" icon={<ReloadOutlined />} onClick={loadPreview}>check again</Button>
                </>
              )}
            </div>
            {problems.length > 0 && <Alert type="error" showIcon style={{ marginBottom: 12 }} message="Can't run right now" description={problems.join(' ')} />}

            <div style={{ fontSize: 13, marginBottom: 6 }}>Type <b>{phrase}</b> to confirm:</div>
            <Input value={confirm} onChange={e => setConfirm(e.target.value)} placeholder={phrase} />
            <Space style={{ marginTop: 14 }}>
              <Button danger type="primary" icon={<DeleteOutlined />} loading={starting}
                disabled={confirm.trim().toUpperCase() !== phrase || problems.length > 0 || loading}
                onClick={start}>Remove all staff{repopulate ? ' and pull back' : ''}</Button>
              <Button onClick={() => setOpen(false)}>Cancel</Button>
            </Space>
          </div>
        )}
      </Modal>
    </Card>
  );
}
