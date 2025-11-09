#!/usr/bin/env python
"""调试Giga价格API返回数据"""
import json
import os
from datetime import datetime
from collections import Counter
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path('.env'))

from infrastructure.giga.api_client import GigaAPIClient
from infrastructure.db_pool import SessionLocal
from src.repositories.giga_product_price_repository import GigaProductPriceRepository

def analyze_price_api():
    """分析价格API返回数据"""
    
    print("=" * 60)
    print("🔍 Giga价格API数据分析")
    print("=" * 60)
    
    # 1. 获取SKU列表
    with SessionLocal() as session:
        repo = GigaProductPriceRepository(session)
        all_skus = repo.get_all_skus()
    
    # 只取前50个SKU用于测试
    test_skus = all_skus[:50]
    
    print(f"\n📊 测试SKU数量: {len(test_skus)}")
    print(f"示例SKU: {test_skus[:5]}")
    
    # 2. 调用API
    print(f"\n⏳ 正在调用API...")
    client = GigaAPIClient()
    
    try:
        payload = {"skus": test_skus}
        response = client.execute("product_price", payload, method="POST")
        
        body = response.get('body', {})
        if not body.get('success'):
            print(f"❌ API返回错误: {body.get('error')}")
            return
        
        prices = body.get('data', [])
        print(f"✅ API响应成功，返回 {len(prices)} 条数据")
        
    except Exception as e:
        print(f"❌ API调用失败: {e}")
        return
    
    # 3. 分析重复
    print("\n" + "=" * 60)
    print("📊 数据分析")
    print("=" * 60)
    
    # 统计SKU出现次数
    sku_counter = Counter(item.get('sku') for item in prices)
    
    total_items = len(prices)
    unique_skus = len(sku_counter)
    duplicates = sum(1 for count in sku_counter.values() if count > 1)
    
    print(f"\n总数据条数: {total_items}")
    print(f"唯一SKU数: {unique_skus}")
    print(f"重复SKU数: {duplicates}")
    print(f"重复率: {duplicates/unique_skus*100:.1f}%")
    
    # 4. 显示重复的SKU详情
    if duplicates > 0:
        print("\n" + "=" * 60)
        print("⚠️  重复SKU详细信息")
        print("=" * 60)
        
        for sku, count in sku_counter.items():
            if count > 1:
                print(f"\n【SKU: {sku}】出现 {count} 次")
                
                # 找出所有该SKU的数据
                sku_items = [item for item in prices if item.get('sku') == sku]
                
                for idx, item in enumerate(sku_items, 1):
                    print(f"\n  --- 记录 {idx} ---")
                    print(f"  价格: {item.get('price')}")
                    print(f"  可用: {item.get('skuAvailable')}")
                    
                    seller_info = item.get('sellerInfo', {})
                    print(f"  供应商: {seller_info.get('sellerStore')}")
                    print(f"  供应商代码: {seller_info.get('sellerCode')}")
                    print(f"  Giga指数: {seller_info.get('gigaIndex')}")
                    
                    # 显示差异字段
                    if idx > 1:
                        diff_fields = []
                        prev_item = sku_items[idx-2]
                        
                        for key in ['price', 'shippingFee', 'skuAvailable', 'exclusivePrice']:
                            if item.get(key) != prev_item.get(key):
                                diff_fields.append(f"{key}: {prev_item.get(key)} → {item.get(key)}")
                        
                        if diff_fields:
                            print(f"  🔄 差异: {', '.join(diff_fields)}")
                
                print()
    
    # 5. 保存原始数据
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "debug_output"
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, f"price_api_debug_{timestamp}.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "request": {
                "skus": test_skus,
                "count": len(test_skus)
            },
            "response": {
                "total_items": total_items,
                "unique_skus": unique_skus,
                "duplicates": duplicates,
                "data": prices
            },
            "analysis": {
                "sku_counts": dict(sku_counter),
                "duplicate_skus": [sku for sku, count in sku_counter.items() if count > 1]
            }
        }, f, indent=2, ensure_ascii=False)
    
    print("=" * 60)
    print(f"✅ 原始数据已保存到: {output_file}")
    print("=" * 60)
    
    # 6. 建议
    if duplicates > 0:
        print("\n💡 建议:")
        print("1. 同一个SKU有多个供应商提供")
        print("2. 可以按 gigaIndex 或 price 选择最优供应商")
        print("3. 当前代码保留最后一条（可能不是最优的）")
    else:
        print("\n✅ 没有发现重复SKU")

if __name__ == "__main__":
    analyze_price_api()
