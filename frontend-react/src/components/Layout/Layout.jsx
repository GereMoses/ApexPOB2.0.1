import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import ThemeSwitcher from '../ThemeSwitcher/ThemeSwitcher';
import ARIAWidget from '../ARIA/ARIAWidget';
import GlobalSearch from '../GlobalSearch/GlobalSearch';
import useNotificationStream from '../../hooks/useNotificationStream';
import {
  App, Avatar, Badge, Space, Tooltip, Popover, Input, List,
  Empty, Divider, Button, Tag, Modal, Descriptions, Typography, message,
} from 'antd';
import {
  DashboardOutlined, TeamOutlined, ClockCircleOutlined, DesktopOutlined,
  SafetyOutlined, AlertOutlined, FileTextOutlined, SettingOutlined,
  UserOutlined, LogoutOutlined, BellOutlined, MenuFoldOutlined,
  MenuUnfoldOutlined, LockOutlined, UsergroupAddOutlined, CalendarOutlined,
  GlobalOutlined, BarChartOutlined, DollarOutlined, MedicineBoxOutlined,
  DownOutlined, CheckCircleOutlined, AppstoreOutlined,
  ApartmentOutlined, SwapOutlined, GiftOutlined, BookOutlined,
  StarOutlined, WarningOutlined, ToolOutlined,
  SafetyCertificateOutlined, HomeOutlined, SearchOutlined,
  FullscreenOutlined, FullscreenExitOutlined, CloseOutlined,
  ExclamationCircleOutlined, InfoCircleOutlined, CheckOutlined,
  ReloadOutlined, ThunderboltOutlined, IdcardOutlined,
  RightOutlined, QuestionCircleOutlined, CrownOutlined,
  BgColorsOutlined, EditOutlined, CopyOutlined, KeyOutlined,
  HistoryOutlined, NotificationOutlined, FireOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiService from '../../services/api';

const { Text } = Typography;

// COLORS is now supplied dynamically by the theme context (see Layout component body).
// This fallback is only used by the static iconBtnStyle below; real COLORS come from useTheme().
const COLORS_FALLBACK = {
  sidebarBg: '#1E2A3B',
  sidebarBgHover: 'rgba(255,255,255,0.07)',
  sidebarActive: 'rgba(0,120,212,0.18)',
  sidebarActiveBorder: '#0078D4',
  sidebarText: '#C9D1D9',
  sidebarTextActive: '#FFFFFF',
  sidebarGroupLabel: '#8892A4',
  topbarBg: '#FFFFFF',
  topbarBorder: '#E1E4E8',
  contentBg: '#F3F4F8',
  accentBlue: '#0078D4',
  accentBlueDark: '#005A9E',
  topbarIconColor: '#6B7A8D',
  topbarTextColor: '#1F2937',
  topbarMutedColor: '#9CA3AF',
  menuHoverBg: '#F5F7FA',
  headerHeight: 56,
  sidebarWidth: 240,
  sidebarCollapsed: 56,
};

const NAV_GROUPS = [
  {
    label: 'OVERVIEW',
    items: [
      { key: '/dashboard',  icon: <DashboardOutlined />, label: 'Dashboard' },
      { key: '/pob-status', icon: <BarChartOutlined />,  label: 'POB Status', permission: 'pob.view' },
    ],
  },
  {
    label: 'HUMAN RESOURCES',
    items: [
      {
        key: 'personnel-group', icon: <TeamOutlined />, label: 'Personnel', permission: 'personnel.view',
        children: [
          { key: '/personnel',                        icon: <UserOutlined />,             label: 'Employees' },
          // Hidden per Netcom review (#6 — leave handled in SeamlessHR):
          // { key: '/personnel/leave-management',       icon: <CalendarOutlined />,         label: 'Leave Management' },
          { key: '/personnel/training-management',    icon: <BookOutlined />,             label: 'Training' },
          // Hidden per Netcom review (2026-07-08):
          // { key: '/personnel/performance-management', icon: <StarOutlined />,             label: 'Performance' },
          // Hidden per Netcom review (2026-07-08):
          // { key: '/personnel/disciplinary-management',icon: <WarningOutlined />,          label: 'Disciplinary' },
          // Hidden per Netcom review (2026-07-08):
          // { key: '/personnel/promotion-transfer',     icon: <SwapOutlined />,             label: 'Promotion/Transfer' },
          // Hidden per Netcom review (2026-07-08):
          // { key: '/personnel/employment-contract',    icon: <FileTextOutlined />,         label: 'Contracts' },
          // Hidden per Netcom walkthrough action #6 — benefits handled in SeamlessHR:
          // { key: '/personnel/benefits-management',    icon: <GiftOutlined />,             label: 'Benefits' },
          { key: '/personnel/departments',            icon: <ApartmentOutlined />,        label: 'Departments' },
          { key: '/personnel/positions',              icon: <TeamOutlined />,             label: 'Positions' },
          // Hidden per Netcom review (2026-07-08):
          // { key: '/personnel/resignation',            icon: <FileTextOutlined />,         label: 'Resignation' },
          // Hidden per Netcom review (2026-07-08):
          // { key: '/personnel/custom-attributes',      icon: <SettingOutlined />,          label: 'Custom Attributes' },
          { key: '/personnel/onboarding',             icon: <SafetyCertificateOutlined />,label: 'Onboarding' },
          // Hidden per Netcom walkthrough action #8 — vendor master lives in Business Central:
          // { key: '/personnel/vendors',                icon: <ToolOutlined />,             label: 'Contractor/Vendor' },
        ],
      },
      // Hidden per Netcom walkthrough action #6 — payroll handled in SeamlessHR:
      // { key: '/payroll', icon: <DollarOutlined />, label: 'Payroll', permission: 'payroll.view' },
    ],
  },
  {
    label: 'OPERATIONS',
    items: [
      { key: '/attendance',          icon: <ClockCircleOutlined />, label: 'Attendance',            permission: 'attendance.view' },
      { key: '/zones',               icon: <GlobalOutlined />,      label: 'Zones' },
      { key: '/transport-manifest',  icon: <IdcardOutlined />,      label: 'Journey Management' },
      { key: '/emergency-response',  icon: <AlertOutlined />,       label: 'Emergency & Mustering', permission: 'emergency.view' },
      // Hidden per Netcom walkthrough action #7 — MTD is outside client scope / duplicates existing systems:
      // { key: '/mtd',                 icon: <MedicineBoxOutlined />, label: 'MTD' },
    ],
  },
  {
    label: 'SECURITY',
    items: [
      { key: '/access-control', icon: <LockOutlined />,         label: 'Access Control', permission: 'access_control.view' },
      { key: '/device',         icon: <DesktopOutlined />,       label: 'Devices',        permission: 'devices.view' },
      { key: '/visitor',        icon: <UsergroupAddOutlined />,  label: 'Visitor',        permission: 'visitors.view' },
    ],
  },
  {
    label: 'ADMIN',
    items: [
      { key: '/meeting',      icon: <CalendarOutlined />,        label: 'Meeting' },
      { key: '/reports',      icon: <FileTextOutlined />,        label: 'Reports',      permission: 'reports.view' },
      { key: '/settings',     icon: <SettingOutlined />,         label: 'Settings',     permission: 'settings.view' },
      { key: '/subscription', icon: <CrownOutlined />,           label: 'Subscription', globalAdminOnly: true },
    ],
  },
];

const APP_TILES = [
  { key: '/dashboard',          icon: <DashboardOutlined />,    label: 'Dashboard',          color: '#0078D4', bg: '#EFF6FF' },
  { key: '/pob-status',         icon: <BarChartOutlined />,     label: 'POB Status',         color: '#7C3AED', bg: '#F5F3FF', permission: 'pob.view' },
  { key: '/personnel',          icon: <TeamOutlined />,         label: 'Personnel',          color: '#047857', bg: '#ECFDF5', permission: 'personnel.view' },
  { key: '/attendance',         icon: <ClockCircleOutlined />,  label: 'Attendance',         color: '#B45309', bg: '#FFFBEB', permission: 'attendance.view' },
  { key: '/zones',              icon: <GlobalOutlined />,       label: 'Zones',              color: '#0E7490', bg: '#ECFEFF' },
  { key: '/emergency-response', icon: <AlertOutlined />,        label: 'Emergency & Muster', color: '#B91C1C', bg: '#FEF2F2', permission: 'emergency.view' },
  { key: '/access-control',     icon: <LockOutlined />,         label: 'Access Control',     color: '#1D4ED8', bg: '#EFF6FF', permission: 'access_control.view' },
  { key: '/device',             icon: <DesktopOutlined />,      label: 'Devices',            color: '#374151', bg: '#F9FAFB', permission: 'devices.view' },
  { key: '/visitor',            icon: <UsergroupAddOutlined />, label: 'Visitors',           color: '#065F46', bg: '#ECFDF5', permission: 'visitors.view' },
  { key: '/reports',            icon: <FileTextOutlined />,     label: 'Reports',            color: '#92400E', bg: '#FFFBEB', permission: 'reports.view' },
  { key: '/settings',           icon: <SettingOutlined />,      label: 'Settings',           color: '#4B5563', bg: '#F3F4F6', permission: 'settings.view' },
];

const NOTIF_STYLE = {
  info:     { color: '#1890ff', bg: '#e6f7ff', icon: <InfoCircleOutlined /> },
  warning:  { color: '#fa8c16', bg: '#fff7e6', icon: <ExclamationCircleOutlined /> },
  error:    { color: '#f5222d', bg: '#fff1f0', icon: <ExclamationCircleOutlined /> },
  success:  { color: '#52c41a', bg: '#f6ffed', icon: <CheckCircleOutlined /> },
  emergency:{ color: '#f5222d', bg: '#fff1f0', icon: <AlertOutlined /> },
};

const getNotifStyle = (type) => NOTIF_STYLE[type] || NOTIF_STYLE.info;

const timeAgo = (dateStr) => {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};

const Layout = ({ user, onLogout, children }) => {
  const { COLORS: themeColors, theme: activeTheme, themes: allThemes, applyTheme } = useTheme();
  const COLORS = themeColors ?? COLORS_FALLBACK;

  const [sidebarStyle, setSidebarStyle] = useState(() => localStorage.getItem('pob_sidebar_style') || 'dark');
  const sidebarIsLight = sidebarStyle === 'light';

  const SIDEBAR = {
    bg:               sidebarIsLight ? COLORS.topbarBg        : COLORS.sidebarBg,
    bgHover:          sidebarIsLight ? COLORS.menuHoverBg     : COLORS.sidebarBgHover,
    active:           COLORS.sidebarActive,
    activeBorder:     COLORS.sidebarActiveBorder,
    text:             sidebarIsLight ? COLORS.topbarTextColor  : COLORS.sidebarText,
    textActive:       sidebarIsLight ? COLORS.accentBlue       : '#FFFFFF',
    groupLabel:       sidebarIsLight ? COLORS.topbarMutedColor : COLORS.sidebarGroupLabel,
    border:           sidebarIsLight ? COLORS.topbarBorder     : 'rgba(255,255,255,0.06)',
    shadow:           sidebarIsLight ? '2px 0 8px rgba(0,0,0,0.06)' : '2px 0 8px rgba(0,0,0,0.18)',
    scrollThumb:      sidebarIsLight ? 'rgba(0,0,0,0.15)'     : 'rgba(255,255,255,0.12)',
    scrollThumbHover: sidebarIsLight ? 'rgba(0,0,0,0.25)'     : 'rgba(255,255,255,0.2)',
    logoText:         sidebarIsLight ? COLORS.topbarTextColor  : '#fff',
    logoSubtext:      sidebarIsLight ? COLORS.topbarMutedColor : '#6B7A8D',
    groupActive1:     sidebarIsLight ? COLORS.accentBlue       : '#90B8E0',
    groupActive2:     sidebarIsLight ? COLORS.accentBlue       : '#B8D4F0',
  };

  const toggleSidebarStyle = () => {
    const next = sidebarStyle === 'dark' ? 'light' : 'dark';
    setSidebarStyle(next);
    localStorage.setItem('pob_sidebar_style', next);
  };
  const { latest: streamNotif } = useNotificationStream({ enabled: !!user });

  const [collapsed,      setCollapsed]     = useState(false);
  const [expandedItems,  setExpandedItems] = useState({ 'personnel-group': true });
  const [notifOpen,      setNotifOpen]     = useState(false);
  const [appsOpen,       setAppsOpen]      = useState(false);
  const [searchOpen,     setSearchOpen]    = useState(false);
  const [searchVal,      setSearchVal]     = useState('');
  const [globalSearchOpen, setGlobalSearchOpen] = useState(false);
  const [isFullscreen,   setIsFullscreen]  = useState(false);
  const [clockDate,      setClockDate]     = useState('');
  const [clockTime,      setClockTime]     = useState('');
  const [profileOpen,    setProfileOpen]   = useState(false);
  const [userPopOpen,    setUserPopOpen]   = useState(false);
  const [userStatus,     setUserStatus]    = useState('online');
  const [shortcutsOpen,  setShortcutsOpen] = useState(false);
  const searchRef    = useRef(null);
  const sessionStart = useRef(Date.now());
  const qc = useQueryClient();
  const navigate  = useNavigate();
  const location  = useLocation();

  const canSee = useCallback((permission, globalAdminOnly) => {
    if (globalAdminOnly) return Boolean(user?.is_global_admin);
    if (!permission) return true;
    if (user?.is_superuser) return true;
    return (user?.permissions || []).includes(permission);
  }, [user]);

  /* ── subscription status ── */
  const { data: subData } = useQuery({
    queryKey: ['subscription-status-topbar'],
    queryFn: () => fetch('/api/v1/subscription/status').then(r => r.json()),
    refetchInterval: 5 * 60 * 1000,
    staleTime: 60 * 1000,
  });
  const sub = subData?.data;

  const SUB_THEME = {
    active:     { bg: '#F0FDF4', border: '#86EFAC', color: '#166534', dot: '#22C55E' },
    warning:    { bg: '#FFFBEB', border: '#FCD34D', color: '#92400E', dot: '#F59E0B' },
    critical:   { bg: '#FFF1F0', border: '#FCA5A5', color: '#991B1B', dot: '#EF4444' },
    expired:    { bg: '#FFF1F0', border: '#EF4444', color: '#7F1D1D', dot: '#EF4444' },
    no_license: { bg: '#F3F4F6', border: '#D1D5DB', color: '#4B5563', dot: '#9CA3AF' },
  };
  const subTheme = SUB_THEME[sub?.status] || SUB_THEME.active;

  const formatExpiryDt = (dt) => {
    if (!dt) return '—';
    try {
      const d = new Date(dt);
      if (isNaN(d)) return dt;
      return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
        + ' · ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch { return dt; }
  };

  const subLabel = (() => {
    if (!sub || sub.status === 'active') return null; // hide badge when healthy
    if (sub.status === 'no_license') return 'No License';
    if (sub.status === 'expired')    return 'License Expired';
    return `Expires in ${sub.days_remaining}d`;
  })();

  const subTooltip = (() => {
    if (!sub) return '';
    if (sub.status === 'no_license') return 'No subscription found. Contact your vendor.';
    if (sub.status === 'expired')    return `Subscription expired on ${formatExpiryDt(sub.expiry_date)}. Contact your vendor to renew.`;
    return `Subscription expires on ${formatExpiryDt(sub.expiry_date)} (${sub.days_remaining} days remaining)`;
  })();

  /* ── live clock ── */
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setClockDate(now.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }));
      setClockTime(now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  /* ── fullscreen listener ── */
  useEffect(() => {
    const onChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  /* ── Auto-collapse sidebar on small screens ── */
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1024px)');
    const handler = (e) => { if (e.matches) setCollapsed(true); };
    if (mq.matches) setCollapsed(true);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  /* ── Real-time SSE notification → corner pop-up ──
     Used to be a top-centre message with duration 0 — it had no close button, so every
     high/critical alert stayed over the screen until a page refresh. Now: bottom-right,
     stacked, closable, timed by priority; a repeat replaces the earlier one; Esc closes
     all. Every alert is kept in the bell list regardless. */
  const { notification: appNotify } = App.useApp();
  const lastSeenRef = useRef({});
  useEffect(() => {
    if (!streamNotif) return;
    qc.invalidateQueries(['notifications']);
    const title = streamNotif.title || 'Notification';
    const body = streamNotif.message && streamNotif.message !== title ? streamNotif.message : undefined;
    const key = `${streamNotif.type || 'n'}|${title}`;
    const now = Date.now();
    if (now - (lastSeenRef.current[key] || 0) < 3000) return;   // the same alert arriving twice
    lastSeenRef.current[key] = now;
    const [kind, secs] = { critical: ['error', 20], high: ['warning', 12], medium: ['info', 8] }[streamNotif.priority] || ['info', 5];
    const link = streamNotif.link;
    appNotify[kind]({
      key, message: title, description: body, duration: secs, placement: 'bottomRight',
      btn: link ? (
        <Button size="small" type="primary" onClick={() => { appNotify.destroy(key); navigate(link); }}>Open</Button>
      ) : undefined,
    });
  }, [streamNotif]); // eslint-disable-line

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') appNotify.destroy(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [appNotify]);

  /* ── Ctrl+K / Cmd+K global search shortcut ── */
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setGlobalSearchOpen(true);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
    else document.exitFullscreen?.();
  };

  /* ── auto-expand active group ── */
  useEffect(() => {
    NAV_GROUPS.forEach(g =>
      g.items.forEach(item => {
        if (item.children && item.children.some(c => location.pathname.startsWith(c.key)))
          setExpandedItems(prev => ({ ...prev, [item.key]: true }));
      })
    );
  }, [location.pathname]);

  /* ── notifications query ── */
  const { data: notifData, refetch: refetchNotifs } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => apiService.get('/api/v1/notifications/'),
    refetchInterval: notifOpen ? 15000 : 60000,
    retry: 1,
  });
  const rawNotifs = notifData?.data?.results ?? notifData?.data ?? [];
  const notifications = Array.isArray(rawNotifs) ? rawNotifs : [];
  const unreadCount = notifications.filter(n => !n.is_read).length;

  const markAllRead = useMutation({
    mutationFn: () => apiService.put('/api/v1/notifications/mark-all-read/'),
    onSuccess: () => qc.invalidateQueries(['notifications']),
    onSettled: () => qc.invalidateQueries(['notifications']),
  });

  const markOneRead = useMutation({
    mutationFn: (id) => apiService.put(`/api/v1/notifications/${id}/read/`),
    onSuccess: () => qc.invalidateQueries(['notifications']),
  });

  /* ── search ── */
  const allNavItems = NAV_GROUPS.flatMap(g =>
    g.items.filter(item => canSee(item.permission, item.globalAdminOnly)).flatMap(item => item.children
      ? [item, ...item.children]
      : [item]
    )
  );
  const searchResults = searchVal.trim()
    ? allNavItems.filter(i => i.label.toLowerCase().includes(searchVal.toLowerCase()) && i.key !== 'personnel-group')
    : [];

  const openSearch = () => setGlobalSearchOpen(true);

  /* ── nav helpers ── */
  const isActive = key => {
    if (key === '/personnel') return location.pathname === '/personnel';
    return location.pathname === key || location.pathname.startsWith(key + '/');
  };
  const isGroupActive = item => {
    if (!item.children) return isActive(item.key);
    return item.children.some(c => isActive(c.key));
  };
  const toggleExpand = key => setExpandedItems(prev => ({ ...prev, [key]: !prev[key] }));

  /* ── breadcrumbs ── */
  const getBreadcrumbs = () => {
    const path = location.pathname;
    const crumbs = [{ label: 'Home', icon: <HomeOutlined />, path: '/dashboard' }];
    for (const group of NAV_GROUPS) {
      for (const item of group.items) {
        if (item.children) {
          // A grouping parent (e.g. 'personnel-group') has no page of its own, so
          // its breadcrumb must not link to that dead key — fall back to /dashboard.
          const parentPath = item.key.startsWith('/') ? item.key : '/dashboard';
          const child = item.children.find(c => c.key === path);
          if (child) {
            crumbs.push({ label: item.label, path: parentPath });
            crumbs.push({ label: child.label, path: child.key });
            return crumbs;
          }
          if (path.startsWith(item.key + '/')) {
            crumbs.push({ label: item.label, path: parentPath });
            return crumbs;
          }
        } else if (item.key === path || path.startsWith(item.key + '/')) {
          crumbs.push({ label: item.label, path: item.key });
          return crumbs;
        }
      }
    }
    return crumbs;
  };


  /* ── sidebar nav item renderer ── */
  const renderNavItem = (item, depth = 0) => {
    const active      = isActive(item.key);
    const groupActive = isGroupActive(item);
    const expanded    = expandedItems[item.key];
    const hasChildren = !!item.children;

    const itemStyle = {
      display: 'flex', alignItems: 'center', cursor: 'pointer',
      borderRadius: 6, margin: '1px 6px', transition: 'all 0.15s ease',
      position: 'relative',
      padding: collapsed ? '10px 0' : depth === 1 ? '7px 16px 7px 44px' : '10px 16px',
      background: active ? SIDEBAR.active : 'transparent',
      borderLeft: active && depth === 0
        ? `3px solid ${SIDEBAR.activeBorder}`
        : depth === 0 ? '3px solid transparent' : 'none',
      justifyContent: collapsed ? 'center' : 'flex-start',
      gap: 10,
    };

    const content = (
      <div
        style={itemStyle}
        onClick={() => hasChildren ? toggleExpand(item.key) : navigate(item.key)}
        onMouseEnter={e => { if (!active) e.currentTarget.style.background = SIDEBAR.bgHover; }}
        onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent'; }}
      >
        <span style={{
          fontSize: depth === 1 ? 13 : 16,
          color: active ? SIDEBAR.textActive : groupActive ? SIDEBAR.groupActive1 : SIDEBAR.text,
          flexShrink: 0, width: 18, textAlign: 'center',
        }}>{item.icon}</span>
        {!collapsed && (
          <span style={{
            fontSize: depth === 1 ? 12.5 : 13.5,
            fontWeight: active ? 600 : 400,
            color: active ? SIDEBAR.textActive : groupActive && depth === 0 ? SIDEBAR.groupActive2 : SIDEBAR.text,
            flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>{item.label}</span>
        )}
        {!collapsed && hasChildren && (
          <DownOutlined style={{
            fontSize: 10, color: SIDEBAR.groupLabel, flexShrink: 0,
            transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.2s',
          }} />
        )}
      </div>
    );

    return (
      <div key={item.key}>
        {collapsed && depth === 0
          ? <Tooltip title={item.label} placement="right">{content}</Tooltip>
          : content}
        {hasChildren && expanded && !collapsed && (
          <div style={{ overflow: 'hidden' }}>
            {item.children.map(child => renderNavItem(child, 1))}
          </div>
        )}
      </div>
    );
  };

  /* ── notifications panel ── */
  const notifPanel = (
    <div style={{ width: 360 }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 16px', borderBottom: '1px solid #f0f0f0',
      }}>
        <div>
          <span style={{ fontWeight: 700, fontSize: 14, color: '#1F2937' }}>Notifications</span>
          {unreadCount > 0 && (
            <span style={{
              marginLeft: 8, background: '#EFF6FF', color: '#0078D4',
              borderRadius: 10, padding: '1px 7px', fontSize: 11, fontWeight: 600,
            }}>{unreadCount} new</span>
          )}
        </div>
        <Space size={6}>
          <Tooltip title="Close every pop-up on screen (or press Esc)">
            <Button type="text" size="small" style={{ color: '#6B7A8D', fontSize: 12 }}
              onClick={() => appNotify.destroy()}>Close pop-ups</Button>
          </Tooltip>
          <Tooltip title="Refresh">
            <Button type="text" size="small" icon={<ReloadOutlined />}
              onClick={() => refetchNotifs()} style={{ color: '#6B7A8D' }} />
          </Tooltip>
          {unreadCount > 0 && (
            <Button type="text" size="small" style={{ color: COLORS.accentBlue, fontSize: 12 }}
              loading={markAllRead.isPending}
              onClick={() => markAllRead.mutate()}>
              Mark all read
            </Button>
          )}
        </Space>
      </div>

      <div style={{ maxHeight: 380, overflowY: 'auto' }} className="pob-notif-scroll">
        {notifications.length === 0 ? (
          <Empty description="No notifications" image={Empty.PRESENTED_IMAGE_SIMPLE}
            style={{ padding: '32px 0' }} />
        ) : (
          notifications.slice(0, 20).map(n => {
            const ns = getNotifStyle(n.notification_type || n.type);
            return (
              <div
                key={n.id}
                onClick={() => !n.is_read && markOneRead.mutate(n.id)}
                style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid #f8f8f8',
                  background: n.is_read ? 'transparent' : '#FAFCFF',
                  cursor: n.is_read ? 'default' : 'pointer',
                  display: 'flex', gap: 12, alignItems: 'flex-start',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = '#F3F4F8'; }}
                onMouseLeave={e => { e.currentTarget.style.background = n.is_read ? 'transparent' : '#FAFCFF'; }}
              >
                <div style={{
                  width: 34, height: 34, borderRadius: 8, flexShrink: 0,
                  background: ns.bg, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: ns.color, fontSize: 15,
                }}>{ns.icon}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontWeight: n.is_read ? 500 : 600, fontSize: 13,
                    color: '#1F2937', marginBottom: 2,
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>{n.title || n.subject || 'Notification'}</div>
                  <div style={{
                    fontSize: 12, color: '#6B7A8D', lineHeight: 1.4,
                    overflow: 'hidden', display: '-webkit-box',
                    WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                  }}>{n.message || n.body || ''}</div>
                  <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>
                    {timeAgo(n.created_at)}
                  </div>
                </div>
                {!n.is_read && (
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: COLORS.accentBlue, flexShrink: 0, marginTop: 4 }} />
                )}
              </div>
            );
          })
        )}
      </div>

      <div style={{ padding: '10px 16px', borderTop: '1px solid #f0f0f0', textAlign: 'center' }}>
        <Button type="link" size="small" style={{ color: COLORS.accentBlue, fontSize: 12 }}
          onClick={() => { setNotifOpen(false); navigate('/notifications'); }}>
          View all notifications
        </Button>
      </div>
    </div>
  );

  /* ── app launcher panel ── */
  const appsPanel = (
    <div style={{ width: 340 }}>
      <div style={{ padding: '12px 16px 8px', borderBottom: '1px solid #f0f0f0' }}>
        <span style={{ fontWeight: 700, fontSize: 14, color: '#1F2937' }}>All Modules</span>
      </div>
      <div style={{ padding: 12, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        {APP_TILES.filter(tile => canSee(tile.permission)).map(tile => (
          <div
            key={tile.key}
            onClick={() => { navigate(tile.key); setAppsOpen(false); }}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              padding: '14px 8px 10px', borderRadius: 10, cursor: 'pointer',
              transition: 'all 0.15s', border: '1px solid transparent',
              background: location.pathname.startsWith(tile.key) ? tile.bg : 'transparent',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = tile.bg;
              e.currentTarget.style.border = `1px solid ${tile.color}30`;
              e.currentTarget.style.transform = 'translateY(-1px)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = location.pathname.startsWith(tile.key) ? tile.bg : 'transparent';
              e.currentTarget.style.border = '1px solid transparent';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <div style={{
              width: 40, height: 40, borderRadius: 10, background: tile.bg,
              border: `1px solid ${tile.color}25`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: tile.color, fontSize: 18, marginBottom: 6,
            }}>{tile.icon}</div>
            <span style={{ fontSize: 11, color: '#374151', fontWeight: 500, textAlign: 'center', lineHeight: 1.3 }}>
              {tile.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );

  /* ── search results dropdown ── */
  const searchDropdown = searchOpen && searchResults.length > 0 && (
    <div style={{
      position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 200,
      background: 'white', borderRadius: '0 0 8px 8px',
      boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
      border: '1px solid #E1E4E8', borderTop: 'none',
      maxHeight: 280, overflowY: 'auto',
    }}>
      {searchResults.map(item => (
        <div
          key={item.key}
          onClick={() => { navigate(item.key); setSearchOpen(false); setSearchVal(''); }}
          style={{
            padding: '9px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10,
            fontSize: 13, color: '#374151', transition: 'background 0.1s',
          }}
          onMouseEnter={e => e.currentTarget.style.background = '#F3F4F8'}
          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
        >
          <span style={{ color: COLORS.accentBlue, fontSize: 14 }}>{item.icon}</span>
          {item.label}
          <span style={{ fontSize: 11, color: '#9CA3AF', marginLeft: 'auto', fontFamily: 'monospace' }}>
            {item.key}
          </span>
        </div>
      ))}
    </div>
  );

  /* ── icon button style (theme-aware) ── */
  const iconBtnStyle = {
    width: 34, height: 34, borderRadius: 6,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    cursor: 'pointer', color: COLORS.topbarIconColor, transition: 'all 0.15s',
  };

  /* ── user popover panel ── */
  const displayName = user?.first_name
    ? `${user.first_name} ${user.last_name || ''}`.trim()
    : user?.username || 'Admin';
  const initials = displayName.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();

  const STATUS_OPTIONS = [
    { key: 'online',    dot: '#22C55E', label: 'Active',           hint: 'Available to others' },
    { key: 'away',      dot: '#F59E0B', label: 'Away',             hint: 'Temporarily unavailable' },
    { key: 'dnd',       dot: '#EF4444', label: 'Do Not Disturb',   hint: 'Silence all alerts' },
    { key: 'invisible', dot: '#9CA3AF', label: 'Appear Offline',   hint: 'Hidden from others' },
  ];
  const currentStatus = STATUS_OPTIONS.find(s => s.key === userStatus) ?? STATUS_OPTIONS[0];

  const sessionMinutes = Math.floor((Date.now() - sessionStart.current) / 60000);
  const sessionText = sessionMinutes < 1 ? 'Just started'
    : sessionMinutes < 60 ? `${sessionMinutes}m`
    : `${Math.floor(sessionMinutes / 60)}h ${sessionMinutes % 60}m`;

  /* helper: section label */
  const SectionLabel = ({ label }) => (
    <div style={{
      padding: '10px 16px 4px',
      fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
      color: '#9CA3AF', textTransform: 'uppercase', userSelect: 'none',
    }}>{label}</div>
  );

  /* helper: single menu row */
  const MenuItem = ({ icon, color, label, sub, shortcut, badge, right, onClick: act }) => (
    <div
      onClick={act}
      style={{
        display: 'flex', alignItems: 'center', gap: 11,
        padding: '8px 14px', cursor: 'pointer', transition: 'background 0.13s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = COLORS.menuHoverBg}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <div style={{
        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
        background: `${color}14`, border: `1px solid ${color}20`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color, fontSize: 14,
      }}>{icon}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 500, color: COLORS.topbarTextColor, lineHeight: 1.3 }}>{label}</span>
          {badge != null && (
            <span style={{
              background: '#EF4444', color: '#fff',
              fontSize: 9, fontWeight: 700, borderRadius: 8,
              padding: '1px 5px', lineHeight: 1.4,
            }}>{badge}</span>
          )}
        </div>
        {sub && <div style={{ fontSize: 11, color: COLORS.topbarMutedColor, marginTop: 1 }}>{sub}</div>}
      </div>
      {shortcut && (
        <kbd style={{
          background: COLORS.menuHoverBg, border: `1px solid #e5e7eb`,
          borderRadius: 4, padding: '1px 5px',
          fontSize: 10, color: COLORS.topbarMutedColor, fontFamily: 'monospace',
          flexShrink: 0,
        }}>{shortcut}</kbd>
      )}
      {right || <RightOutlined style={{ fontSize: 9, color: '#D1D5DB', flexShrink: 0 }} />}
    </div>
  );

  const userPopPanel = (
    <div style={{ width: 316 }}>

      {/* ── Profile Header ───────────────────────────────── */}
      <div style={{
        background: `linear-gradient(145deg, ${COLORS.sidebarBg} 0%, ${COLORS.accentBlueDark}cc 100%)`,
        borderRadius: '10px 10px 0 0', padding: '18px 16px 14px',
        position: 'relative', overflow: 'hidden',
      }}>
        {/* decorative circles */}
        <div style={{ position:'absolute', top:-30, right:-20, width:100, height:100, borderRadius:'50%', background:`${COLORS.accentBlue}18`, pointerEvents:'none' }} />
        <div style={{ position:'absolute', bottom:-20, left:60, width:70, height:70, borderRadius:'50%', background:`${COLORS.accentBlue}0e`, pointerEvents:'none' }} />

        {/* Top row: avatar + info + edit button */}
        <div style={{ display:'flex', alignItems:'flex-start', gap:13, position:'relative' }}>
          {/* Avatar with status ring */}
          <div style={{ position:'relative', flexShrink:0 }}>
            <div style={{
              width:54, height:54, borderRadius:14,
              background:`linear-gradient(135deg, ${COLORS.accentBlue} 0%, ${COLORS.accentBlueDark} 100%)`,
              display:'flex', alignItems:'center', justifyContent:'center',
              fontSize:20, fontWeight:800, color:'white',
              boxShadow:`0 4px 14px ${COLORS.accentBlue}55`,
              border:'2px solid rgba(255,255,255,0.18)',
            }}>{initials}</div>
            {/* Status badge on avatar */}
            <Tooltip title={currentStatus.label}>
              <div style={{
                position:'absolute', bottom:-2, right:-2,
                width:14, height:14, borderRadius:'50%',
                background: currentStatus.dot,
                border:'2px solid rgba(255,255,255,0.9)',
                cursor:'pointer', transition:'transform 0.15s',
              }}
                onClick={e => { e.stopPropagation(); setUserStatus(s => { const i = STATUS_OPTIONS.findIndex(o => o.key === s); return STATUS_OPTIONS[(i+1) % STATUS_OPTIONS.length].key; }); }}
                onMouseEnter={e => { e.currentTarget.style.transform='scale(1.25)'; }}
                onMouseLeave={e => { e.currentTarget.style.transform='scale(1)'; }}
              />
            </Tooltip>
          </div>

          {/* Name + role + email */}
          <div style={{ flex:1, minWidth:0, paddingTop:2 }}>
            <div style={{ color:'#fff', fontWeight:700, fontSize:15, lineHeight:1.25, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
              {displayName}
            </div>
            <div style={{ marginTop:5, display:'flex', alignItems:'center', gap:6, flexWrap:'wrap' }}>
              {user?.is_superuser && (
                <span style={{
                  background:'rgba(250,204,21,0.18)', color:'#FCD34D',
                  fontSize:9, fontWeight:800, letterSpacing:'0.07em',
                  padding:'2px 7px', borderRadius:10,
                  border:'1px solid rgba(250,204,21,0.28)',
                  display:'inline-flex', alignItems:'center', gap:3,
                }}>
                  <CrownOutlined style={{ fontSize:8 }} /> SUPER ADMIN
                </span>
              )}
              {user?.is_global_admin && (
                <span style={{
                  background:'rgba(167,139,250,0.2)', color:'#C4B5FD',
                  fontSize:9, fontWeight:800, letterSpacing:'0.07em',
                  padding:'2px 7px', borderRadius:10,
                  border:'1px solid rgba(167,139,250,0.28)',
                }}>GLOBAL ADMIN</span>
              )}
              {!user?.is_superuser && !user?.is_global_admin && (
                <span style={{
                  background:'rgba(255,255,255,0.1)', color:'rgba(255,255,255,0.6)',
                  fontSize:9, fontWeight:700, letterSpacing:'0.06em',
                  padding:'2px 7px', borderRadius:10,
                  border:'1px solid rgba(255,255,255,0.12)',
                }}>USER</span>
              )}
            </div>
            {user?.email && (
              <Tooltip title="Click to copy email">
                <div
                  onClick={() => { navigator.clipboard?.writeText(user.email); message.success('Email copied'); }}
                  style={{
                    color:'rgba(255,255,255,0.42)', fontSize:11, marginTop:6,
                    whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis',
                    cursor:'pointer', display:'flex', alignItems:'center', gap:4, maxWidth:160,
                    transition:'color 0.15s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.color='rgba(255,255,255,0.75)'}
                  onMouseLeave={e => e.currentTarget.style.color='rgba(255,255,255,0.42)'}
                >
                  <span style={{ overflow:'hidden', textOverflow:'ellipsis' }}>{user.email}</span>
                  <CopyOutlined style={{ fontSize:10, flexShrink:0 }} />
                </div>
              </Tooltip>
            )}
          </div>

          {/* Edit profile button */}
          <Tooltip title="Edit profile">
            <div
              onClick={() => { setUserPopOpen(false); setProfileOpen(true); }}
              style={{
                width:28, height:28, borderRadius:8, flexShrink:0,
                background:'rgba(255,255,255,0.1)', border:'1px solid rgba(255,255,255,0.15)',
                display:'flex', alignItems:'center', justifyContent:'center',
                cursor:'pointer', transition:'all 0.15s', color:'rgba(255,255,255,0.65)',
                fontSize:13,
              }}
              onMouseEnter={e => { e.currentTarget.style.background='rgba(255,255,255,0.2)'; e.currentTarget.style.color='#fff'; }}
              onMouseLeave={e => { e.currentTarget.style.background='rgba(255,255,255,0.1)'; e.currentTarget.style.color='rgba(255,255,255,0.65)'; }}
            >
              <EditOutlined />
            </div>
          </Tooltip>
        </div>

        {/* Status selector row */}
        <div style={{
          display:'flex', alignItems:'center', justifyContent:'space-between',
          marginTop:14, paddingTop:12,
          borderTop:'1px solid rgba(255,255,255,0.08)',
        }}>
          <div style={{ display:'flex', gap:6 }}>
            {STATUS_OPTIONS.map(opt => (
              <Tooltip key={opt.key} title={opt.hint}>
                <div
                  onClick={() => setUserStatus(opt.key)}
                  style={{
                    display:'flex', alignItems:'center', gap:5,
                    padding:'4px 9px', borderRadius:20, cursor:'pointer',
                    background: userStatus === opt.key ? 'rgba(255,255,255,0.14)' : 'transparent',
                    border: userStatus === opt.key ? '1px solid rgba(255,255,255,0.2)' : '1px solid transparent',
                    transition:'all 0.15s',
                  }}
                  onMouseEnter={e => { if (userStatus !== opt.key) e.currentTarget.style.background='rgba(255,255,255,0.07)'; }}
                  onMouseLeave={e => { if (userStatus !== opt.key) e.currentTarget.style.background='transparent'; }}
                >
                  <div style={{ width:7, height:7, borderRadius:'50%', background:opt.dot, flexShrink:0,
                    ...(userStatus === opt.key && opt.key === 'online' ? { animation:'statusPulse 2s infinite' } : {})
                  }} />
                  <span style={{ fontSize:10.5, color: userStatus === opt.key ? '#fff' : 'rgba(255,255,255,0.45)', fontWeight: userStatus === opt.key ? 600 : 400, whiteSpace:'nowrap' }}>
                    {opt.label}
                  </span>
                </div>
              </Tooltip>
            ))}
          </div>
        </div>

        {/* Session info bar */}
        <div style={{
          display:'flex', alignItems:'center', gap:16,
          marginTop:10,
        }}>
          <div style={{ display:'flex', alignItems:'center', gap:4 }}>
            <ClockCircleOutlined style={{ fontSize:10, color:'rgba(255,255,255,0.3)' }} />
            <span style={{ fontSize:10.5, color:'rgba(255,255,255,0.38)' }}>Session: </span>
            <span style={{ fontSize:10.5, color:'rgba(255,255,255,0.6)', fontWeight:600 }}>{sessionText}</span>
          </div>
          {user?.username && (
            <span style={{ fontSize:10, color:'rgba(255,255,255,0.25)', fontFamily:'monospace', marginLeft:'auto' }}>
              @{user.username}
            </span>
          )}
        </div>
      </div>

      {/* ── ACCOUNT section ─────────────────────────────── */}
      <SectionLabel label="Account" />
      <MenuItem
        icon={<IdcardOutlined />} color={COLORS.accentBlue}
        label="My Profile" sub="View & edit your details"
        onClick={() => { setUserPopOpen(false); setProfileOpen(true); }}
      />
      <MenuItem
        icon={<SettingOutlined />} color="#7C3AED"
        label="Account Settings" sub="Preferences & security"
        shortcut="⌘,"
        onClick={() => { setUserPopOpen(false); navigate('/settings'); }}
      />
      <MenuItem
        icon={<LockOutlined />} color="#047857"
        label="Change Password" sub="Update your credentials"
        onClick={() => { setUserPopOpen(false); navigate('/settings'); }}
      />

      {/* ── WORKSPACE section ───────────────────────────── */}
      <Divider style={{ margin:'4px 0' }} />
      <SectionLabel label="Workspace" />
      <MenuItem
        icon={<NotificationOutlined />} color="#D97706"
        label="Notification Preferences" sub="Manage alert channels"
        onClick={() => { setUserPopOpen(false); navigate('/settings'); }}
      />
      <MenuItem
        icon={<KeyOutlined />} color="#0891B2"
        label="Keyboard Shortcuts" sub="Speed up your workflow"
        shortcut="⌘K"
        onClick={() => { setUserPopOpen(false); setShortcutsOpen(true); }}
        right={null}
      />

      {/* ── APPEARANCE section ──────────────────────────── */}
      <Divider style={{ margin:'4px 0' }} />
      <SectionLabel label="Appearance" />
      <div style={{ padding:'4px 14px 10px' }}>
        <div style={{
          display:'flex', alignItems:'center', gap:6,
          marginBottom:8,
        }}>
          <BgColorsOutlined style={{ fontSize:13, color:COLORS.accentBlue }} />
          <span style={{ fontSize:12, fontWeight:500, color:COLORS.topbarTextColor }}>Theme</span>
          <span style={{
            marginLeft:'auto', fontSize:11,
            color: COLORS.topbarMutedColor,
          }}>{activeTheme?.name}</span>
        </div>
        <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
          {allThemes.map(t => {
            const [sidebar, accent] = t.preview;
            const isActive = t.key === activeTheme?.key;
            return (
              <Tooltip key={t.key} title={t.name}>
                <div
                  onClick={() => applyTheme(t.key)}
                  style={{
                    width:28, height:28, borderRadius:8, cursor:'pointer',
                    border: isActive ? `2px solid ${accent}` : '2px solid transparent',
                    boxShadow: isActive ? `0 0 0 3px ${accent}35` : 'none',
                    overflow:'hidden', transition:'all 0.15s', position:'relative',
                    display:'flex',
                  }}
                  onMouseEnter={e => { if (!isActive) e.currentTarget.style.border=`2px solid ${accent}80`; }}
                  onMouseLeave={e => { if (!isActive) e.currentTarget.style.border='2px solid transparent'; }}
                >
                  <div style={{ width:'40%', background:sidebar }} />
                  <div style={{ flex:1, background:t.preview[3] }} />
                  {isActive && (
                    <div style={{
                      position:'absolute', inset:0,
                      display:'flex', alignItems:'center', justifyContent:'center',
                    }}>
                      <CheckOutlined style={{ fontSize:10, color:accent, fontWeight:900 }} />
                    </div>
                  )}
                </div>
              </Tooltip>
            );
          })}
        </div>
      </div>

      {/* ── HELP section ────────────────────────────────── */}
      <Divider style={{ margin:'4px 0' }} />
      <SectionLabel label="Help" />
      <MenuItem
        icon={<QuestionCircleOutlined />} color="#B45309"
        label="Help & Support" sub="Docs, guides & contact"
        onClick={() => {}}
      />
      <MenuItem
        icon={<FireOutlined />} color="#DC2626"
        label="What's New" sub="Latest updates & features"
        badge={3}
        onClick={() => {}}
      />

      {/* ── Footer: sign out + version ──────────────────── */}
      <Divider style={{ margin:'6px 0 0' }} />
      <div style={{ padding:'10px 14px 12px', display:'flex', alignItems:'center', gap:10 }}>
        <div
          onClick={() => { setUserPopOpen(false); onLogout(); }}
          style={{
            flex:1, display:'flex', alignItems:'center', justifyContent:'center', gap:8,
            padding:'8px 0', borderRadius:8, cursor:'pointer',
            background:'#FEF2F2', border:'1px solid #FECACA',
            color:'#DC2626', fontWeight:600, fontSize:13,
            transition:'all 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background='#FEE2E2'; e.currentTarget.style.borderColor='#EF4444'; }}
          onMouseLeave={e => { e.currentTarget.style.background='#FEF2F2'; e.currentTarget.style.borderColor='#FECACA'; }}
        >
          <LogoutOutlined style={{ fontSize:14 }} />
          Sign Out
        </div>
        <div style={{
          fontSize:10, color:COLORS.topbarMutedColor, lineHeight:1.5,
          textAlign:'right', flexShrink:0,
        }}>
          <div style={{ fontWeight:600 }}>POB v2.0</div>
          <div style={{ opacity:.7 }}>Build 2025</div>
        </div>
      </div>
    </div>
  );

  const breadcrumbs = getBreadcrumbs();

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif" }}>

      {/* ── Sidebar ── */}
      <div style={{
        width: collapsed ? COLORS.sidebarCollapsed : COLORS.sidebarWidth,
        minWidth: collapsed ? COLORS.sidebarCollapsed : COLORS.sidebarWidth,
        background: SIDEBAR.bg,
        display: 'flex', flexDirection: 'column',
        transition: 'width 0.25s cubic-bezier(0.4,0,0.2,1)',
        overflow: 'hidden',
        boxShadow: SIDEBAR.shadow,
        zIndex: 100,
      }}>

        {/* Logo */}
        <div style={{
          height: COLORS.headerHeight,
          display: 'flex', alignItems: 'center',
          padding: collapsed ? '0 12px' : '0 16px',
          borderBottom: `1px solid ${SIDEBAR.border}`,
          gap: 10, flexShrink: 0,
        }}>
          <img src="/logo/image.png" alt="Marconi.ng EPC Limited"
            style={{ width: collapsed ? 32 : 36, height: collapsed ? 32 : 36,
              borderRadius: 6, objectFit: 'contain', flexShrink: 0, background: '#fff', padding: 2 }} />
          {!collapsed && (
            <div>
              <div style={{ color: SIDEBAR.logoText, fontWeight: 700, fontSize: 13, lineHeight: 1.2, letterSpacing: '0.01em' }}>
                Apex POB
              </div>
              <div style={{ color: SIDEBAR.logoSubtext, fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Marconi.ng EPC
              </div>
            </div>
          )}
        </div>

        {/* Nav */}
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', paddingBottom: 8 }}
          className="pob-sidebar-scroll">
          {NAV_GROUPS.map(group => {
            const visibleItems = group.items.filter(item => canSee(item.permission, item.globalAdminOnly));
            if (visibleItems.length === 0) return null;
            return (
              <div key={group.label} style={{ marginTop: 12 }}>
                {!collapsed && (
                  <div style={{
                    padding: '4px 16px', fontSize: 10, fontWeight: 700,
                    color: SIDEBAR.groupLabel, letterSpacing: '0.1em',
                    textTransform: 'uppercase', marginBottom: 2,
                  }}>{group.label}</div>
                )}
                {collapsed && <div style={{ height: 8 }} />}
                {visibleItems.map(item => renderNavItem(item))}
              </div>
            );
          })}
        </div>

        {/* Sidebar footer: style toggle + collapse */}
        <div style={{
          borderTop: `1px solid ${SIDEBAR.border}`,
          padding: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          gap: 4,
        }}>
          {!collapsed && (
            <Tooltip title={sidebarIsLight ? 'Switch to dark sidebar' : 'Switch to light sidebar'} placement="top">
              <div
                onClick={toggleSidebarStyle}
                style={{
                  cursor: 'pointer', width: 32, height: 32, borderRadius: 6,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: SIDEBAR.groupLabel, transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = SIDEBAR.bgHover; e.currentTarget.style.color = SIDEBAR.text; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = SIDEBAR.groupLabel; }}
              >
                <BgColorsOutlined style={{ fontSize: 15 }} />
              </div>
            </Tooltip>
          )}
          <div onClick={() => setCollapsed(!collapsed)} style={{
            cursor: 'pointer', width: 32, height: 32, borderRadius: 6,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: SIDEBAR.text, transition: 'background 0.15s',
          }}
            onMouseEnter={e => e.currentTarget.style.background = SIDEBAR.bgHover}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            {collapsed ? <MenuUnfoldOutlined style={{ fontSize: 16 }} /> : <MenuFoldOutlined style={{ fontSize: 16 }} />}
          </div>
        </div>
      </div>

      {/* ── Main area ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

        {/* ── Top bar ── */}
        <div style={{
          height: COLORS.headerHeight,
          background: COLORS.topbarBg,
          borderBottom: `1px solid ${COLORS.topbarBorder}`,
          display: 'flex', alignItems: 'center',
          padding: '0 16px 0 20px', gap: 8,
          flexShrink: 0, zIndex: 50,
        }}>

          {/* Breadcrumb */}
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 5, overflow: 'hidden' }}>
            {breadcrumbs.map((crumb, i) => (
              <React.Fragment key={`${crumb.path}-${i}`}>
                {i > 0 && <span style={{ color: '#C4C9D0', fontSize: 14 }}>/</span>}
                <span
                  onClick={() => navigate(crumb.path)}
                  style={{
                    fontSize: 13,
                    color: i === breadcrumbs.length - 1 ? COLORS.topbarTextColor : COLORS.topbarMutedColor,
                    fontWeight: i === breadcrumbs.length - 1 ? 600 : 400,
                    cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 4,
                    whiteSpace: 'nowrap', transition: 'color 0.15s',
                  }}
                  onMouseEnter={e => { if (i < breadcrumbs.length - 1) e.currentTarget.style.color = COLORS.accentBlue; }}
                  onMouseLeave={e => { if (i < breadcrumbs.length - 1) e.currentTarget.style.color = COLORS.topbarMutedColor; }}
                >
                  {crumb.icon && <span style={{ fontSize: 12 }}>{crumb.icon}</span>}
                  {crumb.label}
                </span>
              </React.Fragment>
            ))}
          </div>

          {/* ── Right side controls ── */}
          <Space size={2} style={{ flexShrink: 0 }}>

            {/* Search */}
            <div style={{ position: 'relative', marginRight: 4 }}>
              {searchOpen ? (
                <div style={{ display: 'flex', alignItems: 'center', position: 'relative' }}>
                  <Input
                    ref={searchRef}
                    value={searchVal}
                    onChange={e => setSearchVal(e.target.value)}
                    placeholder="Search modules…"
                    prefix={<SearchOutlined style={{ color: '#9CA3AF' }} />}
                    suffix={
                      <CloseOutlined
                        style={{ color: '#9CA3AF', cursor: 'pointer', fontSize: 12 }}
                        onClick={() => { setSearchOpen(false); setSearchVal(''); }}
                      />
                    }
                    onKeyDown={e => {
                      if (e.key === 'Escape') { setSearchOpen(false); setSearchVal(''); }
                      if (e.key === 'Enter' && searchResults.length > 0) {
                        navigate(searchResults[0].key);
                        setSearchOpen(false); setSearchVal('');
                      }
                    }}
                    style={{ width: 220, borderRadius: 6, fontSize: 13 }}
                    size="small"
                  />
                  {searchDropdown}
                </div>
              ) : (
                <Tooltip title="Global search (Ctrl+K)">
                  <div onClick={openSearch} style={iconBtnStyle}>
                    <SearchOutlined style={{ fontSize: 17 }} />
                  </div>
                </Tooltip>
              )}
            </div>

            {/* Clock */}
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              padding: '3px 10px', borderRadius: 6,
              background: '#F9FAFB', border: '1px solid #E5E7EB',
              fontVariantNumeric: 'tabular-nums', lineHeight: 1.3,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <ClockCircleOutlined style={{ fontSize: 9, color: '#9CA3AF' }} />
                <span style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 500 }}>{clockDate}</span>
              </div>
              <span style={{ fontSize: 13, color: '#374151', fontWeight: 700, letterSpacing: '0.04em' }}>{clockTime}</span>
            </div>

            {/* Subscription expiry badge — always visible, hides only when active+healthy */}
            {sub && (
              <Tooltip title={subTooltip} placement="bottomRight">
                <div
                  onClick={() => user?.is_global_admin && navigate('/subscription')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '4px 10px', borderRadius: 6,
                    background: subTheme.bg,
                    border: `1px solid ${subTheme.border}`,
                    fontSize: 11.5, color: subTheme.color, fontWeight: 600,
                    cursor: user?.is_global_admin ? 'pointer' : 'default',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <SafetyCertificateOutlined style={{ fontSize: 12 }} />
                  {subLabel
                    ? subLabel
                    : `License · ${formatExpiryDt(sub.expiry_date)}`}
                </div>
              </Tooltip>
            )}

            {/* Fullscreen */}
            <Tooltip title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}>
              <div onClick={toggleFullscreen} style={iconBtnStyle}>
                {isFullscreen
                  ? <FullscreenExitOutlined style={{ fontSize: 17 }} />
                  : <FullscreenOutlined style={{ fontSize: 17 }} />}
              </div>
            </Tooltip>

            {/* System status */}
            <Tooltip title="All systems operational">
              <div style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '4px 10px', borderRadius: 20,
                background: '#F0FDF4', border: '1px solid #86EFAC',
                fontSize: 11, color: '#166534', fontWeight: 600,
                cursor: 'default',
              }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#22C55E', animation: 'statusPulse 2s infinite' }} />
                Online
              </div>
            </Tooltip>

            {/* Theme switcher */}
            <ThemeSwitcher iconColor={COLORS.topbarIconColor} />

            {/* Notifications */}
            <Popover
              open={notifOpen}
              onOpenChange={setNotifOpen}
              content={notifPanel}
              trigger="click"
              placement="bottomRight"
              arrow={false}
              styles={{ body: { padding: 0 } }}
              overlayStyle={{ width: 360 }}
            >
              <Tooltip title="Notifications" open={notifOpen ? false : undefined}>
                <Badge count={unreadCount} size="small" offset={[-3, 3]}
                  style={{ background: '#EF4444' }}>
                  <div style={{
                    ...iconBtnStyle,
                    background: notifOpen ? '#EFF6FF' : 'transparent',
                    color: notifOpen ? COLORS.accentBlue : COLORS.topbarIconColor,
                  }}>
                    <BellOutlined style={{ fontSize: 17 }} />
                  </div>
                </Badge>
              </Tooltip>
            </Popover>

            {/* App launcher */}
            <Popover
              open={appsOpen}
              onOpenChange={setAppsOpen}
              content={appsPanel}
              trigger="click"
              placement="bottomRight"
              arrow={false}
              styles={{ body: { padding: 0 } }}
              overlayStyle={{ width: 340 }}
            >
              <Tooltip title="All modules" open={appsOpen ? false : undefined}>
                <div style={{
                  ...iconBtnStyle,
                  background: appsOpen ? '#EFF6FF' : 'transparent',
                  color: appsOpen ? COLORS.accentBlue : COLORS.topbarIconColor,
                }}>
                  <AppstoreOutlined style={{ fontSize: 17 }} />
                </div>
              </Tooltip>
            </Popover>

            {/* Divider */}
            <div style={{ width: 1, height: 22, background: '#E5E7EB', margin: '0 4px' }} />

            {/* User popover */}
            <Popover
              open={userPopOpen}
              onOpenChange={setUserPopOpen}
              content={userPopPanel}
              trigger="click"
              placement="bottomRight"
              arrow={false}
              styles={{ body: { padding: 0, borderRadius: 12, overflow: 'hidden' } }}
              overlayStyle={{ width: 316 }}
            >
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '5px 8px', borderRadius: 8, cursor: 'pointer',
                transition: 'all 0.15s',
                background: userPopOpen ? '#EFF6FF' : 'transparent',
                border: userPopOpen ? '1px solid #BAE0FF' : '1px solid transparent',
              }}
                onMouseEnter={e => {
                  if (!userPopOpen) { e.currentTarget.style.background='#F3F4F6'; e.currentTarget.style.borderColor='#E1E4E8'; }
                }}
                onMouseLeave={e => {
                  if (!userPopOpen) { e.currentTarget.style.background='transparent'; e.currentTarget.style.borderColor='transparent'; }
                }}
              >
                {/* Avatar with online ring */}
                <div style={{ position:'relative', flexShrink:0 }}>
                  <div style={{
                    width:32, height:32, borderRadius:8,
                    background:'linear-gradient(135deg, #0078D4 0%, #005A9E 100%)',
                    display:'flex', alignItems:'center', justifyContent:'center',
                    fontSize:13, fontWeight:700, color:'white',
                  }}>
                    {initials}
                  </div>
                  <div style={{
                    position:'absolute', bottom:0, right:0,
                    width:9, height:9, borderRadius:'50%',
                    background:'#22C55E', border:'1.5px solid white',
                  }} />
                </div>

                <div style={{ display:'flex', flexDirection:'column', lineHeight:1, minWidth:0 }}>
                  <span style={{ fontSize:12.5, fontWeight:600, color: userPopOpen ? COLORS.accentBlue : COLORS.topbarTextColor, whiteSpace:'nowrap' }}>
                    {user?.first_name || user?.username || 'Admin'}
                  </span>
                  <span style={{ fontSize:10.5, color: COLORS.topbarMutedColor, marginTop:2, whiteSpace:'nowrap' }}>
                    {user?.is_superuser ? 'Super Admin' : 'User'}
                  </span>
                </div>
                <DownOutlined style={{
                  fontSize:10, color: userPopOpen ? COLORS.accentBlue : '#9CA3AF',
                  transform: userPopOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition:'transform 0.2s',
                }} />
              </div>
            </Popover>
          </Space>
        </div>

        {/* Page content */}
        <div style={{ flex: 1, overflowY: 'auto', background: COLORS.contentBg, padding: 0 }}>
          {children}
        </div>
      </div>

      {/* ── Profile modal ── */}
      <Modal
        open={profileOpen}
        onCancel={() => setProfileOpen(false)}
        footer={[
          <Button key="close" onClick={() => setProfileOpen(false)}>Close</Button>,
          <Button key="settings" type="primary" onClick={() => { setProfileOpen(false); navigate('/settings'); }}>
            Account Settings
          </Button>,
        ]}
        title={
          <Space>
            <IdcardOutlined style={{ color: COLORS.accentBlue }} />
            My Profile
          </Space>
        }
        width={420}
      >
        <div style={{ textAlign: 'center', padding: '20px 0 12px' }}>
          <Avatar size={72} style={{
            background: 'linear-gradient(135deg, #0078D4, #005A9E)',
            fontSize: 28, fontWeight: 700, marginBottom: 12,
          }}>
            {(user?.first_name?.[0] || user?.username?.[0] || 'A').toUpperCase()}
          </Avatar>
          <div style={{ fontWeight: 700, fontSize: 18, color: '#1F2937' }}>
            {user?.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : user?.username}
          </div>
          <div style={{ fontSize: 13, color: '#6B7A8D', marginTop: 4 }}>
            {user?.is_superuser
              ? <Tag color="blue" style={{ borderRadius: 10 }}>Super Administrator</Tag>
              : <Tag style={{ borderRadius: 10 }}>User</Tag>}
          </div>
        </div>
        <Divider style={{ margin: '12px 0' }} />
        <Descriptions column={1} size="small" styles={{ label: { color: '#6B7A8D', fontWeight: 500 } }}>
          <Descriptions.Item label="Username">{user?.username || '—'}</Descriptions.Item>
          <Descriptions.Item label="Email">{user?.email || '—'}</Descriptions.Item>
          <Descriptions.Item label="User ID">#{user?.id || '—'}</Descriptions.Item>
          <Descriptions.Item label="Status">
            {user?.is_active !== false
              ? <span style={{ color: '#22C55E', fontWeight: 600 }}>● Active</span>
              : <span style={{ color: '#EF4444', fontWeight: 600 }}>● Inactive</span>}
          </Descriptions.Item>
        </Descriptions>
      </Modal>

      {/* ── Keyboard Shortcuts modal ── */}
      <Modal
        open={shortcutsOpen}
        onCancel={() => setShortcutsOpen(false)}
        footer={null}
        title={<Space><KeyOutlined style={{ color: COLORS.accentBlue }} />Keyboard Shortcuts</Space>}
        width={460}
      >
        {[
          { group: 'Navigation', items: [
            { keys: ['/', '⌘K'], desc: 'Quick search modules' },
            { keys: ['G', 'D'],  desc: 'Go to Dashboard' },
            { keys: ['G', 'P'],  desc: 'Go to Personnel' },
            { keys: ['G', 'A'],  desc: 'Go to Attendance' },
            { keys: ['G', 'V'],  desc: 'Go to Visitors' },
          ]},
          { group: 'Layout', items: [
            { keys: ['['],         desc: 'Collapse / expand sidebar' },
            { keys: ['F11'],       desc: 'Toggle fullscreen' },
          ]},
          { group: 'General', items: [
            { keys: ['⌘', ','],   desc: 'Open Account Settings' },
            { keys: ['Esc'],       desc: 'Close popover / modal' },
          ]},
        ].map(group => (
          <div key={group.group} style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', color: '#9CA3AF', textTransform: 'uppercase', marginBottom: 8 }}>{group.group}</div>
            {group.items.map(item => (
              <div key={item.desc} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'6px 0', borderBottom:'1px solid #f0f0f0' }}>
                <span style={{ fontSize: 13, color: '#374151' }}>{item.desc}</span>
                <Space size={4}>
                  {item.keys.map((k, i) => (
                    <kbd key={i} style={{ background:'#F3F4F6', border:'1px solid #E5E7EB', borderBottom:'2px solid #D1D5DB', borderRadius:5, padding:'2px 7px', fontSize:12, fontFamily:'monospace', color:'#374151' }}>{k}</kbd>
                  ))}
                </Space>
              </div>
            ))}
          </div>
        ))}
      </Modal>

      {/* ARIA — floats over every page */}
      <ARIAWidget />

      <style>{`
        .pob-sidebar-scroll::-webkit-scrollbar { width: 4px; }
        .pob-sidebar-scroll::-webkit-scrollbar-track { background: transparent; }
        .pob-sidebar-scroll::-webkit-scrollbar-thumb { background: ${SIDEBAR.scrollThumb}; border-radius: 2px; }
        .pob-sidebar-scroll::-webkit-scrollbar-thumb:hover { background: ${SIDEBAR.scrollThumbHover}; }
        .pob-notif-scroll::-webkit-scrollbar { width: 4px; }
        .pob-notif-scroll::-webkit-scrollbar-track { background: transparent; }
        .pob-notif-scroll::-webkit-scrollbar-thumb { background: #E5E7EB; border-radius: 2px; }
        @keyframes statusPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>

      {/* ── Global Search Modal ── */}
      <GlobalSearch
        open={globalSearchOpen}
        onClose={() => setGlobalSearchOpen(false)}
      />
    </div>
  );
};


export default Layout;
