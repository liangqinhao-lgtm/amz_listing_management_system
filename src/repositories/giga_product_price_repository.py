"""Giga商品价格Repository（过滤无效价格版）"""
import logging
import json
import csv
from io import StringIO
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class GigaProductPriceRepository:
    """Giga商品价格数据仓库"""
    
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
    
    def batch_upsert_prices(self, prices: List[Dict]) -> Tuple[int, int]:
        """
        批量插入/更新价格（过滤无效价格版）
        
        Returns:
            (成功数量, 失败数量)
        """
        if not prices:
            return 0, 0
        
        # 1. 过滤：只保留有效价格的记录
        valid_prices = []
        invalid_count = 0
        
        for item in prices:
            # 过滤条件：必须有价格 OR 必须可用
            price = item.get("price")
            sku_available = item.get("skuAvailable", False)
            
            if price is not None or sku_available:
                valid_prices.append(item)
            else:
                invalid_count += 1
                logger.debug(f"过滤无效价格: SKU={item.get('sku')}, price=None, available=False")
        
        if invalid_count > 0:
            logger.info(f"过滤无效价格: {len(prices)} → {len(valid_prices)} (移除{invalid_count}条)")
        
        # 2. 按SKU去重（保留Giga指数最高的）
        sku_map = {}
        for item in valid_prices:
            sku = item.get("sku")
            if not sku:
                continue
            
            # 如果SKU已存在，比较Giga指数
            if sku in sku_map:
                existing_giga_index = float(
                    sku_map[sku].get('sellerInfo', {}).get('gigaIndex', 0)
                )
                current_giga_index = float(
                    item.get('sellerInfo', {}).get('gigaIndex', 0)
                )
                
                # 保留Giga指数更高的
                if current_giga_index > existing_giga_index:
                    logger.debug(f"SKU {sku}: 替换供应商 (Giga指数 {existing_giga_index} → {current_giga_index})")
                    sku_map[sku] = item
            else:
                sku_map[sku] = item
        
        unique_prices = list(sku_map.values())
        
        if len(unique_prices) < len(valid_prices):
            logger.info(f"去重: {len(valid_prices)} → {len(unique_prices)} (合并{len(valid_prices) - len(unique_prices)}条重复)")
        
        success_count = 0
        failed_skus = []
        
        # 3. 准备基础价格数据
        base_price_data = []
        tier_price_data = []
        
        for item in unique_prices:
            try:
                sku = item.get("sku")
                if not sku:
                    failed_skus.append("UNKNOWN_SKU")
                    continue
                
                # 准备基础价格
                shipping_fee_range = item.get("shippingFeeRange", {})
                seller_info = item.get("sellerInfo", {})
                
                base_price_data.append({
                    'giga_sku': sku,
                    'currency': item.get("currency") or 'USD',
                    'base_price': item.get("price"),
                    'shipping_fee': item.get("shippingFee"),
                    'shipping_fee_min': shipping_fee_range.get("minAmount"),
                    'shipping_fee_max': shipping_fee_range.get("maxAmount"),
                    'exclusive_price': item.get("exclusivePrice"),
                    'discounted_price': item.get("discountedPrice"),
                    'promotion_start': self._parse_datetime(item.get("promotionFrom")),
                    'promotion_end': self._parse_datetime(item.get("promotionTo")),
                    'map_price': item.get("mapPrice"),
                    'future_map_price': item.get("futureMapPrice"),
                    'effect_map_time': self._parse_datetime(item.get("effectMapTime")),
                    'sku_available': item.get("skuAvailable", False),
                    'seller_info': json.dumps(seller_info),
                    'full_response': json.dumps(item)
                })
                
                # 准备梯度价格
                tier_mapping = [
                    ("spot", item.get("spotPrice", [])),
                    ("margin", item.get("marginPrice", [])),
                    ("rebate", item.get("rebatesPrice", [])),
                    ("future", item.get("futurePrice", []))
                ]
                
                for tier_type, tier_prices in tier_mapping:
                    if not tier_prices:
                        continue
                    
                    for price_info in tier_prices:
                        tier_price_data.append({
                            'giga_sku': sku,
                            'tier_type': tier_type,
                            'min_quantity': price_info.get("minQuantity"),
                            'max_quantity': price_info.get("maxQuantity"),
                            'price': price_info.get("price"),
                            'discounted_price': price_info.get("discountedSpotPrice") 
                                               or price_info.get("discountedPrice"),
                            'effective_date': self._parse_datetime(price_info.get("effectiveDate"))
                        })
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"准备SKU {item.get('sku')} 数据失败: {e}")
                failed_skus.append(item.get('sku', 'UNKNOWN'))
        
        # 4. 批量插入基础价格（使用临时表 + COPY）
        if base_price_data:
            try:
                self._bulk_upsert_base_prices(base_price_data)
                logger.info(f"批量插入基础价格: {len(base_price_data)}条")
            except Exception as e:
                logger.error(f"批量插入基础价格失败: {e}")
                return 0, len(unique_prices)
        
        # 5. 批量插入梯度价格（使用COPY）
        if tier_price_data:
            try:
                self._bulk_upsert_tier_prices(tier_price_data)
                logger.info(f"批量插入梯度价格: {len(tier_price_data)}条")
            except Exception as e:
                logger.error(f"批量插入梯度价格失败: {e}")
                # 梯度失败不影响基础价格
        
        return success_count, len(failed_skus)
    
    def _bulk_upsert_base_prices(self, data: List[Dict]):
        """使用临时表 + COPY批量UPSERT基础价格"""
        connection = self.db.connection().connection
        
        with connection.cursor() as cursor:
            # 1. 创建临时表
            cursor.execute("""
                CREATE TEMP TABLE tmp_base_prices (
                    giga_sku VARCHAR(100),
                    currency CHAR(3),
                    base_price NUMERIC(10,2),
                    shipping_fee NUMERIC(10,2),
                    shipping_fee_min NUMERIC(10,2),
                    shipping_fee_max NUMERIC(10,2),
                    exclusive_price NUMERIC(10,2),
                    discounted_price NUMERIC(10,2),
                    promotion_start TIMESTAMP WITH TIME ZONE,
                    promotion_end TIMESTAMP WITH TIME ZONE,
                    map_price NUMERIC(10,2),
                    future_map_price NUMERIC(10,2),
                    effect_map_time TIMESTAMP WITH TIME ZONE,
                    sku_available BOOLEAN,
                    seller_info JSONB,
                    full_response JSONB
                ) ON COMMIT DROP
            """)
            
            # 2. 构建CSV数据
            csv_data = StringIO()
            writer = csv.writer(csv_data)
            
            for item in data:
                writer.writerow([
                    item['giga_sku'],
                    item['currency'],
                    item['base_price'],
                    item['shipping_fee'],
                    item['shipping_fee_min'],
                    item['shipping_fee_max'],
                    item['exclusive_price'],
                    item['discounted_price'],
                    item['promotion_start'],
                    item['promotion_end'],
                    item['map_price'],
                    item['future_map_price'],
                    item['effect_map_time'],
                    item['sku_available'],
                    item['seller_info'],
                    item['full_response']
                ])
            
            csv_data.seek(0)
            
            # 3. COPY导入临时表
            cursor.copy_expert(
                sql="COPY tmp_base_prices FROM STDIN WITH CSV",
                file=csv_data
            )
            
            # 4. UPSERT到正式表
            cursor.execute("""
                INSERT INTO giga_product_base_prices (
                    giga_sku, currency, base_price, shipping_fee,
                    shipping_fee_min, shipping_fee_max, exclusive_price,
                    discounted_price, promotion_start, promotion_end,
                    map_price, future_map_price, effect_map_time,
                    sku_available, seller_info, full_response, updated_at
                )
                SELECT 
                    giga_sku, currency, base_price, shipping_fee,
                    shipping_fee_min, shipping_fee_max, exclusive_price,
                    discounted_price, promotion_start, promotion_end,
                    map_price, future_map_price, effect_map_time,
                    sku_available, seller_info, full_response, CURRENT_TIMESTAMP
                FROM tmp_base_prices
                ON CONFLICT (giga_sku) DO UPDATE SET
                    currency = EXCLUDED.currency,
                    base_price = EXCLUDED.base_price,
                    shipping_fee = EXCLUDED.shipping_fee,
                    shipping_fee_min = EXCLUDED.shipping_fee_min,
                    shipping_fee_max = EXCLUDED.shipping_fee_max,
                    exclusive_price = EXCLUDED.exclusive_price,
                    discounted_price = EXCLUDED.discounted_price,
                    promotion_start = EXCLUDED.promotion_start,
                    promotion_end = EXCLUDED.promotion_end,
                    map_price = EXCLUDED.map_price,
                    future_map_price = EXCLUDED.future_map_price,
                    effect_map_time = EXCLUDED.effect_map_time,
                    sku_available = EXCLUDED.sku_available,
                    seller_info = EXCLUDED.seller_info,
                    full_response = EXCLUDED.full_response,
                    updated_at = CURRENT_TIMESTAMP
            """)
    
    def _bulk_upsert_tier_prices(self, data: List[Dict]):
        """使用临时表 + COPY批量插入梯度价格"""
        if not data:
            return
        
        connection = self.db.connection().connection
        
        with connection.cursor() as cursor:
            # 1. 删除旧梯度（本批次涉及的SKU）
            skus = list(set(item['giga_sku'] for item in data))
            cursor.execute(
                """
                DELETE FROM giga_price_tiers 
                WHERE base_price_id IN (
                    SELECT id FROM giga_product_base_prices 
                    WHERE giga_sku = ANY(%s)
                )
                """,
                (skus,)
            )
            
            # 2. 创建临时表
            cursor.execute("""
                CREATE TEMP TABLE tmp_tier_prices (
                    giga_sku VARCHAR(100),
                    tier_type VARCHAR(10),
                    min_quantity INTEGER,
                    max_quantity INTEGER,
                    price NUMERIC(10,2),
                    discounted_price NUMERIC(10,2),
                    effective_date TIMESTAMP WITH TIME ZONE
                ) ON COMMIT DROP
            """)
            
            # 3. 构建CSV数据
            csv_data = StringIO()
            writer = csv.writer(csv_data)
            
            for item in data:
                writer.writerow([
                    item['giga_sku'],
                    item['tier_type'],
                    item['min_quantity'],
                    item['max_quantity'],
                    item['price'],
                    item['discounted_price'],
                    item['effective_date']
                ])
            
            csv_data.seek(0)
            
            # 4. COPY导入临时表
            cursor.copy_expert(
                sql="COPY tmp_tier_prices FROM STDIN WITH CSV",
                file=csv_data
            )
            
            # 5. JOIN插入正式表（将SKU转为ID）
            cursor.execute("""
                INSERT INTO giga_price_tiers (
                    base_price_id, tier_type, min_quantity,
                    max_quantity, price, discounted_price, effective_date
                )
                SELECT 
                    bp.id,
                    tmp.tier_type,
                    tmp.min_quantity,
                    tmp.max_quantity,
                    tmp.price,
                    tmp.discounted_price,
                    tmp.effective_date
                FROM tmp_tier_prices tmp
                INNER JOIN giga_product_base_prices bp 
                    ON bp.giga_sku = tmp.giga_sku
            """)
    
    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """解析时间字符串"""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return None
    
    def get_statistics(self) -> Dict[str, int]:
        """获取价格统计"""
        try:
            result = self.db.execute(
                text("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE sku_available = true) as available,
                        COUNT(DISTINCT currency) as currencies
                    FROM giga_product_base_prices
                """)
            ).fetchone()
            
            tier_count = self.db.execute(
                text("SELECT COUNT(*) FROM giga_price_tiers")
            ).scalar()
            
            return {
                'total_prices': result[0] or 0,
                'available_skus': result[1] or 0,
                'currencies': result[2] or 0,
                'total_tiers': tier_count or 0
            }
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {'total_prices': 0, 'available_skus': 0, 'currencies': 0, 'total_tiers': 0}
