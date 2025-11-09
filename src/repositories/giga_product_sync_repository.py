"""Giga商品同步数据仓库"""
import logging
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class GigaProductSyncRepository:
    """Giga商品同步Repository"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def upsert_product(self, giga_sku: str, raw_data: Dict[str, Any]) -> bool:
        """插入或更新单个商品"""
        try:
            # 提取关键字段
            category_code = raw_data.get('categoryCode')
            is_oversize = raw_data.get('isOversize', False)
            
            # ✅ 修复：使用CAST语法代替::jsonb
            self.db.execute(
                text("""
                    INSERT INTO giga_product_sync_records 
                    (giga_sku, category_code, is_oversize, raw_data, sync_status, updated_at)
                    VALUES (:giga_sku, :category_code, :is_oversize, CAST(:raw_data AS jsonb), 'synced', CURRENT_TIMESTAMP)
                    ON CONFLICT (giga_sku) DO UPDATE SET
                        category_code = EXCLUDED.category_code,
                        is_oversize = EXCLUDED.is_oversize,
                        raw_data = EXCLUDED.raw_data,
                        sync_status = 'synced',
                        updated_at = CURRENT_TIMESTAMP
                """),
                {
                    'giga_sku': giga_sku,
                    'category_code': category_code,
                    'is_oversize': is_oversize,
                    'raw_data': json.dumps(raw_data, ensure_ascii=False)
                }
            )
            return True
            
        except Exception as e:
            logger.error(f"保存商品{giga_sku}失败: {e}")
            return False
    
    def batch_upsert_products(self, products: List[Dict[str, Any]]) -> int:
        """批量插入或更新商品"""
        success_count = 0
        
        for product in products:
            giga_sku = product.get('sku')
            if not giga_sku:
                logger.warning("商品数据缺少SKU，跳过")
                continue
                
            if self.upsert_product(giga_sku, product):
                success_count += 1
        
        return success_count
    
    def get_product_by_sku(self, giga_sku: str) -> Optional[Dict]:
        """根据SKU获取商品"""
        try:
            result = self.db.execute(
                text("""
                    SELECT giga_sku, category_code, is_oversize, raw_data, sync_status
                    FROM giga_product_sync_records
                    WHERE giga_sku = :giga_sku
                """),
                {'giga_sku': giga_sku}
            ).fetchone()
            
            if result:
                return {
                    'giga_sku': result[0],
                    'category_code': result[1],
                    'is_oversize': result[2],
                    'raw_data': result[3],
                    'sync_status': result[4]
                }
            return None
            
        except Exception as e:
            logger.error(f"查询商品{giga_sku}失败: {e}")
            return None
    
    def get_statistics(self) -> Dict[str, int]:
        """获取同步统计"""
        try:
            result = self.db.execute(
                text("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE sync_status = 'synced') as synced,
                        COUNT(*) FILTER (WHERE is_oversize = true) as oversize
                    FROM giga_product_sync_records
                """)
            ).fetchone()
            
            return {
                'total': result[0] or 0,
                'synced': result[1] or 0,
                'oversize': result[2] or 0
            }
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {'total': 0, 'synced': 0, 'oversize': 0}
    
    def get_all_skus(self) -> List[str]:
        """获取所有已同步的SKU"""
        try:
            result = self.db.execute(
                text("SELECT giga_sku FROM giga_product_sync_records ORDER BY id")
            ).fetchall()
            return [row[0] for row in result]
        except Exception as e:
            logger.error(f"获取SKU列表失败: {e}")
            return []
