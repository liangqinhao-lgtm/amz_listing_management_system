"""DeepSeek API客户端（简化版）"""
import os
import json
import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DeepSeekAPIClient:
    """DeepSeek API客户端"""
    
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise EnvironmentError("未找到DEEPSEEK_API_KEY环境变量")
        
        self.base_url = os.getenv("DEEPSEEK_API_ENDPOINT", "https://api.deepseek.com/v1")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        logger.info("DeepSeek客户端初始化完成")
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        json_mode: bool = False,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """生成内容"""
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"} if json_mode else {"type": "text"}
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self.headers,
                timeout=600
            )
            response.raise_for_status()
            result = response.json()
            
            content_str = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if not content_str.strip():
                raise ValueError("API返回空内容")
            
            # 提取usage信息
            usage = result.get("usage", {})
            
            if json_mode:
                return {
                    "content": json.loads(content_str),
                    "usage": usage
                }
            else:
                return {
                    "content": content_str,
                    "usage": usage
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {content_str[:200]}")
            raise ValueError(f"无效JSON响应: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {e}")
            raise
