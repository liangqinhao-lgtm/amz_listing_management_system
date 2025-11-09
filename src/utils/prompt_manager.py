"""Prompt模板管理器"""
import yaml
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class PromptManager:
    """Prompt模板管理器"""
    
    def __init__(self, config_dir: Path = None):
        """
        初始化Prompt管理器
        
        Args:
            config_dir: 配置目录路径，默认为项目根目录/config
        """
        if config_dir is None:
            # 获取项目根目录
            current_file = Path(__file__).resolve()
            project_root = current_file.parents[2]  # 向上两级到项目根目录
            config_dir = project_root / "config"
        
        self.config_dir = config_dir
        self.prompts_cache: Dict[str, str] = {}
        self._load_prompts()
    
    def _load_prompts(self):
        """加载所有Prompt模板"""
        config_path = self.config_dir / "api_clients" / "deepseek.yaml"
        
        if not config_path.exists():
            logger.error(f"Prompt配置文件不存在: {config_path}")
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                self.prompts_cache = config_data.get('prompts', {})
                logger.info(f"成功加载{len(self.prompts_cache)}个Prompt模板")
        except Exception as e:
            logger.error(f"加载Prompt配置失败: {e}")
    
    def get_prompt(self, prompt_key: str) -> Optional[str]:
        """
        获取Prompt模板
        
        Args:
            prompt_key: Prompt键名
            
        Returns:
            Prompt内容，如果不存在返回None
        """
        prompt = self.prompts_cache.get(prompt_key)
        
        if not prompt:
            logger.error(f"未找到Prompt: {prompt_key}")
            logger.debug(f"可用的Prompts: {list(self.prompts_cache.keys())}")
        
        return prompt
    
    def reload(self):
        """重新加载Prompt"""
        self.prompts_cache.clear()
        self._load_prompts()
