'use client';

import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@/lib/AuthContext';
import type { Zone } from '@/lib/types';
import {
  apiGetCalibrationSnapshot,
  apiGetCalibrationDefaults,
  apiGetCalibration,
  apiSaveCalibration,
  type CalibrationSlot,
} from '@/lib/backendApi';
import { Camera, Trash2, Save, RotateCcw, Loader2, CheckCircle2, Upload } from 'lucide-react';

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
      setError('Klik minimal 3 titik untuk membentuk area slot.');
      return;
    }
    if (!selectedSlotId) {
      setError('Pilih Slot ID terlebih dahulu.');
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
      setError('Belum ada slot yang dikalibrasi.');
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
        <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--ink)', marginBottom: 4 }}>Slot Calibration</h1>
        <p style={{ fontSize: 13, color: 'var(--muted)' }}>
          Klik titik-titik sudut area parkir langsung di atas gambar kamera untuk menetapkan lokasi tiap slot secara tetap.
          Ini menghilangkan "goyang"-nya identitas slot pada deteksi live, karena slot tidak lagi ditentukan dari urutan
          deteksi tiap frame, melainkan dari koordinat tetap ini.
        </p>
      </div>

      <div className="grid-canvas">
        {/* Canvas */}
        <div className="card" style={{ padding: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, gap: 8, flexWrap: 'wrap' }}>
            <select
              value={zone}
              onChange={e => setZone(e.target.value as Zone)}
              style={{ padding: '8px 12px', borderRadius: 9, border: '1px solid var(--border)', background: 'var(--bg)', fontSize: 13, fontWeight: 600 }}
            >
              {zoneOptions.map(z => <option key={z.value} value={z.value}>{z.label}</option>)}
            </select>
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
            <div style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 10, padding: '8px 12px', borderRadius: 8, background: 'var(--bg)', border: '1px solid var(--border)' }}>
              Foto diunggah manual ({imgSize.width}×{imgSize.height}px). Pastikan foto ini diambil dari sudut &amp; posisi kamera yang <b>persis sama</b> dengan feed live —
              kalau sudut/kroping berbeda, koordinat slot tidak akan pas dengan deteksi live nantinya.
            </div>
          )}

          {image ? (
            <canvas
              ref={canvasRef}
              onClick={handleCanvasClick}
              style={{ width: '100%', height: 'auto', borderRadius: 10, border: '1px solid var(--border)', cursor: 'crosshair' }}
            />
          ) : (
            <div style={{ padding: 60, textAlign: 'center', color: 'var(--muted)' }}>
              {loading ? 'Mengambil gambar dari kamera…' : 'Belum ada gambar. Klik Camera Snapshot atau Upload Photo.'}
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn-secondary" onClick={undoPoint} disabled={!currentPoints.length}>
              <RotateCcw size={14} /> Undo Titik
            </button>
            <button className="btn-secondary" onClick={clearCurrent} disabled={!currentPoints.length}>
              <Trash2 size={14} /> Bersihkan
            </button>
            <button className="btn-primary" onClick={finishSlot} disabled={currentPoints.length < 3}>
              Simpan Area Slot ({currentPoints.length} titik)
            </button>
          </div>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="card" style={{ padding: 18 }}>
            <div className="label" style={{ marginBottom: 10 }}>Slot yang sedang digambar</div>
            <select
              value={selectedSlotId}
              onChange={e => {
                setSelectedSlotId(e.target.value);
                const found = defaultSlots.find(s => s.id === e.target.value);
                if (found) setCategory(found.category as 'Employee' | 'Vendor' | 'Visitor');
              }}
              style={{ width: '100%', padding: '9px 12px', borderRadius: 9, border: '1px solid var(--border)', background: 'var(--bg)', fontSize: 13, marginBottom: 10 }}
            >
              {defaultSlots.map(s => (
                <option key={s.id} value={s.id}>
                  {s.id} {slots.some(x => x.id === s.id) ? '✓' : ''}
                </option>
              ))}
            </select>
            <select
              value={category}
              onChange={e => setCategory(e.target.value as 'Employee' | 'Vendor' | 'Visitor')}
              style={{ width: '100%', padding: '9px 12px', borderRadius: 9, border: '1px solid var(--border)', background: 'var(--bg)', fontSize: 13 }}
            >
              <option value="Employee">Employee</option>
              <option value="Vendor">Vendor</option>
              <option value="Visitor">Visitor</option>
            </select>
            <p style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 10 }}>
              Klik 3–4 titik sudut slot ini di gambar, lalu tekan "Simpan Area Slot".
            </p>
          </div>

          <div className="card" style={{ padding: 18 }}>
            <div className="label" style={{ marginBottom: 8 }}>
              Progress: {slots.length} / {defaultSlots.length} slot
            </div>
            <div style={{ maxHeight: 220, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
              {slots.map(s => (
                <div key={s.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, padding: '5px 8px', borderRadius: 7, background: 'var(--bg)' }}>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{s.id} · {s.category}</span>
                  <button onClick={() => removeSlot(s.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--danger-text)' }}>
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
              {!slots.length && <div style={{ fontSize: 12, color: 'var(--muted)' }}>Belum ada slot dikalibrasi.</div>}
            </div>
            {remaining.length > 0 && (
              <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8 }}>
                Sisa: {remaining.length} slot belum dikalibrasi.
              </p>
            )}
          </div>

          {error && <div className="card" style={{ padding: 12, fontSize: 12.5, color: 'var(--danger-text)' }}>{error}</div>}

          <button
            className="btn-primary"
            style={{ justifyContent: 'center', padding: '12px 0', display: 'flex', alignItems: 'center', gap: 6 }}
            onClick={handleSave}
            disabled={saving || !slots.length}
          >
            {saving ? <Loader2 size={15} style={{ animation: 'spin 0.8s linear infinite' }} /> : saved ? <CheckCircle2 size={15} /> : <Save size={15} />}
            {saving ? 'Menyimpan…' : saved ? 'Tersimpan' : 'Simpan Semua Kalibrasi'}
          </button>
        </div>
      </div>
    </div>
  );
}