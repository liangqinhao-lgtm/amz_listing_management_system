"""
Amazon Listing Management System - Main Entry Point
主程序入口
"""
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from infrastructure.db_pool import db_manager
from src.services.product_listing_service import ProductListingService


# 配置日志
def setup_logging(log_level: str = "INFO"):
    """配置日志系统"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 设置根日志级别
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # 为特定模块设置日志级别
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


def generate_listing(category: str):
    """
    生成指定品类的发品文件
    
    Args:
        category: 品类名称（如 CABINET, HOME_MIRROR）
    """
    print("\n" + "="*70)
    print(f"🚀 Amazon Listing Management System")
    print(f"📦 品类: {category}")
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    try:
        with db_manager.session_scope() as session:
            # 初始化服务
            service = ProductListingService(db=session)
            
            # 生成发品文件
            result = service.generate_listings_by_category(category)
            
            # 显示结果
            print("\n" + "="*70)
            if result['success']:
                print("✅ 发品文件生成成功！")
                print("="*70)
                print(f"📊 统计信息:")
                print(f"   - 单品数量: {result.get('single_count', 0)}")
                print(f"   - 变体家族: {result.get('variation_count', 0)}")
                print(f"   - 总行数: {result.get('total_rows', 0)}")
                print(f"   - 批次ID: {result.get('batch_id', 'N/A')}")
                
                if 'excel_file' in result:
                    print(f"\n📁 输出文件:")
                    print(f"   {result['excel_file']}")
                
                print("="*70)
                return 0
            else:
                print("❌ 发品文件生成失败")
                print("="*70)
                print(f"💡 原因: {result.get('message', '未知错误')}")
                print("="*70)
                return 1
                
    except KeyboardInterrupt:
        print("\n\n⚠️  操作被用户中断")
        return 130
        
    except Exception as e:
        print("\n" + "="*70)
        print("❌ 系统错误")
        print("="*70)
        print(f"错误信息: {str(e)}")
        print("="*70)
        logging.exception("系统错误详情:")
        return 1


def list_categories():
    """列出所有可用的品类"""
    print("\n" + "="*70)
    print("📋 可用品类列表")
    print("="*70)
    
    try:
        with db_manager.session_scope() as session:
            from sqlalchemy import text
            
            # 查询所有品类
            query = text("""
                SELECT DISTINCT standard_category_name
                FROM supplier_categories_map
                WHERE supplier_platform = 'giga'
                  AND standard_category_name IS NOT NULL
                ORDER BY standard_category_name;
            """)
            
            result = session.execute(query).scalars().all()
            
            if result:
                for i, category in enumerate(result, 1):
                    print(f"   {i}. {category}")
                print(f"\n总计: {len(result)} 个品类")
            else:
                print("   暂无品类数据")
            
            print("="*70)
            return 0
            
    except Exception as e:
        print(f"❌ 查询品类失败: {e}")
        return 1


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Amazon Listing Management System - 发品管理系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s -c CABINET              # 生成 CABINET 品类的发品文件
  %(prog)s -c HOME_MIRROR          # 生成 HOME_MIRROR 品类的发品文件
  %(prog)s --list                  # 列出所有可用品类
  %(prog)s -c CABINET --log DEBUG  # 使用DEBUG日志级别
        """
    )
    
    parser.add_argument(
        '-c', '--category',
        type=str,
        help='品类名称（如 CABINET, HOME_MIRROR）'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='列出所有可用品类'
    )
    
    parser.add_argument(
        '--log',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='日志级别（默认: INFO）'
    )
    
    args = parser.parse_args()
    
    # 配置日志
    setup_logging(args.log)
    
    # 执行命令
    if args.list:
        return list_categories()
    
    elif args.category:
        return generate_listing(args.category)
    
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())