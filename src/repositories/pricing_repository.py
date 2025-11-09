"""定价相关Repository（高性能批量操作版）"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from decimal import Decimal
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class PricingRepository:
    """定价相关数据仓库"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_all_meow_skus(self) -> List[str]:
        """获取所有meow_sku"""
        query = text("SELECT meow_sku FROM meow_sku_map")
        try:
            results = self.db.execute(query).scalars().all()
            return list(results)
        except Exception as e:
            logger.error(f"获取meow_sku列表失败: {e}")
            return []
    
    def get_costs_for_skus(self, meow_skus: List[str]) -> Dict[str, Tuple[Decimal, Decimal]]:
        """
        批量获取SKU的成本数据（采购价 + 物流费）
        
        Args:
            meow_skus: meow_sku列表
            
        Returns:
            {meow_sku: (采购价, 物流费)}
        """
        query = text("""
            SELECT 
                m.meow_sku,
                pbp.currency,
                pbp.discounted_price,
                pbp.promotion_start,
                pbp.promotion_end,
                pbp.base_price,
                pbp.shipping_fee,
                pbp.exclusive_price
            FROM meow_sku_map m
            JOIN giga_product_base_prices pbp 
                ON m.vendor_sku = pbp.giga_sku 
                AND m.vendor_source = 'giga'
            WHERE m.meow_sku = ANY(:meow_sku_list)
        """)
        
        costs = {}
        try:
            results = self.db.execute(query, {"meow_sku_list": meow_skus}).fetchall()
            
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            
            for row in results:
                (meow_sku, currency, discounted_price, promo_start, promo_end, 
                 base_price, shipping_fee, exclusive_price) = row
                
                # 只处理USD
                if currency != 'USD':
                    logger.warning(f"SKU {meow_sku} 的货币类型不是USD，已跳过")
                    continue
                
                # 选择最优价格
                candidate_prices = []
                
                # 促销价（需要在促销期内）
                if discounted_price and promo_start and promo_end:
                    if promo_start <= now <= promo_end:
                        candidate_prices.append(Decimal(str(discounted_price)))
                
                # 基础价
                if base_price:
                    candidate_prices.append(Decimal(str(base_price)))
                
                # 专属价
                if exclusive_price:
                    candidate_prices.append(Decimal(str(exclusive_price)))
                
                if not candidate_prices:
                    logger.warning(f"SKU {meow_sku} 没有任何有效价格，已跳过")
                    continue
                
                # 选择最低价
                pc = min(candidate_prices)
                lf = Decimal(str(shipping_fee)) if shipping_fee else Decimal('0')
                
                costs[meow_sku] = (pc, lf)
        
        except Exception as e:
            logger.error(f"批量获取成本数据失败: {e}")
        
        return costs
    
    def upsert_final_prices(self, price_data: List[Dict[str, Any]]):
        """
        批量更新或插入最终售价（高性能COPY版本）
        
        使用临时表 + COPY 命令实现高性能批量导入
        """
        if not price_data:
            return
        
        connection = self.db.connection().connection
        
        try:
            with connection.cursor() as cursor:
                # 1. 创建临时表
                cursor.execute("""
                    CREATE TEMP TABLE tmp_final_prices (
                        meow_sku VARCHAR(255),
                        final_price NUMERIC(10,2),
                        currency VARCHAR(3),
                        cost_at_pricing NUMERIC(10,2),
                        pricing_formula_version VARCHAR(50),
                        pricing_params_snapshot JSONB
                    ) ON COMMIT DROP
                """)
                
                # 2. 构建CSV数据
                from io import StringIO
                import csv
                
                csv_data = StringIO()
                writer = csv.writer(csv_data)
                
                for item in price_data:
                    writer.writerow([
                        item['meow_sku'],
                        item['final_price'],
                        item['currency'],
                        item['cost_at_pricing'],
                        item['pricing_formula_version'],
                        item['pricing_params_snapshot']
                    ])
                
                csv_data.seek(0)
                
                # 3. COPY 批量导入临时表
                cursor.copy_expert(
                    sql="COPY tmp_final_prices FROM STDIN WITH CSV",
                    file=csv_data
                )
                
                # 4. 从临时表批量 UPSERT 到正式表
                cursor.execute("""
                    INSERT INTO product_final_prices (
                        meow_sku, final_price, currency, cost_at_pricing,
                        pricing_formula_version, pricing_params_snapshot
                    )
                    SELECT 
                        meow_sku, final_price, currency, cost_at_pricing,
                        pricing_formula_version, pricing_params_snapshot
                    FROM tmp_final_prices
                    ON CONFLICT (meow_sku) DO UPDATE SET
                        final_price = EXCLUDED.final_price,
                        currency = EXCLUDED.currency,
                        cost_at_pricing = EXCLUDED.cost_at_pricing,
                        pricing_formula_version = EXCLUDED.pricing_formula_version,
                        pricing_params_snapshot = EXCLUDED.pricing_params_snapshot,
                        updated_at = NOW()
                """)
            
            logger.info(f"成功批量更新或插入 {len(price_data)} 条价格记录（使用COPY优化）")
            
        except Exception as e:
            logger.error(f"批量更新价格失败: {e}")
            raise