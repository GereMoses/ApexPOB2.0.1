import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Card, Table, Button, Space, Tag, Modal, Form, Input, InputNumber, Select, Dropdown,
  Popconfirm, Row, Col, Tabs, Progress, Segmented,
  Drawer, Descriptions, Alert, Empty, Spin, App, Tooltip, Divider, Badge, DatePicker, Switch,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined,
  EnvironmentOutlined, TeamOutlined, WifiOutlined,
  EyeOutlined, ApiOutlined, ClockCircleOutlined, GlobalOutlined,
  LoginOutlined, LogoutOutlined, CheckCircleOutlined,
  RadarChartOutlined, CompassOutlined, AlertOutlined,
  SafetyOutlined, LockOutlined, HomeOutlined,
  SwapOutlined, DesktopOutlined, SearchOutlined,
  ThunderboltOutlined, DashboardOutlined,
  CopyOutlined, InfoCircleOutlined, SendOutlined, PoweroffOutlined,
  SyncOutlined, UnlockOutlined, SettingOutlined, LinkOutlined,
  CheckOutlined, CloseOutlined, DownOutlined, DownloadOutlined,
  ExclamationCircleOutlined, LeftOutlined, RightOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService from '../../services/api';
import ZoneMapView from './ZoneMapView';
import POBDashboard from './POBDashboard';

/* ── Constants ─────────────────────────────────────────────────────────────── */

const ZONE_TYPE_LABELS = {
  LOCATION: 'Location', MUSTER_POINT: 'Muster Point', WORK_AREA: 'Work Area',
  OUTSIDE: 'Outside Area', TRANSIT: 'In Transit', RESTRICTED: 'Restricted',
  PUBLIC: 'Public', SAFE_HAVEN: 'Safe Haven', ACCOMMODATION: 'Accommodation',
  HELIPAD: 'Helipad', CONTROL_ROOM: 'Control Room', STORAGE: 'Storage',
  EMERGENCY: 'Emergency',
};

const ZONE_STYLE = {
  LOCATION:     { color: '#10B981', dark: '#059669', bg: '#ECFDF5', icon: <EnvironmentOutlined /> },
  MUSTER_POINT: { color: '#10B981', dark: '#059669', bg: '#ECFDF5', icon: <SafetyOutlined /> },
  WORK_AREA:    { color: '#EF4444', dark: '#DC2626', bg: '#FEF2F2', icon: <DesktopOutlined /> },
  OUTSIDE:      { color: '#6B7280', dark: '#4B5563', bg: '#F9FAFB', icon: <GlobalOutlined /> },
  TRANSIT:      { color: '#0EA5E9', dark: '#0284C7', bg: '#F0F9FF', icon: <SwapOutlined /> },
  RESTRICTED:   { color: '#7C3AED', dark: '#6D28D9', bg: '#F5F3FF', icon: <LockOutlined /> },
  PUBLIC:       { color: '#10B981', dark: '#059669', bg: '#ECFDF5', icon: <GlobalOutlined /> },
  SAFE_HAVEN:   { color: '#0078D4', dark: '#005A9E', bg: '#EFF6FF', icon: <SafetyOutlined /> },
  ACCOMMODATION:{ color: '#8B5CF6', dark: '#7C3AED', bg: '#F5F3FF', icon: <HomeOutlined /> },
  HELIPAD:      { color: '#0078D4', dark: '#005A9E', bg: '#EFF6FF', icon: <CompassOutlined /> },
  CONTROL_ROOM: { color: '#F59E0B', dark: '#D97706', bg: '#FFFBEB', icon: <ThunderboltOutlined /> },
  STORAGE:      { color: '#92400E', dark: '#78350F', bg: '#FEF3C7', icon: <RadarChartOutlined /> },
  EMERGENCY:    { color: '#EF4444', dark: '#DC2626', bg: '#FEF2F2', icon: <AlertOutlined /> },
};

const HAZARD_STYLE = {
  LOW:      { color: '#10B981', bg: '#ECFDF5', border: '#6EE7B7' },
  MEDIUM:   { color: '#F59E0B', bg: '#FFFBEB', border: '#FCD34D' },
  HIGH:     { color: '#EF4444', bg: '#FEF2F2', border: '#FCA5A5' },
  CRITICAL: { color: '#991B1B', bg: '#FEE2E2', border: '#FCA5A5' },
};

const STATUS_STYLE = {
  ACTIVE:      { color: '#10B981', bg: '#ECFDF5', border: '#6EE7B7', pulse: true },
  INACTIVE:    { color: '#6B7280', bg: '#F3F4F6', border: '#D1D5DB', pulse: false },
  MAINTENANCE: { color: '#F59E0B', bg: '#FFFBEB', border: '#FCD34D', pulse: true },
  EMERGENCY:   { color: '#EF4444', bg: '#FEF2F2', border: '#FCA5A5', pulse: true },
  LOCKDOWN:    { color: '#7C3AED', bg: '#F5F3FF', border: '#C4B5FD', pulse: true },
};

const PRESET_COLORS = [
  { label: 'Green — Muster / Location', value: '#52c41a' },
  { label: 'Red — Work Area / Emergency', value: '#f5222d' },
  { label: 'Dark Gray — Outside', value: '#595959' },
  { label: 'Teal — In Transit', value: '#13c2c2' },
  { label: 'Dark Maroon — Restricted', value: '#6B1E35' },
  { label: 'Blue — Safe Haven / Helipad', value: '#0078D4' },
  { label: 'Pink — Muster Total', value: '#eb2f96' },
  { label: 'Brown — Storage', value: '#8B4513' },
  { label: 'Orange — Warning', value: '#fa8c16' },
  { label: 'Purple — Accommodation', value: '#531dab' },
];

/* ── Helpers ───────────────────────────────────────────────────────────────── */

const fmtTime = (iso) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-NG', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
};

const timeAgo = (iso) => {
  if (!iso) return null;
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};

// What feeds a zone: access-control readers + ZKTeco controller doors (T&A terminals
// are not part of zones).
const zoneReaders = (z) => (z?.access_reader_count ?? 0) + (z?.door_count ?? 0);
const zoneReadersLabel = (z) => {
  const r = z?.access_reader_count ?? 0, d = z?.door_count ?? 0;
  if (!r && !d) return 'No doors or readers';
  return [d && `${d} door${d !== 1 ? 's' : ''}`, r && `${r} reader${r !== 1 ? 's' : ''}`].filter(Boolean).join(' · ');
};

const getZoneStyle = (type) => ZONE_STYLE[type] || { color: '#6B7280', dark: '#4B5563', bg: '#F9FAFB', icon: <GlobalOutlined /> };
const getStatusStyle = (s) => STATUS_STYLE[s] || STATUS_STYLE.INACTIVE;
const getHazardStyle = (h) => HAZARD_STYLE[h] || HAZARD_STYLE.LOW;

/* ── ZoneCard ──────────────────────────────────────────────────────────────── */

const ZoneCard = ({ zone, onView, onEdit, onAssignReader, onDelete, onStatusChange, onResetOccupancy }) => {
  const zs = getZoneStyle(zone.zone_type);
  const ss = getStatusStyle(zone.status);
  const hs = getHazardStyle(zone.hazard_level);
  const count = zone.current_personnel_count ?? 0;
  const pct = zone.max_capacity ? Math.min(100, Math.round((count / zone.max_capacity) * 100)) : null;
  const capColor = pct >= 90 ? '#EF4444' : pct >= 70 ? '#F59E0B' : '#10B981';

  return (
    <div style={{
      background: 'white',
      borderRadius: 14,
      border: '1px solid #E5E7EB',
      overflow: 'hidden',
      transition: 'all 0.2s ease',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      boxShadow: '0 1px 6px rgba(0,0,0,0.06)',
    }}
      onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 8px 28px rgba(0,0,0,0.12)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
      onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 1px 6px rgba(0,0,0,0.06)'; e.currentTarget.style.transform = 'translateY(0)'; }}
    >
      {/* Type color bar */}
      <div style={{ height: 4, background: `linear-gradient(90deg, ${zs.dark}, ${zs.color})` }} />

      {/* Card body */}
      <div style={{ padding: '14px 16px', flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>

        {/* Header row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 14.5, color: '#111827', lineHeight: 1.25, marginBottom: 2 }}>
              {zone.name}
            </div>
            <span style={{ fontSize: 10.5, color: '#9CA3AF', fontFamily: 'monospace', letterSpacing: '0.02em' }}>
              {zone.code}
            </span>
          </div>
          {/* Status pill — click to change */}
          {onStatusChange ? (
            <Dropdown
              trigger={['click']}
              placement="bottomRight"
              menu={{
                selectedKeys: [zone.status],
                items: ['ACTIVE','INACTIVE','MAINTENANCE','EMERGENCY','LOCKDOWN'].map(s => {
                  const ss2 = getStatusStyle(s);
                  return {
                    key: s,
                    label: (
                      <div style={{ display:'flex',alignItems:'center',gap:8,padding:'2px 0' }}>
                        <div style={{ width:8,height:8,borderRadius:'50%',background:ss2.color,flexShrink:0 }} />
                        <span style={{color:ss2.color,fontWeight:600,fontSize:12}}>{s.charAt(0)+s.slice(1).toLowerCase()}</span>
                      </div>
                    ),
                    onClick: () => onStatusChange(zone.id, s),
                  };
                }),
              }}
            >
              <div style={{
                display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0,
                background: ss.bg, border: `1px solid ${ss.border}`,
                borderRadius: 20, padding: '3px 9px', cursor: 'pointer',
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%', background: ss.color,
                  animation: ss.pulse ? 'zoneDotPulse 2s infinite' : 'none',
                }} />
                <span style={{ fontSize: 10.5, fontWeight: 600, color: ss.color }}>{zone.status}</span>
                <DownOutlined style={{ fontSize: 7, color: ss.color, opacity: 0.6 }} />
              </div>
            </Dropdown>
          ) : (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0,
              background: ss.bg, border: `1px solid ${ss.border}`,
              borderRadius: 20, padding: '3px 9px',
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%', background: ss.color,
                animation: ss.pulse ? 'zoneDotPulse 2s infinite' : 'none',
              }} />
              <span style={{ fontSize: 10.5, fontWeight: 600, color: ss.color }}>{zone.status}</span>
            </div>
          )}
        </div>

        {/* Type + Hazard tags */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            background: zs.bg, borderRadius: 6, padding: '3px 8px',
            border: `1px solid ${zs.color}30`,
          }}>
            <span style={{ color: zs.color, fontSize: 11 }}>{zs.icon}</span>
            <span style={{ color: zs.color, fontSize: 11, fontWeight: 600 }}>
              {ZONE_TYPE_LABELS[zone.zone_type] || zone.zone_type}
            </span>
          </div>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            background: hs.bg, borderRadius: 6, padding: '3px 8px',
            border: `1px solid ${hs.border}`,
          }}>
            <span style={{ fontSize: 10.5, fontWeight: 600, color: hs.color }}>
              {zone.hazard_level} HAZARD
            </span>
          </div>
        </div>

        {/* Personnel count */}
        <div style={{
          borderRadius: 10, padding: '14px 16px', textAlign: 'center',
          background: `linear-gradient(135deg, ${zs.dark} 0%, ${zs.color} 100%)`,
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', top: -12, right: -12, width: 60, height: 60,
            borderRadius: '50%', background: 'rgba(255,255,255,0.08)',
          }} />
          {/* Reset occupancy button — only when count > 0 */}
          {count > 0 && onResetOccupancy && (
            <Tooltip title="Force-reset occupancy to 0 (clears stale check-ins)">
              <Popconfirm
                title="Reset zone occupancy?"
                description={`This will force-checkout all ${count} personnel currently counted in this zone and reset the count to 0. Use this to clear stale/phantom records.`}
                onConfirm={e => { e.stopPropagation(); onResetOccupancy(zone.id); }}
                onCancel={e => e.stopPropagation()}
                okText="Reset" okButtonProps={{ danger: true }} cancelText="Cancel"
              >
                <button
                  onClick={e => e.stopPropagation()}
                  style={{
                    position: 'absolute', top: 6, right: 6, zIndex: 2,
                    all: 'unset', cursor: 'pointer',
                    background: 'rgba(255,255,255,0.18)', borderRadius: 6,
                    padding: '3px 5px', display: 'flex', alignItems: 'center', gap: 4,
                    fontSize: 10, color: 'rgba(255,255,255,0.9)', fontWeight: 600,
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.32)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.18)'}
                >
                  <SyncOutlined style={{ fontSize: 9 }} /> Reset
                </button>
              </Popconfirm>
            </Tooltip>
          )}
          <div style={{ fontSize: 44, fontWeight: 900, color: 'white', lineHeight: 1, letterSpacing: -2, position: 'relative' }}>
            {count}
          </div>
          <div style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.82)', fontWeight: 600, letterSpacing: '0.08em', marginTop: 3, position: 'relative' }}>
            PERSONNEL ON BOARD
          </div>
        </div>

        {/* Capacity */}
        {zone.max_capacity ? (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, color: '#6B7280', marginBottom: 5 }}>
              <span>Capacity</span>
              <span style={{ fontWeight: 600, color: capColor }}>{count} / {zone.max_capacity} ({pct}%)</span>
            </div>
            <div style={{ height: 5, background: '#F3F4F6', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                height: '100%', width: `${pct}%`,
                background: `linear-gradient(90deg, ${capColor}aa, ${capColor})`,
                borderRadius: 3, transition: 'width 0.5s ease',
              }} />
            </div>
          </div>
        ) : null}

        {/* Meta row */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 'auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#6B7280' }}>
              <ApiOutlined style={{ color: '#7C3AED', fontSize: 13 }} />
              <span>{zoneReadersLabel(zone)}</span>
            </div>
            {zone.state && (
              <span style={{ fontSize: 11, color: '#9CA3AF' }}>{zone.state}</span>
            )}
          </div>

          {zone.latitude && zone.longitude ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: '#6B7280' }}>
              <EnvironmentOutlined style={{ color: '#EF4444', fontSize: 12 }} />
              <span>{parseFloat(zone.latitude).toFixed(4)}°N, {parseFloat(zone.longitude).toFixed(4)}°E</span>
              <a
                href={`https://www.openstreetmap.org/?mlat=${zone.latitude}&mlon=${zone.longitude}#map=14/${zone.latitude}/${zone.longitude}`}
                target="_blank" rel="noopener noreferrer"
                style={{ color: '#0078D4', fontSize: 11, marginLeft: 2 }}
              >↗</a>
            </div>
          ) : (
            <div style={{ fontSize: 11.5, color: '#D1D5DB', display: 'flex', alignItems: 'center', gap: 5 }}>
              <EnvironmentOutlined style={{ fontSize: 12 }} />
              <span>No GPS coordinates</span>
            </div>
          )}

          {zone.last_activity_time && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: '#6B7280' }}>
              <ClockCircleOutlined style={{ color: '#0EA5E9', fontSize: 12 }} />
              <span>Last activity {timeAgo(zone.last_activity_time)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Actions footer */}
      <div style={{
        borderTop: '1px solid #F3F4F6',
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
      }}>
        {[
          { icon: <EyeOutlined />, label: 'Detail', color: '#0078D4', onClick: () => onView(zone) },
          { icon: <EditOutlined />, label: 'Edit', color: '#10B981', onClick: () => onEdit(zone) },
          { icon: <ApiOutlined />, label: 'Doors', color: '#7C3AED', onClick: () => onAssignReader(zone) },
        ].map(btn => (
          <button key={btn.label} onClick={btn.onClick} style={{
            all: 'unset', textAlign: 'center', padding: '9px 4px',
            fontSize: 11, color: btn.color, fontWeight: 500, cursor: 'pointer',
            borderRight: '1px solid #F3F4F6', transition: 'background 0.15s',
          }}
            onMouseEnter={e => e.currentTarget.style.background = '#F9FAFB'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <div style={{ fontSize: 14, marginBottom: 2 }}>{btn.icon}</div>
            {btn.label}
          </button>
        ))}
        <Popconfirm
          title="Delete zone?"
          description="This permanently removes the zone and unassigns all readers."
          onConfirm={() => onDelete(zone.id)}
          okText="Delete" okButtonProps={{ danger: true }} cancelText="Cancel"
        >
          <button style={{
            all: 'unset', textAlign: 'center', padding: '9px 4px',
            fontSize: 11, color: '#EF4444', fontWeight: 500, cursor: 'pointer',
            transition: 'background 0.15s',
          }}
            onMouseEnter={e => e.currentTarget.style.background = '#FEF2F2'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <div style={{ fontSize: 14, marginBottom: 2 }}><DeleteOutlined /></div>
            Delete
          </button>
        </Popconfirm>
      </div>
    </div>
  );
};

/* ── Zone Detail Drawer ────────────────────────────────────────────────────── */

