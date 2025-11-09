"""SKU映射Repository"""
import logging
from typing import Optional, List, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class SkuMappingRepository:
    """SKU映射数据仓库"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_by_vendor_sku(self, vendor_source: str, vendor_sku: str) -> Optional[str]:
        """
        根据供应商SKU查找内部SKU
        
        Args:
            vendor_source: 供应商来源 (如 'giga')
            vendor_sku: 供应商SKU
            
        Returns:
            内部meow_sku，不存在返回None
        """
        try:
            query = text("""
                SELECT meow_sku 
                FROM meow_sku_map
                WHERE vendor_source = :vendor_source 
                  AND vendor_sku = :vendor_sku
                LIMIT 1
            """)
            
            result = self.db.execute(
                query, 
                {"vendor_source": vendor_source, "vendor_sku": vendor_sku}
            ).scalar_one_or_none()
            
            return result
            
        except Exception as e:
            logger.error(f"查询SKU映射失败: {e}")
            return None
    
    def get_skus_from_llm_details(self) -> List[str]:
        """从LLM详情表获取所有SKU"""
        try:
            query = text("""
                SELECT DISTINCT sku_id 
                FROM ds_api_product_details 
                WHERE sku_id IS NOT NULL
            """)
            
            result = self.db.execute(query).scalars().all()
            return list(result)
            
        except Exception as e:
            logger.error(f"获取LLM详情SKU失败: {e}")
            return []
    
    def filter_unmapped_skus(self, vendor_skus: List[str], vendor_source: str) -> List[str]:
        """
        筛选未映射的SKU
        
        Args:
            vendor_skus: 供应商SKU列表
            vendor_source: 供应商来源
            
        Returns:
            未映射的SKU列表
        """
        try:
            query = text("""
                SELECT v.sku
                FROM (SELECT unnest(:vendor_sku_list) AS sku) AS v
                LEFT JOIN meow_sku_map m 
                  ON v.sku = m.vendor_sku 
                  AND m.vendor_source = :vendor_source
                WHERE m.vendor_sku IS NULL
            """)
            
            result = self.db.execute(
                query,
                {
                    "vendor_sku_list": vendor_skus,
                    "vendor_source": vendor_source
                }
            ).scalars().all()
            
            return list(result)
            
        except Exception as e:
            logger.error(f"筛选未映射SKU失败: {e}")
            return []
    
    def bulk_insert_mappings(self, mappings: List[Dict[str, str]]):
        """
        批量插入SKU映射
        
        Args:
            mappings: 映射列表，格式：[{'meow_sku': '...', 'vendor_source': '...', 'vendor_sku': '...'}, ...]
        """
        try:
            query = text("""
                INSERT INTO meow_sku_map (meow_sku, vendor_source, vendor_sku)
                VALUES (:meow_sku, :vendor_source, :vendor_sku)
            """)
            
            self.db.execute(query, mappings)
            logger.info(f"批量插入{len(mappings)}条映射")
            
        except Exception as e:
            logger.error(f"批量插入映射失败: {e}")
            raise
    
    def get_statistics(self) -> Dict[str, int]:
        """获取映射统计"""
        try:
            result = self.db.execute(
                text("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(DISTINCT vendor_source) as sources,
                        COUNT(DISTINCT vendor_sku) as unique_vendor_skus
                    FROM meow_sku_map
                """)
            ).fetchone()
            
            return {
                'total': result[0] or 0,
                'sources': result[1] or 0,
                'unique_vendor_skus': result[2] or 0
            }
        except Exception as e:
            logger.error(f"获取映射统计失败: {e}")
            return {'total': 0, 'sources': 0, 'unique_vendor_skus': 0}
