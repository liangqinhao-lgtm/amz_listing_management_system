"""数据清洗工具（智能截断版）"""
import re
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

class DataCleaner:
    """数据清洗工具类"""
    
    # 高优先级字段（必须保留）
    PRIORITY_FIELDS = [
        'sku', 'name', 'title', 'categoryCode', 'category',
        'brand', 'price', 'cost', 'mainAttributes', 
        'specifications', 'dimensions', 'weight', 'material',
        'color', 'size', 'model', 'features'
    ]
    
    # 低优先级字段（优先删除）
    LOW_PRIORITY_FIELDS = [
        'imageUrls', 'images', 'pictures', 'photos',
        'relatedProducts', 'recommendations', 'reviews',
        'seoKeywords', 'metadata', 'analytics', 'statistics'
    ]
    
    @staticmethod
    def deep_clean(data: Any) -> Any:
        """递归清理数据（移除图片URL和HTML）"""
        if isinstance(data, dict):
            # 移除低优先级字段
            cleaned = {
                key: DataCleaner.deep_clean(value) 
                for key, value in data.items() 
                if key not in DataCleaner.LOW_PRIORITY_FIELDS
            }
            return cleaned
        elif isinstance(data, list):
            return [DataCleaner.deep_clean(item) for item in data]
        elif isinstance(data, str):
            return DataCleaner.clean_text(data)
        else:
            return data
    
    @staticmethod
    def clean_text(text: str) -> str:
        """清理文本中的HTML标签和图片URL"""
        if not text:
            return text
        
        # 移除包含图片的div块
        text = re.sub(
            r'<div[^>]*>[\s\S]*?<img[\s\S]*?>[\s\S]*?</div>', 
            '', 
            text, 
            flags=re.IGNORECASE
        )
        
        # 移除img标签
        text = re.sub(r'<img\b[^>]*>', '', text, flags=re.IGNORECASE)
        
        # 移除所有HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除图片URL
        text = re.sub(
            r'https?://[^\s]+?\.(jpg|jpeg|png|gif|bmp|webp|svg)\b', 
            '', 
            text, 
            flags=re.IGNORECASE
        )
        
        # 清理多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    @staticmethod
    def smart_truncate(data: dict, max_json_length: int = 10000) -> str:
        """
        智能截断：优先保留重要字段，确保JSON完整性
        
        Args:
            data: 原始数据字典
            max_json_length: 最大JSON字符串长度（默认10000）
            
        Returns:
            截断后的JSON字符串
        """
        # 1. 先尝试直接转换
        current_json = json.dumps(data, ensure_ascii=False, indent=2)
        if len(current_json) <= max_json_length:
            return current_json
        
        original_len = len(current_json)
        logger.info(f"数据过长({original_len}字符)，开始智能截断（目标: {max_json_length}字符）...")
        
        # 2. 第一步：截断长描述字段
        for key in list(data.keys()):
            if any(keyword in key.lower() for keyword in ['description', 'detail', 'introduction', 'content']):
                if isinstance(data[key], str) and len(data[key]) > 1000:
                    original_field_len = len(data[key])
                    data[key] = data[key][:1000] + "..."
                    logger.debug(f"截断字段 '{key}': {original_field_len} → 1000字符")
        
        # 3. 检查是否满足要求
        current_json = json.dumps(data, ensure_ascii=False, indent=2)
        if len(current_json) <= max_json_length:
            logger.info(f"✅ 智能截断成功: {original_len} → {len(current_json)}字符")
            return current_json
        
        # 4. 第二步：删除非核心的长字段
        filtered_data = {}
        for key, value in data.items():
            # 保留所有高优先级字段
            if any(priority in key.lower() for priority in DataCleaner.PRIORITY_FIELDS):
                filtered_data[key] = value
            # 保留短字段
            elif len(str(value)) < 500:
                filtered_data[key] = value
            else:
                logger.debug(f"删除长字段 '{key}' (长度: {len(str(value))})")
        
        current_json = json.dumps(filtered_data, ensure_ascii=False, indent=2)
        if len(current_json) <= max_json_length:
            logger.info(f"✅ 删除长字段后: {original_len} → {len(current_json)}字符")
            return current_json
        
        # 5. 第三步：只保留核心字段
        core_fields = ['sku', 'name', 'brand', 'categoryCode', 'mainAttributes', 'specifications']
        core_data = {k: v for k, v in filtered_data.items() if k in core_fields}
        
        current_json = json.dumps(core_data, ensure_ascii=False, indent=2)
        logger.warning(f"⚠️ 仅保留核心字段: {original_len} → {len(current_json)}字符")
        
        # 6. 最后手段：强制截断但保持JSON格式
        if len(current_json) > max_json_length:
            truncated = current_json[:max_json_length-100]
            # 找到最后一个完整的字段
            last_comma = truncated.rfind(',')
            if last_comma > 0:
                truncated = truncated[:last_comma]
            # 添加截断标记并闭合JSON
            truncated += ',\n  "__truncated__": true,\n  "__original_length__": ' + str(original_len) + '\n}'
            logger.error(f"❌ 强制截断: {original_len} → {len(truncated)}字符")
            return truncated
        
        return current_json
    
    @staticmethod
    def truncate_data(data: str, max_length: int = 10000) -> str:
        """
        简单截断（保留作为备用）
        
        Args:
            data: 字符串数据
            max_length: 最大长度（默认10000）
        """
        if len(data) > max_length:
            logger.warning(f"数据过长({len(data)}字符)，简单截断至{max_length}字符")
            return data[:max_length] + "\n...(已截断)"
        return data
