"""千问API客户端（简化版）"""
import os
import json
import logging
from typing import Dict, Any
from http import HTTPStatus
import dashscope
from dashscope.api_entities.dashscope_response import GenerationResponse

logger = logging.getLogger(__name__)

class QwenAPIClient:
    """千问API客户端"""
    
    def __init__(self):
        if not os.getenv("DASHSCOPE_API_KEY"):
            raise EnvironmentError("请设置DASHSCOPE_API_KEY环境变量")
        dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
        logger.info("千问客户端初始化完成")
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        json_mode: bool = False,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """生成内容"""
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]
        
        try:
            response: GenerationResponse = dashscope.Generation.call(
                model=model,
                messages=messages,
                result_format='message',
                temperature=temperature,
            )
            
            if response.status_code == HTTPStatus.OK:
                content = response.output.choices[0]['message']['content']
                usage = response.usage if hasattr(response, 'usage') else {}
                
                if json_mode:
                    return {
                        "content": json.loads(content),
                        "usage": usage
                    }
                else:
                    return {
                        "content": content,
                        "usage": usage
                    }
            else:
                raise ValueError(f"API错误: {response.code} - {response.message}")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {content[:200]}")
            raise ValueError(f"无效JSON响应: {e}")
        except Exception as e:
            logger.error(f"千问API错误: {e}")
            raise
