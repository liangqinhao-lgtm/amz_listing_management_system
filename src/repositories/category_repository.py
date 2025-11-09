"""品类映射Repository"""
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class CategoryRepository:
    """品类映射数据仓库"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_sku_to_category_mapping(self, meow_skus: List[str]) -> List[Tuple[str, Optional[str]]]:
        """
        查询SKU对应的标准品类
        
        Args:
            meow_skus: meow_sku列表
            
        Returns:
            [(meow_sku, standard_category_name or None), ...]
        """
        query = text("""
            SELECT DISTINCT 
                m.meow_sku,
                scm.standard_category_name
            FROM meow_sku_map m
            JOIN giga_product_sync_records psr 
                ON m.vendor_sku = psr.giga_sku 
                AND m.vendor_source = 'giga'
            LEFT JOIN supplier_categories_map scm 
                ON LOWER(psr.category_code) = LOWER(scm.supplier_category_code)
                AND scm.supplier_platform = 'giga'
            WHERE m.meow_sku = ANY(:meow_sku_list)
        """)
        
        try:
            logger.info(f"查询 {len(meow_skus)} 个SKU的品类映射...")
            result = self.db.execute(query, {"meow_sku_list": meow_skus}).fetchall()
            logger.info("品类映射查询成功")
            return result
        except Exception as e:
            logger.error(f"品类映射查询失败: {e}")
            return []
