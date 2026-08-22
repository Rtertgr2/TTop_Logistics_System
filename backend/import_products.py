import openpyxl
from database.db import get_db, init_db
from database.models import Product
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def import_products_from_excel(file_path: str):
    """Import products from Excel file into database"""
    try:
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
        
        db = next(get_db())
        
        # สร้าง table ถ้ายังไม่มี
        from database.models import Base
        from database.db import engine
        Base.metadata.create_all(bind=engine, tables=[Product.__table__])
        
        imported = 0
        skipped = 0
        
        for row in ws.iter_rows(min_row=2, values_only=True):  # ข้าม header
            if not row[0]:  # ข้าม row ที่ไม่มีรหัสสินค้า
                continue
            
            product_code = str(row[0]).strip()
            product_name = str(row[2]).strip() if row[2] else ""
            try:
                weight = float(row[5]) if row[5] else 0
            except (ValueError, TypeError):
                weight = 0
            
            # ตรวจสอบว่ามีสินค้านี้อยู่แล้วหรือไม่
            existing = db.query(Product).filter(Product.product_code == product_code).first()
            if existing:
                skipped += 1
                continue
            
            # สร้างสินค้าใหม่
            product = Product(
                product_code=product_code,
                product_name=product_name,
                weight=weight
            )
            db.add(product)
            imported += 1
        
        db.commit()
        logger.info(f"Import completed: {imported} products imported, {skipped} skipped")
        
    except Exception as e:
        logger.error(f"Error importing products: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python import_products.py <excel_file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    import_products_from_excel(file_path)
