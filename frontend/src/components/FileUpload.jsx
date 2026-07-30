import { useState } from 'react'
import axios from 'axios'

const MAX_FILE_SIZE_MB = 10

function FileUpload({ onSuccess }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState(null)

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
      const response = await axios.post('/api/upload-multiple', formData, {
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setUploadProgress(percent)
        }
      })
      onSuccess(response.data)
    } catch (error) {
      console.error('Upload failed:', error)
      const message = error.response?.data?.detail || error.message || 'เกิดข้อผิดพลาดในการอัปโหลด'
      setError(message)
    } finally {
      setLoading(false)
      setUploadProgress(0)
    }
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
