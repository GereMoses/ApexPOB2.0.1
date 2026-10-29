import { useState, useEffect, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, ZoomControl } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Input, Tooltip } from 'antd';
import { SearchOutlined, EnvironmentOutlined, FullscreenOutlined, FullscreenExitOutlined, TeamOutlined } from '@ant-design/icons';

/* ── Tile layers ───────────────────────────────────────────────────────────── */
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

/* ── Muster status colours ─────────────────────────────────────────────────── */
const musterColor = (inEvent, safeCount, missingCount, injuredCount) => {
  if (inEvent) {
    if (missingCount > 0) return '#ef4444';   // red — personnel unaccounted
    if (injuredCount > 0) return '#f97316';   // orange — all accounted, some injured
    if (safeCount > 0)    return '#22c55e';   // green — all safe
    return '#6b7280';                         // grey — no data yet
  }
  return '#3b82f6';                           // blue — not part of this event
};

/* ── Marker icon ───────────────────────────────────────────────────────────── */
const markerIcon = (zone, inEvent, isSelected, tileKey, safeCount, missingCount, injuredCount, liveCount = 0) => {
  const color  = musterColor(inEvent, safeCount, missingCount, injuredCount);
  const size   = isSelected ? 52 : inEvent ? 48 : 40;
  const isDark = tileKey === 'dark' || tileKey === 'satellite';
  const ring   = isSelected
    ? `0 0 0 3px ${color}88, 0 4px 20px rgba(0,0,0,0.55)`
    : `0 2px 10px rgba(0,0,0,0.4)`;

  const total = safeCount + missingCount + injuredCount;
  const displayLabel = inEvent ? String(total) : (liveCount > 0 ? String(liveCount) : '–');
  const fs = (inEvent ? total : liveCount) >= 100 ? 11 : 15;
  const label = zone.name.length > 22 ? zone.name.slice(0, 20) + '…' : zone.name;

  const pulseHtml = inEvent ? `
    <div style="
      position:absolute; top:50%; left:50%;
      width:${size + 16}px; height:${size + 16}px;
      margin-left:-${(size + 16) / 2}px; margin-top:-${(size + 16) / 2}px;
      border-radius:50%;
      border:2px solid ${color};
      opacity:0.55;
      animation:musterMapPulse 1.2s infinite;
      pointer-events:none;
    "></div>` : '';

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
        ">
          <span style="color:#fff;font-weight:900;font-size:${fs}px;line-height:1;
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
            text-shadow:0 1px 3px rgba(0,0,0,0.4);">${displayLabel}</span>
        </div>
        <div style="
          background:${isDark ? 'rgba(15,20,35,0.9)' : 'rgba(15,20,35,0.82)'};
          color:#fff;font-size:${isSelected ? 10 : 9}px;font-weight:700;
          padding:2px 6px;border-radius:3px;margin-top:4px;
          white-space:nowrap;display:inline-block;max-width:140px;
          overflow:hidden;text-overflow:ellipsis;
          border-bottom:2px solid ${color};letter-spacing:0.02em;
          font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        ">${label}</div>
      </div>`,
    className: '',
    iconSize:   [isSelected ? 150 : 120, isSelected ? 76 : 62],
    iconAnchor: [isSelected ? 75 : 60, isSelected ? 26 : 20],
    popupAnchor:[0, -32],
  });
};

/* ── Map controller ────────────────────────────────────────────────────────── */
const MapController = ({ focusZone, allZones }) => {
  const map = useMap();

  useEffect(() => {
    const size = map.getSize();
    const go = () => {
      try {
        if (focusZone?.latitude && focusZone?.longitude) {
          map.flyTo([focusZone.latitude, focusZone.longitude], 14, { duration: 1, easeLinearity: 0.4 });
        } else if (!focusZone && allZones.length > 0) {
          const coords = allZones
            .filter(z => z.latitude != null && z.longitude != null)
            .map(z => [parseFloat(z.latitude), parseFloat(z.longitude)])
            .filter(([a, b]) => !isNaN(a) && !isNaN(b));
          if (coords.length === 1) map.setView(coords[0], 16, { animate: false });
          else if (coords.length) map.fitBounds(coords, { padding: [60, 60], maxZoom: 17, animate: false });
        }
      } catch (_) {}
    };
    if (size && size.x > 0) go();
    else { map.once('resize', go); return () => map.off('resize', go); }
    // Re-fit when the zones arrive (they load after the map mounts).
  }, [focusZone, map, allZones.map(z => `${z.latitude},${z.longitude}`).join('|')]); // eslint-disable-line

  return null;
};

/* ── Zone popup ────────────────────────────────────────────────────────────── */
const ZonePopup = ({ zone, inEvent, safeCount, missingCount, injuredCount, logs, liveCount = 0 }) => {
  const color = musterColor(inEvent, safeCount, missingCount, injuredCount);
  const total = safeCount + missingCount + injuredCount;

  return (
    <div style={{ width: 220, fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" }}>
      <div style={{
        background: `linear-gradient(135deg, ${color}cc, ${color})`,
        margin: '-12px -12px 12px', padding: '12px 14px',
        borderRadius: '8px 8px 0 0',
      }}>
        <div style={{ fontWeight: 800, color: '#fff', fontSize: 14 }}>{zone.name}</div>
        {inEvent && (
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.8)', marginTop: 3, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff', display: 'inline-block', opacity: 0.9, animation: 'musterMapPulse 1s infinite' }} />
            ACTIVE MUSTER EVENT
          </div>
        )}
      </div>

      {inEvent ? (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginBottom: 10 }}>
            {[
              { label: 'Safe',    val: safeCount,    color: '#22c55e' },
              { label: 'Missing', val: missingCount, color: missingCount > 0 ? '#ef4444' : '#6b7280' },
              { label: 'Injured', val: injuredCount, color: injuredCount > 0 ? '#f97316' : '#6b7280' },
            ].map(s => (
              <div key={s.label} style={{ textAlign: 'center', padding: '6px 4px', background: '#f8fafc', borderRadius: 6 }}>
                <div style={{ fontSize: 22, fontWeight: 900, color: s.color, lineHeight: 1 }}>{s.val}</div>
                <div style={{ fontSize: 9, color: '#9ca3af', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>{s.label}</div>
              </div>
            ))}
          </div>
          {logs.length > 0 && (
            <div style={{ maxHeight: 120, overflowY: 'auto', borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
              {logs.slice(0, 8).map(p => {
                const sc = p.status === 1 ? '#22c55e' : p.status === 2 ? '#f97316' : '#ef4444';
                return (
                  <div key={p.emp_code} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '3px 0', borderBottom: '1px solid #f9f9f9' }}>
                    <span style={{ fontSize: 11, color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140 }}>
                      {p.emp_name || p.emp_code}
                    </span>
                    <span style={{ fontSize: 9, fontWeight: 800, color: sc, flexShrink: 0, marginLeft: 4 }}>
                      {p.status === 1 ? 'SAFE' : p.status === 2 ? 'INJ' : 'MISS'}
                    </span>
                  </div>
                );
              })}
              {logs.length > 8 && (
                <div style={{ fontSize: 10, color: '#9ca3af', paddingTop: 4, textAlign: 'center' }}>
                  +{logs.length - 8} more
                </div>
              )}
            </div>
          )}
        </>
      ) : (
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 40, fontWeight: 900, color: liveCount > 0 ? '#1890ff' : '#6b7280', lineHeight: 1, letterSpacing: -1 }}>{liveCount}</div>
          <div style={{ fontSize: 10, color: '#6b7280', fontWeight: 600, letterSpacing: '0.08em', marginTop: 2, marginBottom: 8 }}>
            OCCUPANCY{zone.capacity ? ` / ${zone.capacity}` : ''}
          </div>
        </div>
      )}

      {zone.latitude && zone.longitude && (
        <div style={{ borderTop: '1px solid #f3f4f6', marginTop: 8, paddingTop: 8 }}>
          <a
            href={`https://www.openstreetmap.org/?mlat=${zone.latitude}&mlon=${zone.longitude}#map=14/${zone.latitude}/${zone.longitude}`}
            target="_blank" rel="noopener noreferrer"
            style={{ fontSize: 11, color: '#0078D4', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <EnvironmentOutlined style={{ fontSize: 11 }} />
            {parseFloat(zone.latitude).toFixed(4)}°N, {parseFloat(zone.longitude).toFixed(4)}°E · Open Map ↗
          </a>
        </div>
      )}
    </div>
  );
};

