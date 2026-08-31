"""
CLI สำหรับโหลดสินค้าพร้อมน้ำหนักจาก CSV เข้า Product table

รูปแบบ CSV (backend/data/products_weight.csv):
    product_code,product_name,weight

ตัวอย่าง:
    python seed_products.py
    python seed_products.py --csv backend/data/products_weight.csv
"""

import argparse
import csv
import os
import sys

DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "data", "products_weight.csv")


def _init_db():
    from database.db import init_db

    init_db()


def cmd_seed(args):
    path = args.csv or DEFAULT_CSV
    if not os.path.exists(path):
        print(f"❌ ไม่พบไฟล์ CSV: {path}")
        sys.exit(1)

    from database.db import SessionLocal
    from database.models import Product as ProductModel

    _init_db()
    db = SessionLocal()
    created = 0
    updated = 0
    skipped = 0
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = (row.get("product_code") or "").strip()
                if not code:
                    skipped += 1
                    continue
                name = (row.get("product_name") or code).strip()
                try:
                    weight = float(row.get("weight") or 0)
                except ValueError:
                    weight = 0.0

                existing = (
                    db.query(ProductModel)
                    .filter(ProductModel.product_code == code)
                    .first()
                )
                if existing:
                    existing.product_name = name
                    existing.weight = weight
                    updated += 1
                else:
                    db.add(
                        ProductModel(
                            product_code=code,
                            product_name=name,
                            weight=weight,
                        )
                    )
                    created += 1
        db.commit()
        print(f"✅ Seed เสร็จ: สร้าง {created} / อัปเดต {updated} / ข้าม {skipped}")
    except Exception as e:
        db.rollback()
        print(f"❌ เกิดข้อผิดพลาด: {e}")
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed products from CSV")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="path to products CSV")
    args = parser.parse_args()
    cmd_seed(args)


if __name__ == "__main__":
    main()
