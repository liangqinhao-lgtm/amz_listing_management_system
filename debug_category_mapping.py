#!/usr/bin/env python
"""品类映射调试脚本"""
import os
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import text

load_dotenv(dotenv_path=Path('.env'))

from infrastructure.db_pool import SessionLocal

def debug_category_mapping():
    """调试品类映射问题"""
    
    print("="*80)
    print("🔍 品类映射调试")
    print("="*80)
    
    with SessionLocal() as db:
        
        # 1. 检查 meow_sku_map 表
        print("\n【1. meow_sku_map 表】")
        result = db.execute(text("""
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT meow_sku) as unique_meow_sku,
                   COUNT(DISTINCT vendor_sku) as unique_vendor_sku,
                   STRING_AGG(DISTINCT vendor_source, ', ') as vendor_sources
            FROM meow_sku_map
        """)).fetchone()
        
        print(f"  总记录数: {result[0]}")
        print(f"  唯一meow_sku: {result[1]}")
        print(f"  唯一vendor_sku: {result[2]}")
        print(f"  供应商来源: {result[3]}")
        
        # 查看前5条
        print("\n  前5条记录:")
        samples = db.execute(text("""
            SELECT meow_sku, vendor_sku, vendor_source
            FROM meow_sku_map
            LIMIT 5
        """)).fetchall()
        for row in samples:
            print(f"    {row[0]:20} | {row[1]:20} | {row[2]}")
        
        # 2. 检查 giga_product_sync_records 表
        print("\n【2. giga_product_sync_records 表】")
        result = db.execute(text("""
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT giga_sku) as unique_giga_sku,
                   COUNT(category_code) as has_category_code,
                   COUNT(DISTINCT category_code) as unique_category_codes
            FROM giga_product_sync_records
        """)).fetchone()
        
        print(f"  总记录数: {result[0]}")
        print(f"  唯一giga_sku: {result[1]}")
        print(f"  有category_code: {result[2]}")
        print(f"  唯一category_code: {result[3]}")
        
        # 查看所有的 category_code
        print("\n  所有category_code分布:")
        categories = db.execute(text("""
            SELECT category_code, COUNT(*) as count
            FROM giga_product_sync_records
            WHERE category_code IS NOT NULL
            GROUP BY category_code
            ORDER BY count DESC
        """)).fetchall()
        
        if categories:
            for cat, count in categories:
                print(f"    {cat:20} : {count:4} 个商品")
        else:
            print("    ⚠️  没有category_code数据！")
        
        # 3. 检查 supplier_categories_map 表
        print("\n【3. supplier_categories_map 表】")
        result = db.execute(text("""
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT supplier_category_code) as unique_codes,
                   COUNT(DISTINCT standard_category_name) as unique_standards
            FROM supplier_categories_map
            WHERE supplier_platform = 'giga'
        """)).fetchone()
        
        print(f"  总映射数: {result[0]}")
        print(f"  唯一供应商代码: {result[1]}")
        print(f"  唯一标准品类: {result[2]}")
        
        # 查看所有映射
        print("\n  Giga品类映射表:")
        mappings = db.execute(text("""
            SELECT supplier_category_code, 
                   supplier_category_name,
                   standard_category_name
            FROM supplier_categories_map
            WHERE supplier_platform = 'giga'
            ORDER BY id
        """)).fetchall()
        
        if mappings:
            print(f"    {'供应商代码':<20} | {'供应商名称':<20} | {'标准品类':<20}")
            print("    " + "-"*65)
            for code, name, standard in mappings:
                print(f"    {code:<20} | {name:<20} | {standard:<20}")
        else:
            print("    ⚠️  映射表为空！")
        
        # 4. 测试完整的JOIN查询
        print("\n【4. 完整JOIN查询测试】")
        print("  执行CategoryRepository的查询逻辑...")
        
        # 取前5个meow_sku测试
        test_skus = db.execute(text("""
            SELECT meow_sku FROM meow_sku_map LIMIT 5
        """)).scalars().all()
        
        if test_skus:
            print(f"\n  测试SKU: {test_skus}")
            
            result = db.execute(text("""
                SELECT DISTINCT 
                    m.meow_sku,
                    m.vendor_sku,
                    psr.giga_sku,
                    psr.category_code,
                    scm.supplier_category_code,
                    scm.standard_category_name
                FROM meow_sku_map m
                JOIN giga_product_sync_records psr 
                    ON m.vendor_sku = psr.giga_sku 
                    AND m.vendor_source = 'giga'
                LEFT JOIN supplier_categories_map scm 
                    ON LOWER(psr.category_code) = LOWER(scm.supplier_category_code)
                    AND scm.supplier_platform = 'giga'
                WHERE m.meow_sku = ANY(:meow_sku_list)
            """), {"meow_sku_list": test_skus}).fetchall()
            
            print(f"\n  查询结果 ({len(result)} 条):")
            if result:
                print(f"    {'meow_sku':<20} | {'category_code':<15} | {'标准品类':<20}")
                print("    " + "-"*60)
                for row in result:
                    meow_sku = row[0]
                    category_code = row[3] or "NULL"
                    standard = row[5] or "未匹配"
                    print(f"    {meow_sku:<20} | {category_code:<15} | {standard:<20}")
            else:
                print("    ⚠️  JOIN结果为空！")
        
        # 5. 诊断问题
        print("\n" + "="*80)
        print("🔬 问题诊断")
        print("="*80)
        
        # 检查是否有数据能匹配上
        match_test = db.execute(text("""
            SELECT COUNT(*) as matched
            FROM meow_sku_map m
            JOIN giga_product_sync_records psr 
                ON m.vendor_sku = psr.giga_sku 
                AND m.vendor_source = 'giga'
            WHERE psr.category_code IS NOT NULL
        """)).scalar()
        
        print(f"\n✓ meow_sku_map 与 giga_product_sync_records 能匹配: {match_test} 条")
        
        if match_test == 0:
            print("\n❌ 问题：meow_sku_map.vendor_sku 与 giga_product_sync_records.giga_sku 无法匹配")
            print("\n  可能原因:")
            print("  1. vendor_sku 和 giga_sku 的值不一致")
            print("  2. vendor_source 不是 'giga'")
            
            # 检查具体不匹配的原因
            print("\n  检查vendor_sku格式:")
            sample_vendor = db.execute(text("""
                SELECT vendor_sku FROM meow_sku_map LIMIT 5
            """)).scalars().all()
            print(f"    meow_sku_map.vendor_sku 样例: {sample_vendor}")
            
            sample_giga = db.execute(text("""
                SELECT giga_sku FROM giga_product_sync_records LIMIT 5
            """)).scalars().all()
            print(f"    giga_product_sync_records.giga_sku 样例: {sample_giga}")
        else:
            # 检查category_code是否能匹配到映射表
            category_match = db.execute(text("""
                SELECT COUNT(*) as matched
                FROM giga_product_sync_records psr
                JOIN supplier_categories_map scm
                    ON LOWER(psr.category_code) = LOWER(scm.supplier_category_code)
                    AND scm.supplier_platform = 'giga'
                WHERE psr.category_code IS NOT NULL
            """)).scalar()
            
            print(f"✓ category_code 能匹配到映射表: {category_match} 条")
            
            if category_match == 0:
                print("\n❌ 问题：category_code 与 supplier_categories_map 无法匹配")
                print("\n  实际category_code与映射表对比:")
                
                actual_codes = db.execute(text("""
                    SELECT DISTINCT category_code 
                    FROM giga_product_sync_records 
                    WHERE category_code IS NOT NULL
                """)).scalars().all()
                
                mapped_codes = db.execute(text("""
                    SELECT supplier_category_code 
                    FROM supplier_categories_map 
                    WHERE supplier_platform = 'giga'
                """)).scalars().all()
                
                print(f"\n    实际的category_code: {actual_codes}")
                print(f"    映射表的supplier_category_code: {mapped_codes}")
                print("\n  ⚠️  两者不匹配！需要更新映射表数据")

if __name__ == "__main__":
    debug_category_mapping()