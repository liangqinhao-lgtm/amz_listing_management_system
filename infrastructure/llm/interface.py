"""LLM服务统一接口"""
from abc import ABC, abstractmethod
from infrastructure.llm.types import LLMRequest, LLMResponse

class LLMServiceInterface(ABC):
    """LLM服务统一接口（适配未来Agent）"""
    
    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        生成内容
        
        Args:
            request: LLM请求对象
            
        Returns:
            LLM响应对象
            
        Raises:
            Exception: 生成失败时抛出异常
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            True: 服务正常
            False: 服务异常
        """
        pass
