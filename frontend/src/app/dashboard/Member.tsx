'use client';
import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import * as XLSX from 'xlsx';
import type { Member, Zone, Category } from '@/lib/types';
import { apiGetMembers, apiCreateMember, apiUpdateMember, apiDeleteMember, apiImportMembers } from '@/lib/backendApi';
import { Plus, Pencil, Trash2, X, Check, Search, Download, Upload, RefreshCw, ChevronLeft, ChevronRight, ArrowUpAZ, ArrowDownAZ } from 'lucide-react';

const PAGE_SIZE = 10;

const zoneLabels: Record<Zone | 'All', string> = {
  All: 'All Zones', 
  west: 'West Plant', 
  east: 'East Plant', 
  eastwest: 'East & West Plant',
};
const catColors: Record<Category, string> = {
  Employee: 'badge-blue', 
  Vendor: 'badge-navy', 
  Visitor: 'badge-yellow',
};

type ModalType = 'add' | 'edit' | null;

const EMPTY_MEMBER: Omit<Member, 'member_id' | 'position' | 'last_in' | 'last_out'> = {
  kpk_number: '', 
  name: '', 
  registered_plant: 'west',
  plate_1: '', 
  vehicle_type_1: 'Car',
  sim_exp: '', 
  stnk_exp_1: '', 
  category: 'Employee',
};

const inputStyle: React.CSSProperties = {
  width: '100%', 
  padding: '9px 12px', 
  borderRadius: 9, 
  border: '1px solid var(--border)',
  background: 'var(--bg)', 
  color: 'var(--ink)', 
  fontSize: 13, 
  outline: 'none',
  fontFamily: 'var(--font-body)', 
  boxSizing: 'border-box',
};

const labelStyle: React.CSSProperties = {
  fontSize: 11, 
  fontWeight: 700, 
  color: 'var(--muted)',
  textTransform: 'uppercase', 
  letterSpacing: '0.06em', 
  marginBottom: 6, 
  display: 'block',
};

