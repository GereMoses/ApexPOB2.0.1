import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  App,
  Popconfirm,
  Tooltip,
  Badge,
  Drawer,
  Card,
  Row,
  Col,
  Upload,
  Switch,
  Statistic,
  Alert,
  Typography,
  Divider,
  Progress,
  Skeleton,
  Spin,
  Tabs,
  List,
  Empty,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  WifiOutlined,
  DisconnectOutlined,
  ThunderboltOutlined,
  UploadOutlined,
  SearchOutlined,
  FilterOutlined,
  ExportOutlined,
  ImportOutlined,
  EyeOutlined,
  DesktopOutlined,
  AppstoreOutlined,
  RadarChartOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  InfoCircleOutlined,
  RobotOutlined,
  ClockCircleFilled,
  GlobalOutlined,
  CheckOutlined,
  StopOutlined,
  ScanOutlined,
} from '@ant-design/icons';
import { deviceAPI } from '../../../services/deviceAPI';
import apiService from '../../../services/api';

const { Option } = Select;
const { Search } = Input;
const { Title, Text } = Typography;

// ─── Pure helpers (module scope — safe to call before component renders) ──────

const CONNECTION_MODE_META = {
  adms:       { label: 'ADMS',       color: 'purple', description: 'Device pushes to server' },
  direct:     { label: 'Direct',     color: 'blue',   description: 'Server polls via ZKLib' },
  both:       { label: 'Both',       color: 'cyan',   description: 'ADMS + ZKLib polling' },
  controller: { label: 'Controller', color: 'gold',   description: 'InBio/C3 access panel (driver pending)' },
};

const READER_PURPOSE_META = {
  ATTENDANCE:   { label: 'T&A',         color: 'blue',   deviceType: 0 },
  ACCESS_ENTRY: { label: 'Entry',        color: 'green',  deviceType: 1 },
  ACCESS_EXIT:  { label: 'Exit',         color: 'cyan',   deviceType: 1 },
  MUSTERING:    { label: 'Mustering',    color: 'orange', deviceType: 2 },
  POB:          { label: 'POB',          color: 'purple', deviceType: 1 },
  EMERGENCY:    { label: 'Emergency',    color: 'red',    deviceType: 3 },
  TRANSPORT_CHECKIN: { label: 'Transport check-in', color: 'geekblue', deviceType: 1 },
};

const getReaderPurposeName  = (p) => (READER_PURPOSE_META[p] || READER_PURPOSE_META.ATTENDANCE).label;
const getReaderPurposeColor = (p) => (READER_PURPOSE_META[p] || READER_PURPOSE_META.ATTENDANCE).color;
const purposeToDeviceType   = (p) => (READER_PURPOSE_META[p] || READER_PURPOSE_META.ATTENDANCE).deviceType;

// kept for legacy read-only display (device_type integer still stored in DB)
const getDeviceTypeName = (deviceType) => {
  const types = { 0: 'Attendance', 1: 'Access Control', 2: 'Mustering', 3: 'Emergency' };
  return types[deviceType] || 'Unknown';
};

const getDeviceTypeColor = (deviceType) => {
  const colors = { 0: 'blue', 1: 'green', 2: 'orange', 3: 'red' };
  return colors[deviceType] || 'default';
};

const getStatusColor = (status) => {
  switch (status) {
    case 'online': return 'success';
    case 'offline': return 'error';
    default: return 'default';
  }
};

const getActivityColor = (lastActivity) => {
  if (!lastActivity) return 'default';
  const diffMinutes = (Date.now() - new Date(lastActivity)) / 60000;
  if (diffMinutes < 5) return 'green';
  if (diffMinutes < 30) return 'orange';
  return 'red';
};

