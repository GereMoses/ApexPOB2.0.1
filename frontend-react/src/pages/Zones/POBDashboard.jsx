import { useState, useEffect, useRef, useMemo } from 'react';
import { Button, Spin, Tooltip, Empty, message, Dropdown, Drawer, Badge, Avatar, Tag } from 'antd';
import {
  ArrowLeftOutlined, ReloadOutlined, TeamOutlined,
  WifiOutlined, DisconnectOutlined,
  UploadOutlined, DeleteOutlined, MoreOutlined,
  VerticalLeftOutlined, VerticalRightOutlined,
  VerticalAlignTopOutlined, VerticalAlignBottomOutlined,
  SyncOutlined, LoginOutlined, LogoutOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import apiService from '../../services/api';

const MAP_KEY = 'pob-map-image';

const DEFAULT_TILE_COLORS = {
  LOCATION:     '#52c41a', MUSTER_POINT: '#52c41a', WORK_AREA:    '#f5222d',
  OUTSIDE:      '#595959', TRANSIT:      '#13c2c2', RESTRICTED:   '#6B1E35',
  ACCOMMODATION:'#6B1E35', SAFE_HAVEN:   '#0078D4', HELIPAD:      '#0078D4',
  CONTROL_ROOM: '#d97706', STORAGE:      '#8B4513', EMERGENCY:    '#f5222d',
  PUBLIC:       '#52c41a',
};

const tileColor = z => z.display_color || DEFAULT_TILE_COLORS[z.zone_type] || '#52c41a';

/* ── Live zone map (replaces the static country image) ──────────────────────── */
const _miniIcon = (zone, count) => {
  const color = tileColor(zone);
  const size = 38;
  const label = zone.name.length > 18 ? zone.name.slice(0, 16) + '…' : zone.name;
  return L.divIcon({
    className: '',
    html: `
      <div style="text-align:center;cursor:pointer;">
        <div style="width:${size}px;height:${size}px;background:linear-gradient(135deg,${color}dd,${color});border-radius:50%;border:2px solid #fff;box-shadow:0 2px 10px rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;margin:0 auto;">
          <span style="color:#fff;font-weight:900;font-size:${count >= 100 ? 11 : 14}px;text-shadow:0 1px 3px rgba(0,0,0,0.4);">${count}</span>
        </div>
        <div style="background:rgba(15,20,35,0.82);color:#fff;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;margin-top:4px;display:inline-block;max-width:140px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-bottom:2px solid ${color};">${label}</div>
      </div>`,
    iconSize: [120, 60], iconAnchor: [60, 19], popupAnchor: [0, -30],
  });
};

const FitToZones = ({ coords }) => {
  const map = useMap();
  useEffect(() => {
    const c = map.getContainer();
    if (!c || typeof ResizeObserver === 'undefined') return;
    let had = false;
    const ro = new ResizeObserver(() => {
      const r = c.getBoundingClientRect();
      const has = r.width > 0 && r.height > 0;
      if (has && !had) map.invalidateSize();
      had = has;
    });
    ro.observe(c);
    return () => ro.disconnect();
  }, [map]);
  useEffect(() => {
    if (!coords.length) return;
    const go = () => { try { map.fitBounds(coords, { padding: [50, 50], maxZoom: 14, animate: false }); } catch (_) {} };
    const s = map.getSize();
    if (s && s.x > 0) go(); else { map.once('resize', go); return () => map.off('resize', go); }
  }, [coords, map]); // eslint-disable-line
  return null;
};

/* Free basemaps — no API key required */
const BASEMAPS = {
  light:     { label: 'Light',     url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', sub: [], maxNativeZoom: 16 },   // CARTO now needs an API key
  street:    { label: 'Street',    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',              sub: ['a', 'b', 'c'] },
  satellite: { label: 'Satellite', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', sub: [] },
};

const LiveZoneMap = ({ zones, getCount, onZoneClick }) => {
  const [bm, setBm] = useState(() => localStorage.getItem('pob-basemap') || 'light');
  const pts = zones.filter(z => !isNaN(parseFloat(z.latitude)) && !isNaN(parseFloat(z.longitude)));
  const coords = pts.map(z => [parseFloat(z.latitude), parseFloat(z.longitude)]);
  const center = coords.length ? coords[0] : [9.08, 8.68]; // Nigeria fallback
  const tile = BASEMAPS[bm] || BASEMAPS.light;
  const pick = (k) => { setBm(k); localStorage.setItem('pob-basemap', k); };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <MapContainer center={center} zoom={11} style={{ width: '100%', height: '100%' }}
        scrollWheelZoom attributionControl={false} preferCanvas>
        <TileLayer key={bm} url={tile.url} subdomains={tile.sub} maxZoom={19} maxNativeZoom={tile.maxNativeZoom || 19} />
        <FitToZones coords={coords} />
        {pts.map(z => {
          const c = getCount(z);
          return (
            <Marker key={z.id} position={[parseFloat(z.latitude), parseFloat(z.longitude)]}
              icon={_miniIcon(z, c)} eventHandlers={{ click: () => onZoneClick?.(z) }}>
              <Popup>
                <div style={{ fontWeight: 700, fontSize: 13 }}>{z.name}</div>
                <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>
                  {(z.zone_type || '').replace('_', ' ')} · <b style={{ color: '#111827' }}>{c}</b> on board
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      {/* Basemap switcher */}
      <div style={{
        position: 'absolute', top: 10, right: 10, zIndex: 1000,
        display: 'flex', gap: 3, padding: 3, borderRadius: 10,
        background: 'rgba(255,255,255,0.85)', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
        boxShadow: '0 4px 16px rgba(15,23,42,0.18)', border: '1px solid rgba(255,255,255,0.7)',
      }}>
        {Object.entries(BASEMAPS).map(([k, v]) => (
          <button key={k} onClick={() => pick(k)}
            style={{
              border: 'none', cursor: 'pointer', borderRadius: 7, padding: '5px 11px',
              fontSize: 11, fontWeight: 700, lineHeight: 1,
              background: bm === k ? '#1a3a5c' : 'transparent',
              color: bm === k ? '#fff' : '#475569',
              transition: 'background .15s',
            }}>
            {v.label}
          </button>
        ))}
      </div>
    </div>
  );
};

const POSITION_ITEMS = [
  { key: 'left',   label: 'Left',   icon: <VerticalRightOutlined /> },
  { key: 'right',  label: 'Right',  icon: <VerticalLeftOutlined />  },
  { key: 'top',    label: 'Top',    icon: <VerticalAlignTopOutlined /> },
  { key: 'bottom', label: 'Bottom', icon: <VerticalAlignBottomOutlined /> },
  { key: 'auto',   label: 'Auto',   icon: <SyncOutlined /> },
];

/* ── Position picker overlay on any tile ────────────────────────────────────── */
const WithPositionPicker = ({ zone, onPositionChange, onViewPersonnel, children }) => {
  const [hovered, setHovered] = useState(false);
  const current = zone.tile_position || 'auto';

  const menuItems = [
    {
      key: 'personnel',
      icon: <TeamOutlined />,
      label: 'View Personnel',
      onClick: () => onViewPersonnel?.(zone),
    },
    { type: 'divider' },
    ...POSITION_ITEMS.map(p => ({
      key: p.key,
      icon: p.icon,
      label: p.label,
      style: p.key === current ? { fontWeight: 700, color: '#0078D4' } : {},
      onClick: () => onPositionChange(zone.id, p.key),
    })),
  ];

  return (
    <div
      style={{ position: 'relative', display: 'inline-block' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {children}
      {hovered && (
        <Dropdown menu={{ items: menuItems }} trigger={['click']} placement="topRight">
          <div
            onClick={e => e.stopPropagation()}
            style={{
              position: 'absolute', top: 3, right: 3,
              background: 'rgba(0,0,0,0.65)', borderRadius: 4,
              width: 20, height: 20, display: 'flex', alignItems: 'center',
              justifyContent: 'center', cursor: 'pointer', zIndex: 50,
              color: '#fff', fontSize: 12,
            }}
          >
            <MoreOutlined />
          </div>
        </Dropdown>
      )}
    </div>
  );
};

/* ── Zone Tile ───────────────────────────────────────────────────────────────── */
const ZoneTile = ({ zone, onClick, width = 200, getCount }) => {
  const bg  = tileColor(zone);
  const cnt = getCount ? getCount(zone) : (zone.current_personnel_count ?? 0);
  const alert = ['EMERGENCY','LOCKDOWN'].includes(zone.status);
  return (
    <div
      onClick={e => { e.stopPropagation(); onClick?.(); }}
      style={{
        background: `linear-gradient(145deg, ${bg}f0, ${bg})`,
        borderRadius: 8, width, textAlign: 'center',
        padding: '10px 18px',
        border: alert ? '2px solid #ff4d4f' : '1px solid rgba(255,255,255,0.22)',
        boxShadow: alert ? '0 0 0 2px #ff4d4f55,0 6px 18px rgba(0,0,0,0.5)' : '0 4px 16px rgba(0,0,0,0.4)',
        cursor: onClick ? 'pointer' : 'default',
        position: 'relative', overflow: 'hidden',
      }}
    >
      <div style={{ position:'absolute',top:0,left:0,right:0,height:3,background:'rgba(255,255,255,0.38)',borderRadius:'8px 8px 0 0' }} />
      <div style={{ fontSize:13,fontWeight:700,color:'rgba(255,255,255,0.95)',textTransform:'uppercase',letterSpacing:'0.05em',lineHeight:1.3,marginBottom:6 }}>
        {zone.name}
      </div>
      <div style={{ fontSize:34,fontWeight:900,color:'#fff',lineHeight:1,textShadow:'0 2px 8px rgba(0,0,0,0.35)' }}>
        {cnt}
      </div>
      {onClick && (
        <div style={{ fontSize:10,color:'rgba(255,255,255,0.5)',marginTop:5,letterSpacing:'0.06em' }}>TAP ▶</div>
      )}
    </div>
  );
};

/* ── Location Card ───────────────────────────────────────────────────────────── */
const LocationCard = ({ zone, onClick, getCount }) => {
  const bg  = tileColor(zone);
  const cnt = getCount ? getCount(zone) : (zone.current_personnel_count ?? 0);
  const alert = ['EMERGENCY','LOCKDOWN'].includes(zone.status);
  return (
    <div
      onClick={e => { e.stopPropagation(); onClick?.(); }}
      style={{
        border: alert ? '2px solid #ff4d4f' : `2px solid ${bg}`,
        borderRadius: 10, overflow: 'hidden', width: 210,
        boxShadow: alert ? '0 0 0 2px #ff4d4f33,0 6px 22px rgba(0,0,0,0.5)' : '0 6px 20px rgba(0,0,0,0.45)',
        cursor: onClick ? 'pointer' : 'default',
        userSelect: 'none',
      }}
    >
      {zone.floor_plan_url && (
        <div style={{ height:80,background:'#111827',overflow:'hidden',display:'flex',alignItems:'center',justifyContent:'center',position:'relative' }}>
          <img src={zone.floor_plan_url} alt={zone.name} style={{ width:'100%',height:'100%',objectFit:'cover',pointerEvents:'none' }} onError={e => { e.target.parentElement.style.display='none'; }} />
          {alert && (
            <div style={{ position:'absolute',top:4,right:4,background:'#ff4d4f',borderRadius:4,padding:'2px 7px',fontSize:10,fontWeight:700,color:'#fff' }}>
              {zone.status}
            </div>
          )}
        </div>
      )}
      <div style={{ background:`linear-gradient(145deg,${bg}f0,${bg})`,padding:'5px 10px',textAlign:'center',position:'relative',overflow:'hidden' }}>
        <div style={{ position:'absolute',top:0,left:0,right:0,height:2,background:'rgba(255,255,255,0.28)' }} />
        {alert && !zone.floor_plan_url && (
          <div style={{ position:'absolute',top:4,right:4,background:'rgba(0,0,0,0.35)',borderRadius:4,padding:'1px 6px',fontSize:10,fontWeight:700,color:'#fff' }}>
            {zone.status}
          </div>
        )}
        <div style={{ fontSize:13,fontWeight:700,color:'rgba(255,255,255,0.95)',textTransform:'uppercase',letterSpacing:'0.04em',marginBottom:3 }}>
          {zone.name}
        </div>
        <div style={{ fontSize:30,fontWeight:900,color:'#fff',lineHeight:1,textShadow:'0 2px 8px rgba(0,0,0,0.3)' }}>
          {cnt}
        </div>
        <div style={{ fontSize:10,color:'rgba(255,255,255,0.6)',letterSpacing:'0.06em',marginTop:4 }}>
          PERSONNEL ON BOARD
        </div>
      </div>
    </div>
  );
};

/* ── POB Counter tile ────────────────────────────────────────────────────────── */
const PobCounter = ({ totalPOB }) => (
  <div style={{
    background:'linear-gradient(135deg,#cf1322,#f5222d)',
    borderRadius:10,padding:'6px 36px 10px',textAlign:'center',
    boxShadow:'0 8px 28px rgba(245,34,45,0.55)',
    border:'1px solid rgba(255,255,255,0.2)',
  }}>
    <div style={{ fontSize:12,fontWeight:700,color:'rgba(255,255,255,0.82)',letterSpacing:'0.14em',marginBottom:4 }}>
      NIGERIA POB
    </div>
    <div style={{ fontSize:46,fontWeight:900,color:'#fff',lineHeight:1,textShadow:'0 3px 12px rgba(0,0,0,0.3)' }}>
      {totalPOB}
    </div>
  </div>
);

/* ── Zone Personnel Drawer ───────────────────────────────────────────────────── */
const ZonePersonnelDrawer = ({ zone, open, onClose }) => {
  const { data: personnel = [], isLoading } = useQuery({
    queryKey: ['zone-live-personnel', zone?.id],
    queryFn: () => apiService.get(`/api/v1/zones/${zone.id}/live-personnel`),
    enabled: !!zone && open,
    refetchInterval: 30000,
  });

  return (
    <Drawer
      title={
        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          <TeamOutlined />
          <span style={{ fontWeight:700 }}>{zone?.name}</span>
          <Badge count={personnel.length} style={{ backgroundColor:'#52c41a' }} />
        </div>
      }
      open={open}
      onClose={onClose}
      width={400}
      placement="right"
      destroyOnHidden
    >
      {isLoading ? (
        <div style={{ textAlign:'center', paddingTop:40 }}>
          <Spin />
          <div style={{ marginTop:12, color:'#6B7280', fontSize:13 }}>Loading personnel…</div>
        </div>
      ) : personnel.length === 0 ? (
        <Empty description="No personnel currently in this zone" style={{ marginTop:40 }} />
      ) : (
        <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
          {personnel.map(p => (
            <div key={p.emp_code} style={{ display:'flex', alignItems:'center', gap:12, padding:'10px 14px', background:'#f9fafb', borderRadius:8, border:'1px solid #e5e7eb' }}>
              <Avatar src={p.photo_url} size={46} style={{ flexShrink:0, background:'#3b82f6' }}>
                {!p.photo_url && (p.full_name?.[0]?.toUpperCase() || '?')}
              </Avatar>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontWeight:600, fontSize:13, color:'#111827', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                  {p.full_name || p.emp_code}
                </div>
                <div style={{ fontSize:11, color:'#6B7280', marginTop:2 }}>{p.emp_code}</div>
                {p.department && (
                  <div style={{ fontSize:11, color:'#4b5563', marginTop:2 }}>{p.department}{p.designation ? ` · ${p.designation}` : ''}</div>
                )}
                {p.entry_time && (
                  <div style={{ fontSize:10, color:'#13c2c2', marginTop:3 }}>
                    Entry: {new Date(p.entry_time).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Drawer>
  );
};

/* ── Country overview (side-column layout) ───────────────────────────────────── */
const CountryOverview = ({ topLevelZones, totalPOB, byParent, onSelectZone, getCount, onPositionChange, onViewPersonnel }) => {
  const gc = getCount || (z => z.current_personnel_count ?? 0);

  /* Zone categorisation */
  const autoZones     = topLevelZones.filter(z => !z.tile_position || z.tile_position === 'auto');
  const leftZones     = topLevelZones.filter(z => z.tile_position === 'left');
  const rightZones    = topLevelZones.filter(z => z.tile_position === 'right');
  const topZones      = topLevelZones.filter(z => z.tile_position === 'top');
  const bottomZones   = topLevelZones.filter(z => z.tile_position === 'bottom');
  const autoLocations = autoZones.filter(z => (byParent[String(z.id)] || []).length > 0);
  const autoOutside   = autoZones.filter(z => !(byParent[String(z.id)] || []).length);
  const finalLeft     = [...leftZones, ...autoLocations];
  const finalRight    = [...rightZones, ...autoOutside];

  /* Map image */
  const [mapSrc, setMapSrc]           = useState(() => localStorage.getItem(MAP_KEY) || '/image.png');
  const [mapIsCustom, setMapIsCustom] = useState(() => !!localStorage.getItem(MAP_KEY));
  const mapInputRef = useRef(null);

  const handleMapUpload = (e) => {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    if (!file.type.startsWith('image/')) { message.error('Please select an image file'); return; }
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        localStorage.setItem(MAP_KEY, ev.target.result);
        setMapSrc(ev.target.result);
        setMapIsCustom(true);
        message.success('Map image updated');
      } catch (_) {
        message.error('Image too large to store locally. Try a smaller/compressed image.');
      }
    };
    reader.readAsDataURL(file);
  };

  const removeCustomMap = () => {
    localStorage.removeItem(MAP_KEY);
    setMapSrc('/image.png');
    setMapIsCustom(false);
    message.success('Reverted to default map');
  };

  /* Container height fills the viewport below the ZM page chrome */
  const containerH = 'max(500px, calc(100vh - 430px))';

  if (topLevelZones.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <div>
            <div style={{ fontWeight:600,fontSize:14,color:'#374151' }}>No zones configured yet</div>
            <div style={{ fontSize:12,color:'#6B7280',marginTop:6,lineHeight:1.7 }}>
              Go to <strong>Zone List</strong> → Create zones. Set a <strong>Parent Zone</strong> to
              build hierarchies. Use <strong>Tile Position</strong> to control placement.
            </div>
          </div>
        }
      />
    );
  }

  /* Which column/row gets the POB counter */
  const pobInLeft   = finalLeft.length > 0;
  const pobInRight  = !pobInLeft && finalRight.length > 0;
  const pobOnMap    = !pobInLeft && !pobInRight;

  const allZonesFlat = [...topLevelZones, ...Object.values(byParent || {}).flat()];

  const renderTile = (z) => {
    const hasChildren = (byParent[String(z.id)] || []).length > 0;
    const isCard = finalLeft.includes(z);
    const tileClick = hasChildren ? () => onSelectZone(z) : () => onViewPersonnel?.(z);
    const tile = isCard
      ? <LocationCard zone={z} getCount={gc} onClick={tileClick} />
      : <ZoneTile zone={z} getCount={gc} onClick={tileClick} width={200} />;
    return (
      <WithPositionPicker key={z.id} zone={z} onPositionChange={onPositionChange} onViewPersonnel={onViewPersonnel}>
        {tile}
      </WithPositionPicker>
    );
  };

  return (
    <div>
      {/* Controls row */}
      <div style={{ display:'flex',alignItems:'center',gap:10,marginBottom:8,flexWrap:'wrap' }}>
        <span style={{ fontSize:11,color:'#6B7280' }}>
          Live map — markers show personnel on board per zone · click a marker or tile to drill in · hover a tile → <MoreOutlined /> to reposition
        </span>
      </div>

      {/* ── Top row ── */}
      {topZones.length > 0 && (
        <div style={{ display:'flex',gap:8,marginBottom:8,flexWrap:'wrap',alignItems:'flex-start',justifyContent:'center' }}>
          {topZones.map(renderTile)}
        </div>
      )}

      {/* ── Middle: left column | map | right column ── */}
      <div style={{ display:'flex', gap:10, height: containerH, justifyContent:'center' }}>

        {/* Left column */}
        {finalLeft.length > 0 && (
          <div style={{ display:'flex',flexDirection:'column',gap:8,flexShrink:0,overflowY:'auto',paddingBottom:4 }}>
            {pobInLeft && <PobCounter totalPOB={totalPOB} />}
            {finalLeft.map(renderTile)}
          </div>
        )}

        {/* Center — live zone map (markers = live POB per zone) */}
        <div style={{
          flex:1, minWidth:0, height:'100%', position:'relative',
          borderRadius:16, overflow:'hidden',
          border:'1px solid rgba(255,255,255,0.6)',
          boxShadow:'0 8px 32px rgba(15,23,42,0.12)',
        }}>
          <LiveZoneMap
            zones={allZonesFlat}
            getCount={gc}
            onZoneClick={(z) => ((byParent[String(z.id)] || []).length > 0 ? onSelectZone(z) : onViewPersonnel?.(z))}
          />
          {pobOnMap && (
            <div style={{ position:'absolute', top:10, left:'50%', transform:'translateX(-50%)', zIndex:1000, pointerEvents:'none' }}>
              <PobCounter totalPOB={totalPOB} />
            </div>
          )}
        </div>

        {/* Right column */}
        {finalRight.length > 0 && (
          <div style={{ display:'flex',flexDirection:'column',gap:8,flexShrink:0,overflowY:'auto',paddingBottom:4 }}>
            {pobInRight && <PobCounter totalPOB={totalPOB} />}
            {finalRight.map(renderTile)}
          </div>
        )}
      </div>

      {/* ── Bottom row ── */}
      {bottomZones.length > 0 && (
        <div style={{ display:'flex',gap:8,marginTop:8,flexWrap:'wrap',alignItems:'flex-start',justifyContent:'center' }}>
          {bottomZones.map(renderTile)}
        </div>
      )}
    </div>
  );
};

/* ── Zone Detail View (drill-down, not draggable) ────────────────────────────── */
const ZoneDetailView = ({ zone, subZones, onBack, onDrillDown, byParent, getCount, onViewPersonnel }) => {
  const gc = getCount || (z => z.current_personnel_count ?? 0);
  const topZones    = subZones.filter(z => z.tile_position === 'top');
  const leftZones   = subZones.filter(z => z.tile_position === 'left');
  const rightZones  = subZones.filter(z => z.tile_position === 'right');
  const bottomZones = subZones.filter(z => z.tile_position === 'bottom');
  const autoZones   = subZones.filter(z => !z.tile_position || z.tile_position === 'auto');
  const autoLeft    = autoZones.filter(z => z.zone_type === 'MUSTER_POINT');
  const autoRight   = autoZones.filter(z => z.zone_type !== 'MUSTER_POINT');
  const finalLeft   = [...leftZones, ...autoLeft];
  const finalRight  = [...rightZones, ...autoRight];
  const musterTotal = subZones.filter(z => z.zone_type === 'MUSTER_POINT').reduce((s, z) => s + gc(z), 0);
  const hasMuster   = finalLeft.some(z => z.zone_type === 'MUSTER_POINT');
  const zonePOB     = subZones.reduce((s, z) => s + gc(z), gc(zone));

  return (
    <div style={{ background:'rgba(255,255,255,0.5)', backdropFilter:'blur(18px) saturate(160%)', WebkitBackdropFilter:'blur(18px) saturate(160%)', border:'1px solid rgba(255,255,255,0.6)', borderRadius:16, padding:12, boxShadow:'0 8px 32px rgba(15,23,42,0.1)' }}>
      {/* Header */}
      <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:10 }}>
        <Button icon={<ArrowLeftOutlined />} size="small" onClick={onBack} style={{ borderRadius:6,fontWeight:600 }}>
          Overview
        </Button>
        <div style={{ background:'linear-gradient(135deg,#cf1322,#f5222d)',borderRadius:8,padding:'4px 28px',textAlign:'center',boxShadow:'0 4px 16px rgba(245,34,45,0.4)' }}>
          <div style={{ fontSize:9,fontWeight:700,color:'rgba(255,255,255,0.78)',letterSpacing:'0.1em',textTransform:'uppercase' }}>
            TOTAL POB — {zone.name.toUpperCase()}
          </div>
          <div style={{ fontSize:38,fontWeight:900,color:'#fff',lineHeight:1 }}>{zonePOB}</div>
        </div>
        <div style={{ width:90 }} />
      </div>

      {topZones.length > 0 && (
        <div style={{ display:'flex',gap:8,justifyContent:'center',marginBottom:10,flexWrap:'wrap' }}>
          {topZones.map(z => (
            <ZoneTile key={z.id} zone={z} getCount={gc}
              onClick={(byParent[String(z.id)]?.length > 0) ? () => onDrillDown(z) : () => onViewPersonnel?.(z)} width={140} />
          ))}
        </div>
      )}

      <div style={{ display:'flex',gap:10,alignItems:'flex-start' }}>
        {finalLeft.length > 0 && (
          <div style={{ flexShrink:0 }}>
            <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,marginBottom:6 }}>
              {finalLeft.map(z => <ZoneTile key={z.id} zone={z} getCount={gc} width={108} />)}
            </div>
            {hasMuster && (
              <div style={{ background:'linear-gradient(135deg,#c41d7f,#eb2f96)',borderRadius:6,padding:'7px 12px',textAlign:'center',boxShadow:'0 3px 12px rgba(235,47,150,0.4)' }}>
                <div style={{ fontSize:9,fontWeight:700,color:'rgba(255,255,255,0.85)',letterSpacing:'0.06em',textTransform:'uppercase' }}>MUSTER TOTAL</div>
                <div style={{ fontSize:28,fontWeight:900,color:'#fff',lineHeight:1 }}>{musterTotal}</div>
              </div>
            )}
          </div>
        )}

        <div style={{ flex:1,minWidth:0 }}>
          <div style={{ border:'3px solid #92400E',borderRadius:8,overflow:'hidden',background:'#111827',minHeight:270,boxShadow:'0 4px 20px rgba(0,0,0,0.3)' }}>
            {zone.floor_plan_url ? (
              <img src={zone.floor_plan_url} alt={zone.name} style={{ width:'100%',display:'block',objectFit:'cover',minHeight:270 }} onError={e => { e.target.style.display='none'; }} />
            ) : (
              <div style={{ display:'flex',alignItems:'center',justifyContent:'center',minHeight:270,flexDirection:'column',gap:10 }}>
                <TeamOutlined style={{ fontSize:52,color:'#374151' }} />
                <div style={{ color:'#6B7280',fontSize:13,fontWeight:600 }}>No location image</div>
              </div>
            )}
          </div>
          <div style={{ background:'linear-gradient(90deg,#78350F,#92400E)',textAlign:'center',padding:'5px 0',borderRadius:'0 0 6px 6px' }}>
            <span style={{ color:'#fff',fontWeight:700,fontSize:13,letterSpacing:'0.03em' }}>{zone.name}</span>
          </div>
        </div>

        {finalRight.length > 0 && (
          <div style={{ display:'flex',flexDirection:'column',gap:6,flexShrink:0 }}>
            {finalRight.map(z => (
              <ZoneTile key={z.id} zone={z} getCount={gc}
                onClick={(byParent[String(z.id)]?.length > 0) ? () => onDrillDown(z) : () => onViewPersonnel?.(z)} width={140} />
            ))}
          </div>
        )}
      </div>

      {bottomZones.length > 0 && (
        <div style={{ display:'flex',gap:8,justifyContent:'center',marginTop:10,flexWrap:'wrap' }}>
          {bottomZones.map(z => (
            <ZoneTile key={z.id} zone={z} getCount={gc}
              onClick={(byParent[String(z.id)]?.length > 0) ? () => onDrillDown(z) : () => onViewPersonnel?.(z)} width={150} />
          ))}
        </div>
      )}
    </div>
  );
};

/* ── Time-ago helper ─────────────────────────────────────────────────────────── */
const timeAgo = (isoStr) => {
  if (!isoStr) return '';
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (diff < 10)  return 'just now';
  if (diff < 60)  return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
};

/* ── Activity Feed Drawer ────────────────────────────────────────────────────── */
const ActivityFeedDrawer = ({ open, onClose }) => {
  const [events, setEvents]       = useState([]);
  const [newCount, setNewCount]   = useState(0);
  const latestIdRef               = useRef(null);
  const [tick, setTick]           = useState(0);

  // Tick every 30s to update time-ago labels
  useEffect(() => {
    const t = setInterval(() => setTick(n => n + 1), 30000);
    return () => clearInterval(t);
  }, []);

  // Initial load
  const { data: initialData, isLoading } = useQuery({
    queryKey: ['zone-activity-initial'],
    queryFn:  () => apiService.get('/api/v1/zones/activity-feed?limit=30'),
    refetchOnWindowFocus: false,
    staleTime: Infinity,
  });
  useEffect(() => {
    if (!initialData) return;
    const rows = Array.isArray(initialData) ? initialData : (initialData?.data ?? []);
    setEvents(rows);
    if (rows.length > 0) latestIdRef.current = rows[0].id;
  }, [initialData]);

  // Poll for new events every 5s
  useQuery({
    queryKey: ['zone-activity-poll'],
    queryFn:  async () => {
      const res = await apiService.get('/api/v1/zones/activity-feed?limit=20');
      const rows = Array.isArray(res) ? res : (res?.data ?? []);
      const fresh = latestIdRef.current
        ? rows.filter(r => r.id > latestIdRef.current)
        : [];
      if (fresh.length > 0) {
        latestIdRef.current = fresh[0].id;
        setEvents(prev => {
          const merged = [...fresh, ...prev];
          return merged.slice(0, 60);
        });
        if (!open) setNewCount(p => p + fresh.length);
      }
      return rows;
    },
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });

  const handleOpen = () => { setNewCount(0); onClose(false); };

  const eventColor = (type) => type === 'CLOCK_IN' ? '#22c55e' : '#f97316';
  const eventLabel = (type) => type === 'CLOCK_IN' ? 'IN' : 'OUT';
  const EventIcon  = ({ type }) => type === 'CLOCK_IN'
    ? <LoginOutlined  style={{ fontSize: 11, color: eventColor(type) }} />
    : <LogoutOutlined style={{ fontSize: 11, color: eventColor(type) }} />;

  return (
    <>
      {/* Toggle button with unread badge */}
      <Tooltip title="Live Activity Feed" placement="left">
        <Badge count={newCount} size="small" offset={[-2, 2]}>
          <Button
            size="small"
            icon={<ThunderboltOutlined />}
            onClick={() => { setNewCount(0); onClose(true); }}
            style={{
              borderRadius: 6, fontWeight: 600, fontSize: 11,
              background: open ? '#0078D4' : undefined,
              color: open ? '#fff' : undefined,
              borderColor: open ? '#0078D4' : undefined,
            }}
          >
            Activity
          </Button>
        </Badge>
      </Tooltip>

      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ThunderboltOutlined style={{ color: '#0078D4' }} />
            <span style={{ fontWeight: 700 }}>Live Activity Feed</span>
            <Tag color="blue" style={{ marginLeft: 'auto', fontSize: 10 }}>
              {events.length} events
            </Tag>
          </div>
        }
        open={open}
        onClose={() => onClose(false)}
        width={340}
        placement="right"
        destroyOnHidden={false}
        styles={{ body: { padding: '8px 0', background: '#0F172A' }, header: { background: '#1E293B', borderBottom: '1px solid rgba(255,255,255,0.08)', color: '#F1F5F9' } }}
      >
        {isLoading ? (
          <div style={{ textAlign: 'center', paddingTop: 48 }}>
            <Spin />
            <div style={{ marginTop: 12, color: '#64748B', fontSize: 12 }}>Loading activity…</div>
          </div>
        ) : events.length === 0 ? (
          <div style={{ textAlign: 'center', paddingTop: 48 }}>
            <ThunderboltOutlined style={{ fontSize: 32, color: '#334155', display: 'block', marginBottom: 10 }} />
            <div style={{ color: '#64748B', fontSize: 12 }}>No badge events yet</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {events.map((ev, idx) => (
              <div
                key={ev.id ?? idx}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 14px',
                  borderBottom: '1px solid rgba(255,255,255,0.04)',
                  background: idx === 0 ? 'rgba(0,120,212,0.08)' : 'transparent',
                  transition: 'background 0.3s',
                }}
              >
                <Avatar
                  src={ev.photo_url}
                  size={36}
                  style={{ flexShrink: 0, background: ev.event_type === 'CLOCK_IN' ? '#064e3b' : '#7c2d12', border: `1.5px solid ${eventColor(ev.event_type)}40` }}
                >
                  {!ev.photo_url && (ev.emp_name?.[0]?.toUpperCase() || '?')}
                </Avatar>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 2 }}>
                    <span style={{ fontWeight: 600, fontSize: 12, color: '#E2E8F0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {ev.emp_name || ev.emp_code}
                    </span>
                    <span style={{
                      flexShrink: 0, fontSize: 9, fontWeight: 800,
                      color: eventColor(ev.event_type),
                      background: `${eventColor(ev.event_type)}18`,
                      borderRadius: 3, padding: '1px 5px', letterSpacing: '0.06em',
                    }}>
                      {eventLabel(ev.event_type)}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: '#64748B', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <EventIcon type={ev.event_type} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {ev.zone_name || 'Unknown zone'}
                    </span>
                  </div>
                  {ev.department && (
                    <div style={{ fontSize: 10, color: '#475569', marginTop: 1 }}>{ev.department}</div>
                  )}
                </div>

                <div style={{ flexShrink: 0, fontSize: 10, color: '#475569', textAlign: 'right' }}>
                  {/* tick dependency keeps time-ago labels fresh */}
                  {tick >= 0 && timeAgo(ev.punch_time)}
                </div>
              </div>
            ))}
          </div>
        )}
      </Drawer>
    </>
  );
};

/* ── Main POBDashboard ───────────────────────────────────────────────────────── */
const POBDashboard = ({ onRefreshDash }) => {
  const [selectedZone,       setSelectedZone]       = useState(null);
  const [history,            setHistory]            = useState([]);
  const [liveCounts,         setLiveCounts]         = useState({});
  const [personnelDrawerZone, setPersonnelDrawerZone] = useState(null);
  const [activityOpen,       setActivityOpen]       = useState(false);
  const [wsStatus,     setWsStatus]     = useState('connecting');
  const wsRef          = useRef(null);
  const reconnectTimer = useRef(null);
  const queryClient    = useQueryClient();

  const { data: hierarchyData, isLoading, refetch } = useQuery({
    queryKey: ['zones-hierarchy'],
    queryFn:  () => apiService.get('/api/v1/zones/hierarchy'),
  });

  const patchPositionM = useMutation({
    mutationFn: ({ id, position }) =>
      apiService.patch(`/api/v1/zones/${id}/position`, { tile_position: position }),
    onSuccess: (_, { position }) => {
      message.success(`Zone moved to ${position}`);
      queryClient.invalidateQueries({ queryKey: ['zones-hierarchy'] });
      queryClient.invalidateQueries({ queryKey: ['zones-dashboard'] });
    },
    onError: err => message.error(err?.message || 'Position update failed'),
  });

  /* WebSocket for live counts */
  useEffect(() => {
    let alive = true;
    const connect = () => {
      if (!alive) return;
      setWsStatus('connecting');
      const token = localStorage.getItem('token') || '';
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws    = new WebSocket(`${proto}//${window.location.host}/api/v1/zones/ws?token=${token}`);
      wsRef.current = ws;
      ws.onopen  = () => { if (alive) setWsStatus('live'); };
      ws.onmessage = (evt) => {
        if (!alive) return;
        try {
          const d = JSON.parse(evt.data);
          if (Array.isArray(d)) {
            const m = {};
            d.forEach(i => { if (i.zone_id != null) m[i.zone_id] = i.count; });
            setLiveCounts(m);
          } else if (d.type === 'zone_update' && d.zone_id != null) {
            setLiveCounts(p => ({ ...p, [d.zone_id]: d.count }));
          }
        } catch (_) {}
      };
      ws.onclose = () => {
        if (!alive) return;
        setWsStatus('disconnected');
        reconnectTimer.current = setTimeout(connect, 5000);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      alive = false;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);

  const getCount  = z => liveCounts.hasOwnProperty(z.id) ? liveCounts[z.id] : (z.current_personnel_count ?? 0);

  const topLevel  = hierarchyData?.top_level || [];
  const byParent  = hierarchyData?.by_parent || {};

  const totalPOB  = useMemo(() => {
    const allZones = [...topLevel, ...Object.values(byParent).flat()];
    const seen = new Set();
    return allZones.reduce((s, z) => {
      if (seen.has(z.id)) return s;
      seen.add(z.id);
      return s + getCount(z);
    }, 0);
  }, [topLevel, byParent, liveCounts]); // eslint-disable-line

  const handleSelectZone = (zone) => {
    if ((byParent[String(zone.id)] || []).length > 0) {
      setHistory(p => [...p, selectedZone]);
      setSelectedZone(zone);
    }
  };
  const handleBack = () => {
    setSelectedZone(history[history.length - 1] ?? null);
    setHistory(h => h.slice(0, -1));
  };

  if (isLoading) {
    return (
      <div style={{ textAlign:'center',padding:60 }}>
        <Spin size="large" />
        <div style={{ marginTop:12,color:'#6B7280',fontSize:13 }}>Loading POB data…</div>
      </div>
    );
  }

  const wsStyle = {
    live:         { color:'#52c41a', label:'Live' },
    connecting:   { color:'#faad14', label:'Connecting…' },
    disconnected: { color:'#8c8c8c', label:'Reconnecting…' },
  }[wsStatus];

  return (
    <div style={{ position:'relative', overflow:'hidden', borderRadius:20, padding:'14px 16px',
      background:'linear-gradient(180deg,#e7edf5 0%,#eef2f8 50%,#f3eef9 100%)' }}>
      {/* glassy colour blobs */}
      <div style={{ position:'absolute', width:360, height:360, top:-90, left:-50, borderRadius:'50%', filter:'blur(72px)', opacity:.5, background:'radial-gradient(circle,#22d3ee,transparent 70%)', pointerEvents:'none' }} />
      <div style={{ position:'absolute', width:420, height:420, top:120, right:-110, borderRadius:'50%', filter:'blur(72px)', opacity:.5, background:'radial-gradient(circle,#818cf8,transparent 70%)', pointerEvents:'none' }} />
      <div style={{ position:'absolute', width:340, height:340, bottom:-120, left:'35%', borderRadius:'50%', filter:'blur(72px)', opacity:.38, background:'radial-gradient(circle,#f472b6,transparent 70%)', pointerEvents:'none' }} />
      <div style={{ position:'relative', zIndex:1 }}>
      {/* Header bar */}
      <div style={{ display:'flex',justifyContent:'flex-end',alignItems:'center',gap:10,marginBottom:8 }}>
        <Tooltip title={`WebSocket: ${wsStyle.label}`}>
          <span style={{ display:'flex',alignItems:'center',gap:5,fontSize:11,color:wsStyle.color,fontWeight:600,background:`${wsStyle.color}18`,border:`1px solid ${wsStyle.color}40`,borderRadius:20,padding:'3px 10px' }}>
            <span style={{ width:7,height:7,borderRadius:'50%',background:wsStyle.color,display:'inline-block',animation:wsStatus==='live'?'pobWsPulse 2s infinite':'none' }} />
            {wsStyle.label}
          </span>
        </Tooltip>
        <ActivityFeedDrawer open={activityOpen} onClose={setActivityOpen} />
        <Button icon={<ReloadOutlined />} size="small" style={{ borderRadius:6 }}
          onClick={() => { refetch(); onRefreshDash?.(); }}>
          Refresh
        </Button>
      </div>

      {selectedZone ? (
        <ZoneDetailView
          zone={selectedZone}
          subZones={byParent[String(selectedZone.id)] || []}
          byParent={byParent}
          onBack={handleBack}
          onDrillDown={handleSelectZone}
          getCount={getCount}
          onViewPersonnel={setPersonnelDrawerZone}
        />
      ) : (
        <CountryOverview
          topLevelZones={topLevel}
          totalPOB={totalPOB}
          byParent={byParent}
          onSelectZone={handleSelectZone}
          getCount={getCount}
          onPositionChange={(id, position) => patchPositionM.mutate({ id, position })}
          onViewPersonnel={setPersonnelDrawerZone}
        />
      )}

      <ZonePersonnelDrawer
        zone={personnelDrawerZone}
        open={!!personnelDrawerZone}
        onClose={() => setPersonnelDrawerZone(null)}
      />

      </div>
      <style>{`
        @keyframes pobWsPulse {
          0%,100% { opacity:1; transform:scale(1); }
          50%      { opacity:0.4; transform:scale(1.5); }
        }
      `}</style>
    </div>
  );
};

export default POBDashboard;
