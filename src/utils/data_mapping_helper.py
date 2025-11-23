"""
Data Mapping Helper
处理产品数据到Amazon字段的映射逻辑
"""
import json
import logging
import re
import difflib
import unicodedata
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class DataMappingHelper:
    """
    数据映射助手
    
    职责：
    - 加载和解析 amz_mapping.json 配置
    - 执行各种类型的字段映射（static, direct, jsonb等）
    - 集成LLM增强字段
    - 提供统一的映射接口
    """
    
    # 单位映射字典
    WEIGHT_UNIT_MAP = {
        "lb": "Pounds",
        "kg": "Kilograms", 
        "oz": "Ounces",
        "g": "Grams"
    }
    
    DIMENSION_UNIT_MAP = {
        "in": "Inches",
        "cm": "Centimeters",
        "mm": "Millimeters",
        "ft": "Feet"
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化映射助手
        
        Args:
            config_path: 配置文件路径，默认自动查找项目根目录
        """
        if config_path is None:
            config_path = self._find_config_path()
        
        self.config_path = config_path
        self.mapping_config = self._load_mapping_config()
        
        logger.info(f"数据映射助手初始化完成，加载 {len(self.mapping_config)} 个字段映射规则")
    
    def _find_config_path(self) -> Path:
        """查找配置文件路径"""
        # 方法1: 从当前文件向上查找项目根目录
        current = Path(__file__).resolve()
        
        for parent in current.parents:
            config_file = parent / "config" / "amz_listing_data_mapping" / "amz_mapping.json"
            if config_file.exists():
                return config_file
        
        # 方法2: 尝试相对于src目录
        src_dir = Path(__file__).resolve().parent.parent  # 从 src/utils 到 src
        project_root = src_dir.parent  # 从 src 到项目根
        config_file = project_root / "config" / "amz_listing_data_mapping" / "amz_mapping.json"
        
        if config_file.exists():
            return config_file
        
        # 方法3: 如果测试从项目根运行
        config_file = Path("config/amz_listing_data_mapping/amz_mapping.json")
        if config_file.exists():
            return config_file.resolve()
        
        raise FileNotFoundError(
            f"未找到 amz_mapping.json 配置文件\n"
            f"当前文件: {Path(__file__)}\n"
            f"尝试路径: {config_file}"
        )
    
    def _load_mapping_config(self) -> Dict:
        """加载映射配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                return config_data.get("mappings", {})
        except Exception as e:
            logger.error(f"❌ 加载映射配置失败: {e}")
            raise
    
    def apply_mapping(
        self,
        product_data: Dict[str, Any],
        template_rules: Dict[str, Any],
        category_map: Optional[Dict] = None,
        llm_service = None  # LLM服务实例（可选）
    ) -> Dict[str, Any]:
        """
        应用映射规则到产品数据
        
        Args:
            product_data: 产品原始数据，包含：
                - meow_sku
                - vendor_sku
                - category_name
                - product_name
                - product_description
                - selling_point_1~5
                - raw_data (JSONB)
                - final_price
                - total_quantity
            template_rules: 模板规则，包含：
                - valid_values
                - variation_mapping
            category_map: 品类映射配置（可选）
            llm_service: LLM服务实例（可选，用于增强字段）
                
        Returns:
            映射后的字段字典
        """
        if not product_data:
            return {}
        
        raw_data = product_data.get("raw_data", {}) or {}
        mapped_data = {}
        llm_tasks = []  # 收集LLM任务
        
        # 第一轮：处理非LLM字段
        for field_name, rule in self.mapping_config.items():
            source_type = rule.get("source_type")
            
            # 收集LLM增强任务
            if source_type == "llm_enhanced":
                llm_tasks.append({
                    "field_name": field_name,
                    "description": rule.get("description", ""),
                    "output_type": rule.get("output_type", "string")
                })
                continue
            
            # 跳过field_reference，稍后处理
            if source_type == "field_reference":
                continue
            
            value = self._map_single_field(
                field_name, rule, product_data, raw_data, category_map
            )
            
            if value is not None:
                mapped_data[field_name] = value
        
        # 第二轮：处理field_reference
        for field_name, rule in self.mapping_config.items():
            if rule.get("source_type") == "field_reference":
                referenced_field = rule.get("field")
                if referenced_field in mapped_data:
                    mapped_data[field_name] = mapped_data[referenced_field]

        # 第三轮：与模板有效值对齐（模糊匹配）
        try:
            valid_values = template_rules.get('valid_values', []) if template_rules else []
            attr_to_values = {
                str(item.get('attribute')).strip(): item.get('values', [])
                for item in valid_values
                if item.get('attribute')
            }
            for field_name, value in list(mapped_data.items()):
                candidates = attr_to_values.get(field_name)
                if not candidates:
                    continue
                if value is None:
                    continue
                if isinstance(value, list):
                    continue
                if not isinstance(value, str):
                    continue
                if value in candidates:
                    continue
                norm_val = self._normalize_text(value)
                exact = next((c for c in candidates if self._normalize_text(str(c)) == norm_val), None)
                if exact is not None:
                    mapped_data[field_name] = exact
                    continue
                match = self._fuzzy_select(value, candidates, cutoff=0.9)
                if match is not None:
                    mapped_data[field_name] = match
                else:
                    pass
        except Exception as e:
            logger.warning(f"有效值对齐失败: {e}")

        # 第四轮：处理LLM增强字段
        if llm_tasks and llm_service:
            try:
                enriched_data = self._enrich_with_llm(
                    product_data,
                    llm_tasks,
                    template_rules,
                    llm_service
                )
                mapped_data.update(enriched_data)
                logger.debug(f"LLM增强完成，添加 {len(enriched_data)} 个字段")
            except Exception as e:
                logger.error(f"LLM增强失败: {e}")

        logger.debug(f"映射完成，生成 {len(mapped_data)} 个字段")
        return mapped_data
    
    def _enrich_with_llm(
        self,
        product_data: Dict[str, Any],
        llm_tasks: List[Dict],
        template_rules: Dict,
        llm_service
    ) -> Dict[str, Any]:
        """
        使用LLM增强产品属性
        
        Args:
            product_data: 产品原始数据
            llm_tasks: LLM任务列表
            template_rules: 模板规则
            llm_service: LLM服务实例
        """
        from infrastructure.llm import LLMRequest
        from src.utils.prompt_manager import PromptManager
        
        raw_data = product_data.get("raw_data", {}) or {}
        
        # 1. 构建产品profile
        product_profile = {
            "name": product_data.get("product_name"),
            "description": self._strip_html(
                product_data.get("product_description") or raw_data.get("description")
            ),
            "attributes": raw_data.get("attributes", {}),
            "characteristics": raw_data.get("characteristics", []),
            "dimensions_and_weight": {
                "assembledLength": raw_data.get("assembledLength"),
                "assembledWidth": raw_data.get("assembledWidth"),
                "assembledHeight": raw_data.get("assembledHeight"),
            }
        }
        
        # 2. 构建标准化的 valid_values_map
        valid_values_map = {
            str(item.get('attribute')).strip().lower(): item.get('values', [])
            for item in template_rules.get('valid_values', [])
            if item.get('attribute')
        }
        
        # 3. 为每个任务添加 valid_options（如果有）
        processed_tasks = []
        for task in llm_tasks:
            field_name = task.get("field_name")
            normalized_field_name = str(field_name).strip().lower()
            
            # 从 valid_values_map 查找
            if normalized_field_name in valid_values_map:
                task["valid_options"] = valid_values_map[normalized_field_name]
            
            processed_tasks.append(task)
        
        # 4. 构建LLM请求
        user_content_data = {
            "product_profile": product_profile,
            "tasks": processed_tasks
        }
        user_content_str = json.dumps(user_content_data, indent=2, ensure_ascii=False)
        
        # 5. 获取Prompt
        prompt_manager = PromptManager()
        system_prompt = prompt_manager.get_prompt('prod_attribute_enrichment')
        
        if not system_prompt:
            logger.error("未找到 prod_attribute_enrichment Prompt")
            return {}
        
        # 6. 调用LLM
        try:
            request = LLMRequest(
                task_type='product_attribute_enrichment',
                system_prompt=system_prompt,
                user_prompt=user_content_str,
                json_mode=True,
                temperature=0.7
            )
            
            response = llm_service.generate(request)
            llm_result = response.content
            
            logger.info(f"LLM成功生成 {len(llm_result)} 个增强字段")
            return llm_result
            
        except Exception as e:
            logger.error(f"调用LLM失败: {e}", exc_info=True)
            return {}
    
    @staticmethod
    def _strip_html(html_string: Optional[str]) -> str:
        """移除HTML标签"""
        if not html_string:
            return ""
        clean_text = re.sub(r'<[^>]+>', '', html_string)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        return clean_text
    
    def _map_single_field(
        self,
        field_name: str,
        rule: Dict,
        product_data: Dict,
        raw_data: Dict,
        category_map: Optional[Dict]
    ) -> Any:
        """映射单个字段"""
        source_type = rule.get("source_type")
        
        # 静态值
        if source_type == "static":
            return rule.get("value")
        
        # 直接字段
        elif source_type == "direct":
            value = product_data.get(rule.get("value"))
            # 特殊处理：Product Type转大写
            if field_name == "Product Type" and isinstance(value, str):
                return value.upper()
            return value
        
        # 数据库字段
        elif source_type == "db_field":
            return product_data.get(rule.get("field"))
        
        # 多个数据库字段
        elif source_type == "db_field_multiple":
            fields = rule.get("fields", [])
            return [product_data.get(f) for f in fields if product_data.get(f)]
        
        # JSONB字段
        elif source_type == "jsonb":
            value = self._get_jsonb_value(raw_data, rule.get("json_path"))
            if value in (None, "", "Not Applicable"):
                fallback = rule.get("fallback")
                return fallback if fallback is not None else value
            return value
        
        # JSONB数组
        elif source_type == "jsonb_array":
            return raw_data.get(rule.get("json_path"), [])
        
        # JSONB计算值
        elif source_type == "jsonb_computed":
            combo_info = raw_data.get(rule.get("json_path"), [])
            return len(combo_info) if combo_info else 1
        
        # 包装尺寸
        elif source_type == "package_dimension":
            dim = rule.get("dimension")
            combo_info = raw_data.get("comboInfo", [])
            value = raw_data.get(dim)
            if not value and combo_info:
                value = combo_info[0].get(dim)
            return value
        
        # 产品尺寸
        elif source_type == "item_dimension":
            dim = rule.get("dimension")
            value = raw_data.get(dim)
            if value == "Not Applicable":
                return None
            return value
        
        # 单位映射
        elif source_type == "unit_mapper":
            return self._map_unit(rule.get("unit_type"), raw_data)
        
        # 重量求和
        elif source_type == "summed_weight":
            return self._calculate_weight(rule.get("weight_type"), raw_data)
        
        # 品类查找
        elif source_type == "category_lookup":
            if not category_map:
                return None
            current_category = product_data.get("category_name", "").upper()
            lookup_key = rule.get("lookup_key")
            if current_category and lookup_key:
                return category_map.get(current_category, {}).get(lookup_key)
        
        # 未知类型
        else:
            logger.warning(f"未知的source_type: {source_type} (字段: {field_name})")
            return None
    
    def _get_jsonb_value(self, raw_data: Dict, json_path: str) -> Any:
        """从JSONB中提取值"""
        if not json_path:
            return None
        
        path_keys = json_path.split('.')
        temp_value = raw_data
        
        for key in path_keys:
            if isinstance(temp_value, dict):
                temp_value = temp_value.get(key)
            else:
                return None
            
            if temp_value is None:
                break
        
        return temp_value

    @staticmethod
    def _normalize_text(text: str) -> str:
        s = str(text)
        s = unicodedata.normalize('NFKC', s)
        s = s.casefold()
        s = re.sub(r"\s+", " ", s).strip()
        s = s.replace("-", " ")
        s = s.replace("_", " ")
        s = s.replace("  ", " ")
        return s

    @staticmethod
    def _fuzzy_select(value: str, candidates: List[str], cutoff: float = 0.9) -> Optional[str]:
        norm_candidates = {DataMappingHelper._normalize_text(c): c for c in candidates}
        norm_value = DataMappingHelper._normalize_text(value)
        pool = list(norm_candidates.keys())
        matches = difflib.get_close_matches(norm_value, pool, n=1, cutoff=cutoff)
        if matches:
            return norm_candidates[matches[0]]
        return None
    
    def _map_unit(self, unit_type: str, raw_data: Dict) -> Optional[str]:
        """映射单位"""
        if unit_type == "weight":
            raw_unit = raw_data.get("weightUnit")
            return self.WEIGHT_UNIT_MAP.get(str(raw_unit).lower())
        
        elif unit_type == "dimension":
            raw_unit = raw_data.get("lengthUnit")
            return self.DIMENSION_UNIT_MAP.get(str(raw_unit).lower())
        
        return None
    
    def _calculate_weight(self, weight_type: str, raw_data: Dict) -> Optional[float]:
        """计算重量"""
        if weight_type == "item":
            total_weight = raw_data.get("assembledWeight")
        else:
            total_weight = raw_data.get("weight")
        
        # 如果没有重量且是组合商品，求和
        if not total_weight and raw_data.get("comboFlag"):
            combo_info = raw_data.get("comboInfo", [])
            total_weight = sum(item.get("weight", 0) for item in combo_info)
        
        return total_weight if total_weight else None
    
    def get_llm_tasks(self, template_rules: Dict) -> List[Dict]:
        """
        提取需要LLM处理的字段任务
        
        Args:
            template_rules: 模板规则
            
        Returns:
            LLM任务列表，每个任务包含：
            {
                'field_name': 字段名,
                'description': 任务描述,
                'output_type': 输出类型,
                'valid_options': 有效选项（可选）
            }
        """
        llm_tasks = []
        
        # 标准化valid_values映射（不区分大小写和空格）
        valid_values_map = {}
        for item in template_rules.get('valid_values', []):
            attr = item.get('attribute')
            if attr:
                normalized_key = str(attr).strip().lower()
                valid_values_map[normalized_key] = item.get('values', [])
        
        # 提取LLM字段
        for field_name, rule in self.mapping_config.items():
            if rule.get("source_type") == "llm_enhanced":
                task = {
                    "field_name": field_name,
                    "description": rule.get("description", ""),
                    "output_type": rule.get("output_type", "string")
                }
                
                # 检查是否有有效值约束
                normalized_field = str(field_name).strip().lower()
                if normalized_field in valid_values_map:
                    task["valid_options"] = valid_values_map[normalized_field]
                
                llm_tasks.append(task)
        
        logger.debug(f"提取 {len(llm_tasks)} 个LLM任务")
        return llm_tasks