/* ── Sidebar zone card ─────────────────────────────────────────────────────── */
const ZoneCard = ({ zone, inEvent, isSelected, onClick, safeCount, missingCount, injuredCount, liveCount = 0 }) => {
  const color = musterColor(inEvent, safeCount, missingCount, injuredCount);
  const total = safeCount + missingCount + injuredCount;
  const count = inEvent ? total : liveCount;

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '9px 10px', marginBottom: 2, borderRadius: 8,
        background: isSelected ? `${color}18` : 'transparent',
        borderTop: isSelected ? `1px solid ${color}50` : '1px solid transparent',
        borderRight: isSelected ? `1px solid ${color}50` : '1px solid transparent',
        borderBottom: isSelected ? `1px solid ${color}50` : '1px solid transparent',
        borderLeft: `3px solid ${color}`,
        cursor: 'pointer', transition: 'all 0.15s',
      }}
    >
      <div style={{
        width: 38, height: 38, borderRadius: 10, flexShrink: 0,
        background: `linear-gradient(135deg, ${color}cc, ${color})`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ color: '#fff', fontWeight: 900, fontSize: count >= 100 ? 11 : 14 }}>{count}</span>
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontWeight: isSelected ? 700 : 500, fontSize: 12.5,
          color: isSelected ? '#fff' : '#E2E8F0',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>{zone.name}</div>
        {inEvent && (
          <div style={{ fontSize: 10, color: '#64748B', marginTop: 2, display: 'flex', gap: 6 }}>
            {safeCount > 0    && <span style={{ color: '#22c55e', fontWeight: 700 }}>{safeCount} safe</span>}
            {missingCount > 0 && <span style={{ color: '#ef4444', fontWeight: 700 }}>{missingCount} miss</span>}
            {injuredCount > 0 && <span style={{ color: '#f97316', fontWeight: 700 }}>{injuredCount} inj</span>}
          </div>
        )}
      </div>

      {inEvent && (
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0, animation: 'musterMapPulse 1.2s infinite' }} />
      )}
    </div>
  );
};

