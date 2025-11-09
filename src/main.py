# src/main.py

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import csv
import os
import datetime
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量
load_dotenv(dotenv_path=Path('.env'))

from infrastructure.db_pool import SessionLocal
from src.services.giga_sync_service import GigaSyncService
from src.services.giga_price_sync_service import GigaPriceSyncService
from src.services.giga_inventory_sync_service import GigaInventorySyncService
from src.services.product_detail_generation_service import ProductDetailGenerationService
from src.services.sku_mapping_service import SkuMappingService
from src.services.amz_full_list_importer_service import AmzFullListImporterService
# ✨ 新增：导入定价服务
from src.services.pricing_service import PricingService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def display_menu():
    """显示菜单"""
    print("\n" + "="*60)
    print("📦 电商自动化运营系统")
    print("="*60)
    print("\n--- 1. Giga 商品管理 ---")
    print("1.1 同步全量Giga收藏商品详情")
    print("1.2 导入亚马逊全量listing数据")
    print("1.4 使用AI生成商品详情（并自动映射SKU）")
    print("1.5 同步Giga商品价格")
    print("1.6 同步Giga商品库存")
    print("1.7 更新售价")  # ✨ 已存在
    print("\n--- 2. 数据查询 ---")
    print("2.1 查看数据统计")
    print("\n--- 0. 系统 ---")
    print("0. 退出")
    print("="*60)


def handle_sync_products(db: Session):
    """1.1 同步全量Giga收藏商品详情"""
    logger.info("🚀 启动商品同步流程...")
    
    service = GigaSyncService(db)
    
    print("\n➡️  步骤 1/2: 获取收藏商品列表...")
    sku_list = service.get_favorite_product_list()
    
    if not sku_list:
        print("✅ 没有收藏商品需要同步")
        return
    
    print(f"✅ 获取到 {len(sku_list)} 个收藏商品")
    print(f"\n➡️  步骤 2/2: 同步商品详情...")
    
    total, success, failed = service.sync_product_details(sku_list)
    
    print(f"\n{'='*60}")
    print("✅ 商品同步完成")
    print(f"{'='*60}")
    print(f"总计: {total}")
    print(f"成功: {success}")
    print(f"失败: {failed}")
    print(f"{'='*60}\n")


def handle_import_amazon_report(db: Session):
    """1.2 导入亚马逊全量listing数据"""
    logger.info("🚀 启动Amazon数据导入流程...")
    
    file_path = input("\n请输入Amazon报告文件路径(.txt): ").strip().strip('"')
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return
    
    service = AmzFullListImporterService(db)
    service.import_report_from_file(file_path)


def handle_generate_details(db: Session):
    """1.4 使用AI生成商品详情"""
    logger.info("🚀 启动AI详情生成流程...")
    
    llm_provider = os.getenv("LLM_PROVIDER", "deepseek").lower()
    llm_model = os.getenv(f"{llm_provider.upper()}_MODEL", "deepseek-chat")
    
    print(f"\n🤖 使用 {llm_provider.upper()} 模型: {llm_model}")
    
    service = ProductDetailGenerationService(
        db=db,
        llm_provider=llm_provider,
        llm_model=llm_model
    )
    
    service.process_all_products()
    
    # 自动触发SKU映射
    print("\n➡️  自动触发SKU映射...")
    mapping_service = SkuMappingService(db)
    total, created = mapping_service.sync_mappings_from_llm_details()
    print(f"✅ SKU映射完成。检查: {total}, 新建: {created}")


def handle_sync_prices(db: Session):
    """1.5 同步Giga商品价格"""
    logger.info("🚀 启动价格同步流程...")
    
    service = GigaPriceSyncService(db)
    result = service.sync_all_prices()
    
    logger.info(f"价格同步完成: {result}")


def handle_sync_inventory(db: Session):
    """1.6 同步Giga商品库存"""
    logger.info("🚀 启动库存同步流程...")
    
    service = GigaInventorySyncService(db)
    result = service.sync_all_inventory()
    
    logger.info(f"库存同步完成: {result}")


