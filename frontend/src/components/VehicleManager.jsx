import { useState, useEffect } from 'react'
import axios from 'axios'

function VehicleManager() {
  const [vehicles, setVehicles] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    fetchVehicles()
  }, [])

  const fetchVehicles = async () => {
    setLoading(true)
    try {
      const res = await axios.get('/api/v1/vehicles')
      const rawList = res.data.vehicles || []
      setVehicles(rawList)
    } catch (err) {
      console.error('Failed to load vehicles:', err)
      setMessage({ type: 'error', text: 'ไม่สามารถดึงข้อมูลรถขนส่งได้' })
    } finally {
      setLoading(false)
    }
  }

  const handleInputChange = (index, field, value) => {
    const updated = [...vehicles]
    updated[index][field] = value
    setVehicles(updated)
  }

  const handleAddVehicle = async () => {
    const maxId = vehicles.length > 0 ? Math.max(...vehicles.map(v => v.id || 0)) : 0
    const newId = maxId + 1
    const newVehicle = {
      id: newId,
      name: `รถคันที่ ${newId} (รถบรรทุก 3.5 ตัน)`,
      plate: `กข ${1000 + newId}`,
      capacity: 3500,
      driver: `พนักงานขับรถ ${newId}`,
      active: true
    }
    const updated = [...vehicles, newVehicle]
    setVehicles(updated)
    
    // Auto-save additions immediately
    try {
      const res = await axios.put('/api/v1/vehicles', updated)
      if (res.data && res.data.vehicles) {
        setVehicles(res.data.vehicles)
      }
      setMessage({ type: 'success', text: `✨ เพิ่ม "รถคันที่ ${newId}" ลงฐานข้อมูลเรียบร้อยแล้ว!` })
    } catch (err) {
      console.error('Auto-save failed:', err)
      setMessage({ type: 'error', text: `⚠️ เกิดข้อผิดพลาดในการบันทึกข้อมูลรถ: ${err.message}` })
    }
  }

  const handleDuplicateVehicle = async (index) => {
    const target = vehicles[index]
    const maxId = Math.max(...vehicles.map(v => v.id || 0))
    const duplicated = {
      ...target,
      id: maxId + 1,
      name: `${target.name || 'รถขนส่ง'} (สำเนา)`,
      plate: `${target.plate || 'กข 0000'}`,
      active: true
    }
    const copyList = [...vehicles]
    copyList.splice(index + 1, 0, duplicated)
    setVehicles(copyList)
    
    try {
      const res = await axios.put('/api/v1/vehicles', copyList)
      if (res.data && res.data.vehicles) {
        setVehicles(res.data.vehicles)
      }
      setMessage({ type: 'success', text: `📋 สำเนารถและบันทึกลงฐานข้อมูลเรียบร้อยแล้ว!` })
    } catch (err) {
      console.error('Auto-save failed:', err)
    }
  }

  const handleToggleActive = async (index) => {
    const updated = [...vehicles]
    updated[index].active = !updated[index].active
    setVehicles(updated)
    try {
      const res = await axios.put('/api/v1/vehicles', updated)
      if (res.data && res.data.vehicles) {
        setVehicles(res.data.vehicles)
      }
      setMessage({ type: 'info', text: `อัปเดตสถานะ "${updated[index].name}" เป็น ${updated[index].active ? 'เปิดใช้งาน' : 'ปิดใช้งาน'} ในฐานข้อมูลเรียบร้อยแล้ว` })
    } catch (err) {
      console.error('Failed to toggle vehicle state:', err)
    }
  }

  const handleDeleteVehicle = async (index) => {
    if (vehicles.length <= 1) {
      alert('⚠️ ระบบต้องมีรถขนส่งอย่างน้อย 1 คัน')
      return
    }

    const targetName = vehicles[index].name || `คันที่ ${index + 1}`

    const filtered = vehicles.filter((_, idx) => idx !== index)
    setVehicles(filtered)

    try {
      const res = await axios.put('/api/v1/vehicles', filtered)
      if (res.data && res.data.vehicles) {
        setVehicles(res.data.vehicles)
      }
      setMessage({ type: 'success', text: `🗑️ ลบ "${targetName}" ออกจากฐานข้อมูลเรียบร้อยแล้ว!` })
    } catch (err) {
      console.error('Failed to delete vehicle:', err)
      setMessage({ type: 'error', text: `⚠️ ไม่สามารถบันทึกการลบบนเซิร์ฟเวอร์ได้: ${err.message}` })
    }
  }

  const handleSave = async (e) => {
    if (e) e.preventDefault()
    setSaving(true)
    setMessage(null)
    try {
      await axios.put('/api/v1/vehicles', vehicles)
      setMessage({ type: 'success', text: '🎉 บันทึก Fleet รถขนส่งเรียบร้อยแล้ว!' })
    } catch (err) {
      console.error('Failed to save vehicles:', err)
      setMessage({ type: 'error', text: '⚠️ เกิดข้อผิดพลาดในการบันทึกข้อมูลรถ' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="vehicle-manager-container">
        <div className="loading-spinner">กำลังโหลดข้อมูลรถ...</div>
      </div>
    )
  }

  return (
    <div className="vehicle-manager-container">
      <div className="vehicle-manager-header">
        <div>
          <h2>🚛 จัดการข้อมูล Fleet รถขนส่ง ({vehicles.length} คัน)</h2>
          <p>เพิ่ม/ลบรถ ตั้งค่าชื่อคนขับ ทะเบียนรถ น้ำหนักบรรทุกสูงสุด โดยลำดับคันจะเรียงเป็น 1, 2, 3, 4... อัตโนมัติ</p>
        </div>
        <div className="header-action-group">
          <button
            type="button"
            className="btn-secondary"
            onClick={handleAddVehicle}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            ➕ เพิ่มรถคันใหม่
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleSave}
            disabled={saving}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            {saving ? '⏳ กำลังบันทึก...' : '💾 บันทึกการเปลี่ยนแปลง'}
          </button>
        </div>
      </div>

      {message && (
        <div className={`status-banner ${message.type}`}>
          {message.text}
        </div>
      )}

      {vehicles.length === 0 && (
        <div className="empty-state" style={{ padding: '24px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '8px', marginBottom: '16px' }}>
          ยังไม่มีข้อมูลรถ — กรอกข้อมูลด้านล่างแล้วกด "บันทึก" เพื่อเพิ่มรถ
        </div>
      )}

      <div className="vehicles-grid">
        {vehicles.map((v, idx) => (
          <div key={v.id || idx} className={`vehicle-edit-card ${v.active !== false ? 'active' : 'disabled'}`}>
            <div className="vehicle-card-top">
              <div className="vehicle-id-badge-group">
                <span className="vehicle-id-badge">คันที่ {idx + 1}</span>
                <span className={`status-dot ${v.active !== false ? 'online' : 'offline'}`}></span>
              </div>
              <div className="vehicle-card-actions" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button
                  type="button"
                  onClick={() => handleToggleActive(idx)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    border: 'none',
                    background: v.active !== false ? '#ecfdf5' : '#f1f5f9',
                    color: v.active !== false ? '#047857' : '#64748b',
                    fontWeight: 700,
                    fontSize: '12px',
                    cursor: 'pointer'
                  }}
                  title="คลิกเพื่อเปิดหรือปิดใช้งานรถคันนี้"
                >
                  {v.active !== false ? '🟢 เปิดใช้งานอยู่' : '🔴 ปิดใช้งานอยู่'}
                </button>
                <button
                  type="button"
                  onClick={() => handleDuplicateVehicle(idx)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: '8px',
                    border: '1px solid #cbd5e1',
                    background: 'white',
                    color: '#334155',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                  title="คัดลอกรถคันนี้"
                >
                  📋 สำเนา
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteVehicle(idx)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#fee2e2',
                    color: '#ef4444',
                    fontWeight: 700,
                    fontSize: '12px',
                    cursor: 'pointer'
                  }}
                  title="ลบรถคันนี้ออกจากระบบ"
                >
                  🗑️ ลบรถ
                </button>
              </div>
            </div>

            <div className="form-group">
              <label>ชื่อเรียก / ชนิดรถ:</label>
              <input
                type="text"
                value={v.name || ''}
                onChange={(e) => handleInputChange(idx, 'name', e.target.value)}
                placeholder="เช่น รถใหญ่ 3.75 ตัน"
              />
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label>ทะเบียนรถ:</label>
                <input
                  type="text"
                  value={v.plate || ''}
                  onChange={(e) => handleInputChange(idx, 'plate', e.target.value)}
                  placeholder="เช่น กข 1234"
                />
              </div>
              <div className="form-group">
                <label>พนักงานขับรถ:</label>
                <input
                  type="text"
                  value={v.driver || ''}
                  onChange={(e) => handleInputChange(idx, 'driver', e.target.value)}
                  placeholder="เช่น สมชาย"
                />
              </div>
            </div>

            <div className="form-group">
              <label>LINE User ID (สำหรับส่งลิงค์แมพเข้า LINE):</label>
              <input
                type="text"
                value={v.line_user_id || ''}
                onChange={(e) => handleInputChange(idx, 'line_user_id', e.target.value)}
                placeholder="เช่น U4a5b6c7d8... (คัดลอกจาก LINE Developers)"
              />
              <small className="help-text">
                คนขับต้อง add LINE OA นี้เป็นเพื่อนก่อน จึงจะรับข้อความได้
              </small>
            </div>

            <div className="form-group">
              <label>น้ำหนักบรรทุกสูงสุด (กิโลกรัม / kg):</label>
              <input
                type="number"
                min="0"
                value={v.capacity === '' || v.capacity == null ? '' : v.capacity}
                onChange={(e) => handleInputChange(idx, 'capacity', e.target.value === '' ? '' : parseFloat(e.target.value))}
                placeholder="3750"
              />
              <small className="help-text">
                = {(((v.capacity === '' ? 0 : v.capacity) || 0) / 1000).toFixed(2)} ตัน
              </small>
            </div>

            <div className="form-grid-3">
              <div className="form-group">
                <label>ปริมาตรสูงสุด (ลบ.ม. / CBM):</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={v.max_volume_cbm === '' || v.max_volume_cbm == null ? '' : v.max_volume_cbm}
                  onChange={(e) => handleInputChange(idx, 'max_volume_cbm', e.target.value === '' ? '' : parseFloat(e.target.value))}
                  placeholder="0"
                />
                <small className="help-text">
                  0 = ไม่จำกัด
                </small>
              </div>
              <div className="form-group">
                <label>จำนวนกล่องสูงสุด:</label>
                <input
                  type="number"
                  min="0"
                  value={v.max_boxes === '' || v.max_boxes == null ? '' : v.max_boxes}
                  onChange={(e) => handleInputChange(idx, 'max_boxes', e.target.value === '' ? '' : parseInt(e.target.value))}
                  placeholder="0"
                />
                <small className="help-text">
                  0 = ไม่จำกัด
                </small>
              </div>
              <div className="form-group">
                <label>จำนวนจุดส่งสูงสุด:</label>
                <input
                  type="number"
                  min="0"
                  value={v.max_stops === '' || v.max_stops == null ? '' : v.max_stops}
                  onChange={(e) => handleInputChange(idx, 'max_stops', e.target.value === '' ? '' : parseInt(e.target.value))}
                  placeholder="0"
                />
                <small className="help-text">
                  0 = ไม่จำกัด
                </small>
              </div>
            </div>
          </div>
        ))}

        {/* Add New Vehicle Card inside grid */}
        <div className="add-vehicle-dashed-card" onClick={handleAddVehicle}>
          <div className="add-vehicle-icon">➕</div>
          <div className="add-vehicle-title">เพิ่มรถขนส่งคันใหม่</div>
          <div className="add-vehicle-desc">คลิกเพื่อเพิ่มรถบรรทุกใหม่เข้าสู่ Fleet จัดส่ง</div>
        </div>
      </div>
    </div>
  )
}

export default VehicleManager
