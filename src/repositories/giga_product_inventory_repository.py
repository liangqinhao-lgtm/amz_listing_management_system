"""Giga商品库存Repository"""
import logging
import json
import csv
from io import StringIO
from typing import List, Dict, Tuple
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class GigaProductInventoryRepository:
    """Giga商品库存数据仓库"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_all_skus(self) -> List[str]:
        """获取所有Giga商品SKU"""
        try:
            query = text("""
                SELECT DISTINCT giga_sku 
                FROM giga_product_sync_records 
                WHERE giga_sku IS NOT NULL
                ORDER BY giga_sku
            """)
            
            result = self.db.execute(query).fetchall()
            skus = [row[0] for row in result]
            
            logger.info(f"获取到{len(skus)}个SKU")
            return skus
            
        except Exception as e:
            logger.error(f"获取SKU列表失败: {e}")
            return []
    
    def bulk_upsert_inventory(self, inventory_data: List[Dict]) -> Tuple[int, int]:
        """
        批量更新库存（使用PostgreSQL COPY命令高性能导入）
        
        Returns:
            (处理数量, 成功数量)
        """
        if not inventory_data:
            return 0, 0
        
        try:
            # 1. 构建内存CSV流
            csv_data = StringIO()
            writer = csv.writer(csv_data)
            
            for item in inventory_data:
                writer.writerow([
                    item["giga_sku"],
                    item["quantity"],
                    item["buyer_qty"],
                    item["buyer_partner_qty"],
                    item["seller_qty"],
                    item["buyer_distribution"],
                    item["seller_distribution"],
                    item["next_arrival_date"],
                    item["next_arrival_date_end"],
                    item["next_arrival_qty"],
                    item["next_arrival_qty_max"],
                    item["last_updated"]
                ])
            
            csv_data.seek(0)
            
            # 2. 使用原生COPY命令导入
            connection = self.db.connection().connection
            with connection.cursor() as cursor:
                # 创建临时表
                cursor.execute("""
                    CREATE TEMP TABLE tmp_inventory (
                        LIKE giga_inventory
                    ) ON COMMIT DROP
                """)
                
                # 从内存流COPY到临时表
                cursor.copy_expert(
                    sql="COPY tmp_inventory FROM STDIN WITH CSV",
                    file=csv_data
                )
                
                # 执行UPSERT
                cursor.execute("""
                    INSERT INTO giga_inventory
                    SELECT * FROM tmp_inventory
                    ON CONFLICT (giga_sku) DO UPDATE SET
                        quantity = EXCLUDED.quantity,
                        buyer_qty = EXCLUDED.buyer_qty,
                        buyer_partner_qty = EXCLUDED.buyer_partner_qty,
                        seller_qty = EXCLUDED.seller_qty,
                        buyer_distribution = EXCLUDED.buyer_distribution,
                        seller_distribution = EXCLUDED.seller_distribution,
                        next_arrival_date = EXCLUDED.next_arrival_date,
                        next_arrival_date_end = EXCLUDED.next_arrival_date_end,
                        next_arrival_qty = EXCLUDED.next_arrival_qty,
                        next_arrival_qty_max = EXCLUDED.next_arrival_qty_max,
                        last_updated = EXCLUDED.last_updated
                """)
            
            self.db.commit()
            
            processed = len(inventory_data)
            logger.info(f"批量更新成功: {processed}条")
            return processed, processed
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"批量更新库存失败: {e}")
            return len(inventory_data), 0
    
    def parse_inventory_item(self, item: Dict) -> Dict:
        """解析单个库存项"""
        try:
            sku = item.get("sku") or "UNKNOWN_SKU"
            quantity = item.get("quantity", 0)
            qty_detail = item.get("qtyDetail", {})
            
            buyer_qty = qty_detail.get("buyerQty", 0)
            buyer_partner_qty = qty_detail.get("buyerPartnerQty", 0)
            seller_qty = qty_detail.get("sellerQty", 0)
            
            buyer_distribution = qty_detail.get("buyerQtyDistribution", [])
            seller_distribution = qty_detail.get("sellerQtyDistribution", [])
            
            # 特殊处理：seller_qty为0时清空distribution
            if seller_qty == 0 and seller_distribution:
                seller_distribution = []
            
            next_arrival = item.get("nextArrival") or {}
            
            return {
                "giga_sku": sku,
                "quantity": quantity,
                "buyer_qty": buyer_qty,
                "buyer_partner_qty": buyer_partner_qty,
                "seller_qty": seller_qty,
                "buyer_distribution": json.dumps(buyer_distribution),
                "seller_distribution": json.dumps(seller_distribution),
                "next_arrival_date": next_arrival.get("nextArrivalDate", "1970-01-01"),
                "next_arrival_date_end": next_arrival.get("nextArrivalDateEnd", "1970-01-01"),
                "next_arrival_qty": next_arrival.get("nextArrivalQty", 0),
                "next_arrival_qty_max": next_arrival.get("nextArrivalQtyMax", 0),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            logger.error(f"解析库存项失败 (SKU={item.get('sku', 'UNKNOWN')}): {e}")
            raise
    
    def get_statistics(self) -> Dict[str, int]:
        """获取库存统计"""
        try:
            result = self.db.execute(
                text("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE quantity > 0) as in_stock,
                        SUM(quantity) as total_quantity
                    FROM giga_inventory
                """)
            ).fetchone()
            
            return {
                'total_skus': result[0] or 0,
                'in_stock_skus': result[1] or 0,
                'total_quantity': int(result[2] or 0)
            }
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {'total_skus': 0, 'in_stock_skus': 0, 'total_quantity': 0}
