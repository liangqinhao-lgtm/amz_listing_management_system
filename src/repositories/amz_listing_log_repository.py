"""
Amazon Listing Log Repository
数据仓库层，负责发品日志的管理
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
import json
from typing import List, Optional, Dict, Any
import uuid

logger = logging.getLogger(__name__)


class AmzListingLogRepository:
    """
    发品日志数据仓库
    
    职责：
    - 记录和查询发品日志
    - 管理父子SKU关系
    - 跟踪发品状态
    """
    
    def __init__(self, db: Session):
        """
        初始化Repository
        
        Args:
            db: SQLAlchemy Session实例
        """
        self.db = db
    
    def find_log_for_family(self, meow_sku_family: List[str]) -> Optional[Dict[str, Any]]:
        """
        查找变体家族的发品日志
        
        用于判断家族是否已经发过品。
        
        Args:
            meow_sku_family: 家族成员的meow_sku列表
            
        Returns:
            日志记录字典，包含：
            {
                'parent_sku': 父SKU,
                'status': 状态（GENERATED/LISTED）,
                'variation_theme': 变体主题
            }
            如果未找到返回None
        """
        if not meow_sku_family:
            return None
        
        query = text("""
            SELECT parent_sku, status, variation_theme
            FROM amz_listing_log
            WHERE meow_sku = ANY(:family)
            ORDER BY created_at DESC 
            LIMIT 1;
        """)
        
        try:
            result = self.db.execute(query, {"family": meow_sku_family}).mappings().first()
            
            if result:
                logger.debug(f"找到家族日志: parent={result['parent_sku']}, status={result['status']}")
                return dict(result)
            else:
                logger.debug(f"家族 {meow_sku_family[:2]}... 没有发品记录")
                return None
                
        except Exception as e:
            logger.error(f"❌ 查询家族日志失败: {e}", exc_info=True)
            raise
    
    def get_family_details_by_parent(self, parent_sku: str) -> List[Dict[str, Any]]:
        """
        根据父SKU获取家族详情
        
        用于增补变体场景，需要知道已有的子SKU和属性。
        
        Args:
            parent_sku: 父SKU
            
        Returns:
            子SKU列表，每个元素包含：
            {
                'meow_sku': 子SKU,
                'variation_attributes': 变体属性字典
            }
        """
        query = text("""
            SELECT meow_sku, variation_attributes
            FROM amz_listing_log
            WHERE parent_sku = :parent_sku;
        """)
        
        try:
            results = self.db.execute(query, {"parent_sku": parent_sku}).mappings().all()
            
            # 解析JSONB字段
            parsed_results = []
            for row in results:
                row_dict = dict(row)
                
                # 如果variation_attributes是字符串，解析为字典
                if isinstance(row_dict['variation_attributes'], str):
                    try:
                        row_dict['variation_attributes'] = json.loads(row_dict['variation_attributes'])
                    except json.JSONDecodeError:
                        row_dict['variation_attributes'] = {}
                
                parsed_results.append(row_dict)
            
            logger.debug(f"找到父SKU {parent_sku} 的 {len(parsed_results)} 个子SKU")
            return parsed_results
            
        except Exception as e:
            logger.error(f"❌ 查询家族详情失败: {e}", exc_info=True)
            raise
    
    def bulk_insert_log(self, log_data: List[Dict[str, Any]]):
        """
        批量插入或更新发品日志
        
        使用 ON CONFLICT 实现 UPSERT。
        
        Args:
            log_data: 日志数据列表，每个元素包含：
            {
                'meow_sku': SKU,
                'parent_sku': 父SKU（单品为None）,
                'variation_attributes': 变体属性字典,
                'listing_batch_id': 批次ID,
                'status': 状态,
                'variation_theme': 变体主题（可选）
            }
        """
        if not log_data:
            return
        
        # 转换字典为JSON字符串
        for item in log_data:
            if 'variation_attributes' in item and isinstance(item['variation_attributes'], dict):
                item['variation_attributes'] = json.dumps(item['variation_attributes'])
        
        query = text("""
            INSERT INTO amz_listing_log (
                meow_sku, 
                parent_sku, 
                variation_attributes,
                listing_batch_id, 
                status, 
                variation_theme
            )
            VALUES (
                :meow_sku, 
                :parent_sku, 
                :variation_attributes,
                :listing_batch_id, 
                :status, 
                :variation_theme
            )
            ON CONFLICT (meow_sku) DO UPDATE SET
                parent_sku = EXCLUDED.parent_sku,
                variation_attributes = EXCLUDED.variation_attributes,
                listing_batch_id = EXCLUDED.listing_batch_id,
                status = EXCLUDED.status,
                variation_theme = EXCLUDED.variation_theme,
                created_at = CURRENT_TIMESTAMP;
        """)
        
        try:
            self.db.execute(query, log_data)
            logger.info(f"✅ 批量插入/更新 {len(log_data)} 条发品日志")
            
        except Exception as e:
            logger.error(f"❌ 批量插入日志失败: {e}", exc_info=True)
            raise
    
    def bulk_update_status_to_listed(self) -> int:
        """
        批量更新发品状态
        
        将所有 GENERATED 状态的、且能在 amz_all_listing_report 中找到
        Active 或 Inactive 状态的记录，更新为 LISTED。
        
        用于定期同步发品状态。
        
        Returns:
            更新的记录数量
        """
        query = text("""
            UPDATE amz_listing_log
            SET status = 'LISTED'
            WHERE status = 'GENERATED'
              AND meow_sku IN (
                  SELECT "seller-sku"
                  FROM amz_all_listing_report
                  WHERE status IN ('Active', 'Inactive')
              );
        """)
        
        try:
            result = self.db.execute(query)
            updated_rows = result.rowcount
            
            logger.info(f"✅ 批量更新状态: {updated_rows} 条记录从 GENERATED → LISTED")
            return updated_rows
            
        except Exception as e:
            logger.error(f"❌ 批量更新状态失败: {e}", exc_info=True)
            self.db.rollback()
            return -1