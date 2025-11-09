#!/usr/bin/env python
"""根据实际category_code创建映射数据"""
import os
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import text

load_dotenv(dotenv_path=Path('.env'))

from infrastructure.db_pool import SessionLocal

# 品类映射定义（仅映射已定义的标准品类）
# 其他未映射的类目将使用 fallback 配置
CATEGORY_MAPPINGS = {
    # 浴室柜类 (cabinet)
    '10143': ('Bathroom Vanities', 'cabinet'),
    '10148': ('Bathroom Storage', 'cabinet'),
    
    # 镜子类 (home_mirror)
    '10104': ('Bathroom Mirrors', 'home_mirror'),
    '10105': ('Full Length Mirrors', 'home_mirror'),
    '10053': ('Wall Mirrors', 'home_mirror'),
    '10144': ('Mirrors', 'home_mirror'),
    
    # 注意：其他类目暂不映射，将使用 fallback 配置
    # 如需添加新品类，需要先在 amz_pricing_config.yaml 中定义
}

def update_category_mappings():
    """更新品类映射表"""
    
    print("="*80)
    print("🔄 更新品类映射表")
    print("="*80)
    
    with SessionLocal() as db:
        try:
            # 1. 清空旧数据
            print("\n➡️  步骤 1/3: 清空旧映射数据...")
            db.execute(text("TRUNCATE TABLE supplier_categories_map RESTART IDENTITY CASCADE"))
            print("✅ 旧数据已清空")
            
            # 2. 批量插入新数据
            print("\n➡️  步骤 2/3: 插入新映射数据...")
            
            insert_query = text("""
                INSERT INTO supplier_categories_map (
                    supplier_platform,
                    supplier_category_code,
                    supplier_category_name,
                    standard_category_name
                ) VALUES (
                    :platform,
                    :code,
                    :name,
                    :standard
                )
            """)
            
            for code, (name, standard) in CATEGORY_MAPPINGS.items():
                db.execute(insert_query, {
                    'platform': 'giga',
                    'code': code,
                    'name': name,
                    'standard': standard
                })
            
            db.commit()
            print(f"✅ 成功插入 {len(CATEGORY_MAPPINGS)} 条映射记录")
            
            # 3. 验证
            print("\n➡️  步骤 3/3: 验证映射数据...")
            
            # 统计
            result = db.execute(text("""
                SELECT 
                    standard_category_name,
                    COUNT(*) as count
                FROM supplier_categories_map
                WHERE supplier_platform = 'giga'
                GROUP BY standard_category_name
                ORDER BY count DESC
            """)).fetchall()
            
            print("\n品类分布:")
            for standard, count in result:
                print(f"  {standard:20} : {count:3} 个Giga类目")
            
            # 测试匹配率
            match_test = db.execute(text("""
                SELECT 
                    COUNT(DISTINCT psr.giga_sku) as total,
                    COUNT(DISTINCT CASE 
                        WHEN scm.standard_category_name IS NOT NULL 
                        THEN psr.giga_sku 
                    END) as matched
                FROM giga_product_sync_records psr
                LEFT JOIN supplier_categories_map scm
                    ON psr.category_code = scm.supplier_category_code
                    AND scm.supplier_platform = 'giga'
            """)).fetchone()
            
            total_products = match_test[0]
            matched_products = match_test[1]
            match_rate = matched_products / total_products * 100 if total_products > 0 else 0
            
            print(f"\n匹配测试:")
            print(f"  总商品数: {total_products}")
            print(f"  已匹配: {matched_products}")
            print(f"  匹配率: {match_rate:.1f}%")
            
            # 查看未匹配的category_code
            if match_rate < 100:
                print("\n📋 未映射的category_code（将使用fallback配置）:")
                unmatched = db.execute(text("""
                    SELECT 
                        psr.category_code,
                        COUNT(*) as count
                    FROM giga_product_sync_records psr
                    LEFT JOIN supplier_categories_map scm
                        ON psr.category_code = scm.supplier_category_code
                        AND scm.supplier_platform = 'giga'
                    WHERE scm.id IS NULL
                    GROUP BY psr.category_code
                    ORDER BY count DESC
                """)).fetchall()
                
                total_unmapped = sum(count for _, count in unmatched)
                print(f"    总计: {len(unmatched)} 个类目, {total_unmapped} 个商品")
                print(f"\n    这些商品将使用 fallback 定价配置")
                
                if len(unmatched) <= 10:
                    print(f"\n    详细列表:")
                    for code, count in unmatched:
                        print(f"      {code:10} : {count:3} 个商品")
            else:
                print("\n✅ 所有商品都已映射到标准品类")
            
            print("\n" + "="*80)
            print("✅ 品类映射表更新完成")
            print("="*80)
            
        except Exception as e:
            db.rollback()
            print(f"\n❌ 更新失败: {e}")
            raise

if __name__ == "__main__":
    update_category_mappings()