"""LLM相关类型定义"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class LLMRequest:
    """LLM请求"""
    task_type: str                          # 任务类型（用于路由）
    system_prompt: str                      # 系统提示
    user_prompt: str                        # 用户提示
    model: Optional[str] = None             # 指定模型（None则自动选择）
    json_mode: bool = False                 # JSON模式
    temperature: float = 0.7                # 温度
    metadata: Optional[Dict] = field(default_factory=dict)  # 扩展元数据

@dataclass
class LLMResponse:
    """LLM响应"""
    content: Any                            # 生成内容
    usage: Optional[Dict] = None            # Token使用统计
    model: Optional[str] = None             # 实际使用的模型
    provider: Optional[str] = None          # 实际使用的提供商
    metadata: Optional[Dict] = field(default_factory=dict)  # 扩展元数据
