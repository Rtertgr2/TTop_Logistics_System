import { useState } from "react"
import { useNavigate } from "react-router-dom"
import axios from "axios"
import { useData } from "@/context/DataContext"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { Upload, FileText, X, Loader2, AlertTriangle, Plus, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"

const MAX_FILE_SIZE_MB = 10

const PRODUCT_UNITS = ["กล่อง", "ชิ้น", "ถุง", "แพ็ค", "กิโลกรัม"]

function FileUpload({ onSuccess }) {
  const { setOrders } = useData()
  const navigate = useNavigate()
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
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
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
      if (!file.name.toLowerCase().endsWith(".pdf")) {
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
      setError(errors.join("\n"))
    }
    if (validFiles.length > 0) {
      setFiles((prev) => [...prev, ...validFiles])
    }
  }

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
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
    files.forEach((file) => {
      formData.append("files", file)
    })

    try {
      const response = await axios.post("/api/v1/upload-multiple", formData, {
        onUploadProgress: (progressEvent) => {
          const percent = progressEvent.total ? Math.round((progressEvent.loaded * 100) / progressEvent.total) : 0
          setUploadProgress(percent)
        },
      })
      const data = response.data
      // ตรวจสอบกรณีสินค้าไม่มีในระบบ (backend ตอบ 200 พร้อม errors.missing_products)
      const missingFromErrors = (data.errors || []).find((e) => e.missing_products && e.missing_products.length > 0)
      if (missingFromErrors) {
        setMissingProducts(missingFromErrors)
        setProductInputs(
          missingFromErrors.missing_products.map((name) => ({
            name: name,
            code: name.split(" - ")[0] || "",
            weight: "",
            unit: "กล่อง",
          }))
        )
        return  // หยุด here — รอผู้ใช้กรอกน้ำหนักใน Dialog
      }
      // กรณีอื่นที่ backend คืน errors (เช่น File processing failed)
      if (data.errors && data.errors.length > 0) {
        const msgs = data.errors.map((e) => `${e.filename || ""}: ${e.error || "error"}`).join("\n")
        setError(msgs)
        return
      }
      if (data.orders && data.orders.length > 0) {
        setOrders((prev) => [...prev, ...data.orders])
      }
      if (onSuccess) {
        onSuccess(data)
      } else {
        navigate("/orders")
      }
    } catch (error) {
      console.error("Upload failed:", error)
      const errorData = error.response?.data?.detail

      if (errorData && typeof errorData === "object" && errorData.missing_products) {
        setMissingProducts(errorData)
        setProductInputs(
          errorData.missing_products.map((name) => ({
            name: name,
            code: name.split(" - ")[0] || "",
            weight: "",
            unit: "กล่อง",
          }))
        )
      } else {
        const message = errorData || error.message || "เกิดข้อผิดพลาดในการอัปโหลด"
        setError(message)
      }
    } finally {
      setLoading(false)
      setUploadProgress(0)
    }
  }

  const handleProductInputChange = (index, field, value) => {
    setProductInputs((prev) =>
      prev.map((item, i) => (i === index ? { ...item, [field]: value } : item))
    )
  }

  const handleSaveProducts = async () => {
    setSavingProducts(true)
    try {
      const productsToSave = productInputs.filter((p) => p.weight && parseFloat(p.weight) > 0)

      if (productsToSave.length === 0) {
        setError("กรุณากรอกน้ำหนักอย่างน้อย 1 รายการ")
        return
      }

      await axios.post(
        "/api/v1/products/bulk-create",
        {
          products: productsToSave.map((p) => ({
            product_code: p.code,
            product_name: p.name,
            weight: parseFloat(p.weight),
            unit: p.unit,
          })),
        }
      )

      setMissingProducts(null)
      setProductInputs([])
      setError(null)

      handleSubmit(new Event("submit"))
    } catch (err) {
      console.error("Save products failed:", err)
      setError("ไม่สามารถบันทึกสินค้าได้: " + (err.response?.data?.detail || err.message))
    } finally {
      setSavingProducts(false)
    }
  }

  const handleSkipProducts = () => {
    setMissingProducts(null)
    setProductInputs([])
    setError("ข้ามการบันทึกสินค้า — กรุณาเพิ่มสินค้าในระบบก่อนอัปโหลดใหม่")
  }

  const handleCloseModal = () => {
    setMissingProducts(null)
    setProductInputs([])
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
              <Upload className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <CardTitle className="text-lg">อัปโหลดไฟล์ OP</CardTitle>
              <CardDescription>
                อัปโหลดไฟล์ PDF ได้หลายไฟล์พร้อมกัน (สูงสุด {MAX_FILE_SIZE_MB}MB ต่อไฟล์)
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>เกิดข้อผิดพลาด</AlertTitle>
              <AlertDescription className="whitespace-pre-line">{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div
              className={cn(
                "flex min-h-[180px] flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-colors",
                dragActive
                  ? "border-primary bg-primary/5"
                  : "border-muted-foreground/30 hover:border-primary/50",
                files.length > 0 && "justify-start"
              )}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                type="file"
                accept=".pdf"
                multiple
                onChange={handleFileSelect}
                id="file-input"
                className="hidden"
              />

              {files.length > 0 ? (
                <div className="w-full space-y-3">
                  <div className="flex items-center justify-between">
                    <Badge variant="secondary" className="gap-1">
                      <FileText className="h-3.5 w-3.5" />
                      {files.length} ไฟล์
                    </Badge>
                    <Button type="button" variant="ghost" size="sm" onClick={clearAll}>
                      <Trash2 className="h-4 w-4" />
                      ลบทั้งหมด
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {files.map((file, index) => (
                      <div
                        key={index}
                        className="flex items-center gap-3 rounded-md border bg-muted/30 p-2"
                      >
                        <FileText className="h-4 w-4 shrink-0 text-blue-600" />
                        <span className="min-w-0 flex-1 truncate text-sm font-medium">
                          {file.name}
                        </span>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {(file.size / 1024).toFixed(1)} KB
                        </span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => removeFile(index)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                  <label
                    htmlFor="file-input"
                    className="inline-flex cursor-pointer items-center gap-1 text-sm font-medium text-primary hover:underline"
                  >
                    <Plus className="h-4 w-4" />
                    เพิ่มไฟล์
                  </label>
                </div>
              ) : (
                <label htmlFor="file-input" className="flex cursor-pointer flex-col items-center gap-2">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-blue-50">
                    <Upload className="h-7 w-7 text-blue-600" />
                  </div>
                  <span className="text-sm font-semibold">ลากไฟล์มาที่นี่ หรือคลิกเพื่อเลือกไฟล์</span>
                  <span className="text-xs text-muted-foreground">
                    รองรับไฟล์ PDF หลายไฟล์พร้อมกัน (สูงสุด {MAX_FILE_SIZE_MB}MB/ไฟล์)
                  </span>
                </label>
              )}
            </div>

            {loading && (
              <div className="space-y-1.5">
                <Progress value={uploadProgress} />
                <p className="text-center text-xs text-muted-foreground">{uploadProgress}%</p>
              </div>
            )}

            <Button type="submit" className="w-full" disabled={files.length === 0 || loading}>
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  กำลังอัปโหลด...
                </>
              ) : (
                <>
                  <FileText className="h-4 w-4" />
                  {`อ่านไฟล์ ${files.length > 0 ? `(${files.length} ไฟล์)` : ""}`}
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">ขั้นตอนการทำงานของระบบ</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-2 text-sm text-muted-foreground">
            <li className="flex gap-2">
              <span className="font-semibold text-foreground">1. อ่านไฟล์ (Extract Data):</span>
              ดึงชื่อลูกค้า ที่อยู่ และน้ำหนักสินค้าจากไฟล์ PDF
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-foreground">2. แปลงพิกัด (Geocoding):</span>
              แปลงที่อยู่อิสระเป็นพิกัด Lat/Lng บนแผนที่
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-foreground">3. คำนวณเส้นทาง (Vehicle Routing Problem):</span>
              ใช้ OR-Tools คำนวณจัดลำดับจุดจอดและคิวรถให้อัตโนมัติ
            </li>
          </ol>
        </CardContent>
      </Card>

      <Dialog open={!!missingProducts} onOpenChange={(open) => !open && handleCloseModal()}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-700">
              <AlertTriangle className="h-5 w-5" />
              พบสินค้าที่ไม่มีในระบบ
            </DialogTitle>
            <DialogDescription>
              พบสินค้า {missingProducts?.missing_products?.length || 0} รายการที่ไม่มีในระบบ
              กรุณากรอกน้ำหนักต่อหน่วย (kg) เพื่อบันทึกเข้าระบบ
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[50vh] space-y-3 overflow-y-auto pr-1">
            {productInputs.map((product, index) => (
              <div
                key={index}
                className="grid grid-cols-1 gap-3 rounded-lg border bg-muted/30 p-3 sm:grid-cols-2 lg:grid-cols-4"
              >
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">รหัสสินค้า</Label>
                  <Input
                    type="text"
                    value={product.code}
                    onChange={(e) => handleProductInputChange(index, "code", e.target.value)}
                    placeholder="รหัสสินค้า"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">ชื่อสินค้า</Label>
                  <Input
                    type="text"
                    value={product.name}
                    onChange={(e) => handleProductInputChange(index, "name", e.target.value)}
                    placeholder="ชื่อสินค้า"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">น้ำหนัก (kg)</Label>
                  <Input
                    type="number"
                    value={product.weight}
                    onChange={(e) => handleProductInputChange(index, "weight", e.target.value)}
                    placeholder="0.0"
                    min="0"
                    step="0.1"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">หน่วย</Label>
                  <Select
                    value={product.unit}
                    onValueChange={(value) => handleProductInputChange(index, "unit", value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="หน่วย" />
                    </SelectTrigger>
                    <SelectContent>
                      {PRODUCT_UNITS.map((unit) => (
                        <SelectItem key={unit} value={unit}>
                          {unit}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            ))}
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button type="button" variant="outline" onClick={handleSkipProducts} disabled={savingProducts}>
              ข้าม
            </Button>
            <Button type="button" onClick={handleSaveProducts} disabled={savingProducts}>
              {savingProducts ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  กำลังบันทึก...
                </>
              ) : (
                "บันทึกทั้งหมด"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default FileUpload
