"""
Variation Helper
处理变体识别和属性格式化
"""
import logging
import re
from typing import List, Tuple, Dict, Any, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class VariationHelper:
    """
    变体处理助手
    
    职责：
    - 使用图论DFS算法识别变体家族
    - 格式化变体属性（如尺寸取整）
    - 泛化父体标题
    """
    
    def __init__(self):
        """初始化助手"""
        logger.info("变体助手初始化完成")
    
    def find_variation_families(
        self,
        variation_data: List[Tuple[str, str, List[str]]]
    ) -> Tuple[List[str], List[List[str]]]:
        """
        识别变体家族（使用图论DFS算法）
        
        算法说明：
        1. 将变体关系构建为无向图
        2. 使用DFS查找所有连通分量
        3. 单独的节点视为单品，连通分量视为变体家族
        
        Args:
            variation_data: 变体数据列表
                格式：[(meow_sku, vendor_sku, associate_list), ...]
                - meow_sku: 内部SKU
                - vendor_sku: 供应商SKU（图中的节点）
                - associate_list: 关联的供应商SKU列表（图中的边）
        
        Returns:
            元组 (single_products, variation_families)
            - single_products: 单品的meow_sku列表
            - variation_families: 变体家族列表，每个家族是meow_sku列表
        
        Example:
            >>> data = [
            ...     ('MEOW-A', 'VENDOR-A', ['VENDOR-B', 'VENDOR-C']),
            ...     ('MEOW-B', 'VENDOR-B', ['VENDOR-A', 'VENDOR-C']),
            ...     ('MEOW-C', 'VENDOR-C', ['VENDOR-A', 'VENDOR-B']),
            ...     ('MEOW-D', 'VENDOR-D', [])
            ... ]
            >>> single, families = helper.find_variation_families(data)
            >>> print(single)  # ['MEOW-D']
            >>> print(families)  # [['MEOW-A', 'MEOW-B', 'MEOW-C']]
        """
        if not variation_data:
            return [], []
        
        logger.info(f"开始变体识别，总共 {len(variation_data)} 个SKU")
        
        # 1. 构建映射关系
        meow_to_vendor_map = {meow: vendor for meow, vendor, _ in variation_data}
        vendor_to_meow_map = {vendor: meow for meow, vendor, _ in variation_data}
        
        # 2. 构建邻接表（无向图）
        adj_list = defaultdict(list)
        for _, vendor_sku, assoc_list in variation_data:
            if vendor_sku not in adj_list:
                adj_list[vendor_sku] = []
            
            for assoc_vendor_sku in assoc_list:
                if assoc_vendor_sku in vendor_to_meow_map:
                    # 添加双向边
                    if assoc_vendor_sku not in adj_list[vendor_sku]:
                        adj_list[vendor_sku].append(assoc_vendor_sku)
                    if vendor_sku not in adj_list[assoc_vendor_sku]:
                        adj_list[assoc_vendor_sku].append(vendor_sku)
        
        # 3. DFS查找连通分量
        visited = set()
        single_products_meow = []
        variation_families_meow = []
        
        all_vendor_skus = set(vendor_to_meow_map.keys())
        
        for vendor_sku in all_vendor_skus:
            if vendor_sku in visited:
                continue
            
            # 孤立节点（无边）
            if not adj_list.get(vendor_sku):
                single_products_meow.append(vendor_to_meow_map[vendor_sku])
                visited.add(vendor_sku)
            else:
                # 执行DFS找到整个连通分量
                component_vendor = []
                self._dfs(vendor_sku, adj_list, visited, component_vendor)
                
                # 转换为meow_sku
                component_meow = [
                    vendor_to_meow_map[v] 
                    for v in component_vendor 
                    if v in vendor_to_meow_map
                ]
                
                if len(component_meow) > 1:
                    variation_families_meow.append(component_meow)
                else:
                    single_products_meow.extend(component_meow)
        
        logger.info(f"✅ 变体识别完成")
        logger.info(f"   单品: {len(single_products_meow)} 个")
        logger.info(f"   变体家族: {len(variation_families_meow)} 个")
        
        return single_products_meow, variation_families_meow
    
    def _dfs(
        self,
        node: str,
        adj_list: Dict[str, List[str]],
        visited: Set[str],
        component: List[str]
    ):
        """
        深度优先搜索（DFS）
        
        Args:
            node: 当前节点
            adj_list: 邻接表
            visited: 已访问集合
            component: 当前连通分量（输出参数）
        """
        visited.add(node)
        component.append(node)
        
        for neighbor in adj_list.get(node, []):
            if neighbor not in visited:
                self._dfs(neighbor, adj_list, visited, component)
    
    def format_variation_attributes(
        self,
        child_attributes_map: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        格式化变体属性
        
        主要处理：
        1. 尺寸类数值取整（如 19.88 → 20）
        2. 确保数值转为字符串格式
        
        Args:
            child_attributes_map: 子SKU的属性映射
                格式：{meow_sku: {attr_name: attr_value, ...}, ...}
        
        Returns:
            格式化后的属性映射
        
        Example:
            >>> attrs = {
            ...     'SKU-001': {'size_name': '19.88', 'color_name': 'White'},
            ...     'SKU-002': {'size_name': 23.5, 'color_name': 'Black'}
            ... }
            >>> formatted = helper.format_variation_attributes(attrs)
            >>> print(formatted['SKU-001']['size_name'])  # '20'
            >>> print(formatted['SKU-002']['size_name'])  # '24'
        """
        if not child_attributes_map:
            return {}
        
        formatted_map = {}
        
        for sku, attributes in child_attributes_map.items():
            new_attributes = {}
            
            for key, value in attributes.items():
                # 对包含 "size" 的属性进行取整处理
                if "size" in key.lower() and isinstance(value, (int, float, str)):
                    try:
                        # 转为浮点数，四舍五入，转为整数，再转为字符串
                        rounded_value = int(round(float(value)))
                        new_attributes[key] = str(rounded_value)
                    except (ValueError, TypeError):
                        # 转换失败，保持原值
                        new_attributes[key] = value
                else:
                    new_attributes[key] = value
            
            formatted_map[sku] = new_attributes
        
        logger.debug(f"格式化 {len(formatted_map)} 个SKU的变体属性")
        return formatted_map
    
    def generalize_parent_title(self, title: str) -> str:
        """
        泛化父体标题
        
        移除标题中的具体颜色或尺寸描述，使其适合作为父体标题。
        
        策略：
        1. 移除末尾的 "- 颜色/尺寸" 模式（如 "Cabinet - White"）
        2. 保留核心产品描述
        
        Args:
            title: 原始标题
        
        Returns:
            泛化后的标题
        
        Example:
            >>> helper.generalize_parent_title("Modern Cabinet - White")
            'Modern Cabinet'
            >>> helper.generalize_parent_title("Vanity 24 Inch - Black")
            'Vanity 24 Inch'
        """
        if not title:
            return title
        
        # 移除末尾的 "- 单词" 模式
        # 这通常是颜色或风格的描述
        generalized = re.sub(r'\s*-\s*\w+$', '', title, flags=re.IGNORECASE)
        
        logger.debug(f"标题泛化: '{title}' → '{generalized}'")
        return generalized