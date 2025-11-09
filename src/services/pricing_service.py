"""定价服务"""
from sqlalchemy.orm import Session
from src.repositories.pricing_repository import PricingRepository
from src.services.category_service import CategoryService
from src.utils.pricing_config import PricingConfigLoader
import logging
from typing import List, Dict, Any, Tuple, Optional
from decimal import Decimal, getcontext
import json

# 设置Decimal精度
getcontext().prec = 12

logger = logging.getLogger(__name__)

class PricingService:
    """定价服务 - 负责价格计算和更新"""
    
    def __init__(self, db: Session):
        self.db = db
        self.pricing_repo = PricingRepository(db=self.db)
        self.category_service = CategoryService(db=self.db)
    
    def _calculate_price(self, pc: Decimal, lf: Decimal, params: Dict[str, Any]) -> Decimal:
        """
        根据公式计算最终售价
        
        公式: price = (pc + lf) * (1 + lpc + rr) / (1 - cr - ac - sc - tmg)
        
        Args:
            pc: 采购价 (Purchase Cost)
            lf: 物流费 (Logistic Fee)
            params: 业务参数字典
            
        Returns:
            计算出的最终价格
        """
        cr = Decimal(str(params['commission_rate']))
        rr = Decimal(str(params['return_rate']))
        sc = Decimal(str(params['settlement_cost_rate']))
        ac = Decimal(str(params['ad_cost_rate']))
        lpc = Decimal(str(params['logistic_protection_rate']))
        tmg = Decimal(str(params['target_margin_rate']))
        
        denominator = Decimal('1') - cr - ac - sc - tmg
        
        if denominator <= 0:
            raise ValueError(f"定价公式分母无效 (<=0): {denominator}")
        
        price = (pc + lf) * (Decimal('1') + lpc + rr) / denominator
        return round(price, 2)
    
    def update_prices(self, sku_list: Optional[List[str]] = None) -> Tuple[int, int, List[Dict[str, Any]]]:
        """
        更新商品价格
        
        Args:
            sku_list: 如果提供则只处理指定SKU，否则处理所有SKU
            
        Returns:
            (总处理数, 成功数, 报告数据)
        """
        logger.info("🚀 开始批量价格更新流程...")
        print("\n" + "="*60)
        print("💰 价格更新流程")
        print("="*60)
        
        # 1. 获取SKU列表
        if sku_list is None:
            print("➡️  步骤 1/4: 获取所有需要定价的SKU...")
            target_skus = self.pricing_repo.get_all_meow_skus()
        else:
            print(f"➡️  步骤 1/4: 处理指定的 {len(sku_list)} 个SKU...")
            target_skus = sku_list
        
        if not target_skus:
            logger.info("没有找到需要处理的SKU")
            print("✔️  没有找到需要处理的SKU")
            return 0, 0, []
        
        print(f"✔️  找到 {len(target_skus)} 个需要处理的SKU")
        
        # 2. 品类匹配
        print("➡️  步骤 2/4: 品类匹配...")
        categorized_skus, uncategorized = self.category_service.categorize_skus(target_skus)
        
        category_summary = {cat: len(skus) for cat, skus in categorized_skus.items()}
        if category_summary:
            print(f"✔️  品类分布: {category_summary}")
        if uncategorized:
            print(f"   未分类: {len(uncategorized)} 个（使用fallback配置）")
        
        # 3. 获取成本数据
        print("➡️  步骤 3/4: 获取成本数据...")
        sku_costs = self.pricing_repo.get_costs_for_skus(target_skus)
        print(f"✔️  成功获取 {len(sku_costs)} 个SKU的成本数据")
        
        if len(sku_costs) < len(target_skus):
            missing = len(target_skus) - len(sku_costs)
            print(f"   ⚠️  {missing} 个SKU没有成本数据（将跳过）")
        
        # 4. 计算价格
        print("➡️  步骤 4/4: 计算最终价格...")
        
        # 构建SKU到品类的映射
        sku_to_category = {}
        for cat, sku_list_in_cat in categorized_skus.items():
            for sku in sku_list_in_cat:
                sku_to_category[sku] = cat
        
        price_data_to_upsert = []
        report_data = []
        success_count = 0
        
        for sku, (pc, lf) in sku_costs.items():
            category = sku_to_category.get(sku)
            params = PricingConfigLoader.get_params_for_category(category)
            
            try:
                final_price = self._calculate_price(pc, lf, params)
                
                # 准备数据库更新数据
                price_data_to_upsert.append({
                    "meow_sku": sku,
                    "final_price": final_price,
                    "currency": "USD",
                    "cost_at_pricing": pc + lf,
                    "pricing_formula_version": params.get("formula_version", "unknown"),
                    "pricing_params_snapshot": json.dumps(params)
                })
                
                # 准备报告数据
                report_row = {
                    "meow_sku": sku,
                    "category": category or "fallback",
                    "purchase_cost": f"{pc:.2f}",
                    "logistic_fee": f"{lf:.2f}",
                    "total_cost": f"{pc + lf:.2f}",
                    "final_price": f"{final_price:.2f}",
                    "margin": f"{(final_price - pc - lf) / final_price * 100:.1f}%"
                }
                report_data.append(report_row)
                
                success_count += 1
                
            except ValueError as e:
                logger.error(f"计算SKU '{sku}' 价格失败: {e}")
        
        # 5. 批量更新数据库
        if price_data_to_upsert:
            try:
                self.pricing_repo.upsert_final_prices(price_data_to_upsert)
                self.db.commit()
                print(f"✔️  成功更新 {len(price_data_to_upsert)} 条价格记录到数据库")
            except Exception as e:
                logger.error(f"数据库批量更新失败: {e}")
                self.db.rollback()
                success_count = 0
                print(f"❌ 数据库更新失败: {e}")
        
        total_processed = len(target_skus)
        
        print("\n" + "="*60)
        print("✅ 价格更新完成")
        print("="*60)
        print(f"总计处理: {total_processed}")
        print(f"成功更新: {success_count}")
        print(f"失败/跳过: {total_processed - success_count}")
        print("="*60 + "\n")
        
        logger.info(f"价格更新流程完成。处理: {total_processed}, 成功: {success_count}")
        
        return total_processed, success_count, report_data
