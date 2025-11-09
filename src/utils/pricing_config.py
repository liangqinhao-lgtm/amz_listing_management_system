"""定价配置加载器"""
import yaml
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PricingConfigLoader:
    """定价配置加载器"""
    
    _config: Optional[Dict[str, Any]] = None
    _config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'config', 'pricing', 'amz_pricing_config.yaml'
    )
    
    @classmethod
    def _load_config(cls) -> Dict[str, Any]:
        """加载YAML配置文件，并缓存结果"""
        if cls._config is None:
            logger.info(f"正在加载定价配置文件: {cls._config_path}")
            try:
                with open(cls._config_path, 'r', encoding='utf-8') as f:
                    cls._config = yaml.safe_load(f)
                logger.info("定价配置文件加载成功")
            except FileNotFoundError:
                logger.error(f"找不到定价配置文件: {cls._config_path}")
                raise
            except Exception as e:
                logger.error(f"解析定价配置文件时出错: {e}")
                raise
        return cls._config
    
    @classmethod
    def get_params_for_category(cls, category_name: Optional[str]) -> Dict[str, Any]:
        """
        获取指定品类的定价参数
        
        Args:
            category_name: 品类名称，如果为None则使用fallback配置
            
        Returns:
            定价参数字典
        """
        config = cls._load_config()
        fallback_params = config.get('fallback', {})
        
        # 如果没有品类名或品类未配置，使用fallback
        if not category_name:
            return fallback_params
        
        # 获取品类特定配置
        category_params = config.get('categories', {}).get(category_name.lower(), {})
        
        # 合并配置：fallback为基础，品类配置覆盖
        final_params = {**fallback_params, **category_params}
        
        return final_params