export default function MembersPage() {
  const [data, setData] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [activeZone, setActiveZone] = useState<Zone | 'All'>('All');
  const [search, setSearch] = useState('');
  const [filterCat, setFilterCat] = useState<Category | 'All'>('All');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<number[]>([]);
  const [modal, setModal] = useState<ModalType>(null);
  const [editMember, setEditMember] = useState<Member | null>(null);
  const [form, setForm] = useState<Omit<Member, 'member_id' | 'position' | 'last_in' | 'last_out'>>(EMPTY_MEMBER);
  const [formError, setFormError] = useState('');
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchMembers = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const res = await apiGetMembers({
        zone: activeZone !== 'All' ? activeZone : undefined,
        category: filterCat !== 'All' ? filterCat : undefined,
        search: search || undefined,
        sort: sortDir,
        page,
        page_size: PAGE_SIZE,
      });
      setData(res.items);
      setTotal(res.total);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [activeZone, filterCat, search, sortDir, page]);

  useEffect(() => {
    void fetchMembers();
  }, [fetchMembers]);

  // Filters/search/sort invalidate the current page — jump back to page 1
  useEffect(() => {
    setPage(1);
  }, [activeZone, filterCat, search, sortDir]);

  const filtered = useMemo(() => data, [data]);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const openAdd = () => { 
    setForm(EMPTY_MEMBER); setFormError(''); setModal('add'); 
  };
  const openEdit = (m: Member) => {
    setEditMember(m);
    setForm({
      kpk_number: m.kpk_number, 
      name: m.name, 
      registered_plant: m.registered_plant,
      plate_1: m.plate_1, 
      plate_2: m.plate_2, 
      vehicle_type_1: m.vehicle_type_1,
      vehicle_type_2: m.vehicle_type_2, 
      sim_exp: m.sim_exp, 
      stnk_exp_1: m.stnk_exp_1,
      category: m.category,
    });
    setFormError(''); setModal('edit');
  };
  const closeModal = () => { setModal(null); setEditMember(null); setFormError(''); };

  const handleSave = async () => {
    if (!form.kpk_number || !form.name || !form.plate_1) {
      setFormError('KPK Number, Name, and Plate 1 are mandatory fields.');
      return;
    }
    setSaving(true); setFormError('');
    const payload = { ...form };
    (Object.keys(payload) as (keyof typeof payload)[]).forEach(k => {
      if (payload[k] === '') {
        delete payload[k]; 
      }
    });

    try {
      if (modal === 'add') {
        await apiCreateMember(payload as any); 
      } else if (modal === 'edit' && editMember) {
        await apiUpdateMember(editMember.member_id, payload as any);
      }
      closeModal();
      void fetchMembers();
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (ids: number[]) => {
    if (!window.confirm(`Hapus ${ids.length} member?`)) return;
    setSaving(true);
    try {
      await Promise.all(ids.map(id => apiDeleteMember(id)));
      setSelected([]);
      void fetchMembers();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const toggleSelect = (id: number) =>
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);
  const toggleAll = () =>
    setSelected(s => s.length === filtered.length ? [] : filtered.map(m => m.member_id));

  const exportExcel = () => {
    const rows = data.map(m => ({
      KPK: m.kpk_number,
      Name: m.name,
      Zone: m.registered_plant,
      Category: m.category,
      'Plate 1': m.plate_1,
      'Plate 2': m.plate_2 || '',
      'Type 1': m.vehicle_type_1,
      'Type 2': m.vehicle_type_2 || '',
      'SIM Exp': m.sim_exp,
      'STNK Exp': m.stnk_exp_1,
      Position: m.position,
    }));
    const ws = XLSX.utils.json_to_sheet(rows);
    ws['!cols'] = [
      { wch: 10 }, { wch: 20 }, { wch: 10 }, { wch: 10 }, { wch: 12 },
      { wch: 12 }, { wch: 10 }, { wch: 10 }, { wch: 12 }, { wch: 12 }, { wch: 8 },
    ];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Members');
    XLSX.writeFile(wb, `aips_members_${new Date().toISOString().slice(0, 10)}.xlsx`);
  };

  const IMPORT_KEY_MAP: Record<string, keyof Omit<Member, 'member_id' | 'position' | 'last_in' | 'last_out'>> = {
    kpk: 'kpk_number', kpknumber: 'kpk_number', kpkno: 'kpk_number',
    name: 'name', fullname: 'name',
    zone: 'registered_plant', plant: 'registered_plant', registeredplant: 'registered_plant',
    category: 'category',
    plate1: 'plate_1',
    plate2: 'plate_2',
    type1: 'vehicle_type_1', vehicletype1: 'vehicle_type_1',
    type2: 'vehicle_type_2', vehicletype2: 'vehicle_type_2',
    simexp: 'sim_exp',
    stnkexp: 'stnk_exp_1', stnkexp1: 'stnk_exp_1',
  };

  const normalizeKey = (k: string) => k.toLowerCase().replace(/[^a-z0-9]/g, '');

  const handleImportFile = async (file: File) => {
    setImporting(true); setError('');
    try {
      const buf = await file.arrayBuffer();
      const wb = XLSX.read(buf, { type: 'array', cellDates: false });
      const sheet = wb.Sheets[wb.SheetNames[0]];
      const raw = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, { defval: '' });

      const rows = raw.map(r => {
        const out: Record<string, string> = {};
        for (const [k, v] of Object.entries(r)) {
          const mapped = IMPORT_KEY_MAP[normalizeKey(k)];
          if (mapped) out[mapped] = String(v ?? '').trim();
        }
        return out;
      }).filter(r => r.kpk_number && r.name && r.plate_1);

      if (rows.length === 0) {
        setError('No valid rows found. Expecting columns like KPK, Name, Zone, Category, Plate 1, Plate 2, Type 1, Type 2, SIM Exp, STNK Exp.');
        return;
      }

      const payload = rows.map(r => ({
        kpk_number: r.kpk_number,
        name: r.name,
        registered_plant: (r.registered_plant || 'west') as Zone,
        category: (r.category || 'Employee') as Category,
        sim_exp: r.sim_exp || undefined,
        plate_1: r.plate_1,
        vehicle_type_1: r.vehicle_type_1 || 'Car',
        stnk_exp_1: r.stnk_exp_1 || undefined,
        plate_2: r.plate_2 || undefined,
        vehicle_type_2: r.vehicle_type_2 || undefined,
      }));

      const result = await apiImportMembers(payload);
      if (result.errors?.length) {
        setError(`Imported ${result.created} member(s). ${result.errors.length} row(s) skipped: ${result.errors.slice(0, 5).join('; ')}${result.errors.length > 5 ? '…' : ''}`);
      }
      void fetchMembers();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setImporting(false);
    }
  };

  const onImportInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void handleImportFile(file);
    e.target.value = '';
  };

  const FIELDS = [
    { label: 'KPK Number *', key: 'kpk_number', placeholder: 'KPK001', span: 1 },
    { label: 'Full Name *', key: 'name', placeholder: 'Full Name', span: 1 },
    { label: 'Plate 1 *', key: 'plate_1', placeholder: 'B 1234 ABC', span: 1 },
    { label: 'Plate 2', key: 'plate_2', placeholder: 'Opsional', span: 1 },
    { label: 'Vehicle Type 1', key: 'vehicle_type_1', placeholder: 'Car / Motorcycle', span: 1 },
    { label: 'Vehicle Type 2', key: 'vehicle_type_2', placeholder: 'Opsional', span: 1 },
    { label: 'SIM Expiry', key: 'sim_exp', placeholder: 'YYYY-MM-DD', span: 1 },
    { label: 'STNK Expiry', key: 'stnk_exp_1', placeholder: 'YYYY-MM-DD', span: 1 },
  ] as const;

  return (
    <>
      <div className="page-pad fadein">
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--ink)', letterSpacing: '-0.02em', marginBottom: 4 }}>Members</h1>
            <p style={{ fontSize: 13, color: 'var(--muted)' }}>
              Manage registered vehicle members · {loading ? '…' : `${total} total`}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => void fetchMembers()} className="btn-secondary" style={{ fontSize: 12 }} disabled={loading}>
              <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              style={{ display: 'none' }}
              onChange={onImportInputChange}
            />
            <button onClick={() => fileInputRef.current?.click()} className="btn-secondary" style={{ fontSize: 12 }} disabled={importing}>
              <Upload size={13} /> {importing ? 'Importing…' : 'Import Excel'}
            </button>
            <button onClick={exportExcel} className="btn-secondary" style={{ fontSize: 12 }}>
              <Download size={13} /> Export Excel
            </button>
            {selected.length > 0 && (
              <button onClick={() => void handleDelete(selected)} className="btn-secondary"
                style={{ fontSize: 12, color: 'var(--red)', borderColor: 'var(--red)' }} disabled={saving}>
                <Trash2 size={13} /> Delete ({selected.length})
              </button>
            )}
            <button onClick={openAdd} className="btn-primary" style={{ fontSize: 12 }}>
              <Plus size={13} /> Add Member
            </button>
          </div>
        </div>

        {error && (
          <div style={{ padding: '10px 14px', borderRadius: 9, background: 'var(--danger-bg)', border: '1px solid var(--red-mid)', color: 'var(--danger-text)', fontSize: 13, marginBottom: 16 }}>
            {error}
          </div>
        )}

        {/* Filters */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
            <Search size={13} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search name, KPK, or plate…"
              style={{ ...inputStyle, paddingLeft: 32 }} />
          </div>
          {(['All','west','east','eastwest'] as const).map(z => (
            <button key={z} onClick={() => setActiveZone(z)} style={{
              padding: '8px 14px', borderRadius: 8, border: '1px solid', fontSize: 12, fontWeight: 700, cursor: 'pointer',
              borderColor: activeZone === z ? 'var(--red)' : 'var(--border)',
              background:  activeZone === z ? 'var(--red)' : '#fff',
              color:       activeZone === z ? '#fff' : 'var(--text)',
            }}>{zoneLabels[z]}</button>
          ))}
          <select value={filterCat} onChange={e => setFilterCat(e.target.value as Category | 'All')}
            style={{ ...inputStyle, width: 'auto', padding: '8px 12px' }}>
            <option value="All">All Categories</option>
            <option value="Employee">Employee</option>
            <option value="Vendor">Vendor</option>
            <option value="Visitor">Visitor</option>
          </select>
        </div>

        {/* Table */}
        <div className="card" style={{ overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th><input type="checkbox" checked={selected.length === filtered.length && filtered.length > 0} onChange={toggleAll} /></th>
                  <th>KPK</th>
                  <th>
                    <button
                      onClick={() => setSortDir(d => d === 'asc' ? 'desc' : 'asc')}
                      style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'none', border: 'none', cursor: 'pointer', font: 'inherit', color: 'inherit', padding: 0 }}
                      title={sortDir === 'asc' ? 'Sorted A–Z (click for Z–A)' : 'Sorted Z–A (click for A–Z)'}
                    >
                      Name {sortDir === 'asc' ? <ArrowUpAZ size={12} /> : <ArrowDownAZ size={12} />}
                    </button>
                  </th>
                  <th>Zone</th><th>Cat.</th>
                  <th>Plate 1</th><th>Plate 2</th><th>Type</th>
                  <th>SIM Exp</th><th>STNK Exp</th><th>Status</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={12} style={{ textAlign: 'center', padding: 40, color: 'var(--muted)' }}>Memuat data…</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={12} style={{ textAlign: 'center', padding: 40, color: 'var(--muted)' }}>No members found.</td></tr>
                ) : filtered.map(m => (
                  <tr key={m.member_id} style={{ opacity: saving ? 0.6 : 1 }}>
                    <td><input type="checkbox" checked={selected.includes(m.member_id)} onChange={() => toggleSelect(m.member_id)} /></td>
                    <td><span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, color: 'var(--red)' }}>{m.kpk_number}</span></td>
                    <td style={{ fontWeight: 600 }}>{m.name}</td>
                    <td style={{ fontSize: 11 }}>{zoneLabels[m.registered_plant]}</td>
                    <td><span className={`badge ${catColors[m.category]}`} style={{ fontSize: 10 }}>{m.category.slice(0,3)}</span></td>
                    <td><span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{m.plate_1}</span></td>
                    <td><span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{m.plate_2 || '—'}</span></td>
                    <td style={{ fontSize: 12 }}>{m.vehicle_type_1}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{m.sim_exp}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{m.stnk_exp_1}</td>
                    <td>
                      <span style={{
                        fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 6,
                        background: m.position === 'IN' ? 'var(--green-bg)' : 'var(--bg)',
                        color: m.position === 'IN' ? 'var(--green-text)' : 'var(--muted)',
                        border: `1px solid ${m.position === 'IN' ? '#6EE7B7' : 'var(--border)'}`,
                      }}>{m.position}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button onClick={() => openEdit(m)} className="btn-secondary" style={{ padding: '4px 8px' }}><Pencil size={11} /></button>
                        <button onClick={() => void handleDelete([m.member_id])} className="btn-secondary" style={{ padding: '4px 8px', color: 'var(--red)' }}><Trash2 size={11} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>
              {loading ? 'Loading…' : total === 0 ? 'No members' : `Page ${page} of ${totalPages}`}
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn-secondary"
                style={{ padding: '6px 10px', display: 'flex', alignItems: 'center', gap: 4 }}
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={loading || page <= 1}
              >
                <ChevronLeft size={13} /> Prev
              </button>
              <button
                className="btn-secondary"
                style={{ padding: '6px 10px', display: 'flex', alignItems: 'center', gap: 4 }}
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={loading || page >= totalPages}
              >
                Next <ChevronRight size={13} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Modal Add / Edit */}
      {modal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', 
          zIndex: 1000, padding: '20px', 
        }}>
          <div style={{
            background: '#fff', borderRadius: 16, width: '100%', maxWidth: 580,
            boxShadow: '0 32px 80px rgba(0,0,0,.2)',
            display: 'flex', flexDirection: 'column',
            /* maxHeight: '90vh' TELAH DIHAPUS agar modal bisa terbuka penuh sesuai isi */
          }}>
            
            {/* Modal Header */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '20px 24px', borderBottom: '1px solid var(--border)',
              flexShrink: 0,
            }}>
              <h3 style={{ fontSize: 16, fontWeight: 800, color: 'var(--ink)', margin: 0 }}>
                {modal === 'add' ? '+ Add Member' : 'Edit Member'}
              </h3>
              <button onClick={closeModal} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)', padding: 4 }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '24px' }}>
              {formError && (
                <div style={{ padding: '10px 14px', borderRadius: 9, background: 'var(--danger-bg)', border: '1px solid var(--red-mid)', color: 'var(--danger-text)', fontSize: 13, marginBottom: 16 }}>
                  {formError}
                </div>
              )}

              {/* Section: Identity */}
              <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>Identity</p>
              <div className="grid-2" style={{ gap: 12, marginBottom: 20 }}>
                {FIELDS.slice(0, 2).map(f => (
                  <div key={f.key}>
                    <label style={labelStyle}>{f.label}</label>
                    <input style={inputStyle} value={(form as Record<string, string | undefined>)[f.key] || ''}
                      onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                      placeholder={f.placeholder} />
                  </div>
                ))}
              </div>

              {/* Section: Vehicle */}
              <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>Vehicle</p>
              <div className="grid-2" style={{ gap: 12, marginBottom: 20 }}>
                {FIELDS.slice(2, 6).map(f => (
                  <div key={f.key}>
                    <label style={labelStyle}>{f.label}</label>
                    <input style={inputStyle} value={(form as Record<string, string | undefined>)[f.key] || ''}
                      onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                      placeholder={f.placeholder} />
                  </div>
                ))}
              </div>

              {/* Section: Documents */}
              <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>Documents</p>
              <div className="grid-2" style={{ gap: 12, marginBottom: 20 }}>
                {FIELDS.slice(6, 8).map(f => (
                  <div key={f.key}>
                    <label style={labelStyle}>{f.label}</label>
                    <input style={inputStyle} type="date"
                      value={(form as Record<string, string | undefined>)[f.key] || ''}
                      onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))} />
                  </div>
                ))}
              </div>

              {/* Section: Assignment */}
              <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>Assignment</p>
              <div className="grid-2" style={{ gap: 12 }}>
                <div>
                  <label style={labelStyle}>Registered Plant</label>
                  <select value={form.registered_plant}
                    onChange={e => setForm(p => ({ ...p, registered_plant: e.target.value as Zone }))}
                    style={inputStyle}>
                    <option value="west">West Plant</option>
                    <option value="east">East Plant</option>
                    <option value="eastwest">East & West Plant</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Category</label>
                  <select value={form.category}
                    onChange={e => setForm(p => ({ ...p, category: e.target.value as Category }))}
                    style={inputStyle}>
                    <option value="Employee">Employee</option>
                    <option value="Vendor">Vendor</option>
                    <option value="Visitor">Visitor</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div style={{
              display: 'flex', gap: 10, justifyContent: 'flex-end',
              padding: '16px 24px', borderTop: '1px solid var(--border)',
              flexShrink: 0,
            }}>
              <button onClick={closeModal} className="btn-secondary" style={{ fontSize: 13 }}>Cancel</button>
              <button onClick={() => void handleSave()} className="btn-primary" style={{ fontSize: 13 }} disabled={saving}>
                <Check size={13} /> {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}