/* ── Main MusteringLiveMap ─────────────────────────────────────────────────── */
const MusteringLiveMap = ({ zones, activeZoneId, allLogs, isEventActive, zoneLiveCounts = {} }) => {
  const [selectedId,    setSelectedId]    = useState(null);
  const [search,        setSearch]        = useState('');
  const [tileKey,       setTileKey]       = useState('light');
  const [isFullscreen,  setIsFullscreen]  = useState(false);
  const containerRef = useRef(null);

  // Auto-select the active zone on mount / when event changes
  useEffect(() => {
    setSelectedId(activeZoneId ?? null);
  }, [activeZoneId]);

  useEffect(() => {
    const onChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) containerRef.current?.requestFullscreen();
    else document.exitFullscreen();
  };

  // Global totals for the event summary chips
  const safeCount    = allLogs.filter(l => l.status === 1).length;
  const missingCount = allLogs.filter(l => l.status === 0).length;
  const injuredCount = allLogs.filter(l => l.status === 2).length;

  // Per-zone breakdown — match log's last_punch_area (zone name) to zone.name
  const zoneStats = useMemo(() => {
    const m = {};
    for (const z of zones) m[z.id] = { safe: 0, missing: 0, injured: 0, logs: [] };
    for (const l of allLogs) {
      const z = zones.find(z => z.name && l.last_punch_area && z.name === l.last_punch_area);
      if (z) {
        if (l.status === 1)      m[z.id].safe++;
        else if (l.status === 0) m[z.id].missing++;
        else                     m[z.id].injured++;
        m[z.id].logs.push(l);
      }
    }
    return m;
  }, [zones, allLogs]);

  const geoZones   = zones.filter(z => z.latitude != null && z.longitude != null);
  const noGeoCount = zones.length - geoZones.length;
  const tile       = TILE_LAYERS[tileKey];
  const isDark     = tileKey === 'dark' || tileKey === 'satellite';

  const filtered = geoZones.filter(z =>
    z.name.toLowerCase().includes(search.toLowerCase())
  );

  const selectedZone = geoZones.find(z => z.id === selectedId) ?? null;
  const focusZone    = selectedZone;

  if (geoZones.length === 0) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        height: '100%', background: '#0F1927', color: '#64748B',
      }}>
        <EnvironmentOutlined style={{ fontSize: 40, marginBottom: 16, color: '#334155' }} />
        <div style={{ fontSize: 14, fontWeight: 700, color: '#94a3b8', marginBottom: 6 }}>
          No GPS Coordinates Set
        </div>
        <div style={{ fontSize: 12, color: '#64748B', textAlign: 'center', maxWidth: 240 }}>
          {noGeoCount > 0
            ? `Add latitude & longitude to your ${noGeoCount} muster zone${noGeoCount > 1 ? 's' : ''} in the Zones tab to enable the live map`
            : 'No zones configured yet — add muster zones in the Zones tab'}
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{ display: 'flex', height: '100%', background: '#0F1927', position: 'relative' }}
    >
      {/* ── CSS animations ── */}
      <style>{`
        @keyframes musterMapPulse {
          0%   { transform: scale(1);   opacity: 0.6; }
          50%  { transform: scale(1.4); opacity: 0.2; }
          100% { transform: scale(1);   opacity: 0.6; }
        }
        .leaflet-popup-content-wrapper { border-radius: 10px !important; padding: 0 !important; overflow: hidden; }
        .leaflet-popup-content { margin: 12px !important; }
        .muster-map-container .leaflet-control-zoom { border: none !important; }
        .muster-map-container .leaflet-control-zoom a {
          background: rgba(15,25,39,0.88) !important;
          color: #94a3b8 !important;
          border: 1px solid rgba(255,255,255,0.08) !important;
        }
        .muster-map-container .leaflet-control-zoom a:hover {
          background: rgba(30,41,59,0.95) !important;
          color: #e2e8f0 !important;
        }
        .muster-map-container .leaflet-control-attribution {
          background: rgba(0,0,0,0.45) !important;
          color: rgba(255,255,255,0.35) !important;
          font-size: 9px !important;
        }
        .muster-map-container .leaflet-control-attribution a { color: rgba(255,255,255,0.45) !important; }
      `}</style>

      {/* ── Left sidebar ── */}
      <div style={{
        width: 230, flexShrink: 0,
        background: '#0F1927',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden', zIndex: 10,
      }}>
        {/* Sidebar header */}
        <div style={{ padding: '12px 10px 8px', flexShrink: 0 }}>
          <div style={{ fontWeight: 800, fontSize: 13, color: '#F1F5F9', marginBottom: 8, letterSpacing: 0.3 }}>
            Muster Zones
          </div>
          <Input
            prefix={<SearchOutlined style={{ color: '#475569', fontSize: 12 }} />}
            placeholder="Search zones..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.1)', color: '#94a3b8', fontSize: 12 }}
            size="small"
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 8, fontSize: 10.5, color: '#475569' }}>
            <span><span style={{ color: '#F1F5F9', fontWeight: 700 }}>{geoZones.length}</span> on map</span>
            {noGeoCount > 0 && <span style={{ color: '#64748B' }}>{noGeoCount} no GPS</span>}
          </div>
        </div>

        {/* Stats chips */}
        {isEventActive && allLogs.length > 0 && (
          <div style={{ padding: '0 10px 8px', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#22c55e', background: 'rgba(34,197,94,0.12)', borderRadius: 4, padding: '2px 7px' }}>
              {safeCount} SAFE
            </div>
            {missingCount > 0 && (
              <div style={{ fontSize: 10, fontWeight: 700, color: '#ef4444', background: 'rgba(239,68,68,0.12)', borderRadius: 4, padding: '2px 7px' }}>
                {missingCount} MISSING
              </div>
            )}
            {injuredCount > 0 && (
              <div style={{ fontSize: 10, fontWeight: 700, color: '#f97316', background: 'rgba(249,115,22,0.12)', borderRadius: 4, padding: '2px 7px' }}>
                {injuredCount} INJURED
              </div>
            )}
          </div>
        )}

        {/* Zone list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 6px' }}>
          {filtered.map(zone => {
            const zs = zoneStats[zone.id] ?? { safe: 0, missing: 0, injured: 0 };
            const inEvent = isEventActive && allLogs.length > 0 && (zs.safe + zs.missing + zs.injured > 0);
            const liveCount = zoneLiveCounts[zone.id] ?? zone.adms_occupancy ?? 0;
            return (
              <ZoneCard
                key={zone.id}
                zone={zone}
                inEvent={inEvent}
                isSelected={zone.id === selectedId}
                safeCount={zs.safe}
                missingCount={zs.missing}
                injuredCount={zs.injured}
                liveCount={liveCount}
                onClick={() => setSelectedId(prev => prev === zone.id ? null : zone.id)}
              />
            );
          })}
        </div>

        {/* Tile switcher */}
        <div style={{ padding: '8px 10px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {Object.entries(TILE_LAYERS).map(([k, t]) => (
            <button
              key={k}
              onClick={() => setTileKey(k)}
              style={{
                fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 4, cursor: 'pointer',
                border: tileKey === k ? '1px solid rgba(255,255,255,0.4)' : '1px solid rgba(255,255,255,0.1)',
                background: tileKey === k ? 'rgba(255,255,255,0.12)' : 'transparent',
                color: tileKey === k ? '#F1F5F9' : '#64748B',
                textTransform: 'uppercase', letterSpacing: 0.5,
              }}
            >{t.label}</button>
          ))}
        </div>
      </div>

      {/* ── Map ── */}
      <div style={{ flex: 1, position: 'relative' }}>
        <MapContainer
          className="muster-map-container"
          center={[0, 0]}
          zoom={2}
          zoomControl={false}
          style={{ height: '100%', width: '100%', background: isDark ? '#0f172a' : '#e8edf0' }}
          preferCanvas
        >
          <TileLayer key={tile.url} url={tile.url} attribution={tile.attribution} maxZoom={19} maxNativeZoom={tile.maxNativeZoom || 19} />
          <ZoomControl position="bottomright" />
          <MapController focusZone={focusZone} allZones={geoZones} />

          {geoZones.map(zone => {
            const isSelected = zone.id === selectedId;
            const zs = zoneStats[zone.id] ?? { safe: 0, missing: 0, injured: 0, logs: [] };
            const inEvent = isEventActive && allLogs.length > 0 && (zs.safe + zs.missing + zs.injured > 0);
            const liveCount = zoneLiveCounts[zone.id] ?? zone.adms_occupancy ?? 0;
            return (
              <Marker
                key={zone.id}
                position={[zone.latitude, zone.longitude]}
                icon={markerIcon(zone, inEvent, isSelected, tileKey, zs.safe, zs.missing, zs.injured, liveCount)}
                eventHandlers={{ click: () => setSelectedId(prev => prev === zone.id ? null : zone.id) }}
                zIndexOffset={inEvent ? 1000 : isSelected ? 500 : 0}
              >
                <Popup>
                  <ZonePopup
                    zone={zone}
                    inEvent={inEvent}
                    safeCount={zs.safe}
                    missingCount={zs.missing}
                    injuredCount={zs.injured}
                    liveCount={liveCount}
                    logs={zs.logs}
                  />
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>

        {/* Fullscreen button */}
        <Tooltip title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'} placement="left">
          <button
            onClick={toggleFullscreen}
            style={{
              position: 'absolute', top: 10, right: 10, zIndex: 1000,
              width: 32, height: 32, borderRadius: 6, cursor: 'pointer',
              background: 'rgba(15,25,39,0.88)', border: '1px solid rgba(255,255,255,0.12)',
              color: '#94a3b8', fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            {isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          </button>
        </Tooltip>

        {/* Active event badge */}
        {isEventActive && allLogs.length > 0 && (
          <div style={{
            position: 'absolute', top: 10, left: 10, zIndex: 1000,
            background: 'rgba(239,68,68,0.9)', color: 'white',
            borderRadius: 6, padding: '4px 10px', fontSize: 11, fontWeight: 700,
            display: 'flex', alignItems: 'center', gap: 6,
            backdropFilter: 'blur(4px)',
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff', display: 'inline-block', animation: 'musterMapPulse 1s infinite' }} />
            LIVE MUSTER
          </div>
        )}
      </div>
    </div>
  );
};

export default MusteringLiveMap;
