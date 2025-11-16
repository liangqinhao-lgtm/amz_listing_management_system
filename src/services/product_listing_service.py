"""
Product Listing Service
产品发品服务，整合所有Repository和Helper
"""
import logging
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from sqlalchemy.orm import Session

from src.repositories.product_listing_repository import ProductListingRepository
from src.repositories.product_data_repository import ProductDataRepository
from src.repositories.amz_template_repository import AmzTemplateRepository
from src.repositories.amz_listing_log_repository import AmzListingLogRepository
from src.utils.data_mapping_helper import DataMappingHelper
from src.utils.excel_generator import ExcelGenerator
from src.utils.variation_helper import VariationHelper

logger = logging.getLogger(__name__)


class ProductListingService:
    """
    产品发品服务
    
    职责：
    - 协调所有Repository和Helper
    - 实现完整的发品流程
    - 处理单品和变体的不同逻辑
    - 集成LLM增强功能
    """
    
    def __init__(
        self,
        db: Session,
        mapping_config_path: Optional[Path] = None,
        category_config_path: Optional[Path] = None
    ):
        """
        初始化服务
        
        Args:
            db: 数据库Session
            mapping_config_path: 映射配置文件路径
            category_config_path: 品类配置文件路径
        """
        # 初始化所有Repository
        self.product_listing_repo = ProductListingRepository(db)
        self.product_data_repo = ProductDataRepository(db)
        self.template_repo = AmzTemplateRepository(db)
        self.listing_log_repo = AmzListingLogRepository(db)
        
        # 初始化所有Helper
        self.data_mapper = DataMappingHelper(config_path=mapping_config_path)
        self.excel_generator = ExcelGenerator()
        self.variation_helper = VariationHelper()
        
        # 加载品类配置（如果提供）
        self.category_config = self._load_category_config(category_config_path)
        
        # 初始化LLM服务
        try:
            from infrastructure.llm import get_llm_service
            self.llm_service = get_llm_service()
            logger.info("LLM服务初始化成功")
        except Exception as e:
            logger.warning(f"LLM服务初始化失败: {e}，将跳过LLM增强字段")
            self.llm_service = None
        
        # 初始化变体主题服务
        try:
            from src.services.variation_theme_service import VariationThemeService
            self.variation_theme_service = VariationThemeService()
            logger.info("变体主题服务初始化成功")
        except Exception as e:
            logger.warning(f"变体主题服务初始化失败: {e}")
            self.variation_theme_service = None
        
        self.db = db
        
        logger.info("ProductListingService 初始化完成")
    
    def _load_category_config(self, config_path: Optional[Path]) -> Optional[Dict]:
        """加载品类配置"""
        if config_path is None:
            # 尝试自动查找
            try:
                current = Path(__file__).resolve()
                for parent in current.parents:
                    config_file = parent / "config" / "amz_listing_data_mapping" / "category_mapping.json"
                    if config_file.exists():
                        config_path = config_file
                        break
            except:
                return None
        
        if config_path and config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 提取 category_details 部分
                    return config.get("category_details", {})
            except Exception as e:
                logger.warning(f"加载品类配置失败: {e}")
                return None
        
        return None
    
    def generate_listings_by_category(self, category_name: str) -> Dict[str, Any]:
        """
        按品类生成发品文件
        
        这是主要的业务流程方法。
        
        Args:
            category_name: 品类名称（如 'CABINET', 'HOME_MIRROR'）
        
        Returns:
            结果字典：
            {
                'success': bool,
                'batch_id': uuid,
                'excel_file': str,
                'single_count': int,
                'variation_count': int,
                'total_rows': int,
                'message': str
            }
        """
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"开始生成品类 '{category_name}' 的发品文件")
            logger.info(f"{'='*60}")
            
            batch_id = uuid.uuid4()
            
            # 步骤1: 获取所有待发品SKU
            logger.info("步骤1: 获取所有待发品SKU...")
            all_pending_skus = self.product_listing_repo.get_pending_listing_skus()
            
            if not all_pending_skus:
                return {
                    'success': False,
                    'message': "没有待发品SKU"
                }
            
            logger.info(f"  找到 {len(all_pending_skus)} 个待发品SKU")
            
            # 步骤2: 获取SKU到品类的映射
            logger.info("步骤2: 获取SKU品类映射...")
            sku_category_mapping = self.product_listing_repo.get_sku_to_category_mapping(all_pending_skus)
            
            # 步骤3: 过滤出指定品类的SKU
            logger.info(f"步骤3: 过滤品类 '{category_name}'...")
            pending_skus = [
                sku for sku, cat in sku_category_mapping 
                if cat and cat.upper() == category_name.upper()
            ]
            
            if not pending_skus:
                return {
                    'success': False,
                    'message': f"品类 '{category_name}' 没有待发品SKU"
                }
            
            logger.info(f"  品类 '{category_name}' 有 {len(pending_skus)} 个待发品SKU")
            
            # 步骤4: 获取变体关联数据
            logger.info("步骤4: 获取变体关联数据...")
            variation_data = self.product_listing_repo.get_variation_data(pending_skus)
            
            # 步骤5: 识别变体家族
            logger.info("步骤5: 识别变体家族...")
            single_skus, variation_families = self.variation_helper.find_variation_families(variation_data)
            
            logger.info(f"  单品: {len(single_skus)} 个")
            logger.info(f"  变体家族: {len(variation_families)} 个")
            
            # 步骤6: 获取品类模板规则
            logger.info("步骤6: 加载品类模板...")
            template_rules = self.template_repo.find_template_by_category(category_name)
            
            if not template_rules:
                return {
                    'success': False,
                    'message': f"品类 '{category_name}' 没有模板规则"
                }
            
            # 步骤7: 处理单品
            logger.info("步骤7: 处理单品...")
            single_rows = self._process_single_products(single_skus, template_rules)
            
            # 步骤8: 处理变体
            logger.info("步骤8: 处理变体家族...")
            variation_rows, variation_logs = self._process_variations(
                variation_families, 
                template_rules
            )
            
            # 步骤9: 合并所有行
            all_rows = single_rows + variation_rows
            
            if not all_rows:
                return {
                    'success': False,
                    'message': "没有生成任何数据行"
                }
            
            logger.info(f"  总共生成 {len(all_rows)} 行数据")
            
            # 步骤10: 生成Excel文件
            logger.info("步骤10: 生成Excel文件...")
            excel_file = self.excel_generator.generate_excel(
                rows_data=all_rows,
                category_name=category_name,
                batch_id=batch_id
            )
            
            # 步骤11: 记录日志
            logger.info("步骤11: 记录发品日志...")
            self._save_listing_logs(single_skus, variation_logs, batch_id)
            
            self.db.commit()
            
            logger.info(f"\n{'='*60}")
            logger.info(f"✅ 发品文件生成成功！")
            logger.info(f"{'='*60}")
            
            return {
                'success': True,
                'batch_id': batch_id,
                'excel_file': excel_file,
                'single_count': len(single_skus),
                'variation_count': len(variation_families),
                'total_rows': len(all_rows),
                'message': f"成功生成 {len(all_rows)} 行数据"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ 生成发品文件失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f"生成失败: {str(e)}"
            }
    
    def _process_single_products(
        self,
        meow_skus: List[str],
        template_rules: Dict
    ) -> List[Dict[str, Any]]:
        """
        处理单品
        
        Args:
            meow_skus: 单品的meow_sku列表
            template_rules: 模板规则
        
        Returns:
            数据行列表
        """
        rows = []
        
        for meow_sku in meow_skus:
            try:
                # 获取产品数据
                product_data = self.product_data_repo.get_full_product_data(meow_sku)
                
                if not product_data:
                    logger.warning(f"  跳过SKU {meow_sku}: 无数据")
                    continue
                
                # 应用映射（传入LLM服务）
                mapped_data = self.data_mapper.apply_mapping(
                    product_data,
                    template_rules,
                    self.category_config,
                    self.llm_service
                )
                
                # 添加单品特定字段
                mapped_data['Listing Action'] = 'Create or Replace (Full Update)'
                
                rows.append(mapped_data)
                
            except Exception as e:
                logger.error(f"  处理单品 {meow_sku} 失败: {e}")
                continue
        
        logger.info(f"  成功处理 {len(rows)}/{len(meow_skus)} 个单品")
        return rows
    
    def _process_variations(
        self,
        families: List[List[str]],
        template_rules: Dict
    ) -> Tuple[List[Dict[str, Any]], List[Dict]]:
        """
        处理变体家族
        
        Args:
            families: 变体家族列表
            template_rules: 模板规则
        
        Returns:
            (数据行列表, 日志数据列表)
        """
        rows = []
        logs = []
        
        for family in families:
            try:
                family_rows, family_logs = self._process_single_family(family, template_rules)
                rows.extend(family_rows)
                logs.extend(family_logs)
            except Exception as e:
                logger.error(f"  处理变体家族失败: {e}")
                continue
        
        logger.info(f"  成功处理 {len(families)} 个变体家族，生成 {len(rows)} 行")
        return rows, logs
    
    def _process_single_family(
        self,
        family_skus: List[str],
        template_rules: Dict
    ) -> Tuple[List[Dict[str, Any]], List[Dict]]:
        """处理单个变体家族"""
        rows = []
        logs = []
        
        # 生成父SKU
        parent_sku = f"PARENT-{uuid.uuid4().hex[:12].upper()}"
        
        # 1. 获取所有子SKU的完整数据
        family_full_data = []
        for sku in family_skus:
            product_data = self.product_data_repo.get_full_product_data(sku)
            if product_data:
                family_full_data.append(product_data)
        
        if not family_full_data:
            logger.warning(f"  跳过家族: 无法获取任何SKU数据")
            return rows, logs
        
        # 2. 使用LLM判定变体主题和属性
        variation_theme = None
        child_attributes_map = {}
        
        if self.variation_theme_service:
            try:
                # 获取有效的变体主题列表
                valid_themes = self._extract_valid_themes(template_rules)
                priority_themes = template_rules.get('priority_themes', [])
                
                logger.info(f"  调用LLM判定变体主题...")
                llm_result = self.variation_theme_service.determine_variation_theme(
                    family_full_data,
                    valid_themes,
                    priority_themes
                )
                
                variation_theme = llm_result.get('variation_theme')
                child_attributes_map = llm_result.get('child_attributes', {})
                
                logger.info(f"  变体主题: {variation_theme}")
                
            except Exception as e:
                logger.error(f"  变体主题判定失败: {e}")
        
        # 3. 获取变体属性映射规则
        variation_mapping = template_rules.get('variation_mapping', {})
        
        # 4. 生成父体行
        first_product = family_full_data[0]
        parent_row = self.data_mapper.apply_mapping(
            first_product,
            template_rules,
            self.category_config,
            self.llm_service
        )
        
        parent_row['SKU'] = parent_sku
        parent_row['Listing Action'] = 'Create or Replace (Full Update)'
        parent_row['Relationship Type'] = 'Parent'
        
        # 添加变体主题
        if variation_theme:
            parent_row['Variation Theme'] = variation_theme
        
        # 泛化标题
        if 'Item Name' in parent_row:
            parent_row['Item Name'] = self.variation_helper.generalize_parent_title(
                parent_row['Item Name']
            )
        
        rows.append(parent_row)
        
        # 5. 生成所有子体行
        for child_sku in family_skus:
            child_product = self.product_data_repo.get_full_product_data(child_sku)
            
            if not child_product:
                continue
            
            child_row = self.data_mapper.apply_mapping(
                child_product,
                template_rules,
                self.category_config,
                self.llm_service
            )
            
            child_row['Listing Action'] = 'Create or Replace (Full Update)'
            child_row['Relationship Type'] = 'Child'
            child_row['Parent SKU'] = parent_sku
            
            # 添加变体属性
            if child_sku in child_attributes_map:
                # 获取内部属性（如 {'color_name': 'White', 'size_name': '36'}）
                internal_attributes = child_attributes_map[child_sku]
                
                # 转换为Amazon字段名（如 {'Color': 'White', 'Size': '36'}）
                amazon_attributes = {
                    variation_mapping.get(k, k): v 
                    for k, v in internal_attributes.items()
                    if variation_mapping.get(k)
                }
                
                # 合并到子体行
                child_row.update(amazon_attributes)
            
            rows.append(child_row)
            
            # 记录日志
            logs.append({
                'meow_sku': child_sku,
                'parent_sku': parent_sku,
                'variation_attributes': child_attributes_map.get(child_sku, {}),
                'listing_batch_id': None,
                'status': 'GENERATED',
                'variation_theme': variation_theme
            })
        
        return rows, logs
    
    def _extract_valid_themes(self, template_rules: Dict) -> List[str]:
        """
        从模板规则中提取有效的变体主题列表
        
        Args:
            template_rules: 模板规则
        
        Returns:
            有效主题列表，如 ['Color', 'Size', 'Color/Size', 'Material']
        """
        # 从 valid_values 中查找 Variation Theme Name 的有效值
        for item in template_rules.get('valid_values', []):
            if item.get('attribute') == 'Variation Theme Name':
                return item.get('values', [])
        
        # 如果没找到，返回常见主题
        return ['Color', 'Size', 'Color/Size']
    
    def _save_listing_logs(
        self,
        single_skus: List[str],
        variation_logs: List[Dict],
        batch_id: uuid.UUID
    ):
        """保存发品日志"""
        all_logs = []
        
        # 单品日志 - 使用固定标识符表示单品
        for sku in single_skus:
            all_logs.append({
                'meow_sku': sku,
                'parent_sku': 'SINGLE_PRODUCT',  # 固定标识：表示这是单品
                'variation_attributes': {},
                'listing_batch_id': batch_id,
                'status': 'GENERATED',
                'variation_theme': None
            })
        
        # 变体日志
        for log in variation_logs:
            log['listing_batch_id'] = batch_id
            all_logs.append(log)
        
        if all_logs:
            self.listing_log_repo.bulk_insert_log(all_logs)
            logger.info(f"  保存了 {len(all_logs)} 条日志")