const ZoneDetailDrawer = ({ zone, open, onClose, onPrev, onNext, hasPrev, hasNext }) => {
  const [drawerTab, setDrawerTab] = useState('personnel');
  const [reassignReader, setReassignReader] = useState(null); // {reader_id, alias, sn}
  const [reassignZoneId, setReassignZoneId] = useState(null);
  const { message } = App.useApp();
  const qc = useQueryClient();

  const removeReaderMutation = useMutation({
    mutationFn: ({ zoneId, readerId }) =>
      apiService.delete(`/api/v1/zones/${zoneId}/readers/${readerId}`),
    onSuccess: () => {
      message.success('Reader removed from zone');
      qc.invalidateQueries({ queryKey: ['zone-readers', zone?.id] });
      qc.invalidateQueries({ queryKey: ['zones-dashboard'] });
    },
    onError: (err) => message.error(err?.message || 'Failed to remove reader'),
  });

  const reassignMutation = useMutation({
    mutationFn: ({ newZoneId, deviceId }) =>
      apiService.post(`/api/v1/zones/${newZoneId}/assign-reader`, { device_id: deviceId }),
    onSuccess: (res) => {
      message.success(res?.moved_from ? 'Reader moved to zone' : 'Reader assigned to zone');
      setReassignReader(null); setReassignZoneId(null);
      qc.invalidateQueries({ queryKey: ['zone-readers', zone?.id] });
      if (res?.zone_id) qc.invalidateQueries({ queryKey: ['zone-readers', res.zone_id] });
      qc.invalidateQueries({ queryKey: ['zones-dashboard'] });
      qc.invalidateQueries({ queryKey: ['adms-terminals'] });
      qc.invalidateQueries({ queryKey: ['available-devices'] });
    },
    onError: (err) => message.error(err?.message || 'Failed to reassign reader'),
  });

  const { data: allZones } = useQuery({
    queryKey: ['zones-list-simple'],
    queryFn: () => apiService.get('/api/v1/zones/dashboard'),
    enabled: !!reassignReader,
    select: (d) => (Array.isArray(d) ? d : []).filter(z => z.id !== zone?.id),
  });

  const { data: personnel, isLoading: pLoading } = useQuery({
    queryKey: ['zone-personnel', zone?.id],
    queryFn: () => apiService.get(`/api/v1/zones/${zone.id}/current-personnel`),
    enabled: !!zone && open, refetchInterval: 10000,
  });
  const { data: tracking, isLoading: tLoading } = useQuery({
    queryKey: ['zone-tracking', zone?.id],
    queryFn: () => apiService.get(`/api/v1/zones/${zone.id}/tracking?limit=100`),
    enabled: !!zone && open, refetchInterval: 15000,
  });
  const { data: readers, isLoading: rLoading } = useQuery({
    queryKey: ['zone-readers', zone?.id],
    queryFn: () => apiService.get(`/api/v1/zones/${zone.id}/readers`),
    enabled: !!zone && open,
  });
  const { data: zoneDoors } = useQuery({
    queryKey: ['zone-doors', zone?.id],
    queryFn: () => apiService.get(`/api/v1/zones/${zone.id}/doors`),
    enabled: !!zone && open,
  });

  if (!zone) return null;

  const zs = getZoneStyle(zone.zone_type);
  const ss = getStatusStyle(zone.status);
  const hs = getHazardStyle(zone.hazard_level);
  const personnelList = Array.isArray(personnel) ? personnel : [];
  const trackingList  = Array.isArray(tracking)  ? tracking  : [];
  // T&A terminals are not part of zones — list only access / mustering readers.
  const readerList    = (Array.isArray(readers) ? readers : []).filter(r => (r.reader_purpose || 'ATTENDANCE') !== 'ATTENDANCE');
  const doorList      = Array.isArray(zoneDoors) ? zoneDoors : [];
  const count = zone.current_personnel_count ?? 0;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={660}
      styles={{ header: { padding: 0, border: 'none' }, body: { padding: 0 } }}
      title={
        <div style={{
          background: `linear-gradient(135deg, ${zs.dark} 0%, ${zs.color} 100%)`,
          padding: '20px 24px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 48, height: 48, borderRadius: 12,
              background: 'rgba(255,255,255,0.18)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 22, color: 'white',
            }}>{zs.icon}</div>
            <div>
              <div style={{ color: 'white', fontWeight: 700, fontSize: 18, lineHeight: 1.2 }}>{zone.name}</div>
              <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12, marginTop: 3, fontFamily: 'monospace' }}>
                {zone.code} · {ZONE_TYPE_LABELS[zone.zone_type] || zone.zone_type}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={onPrev} disabled={!hasPrev}
              style={{
                all: 'unset', cursor: hasPrev ? 'pointer' : 'not-allowed',
                width: 30, height: 30, borderRadius: 8,
                background: hasPrev ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: hasPrev ? 'white' : 'rgba(255,255,255,0.25)', fontSize: 12,
                transition: 'background 0.15s',
              }}
              title="Previous zone"
            ><LeftOutlined /></button>

            <div style={{
              background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(4px)',
              borderRadius: 12, padding: '10px 18px', textAlign: 'center',
              border: '1px solid rgba(255,255,255,0.25)',
            }}>
              <div style={{ fontSize: 36, fontWeight: 900, color: 'white', lineHeight: 1 }}>{count}</div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.8)', fontWeight: 600, letterSpacing: '0.06em', marginTop: 2 }}>ON BOARD</div>
            </div>

            <button
              onClick={onNext} disabled={!hasNext}
              style={{
                all: 'unset', cursor: hasNext ? 'pointer' : 'not-allowed',
                width: 30, height: 30, borderRadius: 8,
                background: hasNext ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: hasNext ? 'white' : 'rgba(255,255,255,0.25)', fontSize: 12,
                transition: 'background 0.15s',
              }}
              title="Next zone"
            ><RightOutlined /></button>
          </div>
        </div>
      }
    >
      {/* Meta strip */}
      <div style={{ padding: '14px 24px', background: '#FAFAFA', borderBottom: '1px solid #F0F0F0' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {[
            { label: 'Status', value: (
              <div style={{ display:'flex', alignItems:'center', gap:5 }}>
                <div style={{ width:7,height:7,borderRadius:'50%',background:ss.color, animation: ss.pulse ? 'zoneDotPulse 2s infinite' : 'none' }} />
                <span style={{ color:ss.color, fontWeight:600, fontSize:12 }}>{zone.status}</span>
              </div>
            )},
            { label: 'Hazard', value: <span style={{ color:hs.color, fontWeight:600, fontSize:12 }}>{zone.hazard_level}</span> },
            { label: 'Access', value: zone.access_level },
            { label: 'State',  value: zone.state || '—' },
            { label: 'Capacity', value: zone.max_capacity ? `${count} / ${zone.max_capacity}` : '—' },
            { label: 'Doors & readers', value: zoneReadersLabel({ door_count: doorList.length, access_reader_count: readerList.length }) },
          ].map(item => (
            <div key={item.label} style={{
              background: 'white', border: '1px solid #E5E7EB', borderRadius: 8,
              padding: '6px 12px', minWidth: 90,
            }}>
              <div style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 500, marginBottom: 2 }}>{item.label}</div>
              <div style={{ fontSize: 12.5, color: '#1F2937', fontWeight: 500 }}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ padding: '0 24px' }}>
        <Tabs
          size="small"
          activeKey={drawerTab}
          onChange={setDrawerTab}
          style={{ marginTop: 4 }}
          items={[
            {
              key: 'personnel',
              label: <Space size={4}><TeamOutlined />Now ({personnelList.length})</Space>,
              children: (
                <Spin spinning={pLoading}>
                  {personnelList.length === 0 ? (
                    <Empty description="No personnel currently on board" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ padding: '32px 0' }} />
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingBottom: 16 }}>
                      {personnelList.map((p) => (
                        <div key={p.emp_code} style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          padding: '10px 14px', background: '#F6FFF8', borderRadius: 8,
                          border: '1px solid #D1FAE5',
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <div style={{
                              width: 34, height: 34, borderRadius: 8,
                              background: 'linear-gradient(135deg, #059669, #10B981)',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              color: 'white', fontSize: 13, fontWeight: 700, flexShrink: 0,
                            }}>
                              {(p.full_name?.[0] || p.emp_code?.[0] || 'P').toUpperCase()}
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, fontSize: 13, color: '#111827' }}>{p.full_name}</div>
                              <div style={{ fontSize: 11, color: '#9CA3AF', fontFamily: 'monospace' }}>{p.emp_code}</div>
                              {p.department && (
                                <div style={{ fontSize: 10, color: '#6B7280', marginTop: 1 }}>{p.department}</div>
                              )}
                            </div>
                          </div>
                          <div style={{ textAlign: 'right', fontSize: 11 }}>
                            <div style={{ color: '#10B981', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
                              <LoginOutlined />
                              {timeAgo(p.punch_time)}
                            </div>
                            <div style={{ color: '#9CA3AF', marginTop: 2 }}>{fmtTime(p.punch_time)}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Spin>
              ),
            },
            {
              key: 'activity',
              label: <Space size={4}><ClockCircleOutlined />Activity</Space>,
              children: (
                <Spin spinning={tLoading}>
                  <Table
                    dataSource={trackingList}
                    rowKey={(_, i) => i}
                    size="small"
                    pagination={{ pageSize: 15, size: 'small' }}
                    style={{ marginTop: 4 }}
                    columns={[
                      {
                        title: 'Personnel', key: 'person',
                        render: (_, r) => (
                          <div>
                            <div style={{ fontWeight: 500, fontSize: 12 }}>{r.full_name}</div>
                            <div style={{ fontSize: 10, color: '#9CA3AF', fontFamily: 'monospace' }}>{r.emp_code}</div>
                          </div>
                        ),
                      },
                      {
                        title: 'Event', dataIndex: 'event_type', width: 80,
                        render: e => e === 'CLOCK_IN'
                          ? <span style={{ color:'#10B981', fontSize:11, fontWeight:600 }}>↑ IN</span>
                          : <span style={{ color:'#EF4444', fontSize:11, fontWeight:600 }}>↓ OUT</span>,
                      },
                      { title: 'Reader', dataIndex: 'device_sn', width: 110, render: s => <code style={{ fontSize: 10 }}>{s}</code> },
                      { title: 'Time', dataIndex: 'punch_time', width: 120, render: fmtTime },
                    ]}
                  />
                </Spin>
              ),
            },
            {
              key: 'readers',
              label: <Space size={4}><ApiOutlined />Doors & readers ({doorList.length + readerList.length})</Space>,
              children: (
                <Spin spinning={rLoading}>
                  {doorList.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
                      {doorList.map(d => (
                        <div key={`${d.controller_id}:${d.door_no}`} style={{ padding: '10px 14px', borderRadius: 10, background: '#F5F3FF', border: '1px solid #DDD6FE', display: 'flex', alignItems: 'center', gap: 10 }}>
                          <ApiOutlined style={{ color: '#7C3AED' }} />
                          <span style={{ fontWeight: 600 }}>Door {d.door_no}</span>
                          <span style={{ fontSize: 12, color: '#6B7280' }}>{d.controller_name}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {readerList.length === 0 ? (doorList.length === 0 &&
                    <Empty description="No doors or readers — assign controller doors with Doors on the zone card" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ padding: '32px 0' }} />
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingBottom: 16 }}>
                      {readerList.map((r) => (
                        <div key={r.reader_id} style={{
                          padding: '12px 14px', borderRadius: 10,
                          background: r.state === 1 ? '#F0FDF4' : '#F9FAFB',
                          border: `1px solid ${r.state === 1 ? '#BBF7D0' : '#E5E7EB'}`,
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <div style={{
                              width: 36, height: 36, borderRadius: 8,
                              background: r.state === 1
                                ? 'linear-gradient(135deg,#059669,#10B981)'
                                : 'linear-gradient(135deg,#6B7280,#9CA3AF)',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              color: 'white', fontSize: 16,
                            }}>
                              <WifiOutlined />
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
                                {r.alias}
                                {(() => {
                                  const p = r.reader_purpose || 'ATTENDANCE';
                                  const cfg = {
                                    ACCESS_ENTRY:  { color: '#10B981', bg: '#ECFDF5', border: '#A7F3D0', label: '▶ Entry'     },
                                    ACCESS_EXIT:   { color: '#EF4444', bg: '#FEF2F2', border: '#FECACA', label: '◀ Exit'      },
                                    ATTENDANCE:    { color: '#6B7280', bg: '#F9FAFB', border: '#E5E7EB', label: '⏱ T&A'       },
                                    MUSTERING:     { color: '#F59E0B', bg: '#FFFBEB', border: '#FDE68A', label: '🔔 Muster'   },
                                    POB:           { color: '#3B82F6', bg: '#EFF6FF', border: '#BFDBFE', label: '👤 POB'      },
                                    EMERGENCY:     { color: '#DC2626', bg: '#FEF2F2', border: '#FECACA', label: '🚨 Emergency' },
                                  }[p] || { color: '#6B7280', bg: '#F9FAFB', border: '#E5E7EB', label: p };
                                  return (
                                    <span style={{
                                      fontSize: 10, fontWeight: 700, padding: '1px 6px',
                                      borderRadius: 4, border: `1px solid ${cfg.border}`,
                                      background: cfg.bg, color: cfg.color,
                                    }}>{cfg.label}</span>
                                  );
                                })()}
                              </div>
                              <div style={{ fontSize: 11, color: '#9CA3AF', fontFamily: 'monospace' }}>
                                {r.sn}{r.ip_address ? ` · ${r.ip_address}` : ''}
                              </div>
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <div style={{ textAlign: 'right' }}>
                              <div style={{
                                fontSize: 11, fontWeight: 600,
                                color: r.state === 1 ? '#10B981' : '#9CA3AF',
                              }}>{r.state === 1 ? '● Online' : '○ Offline'}</div>
                              <div style={{ fontSize: 10, color: '#9CA3AF', marginTop: 2 }}>
                                {timeAgo(r.last_activity)}
                              </div>
                            </div>
                            <Button
                              size="small"
                              icon={<SwapOutlined />}
                              onClick={() => { setReassignReader(r); setReassignZoneId(null); }}
                              style={{ fontSize: 11 }}
                            >
                              Reassign
                            </Button>
                            <Popconfirm
                              title="Remove this reader from the zone?"
                              description="The reader will be unassigned and can be added to another zone."
                              okText="Remove"
                              okType="danger"
                              onConfirm={() => removeReaderMutation.mutate({ zoneId: zone.id, readerId: r.reader_id })}
                            >
                              <Button
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                loading={removeReaderMutation.isPending}
                                style={{ fontSize: 11 }}
                              >
                                Remove
                              </Button>
                            </Popconfirm>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Spin>
              ),
            },
            {
              key: 'info',
              label: <Space size={4}><InfoCircleOutlined />Info</Space>,
              children: (
                <div style={{ paddingBottom: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {[
                    { label: 'Description',     value: zone.description,    mono: false },
                    { label: 'Address',          value: zone.address,        mono: false },
                    { label: 'Safety Contact',   value: zone.contact_person, mono: false },
                    { label: 'Contact Phone',    value: zone.contact_phone,  mono: true  },
                    { label: 'Safety Level',     value: zone.safety_level,   mono: false },
                    { label: 'Parent Zone ID',   value: zone.parent_zone_id ? `#${zone.parent_zone_id}` : null, mono: true },
                    { label: 'ZKTeco Sync',      value: zone.zkteco_sync_enabled ? 'Enabled' : 'Disabled', mono: false },
                    { label: 'Last Sync',        value: zone.last_sync_at ? fmtTime(zone.last_sync_at) : null, mono: false },
                    { label: 'Created',          value: zone.created_at ? fmtTime(zone.created_at) : null, mono: false },
                    { label: 'Updated',          value: zone.updated_at ? fmtTime(zone.updated_at) : null, mono: false },
                  ].filter(row => row.value != null && row.value !== '').map(row => (
                    <div key={row.label} style={{
                      display: 'flex', gap: 10, alignItems: 'flex-start',
                      padding: '8px 14px', background: '#FAFAFA',
                      borderRadius: 8, border: '1px solid #F3F4F6',
                    }}>
                      <span style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 600, minWidth: 110, flexShrink: 0, paddingTop: 1 }}>{row.label}</span>
                      <span style={{
                        fontSize: 12.5, color: '#1F2937', fontWeight: 500,
                        fontFamily: row.mono ? 'monospace' : 'inherit',
                        wordBreak: 'break-all',
                      }}>{row.value}</span>
                    </div>
                  ))}
                  {zone.floor_plan_url && (
                    <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid #E5E7EB', marginTop: 4 }}>
                      <div style={{ padding: '6px 14px', background: '#F9FAFB', borderBottom: '1px solid #F3F4F6', fontSize: 11, color: '#9CA3AF', fontWeight: 600 }}>Location Image</div>
                      <img
                        src={zone.floor_plan_url} alt={zone.name}
                        style={{ width: '100%', maxHeight: 220, objectFit: 'cover', display: 'block' }}
                        onError={e => { e.target.style.display = 'none'; }}
                      />
                    </div>
                  )}
                </div>
              ),
            },
          ]}
        />
      </div>

      {/* Reassign reader modal */}
      <Modal
        open={!!reassignReader}
        title={`Reassign ${reassignReader?.alias || 'Reader'} to another zone`}
        okText="Move Reader"
        onOk={() => {
          if (!reassignZoneId) { message.warning('Select a target zone'); return; }
          reassignMutation.mutate({ newZoneId: reassignZoneId, deviceId: reassignReader.reader_id });
        }}
        confirmLoading={reassignMutation.isPending}
        onCancel={() => { setReassignReader(null); setReassignZoneId(null); }}
        width={440}
      >
        <p style={{ marginBottom: 12, color: '#6B7280', fontSize: 13 }}>
          Moving <strong>{reassignReader?.alias}</strong> ({reassignReader?.sn}) from <strong>{zone?.name}</strong> to:
        </p>
        <Select
          placeholder="Select target zone"
          style={{ width: '100%' }}
          value={reassignZoneId}
          onChange={setReassignZoneId}
          showSearch
          optionFilterProp="label"
        >
          {(allZones || []).map(z => (
            <Select.Option key={z.id} value={z.id} label={z.name}>
              {z.name}
            </Select.Option>
          ))}
        </Select>
      </Modal>
    </Drawer>
  );
};

/* ── ADMS Readers Tab ──────────────────────────────────────────────────────── */

const CMD_PRESETS = [
  { label: 'Open Door (5s)',    value: 'RELAY,0,5',     icon: <UnlockOutlined />, color: '#10B981' },
  { label: 'Open Door (10s)',   value: 'RELAY,0,10',    icon: <UnlockOutlined />, color: '#10B981' },
  { label: 'Restart Device',   value: 'REBOOT',         icon: <PoweroffOutlined />, color: '#EF4444' },
  { label: 'Sync Time',        value: 'SYNCTIME',       icon: <SyncOutlined />,   color: '#1D4ED8' },
  { label: 'Clear Attendance', value: 'CLEAR ATTLOG',   icon: <DeleteOutlined />, color: '#F59E0B' },
  { label: 'Lock Door (relay off)', value: 'RELAY,0,0',   icon: <LockOutlined />,  color: '#7C3AED' },
  { label: 'Emergency Unlock (5m)', value: 'RELAY,0,300', icon: <AlertOutlined />, color: '#EF4444' },
];

const OPER_EVENT_META = {
  0: { label: 'Door Normal',          color: '#10B981', bg: '#ECFDF5' },
  1: { label: 'Door Alarm',           color: '#EF4444', bg: '#FEF2F2' },
  2: { label: 'Tamper',               color: '#EF4444', bg: '#FEF2F2' },
  3: { label: 'Anti-Passback',        color: '#F59E0B', bg: '#FFFBEB' },
  4: { label: 'Duress',               color: '#7C3AED', bg: '#F5F3FF' },
  5: { label: 'Fire Unlock',          color: '#F97316', bg: '#FFF7ED' },
  6: { label: 'Emergency Lock',       color: '#EF4444', bg: '#FEF2F2' },
  8: { label: 'Door Open Too Long',   color: '#F59E0B', bg: '#FFFBEB' },
  200: { label: 'Admin Op',           color: '#1D4ED8', bg: '#EFF6FF' },
};

const ReadersTab = () => {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [search,          setSearch]          = useState('');
  const [activeSubTab,    setActiveSubTab]    = useState('readers');
  const [cmdModal,        setCmdModal]        = useState(null);
  const [cmdValue,        setCmdValue]        = useState('');
  const [customCmd,       setCustomCmd]       = useState('');
  const [addModal,        setAddModal]        = useState(false);
  const [addForm]                             = Form.useForm();
  const [copied,          setCopied]          = useState(false);
  const [editModal,       setEditModal]       = useState(null);
  const [editAlias,       setEditAlias]       = useState('');
  const [editIp,          setEditIp]          = useState('');
  const [capModal,        setCapModal]        = useState(null);  // device for capability panel
  const [pushUsersModal,  setPushUsersModal]  = useState(null);  // device for push users
  const [pushTplModal,    setPushTplModal]    = useState(null);  // device for push templates
  const [pushTzModal,     setPushTzModal]     = useState(null);  // device for push timezones
  const [pushAccModal,    setPushAccModal]    = useState(null);  // device for push access levels
  const [cmdHistModal,    setCmdHistModal]    = useState(null);  // device for command history
  const [operlogFilter,      setOperlogFilter]      = useState(null);  // event type filter
  const [operlogSnFilter,    setOperlogSnFilter]    = useState(null);  // device SN filter
  const [operlogRange,       setOperlogRange]       = useState(null);  // [dayjs, dayjs] date range
  const [pendingZoneAssign,  setPendingZoneAssign]  = useState(null);  // {deviceId, zoneId, currentZoneId}
  const [pushUsersForm]                       = Form.useForm();
  const [pushTzForm]                          = Form.useForm();
  const [pushAccForm]                         = Form.useForm();
  const [editingAddr,    setEditingAddr]    = useState(false);
  const [addrInput,      setAddrInput]      = useState('');

  /* ── ADMS server config (editable) ── */
  // ADMS readers push over HTTP on port 80 (nginx proxies /iclock → backend); never :8000.
  const defaultAddr = `http://${window.location.hostname}`;
  const { data: admsConfig, refetch: refetchAdmsConfig } = useQuery({
    queryKey: ['adms-config'],
    queryFn:  () => apiService.get('/api/device/adms-config'),
    staleTime: 60000,
  });
  const serverAddr = admsConfig?.data?.server_url || admsConfig?.server_url || defaultAddr;

  const saveAddrMutation = useMutation({
    mutationFn: (url) => apiService.put('/api/device/adms-config', { server_url: url }),
    onSuccess: () => {
      message.success('ADMS server address saved');
      setEditingAddr(false);
      refetchAdmsConfig();
    },
    onError: () => message.error('Failed to save ADMS server address'),
  });

  /* ── registered readers ── */
  const { data: termData, isLoading, refetch } = useQuery({
    queryKey: ['adms-terminals'],
    queryFn:  () => apiService.get('/api/device/terminals/'),
    refetchInterval: 15000,
  });
  const all = Array.isArray(termData?.data) ? termData.data : Array.isArray(termData) ? termData : [];

  /* ── pending devices (state=0) ── */
  const { data: pendingData, refetch: refetchPending } = useQuery({
    queryKey: ['adms-pending'],
    queryFn:  () => apiService.get('/iclock/pending-devices'),
    refetchInterval: 10000,
  });
  const pendingDevices = Array.isArray(pendingData?.data) ? pendingData.data : Array.isArray(pendingData) ? pendingData : [];

  /* ── zones for dropdowns ── */
  const { data: zonesData } = useQuery({
    queryKey: ['zones-for-parent'],
    queryFn:  () => apiService.get('/api/v1/zones/'),
  });
  const zones = Array.isArray(zonesData) ? zonesData : Array.isArray(zonesData?.data) ? zonesData.data : [];

  /* ── OPERLOG events ── */
  const operlogQP = new URLSearchParams({ limit: 500 });
  if (operlogSnFilter) operlogQP.set('sn', operlogSnFilter);
  if (operlogFilter != null) operlogQP.set('event_type', operlogFilter);
  if (operlogRange?.[0]) operlogQP.set('from_dt', operlogRange[0].startOf('day').toISOString());
  if (operlogRange?.[1]) operlogQP.set('to_dt', operlogRange[1].endOf('day').toISOString());
  const { data: operlogData, isLoading: operlogLoading, refetch: refetchOperlog } = useQuery({
    queryKey: ['adms-operlog', operlogSnFilter, operlogFilter, operlogRange?.[0]?.valueOf(), operlogRange?.[1]?.valueOf()],
    queryFn:  () => apiService.get(`/iclock/operlog?${operlogQP}`),
    enabled:  activeSubTab === 'operlog',
  });
  const operlogRows = Array.isArray(operlogData?.data?.results) ? operlogData.data.results
                   : Array.isArray(operlogData?.results) ? operlogData.results : [];

  /* ── command history for selected device ── */
  const { data: cmdHistData, isLoading: cmdHistLoading } = useQuery({
    queryKey: ['adms-cmdhistory', cmdHistModal?.sn],
    queryFn:  () => apiService.get(`/api/device/devcmd/?sn=${cmdHistModal?.sn}&limit=50`),
    enabled:  !!cmdHistModal,
  });
  const cmdHistRows = Array.isArray(cmdHistData?.data?.results) ? cmdHistData.data.results
                   : Array.isArray(cmdHistData?.data) ? cmdHistData.data
                   : Array.isArray(cmdHistData) ? cmdHistData : [];

  /* ── employees for push-users modal ── */
  const { data: empData } = useQuery({
    queryKey: ['personnel-list'],
    queryFn:  () => apiService.get('/api/v1/personnel/'),
    enabled:  !!pushUsersModal,
  });
  const employees = Array.isArray(empData?.data) ? empData.data : Array.isArray(empData?.results) ? empData.results : [];

  /* ── shifts for push-timezones modal ── */
  const { data: shiftData } = useQuery({
    queryKey: ['att-timetables'],
    queryFn:  () => apiService.get('/api/v1/attendance/timetables/'),
    enabled:  !!pushTzModal,
  });
  const timetables = Array.isArray(shiftData?.data) ? shiftData.data : Array.isArray(shiftData?.results) ? shiftData.results : [];

  /* ── access levels for push-access modal ── */
  const { data: accLevelData } = useQuery({
    queryKey: ['acc-levels'],
    queryFn:  () => apiService.get('/api/access-control/levels/'),
    enabled:  !!pushAccModal,
  });
  const accLevels = Array.isArray(accLevelData?.data) ? accLevelData.data : [];

  const filtered = search
    ? all.filter(d =>
        (d.alias || '').toLowerCase().includes(search.toLowerCase()) ||
        (d.sn   || '').toLowerCase().includes(search.toLowerCase()) ||
        (d.ip_address || '').includes(search))
    : all;

  const online   = all.filter(d => d.status?.toLowerCase() === 'online').length;
  const assigned = all.filter(d => d.zone_id || d.area_id).length;
  const offline  = all.length - online;

  /* ── mutations ── */
  const sendCmd = useMutation({
    mutationFn: ({ sn, cmd }) => apiService.post('/api/device/devcmd/', { sn, cmd }),
    onSuccess: () => { message.success('Command queued'); setCmdModal(null); setCmdValue(''); setCustomCmd(''); },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const approveMutation = useMutation({
    mutationFn: ({ sn, action }) => apiService.post('/iclock/approve-device', { sn, action }),
    onSuccess: (_, v) => {
      message.success(v.action === 'approve' ? 'Device approved — users will sync automatically' : 'Device rejected');
      qc.invalidateQueries({ queryKey: ['adms-pending'] }); qc.invalidateQueries({ queryKey: ['adms-terminals'] });
    },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const registerMutation = useMutation({
    mutationFn: (vals) => apiService.post('/api/device/terminals/', vals),
    onSuccess: () => { message.success('Pre-registered'); qc.invalidateQueries({ queryKey: ['adms-terminals'] }); setAddModal(false); addForm.resetFields(); },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, alias, ip_address }) => apiService.put(`/api/device/terminals/${id}`, { alias, ip_address }),
    onSuccess: () => { message.success('Updated'); qc.invalidateQueries({ queryKey: ['adms-terminals'] }); setEditModal(null); },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ id, force = false }) =>
      apiService.delete(`/api/device/terminals/${id}${force ? '?force=true' : ''}`),
    onSuccess: () => { message.success('Removed'); qc.invalidateQueries({ queryKey: ['adms-terminals'] }); },
    onError: (e, vars) => {
      const detail = e?.message || 'Failed';
      if (e?.status === 409) {
        Modal.confirm({
          title: 'Terminal has attendance history',
          content: `${detail} Force-deleting will also remove all attendance records from this device. This cannot be undone.`,
          okText: 'Force Delete',
          okType: 'danger',
          onOk: () => deleteMutation.mutate({ id: vars.id, force: true }),
        });
      } else {
        message.error(detail);
      }
    },
  });

  const queryLogsMutation = useMutation({
    mutationFn: (sn) => apiService.post('/iclock/cmd/query-attlog', { sn, cmd_content: 'QUERY ATTLOG' }),
    onSuccess: () => message.success('QUERY ATTLOG queued — device will re-upload its buffer'),
    onError: e => message.error(e?.message || 'Failed'),
  });

  const assignZoneMutation = useMutation({
    mutationFn: ({ deviceId, zoneId, currentZoneId }) => {
      if (zoneId) return apiService.post(`/api/v1/zones/${zoneId}/assign-reader`, { device_id: deviceId });
      if (!currentZoneId) return Promise.resolve({ message: 'Already unassigned' });
      return apiService.delete(`/api/v1/zones/${currentZoneId}/readers/${deviceId}`);
    },
    onSuccess: (res, vars) => {
      message.success(vars.zoneId
        ? (res?.moved_from ? 'Reader moved to zone' : 'Reader assigned to zone')
        : 'Reader unassigned from zone'
      );
      setPendingZoneAssign(null);
      qc.invalidateQueries({ queryKey: ['adms-terminals'] });
      qc.invalidateQueries({ queryKey: ['zones-dashboard'] });
      qc.invalidateQueries({ queryKey: ['available-devices'] });
      if (res?.zone_id)      qc.invalidateQueries({ queryKey: ['zone-readers', res.zone_id] });
      if (res?.moved_from)   qc.invalidateQueries({ queryKey: ['zone-readers', res.moved_from] });
      if (vars.currentZoneId) qc.invalidateQueries({ queryKey: ['zone-readers', vars.currentZoneId] });
    },
    onError: (e) => { message.error(e?.message || 'Failed to assign zone'); setPendingZoneAssign(null); },
  });

  const pushUsersMutation = useMutation({
    mutationFn: ({ sn, emp_codes }) => apiService.post('/iclock/cmd/push-users', { sn, emp_codes: emp_codes?.length ? emp_codes : null }),
    onSuccess: (d) => { message.success(d?.detail || 'Users queued'); setPushUsersModal(null); pushUsersForm.resetFields(); },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const pushTplMutation = useMutation({
    mutationFn: ({ sn, emp_codes }) => apiService.post('/iclock/cmd/push-templates', { sn, emp_codes: emp_codes?.length ? emp_codes : null }),
    onSuccess: (d) => { message.success(d?.detail || 'Templates queued'); setPushTplModal(null); },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const pushTzMutation = useMutation({
    mutationFn: ({ sn, shift_ids }) => apiService.post('/iclock/cmd/push-timezones', { sn, shift_ids: shift_ids?.length ? shift_ids : null }),
    onSuccess: (d) => { message.success(d?.detail || 'Timezones queued'); setPushTzModal(null); pushTzForm.resetFields(); },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const pushAccMutation = useMutation({
    mutationFn: ({ sn, level_ids }) => apiService.post('/iclock/cmd/push-access-levels', { sn, level_ids: level_ids?.length ? level_ids : null }),
    onSuccess: (d) => { message.success(d?.detail || 'Access levels queued'); setPushAccModal(null); pushAccForm.resetFields(); },
    onError: e => message.error(e?.message || 'Failed'),
  });

  const copyAddr = () => {
    navigator.clipboard.writeText(serverAddr);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  /* ── columns ── */
  /* ── reader table columns ── */
  const cols = [
    {
      title: 'Reader', key: 'reader', width: 240, fixed: 'left',
      render: (_, r) => {
        const isOnline = r.status?.toLowerCase() === 'online';
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ position: 'relative', flexShrink: 0 }}>
              <div style={{
                width: 38, height: 38, borderRadius: 9,
                background: isOnline
                  ? 'linear-gradient(135deg,#059669,#10B981)'
                  : 'linear-gradient(135deg,#374151,#6B7280)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'white', fontSize: 17,
                boxShadow: isOnline ? '0 0 0 2px #D1FAE5' : 'none',
              }}><ApiOutlined /></div>
              <div style={{
                position: 'absolute', bottom: 1, right: 1,
                width: 9, height: 9, borderRadius: '50%',
                background: isOnline ? '#10B981' : '#6B7280',
                border: '1.5px solid white',
                boxShadow: isOnline ? '0 0 4px #10B981' : 'none',
                animation: isOnline ? 'statusPulse 2s infinite' : 'none',
              }} />
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13, color: '#111827' }}>
                {r.alias || `Terminal-${r.sn}`}
              </div>
              <div style={{ fontSize: 10.5, color: '#9CA3AF', fontFamily: 'monospace', letterSpacing: '0.03em' }}>
                SN: {r.sn}
              </div>
            </div>
          </div>
        );
      },
    },
    {
      title: 'IP Address', dataIndex: 'ip_address', width: 140,
      render: ip => ip
        ? <code style={{ fontSize: 11, background: '#F3F4F6', padding: '2px 7px', borderRadius: 4, color: '#374151' }}>{ip}</code>
        : <span style={{ color: '#D1D5DB', fontSize: 12 }}>—</span>,
    },
    {
      title: 'Status', key: 'status', width: 105,
      render: (_, r) => {
        const isOnline = r.status?.toLowerCase() === 'online';
        return (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            background: isOnline ? '#ECFDF5' : '#F9FAFB',
            border: `1px solid ${isOnline ? '#6EE7B7' : '#E5E7EB'}`,
            borderRadius: 20, padding: '3px 10px',
          }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: isOnline ? '#10B981' : '#9CA3AF',
            }} />
            <span style={{ fontSize: 11, fontWeight: 600, color: isOnline ? '#059669' : '#6B7280' }}>
              {isOnline ? 'Online' : 'Offline'}
            </span>
          </div>
        );
      },
    },
    {
      title: 'Zone', key: 'zone', width: 200,
      render: (_, r) => {
        const pending = pendingZoneAssign?.deviceId === r.id;
        if (pending) {
          const targetZone = zones.find(z => z.id === pendingZoneAssign.zoneId);
          return (
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ fontSize: 11, color: '#374151', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {targetZone ? targetZone.name : 'Unassign'}?
              </span>
              <Button
                size="small" type="primary" style={{ fontSize: 10, padding: '0 7px', height: 22, minWidth: 0 }}
                loading={assignZoneMutation.isPending}
                onClick={() => assignZoneMutation.mutate(pendingZoneAssign)}
              >✓</Button>
              <Button
                size="small" style={{ fontSize: 10, padding: '0 7px', height: 22, minWidth: 0 }}
                disabled={assignZoneMutation.isPending}
                onClick={() => setPendingZoneAssign(null)}
              >✕</Button>
            </div>
          );
        }
        if ((r.reader_purpose || 'ATTENDANCE') === 'ATTENDANCE' && r.device_type !== 2) {
          return (
            <Tooltip title="Time & attendance readers are not part of zones or mustering (they can be in another state or country). To use it on a door, change its purpose to Access Entry/Exit under Devices.">
              <span style={{ fontSize: 11, color: '#6B7280' }}>T&amp;A — not in a zone{r.zone_id ? ' (old link ignored)' : ''}</span>
            </Tooltip>
          );
        }
        return (
          <Select
            size="small"
            allowClear
            placeholder="Unassigned"
            value={r.zone_id ?? undefined}
            style={{ width: '100%', fontSize: 11 }}
            onChange={(zoneId) => setPendingZoneAssign({ deviceId: r.id, zoneId: zoneId ?? null, currentZoneId: r.zone_id })}
            options={zones.map(z => ({ value: z.id, label: z.name }))}
          />
        );
      },
    },
    {
      title: 'Firmware', dataIndex: 'fw_version', width: 110,
      render: v => v
        ? <Tag style={{ fontSize: 10, borderRadius: 4 }}>{v}</Tag>
        : <span style={{ color: '#D1D5DB', fontSize: 12 }}>—</span>,
    },
    {
      title: 'Last Seen', dataIndex: 'last_activity', width: 140,
      render: v => <span style={{ fontSize: 11, color: '#6B7280' }}>{fmtTime(v)}</span>,
    },
    {
      title: '', key: 'actions', width: 200, fixed: 'right',
      render: (_, r) => (
        <Space size={4} wrap>
          <Tooltip title="Send Command">
            <Button size="small" type="primary" ghost icon={<SendOutlined />}
              onClick={() => { setCmdModal(r); setCmdValue(''); setCustomCmd(''); }} />
          </Tooltip>
          <Tooltip title="Capability Stats">
            <Button size="small" icon={<DashboardOutlined />}
              onClick={() => setCapModal(r)} />
          </Tooltip>
          <Tooltip title="Push Users">
            <Button size="small" icon={<TeamOutlined />}
              onClick={() => setPushUsersModal(r)} />
          </Tooltip>
          <Tooltip title="Push Templates">
            <Button size="small" icon={<SyncOutlined />}
              onClick={() => setPushTplModal(r)} />
          </Tooltip>
          <Tooltip title="Push Time Rules">
            <Button size="small" icon={<ClockCircleOutlined />}
              onClick={() => setPushTzModal(r)} />
          </Tooltip>
          <Tooltip title="Push Access Levels">
            <Button size="small" icon={<LockOutlined />}
              onClick={() => setPushAccModal(r)} />
          </Tooltip>
          <Tooltip title="Query / Force Re-upload Logs">
            <Popconfirm title="Reset Stamp and force device to re-upload all logs?" okType="primary"
              onConfirm={() => queryLogsMutation.mutate(r.sn)}>
              <Button size="small" icon={<ReloadOutlined />} />
            </Popconfirm>
          </Tooltip>
          <Tooltip title="Command History">
            <Button size="small" icon={<ClockCircleOutlined />} style={{ color: '#7C3AED' }}
              onClick={() => setCmdHistModal(r)} />
          </Tooltip>
          <Tooltip title="Rename">
            <Button size="small" icon={<EditOutlined />}
              onClick={() => { setEditModal(r); setEditAlias(r.alias || ''); setEditIp(r.ip_address || ''); }} />
          </Tooltip>
          <Popconfirm title="Remove this reader?" okType="danger"
            onConfirm={() => deleteMutation.mutate({ id: r.id })}>
            <Button size="small" danger type="text" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  /* ── CMD status chip helper ── */
  const cmdStatusChip = (s) => {
    const map = { 0: ['Pending','#F59E0B','#FFFBEB'], 1: ['Sent','#1D4ED8','#EFF6FF'], 2: ['Success','#059669','#ECFDF5'], 3: ['Failed','#EF4444','#FEF2F2'] };
    const [label,color,bg] = map[s] || ['Unknown','#6B7280','#F9FAFB'];
    return <span style={{ fontSize:10, fontWeight:600, color, background:bg, border:`1px solid ${color}30`, borderRadius:4, padding:'1px 7px' }}>{label}</span>;
  };

  /* ── sub-tab: registered readers ── */
  const readersTab = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <Input
          prefix={<SearchOutlined style={{ color: '#9CA3AF' }} />}
          placeholder="Search by alias, SN or IP…"
          value={search} onChange={e => setSearch(e.target.value)}
          allowClear size="small" style={{ maxWidth: 300 }}
        />
        <Button size="small" icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading}>
          Refresh
        </Button>
        <Button size="small" type="primary" icon={<PlusOutlined />}
          style={{ marginLeft: 'auto', borderRadius: 7 }}
          onClick={() => setAddModal(true)}>
          Pre-register Reader
        </Button>
        <span style={{ fontSize: 12, color: '#9CA3AF' }}>
          {filtered.length} reader{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div style={{ background: 'white', borderRadius: 12, border: '1px solid #E5E7EB', overflow: 'hidden' }}>
        <Table
          dataSource={filtered}
          loading={isLoading}
          rowKey={r => r.id ?? r.sn}
          size="small"
          pagination={{ pageSize: 20, size: 'small' }}
          scroll={{ x: 1050 }}
          columns={cols}
          locale={{ emptyText: (
            <div style={{ padding: '40px 0', textAlign: 'center', color: '#9CA3AF' }}>
              <ApiOutlined style={{ fontSize: 32, display: 'block', marginBottom: 8 }} />
              <div style={{ fontWeight: 600, marginBottom: 4 }}>No readers yet</div>
              <div style={{ fontSize: 12 }}>Configure your ZKTeco device with this server address to get started</div>
            </div>
          )}}
        />
      </div>
    </div>
  );

  /* ── sub-tab: pending approval ── */
  const pendingTab = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {pendingDevices.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: '#9CA3AF' }}>
          <CheckOutlined style={{ fontSize: 40, color: '#10B981', marginBottom: 12 }} />
          <div style={{ fontWeight: 600, fontSize: 14, color: '#374151' }}>All clear — no devices awaiting approval</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>New devices that connect for the first time will appear here</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {pendingDevices.map(d => (
            <div key={d.sn} style={{
              background: 'white', borderRadius: 12, border: '1.5px solid #FCD34D',
              padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              boxShadow: '0 2px 8px rgba(251,191,36,0.12)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 10,
                  background: 'linear-gradient(135deg,#F59E0B,#D97706)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: 'white', fontSize: 20,
                }}>
                  <ApiOutlined />
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14, color: '#111827' }}>
                    {d.alias || `Unknown Device`}
                  </div>
                  <div style={{ display: 'flex', gap: 16, marginTop: 3 }}>
                    <span style={{ fontSize: 11, color: '#6B7280' }}>
                      SN: <code style={{ background: '#F3F4F6', padding: '1px 5px', borderRadius: 3 }}>{d.sn}</code>
                    </span>
                    {d.ip_address && (
                      <span style={{ fontSize: 11, color: '#6B7280' }}>
                        IP: <code style={{ background: '#F3F4F6', padding: '1px 5px', borderRadius: 3 }}>{d.ip_address}</code>
                      </span>
                    )}
                    {d.fw_version && (
                      <span style={{ fontSize: 11, color: '#6B7280' }}>FW: {d.fw_version}</span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>
                    First seen: {fmtTime(d.created_at)}
                  </div>
                </div>
              </div>
              <Space size={8}>
                <Button
                  type="primary"
                  icon={<CheckOutlined />}
                  style={{ background: '#059669', borderColor: '#059669', borderRadius: 8 }}
                  loading={approveMutation.isPending && approveMutation.variables?.sn === d.sn && approveMutation.variables?.action === 'approve'}
                  disabled={approveMutation.isPending && approveMutation.variables?.sn === d.sn}
                  onClick={() => approveMutation.mutate({ sn: d.sn, action: 'approve' })}>
                  Approve
                </Button>
                <Button
                  danger
                  icon={<CloseOutlined />}
                  style={{ borderRadius: 8 }}
                  loading={approveMutation.isPending && approveMutation.variables?.sn === d.sn && approveMutation.variables?.action === 'reject'}
                  disabled={approveMutation.isPending && approveMutation.variables?.sn === d.sn}
                  onClick={() => approveMutation.mutate({ sn: d.sn, action: 'reject' })}>
                  Reject
                </Button>
              </Space>
            </div>
          ))}
        </div>
      )}
      <Alert
        type="warning"
        showIcon
        message="Security notice: Until approved, attendance records from pending devices are not processed. Reject any device you do not recognise."
        style={{ fontSize: 12 }}
      />
    </div>
  );

  /* ── sub-tab: OPERLOG viewer ── */
  const operlogTab = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <Select
          placeholder="All devices"
          allowClear
          style={{ width: 220 }}
          size="small"
          value={operlogSnFilter}
          onChange={v => setOperlogSnFilter(v || null)}
          showSearch
          optionFilterProp="label"
        >
          {all.map(d => (
            <Select.Option key={d.sn} value={d.sn} label={d.alias || d.sn}>
              {d.alias || d.sn}
            </Select.Option>
          ))}
        </Select>
        <Select
          placeholder="All event types"
          allowClear
          style={{ width: 200 }}
          size="small"
          value={operlogFilter}
          onChange={v => setOperlogFilter(v ?? null)}
        >
          {Object.entries(OPER_EVENT_META).map(([k, m]) => (
            <Select.Option key={k} value={Number(k)}>{m.label}</Select.Option>
          ))}
        </Select>
        <DatePicker.RangePicker
          size="small"
          value={operlogRange}
          onChange={v => setOperlogRange(v || null)}
          allowClear
          style={{ width: 240 }}
          placeholder={['From date', 'To date']}
        />
        <Button size="small" icon={<ReloadOutlined />} onClick={() => refetchOperlog()}>
          Refresh
        </Button>
        {(operlogSnFilter || operlogFilter != null || operlogRange) && (
          <Button size="small" type="link" style={{ color: '#EF4444', padding: '0 4px', fontSize: 12 }}
            onClick={() => { setOperlogSnFilter(null); setOperlogFilter(null); setOperlogRange(null); }}>
            ✕ Clear
          </Button>
        )}
        <span style={{ fontSize: 12, color: '#9CA3AF', marginLeft: 'auto' }}>
          {operlogRows.length} event{operlogRows.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div style={{ background: 'white', borderRadius: 12, border: '1px solid #E5E7EB', overflow: 'hidden' }}>
        <Table
          dataSource={operlogRows}
          loading={operlogLoading}
          rowKey={r => r.id}
          size="small"
          pagination={{ pageSize: 25, size: 'small' }}
          scroll={{ x: 800 }}
          columns={[
            {
              title: 'Event', key: 'event', width: 160,
              render: (_, r) => {
                const meta = OPER_EVENT_META[r.oper_event] || { label: `Event ${r.oper_event}`, color: '#6B7280', bg: '#F9FAFB' };
                return (
                  <span style={{
                    fontSize: 11, fontWeight: 600, color: meta.color,
                    background: meta.bg, border: `1px solid ${meta.color}30`,
                    borderRadius: 5, padding: '2px 8px',
                  }}>{meta.label}</span>
                );
              },
            },
            {
              title: 'Device', dataIndex: 'terminal_sn', width: 160,
              render: sn => {
                const dev = all.find(d => d.sn === sn);
                return (
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 500 }}>{dev?.alias || sn}</div>
                    <code style={{ fontSize: 10, color: '#9CA3AF' }}>{sn}</code>
                  </div>
                );
              },
            },
            {
              title: 'Time', dataIndex: 'event_time', width: 160,
              render: v => <span style={{ fontSize: 11, color: '#374151' }}>{fmtTime(v)}</span>,
            },
            {
              title: 'Door', dataIndex: 'door_id', width: 80,
              render: v => v != null ? <Tag style={{ fontSize: 10 }}>Door {v}</Tag> : <span style={{ color: '#D1D5DB' }}>—</span>,
            },
            {
              title: 'Admin', dataIndex: 'admin_id', width: 100,
              render: v => v ? <code style={{ fontSize: 11 }}>{v}</code> : <span style={{ color: '#D1D5DB' }}>—</span>,
            },
            { title: 'Object', dataIndex: 'object_name', width: 140, render: v => v || '—' },
            { title: 'Param1', dataIndex: 'param1', width: 120, render: v => v ? <code style={{ fontSize: 10 }}>{v}</code> : '—' },
          ]}
          locale={{ emptyText: (
            <div style={{ padding: '40px 0', textAlign: 'center', color: '#9CA3AF' }}>
              <InfoCircleOutlined style={{ fontSize: 28, marginBottom: 8 }} />
              <div>No OPERLOG events yet.</div>
              <div style={{ fontSize: 12 }}>Door events and alarms will appear here once a device sends them.</div>
            </div>
          )}}
        />
      </div>
    </div>
  );

  /* ── sub-tab: server setup guide ── */
  const setupTab = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{
        background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)',
        borderRadius: 14, padding: 24, color: 'white',
      }}>
        <div style={{ fontSize: 11, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
          ADMS Server Address (enter this on your device)
        </div>
        {editingAddr ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Input
              value={addrInput}
              onChange={e => setAddrInput(e.target.value)}
              placeholder={defaultAddr}
              style={{ flex: 1, fontSize: 16, fontWeight: 600, fontFamily: 'monospace', height: 44, borderRadius: 8 }}
              autoFocus
              onPressEnter={() => saveAddrMutation.mutate(addrInput)}
            />
            <Button
              type="primary" icon={<CheckOutlined />}
              loading={saveAddrMutation.isPending}
              onClick={() => saveAddrMutation.mutate(addrInput)}
              style={{ height: 44, borderRadius: 8, fontWeight: 600 }}>
              Save
            </Button>
            <Button
              icon={<CloseOutlined />}
              onClick={() => setEditingAddr(false)}
              style={{ height: 44, borderRadius: 8, background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)', color: 'white' }}>
              Cancel
            </Button>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <code style={{
              fontSize: 22, fontWeight: 700, color: '#38BDF8',
              background: 'rgba(56,189,248,0.1)', border: '1px solid rgba(56,189,248,0.2)',
              borderRadius: 8, padding: '8px 18px', flex: 1, letterSpacing: '0.04em',
            }}>{serverAddr}</code>
            <Button
              icon={<EditOutlined />}
              onClick={() => { setAddrInput(serverAddr); setEditingAddr(true); }}
              style={{
                background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)',
                color: '#94A3B8', borderRadius: 8, height: 44, padding: '0 14px',
              }}>
              Edit
            </Button>
            <Button
              icon={copied ? <CheckOutlined /> : <CopyOutlined />}
              onClick={copyAddr}
              style={{
                background: copied ? '#059669' : 'rgba(255,255,255,0.1)',
                border: `1px solid ${copied ? '#059669' : 'rgba(255,255,255,0.2)'}`,
                color: 'white', borderRadius: 8, height: 44, padding: '0 18px', fontWeight: 600,
              }}>
              {copied ? 'Copied!' : 'Copy'}
            </Button>
          </div>
        )}
        <div style={{ marginTop: 10, fontSize: 12, color: '#64748B', display: 'flex', gap: 20 }}>
          <span><strong style={{ color: '#94A3B8' }}>Protocol:</strong> HTTP (ADMS push)</span>
          <span><strong style={{ color: '#94A3B8' }}>Endpoint:</strong> /iclock/cdata</span>
          <span><strong style={{ color: '#94A3B8' }}>Auto-register:</strong> Enabled</span>
          {admsConfig?.data?.server_url && (
            <span style={{ color: '#22C55E' }}>
              <CheckOutlined style={{ marginRight: 4 }} />Custom address saved
            </span>
          )}
        </div>
      </div>

      <Row gutter={16}>
        <Col xs={24} md={14}>
          <div style={{ background: 'white', borderRadius: 12, border: '1px solid #E5E7EB', padding: 20 }}>
            <div style={{ fontWeight: 700, fontSize: 14, color: '#111827', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <InfoCircleOutlined style={{ color: '#1D4ED8' }} /> How ADMS Registration Works
            </div>
            {[
              {
                step: '01', color: '#1D4ED8',
                title: 'Configure the ZKTeco device',
                desc: 'On the device keypad: Menu → Comm → ADMS → set "Server Address" to the address above. Set port to 8000.',
              },
              {
                step: '02', color: '#7C3AED',
                title: 'Device connects & auto-registers',
                desc: 'The reader calls GET /iclock/cdata?SN=<serial> on boot and every 30 s. The server auto-creates a pending record.',
              },
              {
                step: '03', color: '#F59E0B',
                title: 'Approve the device',
                desc: 'Go to the "Pending Approval" tab, verify the SN, and click Approve. Rejected devices are blocked permanently.',
              },
              {
                step: '04', color: '#059669',
                title: 'Assign to a Zone',
                desc: 'From the Readers table assign the reader to a zone. Punches update that zone\'s POB count in real time.',
              },
            ].map(s => (
              <div key={s.step} style={{ display: 'flex', gap: 14, marginBottom: 18 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                  background: `${s.color}18`, border: `1.5px solid ${s.color}40`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 800, color: s.color,
                }}>{s.step}</div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13, color: '#111827', marginBottom: 2 }}>{s.title}</div>
                  <div style={{ fontSize: 12, color: '#6B7280', lineHeight: 1.6 }}>{s.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </Col>
        <Col xs={24} md={10}>
          <div style={{ background: 'white', borderRadius: 12, border: '1px solid #E5E7EB', padding: 20 }}>
            <div style={{ fontWeight: 700, fontSize: 14, color: '#111827', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <SettingOutlined style={{ color: '#059669' }} /> ADMS Protocol Endpoints
            </div>
            {[
              { method: 'GET',  path: '/iclock/cdata',     desc: 'Heartbeat / attendance upload trigger', color: '#1D4ED8' },
              { method: 'POST', path: '/iclock/cdata',     desc: 'Bulk ATTLOG / OPERLOG / USERINFO push',  color: '#1D4ED8' },
              { method: 'GET',  path: '/iclock/getrequest',desc: 'Device polls for queued commands',       color: '#7C3AED' },
              { method: 'POST', path: '/iclock/devicecmd', desc: 'Device reports command result',          color: '#059669' },
            ].map(ep => (
              <div key={`${ep.method}-${ep.path}`} style={{ marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, color: ep.color,
                    background: `${ep.color}15`, border: `1px solid ${ep.color}30`,
                    borderRadius: 4, padding: '1px 6px',
                  }}>{ep.method}</span>
                  <code style={{ fontSize: 11, color: '#374151' }}>{ep.path}</code>
                </div>
                <div style={{ fontSize: 11, color: '#9CA3AF', paddingLeft: 6 }}>{ep.desc}</div>
              </div>
            ))}
            <Divider style={{ margin: '12px 0' }} />
            <div style={{ fontSize: 11, color: '#6B7280', lineHeight: 1.7 }}>
              <strong>Push direction:</strong> Reader → Server (device-initiated)<br />
              <strong>Commands direction:</strong> Server → Reader (via poll queue)<br />
              <strong>Poll interval:</strong> Every 30 s (configurable per-device)
            </div>
          </div>

          <div style={{
            background: 'linear-gradient(135deg,#FFFBEB,#FEF3C7)',
            border: '1px solid #FCD34D', borderRadius: 12, padding: 16, marginTop: 14,
          }}>
            <div style={{ fontWeight: 700, fontSize: 12, color: '#92400E', marginBottom: 10 }}>
              vs. BioTime Cloud (same protocol, different server)
            </div>
            {[
              { label: 'BioTime Cloud',      value: 'adms.zkteco.com:443' },
              { label: 'Your Server (ADMS)', value: `${window.location.hostname}:80` },
            ].map(r => (
              <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 6 }}>
                <span style={{ color: '#92400E' }}>{r.label}</span>
                <code style={{ color: '#78350F', fontWeight: 600 }}>{r.value}</code>
              </div>
            ))}
            <div style={{ fontSize: 11, color: '#B45309', marginTop: 6 }}>
              Identical ADMS protocol. Simply point the device at your server instead of ZKTeco's cloud.
            </div>
          </div>
        </Col>
      </Row>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Header ── */}
      <div style={{
        background: 'linear-gradient(135deg, #0F172A 0%, #1E3A8A 60%, #1D4ED8 100%)',
        borderRadius: 14, padding: '18px 22px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        boxShadow: '0 8px 24px rgba(29,78,216,0.2)',
      }}>
        <Space size={14}>
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: 'linear-gradient(135deg,#3B82F6,#1D4ED8)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 14px rgba(59,130,246,0.4)',
          }}>
            <WifiOutlined style={{ color: 'white', fontSize: 22 }} />
          </div>
          <div>
            <div style={{ color: 'white', fontWeight: 700, fontSize: 16 }}>ADMS Reader Management</div>
            <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12, marginTop: 1 }}>
              ZKTeco terminals — push-based protocol over LAN / 4G
            </div>
          </div>
        </Space>
        <Space size={20}>
          {[
            { label: 'Total',    value: all.length,                 color: '#93C5FD' },
            { label: 'Online',   value: online,                     color: '#6EE7B7' },
            { label: 'Offline',  value: offline,                    color: '#FCA5A5' },
            { label: 'Assigned', value: assigned,                   color: '#C4B5FD' },
            { label: 'Pending',  value: pendingDevices.length,      color: '#FDE68A' },
          ].map(s => (
            <div key={s.label} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.value}</div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)', marginTop: 2 }}>{s.label}</div>
            </div>
          ))}
        </Space>
      </div>

      {/* ── Sub-tabs ── */}
      <Tabs
        activeKey={activeSubTab}
        onChange={setActiveSubTab}
        size="small"
        items={[
          {
            key: 'readers',
            label: (
              <Space size={6}>
                <ApiOutlined />
                Registered Readers
                {online > 0 && <Badge count={online} color="#10B981" size="small" />}
              </Space>
            ),
            children: readersTab,
          },
          {
            key: 'pending',
            label: (
              <Space size={6}>
                <ClockCircleOutlined />
                Pending Approval
                {pendingDevices.length > 0 && <Badge count={pendingDevices.length} color="#F59E0B" size="small" />}
              </Space>
            ),
            children: pendingTab,
          },
          {
            key: 'operlog',
            label: <Space size={6}><AlertOutlined />OPERLOG Viewer</Space>,
            children: operlogTab,
          },
          {
            key: 'setup',
            label: <Space size={6}><InfoCircleOutlined />Server Setup & Protocol</Space>,
            children: setupTab,
          },
        ]}
      />

      {/* ── Send Command Modal ── */}
      <Modal
        open={!!cmdModal}
        title={
          <Space>
            <SendOutlined style={{ color: '#1D4ED8' }} />
            Send Command — <code style={{ fontSize: 13 }}>{cmdModal?.sn}</code>
          </Space>
        }
        onCancel={() => { setCmdModal(null); setCmdValue(''); setCustomCmd(''); }}
        onOk={() => {
          const cmd = cmdValue === 'custom' ? customCmd.trim() : cmdValue;
          if (!cmd) { message.warning('Select or type a command'); return; }
          sendCmd.mutate({ sn: cmdModal.sn, cmd });
        }}
        confirmLoading={sendCmd.isPending}
        okText="Queue Command"
        width={520}
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 12 }}>
            Commands are queued and delivered the next time the device polls
            <code style={{ margin: '0 4px', fontSize: 11, background:'#F3F4F6', padding:'1px 5px', borderRadius:3 }}>/iclock/getrequest</code>
            (every ~30 s).
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
            {CMD_PRESETS.map(p => (
              <button key={p.value}
                onClick={() => { setCmdValue(p.value); setCustomCmd(''); }}
                style={{
                  border: `1.5px solid ${cmdValue === p.value ? p.color : '#E5E7EB'}`,
                  borderRadius: 8, padding: '8px 12px', background: cmdValue === p.value ? `${p.color}12` : 'white',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, textAlign: 'left',
                  transition: 'all 0.15s',
                }}>
                <span style={{ color: p.color, fontSize: 14 }}>{p.icon}</span>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#111827' }}>{p.label}</div>
                  <code style={{ fontSize: 10, color: '#6B7280' }}>{p.value}</code>
                </div>
              </button>
            ))}
          </div>
          <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 6 }}>Or type a custom command:</div>
          <Input
            placeholder="e.g. DATA UPDATE USERINFO PIN=001 Name=John"
            value={customCmd}
            onChange={e => { setCustomCmd(e.target.value); setCmdValue('custom'); }}
            onClick={() => setCmdValue('custom')}
            style={{ fontFamily: 'monospace', fontSize: 12 }}
          />
        </div>
      </Modal>

      {/* ── Capability Stats Modal ── */}
      <Modal
        open={!!capModal}
        title={
          <Space>
            <DashboardOutlined style={{ color: '#7C3AED' }} />
            Device Capacity — <code style={{ fontSize: 13 }}>{capModal?.alias || capModal?.sn}</code>
          </Space>
        }
        onCancel={() => setCapModal(null)}
        footer={<Button onClick={() => setCapModal(null)}>Close</Button>}
        width={480}
      >
        {capModal && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[
              { label: 'Enrolled Users',       value: capModal.user_count  ?? '—', icon: <TeamOutlined />,        color: '#1D4ED8' },
              { label: 'Fingerprint Templates',value: capModal.fp_count    ?? '—', icon: <SyncOutlined />,        color: '#7C3AED' },
              { label: 'Face Templates',       value: capModal.face_count  ?? '—', icon: <ApiOutlined />,         color: '#059669' },
              { label: 'Palm Templates',       value: capModal.palm_count  ?? '—', icon: <ApiOutlined />,         color: '#F59E0B' },
              { label: 'Attendance Records',   value: capModal.log_count   ?? '—', icon: <ClockCircleOutlined />, color: '#EF4444' },
            ].map(s => (
              <div key={s.label} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 14px', borderRadius: 10,
                background: `${s.color}08`, border: `1px solid ${s.color}20`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: s.color, fontSize: 15 }}>{s.icon}</span>
                  <span style={{ fontSize: 13, color: '#374151' }}>{s.label}</span>
                </div>
                <span style={{ fontSize: 20, fontWeight: 800, color: s.color }}>{s.value}</span>
              </div>
            ))}
            <div style={{ fontSize: 11, color: '#9CA3AF', textAlign: 'center', marginTop: 4 }}>
              Counts are updated on each device heartbeat.
            </div>
          </div>
        )}
      </Modal>

      {/* ── Push Users Modal ── */}
      <Modal
        open={!!pushUsersModal}
        title={
          <Space>
            <TeamOutlined style={{ color: '#1D4ED8' }} />
            Push Users to — <code style={{ fontSize: 13 }}>{pushUsersModal?.alias || pushUsersModal?.sn}</code>
          </Space>
        }
        onCancel={() => { setPushUsersModal(null); pushUsersForm.resetFields(); }}
        onOk={() => pushUsersForm.validateFields().then(v =>
          pushUsersMutation.mutate({ sn: pushUsersModal.sn, emp_codes: v.emp_codes })
        )}
        confirmLoading={pushUsersMutation.isPending}
        okText="Push to Device"
        width={520}
      >
        <Alert type="info" showIcon message="Leaves emp_codes empty to push ALL personnel to the device." style={{ marginBottom: 16, fontSize: 12 }} />
        <Form form={pushUsersForm} layout="vertical">
          <Form.Item name="emp_codes" label="Select Employees (leave blank for all)">
            <Select
              mode="multiple"
              placeholder="All employees"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: '100%' }}
            >
              {employees.map(e => (
                <Select.Option key={e.emp_code} value={e.emp_code} label={`${e.first_name} ${e.last_name} (${e.emp_code})`}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 500 }}>{e.first_name} {e.last_name}</div>
                    <code style={{ fontSize: 10, color: '#9CA3AF' }}>{e.emp_code}</code>
                  </div>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Push Templates Modal ── */}
      <Modal
        open={!!pushTplModal}
        title={
          <Space>
            <SyncOutlined style={{ color: '#7C3AED' }} />
            Push Biometric Templates — <code style={{ fontSize: 13 }}>{pushTplModal?.alias || pushTplModal?.sn}</code>
          </Space>
        }
        onCancel={() => setPushTplModal(null)}
        onOk={() => pushTplMutation.mutate({ sn: pushTplModal.sn, emp_codes: null })}
        confirmLoading={pushTplMutation.isPending}
        okText="Push All Templates"
        width={480}
      >
        <Alert
          type="info" showIcon
          message="This queues DATA UPDATE BIODATA commands for all fingerprint and face templates stored on this server."
          style={{ marginBottom: 16, fontSize: 12 }}
        />
        <div style={{ background: '#F9FAFB', borderRadius: 10, padding: '12px 16px', fontSize: 12, color: '#374151' }}>
          Device: <strong>{pushTplModal?.alias || pushTplModal?.sn}</strong><br />
          Templates on server: <strong>{pushTplModal?.fp_count ?? 0} FP + {pushTplModal?.face_count ?? 0} Face</strong>
        </div>
      </Modal>

      {/* ── Push Time Rules Modal ── */}
      <Modal
        open={!!pushTzModal}
        title={
          <Space>
            <ClockCircleOutlined style={{ color: '#059669' }} />
            Push Time Rules — <code style={{ fontSize: 13 }}>{pushTzModal?.alias || pushTzModal?.sn}</code>
          </Space>
        }
        onCancel={() => { setPushTzModal(null); pushTzForm.resetFields(); }}
        onOk={() => pushTzForm.validateFields().then(v =>
          pushTzMutation.mutate({ sn: pushTzModal.sn, shift_ids: v.shift_ids })
        )}
        confirmLoading={pushTzMutation.isPending}
        okText="Push to Device"
        width={500}
      >
        <Alert type="info" showIcon message="Leave blank to push all shift timetables. The device uses these for offline access control." style={{ marginBottom: 16, fontSize: 12 }} />
        <Form form={pushTzForm} layout="vertical">
          <Form.Item name="shift_ids" label="Select Timetables (leave blank for all)">
            <Select
              mode="multiple"
              placeholder="All timetables"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: '100%' }}
            >
              {timetables.map(t => (
                <Select.Option key={t.id} value={t.id} label={t.name}>{t.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Push Access Levels Modal ── */}
      <Modal
        open={!!pushAccModal}
        title={
          <Space>
            <LockOutlined style={{ color: '#EF4444' }} />
            Push Access Levels — <code style={{ fontSize: 13 }}>{pushAccModal?.alias || pushAccModal?.sn}</code>
          </Space>
        }
        onCancel={() => { setPushAccModal(null); pushAccForm.resetFields(); }}
        onOk={() => pushAccForm.validateFields().then(v =>
          pushAccMutation.mutate({ sn: pushAccModal.sn, level_ids: v.level_ids })
        )}
        confirmLoading={pushAccMutation.isPending}
        okText="Push to Device"
        width={500}
      >
        <Alert type="info" showIcon message="Leave blank to push all access levels. These control which doors each employee can open." style={{ marginBottom: 16, fontSize: 12 }} />
        <Form form={pushAccForm} layout="vertical">
          <Form.Item name="level_ids" label="Select Access Levels (leave blank for all)">
            <Select
              mode="multiple"
              placeholder="All access levels"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: '100%' }}
            >
              {accLevels.map(l => (
                <Select.Option key={l.id} value={l.id} label={l.name}>{l.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Command History Modal ── */}
      <Modal
        open={!!cmdHistModal}
        title={
          <Space>
            <ClockCircleOutlined style={{ color: '#7C3AED' }} />
            Command History — <code style={{ fontSize: 13 }}>{cmdHistModal?.alias || cmdHistModal?.sn}</code>
          </Space>
        }
        onCancel={() => setCmdHistModal(null)}
        footer={<Button onClick={() => setCmdHistModal(null)}>Close</Button>}
        width={640}
      >
        <Table
          dataSource={cmdHistRows}
          loading={cmdHistLoading}
          rowKey={r => r.id}
          size="small"
          pagination={{ pageSize: 15, size: 'small' }}
          columns={[
            {
              title: 'Command', dataIndex: 'cmd_content', ellipsis: true,
              render: v => <code style={{ fontSize: 11 }}>{v}</code>,
            },
            {
              title: 'Status', dataIndex: 'status', width: 90,
              render: s => cmdStatusChip(s),
            },
            {
              title: 'Queued', dataIndex: 'created_at', width: 130,
              render: v => <span style={{ fontSize: 11 }}>{fmtTime(v)}</span>,
            },
            {
              title: 'Executed', dataIndex: 'executed_at', width: 130,
              render: v => v ? <span style={{ fontSize: 11 }}>{fmtTime(v)}</span> : <span style={{ color: '#D1D5DB' }}>—</span>,
            },
          ]}
          locale={{ emptyText: <div style={{ padding: '24px 0', textAlign: 'center', color: '#9CA3AF' }}>No commands sent yet</div> }}
        />
      </Modal>

      {/* ── Pre-register Modal ── */}
      <Modal
        open={addModal}
        title={<Space><PlusOutlined style={{ color: '#059669' }} />Pre-register a Reader</Space>}
        onCancel={() => { setAddModal(false); addForm.resetFields(); }}
        onOk={() => addForm.validateFields().then(vals => registerMutation.mutate(vals))}
        confirmLoading={registerMutation.isPending}
        okText="Register"
      >
        <Alert
          type="info"
          showIcon
          message="Pre-registration is optional — devices auto-register on first connection and appear in Pending Approval."
          style={{ marginBottom: 16, fontSize: 12 }}
        />
        <Form form={addForm} layout="vertical">
          <Form.Item name="sn" label="Serial Number (SN)" rules={[{ required: true, message: 'SN is required' }]}>
            <Input placeholder="e.g. BKMD203460031" style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="alias" label="Alias / Name">
            <Input placeholder="e.g. Gate A Reader" />
          </Form.Item>
          <Form.Item name="ip_address" label="Expected IP Address">
            <Input placeholder="e.g. 192.168.1.120" />
          </Form.Item>
          <Form.Item name="zone_id" label="Assign to Zone">
            <Select placeholder="Select zone" allowClear showSearch optionFilterProp="label">
              {zones.map(z => (
                <Select.Option key={z.id} value={z.id} label={z.name}>{z.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Edit Reader Modal ── */}
      <Modal
        open={!!editModal}
        title={<Space><EditOutlined style={{ color: '#1D4ED8' }} />Edit Reader</Space>}
        onCancel={() => setEditModal(null)}
        onOk={() => renameMutation.mutate({ id: editModal.id, alias: editAlias, ip_address: editIp || undefined })}
        confirmLoading={renameMutation.isPending}
        okText="Save"
      >
        <div style={{ marginBottom: 12, fontSize: 12, color: '#6B7280' }}>
          SN: <code style={{ background: '#F3F4F6', padding: '1px 6px', borderRadius: 3 }}>{editModal?.sn}</code>
        </div>
        <div style={{ marginBottom: 8, fontSize: 12, fontWeight: 600, color: '#374151' }}>Display Name</div>
        <Input
          placeholder="Friendly name, e.g. Main Gate Entry"
          value={editAlias}
          onChange={e => setEditAlias(e.target.value)}
          autoFocus
          style={{ marginBottom: 16 }}
        />
        <div style={{ marginBottom: 8, fontSize: 12, fontWeight: 600, color: '#374151' }}>
          IP Address
          <span style={{ fontWeight: 400, color: '#9CA3AF', marginLeft: 8 }}>
            (correct if shown as 192.168.65.1 — Docker masks the real IP)
          </span>
        </div>
        <Input
          placeholder="e.g. 192.168.0.100"
          value={editIp}
          onChange={e => setEditIp(e.target.value)}
        />
      </Modal>

      <style>{`
        @keyframes statusPulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
};

/* ── Main Component ────────────────────────────────────────────────────────── */

/* ── Shared filter bar (used by Zone Cards + Zone List tabs) ──────────────── */
const ZoneFilterBar = ({ typeFilter, setTypeFilter, statusFilter, setStatusFilter, hazardFilter, setHazardFilter, onClear }) => (
  <>
    <Select
      placeholder="All Types" allowClear value={typeFilter} onChange={setTypeFilter}
      size="small" style={{ width: 148 }} popupMatchSelectWidth={false}
    >
      {Object.entries(ZONE_TYPE_LABELS).map(([v, l]) => {
        const zs = getZoneStyle(v);
        return (
          <Select.Option key={v} value={v}>
            <span style={{ color: zs.color, marginRight: 6 }}>{zs.icon}</span>{l}
          </Select.Option>
        );
      })}
    </Select>

    <Select
      placeholder="All Statuses" allowClear value={statusFilter} onChange={setStatusFilter}
      size="small" style={{ width: 138 }}
    >
      {['ACTIVE','INACTIVE','MAINTENANCE','EMERGENCY','LOCKDOWN'].map(s => {
        const ss = getStatusStyle(s);
        return (
          <Select.Option key={s} value={s}>
            <span style={{ color: ss.color, marginRight: 5 }}>●</span>
            {s.charAt(0) + s.slice(1).toLowerCase()}
          </Select.Option>
        );
      })}
    </Select>

    <Select
      placeholder="All Hazard Levels" allowClear value={hazardFilter} onChange={setHazardFilter}
      size="small" style={{ width: 158 }}
    >
      {['LOW','MEDIUM','HIGH','CRITICAL'].map(h => {
        const hs = getHazardStyle(h);
        return (
          <Select.Option key={h} value={h}>
            <span style={{ color: hs.color, marginRight: 5, fontWeight: 700 }}>⚠</span>
            {h.charAt(0) + h.slice(1).toLowerCase()} Hazard
          </Select.Option>
        );
      })}
    </Select>

    {(typeFilter || statusFilter || hazardFilter) && (
      <Button size="small" type="link" style={{ color: '#EF4444', padding: '0 4px', fontSize: 12 }} onClick={onClear}>
        ✕ Clear
      </Button>
    )}
  </>
);

/* ─────────────────────────────────────────────────────────────────
   MUSTER POINTS TAB
   Separate create/edit form and live monitoring for MUSTER_POINT zones.
───────────────────────────────────────────────────────────────── */
function MusterPointsTab({ musterPoints, isLoading }) {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing,   setEditing]   = useState(null);
  const [musterForm] = Form.useForm();

  const { data: activeEventsRaw } = useQuery({
    queryKey: ['muster-events-active'],
    queryFn:  () => apiService.get('/api/mustering/events/?status=0'),
    refetchInterval: 10000,
  });
  const activeEvents   = Array.isArray(activeEventsRaw) ? activeEventsRaw : [];
  const hasActiveEvent = activeEvents.length > 0;

  const { data: termRaw } = useQuery({
    queryKey: ['adms-terminals'],
    queryFn:  () => apiService.get('/api/device/terminals/'),
  });
  const terminals = Array.isArray(termRaw?.data) ? termRaw.data
                  : Array.isArray(termRaw) ? termRaw : [];

  const openCreate = () => {
    setEditing(null);
    musterForm.resetFields();
    musterForm.setFieldsValue({ status: 'ACTIVE' });
    setModalOpen(true);
  };
  const openEdit = (mp) => {
    setEditing(mp);
    musterForm.setFieldsValue({
      name: mp.name, code: mp.code, status: mp.status,
      reader_sn: mp.reader_sn, evac_point: mp.evac_point,
      evac_gps: mp.evac_gps, max_capacity: mp.max_capacity,
      state: mp.state, latitude: mp.latitude, longitude: mp.longitude,
    });
    setModalOpen(true);
  };

  const saveMutation = useMutation({
    mutationFn: (values) => editing
      ? apiService.put(`/api/v1/zones/${editing.id}/`, { ...values, zone_type: 'MUSTER_POINT' })
      : apiService.post('/api/v1/zones/', { ...values, zone_type: 'MUSTER_POINT' }),
    onSuccess: () => {
      message.success(editing ? 'Muster point updated' : 'Muster point created');
      queryClient.invalidateQueries({ queryKey: ['zones-dashboard'] });
      setModalOpen(false);
      setEditing(null);
      musterForm.resetFields();
    },
    onError: (e) => message.error(e?.detail || e?.message || 'Save failed'),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ id }) => apiService.delete(`/api/v1/zones/${id}/`),
    onSuccess: () => {
      message.success('Muster point deleted');
      queryClient.invalidateQueries({ queryKey: ['zones-dashboard'] });
    },
    onError: (e) => message.error(e?.detail || e?.message || 'Delete failed'),
  });

  return (
    <div>
      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <span style={{ fontWeight: 700, fontSize: 15, color: '#1f2937' }}>Mustering Points</span>
          <span style={{ fontSize: 12, color: '#9CA3AF', marginLeft: 8 }}>
            {musterPoints.length} configured
          </span>
          {hasActiveEvent && (
            <Tag color="error" style={{ marginLeft: 8 }}>
              {activeEvents.length} Active Event{activeEvents.length > 1 ? 's' : ''}
            </Tag>
          )}
        </div>
        <Button type="primary" icon={<PlusOutlined />} size="small"
          style={{ background: '#10B981', borderColor: '#10B981', fontWeight: 600 }}
          onClick={openCreate}>
          Add Muster Point
        </Button>
      </div>

      {/* Active event alert */}
      {hasActiveEvent && (
        <Alert
          type="warning" showIcon style={{ marginBottom: 16 }}
          message="Muster Event in Progress"
          description="Personnel are actively scanning in. Check-in counts below update every 10 seconds."
        />
      )}

      <Spin spinning={isLoading}>
        {musterPoints.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <SafetyOutlined style={{ fontSize: 48, color: '#D1D5DB', marginBottom: 12, display: 'block' }} />
            <div style={{ color: '#9CA3AF', fontSize: 14, marginBottom: 16 }}>
              No muster points configured. Add your first emergency assembly area.
            </div>
            <Button type="primary" icon={<PlusOutlined />}
              style={{ background: '#10B981', borderColor: '#10B981' }}
              onClick={openCreate}>Add First Muster Point</Button>
          </div>
        ) : (
          <Row gutter={[16, 16]}>
            {musterPoints.map(mp => {
              const count = mp.current_personnel_count ?? 0;
              const cap   = mp.max_capacity ?? 0;
              const pct   = cap > 0 ? Math.min(Math.round((count / cap) * 100), 100) : null;
              const isOver = cap > 0 && count > cap;
              return (
                <Col key={mp.id} xs={24} sm={12} lg={8} xl={6}>
                  <Card
                    size="small"
                    style={{
                      borderRadius: 12,
                      border: `2px solid ${hasActiveEvent ? '#10B981' : '#e2e8f0'}`,
                      boxShadow: hasActiveEvent ? '0 4px 16px rgba(16,185,129,0.15)' : '0 2px 8px rgba(0,0,0,0.06)',
                    }}
                    styles={{ body: { padding: '14px 16px' } }}
                    actions={[
                      <EditOutlined key="edit" title="Edit" onClick={() => openEdit(mp)} />,
                      <Popconfirm key="del" title="Delete this muster point?" okText="Delete" okButtonProps={{ danger: true }}
                        onConfirm={() => deleteMutation.mutate({ id: mp.id })}>
                        <DeleteOutlined style={{ color: '#ef4444' }} />
                      </Popconfirm>,
                    ]}
                  >
                    {/* Header */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 10 }}>
                      <div style={{
                        width: 40, height: 40, borderRadius: 10, flexShrink: 0,
                        background: 'linear-gradient(135deg,#10B981,#059669)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: 'white', fontSize: 18,
                        boxShadow: '0 2px 8px rgba(16,185,129,0.35)',
                      }}><SafetyOutlined /></div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 700, fontSize: 13.5, color: '#111827', lineHeight: 1.25,
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {mp.evac_point || mp.name}
                        </div>
                        <div style={{ fontSize: 11, color: '#9CA3AF', fontFamily: 'monospace', letterSpacing: '0.04em', marginTop: 2 }}>
                          {mp.code}
                        </div>
                      </div>
                      <Badge status={mp.status === 'ACTIVE' ? 'success' : 'default'} />
                    </div>

                    {/* Reader info — matched against terminal registry */}
                    {(() => {
                      const term = terminals.find(t => t.sn === mp.reader_sn);
                      const isOnline = term?.status?.toLowerCase() === 'online';
                      const doors = mp.door_count || 0;
                      const doorsNote = doors > 0 && (
                        <div style={{ fontSize: 11.5, color: '#16a34a', marginBottom: 8, fontWeight: 600 }}>
                          <ApiOutlined style={{ fontSize: 11, marginRight: 5 }} />
                          {doors} controller door{doors !== 1 ? 's' : ''} count people safe here
                        </div>
                      );
                      if (term && (term.reader_purpose || 'ATTENDANCE') === 'ATTENDANCE' && term.device_type !== 2) return (
                        <>
                          {doorsNote}
                          <div style={{ fontSize: 11.5, color: '#b45309', marginBottom: 8, fontWeight: 600 }}>
                            <WifiOutlined style={{ fontSize: 11, marginRight: 5 }} />
                            {term.alias || term.sn} is a T&amp;A reader — it does not count anyone safe. Choose an access or mustering reader.
                          </div>
                        </>
                      );
                      if (!mp.reader_sn && doors > 0) return doorsNote;
                      if (mp.reader_sn) return (
                        <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6,
                          background: term ? (isOnline ? '#f0fdf4' : '#fafafa') : '#fff7ed',
                          border: `1px solid ${term ? (isOnline ? '#86efac' : '#d1d5db') : '#fbbf24'}`,
                          borderRadius: 6, padding: '4px 8px' }}>
                          <div style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                            background: term ? (isOnline ? '#22c55e' : '#9ca3af') : '#f59e0b' }} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 11.5, fontWeight: 600, color: '#374151',
                              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {term ? (term.alias || `Terminal-${term.sn}`) : mp.reader_sn}
                            </div>
                            <div style={{ fontSize: 10, color: '#9ca3af', fontFamily: 'monospace' }}>
                              {mp.reader_sn}{term && !term.alias ? '' : term ? ` · ${term.sn}` : ''}
                            </div>
                          </div>
                          <span style={{ fontSize: 9.5, fontWeight: 700,
                            color: term ? (isOnline ? '#16a34a' : '#6b7280') : '#b45309',
                            whiteSpace: 'nowrap' }}>
                            {term ? (isOnline ? 'ONLINE' : 'OFFLINE') : 'NOT REG.'}
                          </span>
                        </div>
                      );
                      return (
                        <div style={{ fontSize: 11.5, color: '#EF4444', marginBottom: 8,
                          display: 'flex', alignItems: 'center', gap: 5, fontWeight: 600 }}>
                          <WifiOutlined style={{ fontSize: 11 }} /> No headcount reader assigned
                        </div>
                      );
                    })()}

                    {/* Live count — monitoring mode during active event */}
                    {hasActiveEvent ? (
                      <div style={{ background: '#f0fdf4', borderRadius: 8, padding: '8px 10px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                          <span style={{ fontSize: 12, color: '#374151', fontWeight: 600 }}>Check-ins</span>
                          <span style={{ fontSize: 16, fontWeight: 800,
                            color: isOver ? '#EF4444' : '#10B981' }}>
                            {count}{cap > 0 ? ` / ${cap}` : ''}
                          </span>
                        </div>
                        {cap > 0 && (
                          <Progress
                            percent={pct} size="small" showInfo={false}
                            strokeColor={isOver ? '#EF4444' : '#10B981'}
                            trailColor="#d1fae5"
                          />
                        )}
                      </div>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <TeamOutlined style={{ color: '#9CA3AF', fontSize: 13 }} />
                        <span style={{ fontSize: 12, color: '#374151' }}>{count} personnel</span>
                        {cap > 0 && <span style={{ fontSize: 11, color: '#9CA3AF' }}>/ {cap} capacity</span>}
                      </div>
                    )}

                    {/* GPS */}
                    {mp.evac_gps && (
                      <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 6,
                        display: 'flex', alignItems: 'center', gap: 4 }}>
                        <EnvironmentOutlined style={{ fontSize: 10 }} />{mp.evac_gps}
                      </div>
                    )}
                  </Card>
                </Col>
              );
            })}
          </Row>
        )}
      </Spin>

      {/* Create / Edit Modal */}
      <Modal
        title={
          <Space>
            <span style={{ fontSize: 18 }}>🟢</span>
            {editing ? `Edit Muster Point — ${editing.name}` : 'New Mustering Point'}
          </Space>
        }
        open={modalOpen}
        onOk={() => musterForm.validateFields().then(saveMutation.mutate).catch(() => {})}
        onCancel={() => { setModalOpen(false); setEditing(null); musterForm.resetFields(); }}
        okText={editing ? 'Update' : 'Create Muster Point'}
        confirmLoading={saveMutation.isPending}
        width={580} destroyOnHidden
      >
        <Alert
          type="success" showIcon style={{ marginBottom: 16 }}
          message="Emergency Assembly Area"
          description="Personnel scan in here during a muster to be recorded as safe. This zone is separate from regular access/work zones."
        />
        <Form form={musterForm} layout="vertical" size="middle">
          <Row gutter={16}>
            <Col span={14}>
              <Form.Item name="name" label="Muster Point Name" rules={[{ required: true, message: 'Required' }]}>
                <Input placeholder="e.g. Muster Station Alpha" />
              </Form.Item>
            </Col>
            <Col span={10}>
              <Form.Item name="code" label="Code" rules={[{ required: true, message: 'Required' }]}>
                <Input placeholder="e.g. MSP-001" disabled={!!editing} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="evac_point" label="Assembly Point Display Name"
            tooltip="Name shown on muster dashboards and headcount screens">
            <Input placeholder="e.g. Lifeboat Station 3 / Forward Assembly Area" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={14}>
              <Form.Item name="reader_sn" label="Headcount Reader"
                tooltip="A standalone access or mustering reader where people scan to be marked SAFE during a muster. Doors on the ZKTeco controllers count too — assign them to this muster point with Doors on the Zones tab. T&A readers never count anyone safe.">
                <Select
                  showSearch
                  allowClear
                  placeholder="Select a reader terminal..."
                  optionFilterProp="label"
                  notFoundContent={
                    <div style={{ textAlign: 'center', padding: '8px 0', color: '#9ca3af', fontSize: 12 }}>
                      No registered terminals found
                    </div>
                  }
                >
                  {terminals.filter(t => (t.reader_purpose || 'ATTENDANCE') !== 'ATTENDANCE' || t.device_type === 2).map(t => {
                    const isOnline = t.status?.toLowerCase() === 'online';
                    const inUse = musterPoints.find(mp => mp.reader_sn === t.sn && mp.id !== editing?.id);
                    return (
                      <Select.Option key={t.sn} value={t.sn} label={`${t.alias || t.sn} ${t.sn}`}>
                        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                          <Space size={6}>
                            <div style={{ width: 7, height: 7, borderRadius: '50%',
                              background: isOnline ? '#22c55e' : '#9ca3af', flexShrink: 0 }} />
                            <div>
                              <div style={{ fontWeight: 600, fontSize: 12.5 }}>
                                {t.alias || `Terminal-${t.sn}`}
                              </div>
                              <div style={{ fontSize: 10.5, color: '#9ca3af', fontFamily: 'monospace' }}>
                                {t.sn}{t.ip_address ? ` · ${t.ip_address}` : ''}
                              </div>
                            </div>
                          </Space>
                          <Space size={4}>
                            <Tag color={isOnline ? 'success' : 'default'} style={{ margin: 0, fontSize: 10 }}>
                              {isOnline ? 'Online' : 'Offline'}
                            </Tag>
                            {inUse && (
                              <Tag color="warning" style={{ margin: 0, fontSize: 10 }}>
                                → {inUse.name}
                              </Tag>
                            )}
                          </Space>
                        </Space>
                      </Select.Option>
                    );
                  })}
                </Select>
              </Form.Item>
            </Col>
            <Col span={10}>
              <Form.Item name="max_capacity" label="Capacity">
                <InputNumber style={{ width: '100%' }} min={1} placeholder="Max persons" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="evac_gps" label="Assembly GPS"
                tooltip="Format: lat,lon — e.g. 5.5557,5.7440">
                <Input placeholder="5.5557,5.7440" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="status" label="Status" initialValue="ACTIVE">
                <Select>
                  {['ACTIVE','INACTIVE','MAINTENANCE'].map(s => (
                    <Select.Option key={s} value={s}>{s.charAt(0) + s.slice(1).toLowerCase()}</Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Divider style={{ margin: '4px 0 12px' }} />
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="state" label="Area / Location">
                <Input placeholder="e.g. Offshore, Deck 3" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="latitude" label="Latitude"
                rules={[{ type: 'number', min: -90, max: 90 }]}>
                <InputNumber style={{ width: '100%' }} step={0.0001} precision={6} placeholder="5.5557" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="longitude" label="Longitude"
                rules={[{ type: 'number', min: -180, max: 180 }]}>
                <InputNumber style={{ width: '100%' }} step={0.0001} precision={6} placeholder="5.7440" />
              </Form.Item>
            </Col>
          </Row>
        </Form>

        {/* Reader → Emergency flow explanation */}
        <div style={{ marginTop: 8, background: '#f8fafc', border: '1px solid #e2e8f0',
          borderRadius: 8, padding: '10px 14px' }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: '#475569', marginBottom: 8,
            display: 'flex', alignItems: 'center', gap: 6 }}>
            <InfoCircleOutlined style={{ color: '#0284c7' }} />
            How muster point readers work during an emergency
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 0 }}>
            {[
              { icon: '1', color: '#7c3aed', bg: '#f3e8ff', title: 'Assign reader here', desc: 'Link a ZKTeco terminal to this muster point.' },
              { icon: '2', color: '#0284c7', bg: '#e0f2fe', title: 'Emergency declared', desc: 'All POB personnel are flagged as MISSING. Zone occupancy counts reset to 0.' },
              { icon: '3', color: '#059669', bg: '#d1fae5', title: 'Staff scan at reader', desc: 'Each badge-scan marks that person as SAFE in the muster event log.' },
              { icon: '4', color: '#dc2626', bg: '#fee2e2', title: 'Unscanned = rescue', desc: 'Remaining MISSING persons show their last-known zone to guide rescue teams.' },
            ].map((step, i, arr) => (
              <React.Fragment key={i}>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
                  <div style={{ width: 26, height: 26, borderRadius: '50%', background: step.bg,
                    border: `2px solid ${step.color}`, display: 'flex', alignItems: 'center',
                    justifyContent: 'center', fontWeight: 800, fontSize: 12, color: step.color, marginBottom: 5 }}>
                    {step.icon}
                  </div>
                  <div style={{ fontSize: 10.5, fontWeight: 700, color: '#1e293b', lineHeight: 1.3 }}>{step.title}</div>
                  <div style={{ fontSize: 10, color: '#64748b', marginTop: 2, lineHeight: 1.3 }}>{step.desc}</div>
                </div>
                {i < arr.length - 1 && (
                  <div style={{ alignSelf: 'flex-start', marginTop: 11, color: '#cbd5e1', fontSize: 14, flexShrink: 0 }}>›</div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </Modal>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   MAIN COMPONENT
───────────────────────────────────────────────────────────────── */
const ZoneManagement = () => {
  const { message, modal } = App.useApp();
  const [activeTab,        setActiveTab]        = useState('zones');
  const [detailZoneId,     setDetailZoneId]     = useState(null);
  const [editingZone,      setEditingZone]      = useState(null);
  const [isModalOpen,      setIsModalOpen]      = useState(false);
  const [readerZone,       setReaderZone]       = useState(null);
  const [isReaderModalOpen,setIsReaderModalOpen]= useState(false);
  const [searchVal,        setSearchVal]        = useState('');
  const [typeFilter,       setTypeFilter]       = useState(null);
  const [statusFilter,     setStatusFilter]     = useState(null);
  const [hazardFilter,     setHazardFilter]     = useState(null);
  const [sortBy,           setSortBy]           = useState('pob_desc');
  const [zoneView,         setZoneView]         = useState('cards');
  const [selectedRowKeys,  setSelectedRowKeys]  = useState([]);
  const [wsStatus,         setWsStatus]         = useState('connecting');
  const wsRef = useRef(null);
  const [form]       = Form.useForm();
  const [readerForm] = Form.useForm();
  const queryClient  = useQueryClient();

  const { data: dashData, isLoading: dashLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ['zones-dashboard'],
    queryFn:  () => apiService.get('/api/v1/zones/dashboard'),
    refetchInterval: 10000,
  });

  const { data: allZonesForParent } = useQuery({
    queryKey: ['zones-for-parent'],
    queryFn:  () => apiService.get('/api/v1/zones/'),
    enabled: isModalOpen,
  });

  const { data: devicesData } = useQuery({
    queryKey: ['available-devices'],
    queryFn:  () => apiService.get('/api/v1/zones/available-devices'),
    enabled: isReaderModalOpen,
  });

  const { data: modalReadersData, isLoading: modalReadersLoading } = useQuery({
    queryKey: ['zone-readers', readerZone?.id],
    queryFn:  () => apiService.get(`/api/v1/zones/${readerZone?.id}/readers`),
    enabled:  isReaderModalOpen && !!readerZone?.id,
  });

  const { data: doorsData } = useQuery({
    queryKey: ['available-doors'],
    queryFn:  () => apiService.get('/api/v1/zones/available-doors'),
    enabled: isReaderModalOpen,
  });
  const { data: modalDoorsData, isLoading: modalDoorsLoading } = useQuery({
    queryKey: ['zone-doors', readerZone?.id],
    queryFn:  () => apiService.get(`/api/v1/zones/${readerZone?.id}/doors`),
    enabled:  isReaderModalOpen && !!readerZone?.id,
  });

  const zones = Array.isArray(dashData) ? dashData : [];
  const devices = Array.isArray(devicesData) ? devicesData : [];
  const currentModalReaders = Array.isArray(modalReadersData) ? modalReadersData : [];
  const availableDoors = Array.isArray(doorsData) ? doorsData : [];
  const currentModalDoors = Array.isArray(modalDoorsData) ? modalDoorsData : [];

  const musterPoints = useMemo(() => zones.filter(z => z.zone_type === 'MUSTER_POINT'), [zones]);

  const HAZARD_ORDER = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };

  const filtered = useMemo(() => {
    const result = zones.filter(z => {
      if (z.zone_type === 'MUSTER_POINT') return false;
      if (searchVal.trim()) {
        const q = searchVal.toLowerCase();
        if (!z.name.toLowerCase().includes(q) && !z.code.toLowerCase().includes(q) && !(z.state || '').toLowerCase().includes(q)) return false;
      }
      if (typeFilter   && z.zone_type    !== typeFilter)   return false;
      if (statusFilter && z.status       !== statusFilter) return false;
      if (hazardFilter && z.hazard_level !== hazardFilter) return false;
      return true;
    });

    return [...result].sort((a, b) => {
      switch (sortBy) {
        case 'pob_desc':  return (b.current_personnel_count ?? 0) - (a.current_personnel_count ?? 0);
        case 'cap_pct': {
          const pA = a.max_capacity ? (a.current_personnel_count ?? 0) / a.max_capacity : 0;
          const pB = b.max_capacity ? (b.current_personnel_count ?? 0) / b.max_capacity : 0;
          return pB - pA;
        }
        case 'hazard':    return (HAZARD_ORDER[b.hazard_level] || 0) - (HAZARD_ORDER[a.hazard_level] || 0);
        case 'activity':  return new Date(b.last_activity_time || 0) - new Date(a.last_activity_time || 0);
        default:          return a.name.localeCompare(b.name);
      }
    });
  }, [zones, typeFilter, statusFilter, hazardFilter, searchVal, sortBy]); // eslint-disable-line react-hooks/exhaustive-deps

  const hasFilters = searchVal || typeFilter || statusFilter || hazardFilter;

  // Operational zones exclude muster/assembly points — those are safe destinations,
  // not tracked-occupancy zones, so they get their own count (see musterPoints above).
  const { totalPOB, operationalZones, activeZones, totalReaders, alerts } = useMemo(() => {
    const ops = zones.filter(z => z.zone_type !== 'MUSTER_POINT');
    return {
      totalPOB:        zones.reduce((s, z) => s + (z.current_personnel_count || 0), 0),
      operationalZones: ops.length,
      activeZones:     ops.filter(z => z.is_active && z.status === 'ACTIVE').length,
      totalReaders:    zones.reduce((s, z) => s + zoneReaders(z), 0),
      alerts:          zones.filter(z => ['EMERGENCY','LOCKDOWN'].includes(z.status)).length,
    };
  }, [zones]);

  // Always reflects the latest polling data — no manual sync needed
  const detailZone = useMemo(() => zones.find(z => z.id === detailZoneId) ?? null, [zones, detailZoneId]);

  const saveMutation = useMutation({
    mutationFn: (values) => editingZone
      ? apiService.put(`/api/v1/zones/${editingZone.id}/`, values)
      : apiService.post('/api/v1/zones/', values),
    onSuccess: () => {
      message.success(editingZone ? 'Zone updated' : 'Zone created');
      setIsModalOpen(false); setEditingZone(null); form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['zones-dashboard'] });
    },
    onError: err => message.error(err?.message || 'Failed to save zone'),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ id, cascade = false }) =>
      apiService.delete(`/api/v1/zones/${id}/${cascade ? '?cascade=true' : ''}`),
    onSuccess: (res, { id }) => {
      message.success(res?.message || 'Zone deleted');
      if (detailZoneId === id) setDetailZoneId(null);
      queryClient.invalidateQueries({ queryKey: ['zones-dashboard'] });
    },
    onError: (err, vars) => {
      if (err?.message?.includes('sub-zone')) {
        Modal.confirm({
          title: 'Zone has sub-zones',
          icon: <ExclamationCircleOutlined style={{ color: '#faad14' }} />,
          content: (
            <div>
              <p>{err.message}</p>
              <p>Do you want to delete this zone <strong>and all its sub-zones</strong>?</p>
            </div>
          ),
          okText: 'Delete All',
          okButtonProps: { danger: true },
          cancelText: 'Cancel',
          onOk: () => deleteMutation.mutateAsync({ id: vars.id, cascade: true }),
        });
      } else {
        message.error(err?.message || 'Delete failed');
      }
    },
  });

  const assignReaderMutation = useMutation({
    mutationFn: (values) => {
      const ids = Array.isArray(values.device_id) ? values.device_id : [values.device_id];
      return Promise.all(ids.map(id =>
        apiService.post(`/api/v1/zones/${readerZone?.id}/assign-reader`, { ...values, device_id: id })
      ));
    },
    onSuccess: (results) => {
      const moved = results.some(r => r?.moved_from);
      message.success(moved ? 'Reader(s) moved to zone' : 'Reader(s) assigned to zone');
      readerForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['zones-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['zone-readers', readerZone?.id] });
      queryClient.invalidateQueries({ queryKey: ['adms-terminals'] });
      queryClient.invalidateQueries({ queryKey: ['available-devices'] });
    },
    onError: err => message.error(err?.message || 'Assignment failed'),
  });

  const removeReaderModalMutation = useMutation({
    mutationFn: ({ zoneId, readerId }) => apiService.delete(`/api/v1/zones/${zoneId}/readers/${readerId}`),
    onSuccess: () => {
      message.success('Reader removed from zone');
      queryClient.invalidateQueries({ queryKey: ['zone-readers', readerZone?.id] });
      queryClient.invalidateQueries({ queryKey: ['zones-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['available-devices'] });
    },
    onError: err => message.error(err?.message || 'Failed to remove reader'),
  });

  const assignDoorMutation = useMutation({
    mutationFn: (values) => {
      const keys = Array.isArray(values.door) ? values.door : [values.door];
      return Promise.all(keys.map(k => {
        const [cid, dn] = String(k).split(':').map(Number);
        return apiService.post(`/api/v1/zones/${readerZone?.id}/assign-door`, { controller_id: cid, door_no: dn });
      }));
    },
    onSuccess: () => {
      message.success('Door(s) assigned to zone');
      readerForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['zones-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['zone-doors', readerZone?.id] });
      queryClient.invalidateQueries({ queryKey: ['available-doors'] });
    },
    onError: err => message.error(err?.message || 'Assignment failed'),
  });

  const removeDoorMutation = useMutation({
    mutationFn: ({ zoneId, controllerId, doorNo }) =>
      apiService.delete(`/api/v1/zones/${zoneId}/doors?controller_id=${controllerId}&door_no=${doorNo}`),
    onSuccess: () => {
      message.success('Door removed from zone');
      queryClient.invalidateQueries({ queryKey: ['zone-doors', readerZone?.id] });
      queryClient.invalidateQueries({ queryKey: ['zones-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['available-doors'] });
    },
    onError: err => message.error(err?.message || 'Failed to remove door'),
  });

  const patchStatusM = useMutation({
    mutationFn: ({ id, status }) => apiService.patch(`/api/v1/zones/${id}/status`, { status }),
    onSuccess: (r, vars) => {
      const d = r?.doors;
      if (d) {
        const bad = (d.failed_doors || 0) > 0 || !d.total_doors;
        (bad ? message.warning : message.success)(`Zone ${vars.status === 'LOCKDOWN' ? 'locked down' : `→ ${vars.status.toLowerCase()}`}: ${d.message}`, 8);
      } else message.success(`Zone status → ${vars.status.toLowerCase()}`);
      queryClient.invalidateQueries({ queryKey: ['zones-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['em-door-state'] });
    },
    onError: err => message.error(err?.message || 'Status update failed'),
  });

  const resetOccupancyM = useMutation({
    mutationFn: (zoneId) => apiService.post(`/api/v1/zones/${zoneId}/reset-occupancy`, {}),
    onSuccess: (data) => {
      const n = data?.cleared_count ?? 0;
      message.success(n > 0
        ? `Occupancy reset. ${n} stale check-in${n !== 1 ? 's' : ''} cleared.`
        : 'Zone occupancy reset to 0.');
      queryClient.invalidateQueries({ queryKey: ['zones-dashboard'] });
    },
    onError: err => message.error(err?.message || 'Reset failed'),
  });

  const exportCSV = () => {
    const rows = selectedRowKeys.length > 0
      ? filtered.filter(z => selectedRowKeys.includes(z.id))
      : filtered;
    const header = ['Name','Code','Type','Status','Hazard','POB','Capacity','State','Readers','Latitude','Longitude'];
    const lines = rows.map(z => [
      z.name, z.code, z.zone_type, z.status, z.hazard_level,
      z.current_personnel_count ?? 0,
      z.max_capacity ? `${z.current_personnel_count ?? 0}/${z.max_capacity}` : '',
      z.state || '', zoneReaders(z),
      z.latitude || '', z.longitude || '',
    ].map(v => `"${String(v).replace(/"/g,'""')}"`).join(','));
    const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' });
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(blob),
      download: `zones_${new Date().toISOString().slice(0,10)}.csv`,
    });
    a.click(); URL.revokeObjectURL(a.href);
  };

  const handleEdit = (zone) => {
    setEditingZone(zone);
    // Only pass known flat fields — passing the full zone object can include
    // nested relational data that triggers AntD's circular-reference warning.
    form.setFieldsValue({
      name: zone.name,
      code: zone.code,
      zone_type: zone.zone_type,
      status: zone.status,
      hazard_level: zone.hazard_level,
      state: zone.state,
      latitude: zone.latitude,
      longitude: zone.longitude,
      max_capacity: zone.max_capacity,
      description: zone.description,
      parent_zone_id: zone.parent_zone_id,
      tile_position: zone.tile_position,
      display_color: zone.display_color,
      reader_sn: zone.reader_sn,
      evac_point: zone.evac_point,
      evac_gps: zone.evac_gps,
      is_site_boundary: !!zone.is_site_boundary,
    });
    setIsModalOpen(true);
  };
  const handleAssignReader = (zone) => { setReaderZone(zone); setIsReaderModalOpen(true); };

  useEffect(() => {
    let retryTimer = null;
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${proto}//${window.location.host}/api/v1/zones/ws`);
      wsRef.current = ws;
      setWsStatus('connecting');
      ws.onopen  = () => setWsStatus('connected');
      ws.onclose = () => { setWsStatus('disconnected'); retryTimer = setTimeout(connect, 5000); };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="zone-module">
      <Card
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', overflow: 'visible' }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>Zone Management</div>
              <div style={{ fontSize: 12, color: '#64748b', fontWeight: 400, marginTop: 2 }}>
                Who is where on site — from ZKTeco access-control doors and readers
              </div>
            </div>
            <Space size="middle" style={{ overflow: 'visible' }}>
              {/* WebSocket live status */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{
                  width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                  background: wsStatus === 'connected' ? '#10B981' : wsStatus === 'connecting' ? '#F59E0B' : '#6B7280',
                  animation: wsStatus === 'connected' ? 'zoneDotPulse 2s infinite' : 'none',
                }} />
                <span style={{
                  fontSize: 10.5, fontWeight: 700, letterSpacing: '0.06em',
                  color: wsStatus === 'connected' ? '#10B981' : wsStatus === 'connecting' ? '#F59E0B' : '#6B7280',
                }}>
                  {wsStatus === 'connected' ? 'LIVE' : wsStatus === 'connecting' ? 'CONNECTING' : 'OFFLINE'}
                </span>
              </div>
              <Badge count={totalPOB} showZero color="#0078D4">
                <TeamOutlined style={{ fontSize: 16 }} />
              </Badge>
              <Badge count={activeZones} showZero color="#059669">
                <CheckCircleOutlined style={{ fontSize: 16 }} />
              </Badge>
              {alerts > 0 && (
                <Badge count={alerts} color="#DC2626">
                  <AlertOutlined style={{ fontSize: 16 }} />
                </Badge>
              )}
              <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={dashLoading} size="small">
                Refresh
              </Button>
              <Button type="primary" icon={<PlusOutlined />} size="small" style={{ fontWeight: 600 }}
                onClick={() => { setEditingZone(null); form.resetFields(); setIsModalOpen(true); }}>
                New Zone
              </Button>
            </Space>
          </div>
        }
        styles={{ header: { overflow: 'visible' } }}
      >
        {/* ── KPI strip ── */}
        <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
          {[
            { label: 'Total Personnel On Board', value: totalPOB,            color: '#0078D4', icon: <TeamOutlined /> },
            { label: 'Active Zones',              value: activeZones,         color: '#059669', icon: <CheckCircleOutlined /> },
            { label: 'Zones',                     value: operationalZones,    color: '#374151', icon: <RadarChartOutlined /> },
            { label: 'Muster Points',             value: musterPoints.length, color: '#10B981', icon: <SafetyOutlined /> },
            { label: 'Doors & Readers',           value: totalReaders,        color: '#6D28D9', icon: <ApiOutlined /> },
            { label: 'Alerts',                    value: alerts,              color: alerts > 0 ? '#DC2626' : '#94a3b8', icon: <AlertOutlined /> },
          ].map(s => (
            <Col key={s.label} xs={12} sm={4}>
              <div style={{
                background: '#fff', borderRadius: 10, padding: '14px 18px',
                border: `1px solid ${s.label === 'Alerts' && alerts > 0 ? '#fecaca' : '#f0f0f0'}`,
                borderTop: `3px solid ${s.color}`,
                boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                display: 'flex', alignItems: 'center', gap: 12,
              }}>
                <div style={{ width: 36, height: 36, borderRadius: 9, background: `${s.color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: s.color, fontSize: 16, flexShrink: 0 }}>
                  {s.icon}
                </div>
                <div>
                  <div style={{ fontSize: 11, color: '#8c8c8c', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.5px' }}>{s.label}</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: s.color, lineHeight: 1.2, marginTop: 2 }}>{s.value ?? 0}</div>
                </div>
              </div>
            </Col>
          ))}
        </Row>

        {/* Emergency / lockdown banner */}
        {zones.some(z => ['EMERGENCY','LOCKDOWN'].includes(z.status)) && (
          <Alert
            type="error" showIcon
            message={
              <span>
                <strong>Emergency Alert:</strong>{' '}
                {zones.filter(z => ['EMERGENCY','LOCKDOWN'].includes(z.status)).map(z => `${z.name} (${z.status})`).join(' · ')}
              </span>
            }
            style={{ marginBottom: 12, borderRadius: 10 }}
          />
        )}

        {/* Capacity warning banner */}
        {zones.some(z => z.max_capacity && (z.current_personnel_count ?? 0) / z.max_capacity >= 0.8) && (
          <Alert
            type="warning" showIcon closable
            message={
              <span>
                <strong>Capacity Warning:</strong>{' '}
                {zones
                  .filter(z => z.max_capacity && (z.current_personnel_count ?? 0) / z.max_capacity >= 0.8)
                  .map(z => `${z.name} (${Math.round((z.current_personnel_count ?? 0) / z.max_capacity * 100)}%)`)
                  .join(' · ')}{' '}at or above 80% capacity.
              </span>
            }
            style={{ marginBottom: 12, borderRadius: 10 }}
          />
        )}

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          tabBarStyle={{ marginBottom: 16 }}
          tabBarExtraContent={
            (activeTab === 'cards' || activeTab === 'list') ? (
              <Input
                prefix={<SearchOutlined style={{ color: '#9CA3AF' }} />}
                placeholder="Search zones…"
                value={searchVal}
                onChange={e => setSearchVal(e.target.value)}
                allowClear
                size="small"
                style={{ width: 200, borderRadius: 6 }}
              />
            ) : null
          }
          items={[
            {
              key: 'zones',
              label: <Space size={5}><TeamOutlined />POB Dashboard</Space>,
              children: <POBDashboard onRefreshDash={() => refetch()} />,
            },
            {
              key: 'cards',
              label: <Space size={5}><GlobalOutlined />Zones</Space>,
              children: (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
                    <Segmented
                      value={zoneView}
                      onChange={setZoneView}
                      options={[
                        { label: 'Cards', value: 'cards', icon: <GlobalOutlined /> },
                        { label: 'Table', value: 'table', icon: <DashboardOutlined /> },
                      ]}
                    />
                  </div>
                  <div style={{ display: zoneView === 'cards' ? 'block' : 'none' }}>
                <Spin spinning={dashLoading}>
                  {/* Filter toolbar */}
                  <div style={{ marginBottom: 14, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <ZoneFilterBar
                      typeFilter={typeFilter} setTypeFilter={setTypeFilter}
                      statusFilter={statusFilter} setStatusFilter={setStatusFilter}
                      hazardFilter={hazardFilter} setHazardFilter={setHazardFilter}
                      onClear={() => { setSearchVal(''); setTypeFilter(null); setStatusFilter(null); setHazardFilter(null); }}
                    />

                    <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 11, color: '#9CA3AF', whiteSpace: 'nowrap' }}>Sort:</span>
                      {[
                        { key: 'pob_desc', label: 'POB ↓' },
                        { key: 'name',     label: 'Name'   },
                        { key: 'cap_pct',  label: 'Cap %'  },
                        { key: 'hazard',   label: 'Hazard' },
                        { key: 'activity', label: 'Recent' },
                      ].map(s => (
                        <button
                          key={s.key}
                          onClick={() => setSortBy(s.key)}
                          style={{
                            all: 'unset', cursor: 'pointer',
                            padding: '3px 10px', borderRadius: 20, fontSize: 11.5,
                            fontWeight: sortBy === s.key ? 700 : 500,
                            background: sortBy === s.key ? '#1D4ED8' : '#F3F4F6',
                            color: sortBy === s.key ? 'white' : '#374151',
                            border: `1px solid ${sortBy === s.key ? '#1D4ED8' : '#E5E7EB'}`,
                            transition: 'all 0.15s', whiteSpace: 'nowrap',
                          }}
                        >{s.label}</button>
                      ))}
                      <span style={{ fontSize: 12, color: '#9CA3AF', whiteSpace: 'nowrap', marginLeft: 6 }}>
                        {hasFilters ? `${filtered.length} of ${zones.length}` : zones.length} zone{zones.length !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>

                  {filtered.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '60px 0' }}>
                      <GlobalOutlined style={{ fontSize: 48, color: '#D1D5DB', marginBottom: 12, display: 'block' }} />
                      <div style={{ color: '#9CA3AF', fontSize: 14 }}>
                        {hasFilters ? 'No zones match your filters.' : 'No zones configured. Create your first zone.'}
                      </div>
                      {hasFilters && (
                        <Button type="link" size="small" style={{ marginTop: 8 }}
                          onClick={() => { setSearchVal(''); setTypeFilter(null); setStatusFilter(null); setHazardFilter(null); }}>
                          Clear all filters
                        </Button>
                      )}
                    </div>
                  ) : (
                    <Row gutter={[16, 16]}>
                      {filtered.map(zone => (
                        <Col key={zone.id} xs={24} sm={12} lg={8} xl={6}>
                          <ZoneCard
                            zone={zone}
                            onView={z => setDetailZoneId(z.id)}
                            onEdit={handleEdit}
                            onAssignReader={handleAssignReader}
                            onDelete={id => deleteMutation.mutate({ id })}
                            onStatusChange={(id, s) => (s === 'LOCKDOWN'
                              ? modal.confirm({
                                  title: 'Lock down this zone?', okType: 'danger', okText: 'Lock doors',
                                  content: "Every door into the zone is locked (fire exits stay free). Setting it back to Active unlocks them. The response team is alerted.",
                                  onOk: () => patchStatusM.mutate({ id, status: s }),
                                })
                              : patchStatusM.mutate({ id, status: s }))}
                            onResetOccupancy={id => resetOccupancyM.mutate(id)}
                          />
                        </Col>
                      ))}
                    </Row>
                  )}
                </Spin>
                  </div>
                  <div style={{ display: zoneView === 'table' ? 'block' : 'none' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 0, background: 'white', borderRadius: 14, border: '1px solid #E5E7EB', overflow: 'hidden', boxShadow: '0 2px 12px rgba(0,0,0,0.06)' }}>

                  {/* ── Toolbar ── */}
                  <div style={{
                    padding: '14px 18px', borderBottom: '1px solid #F3F4F6',
                    display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
                    background: '#FAFAFA',
                  }}>
                    {/* Filter chips */}
                    <ZoneFilterBar
                      typeFilter={typeFilter} setTypeFilter={setTypeFilter}
                      statusFilter={statusFilter} setStatusFilter={setStatusFilter}
                      hazardFilter={hazardFilter} setHazardFilter={setHazardFilter}
                      onClear={() => { setSearchVal(''); setTypeFilter(null); setStatusFilter(null); setHazardFilter(null); }}
                    />

                    <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
                      {hasFilters && (
                        <span style={{ fontSize: 12, color: '#6B7280' }}>
                          <span style={{ fontWeight: 700, color: '#1F2937' }}>{filtered.length}</span> of {zones.length} zones
                        </span>
                      )}
                      {!hasFilters && (
                        <span style={{ fontSize: 12, color: '#9CA3AF' }}>{zones.length} zone{zones.length !== 1 ? 's' : ''}</span>
                      )}
                      <Button
                        size="small"
                        icon={<DownloadOutlined />}
                        onClick={exportCSV}
                        style={{ borderRadius: 6 }}
                      >Export CSV</Button>
                    </div>
                  </div>

                  {/* ── Bulk action bar (visible only when rows are selected) ── */}
                  {selectedRowKeys.length > 0 && (
                    <div style={{
                      padding: '10px 18px',
                      background: 'linear-gradient(90deg, #EFF6FF, #DBEAFE)',
                      borderBottom: '1px solid #BFDBFE',
                      display: 'flex', alignItems: 'center', gap: 12,
                    }}>
                      <div style={{
                        width: 28, height: 28, borderRadius: 7,
                        background: 'linear-gradient(135deg,#1D4ED8,#3B82F6)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: 'white', fontSize: 13, fontWeight: 700, flexShrink: 0,
                      }}>{selectedRowKeys.length}</div>
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#1E3A8A' }}>
                        zone{selectedRowKeys.length !== 1 ? 's' : ''} selected
                      </span>
                      <div style={{ width: 1, height: 16, background: '#BFDBFE' }} />
                      <Button
                        size="small"
                        icon={<EyeOutlined />}
                        style={{ borderColor: '#93C5FD', color: '#1D4ED8', background: 'white', borderRadius: 6 }}
                        onClick={() => {
                          const zone = filtered.find(z => z.id === selectedRowKeys[0]);
                          if (zone) setDetailZoneId(zone.id);
                        }}
                        disabled={selectedRowKeys.length !== 1}
                      >View Detail</Button>
                      <Dropdown
                        menu={{
                          items: ['ACTIVE','INACTIVE','MAINTENANCE','EMERGENCY','LOCKDOWN'].map(s => {
                            const ss2 = getStatusStyle(s);
                            return {
                              key: s,
                              label: (
                                <div style={{ display:'flex',alignItems:'center',gap:8 }}>
                                  <div style={{ width:8,height:8,borderRadius:'50%',background:ss2.color,flexShrink:0 }} />
                                  <span style={{color:ss2.color,fontWeight:600,fontSize:12}}>{s.charAt(0)+s.slice(1).toLowerCase()}</span>
                                </div>
                              ),
                              onClick: () => {
                                Promise.all(selectedRowKeys.map(id => patchStatusM.mutateAsync({ id, status: s })))
                                  .then(() => { message.success(`${selectedRowKeys.length} zone(s) → ${s.toLowerCase()}`); setSelectedRowKeys([]); })
                                  .catch(() => message.error('Some status updates failed'));
                              },
                            };
                          }),
                        }}
                      >
                        <Button
                          size="small"
                          icon={<SwapOutlined />}
                          style={{ borderColor: '#93C5FD', color: '#1D4ED8', background: 'white', borderRadius: 6 }}
                        >Set Status <DownOutlined style={{ fontSize: 10 }} /></Button>
                      </Dropdown>
                      <Button
                        size="small"
                        icon={<DownloadOutlined />}
                        style={{ borderColor: '#93C5FD', color: '#0891b2', background: 'white', borderRadius: 6 }}
                        onClick={exportCSV}
                      >Export</Button>
                      <Popconfirm
                        title={`Delete ${selectedRowKeys.length} zone${selectedRowKeys.length !== 1 ? 's' : ''}?`}
                        description="This will permanently remove all selected zones and unassign their readers."
                        okText="Delete All" okButtonProps={{ danger: true }}
                        onConfirm={() => {
                          Promise.all(selectedRowKeys.map(id => deleteMutation.mutateAsync({ id })))
                            .then(() => { message.success(`${selectedRowKeys.length} zone(s) deleted`); setSelectedRowKeys([]); })
                            .catch(() => message.error('Some deletions failed'));
                        }}
                      >
                        <Button
                          size="small" danger
                          icon={<DeleteOutlined />}
                          style={{ borderRadius: 6 }}
                        >Delete Selected</Button>
                      </Popconfirm>
                      <Button
                        size="small" type="text"
                        style={{ color: '#6B7280', marginLeft: 'auto' }}
                        onClick={() => setSelectedRowKeys([])}
                      >✕ Deselect all</Button>
                    </div>
                  )}

                  {/* ── Table ── */}
                  <Table
                    dataSource={filtered}
                    loading={dashLoading}
                    rowKey="id"
                    size="middle"
                    scroll={{ x: 1260 }}
                    rowSelection={{
                      selectedRowKeys,
                      onChange: setSelectedRowKeys,
                      columnWidth: 44,
                      selections: [
                        Table.SELECTION_ALL,
                        Table.SELECTION_INVERT,
                        Table.SELECTION_NONE,
                      ],
                    }}
                    pagination={{
                      pageSize: 15,
                      showTotal: (t, r) => `Showing ${r[0]}–${r[1]} of ${t} zones`,
                      showSizeChanger: true,
                      pageSizeOptions: ['10','15','25','50'],
                      size: 'default',
                      style: { padding: '12px 18px', margin: 0, borderTop: '1px solid #F3F4F6' },
                    }}
                    rowClassName={r => ['EMERGENCY','LOCKDOWN'].includes(r.status) ? 'zone-row-alert' : ''}
                    style={{ borderRadius: 0 }}
                    columns={[
                      /* ── Zone name / code ── */
                      {
                        title: 'Zone', dataIndex: 'name', width: 220, fixed: 'left',
                        sorter: (a, b) => a.name.localeCompare(b.name),
                        render: (name, rec) => {
                          const zs = getZoneStyle(rec.zone_type);
                          return (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
                              <div style={{
                                width: 36, height: 36, borderRadius: 9, flexShrink: 0,
                                background: `linear-gradient(135deg, ${zs.dark}, ${zs.color})`,
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                color: 'white', fontSize: 15,
                                boxShadow: `0 2px 8px ${zs.color}44`,
                              }}>{zs.icon}</div>
                              <div>
                                <div style={{ fontWeight: 700, fontSize: 13.5, color: '#111827', lineHeight: 1.2 }}>{name}</div>
                                <div style={{ fontSize: 10.5, color: '#9CA3AF', fontFamily: 'monospace', marginTop: 2, letterSpacing: '0.02em' }}>{rec.code}</div>
                              </div>
                            </div>
                          );
                        },
                      },

                      /* ── Type ── */
                      {
                        title: 'Type', dataIndex: 'zone_type', width: 148,
                        filters: Object.entries(ZONE_TYPE_LABELS).map(([v, l]) => ({ text: l, value: v })),
                        onFilter: (v, r) => r.zone_type === v,
                        render: t => {
                          const zs = getZoneStyle(t);
                          return (
                            <div style={{
                              display: 'inline-flex', alignItems: 'center', gap: 5,
                              background: zs.bg, borderRadius: 6, padding: '4px 9px',
                              border: `1px solid ${zs.color}28`,
                            }}>
                              <span style={{ color: zs.color, fontSize: 11 }}>{zs.icon}</span>
                              <span style={{ color: zs.color, fontSize: 11.5, fontWeight: 600 }}>{ZONE_TYPE_LABELS[t] || t}</span>
                            </div>
                          );
                        },
                      },

                      /* ── Status (click to change) ── */
                      {
                        title: 'Status', dataIndex: 'status', width: 148,
                        filters: ['ACTIVE','INACTIVE','MAINTENANCE','EMERGENCY','LOCKDOWN'].map(s => ({ text: s.charAt(0)+s.slice(1).toLowerCase(), value: s })),
                        onFilter: (v, r) => r.status === v,
                        render: (s, record) => {
                          const ss = getStatusStyle(s);
                          return (
                            <Dropdown
                              trigger={['click']}
                              placement="bottomLeft"
                              menu={{
                                selectedKeys: [s],
                                items: ['ACTIVE','INACTIVE','MAINTENANCE','EMERGENCY','LOCKDOWN'].map(st => {
                                  const ss2 = getStatusStyle(st);
                                  return {
                                    key: st,
                                    label: (
                                      <div style={{ display:'flex',alignItems:'center',gap:8 }}>
                                        <div style={{ width:8,height:8,borderRadius:'50%',background:ss2.color,flexShrink:0 }} />
                                        <span style={{color:ss2.color,fontWeight:600,fontSize:12}}>{st.charAt(0)+st.slice(1).toLowerCase()}</span>
                                      </div>
                                    ),
                                    onClick: () => patchStatusM.mutate({ id: record.id, status: st }),
                                  };
                                }),
                              }}
                            >
                              <div style={{
                                display: 'inline-flex', alignItems: 'center', gap: 6,
                                background: ss.bg, borderRadius: 20, padding: '3px 10px',
                                border: `1px solid ${ss.border}`, cursor: 'pointer',
                              }}>
                                <div style={{ width: 6, height: 6, borderRadius: '50%', background: ss.color, flexShrink: 0, animation: ss.pulse ? 'zoneDotPulse 2s infinite' : 'none' }} />
                                <span style={{ fontSize: 11.5, fontWeight: 600, color: ss.color }}>{s.charAt(0) + s.slice(1).toLowerCase()}</span>
                                <DownOutlined style={{ fontSize: 8, color: ss.color, opacity: 0.5 }} />
                              </div>
                            </Dropdown>
                          );
                        },
                      },

                      /* ── Hazard ── */
                      {
                        title: 'Hazard', dataIndex: 'hazard_level', width: 118,
                        filters: ['LOW','MEDIUM','HIGH','CRITICAL'].map(h => ({ text: h, value: h })),
                        onFilter: (v, r) => r.hazard_level === v,
                        render: h => {
                          const hs = getHazardStyle(h);
                          return (
                            <div style={{
                              display: 'inline-flex', alignItems: 'center', gap: 5,
                              background: hs.bg, borderRadius: 6, padding: '3px 9px',
                              border: `1px solid ${hs.border}`,
                            }}>
                              <span style={{ fontSize: 11, color: hs.color, fontWeight: 700 }}>⚠</span>
                              <span style={{ fontSize: 11.5, fontWeight: 600, color: hs.color }}>{h.charAt(0) + h.slice(1).toLowerCase()}</span>
                            </div>
                          );
                        },
                      },

                      /* ── POB ── */
                      {
                        title: <span style={{ color: '#0078D4' }}>POB</span>,
                        dataIndex: 'current_personnel_count',
                        width: 80, align: 'center',
                        sorter: (a, b) => (a.current_personnel_count ?? 0) - (b.current_personnel_count ?? 0),
                        render: n => (
                          <div style={{
                            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                            minWidth: 40, height: 32, borderRadius: 8,
                            background: (n ?? 0) > 0 ? 'linear-gradient(135deg,#0078D4,#005A9E)' : '#F3F4F6',
                            boxShadow: (n ?? 0) > 0 ? '0 2px 8px rgba(0,120,212,0.35)' : 'none',
                          }}>
                            <span style={{
                              fontSize: (n ?? 0) >= 100 ? 15 : 18,
                              fontWeight: 900,
                              color: (n ?? 0) > 0 ? 'white' : '#D1D5DB',
                              lineHeight: 1,
                            }}>{n ?? 0}</span>
                          </div>
                        ),
                      },

                      /* ── Capacity ── */
                      {
                        title: 'Capacity', key: 'cap', width: 150,
                        sorter: (a, b) => {
                          const pa = a.max_capacity ? (a.current_personnel_count || 0) / a.max_capacity : 0;
                          const pb = b.max_capacity ? (b.current_personnel_count || 0) / b.max_capacity : 0;
                          return pa - pb;
                        },
                        render: (_, r) => {
                          if (!r.max_capacity) return <span style={{ color: '#D1D5DB', fontSize: 12 }}>No limit</span>;
                          const pct = Math.min(100, Math.round(((r.current_personnel_count || 0) / r.max_capacity) * 100));
                          const c   = pct >= 90 ? '#EF4444' : pct >= 70 ? '#F59E0B' : '#10B981';
                          return (
                            <div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
                                <span style={{ fontSize: 11.5, color: '#374151', fontWeight: 500 }}>
                                  {r.current_personnel_count ?? 0} <span style={{ color: '#9CA3AF' }}>/ {r.max_capacity}</span>
                                </span>
                                <span style={{ fontSize: 11, fontWeight: 700, color: c }}>{pct}%</span>
                              </div>
                              <div style={{ height: 5, background: '#F3F4F6', borderRadius: 3, overflow: 'hidden' }}>
                                <div style={{
                                  height: '100%', width: `${pct}%`,
                                  background: `linear-gradient(90deg, ${c}88, ${c})`,
                                  borderRadius: 3, transition: 'width 0.5s',
                                }} />
                              </div>
                            </div>
                          );
                        },
                      },

                      /* ── Readers ── */
                      {
                        title: 'Readers', key: 'reader_count', width: 90, align: 'center',
                        sorter: (a, b) => zoneReaders(a) - zoneReaders(b),
                        render: (_, row) => { const n = zoneReaders(row); return (
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5 }}>
                            <ApiOutlined style={{ color: n > 0 ? '#7C3AED' : '#D1D5DB', fontSize: 13 }} />
                            <span style={{ fontWeight: 700, color: n > 0 ? '#7C3AED' : '#9CA3AF', fontSize: 13 }}>{n ?? 0}</span>
                          </div>
                        ); },
                      },

                      /* ── Location ── */
                      {
                        title: 'Location', key: 'loc', width: 170,
                        render: (_, r) => (
                          <div>
                            {r.state && (
                              <div style={{ fontSize: 12.5, fontWeight: 500, color: '#374151', marginBottom: 2 }}>{r.state}</div>
                            )}
                            {r.latitude && r.longitude ? (
                              <a
                                href={`https://www.openstreetmap.org/?mlat=${r.latitude}&mlon=${r.longitude}#map=14/${r.latitude}/${r.longitude}`}
                                target="_blank" rel="noopener noreferrer"
                                style={{ fontSize: 11, color: '#0078D4', display: 'flex', alignItems: 'center', gap: 3 }}
                              >
                                <EnvironmentOutlined style={{ fontSize: 10 }} />
                                {parseFloat(r.latitude).toFixed(4)}°, {parseFloat(r.longitude).toFixed(4)}°
                              </a>
                            ) : (
                              <span style={{ fontSize: 11, color: '#D1D5DB' }}>No GPS</span>
                            )}
                          </div>
                        ),
                      },

                      /* ── Last Activity ── */
                      {
                        title: 'Last Activity', dataIndex: 'last_activity_time', width: 130,
                        sorter: (a, b) => new Date(a.last_activity_time || 0) - new Date(b.last_activity_time || 0),
                        render: v => v ? (
                          <Tooltip title={fmtTime(v)} placement="left">
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                              <span style={{ fontSize: 12, color: '#374151', fontWeight: 500 }}>{timeAgo(v)}</span>
                              <span style={{ fontSize: 10.5, color: '#9CA3AF' }}>{new Date(v).toLocaleDateString('en-NG', { day:'2-digit', month:'short' })}</span>
                            </div>
                          </Tooltip>
                        ) : <span style={{ color: '#D1D5DB', fontSize: 12 }}>No activity</span>,
                      },

                      /* ── Actions ── */
                      {
                        title: '', key: 'actions', fixed: 'right', width: 112,
                        render: (_, record) => (
                          <Space size={2}>
                            <Tooltip title="View Detail">
                              <Button
                                size="small" type="text" icon={<EyeOutlined />}
                                onClick={() => setDetailZoneId(record.id)}
                                style={{ color: '#0078D4', width: 28, height: 28 }}
                              />
                            </Tooltip>
                            <Tooltip title="Edit Zone">
                              <Button
                                size="small" type="text" icon={<EditOutlined />}
                                onClick={() => handleEdit(record)}
                                style={{ color: '#10B981', width: 28, height: 28 }}
                              />
                            </Tooltip>
                            <Tooltip title="Assign Reader">
                              <Button
                                size="small" type="text" icon={<ApiOutlined />}
                                onClick={() => handleAssignReader(record)}
                                style={{ color: '#7C3AED', width: 28, height: 28 }}
                              />
                            </Tooltip>
                            <Popconfirm
                              title="Delete zone?"
                              description="Permanently removes the zone and unassigns all readers."
                              onConfirm={() => deleteMutation.mutate({ id: record.id })}
                              okText="Delete" okButtonProps={{ danger: true }}
                            >
                              <Tooltip title="Delete">
                                <Button size="small" type="text" danger icon={<DeleteOutlined />} style={{ width: 28, height: 28 }} />
                              </Tooltip>
                            </Popconfirm>
                          </Space>
                        ),
                      },
                    ]}
                  />
                </div>
                  </div>
                </div>
              ),
            },
            {
              key: 'map',
              label: <Space size={5}><CompassOutlined />GPS Map</Space>,
              forceRender: true,
              children: <ZoneMapView zones={zones} />,
            },
            {
              key: 'readers',
              label: <Space size={5}><ApiOutlined />ADMS Readers</Space>,
              children: <ReadersTab />,
            },
            {
              key: 'muster-points',
              label: (
                <Space size={5}>
                  <SafetyOutlined style={{ color: '#10B981' }} />
                  <span>Muster Points</span>
                  {musterPoints.length > 0 && (
                    <span style={{ background: '#10B981', color: 'white', borderRadius: 10,
                      padding: '0 6px', fontSize: 10.5, fontWeight: 700, lineHeight: '16px' }}>
                      {musterPoints.length}
                    </span>
                  )}
                </Space>
              ),
              children: (
                <MusterPointsTab
                  musterPoints={musterPoints}
                  isLoading={dashLoading}
                />
              ),
            },
          ]}
        />

      {/* ── Detail Drawer ── */}
      {(() => {
        const navList = filtered.length > 0 ? filtered : zones;
        const idx = detailZone ? navList.findIndex(z => z.id === detailZone.id) : -1;
        return (
          <ZoneDetailDrawer
            zone={detailZone}
            open={!!detailZone}
            onClose={() => setDetailZoneId(null)}
            hasPrev={idx > 0}
            hasNext={idx >= 0 && idx < navList.length - 1}
            onPrev={() => idx > 0 && setDetailZoneId(navList[idx - 1].id)}
            onNext={() => idx >= 0 && idx < navList.length - 1 && setDetailZoneId(navList[idx + 1].id)}
          />
        );
      })()}

      {/* ── Create / Edit Modal ── */}
      <Modal
        title={
          <Space>
            {editingZone ? <EditOutlined style={{ color: '#10B981' }} /> : <PlusOutlined style={{ color: '#0078D4' }} />}
            {editingZone ? `Edit Zone — ${editingZone.name}` : 'Create New Zone'}
          </Space>
        }
        open={isModalOpen}
        onOk={() => form.validateFields().then(saveMutation.mutate).catch(() => {})}
        onCancel={() => { setIsModalOpen(false); setEditingZone(null); form.resetFields(); }}
        okText={editingZone ? 'Update Zone' : 'Create Zone'}
        confirmLoading={saveMutation.isPending}
        width={800} destroyOnHidden
      >
        <div style={{
          background: 'linear-gradient(135deg,#EFF6FF,#DBEAFE)',
          border: '1px solid #BFDBFE', borderRadius: 8,
          padding: '10px 14px', marginBottom: 16,
          display: 'flex', alignItems: 'center', gap: 10, fontSize: 12.5, color: '#1D4ED8',
        }}>
          <EnvironmentOutlined style={{ fontSize: 15 }} />
          Add GPS coordinates to enable real-time map tracking. ADMS readers at this location send punches over 4G —
          assigning them to this zone links their punches to this zone's POB count.
        </div>
        <Form form={form} layout="vertical" size="middle">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="Zone Name" rules={[{ required: true }]}>
                <Input placeholder="e.g. Bonga FPSO Platform" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="code" label="Zone Code" rules={[{ required: true }]}>
                <Input placeholder="e.g. OFF-BONGA-001" disabled={!!editingZone} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="zone_type" label="Zone Type" initialValue="LOCATION" rules={[{ required: true }]}>
                <Select showSearch optionFilterProp="children">
                  {Object.entries(ZONE_TYPE_LABELS)
                    .filter(([v]) => v !== 'MUSTER_POINT')
                    .map(([v, l]) => <Select.Option key={v} value={v}>{l}</Select.Option>)}
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="status" label="Status" initialValue="ACTIVE">
                <Select>
                  {['ACTIVE','INACTIVE','MAINTENANCE','EMERGENCY','LOCKDOWN'].map(s => (
                    <Select.Option key={s} value={s}>{s.charAt(0) + s.slice(1).toLowerCase()}</Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="hazard_level" label="Hazard Level" initialValue="LOW">
                <Select>
                  {['LOW','MEDIUM','HIGH','CRITICAL'].map(h => <Select.Option key={h} value={h}>{h}</Select.Option>)}
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="state" label="State / Location">
                <Input placeholder="e.g. Delta State, Offshore" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="latitude" label="Latitude (GPS)" tooltip="Decimal degrees, e.g. 5.5557 (−90 to 90)"
                rules={[{ type: 'number', min: -90, max: 90, message: 'Must be −90 to 90' }]}>
                <InputNumber style={{ width: '100%' }} placeholder="e.g. 5.5557" step={0.0001} precision={6} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="longitude" label="Longitude (GPS)" tooltip="Decimal degrees, e.g. 5.7440 (−180 to 180)"
                rules={[{ type: 'number', min: -180, max: 180, message: 'Must be −180 to 180' }]}>
                <InputNumber style={{ width: '100%' }} placeholder="e.g. 5.7440" step={0.0001} precision={6} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="max_capacity" label="Max Capacity">
                <InputNumber style={{ width: '100%' }} min={0} placeholder="Max persons" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="access_level" label="Access Level" initialValue="RESTRICTED">
                <Select>
                  {['PUBLIC','RESTRICTED','SECURE'].map(a => <Select.Option key={a} value={a}>{a}</Select.Option>)}
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="contact_person" label="Safety Contact">
                <Input placeholder="Safety officer name" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="contact_phone" label="Contact Phone">
                <Input placeholder="e.g. +234 800 000 0000" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="floor_plan_url" label="Location Image URL"
                tooltip="Used as the zone background image on the POB Dashboard. Must be a publicly accessible image URL.">
                <Input placeholder="https://…/image.png" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="address" label="Physical Address">
            <Input placeholder="Full address or location description" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} placeholder="Zone description and operational notes" />
          </Form.Item>

          <Divider style={{ margin: '8px 0' }} />
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="parent_zone_id" label="Parent Zone" tooltip="Makes this a sub-zone shown inside the parent on the POB Dashboard">
                <Select placeholder="None (top-level)" allowClear showSearch optionFilterProp="label">
                  {(Array.isArray(allZonesForParent) ? allZonesForParent : [])
                    .filter(z => z.id !== editingZone?.id)
                    .map(z => <Select.Option key={z.id} value={z.id} label={z.name}>{z.name}</Select.Option>)}
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="tile_position" label="Dashboard Position" tooltip="Where this tile appears around the parent zone image">
                <Select>
                  {['auto','left','right','top','bottom'].map(v => <Select.Option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</Select.Option>)}
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="display_color" label="Tile Color" tooltip="Color of this zone's tile on the POB Dashboard">
                <Select placeholder="Auto (by zone type)" allowClear>
                  {PRESET_COLORS.map(c => (
                    <Select.Option key={c.value} value={c.value}>
                      <Space size={6}>
                        <span style={{ display:'inline-block',width:14,height:14,background:c.value,borderRadius:2,verticalAlign:'middle' }} />
                        {c.label}
                      </Space>
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="is_site_boundary" label="Site boundary (gate / helideck / jetty)"
            valuePropName="checked"
            tooltip="An EXIT through this zone takes the person off POB. Exits from any other zone only move them to the parent zone.">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Assign Reader Modal ── */}
      <Modal
        title={<Space><ApiOutlined style={{ color: '#7C3AED' }} />Doors — {readerZone?.name}</Space>}
        open={isReaderModalOpen}
        onOk={() => readerForm.validateFields().then(assignDoorMutation.mutate).catch(() => {})}
        onCancel={() => { setIsReaderModalOpen(false); readerForm.resetFields(); }}
        okText="Assign Selected" confirmLoading={assignDoorMutation.isPending}
        width={620} destroyOnHidden
      >
        {/* ── Currently assigned doors ── */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: '#374151', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
            <ApiOutlined style={{ color: '#7C3AED' }} />
            Assigned Doors
            <Tag color="purple" style={{ marginLeft: 4, fontSize: 11 }}>{currentModalDoors.length}</Tag>
          </div>
          {modalDoorsLoading ? (
            <div style={{ textAlign: 'center', padding: '16px 0', color: '#9CA3AF', fontSize: 12 }}>Loading…</div>
          ) : currentModalDoors.length === 0 ? (
            <div style={{ background: '#F9FAFB', border: '1px dashed #D1D5DB', borderRadius: 8, padding: '14px 16px', textAlign: 'center', color: '#9CA3AF', fontSize: 12 }}>
              No doors assigned to this zone yet
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {currentModalDoors.map(d => (
                <div key={`${d.controller_id}:${d.door_no}`} style={{ display: 'flex', alignItems: 'center', gap: 10, background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: 8, padding: '8px 12px' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>Door {d.door_no}</span>
                    <span style={{ fontSize: 11, color: '#9CA3AF', marginLeft: 8 }}>{d.controller_name}</span>
                  </div>
                  <Popconfirm
                    title="Remove this door from the zone?"
                    onConfirm={() => removeDoorMutation.mutate({ zoneId: readerZone.id, controllerId: d.controller_id, doorNo: d.door_no })}
                    okText="Remove" cancelText="Cancel" okButtonProps={{ danger: true }}
                  >
                    <Button type="text" danger size="small" icon={<DeleteOutlined />} loading={removeDoorMutation.isPending} />
                  </Popconfirm>
                </div>
              ))}
            </div>
          )}
        </div>

        <Divider style={{ margin: '0 0 16px' }} />

        {/* ── Assign new doors ── */}
        <div style={{ fontWeight: 600, fontSize: 13, color: '#374151', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <PlusOutlined style={{ color: '#7C3AED' }} />
          Add Doors to Zone
        </div>
        <div style={{
          background: 'linear-gradient(135deg,#F5F3FF,#EDE9FE)',
          border: '1px solid #C4B5FD', borderRadius: 8,
          padding: '8px 12px', marginBottom: 14,
          display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#6D28D9',
        }}>
          <WifiOutlined />
          Access doors map controller events to this zone (controller port → door → zone). Standalone Horus H1 readers go to mustering points, not here.
        </div>
        {availableDoors.length === 0 && (
          <Alert type="info" showIcon style={{ marginBottom: 12 }}
            message="No ZKTeco controller doors yet"
            description="Add the controllers under Access Control → Controllers; each door then appears here to assign to a zone." />
        )}
        <Form form={readerForm} layout="vertical">
          <Form.Item name="door" label="Select Doors (one or more)" rules={[{ required: true, message: 'Please select at least one door' }]}>
            <Select
              mode="multiple" placeholder="Choose doors to assign" showSearch
              optionFilterProp="label" size="large" maxTagCount={4}
            >
              {availableDoors
                .filter(d => !currentModalDoors.some(cd => cd.controller_id === d.controller_id && cd.door_no === d.door_no))
                .map(d => (
                  <Select.Option key={`${d.controller_id}:${d.door_no}`} value={`${d.controller_id}:${d.door_no}`} label={d.label}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{
                        width: 24, height: 24, borderRadius: 5, flexShrink: 0,
                        background: 'linear-gradient(135deg,#7C3AED,#A78BFA)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 11,
                      }}><ApiOutlined /></div>
                      <span style={{ fontWeight: 500 }}>Door {d.door_no}</span>
                      <code style={{ fontSize: 11, color: '#9CA3AF' }}>{d.controller_name}</code>
                      {d.already_assigned && (
                        <Tag color="orange" style={{ marginLeft: 'auto', fontSize: 10 }}>In another zone</Tag>
                      )}
                    </div>
                  </Select.Option>
                ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <style>{`
        @keyframes zoneDotPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.4); }
        }
        .zone-row-alert td { background: #FFF8F7 !important; }
        .zone-row-alert:hover td { background: #FEE2E2 !important; }
        .ant-table-tbody > tr:hover > td { background: #F0F7FF !important; }
        .ant-table-thead > tr > th {
          background: #F8FAFC !important;
          font-size: 12px !important;
          font-weight: 600 !important;
          color: #6B7280 !important;
          letter-spacing: 0.03em !important;
          text-transform: uppercase !important;
          border-bottom: 1px solid #E5E7EB !important;
          padding: 10px 14px !important;
        }
        .ant-table-tbody > tr > td { padding: 12px 14px !important; border-bottom: 1px solid #F9FAFB !important; }
        .ant-table-column-sorter { color: #D1D5DB !important; }
        .ant-table-filter-trigger { color: #D1D5DB !important; }
      `}</style>
      </Card>
    </div>
  );
};

export default ZoneManagement;
