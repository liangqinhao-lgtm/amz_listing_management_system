# src/services/category_maintenance_service.py
"""
Category Maintenance Service
品类维护服务

负责维护 supplier_categories_map 表，同步 Giga 供应商的品类映射
"""

from sqlalchemy.orm import Session
from src.repositories.category_repository import CategoryRepository
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class CategoryMaintenanceService:
    """
    品类维护服务
    负责维护 supplier_categories_map 表
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = CategoryRepository(db)
    
    def sync_giga_categories(self) -> Dict:
        """
        同步 Giga 品类到映射表
        
        流程:
        1. 获取 Giga 所有品类代码（从 giga_product_sync_records）
        2. 获取已存在的映射（从 supplier_categories_map）
        3. 找出新品类（对比差异）
        4. 插入新映射（supplier_platform 硬编码为 'giga'）
        
        注意：
        - supplier_platform 硬编码为 'giga'，因为数据源是 giga_product_sync_records 表
        - standard_category_name 留空（空字符串），待后续手动维护
        - supplier_category_name 从 raw_data->>'category' 提取
        
        Returns:
            {
                'total_giga_categories': 50,      # Giga 中的品类总数
                'existing_mappings': 35,          # 已存在的映射
                'new_categories': 15,             # 新发现的品类
                'inserted_count': 15,             # 成功插入的数量
                'new_category_list': [...]        # 新增的品类列表
            }
        """
        logger.info("🚀 开始同步 Giga 品类映射...")
        print("\n" + "=" * 70)
        print("🔄 同步 Giga 品类映射")
        print("=" * 70)
        
        # 1. 获取 Giga 中的所有品类
        print("\n➡️ 步骤 1/4: 查询 Giga 同步记录中的品类...")
        giga_categories = self.repository.get_giga_category_codes()
        print(f"✅ 发现 {len(giga_categories)} 个不同的品类代码")
        
        if not giga_categories:
            print("\n⚠️  未找到任何品类代码，流程结束")
            logger.warning("No category codes found in giga_product_sync_records")
            return {
                'total_giga_categories': 0,
                'existing_mappings': 0,
                'new_categories': 0,
                'inserted_count': 0,
                'new_category_list': []
            }
        
        # 2. 获取已存在的映射（只查询 giga 平台）
        print("\n➡️ 步骤 2/4: 查询已存在的品类映射...")
        existing_codes = self.repository.get_existing_category_codes('giga')
        print(f"✅ 已有 {len(existing_codes)} 个品类映射")
        
        # 3. 找出新品类
        print("\n➡️ 步骤 3/4: 对比差异，找出新品类...")
        new_categories = [
            cat for cat in giga_categories 
            if cat['category_code'] not in existing_codes
        ]
        
        if not new_categories:
            print("\n✅ 没有发现新品类，所有品类都已映射")
            logger.info("No new categories to sync")
            
            # 显示未映射品类的统计（即使没有新增）
            self._display_unmapped_categories_statistics()
            
            return {
                'total_giga_categories': len(giga_categories),
                'existing_mappings': len(existing_codes),
                'new_categories': 0,
                'inserted_count': 0,
                'new_category_list': []
            }
        
        print(f"\n🆕 发现 {len(new_categories)} 个新品类需要添加:")
        # 显示前10个新品类
        display_limit = min(10, len(new_categories))
        for i, cat in enumerate(new_categories[:display_limit], 1):
            print(f"   {i:2d}. {cat['category_code']:<15} - {cat['category_name']}")
        if len(new_categories) > display_limit:
            print(f"   ... 还有 {len(new_categories) - display_limit} 个")
        
        # 4. 准备插入数据
        print("\n➡️ 步骤 4/4: 插入新品类映射...")
        
        # 注意：supplier_platform 硬编码为 'giga'
        # 因为数据来源是 giga_product_sync_records 表
        mappings = [
            {
                'supplier_platform': 'giga',  # 硬编码，数据来源决定
                'supplier_category_code': cat['category_code'],
                'supplier_category_name': cat['category_name'],
                'standard_category_name': ''  # 留空，待手动维护
            }
            for cat in new_categories
        ]
        
        # 5. 批量插入
        try:
            inserted_count = self.repository.batch_insert_category_mappings(mappings)
            
            print(f"✅ 成功插入 {inserted_count} 条新品类映射")
            
            # 显示统计结果
            print("\n" + "=" * 70)
            print("📊 同步完成统计")
            print("=" * 70)
            print(f"Giga 品类总数:      {len(giga_categories)}")
            print(f"已存在的映射:       {len(existing_codes)}")
            print(f"新发现的品类:       {len(new_categories)}")
            print(f"成功插入记录:       {inserted_count}")
            print("=" * 70)
            
            # 提示需要维护 standard_category_name
            if inserted_count > 0:
                print("\n⚠️  重要提示:")
                print("   新增的品类映射中 standard_category_name 为空")
                print("   请在数据库中手动维护标准品类名称")
                print()
                print("   示例 SQL:")
                print("   UPDATE supplier_categories_map")
                print("   SET standard_category_name = 'your_standard_name'")
                print("   WHERE supplier_platform = 'giga'")
                print("     AND supplier_category_code = 'YOUR_CODE'")
                print("     AND standard_category_name = '';")
                print()
            
            logger.info(f"Category sync completed: inserted {inserted_count} new mappings")
            
            # 显示未映射品类的统计
            self._display_unmapped_categories_statistics()
            
            return {
                'total_giga_categories': len(giga_categories),
                'existing_mappings': len(existing_codes),
                'new_categories': len(new_categories),
                'inserted_count': inserted_count,
                'new_category_list': new_categories
            }
            
        except Exception as e:
            print(f"\n❌ 插入失败: {e}")
            logger.error(f"Failed to insert category mappings: {e}", exc_info=True)
            raise
    
    def _display_unmapped_categories_statistics(self):
        """显示未完成映射的品类统计信息"""
        print("\n" + "=" * 70)
        print("📊 待维护品类统计（按商品数量排序）")
        print("=" * 70)
        
        unmapped_stats = self.repository.get_unmapped_categories_with_product_count('giga')
        
        if not unmapped_stats:
            print("✅ 所有品类都已完成映射")
            print("=" * 70)
            return
        
        total_unmapped_products = sum(item['product_count'] for item in unmapped_stats)
        
        print(f"\n待维护品类数量: {len(unmapped_stats)}")
        print(f"涉及商品总数: {total_unmapped_products}")
        print()
        print(f"{'序号':<6} {'品类代码':<20} {'品类名称':<30} {'商品数量':>10}")
        print("-" * 70)
        
        for i, item in enumerate(unmapped_stats, 1):
            code = item['category_code'][:18] if len(item['category_code']) > 18 else item['category_code']
            name = item['category_name'][:28] if len(item['category_name']) > 28 else item['category_name']
            count = item['product_count']
            
            print(f"{i:<6} {code:<20} {name:<30} {count:>10,}")
        
        print("=" * 70)
        print("\n💡 提示: 请在数据库中为这些品类维护 standard_category_name")
        print("   示例 SQL:")
        print("   UPDATE supplier_categories_map")
        print("   SET standard_category_name = '标准品类名'")
        print("   WHERE supplier_platform = 'giga'")
        print("     AND supplier_category_code = '品类代码';")
        print()
    
    def update_mappings_from_csv(self, csv_file_path: str) -> Dict:
        """
        从 CSV 文件批量更新品类映射
        
        Args:
            csv_file_path: CSV 文件路径
            
        Returns:
            {
                'total_rows': 100,           # CSV 总行数
                'valid_rows': 95,            # 验证通过的行数
                'invalid_rows': 5,           # 验证失败的行数
                'updated_count': 90,         # 成功更新的数量
                'errors': [...]              # 错误详情
            }
        """
        import csv
        import os
        
        logger.info(f"Starting CSV import from: {csv_file_path}")
        print("\n" + "=" * 70)
        print("📥 从 CSV 文件更新品类映射")
        print("=" * 70)
        
        # 验证文件存在
        if not os.path.exists(csv_file_path):
            error_msg = f"文件不存在: {csv_file_path}"
            print(f"\n❌ {error_msg}")
            return {
                'total_rows': 0,
                'valid_rows': 0,
                'invalid_rows': 0,
                'updated_count': 0,
                'errors': [error_msg]
            }
        
        print(f"\n📁 文件路径: {csv_file_path}")
        
        # 读取 CSV 文件
        print("\n➡️ 步骤 1/4: 读取 CSV 文件...")
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            print(f"✅ 读取到 {len(rows)} 行数据")
            
        except Exception as e:
            error_msg = f"读取文件失败: {e}"
            print(f"\n❌ {error_msg}")
            return {
                'total_rows': 0,
                'valid_rows': 0,
                'invalid_rows': 0,
                'updated_count': 0,
                'errors': [error_msg]
            }
        
        if not rows:
            print("\n⚠️  文件为空，没有数据需要处理")
            return {
                'total_rows': 0,
                'valid_rows': 0,
                'invalid_rows': 0,
                'updated_count': 0,
                'errors': []
            }
        
        # 获取有效的亚马逊品类
        print("\n➡️ 步骤 2/4: 验证亚马逊品类有效性...")
        valid_amazon_categories = self.repository.get_valid_amazon_categories()
        print(f"✅ 系统中有 {len(valid_amazon_categories)} 个有效亚马逊品类")
        
        # 验证和准备更新数据
        print("\n➡️ 步骤 3/4: 验证数据...")
        
        valid_updates = []
        errors = []
        
        for i, row in enumerate(rows, 1):
            # 提取字段（忽略大小写和空格）
            supplier_platform = row.get('supplier_platform', '').strip()
            supplier_category_code = row.get('supplier_category_code', '').strip()
            standard_category_name = row.get('standard_category_name', '').strip()
            
            # 验证必填字段
            if not supplier_platform:
                errors.append(f"第 {i} 行: supplier_platform 为空")
                continue
            
            if not supplier_category_code:
                errors.append(f"第 {i} 行: supplier_category_code 为空")
                continue
            
            if not standard_category_name:
                errors.append(f"第 {i} 行: standard_category_name 为空")
                continue
            
            # 验证 standard_category_name 在有效品类中
            if standard_category_name.lower() not in valid_amazon_categories:
                errors.append(
                    f"第 {i} 行: standard_category_name '{standard_category_name}' "
                    f"不是有效的亚马逊品类"
                )
                continue
            
            # 添加到有效更新列表
            valid_updates.append({
                'supplier_platform': supplier_platform,
                'supplier_category_code': supplier_category_code,
                'standard_category_name': standard_category_name
            })
        
        print(f"✅ 验证完成")
        print(f"   有效行数: {len(valid_updates)}")
        print(f"   无效行数: {len(errors)}")
        
        # 显示错误（如果有）
        if errors:
            print("\n⚠️  发现以下错误:")
            for error in errors[:10]:  # 只显示前10个错误
                print(f"   - {error}")
            if len(errors) > 10:
                print(f"   ... 还有 {len(errors) - 10} 个错误")
        
        # 如果没有有效数据，直接返回
        if not valid_updates:
            print("\n❌ 没有有效数据可以更新")
            return {
                'total_rows': len(rows),
                'valid_rows': 0,
                'invalid_rows': len(errors),
                'updated_count': 0,
                'errors': errors
            }
        
        # 执行更新
        print(f"\n➡️ 步骤 4/4: 更新数据库...")
        
        try:
            updated_count = self.repository.batch_update_category_mappings(valid_updates)
            
            print(f"✅ 成功更新 {updated_count} 条记录")
            
            # 显示统计结果
            print("\n" + "=" * 70)
            print("📊 更新完成统计")
            print("=" * 70)
            print(f"CSV 总行数:        {len(rows)}")
            print(f"验证通过行数:      {len(valid_updates)}")
            print(f"验证失败行数:      {len(errors)}")
            print(f"成功更新记录:      {updated_count}")
            print("=" * 70)
            
            if updated_count < len(valid_updates):
                print("\n⚠️  注意: 部分记录未更新成功")
                print("   可能原因: supplier_platform 和 supplier_category_code 组合不存在")
            
            logger.info(f"CSV import completed: {updated_count} records updated")
            
            return {
                'total_rows': len(rows),
                'valid_rows': len(valid_updates),
                'invalid_rows': len(errors),
                'updated_count': updated_count,
                'errors': errors
            }
            
        except Exception as e:
            error_msg = f"更新失败: {e}"
            print(f"\n❌ {error_msg}")
            logger.error(error_msg, exc_info=True)
            return {
                'total_rows': len(rows),
                'valid_rows': len(valid_updates),
                'invalid_rows': len(errors),
                'updated_count': 0,
                'errors': errors + [error_msg]
            }