def handle_update_prices(db: Session):
    """1.7 更新售价 ✨"""
    logger.info("🚀 启动价格更新流程...")
    
    service = PricingService(db)
    
    # 更新所有SKU的价格
    total, success, report_data = service.update_prices()
    
    # 显示样例数据
    if report_data and len(report_data) > 0:
        print("\n📊 价格更新样例（前5条）:")
        print("-" * 100)
        for i, row in enumerate(report_data[:5], 1):
            print(f"{i}. {row['meow_sku']:20} | 品类: {row['category']:15} | "
                  f"成本: ${row['total_cost']:8} | 售价: ${row['final_price']:8} | "
                  f"毛利: {row['margin']}")
        
        if len(report_data) > 5:
            print(f"... 还有 {len(report_data) - 5} 条记录")
        print("-" * 100)


def handle_view_statistics(db: Session):
    """2.1 查看数据统计"""
    from src.repositories.giga_product_sync_repository import GigaProductSyncRepository
    from src.repositories.llm_product_detail_repository import LLMProductDetailRepository
    from src.repositories.sku_mapping_repository import SkuMappingRepository
    from src.repositories.giga_product_price_repository import GigaProductPriceRepository
    from src.repositories.giga_product_inventory_repository import GigaProductInventoryRepository
    from src.repositories.amz_full_list_report_repository import AmzFullListReportRepository
    
    print("\n" + "="*60)
    print("📊 数据统计")
    print("="*60)
    
    # Amazon数据
    amz_repo = AmzFullListReportRepository(db)
    amz_stats = amz_repo.get_statistics()
    print("\n【Amazon数据】")
    print(f"  总记录: {amz_stats['total_records']}")
    print(f"  Active: {amz_stats['active_listings']}")
    print(f"  唯一ASIN: {amz_stats['unique_asins']}")
    
    # Giga商品
    giga_repo = GigaProductSyncRepository(db)
    giga_stats = giga_repo.get_statistics()
    print("\n【Giga商品】")
    print(f"  总记录: {giga_stats['total_products']}")
    print(f"  已同步: {giga_stats['synced_products']}")
    print(f"  超大件: {giga_stats['oversized_products']}")
    
    # LLM生成详情
    llm_repo = LLMProductDetailRepository(db)
    llm_stats = llm_repo.get_statistics()
    print("\n【LLM生成详情】")
    print(f"  总记录: {llm_stats['total_details']}")
    print(f"  唯一SKU: {llm_stats['unique_skus']}")
    
    # SKU映射
    mapping_repo = SkuMappingRepository(db)
    mapping_stats = mapping_repo.get_statistics()
    print("\n【SKU映射】")
    print(f"  总映射: {mapping_stats['total_mappings']}")
    print(f"  供应商数: {mapping_stats['unique_vendors']}")
    
    # Giga价格
    price_repo = GigaProductPriceRepository(db)
    price_stats = price_repo.get_statistics()
    print("\n【Giga价格】")
    print(f"  总价格: {price_stats['total_prices']}")
    print(f"  可用SKU: {price_stats['available_skus']}")
    print(f"  价格梯度: {price_stats['total_tiers']}")
    
    # Giga库存
    inventory_repo = GigaProductInventoryRepository(db)
    inventory_stats = inventory_repo.get_statistics()
    print("\n【Giga库存】")
    print(f"  总SKU: {inventory_stats['total_skus']}")
    print(f"  有库存: {inventory_stats['in_stock_skus']}")
    print(f"  总库存量: {inventory_stats['total_quantity']}")
    
    print("="*60 + "\n")


def main():
    """主程序"""
    load_dotenv()
    
    logger.info("系统启动")
    
    while True:
        try:
            display_menu()
            choice = input("\n请选择操作: ").strip()
            
            if choice == '0':
                print("\n👋 再见！")
                logger.info("系统退出")
                break
            
            # 创建数据库会话
            with SessionLocal() as db:
                if choice == '1.1':
                    handle_sync_products(db)
                elif choice == '1.2':
                    handle_import_amazon_report(db)
                elif choice == '1.4':
                    handle_generate_details(db)
                elif choice == '1.5':
                    handle_sync_prices(db)
                elif choice == '1.6':
                    handle_sync_inventory(db)
                elif choice == '1.7':  # ✨ 新的价格更新流程
                    handle_update_prices(db)
                elif choice == '2.1':
                    handle_view_statistics(db)
                else:
                    print("❌ 无效选项，请重新选择")
        
        except KeyboardInterrupt:
            print("\n\n👋 检测到中断，退出系统")
            break
        except Exception as e:
            logger.error(f"发生错误: {e}", exc_info=True)
            print(f"\n❌ 发生错误: {e}")


if __name__ == "__main__":
    main()