const getRelativeTime = (lastActivity) => {
  if (!lastActivity) return 'Never';
  const diffMinutes = (Date.now() - new Date(lastActivity)) / 60000;
  if (diffMinutes < 1) return 'Just now';
  if (diffMinutes < 60) return `${Math.floor(diffMinutes)}m ago`;
  if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)}h ago`;
  return `${Math.floor(diffMinutes / 1440)}d ago`;
};

const formatDateTime = (dt) => dt ? new Date(dt).toLocaleString() : '—';

const getSignalColor = (s) => {
  if (!s) return '#ff4d4f';
  if (s >= 80) return '#52c41a';
  if (s >= 60) return '#faad14';
  return '#ff4d4f';
};

const DeviceList = ({ onDeviceSelect, refreshTrigger }) => {
  const { message, modal } = App.useApp();
  const [devices, setDevices] = useState([]);
  const [totalDevices, setTotalDevices] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingDevice, setEditingDevice] = useState(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [filters, setFilters] = useState({
    search: '',
    area_id: null,
    device_type: null,
    status: null
  });
  const [areas, setAreas] = useState([]);
  const [zones, setZones] = useState([]);
  const [form] = Form.useForm();
  const readerPurpose = Form.useWatch('reader_purpose', form);
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [fileList, setFileList] = useState([]);
  const [stats, setStats] = useState({
    total: 0,
    online: 0,
    offline: 0,
    byType: {},
    byArea: {}
  });
  const [connectionTestLoading, setConnectionTestLoading] = useState({});
  const [bulkActionLoading, setBulkActionLoading] = useState(false);

  // ── View-details drawer state ─────────────────────────────────────────────
  const [viewDevice, setViewDevice] = useState(null);
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);

  // ── Time sync state ───────────────────────────────────────────────────────
  const [timeSyncLoading, setTimeSyncLoading] = useState({});  // keyed by sn
  const [deviceTimes, setDeviceTimes] = useState({});          // { sn: { device_time, server_time } }
  const [driftMap, setDriftMap] = useState({});                // { sn: { drift_seconds, drift_status, ... } }

  // ── Auto-Detect modal state ───────────────────────────────────────────────
  const [autoDetectVisible, setAutoDetectVisible]     = useState(false);
  const [autoDetectTab, setAutoDetectTab]             = useState('pending');
  // Pending ADMS devices
  const [pendingDevices, setPendingDevices]           = useState([]);
  const [pendingLoading, setPendingLoading]           = useState(false);
  const [admsInfo, setAdmsInfo]                       = useState(null);
  const [approvingSnSet, setApprovingSnSet]           = useState(new Set());
  const [approveForm] = Form.useForm();
  const [approvingSn, setApprovingSn]                 = useState(null);
  // Network scan
  const [scanStatus, setScanStatus]                   = useState(null);  // null | scan-status response
  const [scanPolling, setScanPolling]                 = useState(false);
  const scanPollRef                                   = useRef(null);
  const [detectedSubnets, setDetectedSubnets]         = useState(null);  // { subnets, note } | null
  // Configure found device inline
  const [configuringSn, setConfiguringSn]             = useState(null);  // SN being configured
  const [configuringSnSaving, setConfiguringSnSaving] = useState(false);
  const [configureFoundForm]                          = Form.useForm();
  // Legacy single-IP probe (kept as manual fallback)
  const [discoverVisible, setDiscoverVisible]         = useState(false);
  const [discoverIp, setDiscoverIp]                   = useState('');
  const [discoverPort, setDiscoverPort]               = useState(4370);
  const [discoverCommKey, setDiscoverCommKey]         = useState(0);
  const [discoverLoading, setDiscoverLoading]         = useState(false);
  const [discoverResult, setDiscoverResult]           = useState(null);
  const [registerLoading, setRegisterLoading]         = useState(false);
  const [registerForm] = Form.useForm();

  // Calculate statistics when devices change
  const deviceStats = useMemo(() => {
    const total = devices.length;
    const online = devices.filter(d => d.status?.toLowerCase() === 'online').length;
    const offline = total - online;
    
    const byType = devices.reduce((acc, device) => {
      const type = getDeviceTypeName(device.device_type);
      acc[type] = (acc[type] || 0) + 1;
      return acc;
    }, {});
    
    const byArea = devices.reduce((acc, device) => {
      const area = areas.find(a => a.id === device.area_id);
      const areaName = area ? area.name : 'Unassigned';
      acc[areaName] = (acc[areaName] || 0) + 1;
      return acc;
    }, {});
    
    return { total, online, offline, byType, byArea };
  }, [devices, areas]);

  // Update stats when devices change
  useEffect(() => {
    setStats(deviceStats);
  }, [deviceStats]);

  const fetchDrift = async () => {
    try {
      const res = await apiService.get('/iclock/terminals/time-drift');
      const list = Array.isArray(res?.data) ? res.data : [];
      const map = {};
      list.forEach(d => { map[d.sn] = d; });
      setDriftMap(map);
    } catch { /* drift is informational — don't surface errors */ }
  };

  // Fetch devices when component mounts or filters change — reset to page 1 on new filter
  useEffect(() => {
    setCurrentPage(1);
    fetchDevices(false, 1, pageSize);
    fetchAreas();
    fetchZones();
    fetchDrift();
  }, [refreshTrigger, filters]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh device status every 5 seconds (silent — no loading spinner)
  useEffect(() => {
    const timer = setInterval(() => {
      fetchDevices(true);
    }, 5000);
    return () => clearInterval(timer);
  }, [filters]);

  const fetchDevices = async (silent = false, page = currentPage, size = pageSize) => {
    if (!silent) setLoading(true);
    try {
      const params = { page, limit: size, ...filters };

      // Remove empty filters
      Object.keys(params).forEach(key => {
        if (params[key] === null || params[key] === '') {
          delete params[key];
        }
      });

      const response = await deviceAPI.getTerminals(params);
      // Backend may return { data: [...], total: N } or a plain array
      if (response && typeof response === 'object' && !Array.isArray(response)) {
        setDevices(response.data || response.items || []);
        setTotalDevices(response.total ?? (response.data || []).length);
      } else {
        setDevices(response || []);
        setTotalDevices((response || []).length);
      }
    } catch (error) {
      if (!silent) message.error('Failed to fetch devices');
      console.error('Error fetching devices:', error);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const fetchAreas = async () => {
    try {
      const response = await apiService.get('/api/device/areas/');
      setAreas(Array.isArray(response) ? response : []);
    } catch (error) {
      console.error('Error fetching areas:', error);
    }
  };

  const fetchZones = async () => {
    try {
      const response = await apiService.get('/api/v1/zones/', { limit: 200 });
      setZones(Array.isArray(response) ? response : []);
    } catch (error) {
      console.error('Error fetching zones:', error);
    }
  };

  // ── Auto-Detect handlers ──────────────────────────────────────────────────

  const openAutoDetect = (tab = 'pending') => {
    setAutoDetectTab(tab);
    setAutoDetectVisible(true);
    if (tab === 'pending') fetchPendingDevices();
    if (tab === 'scan') { fetchScanStatus(); fetchDetectedSubnets(); }
  };

  const fetchPendingDevices = async () => {
    setPendingLoading(true);
    try {
      const [res, info] = await Promise.all([
        apiService.get('/api/v1/device-management/discovery/pending'),
        apiService.get('/api/v1/device-management/discovery/adms-info').catch(() => null),
      ]);
      setPendingDevices(res?.pending || []);
      if (info) setAdmsInfo(info);
    } catch (e) {
      message.error('Could not load pending devices');
    } finally {
      setPendingLoading(false);
    }
  };

  const fetchScanStatus = async () => {
    try {
      const res = await apiService.get('/api/v1/device-management/discovery/scan-status');
      setScanStatus(res);
    } catch (_) {}
  };

  const fetchDetectedSubnets = async () => {
    try {
      const res = await apiService.get('/api/v1/device-management/discovery/subnets');
      setDetectedSubnets(res);
    } catch (_) {}
  };

  const handleSaveFoundDevice = async (item) => {
    try {
      const values = await configureFoundForm.validateFields();
      setConfiguringSnSaving(true);
      await apiService.patch(`/api/v1/device-management/discovery/configure/${item.sn}`, {
        ...values,
        ip_address: item.ip,
        port:       item.port || 4370,
      });
      message.success(`Device '${values.name}' added to device list`);
      setConfiguringSn(null);
      configureFoundForm.resetFields();
      fetchDevices();
      fetchScanStatus();
    } catch (e) {
      if (!e.errorFields) message.error(e.message || 'Registration failed');
    } finally {
      setConfiguringSnSaving(false);
    }
  };

  const startNetworkScan = async () => {
    try {
      await apiService.post('/api/v1/device-management/discovery/scan');
      setScanStatus(s => ({ ...s, running: true, probed: 0, found: [], found_count: 0 }));
      // Poll every 2 s until scan finishes
      if (scanPollRef.current) clearInterval(scanPollRef.current);
      setScanPolling(true);
      scanPollRef.current = setInterval(async () => {
        const status = await apiService.get('/api/v1/device-management/discovery/scan-status').catch(() => null);
        if (status) {
          setScanStatus(status);
          if (!status.running) {
            clearInterval(scanPollRef.current);
            setScanPolling(false);
            // Refresh device list so newly found devices appear
            fetchDevices();
          }
        }
      }, 2000);
    } catch (e) {
      message.error(e.message || 'Could not start scan');
    }
  };

  // Clean up scan poll on unmount
  useEffect(() => () => { if (scanPollRef.current) clearInterval(scanPollRef.current); }, []);

  const handleApproveDevice = async (sn) => {
    try {
      const values = await approveForm.validateFields();
      setApprovingSnSet(prev => new Set(prev).add(sn));
      setApprovingSn(sn);
      await apiService.post(`/api/v1/device-management/discovery/approve/${sn}`, values);
      message.success(`Device ${sn} approved`);
      approveForm.resetFields();
      setApprovingSn(null);
      fetchPendingDevices();
      fetchDevices();
    } catch (e) {
      if (!e.errorFields) message.error(e.message || 'Approval failed');
    } finally {
      setApprovingSnSet(prev => { const n = new Set(prev); n.delete(sn); return n; });
    }
  };

  const handleRejectDevice = async (sn) => {
    try {
      await apiService.post(`/api/v1/device-management/discovery/reject/${sn}`);
      message.success(`Device ${sn} rejected`);
      fetchPendingDevices();
    } catch (e) {
      message.error(e.message || 'Rejection failed');
    }
  };

  // ── Discover-by-IP handlers ───────────────────────────────────────────────
  const handleDiscover = async () => {
    if (!discoverIp) { message.warning('Enter an IP address'); return; }
    setDiscoverLoading(true);
    setDiscoverResult(null);
    try {
      const result = await deviceAPI.zkQuickPing({
        ip_address: discoverIp,
        port: discoverPort,
        device_password: discoverCommKey,
      });
      setDiscoverResult(result);
      if (result.connected) {
        registerForm.setFieldsValue({
          name: result.device_name || `ZKTeco ${discoverIp}`,
          ip_address: discoverIp,
          port: discoverPort,
          device_password: discoverCommKey,
          connection_mode: 'direct',
          auto_poll: true,
          poll_interval_sec: 300,
        });
      }
    } catch (e) {
      setDiscoverResult({ connected: false, error: e.message });
    } finally {
      setDiscoverLoading(false);
    }
  };

  const handleRegisterDirect = async () => {
    try {
      const values = await registerForm.validateFields();
      setRegisterLoading(true);
      await deviceAPI.zkRegisterDevice(values);
      message.success(`${values.name} registered successfully`);
      setDiscoverVisible(false);
      setDiscoverResult(null);
      setDiscoverIp('');
      registerForm.resetFields();
      fetchDevices();
    } catch (e) {
      if (!e.errorFields) message.error(e.message || 'Registration failed');
    } finally {
      setRegisterLoading(false);
    }
  };

  const handleAddDevice = () => {
    setEditingDevice(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEditDevice = (device) => {
    setEditingDevice(device);
    form.setFieldsValue({
      sn: device.sn,
      alias: device.alias,
      ip_address: device.ip_address,
      area_id: device.area_id,
      device_type: device.device_type,
      zone_id: device.zone_id,
      reader_purpose: device.reader_purpose || 'ATTENDANCE',
      device_name: device.device_name,
      device_model: device.device_model,
      comm_key: device.comm_key,
      connection_mode: device.connection_mode || 'adms',
    });
    setModalVisible(true);
  };

  const handleDeleteDevice = async (deviceId, force = false) => {
    try {
      await deviceAPI.deleteTerminal(deviceId, force);
      message.success('Device deleted successfully');
      fetchDevices();
    } catch (error) {
      // 409 = has transactions → ask user if they want to force-delete
      if (error.message && error.message.includes('transactions')) {
        modal.confirm({
          title: 'Device has attendance records',
          content: `${error.message} All attendance history for this device will be permanently removed.`,
          okText: 'Force Delete',
          okType: 'danger',
          cancelText: 'Cancel',
          onOk: () => handleDeleteDevice(deviceId, true),
        });
      } else {
        message.error(error.message || 'Failed to delete device');
        console.error('Error deleting device:', error);
      }
    }
  };

  const handleModalOk = async () => {
    try {
      const values = await form.validateFields();

      // Auto-derive device_type from reader_purpose; clear inapplicable location field
      values.device_type = purposeToDeviceType(values.reader_purpose);
      if (values.reader_purpose === 'ATTENDANCE') {
        delete values.zone_id;
      } else {
        delete values.area_id;
      }

      // Coerce integer fields that come back as strings from Input fields
      if (values.zone_id !== undefined && values.zone_id !== null && values.zone_id !== '') {
        values.zone_id = parseInt(values.zone_id, 10);
      } else {
        delete values.zone_id;
      }
      if (values.port !== undefined && values.port !== null && values.port !== '') {
        values.port = parseInt(values.port, 10);
      }

      if (editingDevice) {
        // Update existing device
        await deviceAPI.updateTerminal(editingDevice.id, values);
        message.success('Device updated successfully');
      } else {
        // Create new device
        await deviceAPI.createTerminal(values);
        message.success('Device created successfully');
      }
      
      setModalVisible(false);
      fetchDevices();
    } catch (error) {
      if (error.errorFields) {
        // Validation error
        return;
      }
      message.error(`Failed to ${editingDevice ? 'update' : 'create'} device`);
      console.error('Error saving device:', error);
    }
  };

  const handleBulkAction = async (action) => {
    if (selectedRowKeys.length === 0) {
      message.warning('Please select devices first');
      return;
    }

    try {
      setLoading(true);
      
      switch (action) {
        case 'delete':
          await Promise.all(
            selectedRowKeys.map(sn => {
              const dev = devices.find(d => d.sn === sn);
              return dev ? deviceAPI.deleteTerminal(dev.id, true) : Promise.resolve();
            })
          );
          message.success(`Deleted ${selectedRowKeys.length} devices`);
          break;
        case 'reboot':
          await Promise.all(
            selectedRowKeys.map(sn => deviceAPI.sendCommand({ sn, cmd: 'REBOOT' }))
          );
          message.success(`Reboot command sent to ${selectedRowKeys.length} devices`);
          break;
        case 'syncTime':
          await Promise.all(
            selectedRowKeys.map(sn => deviceAPI.admsSyncTime(sn))
          );
          message.info(`Time sync queued for ${selectedRowKeys.length} device(s) — will apply on next heartbeat`);
          break;
        case 'clearAdmin':
          await Promise.all(
            selectedRowKeys.map(sn => deviceAPI.sendCommand({ sn, cmd: 'CLEAR ADMIN' }))
          );
          message.success(`Clear admin command sent to ${selectedRowKeys.length} devices`);
          break;
        case 'clearData':
          await Promise.all(
            selectedRowKeys.map(sn => deviceAPI.sendCommand({ sn, cmd: 'CLEAR DATA' }))
          );
          message.success(`Clear data command sent to ${selectedRowKeys.length} devices`);
          break;
        default:
          break;
      }
      
      setSelectedRowKeys([]);
      fetchDevices();
    } catch (error) {
      message.error(`Failed to perform ${action} action`);
      console.error('Error performing bulk action:', error);
    } finally {
      setLoading(false);
    }
  };

  const executeBulkAction = (action) => handleBulkAction(action);

  const testDeviceConnection = async (sn) => {
    setConnectionTestLoading(p => ({ ...p, [sn]: true }));
    try {
      await deviceAPI.sendCommand({ sn, cmd: 'CHECK' });
      message.success(`Connection test sent to ${sn}`);
    } catch (err) {
      message.error(`Connection test failed: ${err.message}`);
    } finally {
      setConnectionTestLoading(p => ({ ...p, [sn]: false }));
    }
  };


  const fetchDeviceTime = async (sn, ip, port = 4370) => {
    setTimeSyncLoading(p => ({ ...p, [sn]: 'reading' }));
    try {
      const result = await deviceAPI.zkQuickGetTime({ ip_address: ip, port });
      setDeviceTimes(p => ({ ...p, [sn]: result }));
    } catch (e) {
      message.error(`Could not read time from ${sn}: ${e.message}`);
    } finally {
      setTimeSyncLoading(p => ({ ...p, [sn]: false }));
    }
  };

  const handleSyncTime = async (sn, ip, port = 4370, connectionMode) => {
    setTimeSyncLoading(p => ({ ...p, [sn]: 'syncing' }));
    const isAdms = !connectionMode || connectionMode === 'adms' || (!ip && connectionMode !== 'direct');
    try {
      if (isAdms) {
        // ADMS push devices: queue DATE TIME command via the ADMS endpoint (no IP needed)
        await deviceAPI.admsSyncTime(sn);
        message.info(`Time sync queued for ${sn} — the device will apply it on its next heartbeat (~10–30 s). The options block also auto-syncs the clock on every heartbeat.`);
      } else {
        const result = await deviceAPI.zkQuickSyncTime({ ip_address: ip, port });
        if (result.method === 'adms_queued') {
          message.info(`Time sync queued for ${sn} — device will apply on next heartbeat (~10–30 s)`);
        } else {
          message.success(`Clock synced on ${sn} — device reports: ${result.device_reports}`);
        }
        setDeviceTimes(p => ({
          ...p,
          [sn]: { device_time: result.device_reports, server_time: result.set_to },
        }));
      }
    } catch (e) {
      message.error(`Time sync failed for ${sn}: ${e.message}`);
    } finally {
      setTimeSyncLoading(p => ({ ...p, [sn]: false }));
    }
  };

  const handleImportCSV = async () => {
    if (fileList.length === 0) {
      message.warning('Please select a CSV file');
      return;
    }

    try {
      const file = fileList[0].originFileObj;
      const text = await file.text();
      const lines = text.split('\n');
      
      // Skip header if exists
      const startIndex = lines[0].toLowerCase().includes('sn') ? 1 : 0;
      const devices = [];
      
      for (let i = startIndex; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        
        const [sn, alias, ip, area, commKey] = line.split(',').map(item => item.trim());
        
        if (sn) {
          devices.push({
            sn: sn.replace(/"/g, ''),
            alias: alias?.replace(/"/g, '') || `Terminal ${sn}`,
            ip_address: ip?.replace(/"/g, ''),
            area_id: area ? parseInt(area) : null,
            comm_key: commKey?.replace(/"/g, '') || '0'
          });
        }
      }
      
      const response = await deviceAPI.batchImport({ devices });
      
      if (response.imported > 0) {
        message.success(`Successfully imported ${response.imported} devices`);
        if (response.skipped > 0) {
          message.warning(`${response.skipped} devices were skipped`);
        }
      } else {
        message.error('No devices were imported');
      }
      
      setImportModalVisible(false);
      setFileList([]);
      fetchDevices();
    } catch (error) {
      message.error('Failed to import devices');
      console.error('Error importing devices:', error);
    }
  };

  const getStatusIcon = (status) =>
    status?.toLowerCase() === 'online' ? <WifiOutlined /> : <DisconnectOutlined />;

  const handleViewDetails = (device) => {
    setViewDevice(device);
    setDetailDrawerOpen(true);
    if (onDeviceSelect) onDeviceSelect(device);
  };

  const columns = [
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status, record) => (
        <Badge 
          status={getStatusColor(status)}
          text={status?.toUpperCase()} 
          icon={getStatusIcon(status)}
        />
      ),
      filters: [
        { text: 'Online', value: 'online' },
        { text: 'Offline', value: 'offline' }
      ],
      onFilter: (value, record) => record.status === value
    },
    {
      title: 'Device',
      dataIndex: 'sn',
      key: 'sn',
      width: 120,
      render: (sn, record) => (
        <div>
          <div><strong>{sn}</strong></div>
          <div style={{ fontSize: '12px', color: '#666' }}>{record.alias}</div>
          {record.connection_test_loading && (
            <Spin size="small" />
          )}
        </div>
      )
    },
    {
      title: 'Purpose',
      dataIndex: 'reader_purpose',
      key: 'reader_purpose',
      width: 110,
      render: (purpose, record) => (
        <Tag color={getReaderPurposeColor(purpose)}>
          {getReaderPurposeName(purpose)}
          {record.device_model && (
            <div style={{ fontSize: '10px', color: '#999' }}>
              {record.device_model}
            </div>
          )}
        </Tag>
      ),
      filters: Object.entries(READER_PURPOSE_META).map(([v, m]) => ({ text: m.label, value: v })),
      onFilter: (value, record) => record.reader_purpose === value,
    },
    {
      title: 'IP Address',
      dataIndex: 'ip_address',
      key: 'ip_address',
      width: 165,
      render: (ip, record) => {
        if (!ip) return <Text type="secondary" style={{ fontSize: 12 }}>—</Text>;
        // ADMS and "both" devices have their IP detected automatically by the server
        const autoDetected = record.connection_mode === 'adms' || record.connection_mode === 'both';
        return (
          <Space size={4} direction="vertical" style={{ gap: 2 }}>
            <Text code style={{ fontSize: 12 }}>{ip}</Text>
            {autoDetected && (
              <Tag
                color="green"
                style={{ fontSize: 9, lineHeight: '16px', padding: '0 4px', marginLeft: 0 }}
              >
                auto-detected
              </Tag>
            )}
          </Space>
        );
      },
    },
    {
      title: 'Connection',
      dataIndex: 'connection_mode',
      key: 'connection_mode',
      width: 100,
      render: (mode) => {
        const m = CONNECTION_MODE_META[mode] || CONNECTION_MODE_META.adms;
        return (
          <Tooltip title={m.description}>
            <Tag color={m.color}>{m.label}</Tag>
          </Tooltip>
        );
      },
      filters: Object.entries(CONNECTION_MODE_META).map(([v, m]) => ({ text: m.label, value: v })),
      onFilter: (value, record) => (record.connection_mode || 'adms') === value,
    },
    {
      title: 'Purpose / Location',
      key: 'reader_purpose_loc',
      width: 160,
      render: (_, record) => {
        const area = areas.find(a => a.id === record.area_id);
        const zone = zones.find(z => z.id === record.zone_id);
        const location = area?.name || zone?.name;
        return (
          <div>
            <Tag color={getReaderPurposeColor(record.reader_purpose)}>
              {getReaderPurposeName(record.reader_purpose)}
            </Tag>
            {location && <div style={{ fontSize: '11px', color: '#666', marginTop: 2 }}>{location}</div>}
          </div>
        );
      }
    },
    {
      title: 'Users',
      dataIndex: 'user_count',
      key: 'user_count',
      width: 80,
      render: (count, record) => (
        <div>
          {count || 0}
          <div style={{ fontSize: '10px', color: '#666' }}>users</div>
        </div>
      )
    },
    {
      title: 'Biometrics',
      key: 'biometrics',
      width: 120,
      render: (_, record) => (
        <div style={{ display: 'flex', gap: '4px' }}>
          <div>
            <div style={{ fontSize: '12px', color: '#666' }}>{record.fp_count || 0} FP</div>
            <div style={{ fontSize: '12px', color: '#666' }}>{record.face_count || 0} Face</div>
          </div>
        </div>
      )
    },
    {
      title: 'Last Active',
      dataIndex: 'last_activity',
      key: 'last_activity',
      width: 150,
      render: (date) => (
        <div>
          {formatDateTime(date)}
          {date && (
            <Tag color={getActivityColor(date)}>
              {getRelativeTime(date)}
            </Tag>
          )}
        </div>
      )
    },
    {
      title: 'Sync Status',
      key: 'health_status',
      width: 160,
      render: (_, record) => {
        const statusLower = (record.status || '').toLowerCase();
        const isOnline = statusLower === 'online';
        const lastAct = record.last_activity ? new Date(record.last_activity) : null;
        const diffSec = lastAct ? (Date.now() - lastAct) / 1000 : null;
        const diffMin = diffSec != null ? diffSec / 60 : null;

        let badgeStatus, label, detail, detailColor;

        if (!isOnline) {
          badgeStatus = 'error';
          label = 'Offline';
          if (lastAct) {
            const ago = diffMin < 60
              ? `${Math.round(diffMin)}m ago`
              : diffMin < 1440
                ? `${Math.round(diffMin / 60)}h ago`
                : `${Math.round(diffMin / 1440)}d ago`;
            detail = `Last seen ${ago}`;
            detailColor = '#ef4444';
          } else {
            detail = 'Never connected';
            detailColor = '#94a3b8';
          }
        } else if (!lastAct) {
          badgeStatus = 'warning';
          label = 'Online';
          detail = 'No sync yet';
          detailColor = '#f59e0b';
        } else if (diffMin < 2) {
          badgeStatus = 'success';
          label = 'Syncing';
          detail = `${Math.round(diffSec)}s ago`;
          detailColor = '#22c55e';
        } else if (diffMin < 5) {
          badgeStatus = 'warning';
          label = 'Slow';
          detail = `${Math.round(diffMin)}m since last sync`;
          detailColor = '#f59e0b';
        } else {
          badgeStatus = 'error';
          label = 'Sync stalled';
          detail = `No sync for ${Math.round(diffMin)}m`;
          detailColor = '#ef4444';
        }

        return (
          <div>
            <Badge status={badgeStatus} text={<span style={{ fontSize: 11, fontWeight: 600 }}>{label}</span>} />
            {detail && (
              <div style={{ fontSize: 10, color: detailColor, marginTop: 1, marginLeft: 14 }}>
                {detail}
              </div>
            )}
          </div>
        );
      }
    },
    {
      title: 'Time Drift',
      key: 'time_drift',
      width: 100,
      render: (_, record) => {
        const d = driftMap[record.sn];
        if (!d) return <span style={{ fontSize: 11, color: '#bbb' }}>—</span>;
        const driftAbs = Math.abs(d.drift_seconds ?? 0);
        const tagColor = d.drift_status === 'ok' ? 'success' : d.drift_status === 'warning' ? 'warning' : 'error';
        return (
          <Tooltip title={`${driftAbs}s drift vs server clock`}>
            <Tag color={tagColor} style={{ fontSize: 10, lineHeight: '18px', cursor: 'default' }}>
              {d.drift_status === 'ok' ? `✓ ${driftAbs}s` : `${driftAbs}s`}
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: 'Signal',
      dataIndex: 'signal_strength',
      key: 'signal_strength',
      width: 90,
      render: (signalStrength) => {
        if (signalStrength == null) {
          return <span style={{ fontSize: '11px', color: '#999' }}>N/A</span>;
        }
        return (
          <div>
            <div style={{
              width: '100%', height: '8px',
              backgroundColor: getSignalColor(signalStrength),
              borderRadius: '4px'
            }} />
            <div style={{ fontSize: '10px', color: '#666', marginTop: 2 }}>
              {signalStrength}%
            </div>
          </div>
        );
      }
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 220,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="Edit">
            <Button 
              icon={<EditOutlined />} 
              size="small"
              onClick={() => handleEditDevice(record)}
            />
          </Tooltip>
          
          <Tooltip title="Test Connection">
            <Button 
              icon={<WifiOutlined />} 
              size="small"
              loading={connectionTestLoading[record.sn]}
              onClick={() => testDeviceConnection(record.sn)}
            />
          </Tooltip>
          
          {record.device_type === 3 && (
            <Tooltip title="Emergency Toggle">
              <Button 
                icon={<ThunderboltOutlined />} 
                size="small"
                danger
                onClick={() => deviceAPI.emergencyCommand(record.sn, 'ON')}
              />
            </Tooltip>
          )}
          
          <Tooltip title="Sync Device Clock">
            <Button
              icon={<ClockCircleOutlined />}
              size="small"
              loading={!!timeSyncLoading[record.sn]}
              onClick={() => handleSyncTime(record.sn, record.ip_address, record.port || 4370, record.connection_mode)}
            />
          </Tooltip>

          <Tooltip title="View Details">
            <Button
              icon={<EyeOutlined />}
              size="small"
              onClick={() => handleViewDetails(record)}
            />
          </Tooltip>

          <Popconfirm
            title="Are you sure you want to delete this device?"
            onConfirm={() => handleDeleteDevice(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Tooltip title="Delete">
              <Button 
                icon={<DeleteOutlined />} 
                size="small"
                danger
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      )
    }
  ];

  const rowSelection = {
    selectedRowKeys,
    onChange: setSelectedRowKeys,
    getCheckboxProps: (record) => ({
      disabled: false,
      name: record.sn
    })
  };

  return (
    <div className="device-list">
      {/* Enhanced Toolbar with Statistics */}
      <Card className="device-toolbar" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col span={6}>
            <Space>
              <Title level={4} style={{ margin: 0 }}>Device Management</Title>
              <Text type="secondary">Manage and monitor all devices in the system</Text>
            </Space>
          </Col>
          
          <Col span={18} style={{ textAlign: 'right' }}>
            <Space>
              <Button
                icon={<ImportOutlined />}
                onClick={() => setImportModalVisible(true)}
              >
                Import CSV
              </Button>

              <Button
                icon={<RobotOutlined />}
                type="default"
                onClick={() => openAutoDetect('pending')}
              >
                Auto-Detect Devices
              </Button>

              <Button
                icon={<RadarChartOutlined />}
                onClick={() => { setDiscoverVisible(true); setDiscoverResult(null); }}
                size="small"
                style={{ fontSize: 12 }}
              >
                Manual IP
              </Button>

              <Button
                icon={<PlusOutlined />}
                type="primary"
                onClick={handleAddDevice}
              >
                Add Device
              </Button>
            </Space>
          </Col>
        </Row>
        
        {/* Statistics Cards */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="Total Devices"
                value={stats.total}
                prefix={<DesktopOutlined />}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="Online Devices"
                value={stats.online}
                prefix={<WifiOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="Offline Devices"
                value={stats.offline}
                prefix={<DisconnectOutlined />}
                valueStyle={{ color: '#ff4d4f' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="By Type"
                value={Object.keys(stats.byType).length}
                prefix={<AppstoreOutlined />}
                valueStyle={{ color: '#722ed1' }}
              />
            </Card>
          </Col>
        </Row>

        {/* Search and Filters */}
        <Card size="small" style={{ marginBottom: 16 }}>
          <Row gutter={16} align="middle">
            <Col span={12}>
              <Space>
                <Search
                  placeholder="Search by SN or alias"
                  allowClear
                  enterButton={<SearchOutlined />}
                  onSearch={(value) => setFilters({ ...filters, search: value })}
                  style={{ width: '100%' }}
                />
              </Space>
            </Col>
            
            <Col span={12}>
              <Space>
                <Select
                  placeholder="Filter by Area"
                  allowClear
                  style={{ width: 150 }}
                  onChange={(value) => setFilters({ ...filters, area_id: value })}
                >
                  {areas.map(area => (
                    <Option key={area.id} value={area.id}>{area.name}</Option>
                  ))}
                </Select>
                
                <Select
                  placeholder="Filter by Purpose"
                  allowClear
                  style={{ width: 160 }}
                  onChange={(value) => setFilters({ ...filters, device_type: value })}
                >
                  {Object.entries(READER_PURPOSE_META).map(([v, m]) => (
                    <Option key={v} value={v}>{m.label}</Option>
                  ))}
                </Select>
                
                <Select
                  placeholder="Filter by Status"
                  allowClear
                  style={{ width: 120 }}
                  onChange={(value) => setFilters({ ...filters, status: value })}
                >
                  <Option value="online">Online</Option>
                  <Option value="offline">Offline</Option>
                </Select>
              </Space>
            </Col>
          </Row>
        </Card>
        
        {/* Bulk Actions */}
        {selectedRowKeys.length > 0 && (
          <Card size="small" style={{ marginBottom: 16 }}>
            <Row gutter={16} align="middle">
              <Col span={24}>
                <Space>
                  <span>Selected {selectedRowKeys.length} devices:</span>
                  <Divider type="vertical" />
                  <Space>
                    <Popconfirm
                      title={`Delete ${selectedRowKeys.length} devices?`}
                      onConfirm={() => executeBulkAction('delete')}
                      okText="Yes"
                      cancelText="No"
                    >
                      <Button 
                        size="small" 
                        danger 
                        loading={bulkActionLoading}
                        icon={<DeleteOutlined />}
                      >
                        Delete
                      </Button>
                    </Popconfirm>
                    <Button 
                      size="small" 
                      loading={bulkActionLoading}
                      icon={<ReloadOutlined />}
                      onClick={() => executeBulkAction('reboot')}
                    >
                      Reboot
                    </Button>
                    <Button 
                      size="small" 
                      loading={bulkActionLoading}
                      icon={<ThunderboltOutlined />}
                      onClick={() => executeBulkAction('syncTime')}
                    >
                      Sync Time
                    </Button>
                    <Button 
                      size="small" 
                      loading={bulkActionLoading}
                      icon={<ThunderboltOutlined />}
                      onClick={() => executeBulkAction('clearAdmin')}
                    >
                      Clear Admin
                    </Button>
                    <Button 
                      size="small" 
                      loading={bulkActionLoading}
                      icon={<DeleteOutlined />}
                      onClick={() => executeBulkAction('clearData')}
                    >
                      Clear Data
                    </Button>
                  </Space>
                </Space>
              </Col>
            </Row>
          </Card>
        )}
      </Card>

      {/* Device Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={devices}
          loading={loading}
          rowKey="sn"
          rowSelection={rowSelection}
          pagination={{
            current: currentPage,
            pageSize,
            total: totalDevices,
            showSizeChanger: true,
            showQuickJumper: true,
            pageSizeOptions: ['10', '20', '50', '100'],
            showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} devices`,
            onChange: (page, size) => {
              setCurrentPage(page);
              setPageSize(size);
              fetchDevices(false, page, size);
            },
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* Add/Edit Device Modal */}
      <Modal
        title={editingDevice ? 'Edit Device' : 'Add Device'}
        open={modalVisible}
        onOk={handleModalOk}
        onCancel={() => setModalVisible(false)}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="sn"
                label="Serial Number"
                rules={[{ required: true, message: 'Please enter serial number' }]}
              >
                <Input placeholder="Device serial number" disabled={!!editingDevice} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="alias"
                label="Alias"
                rules={[{ required: true, message: 'Please enter alias' }]}
              >
                <Input placeholder="Device alias" />
              </Form.Item>
            </Col>
          </Row>
          
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="ip_address"
                label="IP Address"
              >
                <Input placeholder="192.168.1.100" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="comm_key"
                label="Communication Key"
              >
                <Input placeholder="0 (default)" />
              </Form.Item>
            </Col>
          </Row>
          
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="connection_mode"
                label="Connection Mode"
                initialValue="adms"
                rules={[{ required: true, message: 'Select connection mode' }]}
              >
                <Select>
                  <Option value="adms">ADMS — device pushes to server</Option>
                  <Option value="direct">Direct — server polls via ZKLib</Option>
                  <Option value="both">Both — ADMS + ZKLib polling</Option>
                  <Option value="controller">Controller — InBio/C3 access panel (driver pending)</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={24}>
              <Form.Item
                name="reader_purpose"
                label="Reader Purpose"
                initialValue="ATTENDANCE"
                rules={[{ required: true, message: 'Select reader purpose' }]}
              >
                <Select>
                  <Option value="ATTENDANCE">T&amp;A Reader (Time &amp; Attendance)</Option>
                  <Option value="ACCESS_ENTRY">Access Control — Entry</Option>
                  <Option value="ACCESS_EXIT">Access Control — Exit</Option>
                  <Option value="MUSTERING">Mustering Station</Option>
                  <Option value="POB">POB (Personnel On Board)</Option>
                  <Option value="EMERGENCY">Emergency Station</Option>
                  <Option value="TRANSPORT_CHECKIN">Transport check-in (helideck / gangway)</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            {(!readerPurpose || readerPurpose === 'ATTENDANCE') && (
              <Col span={24}>
                <Form.Item name="area_id" label="Area (T&A Location)">
                  <Select allowClear placeholder="Select area">
                    {areas.map(area => (
                      <Option key={area.id} value={area.id}>{area.name}</Option>
                    ))}
                  </Select>
                </Form.Item>
              </Col>
            )}
            {readerPurpose && readerPurpose !== 'ATTENDANCE' && (
              <Col span={24}>
                <Form.Item
                  name="zone_id"
                  label="Zone"
                  rules={[{ required: true, message: 'Select the zone this reader controls' }]}
                >
                  <Select allowClear placeholder="Select zone">
                    {zones.map(zone => (
                      <Option key={zone.id} value={zone.id}>{zone.name}</Option>
                    ))}
                  </Select>
                </Form.Item>
              </Col>
            )}
          </Row>
          
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="device_name"
                label="Device Name"
              >
                <Input placeholder="Device model name" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="device_model"
                label="Device Model"
              >
                <Input placeholder="MB20, MB560, etc." />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* ════════════════════════════════════════════════════════════════
          AUTO-DETECT DEVICES MODAL — two tabs:
            1. Pending (ADMS devices that connected and are waiting for approval)
            2. Scan Network (on-demand ZKLib port-4370 subnet scanner)
          ══════════════════════════════════════════════════════════════ */}
      <Modal
        title={
          <Space>
            <RobotOutlined style={{ color: '#4f8ef7' }} />
            <span>Auto-Detect ZKTeco Devices</span>
            <Tag color="blue" style={{ fontSize: 10 }}>No manual IP entry needed</Tag>
          </Space>
        }
        open={autoDetectVisible}
        onCancel={() => {
          setAutoDetectVisible(false);
          if (scanPollRef.current) clearInterval(scanPollRef.current);
          setScanPolling(false);
        }}
        footer={null}
        width={760}
        destroyOnHidden
      >
        <Tabs
          activeKey={autoDetectTab}
          onChange={key => {
            setAutoDetectTab(key);
            if (key === 'pending') fetchPendingDevices();
            if (key === 'scan') { fetchScanStatus(); fetchDetectedSubnets(); }
          }}
          items={[
            {
              key: 'pending',
              label: (
                <span>
                  <ClockCircleFilled style={{ color: '#faad14', marginRight: 6 }} />
                  Waiting for Approval
                  {pendingDevices.length > 0 && (
                    <Badge count={pendingDevices.length} style={{ marginLeft: 8 }} />
                  )}
                </span>
              ),
              children: (
                <div>
                  <Alert
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                    message="ADMS devices connect automatically"
                    description={
                      'When a ZKTeco reader is configured with your server address it pushes its ' +
                      'own IP and serial number here. Just approve it — no IP entry required.'
                    }
                  />

                  <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text type="secondary">
                      {pendingDevices.length === 0
                        ? 'No devices waiting for approval'
                        : `${pendingDevices.length} device${pendingDevices.length > 1 ? 's' : ''} detected and waiting`}
                    </Text>
                    <Button size="small" icon={<ReloadOutlined />} onClick={fetchPendingDevices} loading={pendingLoading}>
                      Refresh
                    </Button>
                  </div>

                  {pendingLoading ? (
                    <Skeleton active />
                  ) : pendingDevices.length === 0 ? (
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        <span>
                          No ADMS devices detected yet.<br />
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            On each ZKTeco reader go to:<br />
                            <strong>Cloud Settings → Server Address</strong><br />
                            and enter:
                          </Text>
                          <br />
                          <Text
                            copyable
                            code
                            style={{ fontSize: 12, marginTop: 6, display: 'inline-block' }}
                          >
                            {admsInfo?.adms_url || `${window.location.origin}/iclock/cdata`}
                          </Text>
                          {admsInfo?.note && (
                            <div style={{ marginTop: 8, fontSize: 11, color: '#8c8c8c' }}>
                              {admsInfo.note}
                            </div>
                          )}
                        </span>
                      }
                    />
                  ) : (
                    <List
                      dataSource={pendingDevices}
                      renderItem={dev => (
                        <List.Item
                          key={dev.sn}
                          style={{
                            background: '#fafafa',
                            borderRadius: 8,
                            marginBottom: 8,
                            padding: '12px 16px',
                            border: '1px solid #f0f0f0',
                          }}
                          actions={[
                            <Popconfirm
                              key="reject"
                              title="Reject this device?"
                              description="It will be blocked from sending attendance data."
                              onConfirm={() => handleRejectDevice(dev.sn)}
                              okText="Reject"
                              okButtonProps={{ danger: true }}
                            >
                              <Button danger size="small" icon={<StopOutlined />}>Reject</Button>
                            </Popconfirm>,
                            <Button
                              key="approve"
                              type="primary"
                              size="small"
                              icon={<CheckOutlined />}
                              loading={approvingSnSet.has(dev.sn)}
                              onClick={() => {
                                setApprovingSn(dev.sn);
                                approveForm.setFieldsValue({
                                  name: dev.alias || dev.device_name || `ZKTeco-${dev.sn}`,
                                  connection_mode: dev.connection_mode || 'adms',
                                  auto_poll: false,
                                  reader_purpose: 'ATTENDANCE',
                                });
                              }}
                            >
                              Approve
                            </Button>,
                          ]}
                        >
                          <List.Item.Meta
                            avatar={
                              <div style={{
                                width: 40, height: 40, borderRadius: 8,
                                background: 'linear-gradient(135deg,#4f8ef7,#1d5ed8)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                              }}>
                                <DesktopOutlined style={{ color: 'white', fontSize: 18 }} />
                              </div>
                            }
                            title={
                              <Space size={4}>
                                <Text strong>{dev.alias}</Text>
                                <Tag color="orange" style={{ fontSize: 10 }}>Pending</Tag>
                                <Tag color="blue" style={{ fontSize: 10 }}>ADMS</Tag>
                              </Space>
                            }
                            description={
                              <Row gutter={[16, 2]} style={{ fontSize: 12 }}>
                                <Col span={12}>
                                  <Text type="secondary">IP (auto-detected): </Text>
                                  <Text code style={{ fontSize: 11 }}>{dev.ip_address || '—'}</Text>
                                </Col>
                                <Col span={12}>
                                  <Text type="secondary">Serial: </Text>
                                  <Text code style={{ fontSize: 11 }}>{dev.sn}</Text>
                                </Col>
                                <Col span={12}>
                                  <Text type="secondary">Firmware: </Text>
                                  <Text style={{ fontSize: 11 }}>{dev.firmware || '—'}</Text>
                                </Col>
                                <Col span={12}>
                                  <Text type="secondary">Last seen: </Text>
                                  <Text style={{ fontSize: 11 }}>
                                    {dev.last_seen ? new Date(dev.last_seen).toLocaleString() : '—'}
                                  </Text>
                                </Col>
                                {dev.user_count > 0 && (
                                  <Col span={12}>
                                    <Text type="secondary">Users on device: </Text>
                                    <Text style={{ fontSize: 11 }}>{dev.user_count}</Text>
                                  </Col>
                                )}
                              </Row>
                            }
                          />
                        </List.Item>
                      )}
                    />
                  )}

                  {/* Approve confirmation inline form */}
                  {approvingSn && (
                    <Card
                      size="small"
                      title={`Approve ${approvingSn}`}
                      style={{ marginTop: 12, border: '1px solid #4f8ef7' }}
                      extra={<Button size="small" onClick={() => setApprovingSn(null)}>Cancel</Button>}
                    >
                      <Form form={approveForm} layout="inline" size="small">
                        <Form.Item name="name" label="Name" rules={[{ required: true }]}>
                          <Input style={{ width: 160 }} placeholder="Friendly name" />
                        </Form.Item>
                        <Form.Item name="connection_mode" label="Mode">
                          <Select style={{ width: 100 }}>
                            <Option value="adms">ADMS</Option>
                            <Option value="direct">Direct</Option>
                            <Option value="both">Both</Option>
                          </Select>
                        </Form.Item>
                        <Form.Item name="reader_purpose" label="Purpose">
                          <Select style={{ width: 130 }}>
                            <Option value="ATTENDANCE">Attendance</Option>
                            <Option value="ACCESS_ENTRY">Entry</Option>
                            <Option value="ACCESS_EXIT">Exit</Option>
                            <Option value="MUSTERING">Mustering</Option>
                            <Option value="TRANSPORT_CHECKIN">Transport check-in</Option>
                          </Select>
                        </Form.Item>
                      </Form>
                      <div style={{ marginTop: 8, textAlign: 'right' }}>
                        <Button
                          type="primary"
                          size="small"
                          icon={<CheckOutlined />}
                          loading={approvingSnSet.has(approvingSn)}
                          onClick={() => handleApproveDevice(approvingSn)}
                        >
                          Confirm Approval
                        </Button>
                      </div>
                    </Card>
                  )}
                </div>
              ),
            },
            {
              key: 'scan',
              label: (
                <span>
                  <GlobalOutlined style={{ marginRight: 6 }} />
                  Scan Network
                </span>
              ),
              children: (
                <div>
                  <Alert
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                    message="Automatic ZKLib device discovery"
                    description={
                      'Scans every network the server is currently connected to for ZKTeco ' +
                      'readers on port 4370. The subnet is detected automatically from the ' +
                      'server\'s network interfaces — moving to a new network is picked up ' +
                      'immediately. Set DEVICE_SCAN_SUBNETS env var for additional IP ranges.'
                    }
                  />

                  {/* Detected subnets — shown before scanning so admin knows what will be scanned */}
                  {detectedSubnets && (
                    <>
                      {detectedSubnets.warning && (
                        <Alert
                          type="warning"
                          showIcon
                          style={{ marginBottom: 12 }}
                          message="Docker bridge mode — LAN not visible"
                          description={detectedSubnets.warning}
                        />
                      )}
                      <div style={{ marginBottom: 16, padding: '8px 12px', background: '#f6ffed', borderRadius: 6, border: '1px solid #b7eb8f' }}>
                        <div style={{ fontSize: 12, marginBottom: 4 }}>
                          <strong>Server IP(s): </strong>
                          {detectedSubnets.local_ips?.length > 0
                            ? detectedSubnets.local_ips.map(ip => (
                                <Tag key={ip} color="blue" style={{ fontSize: 11 }}>{ip}</Tag>
                              ))
                            : <Text type="secondary">not detected</Text>
                          }
                        </div>
                        <div style={{ fontSize: 12 }}>
                          <strong>Will scan: </strong>
                          {detectedSubnets.subnets?.length > 0
                            ? detectedSubnets.subnets.map(s => (
                                <Tag key={s} color="green" style={{ fontSize: 11, marginBottom: 2 }}>{s}</Tag>
                              ))
                            : <Text type="warning">No subnets detected — set DEVICE_SCAN_SUBNETS env var</Text>
                          }
                        </div>
                        {detectedSubnets.note && (
                          <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 4 }}>{detectedSubnets.note}</div>
                        )}
                      </div>
                    </>
                  )}

                  <div style={{ textAlign: 'center', marginBottom: 20 }}>
                    <Button
                      type="primary"
                      size="large"
                      icon={<ScanOutlined />}
                      loading={scanStatus?.running || scanPolling}
                      onClick={startNetworkScan}
                      disabled={scanStatus?.running}
                      style={{ minWidth: 180 }}
                    >
                      {scanStatus?.running ? 'Scanning…' : 'Scan Now'}
                    </Button>
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        Background scan also runs automatically every 60 seconds
                      </Text>
                    </div>
                  </div>

                  {scanStatus && (
                    <>
                      {scanStatus.running && (
                        <Progress
                          percent={scanStatus.progress_pct || 0}
                          status="active"
                          style={{ marginBottom: 12 }}
                          format={p => `${p}% — ${scanStatus.probed}/${scanStatus.total_ips} IPs`}
                        />
                      )}

                      {scanStatus.subnets_scanned?.length > 0 && (
                        <div style={{ marginBottom: 12 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>Subnets: </Text>
                          {scanStatus.subnets_scanned.map(s => (
                            <Tag key={s} style={{ fontSize: 11 }}>{s}</Tag>
                          ))}
                        </div>
                      )}

                      {scanStatus.error && (
                        <Alert type="warning" showIcon message={scanStatus.error} style={{ marginBottom: 12 }} />
                      )}

                      {!scanStatus.running && scanStatus.finished_at && (
                        <Alert
                          type={scanStatus.found_count > 0 ? 'success' : 'info'}
                          showIcon
                          style={{ marginBottom: 12 }}
                          message={
                            scanStatus.found_count > 0
                              ? `Found ${scanStatus.found_count} device${scanStatus.found_count > 1 ? 's' : ''}`
                              : 'Scan complete — no new devices found'
                          }
                          description={`Scanned ${scanStatus.probed} IPs • Finished ${new Date(scanStatus.finished_at).toLocaleTimeString()}`}
                        />
                      )}

                      {scanStatus.found?.length > 0 && (
                        <div>
                          <Text strong style={{ display: 'block', marginBottom: 8 }}>
                            Detected Devices — click Register to add a device without typing the IP
                          </Text>
                          {scanStatus.found.map(item => (
                            <Card
                              key={item.ip}
                              size="small"
                              style={{
                                marginBottom: 10,
                                border: configuringSn === item.sn
                                  ? '1.5px solid #4f8ef7'
                                  : '1px solid #f0f0f0',
                                borderRadius: 8,
                              }}
                              bodyStyle={{ padding: '10px 14px' }}
                            >
                              {/* Device header row */}
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                <Space size={8}>
                                  <div style={{
                                    width: 32, height: 32, borderRadius: 6, flexShrink: 0,
                                    background: 'linear-gradient(135deg,#52c41a,#389e0d)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                  }}>
                                    <DesktopOutlined style={{ color: 'white', fontSize: 15 }} />
                                  </div>
                                  <div>
                                    <Space size={4}>
                                      <Text code style={{ fontSize: 13 }}>{item.ip}</Text>
                                      <Tag color="green" style={{ fontSize: 10 }}>ZKLib</Tag>
                                      {item.already_known
                                        ? <Tag color="blue" style={{ fontSize: 10 }}>Known</Tag>
                                        : <Tag color="orange" style={{ fontSize: 10 }}>New</Tag>}
                                    </Space>
                                    <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2 }}>
                                      SN: <Text code style={{ fontSize: 11 }}>{item.sn}</Text>
                                    </div>
                                  </div>
                                </Space>

                                {configuringSn === item.sn ? (
                                  <Button size="small" onClick={() => { setConfiguringSn(null); configureFoundForm.resetFields(); }}>
                                    Cancel
                                  </Button>
                                ) : (
                                  <Button
                                    type="primary"
                                    size="small"
                                    icon={<EditOutlined />}
                                    onClick={() => {
                                      setConfiguringSn(item.sn);
                                      configureFoundForm.setFieldsValue({
                                        name:             `ZKTeco-${item.ip}`,
                                        reader_purpose:   'ATTENDANCE',
                                        connection_mode:  'direct',
                                        auto_poll:        true,
                                        poll_interval_sec: 300,
                                        zone_id:          null,
                                        comm_key:         '0',
                                      });
                                    }}
                                  >
                                    Register
                                  </Button>
                                )}
                              </div>

                              {/* Inline configure form — visible when this device is selected */}
                              {configuringSn === item.sn && (
                                <div style={{ marginTop: 12, borderTop: '1px solid #f0f0f0', paddingTop: 12 }}>
                                  <Form
                                    form={configureFoundForm}
                                    layout="vertical"
                                    size="small"
                                  >
                                    <Row gutter={10}>
                                      <Col span={14}>
                                        <Form.Item
                                          name="name"
                                          label="Friendly Name"
                                          rules={[{ required: true, message: 'Name is required' }]}
                                          style={{ marginBottom: 10 }}
                                        >
                                          <Input placeholder="e.g. Main Gate Entry" />
                                        </Form.Item>
                                      </Col>
                                      <Col span={10}>
                                        <Form.Item name="reader_purpose" label="Reader Purpose" style={{ marginBottom: 10 }}>
                                          <Select>
                                            <Option value="ATTENDANCE">Attendance (T&A)</Option>
                                            <Option value="ACCESS_ENTRY">Entry Reader</Option>
                                            <Option value="ACCESS_EXIT">Exit Reader</Option>
                                            <Option value="MUSTERING">Mustering Point</Option>
                                            <Option value="TRANSPORT_CHECKIN">Transport check-in</Option>
                                          </Select>
                                        </Form.Item>
                                      </Col>
                                      <Col span={8}>
                                        <Form.Item name="connection_mode" label="Mode" style={{ marginBottom: 10 }}>
                                          <Select>
                                            <Option value="direct">Direct (ZKLib)</Option>
                                            <Option value="adms">ADMS (Push)</Option>
                                            <Option value="both">Both</Option>
                                          </Select>
                                        </Form.Item>
                                      </Col>
                                      <Col span={8}>
                                        <Form.Item name="poll_interval_sec" label="Poll every (s)" style={{ marginBottom: 10 }}>
                                          <InputNumber min={60} max={3600} style={{ width: '100%' }} />
                                        </Form.Item>
                                      </Col>
                                      <Col span={8}>
                                        <Form.Item name="comm_key" label="Comm Key" style={{ marginBottom: 10 }}>
                                          <Input placeholder="0" />
                                        </Form.Item>
                                      </Col>
                                      {zones.length > 0 && (
                                        <Col span={24}>
                                          <Form.Item name="zone_id" label="Zone (optional)" style={{ marginBottom: 10 }}>
                                            <Select allowClear placeholder="Assign to a zone">
                                              {zones.map(z => (
                                                <Option key={z.id} value={z.id}>{z.name}</Option>
                                              ))}
                                            </Select>
                                          </Form.Item>
                                        </Col>
                                      )}
                                    </Row>
                                    <div style={{ textAlign: 'right' }}>
                                      <Button
                                        type="primary"
                                        icon={<CheckOutlined />}
                                        loading={configuringSnSaving}
                                        onClick={() => handleSaveFoundDevice(item)}
                                      >
                                        Save & Add to Device List
                                      </Button>
                                    </div>
                                  </Form>
                                </div>
                              )}
                            </Card>
                          ))}
                        </div>
                      )}
                    </>
                  )}

                  {!scanStatus && (
                    <div style={{ textAlign: 'center', padding: '24px 0', color: '#bfbfbf' }}>
                      <ScanOutlined style={{ fontSize: 32, marginBottom: 8 }} />
                      <div>Click "Scan Now" to discover ZKTeco readers on your network</div>
                    </div>
                  )}
                </div>
              ),
            },
          ]}
        />
      </Modal>

      {/* ── Discover by IP Modal ─────────────────────────────────────── */}
      <Modal
        title={<span><RadarChartOutlined /> Discover &amp; Register Device by IP</span>}
        open={discoverVisible}
        onCancel={() => { setDiscoverVisible(false); setDiscoverResult(null); }}
        footer={null}
        width={620}
      >
        {/* Step 1 — Ping */}
        <Card size="small" title="Step 1 — Enter device IP and test connection" style={{ marginBottom: 16 }}>
          <Row gutter={8} align="middle">
            <Col span={9}>
              <Input
                placeholder="192.168.1.52"
                value={discoverIp}
                onChange={e => setDiscoverIp(e.target.value)}
                onPressEnter={handleDiscover}
                addonBefore="IP"
              />
            </Col>
            <Col span={5}>
              <Input
                type="number"
                placeholder="4370"
                value={discoverPort}
                onChange={e => setDiscoverPort(Number(e.target.value))}
                addonBefore="Port"
              />
            </Col>
            <Col span={5}>
              <Input
                type="number"
                placeholder="0"
                value={discoverCommKey}
                onChange={e => setDiscoverCommKey(Number(e.target.value))}
                addonBefore="Key"
              />
            </Col>
            <Col span={5}>
              <Button
                type="primary"
                icon={<WifiOutlined />}
                loading={discoverLoading}
                onClick={handleDiscover}
                block
              >
                Ping
              </Button>
            </Col>
          </Row>

          {discoverResult && (
            <Alert
              style={{ marginTop: 12 }}
              type={discoverResult.connected ? 'success' : 'warning'}
              icon={discoverResult.connected ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
              showIcon
              message={discoverResult.connected ? 'Device found via ZKLib!' : 'ZKLib port 4370 unreachable'}
              description={
                discoverResult.connected ? (
                  <div style={{ marginTop: 4 }}>
                    <Row gutter={8}>
                      <Col span={12}><Text type="secondary">Model:</Text> <strong>{discoverResult.device_name || '—'}</strong></Col>
                      <Col span={12}><Text type="secondary">Serial:</Text> <strong>{discoverResult.serial_number || '—'}</strong></Col>
                      <Col span={12}><Text type="secondary">Firmware:</Text> {discoverResult.firmware || '—'}</Col>
                      <Col span={12}><Text type="secondary">MAC:</Text> {discoverResult.mac || '—'}</Col>
                      <Col span={12}><Text type="secondary">Users:</Text> {discoverResult.user_count ?? '—'}</Col>
                      <Col span={12}><Text type="secondary">Log entries:</Text> {discoverResult.log_count ?? '—'}</Col>
                    </Row>
                  </div>
                ) : (
                  <div>
                    <div style={{ marginBottom: 8 }}>{discoverResult.error}</div>
                    <div style={{ fontSize: 12, color: '#595959' }}>
                      The device may be configured as <strong>ADMS push-mode</strong> (port 4370 blocked).
                      You can still register it — it will appear ONLINE automatically when it connects to the server.
                    </div>
                  </div>
                )
              }
            />
          )}
        </Card>

        {/* Step 2 — Register after successful ZKLib ping */}
        {discoverResult?.connected && (
          <Card size="small" title="Step 2 — Register the device">
            <Form form={registerForm} layout="vertical">
              <Row gutter={12}>
                <Col span={16}>
                  <Form.Item name="name" label="Device name" rules={[{ required: true }]}>
                    <Input placeholder="F18 - Gate A" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="zone_id" label="Zone ID">
                    <InputNumber placeholder="1" style={{ width: '100%' }} min={1} precision={0} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="location_description" label="Location">
                    <Input placeholder="Main entry gate" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="connection_mode" label="Connection mode">
                    <Select>
                      <Select.Option value="direct">Direct only (no ADMS) — e.g. F18</Select.Option>
                      <Select.Option value="adms">ADMS only — e.g. Huros H1</Select.Option>
                      <Select.Option value="both">Both (ADMS + polling backup)</Select.Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item name="auto_poll" label="Auto-poll" valuePropName="checked">
                    <Switch checkedChildren="On" unCheckedChildren="Off" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="poll_interval_sec" label="Poll every (seconds)">
                    <Input type="number" min={60} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="ip_address" hidden><Input /></Form.Item>
                  <Form.Item name="port" hidden><Input /></Form.Item>
                  <Form.Item name="device_password" hidden><Input /></Form.Item>
                </Col>
              </Row>
              <Button type="primary" icon={<CheckCircleOutlined />} loading={registerLoading}
                onClick={handleRegisterDirect} block>
                Register Device
              </Button>
            </Form>
          </Card>
        )}

        {/* Step 2 fallback — Register as ADMS when ZKLib port 4370 is unreachable */}
        {discoverResult && !discoverResult.connected && discoverIp && (
          <Card size="small"
            title={<Space><InfoCircleOutlined style={{ color: '#fa8c16' }} />Register as ADMS Device</Space>}
            style={{ borderColor: '#fa8c16' }}>
            <Form
              layout="vertical"
              onFinish={async (vals) => {
                setRegisterLoading(true);
                try {
                  await deviceAPI.zkRegisterDevice({
                    ...vals,
                    ip_address: discoverIp,
                    port: discoverPort,
                    device_password: discoverCommKey,
                    connection_mode: 'adms',
                    auto_poll: false,
                    poll_interval_sec: 300,
                    skip_connection_test: true,
                  });
                  message.success(`${vals.name} registered as ADMS device — it will show Online when it connects to the server`);
                  setDiscoverVisible(false);
                  setDiscoverResult(null);
                  setDiscoverIp('');
                  fetchDevices();
                } catch (e) {
                  message.error(e.message || 'Registration failed');
                } finally {
                  setRegisterLoading(false);
                }
              }}
            >
              <Row gutter={12}>
                <Col span={16}>
                  <Form.Item name="name" label="Device name" rules={[{ required: true }]}
                    initialValue={`ZKTeco ${discoverIp}`}>
                    <Input placeholder={`ZKTeco ${discoverIp}`} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="location_description" label="Location">
                    <Input placeholder="e.g. Gate B" />
                  </Form.Item>
                </Col>
              </Row>
              <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 12 }}>
                The device will be registered at <strong>{discoverIp}</strong> in ADMS push-mode.
                Configure the device's server address to point to this system — it will appear
                <strong> Online</strong> automatically when it connects.
              </div>
              <Button type="primary" htmlType="submit" loading={registerLoading}
                icon={<PlusOutlined />} block>
                Register as ADMS Device
              </Button>
            </Form>
          </Card>
        )}
      </Modal>

      {/* Import CSV Modal */}
      <Modal
        title="Import Devices from CSV"
        open={importModalVisible}
        onOk={handleImportCSV}
        onCancel={() => setImportModalVisible(false)}
      >
        <div style={{ marginBottom: 16 }}>
          <p>CSV Format: SN,Alias,IP,Area,CommKey</p>
          <p>Example: ABC123456,Terminal 1,192.168.1.100,1,0</p>
        </div>

        <Upload
          fileList={fileList}
          beforeUpload={() => false}
          onChange={({ fileList }) => setFileList(fileList)}
          accept=".csv"
        >
          <Button icon={<UploadOutlined />}>Select CSV File</Button>
        </Upload>
      </Modal>

      {/* ── Device Details Drawer ─────────────────────────────────────────── */}
      <Drawer
        title={viewDevice ? (viewDevice.alias || viewDevice.sn) : 'Device Details'}
        width={480}
        open={detailDrawerOpen}
        onClose={() => setDetailDrawerOpen(false)}
        extra={
          viewDevice && (
            <Space>
              <Button
                size="small"
                icon={<EditOutlined />}
                onClick={() => { setDetailDrawerOpen(false); handleEditDevice(viewDevice); }}
              >
                Edit
              </Button>
            </Space>
          )
        }
      >
        {viewDevice && (
          <div>
            {/* Status banner */}
            <Alert
              message={viewDevice.status?.toLowerCase() === 'online' ? 'Device Online' : 'Device Offline'}
              type={viewDevice.status?.toLowerCase() === 'online' ? 'success' : 'error'}
              showIcon
              style={{ marginBottom: 20 }}
            />

            <Divider orientation="left">Identity</Divider>
            <Row gutter={[0, 12]}>
              <Col span={10}><Text type="secondary">Serial Number</Text></Col>
              <Col span={14}><Text strong>{viewDevice.sn}</Text></Col>

              <Col span={10}><Text type="secondary">Name / Alias</Text></Col>
              <Col span={14}><Text>{viewDevice.alias || '—'}</Text></Col>

              <Col span={10}><Text type="secondary">Device Name</Text></Col>
              <Col span={14}><Text>{viewDevice.device_name || '—'}</Text></Col>

              <Col span={10}><Text type="secondary">Model</Text></Col>
              <Col span={14}><Text>{viewDevice.device_model || '—'}</Text></Col>

              <Col span={10}><Text type="secondary">Firmware</Text></Col>
              <Col span={14}><Text code>{viewDevice.fw_version || '—'}</Text></Col>

              <Col span={10}><Text type="secondary">Platform</Text></Col>
              <Col span={14}><Text>{viewDevice.platform || '—'}</Text></Col>

              <Col span={10}><Text type="secondary">OEM Vendor</Text></Col>
              <Col span={14}><Text>{viewDevice.oem_vendor || '—'}</Text></Col>

              <Col span={10}><Text type="secondary">Purpose</Text></Col>
              <Col span={14}>
                <Tag color={getReaderPurposeColor(viewDevice.reader_purpose)}>
                  {getReaderPurposeName(viewDevice.reader_purpose)}
                </Tag>
              </Col>
            </Row>

            <Divider orientation="left">Network</Divider>
            <Row gutter={[0, 12]}>
              <Col span={10}><Text type="secondary">IP Address</Text></Col>
              <Col span={14}><Text code>{viewDevice.ip_address || '—'}</Text></Col>

              <Col span={10}><Text type="secondary">Connection Mode</Text></Col>
              <Col span={14}>
                {(() => {
                  const m = CONNECTION_MODE_META[viewDevice.connection_mode] || CONNECTION_MODE_META.adms;
                  return <Tooltip title={m.description}><Tag color={m.color}>{m.label}</Tag></Tooltip>;
                })()}
              </Col>

              <Col span={10}><Text type="secondary">MAC Address</Text></Col>
              <Col span={14}><Text code>{viewDevice.mac_address || '—'}</Text></Col>

              <Col span={10}><Text type="secondary">Comm Key</Text></Col>
              <Col span={14}><Text code>{viewDevice.comm_key ?? '—'}</Text></Col>
            </Row>

            <Divider orientation="left">Capacity</Divider>
            <Row gutter={16}>
              <Col span={6}>
                <Statistic title="Users" value={viewDevice.user_count ?? 0} />
              </Col>
              <Col span={6}>
                <Statistic title="Fingerprints" value={viewDevice.fp_count ?? 0} />
              </Col>
              <Col span={6}>
                <Statistic title="Faces" value={viewDevice.face_count ?? 0} />
              </Col>
              <Col span={6}>
                <Statistic title="Logs" value={viewDevice.log_count ?? 0} />
              </Col>
            </Row>

            <Divider orientation="left">Activity</Divider>
            <Row gutter={[0, 12]}>
              <Col span={10}><Text type="secondary">Last Active</Text></Col>
              <Col span={14}>
                {viewDevice.last_activity ? (
                  <Space direction="vertical" size={0}>
                    <Text>{new Date(viewDevice.last_activity).toLocaleString()}</Text>
                    <Tag color={getActivityColor(viewDevice.last_activity)}>
                      {getRelativeTime(viewDevice.last_activity)}
                    </Tag>
                  </Space>
                ) : <Text type="secondary">Never</Text>}
              </Col>

              <Col span={10}><Text type="secondary">Registered</Text></Col>
              <Col span={14}><Text>{new Date(viewDevice.created_at).toLocaleString()}</Text></Col>

              <Col span={10}><Text type="secondary">Last Updated</Text></Col>
              <Col span={14}><Text>{new Date(viewDevice.updated_at).toLocaleString()}</Text></Col>
            </Row>

            {viewDevice.ip_address && (
              <>
                <Divider orientation="left">Device Clock</Divider>
                {deviceTimes[viewDevice.sn] ? (
                  <Row gutter={[0, 10]} style={{ marginBottom: 14 }}>
                    <Col span={10}><Text type="secondary">Device Time</Text></Col>
                    <Col span={14}>
                      <Text code style={{ fontSize: 12 }}>
                        {deviceTimes[viewDevice.sn].device_time}
                      </Text>
                    </Col>
                    <Col span={10}><Text type="secondary">Server Time</Text></Col>
                    <Col span={14}>
                      <Text code style={{ fontSize: 12 }}>
                        {deviceTimes[viewDevice.sn].server_time
                          ? new Date(deviceTimes[viewDevice.sn].server_time + 'Z').toLocaleString()
                          : '—'}
                      </Text>
                    </Col>
                  </Row>
                ) : (
                  <Text type="secondary" style={{ display: 'block', marginBottom: 14 }}>
                    Click "Read Clock" to check the device time.
                  </Text>
                )}
                <Space>
                  <Button
                    size="small"
                    icon={<ClockCircleOutlined />}
                    loading={timeSyncLoading[viewDevice.sn] === 'reading'}
                    onClick={() => fetchDeviceTime(viewDevice.sn, viewDevice.ip_address, viewDevice.port || 4370)}
                  >
                    Read Clock
                  </Button>
                  <Button
                    size="small"
                    type="primary"
                    icon={<SyncOutlined />}
                    loading={timeSyncLoading[viewDevice.sn] === 'syncing'}
                    onClick={() => handleSyncTime(viewDevice.sn, viewDevice.ip_address, viewDevice.port || 4370, viewDevice.connection_mode)}
                  >
                    Sync to Server Time
                  </Button>
                </Space>
              </>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
};

export default DeviceList;
