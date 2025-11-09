"""SKU映射服务"""
import logging
import random
import string
from datetime import datetime
from typing import Tuple
from sqlalchemy.orm import Session
from src.repositories.sku_mapping_repository import SkuMappingRepository

logger = logging.getLogger(__name__)

class SkuMappingService:
    """SKU映射服务"""
    
    MEOW_SKU_PREFIX = "meow"
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = SkuMappingRepository(db)
    
    def _generate_meow_sku(self) -> str:
        """
        生成新的内部SKU
        
        格式: meow{yymmdd}{5位随机字符}
        例如: meow2501087Jk9A
        """
        date_str = datetime.now().strftime("%y%m%d")
        char_pool = string.ascii_letters + string.digits
        random_str = ''.join(random.choices(char_pool, k=5))
        return f"{self.MEOW_SKU_PREFIX}{date_str}{random_str}"
    
    def sync_mappings_from_llm_details(self) -> Tuple[int, int]:
        """
        从LLM详情表同步SKU映射
        
        Returns:
            (总检查数量, 新创建数量)
        """
        logger.info("🚀 开始同步SKU映射...")
        
        try:
            # 1. 获取所有LLM详情中的SKU
            source_skus = self.repository.get_skus_from_llm_details()
            
            if not source_skus:
                logger.info("LLM详情表中没有SKU")
                return 0, 0
            
            total_checked = len(source_skus)
            logger.info(f"从LLM详情表中找到{total_checked}个SKU")
            
            # 2. 筛选未映射的SKU
            unmapped_skus = self.repository.filter_unmapped_skus(
                source_skus, 
                vendor_source="giga"
            )
            
            if not unmapped_skus:
                logger.info("所有SKU已存在映射")
                return total_checked, 0
            
            count_to_create = len(unmapped_skus)
            logger.info(f"发现{count_to_create}个SKU需要创建映射")
            
            # 3. 生成新映射
            new_mappings = []
            generated_skus = set()
            
            for vendor_sku in unmapped_skus:
                # 生成唯一的meow_sku（带重试）
                retry_count = 0
                while True:
                    new_meow_sku = self._generate_meow_sku()
                    
                    if new_meow_sku not in generated_skus:
                        generated_skus.add(new_meow_sku)
                        break
                    
                    retry_count += 1
                    if retry_count > 10:
                        logger.error(f"为SKU '{vendor_sku}' 生成唯一ID失败")
                        raise Exception("SKU生成失败")
                
                new_mappings.append({
                    "meow_sku": new_meow_sku,
                    "vendor_source": "giga",
                    "vendor_sku": vendor_sku
                })
            
            # 4. 批量插入
            logger.info(f"准备插入{len(new_mappings)}条新映射...")
            self.repository.bulk_insert_mappings(new_mappings)
            self.db.commit()
            
            logger.info("✅ SKU映射同步完成")
            return total_checked, count_to_create
            
        except Exception as e:
            logger.exception(f"SKU映射同步失败: {e}")
            self.db.rollback()
            return 0, 0
