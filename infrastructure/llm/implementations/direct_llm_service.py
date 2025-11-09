"""直接调用LLM的实现（当前阶段）"""
import logging
import time
from typing import Dict
from infrastructure.llm.interface import LLMServiceInterface
from infrastructure.llm.types import LLMRequest, LLMResponse
from infrastructure.llm.clients.deepseek_client import DeepSeekAPIClient
from infrastructure.llm.clients.qwen_client import QwenAPIClient

logger = logging.getLogger(__name__)

class DirectLLMService(LLMServiceInterface):
    """直接调用LLM的实现"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.clients = {}
        self.default_provider = config.get('default_provider', 'qwen')
        
        # 延迟初始化客户端
        self._init_clients()
    
    def _init_clients(self):
        """初始化LLM客户端"""
        try:
            if 'deepseek' in self.config.get('providers', {}):
                self.clients['deepseek'] = DeepSeekAPIClient()
        except Exception as e:
            logger.warning(f"DeepSeek客户端初始化失败: {e}")
        
        try:
            if 'qwen' in self.config.get('providers', {}):
                self.clients['qwen'] = QwenAPIClient()
        except Exception as e:
            logger.warning(f"千问客户端初始化失败: {e}")
        
        if not self.clients:
            raise RuntimeError("没有可用的LLM客户端")
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        """生成内容（带简单重试）"""
        provider = self._select_provider(request.task_type)
        
        if provider not in self.clients:
            raise ValueError(f"LLM提供商不可用: {provider}")
        
        client = self.clients[provider]
        model = request.model or self.config['providers'][provider]['default_model']
        
        logger.info(f"LLM调用 | Provider: {provider} | Model: {model} | Task: {request.task_type}")
        
        # 尝试主LLM
        try:
            start_time = time.time()
            result = client.generate(
                system_prompt=request.system_prompt,
                user_prompt=request.user_prompt,
                model=model,
                json_mode=request.json_mode,
                temperature=request.temperature
            )
            duration = time.time() - start_time
            logger.info(f"LLM响应成功 | 耗时: {duration:.2f}s")
            
            return LLMResponse(
                content=result['content'],
                usage=result.get('usage'),
                model=model,
                provider=provider
            )
            
        except Exception as e:
            logger.error(f"LLM调用失败 ({provider}): {e}")
            
            # 简单降级：尝试另一个LLM
            fallback_provider = 'qwen' if provider != 'qwen' else 'deepseek'
            if fallback_provider in self.clients:
                logger.warning(f"尝试降级到: {fallback_provider}")
                return self._fallback_generate(request, fallback_provider)
            
            raise
    
    def _select_provider(self, task_type: str) -> str:
        """选择LLM提供商"""
        task_routing = self.config.get('task_routing', {})
        return task_routing.get(task_type, self.default_provider)
    
    def _fallback_generate(self, request: LLMRequest, provider: str) -> LLMResponse:
        """降级到备用LLM"""
        client = self.clients[provider]
        model = self.config['providers'][provider]['default_model']
        
        logger.info(f"使用备用LLM | Provider: {provider} | Model: {model}")
        
        result = client.generate(
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
            model=model,
            json_mode=request.json_mode,
            temperature=request.temperature
        )
        
        return LLMResponse(
            content=result['content'],
            usage=result.get('usage'),
            model=model,
            provider=provider
        )
    
    def health_check(self) -> bool:
        """健康检查"""
        for provider, client in self.clients.items():
            try:
                logger.info(f"检查 {provider} 健康状态...")
                # 简单测试
                result = client.generate(
                    system_prompt="You are a helpful assistant.",
                    user_prompt="Say OK",
                    model=self.config['providers'][provider]['default_model'],
                    temperature=0.1
                )
                if result.get('content'):
                    logger.info(f"{provider} 健康检查通过")
                    return True
            except Exception as e:
                logger.warning(f"{provider} 健康检查失败: {e}")
        
        return False