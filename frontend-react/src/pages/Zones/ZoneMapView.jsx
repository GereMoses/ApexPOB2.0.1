import { useState, useEffect, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, useMapEvents, ZoomControl } from 'react-leaflet';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import apiService from '../../services/api';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Input, Space, Empty, Tooltip, App } from 'antd';
import {
  SearchOutlined, EnvironmentOutlined, ApiOutlined,
  FullscreenOutlined, FullscreenExitOutlined,
  TeamOutlined, GlobalOutlined, CheckCircleOutlined,
  AlertOutlined, SafetyOutlined, ReloadOutlined,
} from '@ant-design/icons';

/* ── Tile Layers ──────────────────────────────────────────────────────────── */
const TILE_LAYERS = {
  street: {
    label: 'Street',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  light: {
    label: 'Light',
    // CARTO basemaps now need an API key (every tile read "API KEY REQUIRED") — Esri
    // grey canvas is free and keyless; it stops at zoom 16, so deeper zooms stretch 16.
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: '© <a href="https://www.esri.com/">Esri</a>', maxNativeZoom: 16,
  },
  dark: {
    label: 'Dark',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: '© <a href="https://www.esri.com/">Esri</a>', maxNativeZoom: 16,
  },
  satellite: {
    label: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '© <a href="https://www.esri.com/">Esri</a>',
  },
};

/* ── Zone type colour map (matches ZoneManagement.jsx) ───────────────────── */
const ZONE_COLOR = {
  LOCATION:     '#10B981', MUSTER_POINT: '#10B981', WORK_AREA:    '#EF4444',
  OUTSIDE:      '#6B7280', TRANSIT:      '#0EA5E9', RESTRICTED:   '#7C3AED',
  PUBLIC:       '#10B981', SAFE_HAVEN:   '#0078D4', ACCOMMODATION:'#8B5CF6',
  HELIPAD:      '#0078D4', CONTROL_ROOM: '#F59E0B', STORAGE:      '#92400E',
  EMERGENCY:    '#EF4444',
};

const ZONE_TYPE_LABELS = {
  LOCATION: 'Location', MUSTER_POINT: 'Muster Point', WORK_AREA: 'Work Area',
  OUTSIDE: 'Outside Area', TRANSIT: 'In Transit', RESTRICTED: 'Restricted',
  PUBLIC: 'Public', SAFE_HAVEN: 'Safe Haven', ACCOMMODATION: 'Accommodation',
  HELIPAD: 'Helipad', CONTROL_ROOM: 'Control Room', STORAGE: 'Storage',
  EMERGENCY: 'Emergency',
};

const STATUS_PULSE  = new Set(['ACTIVE', 'EMERGENCY', 'LOCKDOWN', 'MAINTENANCE']);
const HAZARD_COLOR  = { LOW: '#10B981', MEDIUM: '#F59E0B', HIGH: '#EF4444', CRITICAL: '#991B1B' };

const zoneColor = (z) => z.display_color || ZONE_COLOR[z.zone_type] || '#0078D4';

/* ── Custom marker icon ───────────────────────────────────────────────────── */
const markerIcon = (zone, isSelected, tileKey) => {
  const count  = zone.current_personnel_count ?? 0;
  const color  = zoneColor(zone);
  const size   = isSelected ? 52 : 40;
  const fs     = isSelected ? 16 : count >= 100 ? 11 : 14;
  const pulse  = STATUS_PULSE.has(zone.status);
  const isDark = tileKey === 'dark' || tileKey === 'satellite';
  const ring   = isSelected
    ? `0 0 0 3px ${color}88, 0 4px 20px rgba(0,0,0,0.55)`
    : `0 2px 10px rgba(0,0,0,0.4)`;

  const pulseHtml = pulse && !isSelected ? `
    <div style="
      position:absolute; top:50%; left:50%;
      width:${size + 14}px; height:${size + 14}px;
      margin-left:-${(size + 14) / 2}px; margin-top:-${(size + 14) / 2}px;
      border-radius:50%;
      border:2px solid ${color};
      opacity:0.5;
      animation:mapPulse 2s infinite;
      pointer-events:none;
    "></div>` : '';

  const label = zone.name.length > 20 ? zone.name.slice(0, 18) + '…' : zone.name;

  return L.divIcon({
    html: `
      <div style="text-align:center; cursor:pointer; position:relative;">
        ${pulseHtml}
        <div style="
          width:${size}px; height:${size}px;
          background: linear-gradient(135deg, ${color}dd, ${color});
          border-radius:50%;
          border: ${isSelected ? '3px' : '2px'} solid ${isDark ? 'rgba(255,255,255,0.9)' : 'white'};
          box-shadow: ${ring};
          display:flex; align-items:center; justify-content:center;
          margin:0 auto; position:relative; z-index:1;
          transition: all 0.2s;
        ">
          <span style="
            color:#fff; font-weight:900;
            font-size:${fs}px; line-height:1;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            text-shadow: 0 1px 3px rgba(0,0,0,0.4);
          ">${count}</span>
        </div>
        <div style="
          background: ${isDark ? 'rgba(15,20,35,0.9)' : 'rgba(15,20,35,0.82)'};
          color: #fff;
          font-size: ${isSelected ? 10 : 9}px;
          font-weight: 700;
          padding: 2px 6px;
          border-radius: 3px;
          margin-top: 4px;
          white-space: nowrap;
          display: inline-block;
          max-width: 140px;
          overflow: hidden;
          text-overflow: ellipsis;
          border-bottom: 2px solid ${color};
          letter-spacing: 0.02em;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        ">${label}</div>
      </div>`,
    className: '',
    iconSize:   [isSelected ? 150 : 120, isSelected ? 78 : 62],
    iconAnchor: [isSelected ? 75 : 60, isSelected ? 26 : 20],
    popupAnchor:[0, -32],
  });
};

/* ── Map controller (fly / fit) ───────────────────────────────────────────── */
const MapController = ({ zone, allZones }) => {
  const map = useMap();

  // The map mounts with `forceRender` inside an antd Tab pane that starts
  // hidden (display:none). Leaflet measures a 0×0 container at mount time
  // and has no way to know later when the pane becomes visible — a plain
  // window resize never fires in that case, so tiles/markers stayed blank
  // forever even after clicking into the tab. A ResizeObserver on the map's
  // own container catches the display:none → visible transition and forces
  // Leaflet to recompute its size, which is what actually makes it render.
  useEffect(() => {
    const container = map.getContainer();
    if (!container || typeof ResizeObserver === 'undefined') return;
    let lastHadSize = false;
    const ro = new ResizeObserver(() => {
      const { width, height } = container.getBoundingClientRect();
      const hasSize = width > 0 && height > 0;
      if (hasSize && !lastHadSize) map.invalidateSize();
      lastHadSize = hasSize;
    });
    ro.observe(container);
    return () => ro.disconnect();
  }, [map]);

  useEffect(() => {
    const size = map.getSize();
    const go = () => {
      try {
        if (zone?.latitude && zone?.longitude) {
          const lat = parseFloat(zone.latitude);
          const lng = parseFloat(zone.longitude);
          if (!isNaN(lat) && !isNaN(lng)) map.flyTo([lat, lng], 13, { duration: 1, easeLinearity: 0.4 });
        } else if (!zone && allZones.length > 0) {
          const coords = allZones
            .filter(z => z.latitude && z.longitude)
            .map(z => [parseFloat(z.latitude), parseFloat(z.longitude)])
            .filter(([a, b]) => !isNaN(a) && !isNaN(b));
          // Zones on one installation are metres apart: one zone → street level; several
          // → fit them all (capped at street level so a cluster doesn't zoom to rooftops).
          if (coords.length === 1) map.setView(coords[0], 16, { animate: false });
          else if (coords.length) map.fitBounds(coords, { padding: [50, 50], maxZoom: 17, animate: false });
        }
      } catch (_) {}
    };
    if (size && size.x > 0) go();
    else { map.once('resize', go); return () => map.off('resize', go); }
    // Re-fit when the zones (or their coordinates) arrive — they load after the map
    // mounts, so fitting only on mount left the default country-wide view.
  }, [zone, map, allZones.map(z => `${z.latitude},${z.longitude}`).join('|')]); // eslint-disable-line

  return null;
};

/* ── People list (who is in a zone right now) ─────────────────────────────── */
const fmtSince = (iso) => {
  if (!iso) return '';
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  return h < 24 ? `${h}h ${mins % 60}m` : `${Math.floor(h / 24)}d ${h % 24}h`;
};

const PeopleList = ({ people, dark, highlight, limit }) => {
  const list = limit ? people.slice(0, limit) : people;
  const q = (highlight || '').toLowerCase();
  if (!people.length) {
    return <div style={{ fontSize: 11, color: dark ? '#475569' : '#9CA3AF', padding: '4px 0' }}>Nobody here right now</div>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {list.map(p => {
        const hit = q && (p.name.toLowerCase().includes(q) || p.emp_code.toLowerCase().includes(q));
        return (
          <div key={p.emp_code} style={{
            display: 'flex', justifyContent: 'space-between', gap: 6, fontSize: 11,
            padding: '3px 6px', borderRadius: 5,
            background: hit ? (dark ? 'rgba(250,204,21,0.18)' : '#FEF9C3') : 'transparent',
          }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ color: dark ? '#E2E8F0' : '#111827', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.name}</div>
              <div style={{ color: dark ? '#64748B' : '#6B7280', fontSize: 10, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {p.emp_code}{p.department ? ` · ${p.department}` : ''}
              </div>
            </div>
            <div style={{ color: dark ? '#64748B' : '#9CA3AF', fontSize: 10, flexShrink: 0 }}>
              {fmtSince(p.in_zone_since || p.last_seen)}
            </div>
          </div>
        );
      })}
      {limit && people.length > limit && (
        <div style={{ fontSize: 10.5, color: dark ? '#64748B' : '#6B7280', paddingLeft: 6 }}>+{people.length - limit} more — select the zone for the full list</div>
      )}
    </div>
  );
};

/* ── Map click → place a zone ─────────────────────────────────────────────── */
const PlaceOnClick = ({ active, onPlace }) => {
  useMapEvents({ click: (e) => { if (active) onPlace(e.latlng); } });
  return null;
};

/* ── Rich popup ───────────────────────────────────────────────────────────── */
const ZonePopup = ({ zone }) => {
  const color = zoneColor(zone);
  const count = zone.current_personnel_count ?? 0;
  const pct   = zone.max_capacity ? Math.min(100, Math.round((count / zone.max_capacity) * 100)) : null;
  const capC  = pct >= 90 ? '#EF4444' : pct >= 70 ? '#F59E0B' : '#10B981';
  const hc    = HAZARD_COLOR[zone.hazard_level] || '#10B981';
  const mapsUrl = `https://www.openstreetmap.org/?mlat=${zone.latitude}&mlon=${zone.longitude}#map=14/${zone.latitude}/${zone.longitude}`;

  return (
    <div style={{ width: 220, fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" }}>
      {/* Header */}
      <div style={{
        background: `linear-gradient(135deg, ${color}cc, ${color})`,
        margin: '-12px -12px 12px', padding: '12px 14px',
        borderRadius: '8px 8px 0 0',
      }}>
        <div style={{ fontWeight: 800, color: '#fff', fontSize: 14, lineHeight: 1.2 }}>{zone.name}</div>
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.78)', marginTop: 2, fontFamily: 'monospace' }}>
          {zone.code}
        </div>
      </div>

      {/* POB */}
      <div style={{ textAlign: 'center', marginBottom: 10 }}>
        <div style={{ fontSize: 40, fontWeight: 900, color, lineHeight: 1, letterSpacing: -1 }}>{count}</div>
        <div style={{ fontSize: 9.5, fontWeight: 700, color: '#6B7280', letterSpacing: '0.08em', marginTop: 2 }}>
          PERSONNEL ON BOARD
        </div>
      </div>

      {/* Capacity bar */}
      {pct !== null && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, color: '#6B7280', marginBottom: 4 }}>
            <span>Capacity</span>
            <span style={{ fontWeight: 700, color: capC }}>{count}/{zone.max_capacity} ({pct}%)</span>
          </div>
          <div style={{ height: 4, background: '#F3F4F6', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${pct}%`, background: `linear-gradient(90deg,${capC}88,${capC})`, borderRadius: 2 }} />
          </div>
        </div>
      )}

      {/* Meta */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#9CA3AF' }}>Type</span>
          <span style={{ fontWeight: 500, color: '#1F2937' }}>{ZONE_TYPE_LABELS[zone.zone_type] || zone.zone_type}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#9CA3AF' }}>Hazard</span>
          <span style={{ fontWeight: 700, color: hc }}>{zone.hazard_level}</span>
        </div>
        {zone.state && (
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#9CA3AF' }}>State</span>
            <span style={{ fontWeight: 500, color: '#1F2937' }}>{zone.state}</span>
          </div>
        )}
        {zone.reader_count > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#9CA3AF' }}>Readers</span>
            <span style={{ fontWeight: 600, color: '#7C3AED' }}>{zone.reader_count} ADMS</span>
          </div>
        )}
      </div>

      <div style={{ borderTop: '1px solid #F3F4F6', marginTop: 10, paddingTop: 8, maxHeight: 180, overflowY: 'auto' }}>
        <PeopleList people={zone.personnel || []} limit={8} />
      </div>

      <div style={{ borderTop: '1px solid #F3F4F6', marginTop: 10, paddingTop: 8 }}>
        <a href={mapsUrl} target="_blank" rel="noopener noreferrer"
          style={{ fontSize: 11, color: '#0078D4', display: 'flex', alignItems: 'center', gap: 4 }}>
          <EnvironmentOutlined style={{ fontSize: 11 }} />
          {parseFloat(zone.latitude).toFixed(4)}°N, {parseFloat(zone.longitude).toFixed(4)}°E · Open Map ↗
        </a>
      </div>
    </div>
  );
};

/* ── Sidebar zone card ────────────────────────────────────────────────────── */
const SidebarCard = ({ zone, isSelected, onClick }) => {
  const color = zoneColor(zone);
  const count = zone.current_personnel_count ?? 0;
  const hc    = HAZARD_COLOR[zone.hazard_level] || '#10B981';

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '9px 10px', marginBottom: 2, borderRadius: 8,
        background: isSelected ? `${color}18` : 'transparent',
        borderTop:    isSelected ? `1px solid ${color}50` : '1px solid transparent',
        borderRight:  isSelected ? `1px solid ${color}50` : '1px solid transparent',
        borderBottom: isSelected ? `1px solid ${color}50` : '1px solid transparent',
        borderLeft: `3px solid ${color}`,
        cursor: 'pointer', transition: 'all 0.15s',
        boxShadow: isSelected ? `0 2px 10px ${color}28` : 'none',
      }}
      onMouseEnter={e => { if (!isSelected) { e.currentTarget.style.background = `${color}0d`; e.currentTarget.style.borderTopColor = `${color}30`; e.currentTarget.style.borderRightColor = `${color}30`; e.currentTarget.style.borderBottomColor = `${color}30`; } }}
      onMouseLeave={e => { if (!isSelected) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderTopColor = 'transparent'; e.currentTarget.style.borderRightColor = 'transparent'; e.currentTarget.style.borderBottomColor = 'transparent'; } }}
    >
      {/* Avatar */}
      <div style={{
        width: 40, height: 40, borderRadius: 10, flexShrink: 0,
        background: `linear-gradient(135deg, ${color}cc, ${color})`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: isSelected ? `0 0 0 2px white, 0 0 0 4px ${color}55` : 'none',
      }}>
        <span style={{ color: '#fff', fontWeight: 900, fontSize: count >= 100 ? 12 : 15 }}>{count}</span>
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontWeight: isSelected ? 700 : 500, fontSize: 12.5,
          color: isSelected ? '#fff' : '#E2E8F0',
          lineHeight: 1.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>{zone.name}</div>
        <div style={{ fontSize: 10.5, color: '#64748B', marginTop: 3, display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ color: '#64748B', fontFamily: 'monospace' }}>{zone.code}</span>
          {zone.state && <span style={{ color: '#475569' }}>· {zone.state}</span>}
          {!zone.has_gps && !zone.virtual && <span style={{ color: '#F59E0B', fontWeight: 700 }}>· not on map</span>}
        </div>
      </div>

      {/* Hazard dot */}
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: hc, flexShrink: 0 }} />
    </div>
  );
};

/* ── Selected zone info panel (sidebar bottom) ────────────────────────────── */
const SelectedPanel = ({ zone, onClose, onPlace, placing, highlight }) => {
  if (!zone) return null;
  const color = zoneColor(zone);
  const count = zone.current_personnel_count ?? 0;
  const pct   = zone.max_capacity ? Math.min(100, Math.round((count / zone.max_capacity) * 100)) : null;
  const capC  = pct >= 90 ? '#EF4444' : pct >= 70 ? '#F59E0B' : '#10B981';
  const hc    = HAZARD_COLOR[zone.hazard_level] || '#10B981';

  return (
    <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', background: '#0F1927' }}>
      {/* Zone header */}
      <div style={{
        background: `linear-gradient(135deg, ${color}28, ${color}12)`,
        borderTop: `2px solid ${color}`,
        padding: '10px 12px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700, color: '#F1F5F9', fontSize: 13, lineHeight: 1.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {zone.name}
          </div>
          <div style={{ fontSize: 10, color: '#64748B', marginTop: 2, fontFamily: 'monospace' }}>
            {zone.code} · {ZONE_TYPE_LABELS[zone.zone_type] || zone.zone_type}
          </div>
        </div>
        <button onClick={onClose} style={{ all: 'unset', cursor: 'pointer', color: '#475569', fontSize: 14, padding: 4, lineHeight: 1 }}>✕</button>
      </div>

      <div style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* POB */}
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <div>
            <span style={{ fontSize: 34, fontWeight: 900, color, lineHeight: 1 }}>{count}</span>
            <div style={{ fontSize: 9, color: '#64748B', fontWeight: 600, letterSpacing: '0.08em', marginTop: 2 }}>PERSONNEL ON BOARD</div>
          </div>
          <div style={{ textAlign: 'right', fontSize: 10.5 }}>
            <div style={{ color: hc, fontWeight: 700 }}>{zone.hazard_level} HAZARD</div>
            {zone.reader_count > 0 && (
              <div style={{ color: '#8B5CF6', marginTop: 2 }}>{zone.reader_count} ADMS reader{zone.reader_count !== 1 ? 's' : ''}</div>
            )}
          </div>
        </div>

        {/* Capacity bar */}
        {pct !== null && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, color: '#64748B', marginBottom: 4 }}>
              <span>Capacity</span>
              <span style={{ color: capC, fontWeight: 700 }}>{count}/{zone.max_capacity} ({pct}%)</span>
            </div>
            <div style={{ height: 4, background: 'rgba(255,255,255,0.08)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${pct}%`, background: `linear-gradient(90deg,${capC}88,${capC})`, borderRadius: 2 }} />
            </div>
          </div>
        )}

        {/* Who is here */}
        <div style={{ maxHeight: 220, overflowY: 'auto' }} className="map-sidebar-scroll">
          <PeopleList people={zone.personnel || []} dark highlight={highlight} />
        </div>

        {/* Location */}
        {zone.has_gps ? (
          <a
            href={`https://www.openstreetmap.org/?mlat=${zone.latitude}&mlon=${zone.longitude}#map=14/${zone.latitude}/${zone.longitude}`}
            target="_blank" rel="noopener noreferrer"
            style={{ fontSize: 11, color: '#38BDF8', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <EnvironmentOutlined style={{ fontSize: 11 }} />
            {parseFloat(zone.latitude).toFixed(4)}°N, {parseFloat(zone.longitude).toFixed(4)}°E · Open Map ↗
          </a>
        ) : null}
        {!zone.virtual && (
          <button onClick={onPlace} style={{
            all: 'unset', cursor: 'pointer', textAlign: 'center', fontSize: 11.5, fontWeight: 700,
            padding: '6px 8px', borderRadius: 6,
            background: placing ? '#F59E0B' : 'rgba(56,189,248,0.15)',
            color: placing ? '#111827' : '#38BDF8', border: '1px solid rgba(56,189,248,0.35)',
          }}>
            {placing ? 'Click on the map to place this zone… (click here to cancel)'
              : zone.has_gps ? 'Move on map' : 'Place on map'}
          </button>
        )}
      </div>
    </div>
  );
};

/* ── Main ZoneMapView ─────────────────────────────────────────────────────── */
const UNLOCATED_ID = 'unlocated';

const ZoneMapView = ({ zones: zonesProp = [] }) => {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [selectedId,  setSelectedId]  = useState(null);
  const [search,      setSearch]      = useState('');
  const [tileKey,     setTileKey]     = useState('light');
  const [isFullscreen,setIsFullscreen]= useState(false);
  const [placingId,   setPlacingId]   = useState(null);
  const containerRef = useRef(null);

  // Live feed: zones + WHO is in each + on-board people with no known zone.
  const { data: live } = useQuery({
    queryKey: ['zones-map-live'],
    queryFn:  () => apiService.get('/api/v1/zones/map-live'),
    refetchInterval: 5000,
  });
  const zones = useMemo(() => {
    const list = live?.zones || zonesProp.map(z => ({ ...z, personnel: [], has_gps: !!(z.latitude && z.longitude) }));
    return list.map(z => ({ ...z, has_gps: z.has_gps && !isNaN(parseFloat(z.latitude)) && !isNaN(parseFloat(z.longitude)) }));
  }, [live, zonesProp]);
  const unlocated = live?.unlocated || [];

  useEffect(() => {
    const onChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) containerRef.current?.requestFullscreen();
    else document.exitFullscreen();
  };

  const geoZones     = useMemo(() => zones.filter(z => z.has_gps), [zones]);
  const totalPOB     = live?.onboard_total ?? zones.reduce((s, z) => s + (z.current_personnel_count ?? 0), 0);
  const located      = live?.located_total ?? 0;
  const alertCount   = useMemo(() => zones.filter(z => ['EMERGENCY','LOCKDOWN'].includes(z.status)).length, [zones]);

  const unlocatedZone = useMemo(() => ({
    id: UNLOCATED_ID, virtual: true, name: 'On board — location unknown', code: 'NO ZONE',
    zone_type: 'OUTSIDE', hazard_level: 'LOW', display_color: '#94A3B8',
    personnel: unlocated, current_personnel_count: unlocated.length, has_gps: false,
  }), [unlocated]);

  const selectedZone = useMemo(
    () => selectedId === UNLOCATED_ID ? unlocatedZone : (zones.find(z => z.id === selectedId) || null),
    [zones, selectedId, unlocatedZone]);

  // Search matches zone names/codes AND people (name / employee code) inside zones.
  const q = search.trim().toLowerCase();
  const personHit = (p) => p.name.toLowerCase().includes(q) || p.emp_code.toLowerCase().includes(q);
  const filtered = useMemo(() => {
    if (!q) return zones;
    return zones.filter(z =>
      z.name.toLowerCase().includes(q) || (z.state || '').toLowerCase().includes(q) ||
      z.code.toLowerCase().includes(q) || (z.personnel || []).some(personHit));
  }, [zones, q]); // eslint-disable-line
  const showUnlocated = unlocated.length > 0 && (!q || unlocated.some(personHit) || 'location unknown'.includes(q));

  const placeZone = async ({ lat, lng }) => {
    const id = placingId;
    setPlacingId(null);
    try {
      await apiService.put(`/api/v1/zones/${id}/`, {
        latitude: Number(lat.toFixed(6)), longitude: Number(lng.toFixed(6)),
      });
      message.success('Zone placed on the map');
      qc.invalidateQueries({ queryKey: ['zones-map-live'] });
      qc.invalidateQueries({ queryKey: ['zones-dashboard'] });
    } catch (e) {
      message.error(e?.response?.data?.detail || e?.message || 'Could not save the location');
    }
  };

  const tile = TILE_LAYERS[tileKey];
  const isDark = tileKey === 'dark' || tileKey === 'satellite';

  return (
    <div
      ref={containerRef}
      style={{
        display: 'flex',
        height: isFullscreen ? '100vh' : 'calc(100vh - 230px)',
        minHeight: 520,
        width: '100%',
        borderRadius: isFullscreen ? 0 : 14,
        overflow: 'hidden',
        border: isFullscreen ? 'none' : '1px solid #1E2A3B',
        boxShadow: isFullscreen ? 'none' : '0 4px 24px rgba(0,0,0,0.18)',
      }}
    >
      {/* ══ Dark Sidebar ══ */}
      <div style={{
        width: 268, flexShrink: 0,
        display: 'flex', flexDirection: 'column',
        background: '#0F1927',
        borderRight: '1px solid rgba(255,255,255,0.06)',
      }}>

        {/* Sidebar top stats */}
        <div style={{
          padding: '14px 12px 10px',
          background: 'linear-gradient(180deg,#16213E,#0F1927)',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
            {[
              { label: 'ON BOARD',    value: totalPOB,           color: '#0078D4', bg: 'rgba(0,120,212,0.15)' },
              { label: 'IN A ZONE',   value: located,            color: '#10B981', bg: 'rgba(16,185,129,0.12)' },
              alertCount > 0
                ? { label: 'ALERTS', value: alertCount, color: '#EF4444', bg: 'rgba(239,68,68,0.12)' }
                : { label: 'NO ZONE', value: unlocated.length, color: unlocated.length ? '#F59E0B' : '#64748B', bg: 'rgba(245,158,11,0.12)' },
            ].map(s => (
              <div key={s.label} style={{
                flex: 1, background: s.bg, borderRadius: 8,
                padding: '7px 6px', textAlign: 'center',
                border: `1px solid ${s.color}25`,
              }}>
                <div style={{ fontSize: 20, fontWeight: 900, color: s.color, lineHeight: 1 }}>{s.value}</div>
                <div style={{ fontSize: 8.5, color: s.color, fontWeight: 700, marginTop: 2, letterSpacing: '0.06em', opacity: 0.8 }}>{s.label}</div>
              </div>
            ))}
          </div>

          <Input
            size="small"
            prefix={<SearchOutlined style={{ color: '#475569' }} />}
            placeholder="Search zone or person…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            allowClear
            style={{
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 7, color: '#E2E8F0', fontSize: 12,
            }}
          />
        </div>

        {/* Zone list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 8px 6px' }} className="map-sidebar-scroll">
          {showUnlocated && (
            <SidebarCard
              zone={unlocatedZone}
              isSelected={selectedId === UNLOCATED_ID}
              onClick={() => setSelectedId(prev => prev === UNLOCATED_ID ? null : UNLOCATED_ID)}
            />
          )}
          {filtered.length === 0 && !showUnlocated ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: '#475569', fontSize: 12 }}>
              No zone or person matches
            </div>
          ) : (
            filtered.map(z => (
              <SidebarCard
                key={z.id}
                zone={z}
                isSelected={z.id === selectedId}
                onClick={() => setSelectedId(prev => prev === z.id ? null : z.id)}
              />
            ))
          )}
        </div>

        {/* Selected zone panel */}
        <SelectedPanel
          zone={selectedZone}
          highlight={q}
          placing={!!placingId && placingId === selectedZone?.id}
          onPlace={() => setPlacingId(p => (p === selectedZone?.id ? null : selectedZone?.id))}
          onClose={() => { setSelectedId(null); setPlacingId(null); }}
        />
      </div>

      {/* ══ Map ══ */}
      <div style={{ flex: 1, position: 'relative' }}>
        <MapContainer
          center={[9.082, 8.675]}
          zoom={6}
          style={{ width: '100%', height: '100%', cursor: placingId ? 'crosshair' : undefined }}
          zoomControl={false}
        >
          <PlaceOnClick active={!!placingId} onPlace={placeZone} />
          <TileLayer url={tile.url} attribution={tile.attribution} maxZoom={19} maxNativeZoom={tile.maxNativeZoom || 19} key={tileKey} />
          <ZoomControl position="bottomright" />
          <MapController zone={selectedZone?.has_gps ? selectedZone : null} allZones={geoZones} />

          {geoZones.map(z => (
            <Marker
              key={z.id}
              position={[parseFloat(z.latitude), parseFloat(z.longitude)]}
              icon={markerIcon(z, z.id === selectedId, tileKey)}
              zIndexOffset={z.id === selectedId ? 1000 : 0}
              eventHandlers={{ click: () => setSelectedId(prev => prev === z.id ? null : z.id) }}
            >
              <Popup maxWidth={240} className="zone-map-popup">
                <ZonePopup zone={z} />
              </Popup>
            </Marker>
          ))}
        </MapContainer>

        {(placingId || geoZones.length === 0) && (
          <div style={{
            position: 'absolute', top: 52, left: '50%', transform: 'translateX(-50%)', zIndex: 1000,
            background: placingId ? '#F59E0B' : 'rgba(15,25,39,0.9)', color: placingId ? '#111827' : '#E2E8F0',
            padding: '8px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)', maxWidth: 460, textAlign: 'center',
          }}>
            {placingId
              ? `Click on the map where "${zones.find(z => z.id === placingId)?.name}" is.`
              : 'No zone has a map location yet. Select a zone on the left and press "Place on map", then click its spot on the map.'}
          </div>
        )}

        {/* ── Map layer switcher ── */}
        <div style={{
          position: 'absolute', top: 12, left: 12, zIndex: 1000,
          display: 'flex', gap: 4,
        }}>
          {Object.entries(TILE_LAYERS).map(([key, layer]) => (
            <button
              key={key}
              onClick={() => setTileKey(key)}
              style={{
                all: 'unset', cursor: 'pointer',
                padding: '5px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                background: tileKey === key
                  ? 'rgba(0,120,212,0.95)'
                  : 'rgba(15,25,39,0.82)',
                color: tileKey === key ? 'white' : 'rgba(255,255,255,0.65)',
                border: tileKey === key
                  ? '1px solid rgba(0,120,212,0.7)'
                  : '1px solid rgba(255,255,255,0.1)',
                backdropFilter: 'blur(6px)',
                transition: 'all 0.15s',
                boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
              }}
            >
              {layer.label}
            </button>
          ))}
        </div>

        {/* ── Fullscreen toggle ── */}
        <button
          onClick={toggleFullscreen}
          style={{
            position: 'absolute', top: 12, right: 12, zIndex: 1000,
            all: 'unset', cursor: 'pointer',
            width: 32, height: 32, borderRadius: 7,
            background: 'rgba(15,25,39,0.82)',
            border: '1px solid rgba(255,255,255,0.1)',
            backdropFilter: 'blur(6px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'rgba(255,255,255,0.75)', fontSize: 15,
            boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
            transition: 'all 0.15s',
          }}
          title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          onMouseEnter={e => e.currentTarget.style.background='rgba(0,120,212,0.85)'}
          onMouseLeave={e => e.currentTarget.style.background='rgba(15,25,39,0.82)'}
        >
          {isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
        </button>

        {/* ── Fit all zones button ── */}
        {selectedZone && (
          <button
            onClick={() => setSelectedId(null)}
            style={{
              position: 'absolute', bottom: 56, right: 12, zIndex: 1000,
              all: 'unset', cursor: 'pointer',
              padding: '6px 12px', borderRadius: 7, fontSize: 11, fontWeight: 600,
              background: 'rgba(15,25,39,0.88)',
              color: 'rgba(255,255,255,0.8)',
              border: '1px solid rgba(255,255,255,0.12)',
              backdropFilter: 'blur(6px)',
              display: 'flex', alignItems: 'center', gap: 5,
              boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
            }}
          >
            <GlobalOutlined style={{ fontSize: 12 }} /> Fit all zones
          </button>
        )}

        {/* ── Legend ── */}
        <div style={{
          position: 'absolute', bottom: 56, left: 12, zIndex: 1000,
          background: 'rgba(15,25,39,0.88)', backdropFilter: 'blur(6px)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 10, padding: '10px 12px',
          boxShadow: '0 2px 12px rgba(0,0,0,0.35)',
          minWidth: 130,
        }}>
          <div style={{ fontSize: 9.5, fontWeight: 700, color: '#64748B', letterSpacing: '0.08em', marginBottom: 7 }}>LEGEND</div>
          {[
            { color: '#10B981', label: 'Muster / Safe' },
            { color: '#EF4444', label: 'Work / Emergency' },
            { color: '#0078D4', label: 'Helipad / Haven' },
            { color: '#7C3AED', label: 'Restricted' },
            { color: '#F59E0B', label: 'Control / Storage' },
            { color: '#6B7280', label: 'Outside / Transit' },
          ].map(item => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: item.color, flexShrink: 0 }} />
              <span style={{ fontSize: 10.5, color: '#94A3B8' }}>{item.label}</span>
            </div>
          ))}
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', marginTop: 6, paddingTop: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', border: '2px solid #10B981', animation: 'mapPulse 2s infinite', flexShrink: 0 }} />
              <span style={{ fontSize: 10.5, color: '#94A3B8' }}>Pulsing = Active</span>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .map-sidebar-scroll::-webkit-scrollbar { width: 3px; }
        .map-sidebar-scroll::-webkit-scrollbar-track { background: transparent; }
        .map-sidebar-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

        .zone-map-popup .leaflet-popup-content-wrapper {
          border-radius: 10px !important;
          box-shadow: 0 8px 32px rgba(0,0,0,0.25) !important;
          padding: 0 !important;
          overflow: hidden;
        }
        .zone-map-popup .leaflet-popup-content {
          margin: 12px !important;
          width: 220px !important;
        }
        .zone-map-popup .leaflet-popup-tip-container { display: none; }

        @keyframes mapPulse {
          0%   { transform: scale(1);   opacity: 0.8; }
          50%  { transform: scale(1.5); opacity: 0.3; }
          100% { transform: scale(1);   opacity: 0.8; }
        }
      `}</style>
    </div>
  );
};

export default ZoneMapView;
