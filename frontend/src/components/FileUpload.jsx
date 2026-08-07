import { useState } from 'react'
import axios from 'axios'

const MAX_FILE_SIZE_MB = 10

function FileUpload({ onSuccess }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState(null)
  const [missingProducts, setMissingProducts] = useState(null)
  const [productInputs, setProductInputs] = useState([])
  const [savingProducts, setSavingProducts] = useState(false)

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files) {
      addFiles(Array.from(e.dataTransfer.files))
    }
  }

  const handleFileSelect = (e) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files))
    }
  }

  const addFiles = (newFiles) => {
    setError(null)
    const validFiles = []
    const errors = []

    for (const file of newFiles) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        errors.push(`"${file.name}" — รองรับเฉพาะไฟล์ PDF`)
        continue
      }
      if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        errors.push(`"${file.name}" — ขนาดเกิน ${MAX_FILE_SIZE_MB}MB`)
        continue
      }
      validFiles.push(file)
    }

    if (errors.length > 0) {
      setError(errors.join('\n'))
    }
    if (validFiles.length > 0) {
      setFiles(prev => [...prev, ...validFiles])
    }
  }

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const clearAll = () => {
    setFiles([])
    setError(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (files.length === 0) return

    setLoading(true)
    setUploadProgress(0)
    setError(null)

    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })

    try {
      const response = await axios.post('/api/v1/upload-multiple', formData, {
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setUploadProgress(percent)
        }
      })
      onSuccess(response.data)
    } catch (error) {
      console.error('Upload failed:', error)
      const errorData = error.response?.data?.detail
      
      // ตรวจสอบว่าเป็น error จาก Product table หรือไม่
      if (errorData && typeof errorData === 'object' && errorData.missing_products) {
        // แสดง modal สำหรับกรอกน้ำหนักสินค้า
        setMissingProducts(errorData)
        setProductInputs(errorData.missing_products.map(name => ({
          name: name,
          code: name.split(' - ')[0] || '',
          weight: '',
          unit: 'กล่อง'
        })))
      } else {
        const message = errorData || error.message || 'เกิดข้อผิดพลาดในการอัปโหลด'
        setError(message)
      }
    } finally {
      setLoading(false)
      setUploadProgress(0)
    }
  }

  const handleProductInputChange = (index, field, value) => {
    setProductInputs(prev => prev.map((item, i) => 
      i === index ? { ...item, [field]: value } : item
    ))
  }

  const handleSaveProducts = async () => {
    setSavingProducts(true)
    try {
      const token = localStorage.getItem('token')
      const productsToSave = productInputs.filter(p => p.weight && parseFloat(p.weight) > 0)
      
      if (productsToSave.length === 0) {
        setError('กรุณากรอกน้ำหนักอย่างน้อย 1 รายการ')
        return
      }

      await axios.post('/api/v1/products/bulk-create', {
        products: productsToSave.map(p => ({
          product_code: p.code,
          product_name: p.name,
          weight: parseFloat(p.weight),
          unit: p.unit
        }))
      }, {
        headers: { Authorization: `Bearer ${token}` }
      })

      // ปิด modal และลอง upload ใหม่
      setMissingProducts(null)
      setProductInputs([])
      setError(null)
      
      // ลอง upload ใหม่
      handleSubmit(new Event('submit'))
    } catch (err) {
      console.error('Save products failed:', err)
      setError('ไม่สามารถบันทึกสินค้าได้: ' + (err.response?.data?.detail || err.message))
    } finally {
      setSavingProducts(false)
    }
  }

  const handleSkipProducts = () => {
    setMissingProducts(null)
    setProductInputs([])
    setError('ข้ามการบันทึกสินค้า — กรุณาเพิ่มสินค้าในระบบก่อนอัปโหลดใหม่')
  }

  const handleCloseModal = () => {
    setMissingProducts(null)
    setProductInputs([])
  }

  return (
    <div className="upload-container">
      <div className="upload-header">
        <h2>📁 อัปโหลดไฟล์ OP</h2>
        <p>อัปโหลดไฟล์ PDF ได้หลายไฟล์พร้อมกัน (สูงสุด {MAX_FILE_SIZE_MB}MB ต่อไฟล์)</p>
      </div>

      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Modal สำหรับกรอกน้ำหนักสินค้าที่ไม่เจอ */}
      {missingProducts && (
        <div className="modal-overlay" style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'white',
            borderRadius: '12px',
            padding: '24px',
            maxWidth: '600px',
            width: '90%',
            maxHeight: '80vh',
            overflow: 'auto',
            boxShadow: '0 4px 20px rgba(0,0,0,0.15)'
          }}>
            <div className="modal-header" style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '20px',
              borderBottom: '1px solid #e5e7eb',
              paddingBottom: '12px'
            }}>
              <h3 style={{ margin: 0, color: '#1f2937' }}>⚠️ พบสินค้าที่ไม่มีในระบบ</h3>
              <button 
                onClick={handleCloseModal}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '24px',
                  cursor: 'pointer',
                  color: '#6b7280'
                }}
              >✕</button>
            </div>
            
            <div className="modal-body">
              <p style={{ marginBottom: '16px', color: '#4b5563' }}>
                พบสินค้า {missingProducts.missing_products.length} รายการที่ไม่มีในระบบ 
                กรุณากรอกน้ำหนักต่อหน่วย (kg) เพื่อบันทึกเข้าระบบ
              </p>
              
              <div className="product-input-list" style={{ marginBottom: '20px' }}>
                {productInputs.map((product, index) => (
                  <div key={index} style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr 100px 80px',
                    gap: '12px',
                    padding: '12px',
                    backgroundColor: '#f9fafb',
                    borderRadius: '8px',
                    marginBottom: '8px',
                    alignItems: 'center'
                  }}>
                    <div>
                      <label style={{ fontSize: '12px', color: '#6b7280', display: 'block', marginBottom: '4px' }}>
                        รหัสสินค้า
                      </label>
                      <input
                        type="text"
                        value={product.code}
                        onChange={(e) => handleProductInputChange(index, 'code', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '8px',
                          border: '1px solid #d1d5db',
                          borderRadius: '6px',
                          fontSize: '14px'
                        }}
                        placeholder="รหัสสินค้า"
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '12px', color: '#6b7280', display: 'block', marginBottom: '4px' }}>
                        ชื่อสินค้า
                      </label>
                      <input
                        type="text"
                        value={product.name}
                        onChange={(e) => handleProductInputChange(index, 'name', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '8px',
                          border: '1px solid #d1d5db',
                          borderRadius: '6px',
                          fontSize: '14px'
                        }}
                        placeholder="ชื่อสินค้า"
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '12px', color: '#6b7280', display: 'block', marginBottom: '4px' }}>
                        น้ำหนัก (kg)
                      </label>
                      <input
                        type="number"
                        value={product.weight}
                        onChange={(e) => handleProductInputChange(index, 'weight', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '8px',
                          border: '1px solid #d1d5db',
                          borderRadius: '6px',
                          fontSize: '14px'
                        }}
                        placeholder="0.0"
                        min="0"
                        step="0.1"
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '12px', color: '#6b7280', display: 'block', marginBottom: '4px' }}>
                        หน่วย
                      </label>
                      <select
                        value={product.unit}
                        onChange={(e) => handleProductInputChange(index, 'unit', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '8px',
                          border: '1px solid #d1d5db',
                          borderRadius: '6px',
                          fontSize: '14px'
                        }}
                      >
                        <option value="กล่อง">กล่อง</option>
                        <option value="ชิ้น">ชิ้น</option>
                        <option value="ถุง">ถุง</option>
                        <option value="แพ็ค">แพ็ค</option>
                        <option value="กิโลกรัม">กิโลกรัม</option>
                      </select>
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="modal-actions" style={{
                display: 'flex',
                gap: '12px',
                justifyContent: 'flex-end',
                borderTop: '1px solid #e5e7eb',
                paddingTop: '16px'
              }}>
                <button
                  onClick={handleSkipProducts}
                  style={{
                    padding: '10px 20px',
                    border: '1px solid #d1d5db',
                    borderRadius: '8px',
                    backgroundColor: 'white',
                    color: '#374151',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  ข้าม
                </button>
                <button
                  onClick={handleSaveProducts}
                  disabled={savingProducts}
                  style={{
                    padding: '10px 20px',
                    border: 'none',
                    borderRadius: '8px',
                    backgroundColor: '#3b82f6',
                    color: 'white',
                    cursor: savingProducts ? 'not-allowed' : 'pointer',
                    fontSize: '14px',
                    opacity: savingProducts ? 0.7 : 1
                  }}
                >
                  {savingProducts ? '⏳ กำลังบันทึก...' : '💾 บันทึกทั้งหมด'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div
          className={`drop-zone ${dragActive ? 'drag-active' : ''} ${files.length > 0 ? 'has-file' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input type="file" accept=".pdf" multiple onChange={handleFileSelect} id="file-input" className="file-input" />

          {files.length > 0 ? (
            <div className="file-list">
              <div className="file-list-header">
                <span className="file-count">📄 {files.length} ไฟล์</span>
                <button type="button" className="clear-all" onClick={clearAll}>ลบทั้งหมด</button>
              </div>
              <div className="file-items">
                {files.map((file, index) => (
                  <div key={index} className="file-item">
                    <span className="file-icon">📄</span>
                    <span className="file-name">{file.name}</span>
                    <span className="file-size">{(file.size / 1024).toFixed(1)} KB</span>
                    <button type="button" className="remove-file" onClick={() => removeFile(index)}>✕</button>
                  </div>
                ))}
              </div>
              <label htmlFor="file-input" className="add-more-inline">➕ เพิ่มไฟล์</label>
            </div>
          ) : (
            <label htmlFor="file-input" className="drop-label">
              <span className="drop-icon">📤</span>
              <span className="drop-text">ลากไฟล์มาที่นี่ หรือคลิกเพื่อเลือกไฟล์</span>
              <span className="drop-hint">รองรับไฟล์ PDF หลายไฟล์พร้อมกัน (สูงสุด {MAX_FILE_SIZE_MB}MB/ไฟล์)</span>
            </label>
          )}
        </div>

        {loading && (
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
            <span className="progress-text">{uploadProgress}%</span>
          </div>
        )}

        <div className="upload-action-buttons">
          <button
            type="submit"
            className={`upload-btn ${loading ? 'loading' : ''}`}
            disabled={files.length === 0 || loading}
          >
            {loading ? (
              <><span className="spinner"></span> กำลังอัปโหลด...</>
            ) : (
              `📄 อ่านไฟล์ ${files.length > 0 ? `(${files.length} ไฟล์)` : ''}`
            )}
          </button>
        </div>
      </form>

      <div className="upload-tips">
        <h4>💡 ขั้นตอนการทำงานของระบบ</h4>
        <ul>
          <li><strong>1. อ่านไฟล์ (Extract Data):</strong> ดึงชื่อลูกค้า ที่อยู่ และน้ำหนักสินค้าจากไฟล์ PDF</li>
          <li><strong>2. แปลงพิกัด (Geocoding):</strong> แปลงที่อยู่อิสระเป็นพิกัด Lat/Lng บนแผนที่</li>
          <li><strong>3. คำนวณเส้นทาง (Vehicle Routing Problem):</strong> ใช้ OR-Tools คำนวณจัดลำดับจุดจอดและคิวรถให้อัตโนมัติ</li>
        </ul>
      </div>
    </div>
  )
}

export default FileUpload
