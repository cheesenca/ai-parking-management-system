'use client';

import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import type { Zone } from '@/types';
import {
  apiGetCalibrationSnapshot,
  apiGetCalibrationDefaults,
  apiGetCalibration,
  apiSaveCalibration,
  type CalibrationSlot,
} from '@/lib/backendApi';
import { Camera, Trash2, Save, RotateCcw, Loader2, CheckCircle2, Upload, HelpCircle } from 'lucide-react';

const zoneOptions: { value: Zone; label: string }[] = [
  { value: 'west', label: 'West Plant' },
  { value: 'east', label: 'East Plant' },
];

export default function CalibrationPage() {
  const { user } = useAuth();
  const [zone, setZone] = useState<Zone>('west');
  const [image, setImage] = useState<string | null>(null);
  const [imgSize, setImgSize] = useState({ width: 0, height: 0 });
  const [defaultSlots, setDefaultSlots] = useState<{ id: string; category: string }[]>([]);
  const [slots, setSlots] = useState<CalibrationSlot[]>([]);
  const [currentPoints, setCurrentPoints] = useState<[number, number][]>([]);
  const [selectedSlotId, setSelectedSlotId] = useState('');
  const [category, setCategory] = useState<'Employee' | 'Vendor' | 'Visitor'>('Employee');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [source, setSource] = useState<'camera' | 'upload' | null>(null);
  const [showHelp, setShowHelp] = useState(false);

  const loadDefaultsOnly = async () => {
    setError(null);
    try {
      const defaults = await apiGetCalibrationDefaults(zone);
      setDefaultSlots(defaults.default_slots);
      setSlots(defaults.slots || []);
      if (defaults.default_slots.length) setSelectedSlotId(defaults.default_slots[0].id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load zone slot list');
    }
  };

  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setSaved(false);
    setCurrentPoints([]);
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      const probe = new window.Image();
      probe.onload = () => {
        setImage(dataUrl);
        setImgSize({ width: probe.naturalWidth, height: probe.naturalHeight });
        setSource('upload');
        loadDefaultsOnly();
      };
      probe.src = dataUrl;
    };
    reader.readAsDataURL(file);
    // allow re-selecting the same file later
    e.target.value = '';
  };

  const loadSnapshot = async () => {
    setLoading(true);
    setError(null);
    setSaved(false);
    setCurrentPoints([]);
    try {
      const snap = await apiGetCalibrationSnapshot(zone);
      setImage(`data:image/jpeg;base64,${snap.image}`);
      setImgSize({ width: snap.width, height: snap.height });
      setDefaultSlots(snap.default_slots);
      setSource('camera');
      if (snap.default_slots.length) setSelectedSlotId(snap.default_slots[0].id);

      const existing = await apiGetCalibration(zone);
      setSlots(existing.slots || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load camera snapshot');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setImage(null);
    setSource(null);
    setError(null);
    setSaved(false);
    setCurrentPoints([]);
    /* eslint-disable-next-line */
  }, [zone]);

  // Redraw canvas whenever image, existing slots, or in-progress points change
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !image || !imgSize.width) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      imgRef.current = img;
      canvas.width = imgSize.width;
      canvas.height = imgSize.height;
      ctx.drawImage(img, 0, 0);

      // Draw already-saved slot polygons
      slots.forEach(s => {
        ctx.beginPath();
        s.polygon.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
        ctx.closePath();
        ctx.fillStyle = 'rgba(34, 197, 94, 0.25)';
        ctx.fill();
        ctx.strokeStyle = '#22c55e';
        ctx.lineWidth = 2;
        ctx.stroke();
        const [cx, cy] = s.polygon[0];
        ctx.fillStyle = '#065f46';
        ctx.font = 'bold 13px monospace';
        ctx.fillText(s.id, cx + 4, cy - 4);
      });

      // Draw the polygon currently being clicked
      if (currentPoints.length) {
        ctx.beginPath();
        currentPoints.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
        ctx.strokeStyle = '#dc2626';
        ctx.lineWidth = 2;
        ctx.stroke();
        currentPoints.forEach(([x, y]) => {
          ctx.beginPath();
          ctx.arc(x, y, 4, 0, Math.PI * 2);
          ctx.fillStyle = '#dc2626';
          ctx.fill();
        });
      }
    };
    img.src = image;
  }, [image, imgSize, slots, currentPoints]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    setCurrentPoints(pts => [...pts, [x, y]]);
    setSaved(false);
  };

  const finishSlot = () => {
    if (currentPoints.length < 3) {
      setError('Click at least 3 points to form the slot area.');
      return;
    }
    if (!selectedSlotId) {
      setError('Please select a Slot ID first.');
      return;
    }
    setError(null);
    setSlots(prev => {
      const withoutDup = prev.filter(s => s.id !== selectedSlotId);
      return [...withoutDup, { id: selectedSlotId, category, polygon: currentPoints }];
    });
    setCurrentPoints([]);

    // Auto-advance to the next un-calibrated slot for faster workflow
    const done = new Set([...slots.map(s => s.id), selectedSlotId]);
    const next = defaultSlots.find(s => !done.has(s.id));
    if (next) {
      setSelectedSlotId(next.id);
      setCategory(next.category as 'Employee' | 'Vendor' | 'Visitor');
    }
  };

  const removeSlot = (id: string) => setSlots(prev => prev.filter(s => s.id !== id));
  const undoPoint = () => setCurrentPoints(pts => pts.slice(0, -1));
  const clearCurrent = () => setCurrentPoints([]);

  const handleSave = async () => {
    if (!slots.length) {
      setError('No slots have been calibrated yet.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const referenceImage = image?.includes(',') ? image.split(',')[1] : undefined;
      await apiSaveCalibration(zone, slots, referenceImage);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save calibration');
    } finally {
      setSaving(false);
    }
  };

  if (user && user.role !== 'Admin') {
    return <div style={{ padding: 32 }}>Only Admins can access slot calibration.</div>;
  }

  const remaining = defaultSlots.filter(s => !slots.some(x => x.id === s.id));

  return (
    <div className="page-pad fadein">
      <div style={{ marginBottom: 20 }}>
        <div className="cal-title-row">
          <h1 className="tr-title" style={{ marginBottom: 0 }}>Slot Calibration</h1>
          <div className="cal-help-wrap">
            <button
              type="button"
              className="cal-help-btn"
              onClick={() => setShowHelp(s => !s)}
              onBlur={() => setTimeout(() => setShowHelp(false), 150)}
              aria-label="How slot calibration works"
            >
              <HelpCircle size={15} />
            </button>
            {showHelp && (
              <div className="cal-help-popover">
                Click the corner points of each parking slot directly on the camera image to fix its location permanently.
                This eliminates identity &quot;jitter&quot; between slots in live detection, because slots are no longer determined
                by the detection order of each frame, but by these fixed coordinates.
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid-canvas">
        {/* Canvas */}
        <div className="card cal-canvas-card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="cal-toolbar">
            <div className="tr-zone-toggle cal-zone-toggle">
              {zoneOptions.map(z => (
                <button
                  key={z.value}
                  type="button"
                  className={`tr-zone-btn${zone === z.value ? ' active' : ''}`}
                  onClick={() => setZone(z.value)}
                >
                  {z.label}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn-secondary" onClick={loadSnapshot} disabled={loading}>
                <Camera size={14} /> {loading ? 'Loading…' : 'Camera Snapshot'}
              </button>
              <button className="btn-secondary" onClick={() => fileInputRef.current?.click()}>
                <Upload size={14} /> Upload Photo
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handlePhotoUpload}
                style={{ display: 'none' }}
              />
            </div>
          </div>

          {source === 'upload' && (
            <div className="cal-notice">
              Manually uploaded photo ({imgSize.width}×{imgSize.height}px). Make sure this photo was taken from the <b>exact same</b> camera
              angle &amp; position as the live feed — if the angle/cropping differs, the slot coordinates won't align with live detections.
            </div>
          )}

          {image ? (
            <canvas
              ref={canvasRef}
              onClick={handleCanvasClick}
              className="cal-canvas"
            />
          ) : (
            <div className="cal-empty" style={{ flex: 1 }}>
              {loading ? (
                <>
                  <Loader2 size={28} style={{ animation: 'spin 0.8s linear infinite' }} />
                  <span>Fetching image from camera…</span>
                </>
              ) : (
                <>
                  <Camera size={28} />
                  <span>No image yet</span>
                  <span className="cal-empty-hint">Click &quot;Camera Snapshot&quot; or &quot;Upload Photo&quot; to get started</span>
                </>
              )}
            </div>
          )}

          <div className="cal-point-actions">
            <button className="btn-secondary" onClick={undoPoint} disabled={!currentPoints.length}>
              <RotateCcw size={14} /> Undo Point
            </button>
            <button className="btn-secondary" onClick={clearCurrent} disabled={!currentPoints.length}>
              <Trash2 size={14} /> Clear
            </button>
            <button className="btn-primary" onClick={finishSlot} disabled={currentPoints.length < 3} style={{ marginLeft: 'auto' }}>
              Save Slot Area ({currentPoints.length} points)
            </button>
          </div>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="card cal-panel">
            <div className="cal-panel-title">Slot currently being drawn</div>
            <label className="cal-field-label">Slot ID</label>
            <select
              value={selectedSlotId}
              onChange={e => {
                setSelectedSlotId(e.target.value);
                const found = defaultSlots.find(s => s.id === e.target.value);
                if (found) setCategory(found.category as 'Employee' | 'Vendor' | 'Visitor');
              }}
              className="cal-select"
            >
              {defaultSlots.map(s => (
                <option key={s.id} value={s.id}>
                  {s.id} {slots.some(x => x.id === s.id) ? '✓ calibrated' : ''}
                </option>
              ))}
            </select>
            <label className="cal-field-label">Category</label>
            <select
              value={category}
              onChange={e => setCategory(e.target.value as 'Employee' | 'Vendor' | 'Visitor')}
              className="cal-select"
            >
              <option value="Employee">Employee</option>
              <option value="Vendor">Vendor</option>
              <option value="Visitor">Visitor</option>
            </select>
            <p className="cal-hint">
              Click 3–4 corner points of this slot on the image, then press &quot;Save Slot Area&quot;.
            </p>
          </div>

          <div className="card cal-panel">
            <div className="cal-progress-header">
              <span className="cal-panel-title" style={{ marginBottom: 0 }}>Progress</span>
              <span className="cal-progress-count">{slots.length} / {defaultSlots.length}</span>
            </div>
            <div className="cal-progress-track">
              <div className="cal-progress-fill" style={{ width: defaultSlots.length ? `${(slots.length / defaultSlots.length) * 100}%` : '0%' }} />
            </div>
            <div style={{ maxHeight: 220, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4, marginTop: 14 }}>
              {slots.map(s => (
                <div key={s.id} className="cal-slot-row">
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{s.id} · {s.category}</span>
                  <button onClick={() => removeSlot(s.id)} className="cal-slot-remove">
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
              {!slots.length && <div className="cal-empty-note">No slots calibrated yet.</div>}
            </div>
            {remaining.length > 0 && (
              <p className="cal-hint" style={{ marginTop: 10 }}>
                Remaining: {remaining.length} slot(s) not yet calibrated.
              </p>
            )}
          </div>

          {error && <div className="cal-error">{error}</div>}

          <button
            className="btn-primary"
            style={{ justifyContent: 'center', padding: '12px 0', display: 'flex', alignItems: 'center', gap: 6 }}
            onClick={handleSave}
            disabled={saving || !slots.length}
          >
            {saving ? <Loader2 size={15} style={{ animation: 'spin 0.8s linear infinite' }} /> : saved ? <CheckCircle2 size={15} /> : <Save size={15} />}
            {saving ? 'Saving…' : saved ? 'Saved' : 'Save All Calibration'}
          </button>
        </div>
      </div>
    </div>
  );
}