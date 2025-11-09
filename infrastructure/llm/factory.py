"""LLM服务工厂"""
import os
import logging
from typing import Dict
from infrastructure.llm.interface import LLMServiceInterface
from infrastructure.llm.implementations.direct_llm_service import DirectLLMService

logger = logging.getLogger(__name__)

_service_instance = None

def get_llm_service() -> LLMServiceInterface:
    """获取LLM服务单例"""
    global _service_instance
    
    if _service_instance is not None:
        return _service_instance
    
    # 从环境变量决定模式
    mode = os.getenv('LLM_SERVICE_MODE', 'direct')
    
    if mode == 'agent':
        # 未来实现
        raise NotImplementedError("Agent模式尚未实现")
    else:
        config = _load_direct_config()
        _service_instance = DirectLLMService(config)
        logger.info("LLM服务初始化完成（Direct模式）")
    
    return _service_instance

def _load_direct_config() -> Dict:
    """加载Direct模式配置"""
    return {
        'default_provider': os.getenv('LLM_PROVIDER', 'qwen'),
        'providers': {
            'deepseek': {
                'default_model': os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
            },
            'qwen': {
                'default_model': os.getenv('QWEN_MODEL', 'qwen-plus-latest')
            }
        },
        'task_routing': {
            'product_generation': os.getenv('LLM_PROVIDER', 'qwen'),
            'sku_mapping': 'qwen'
        }
    }