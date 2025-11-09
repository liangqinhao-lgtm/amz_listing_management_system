"""Giga API客户端（增强日志版）"""
import logging
import time
import json
from typing import Dict, Optional, Any
import requests
from infrastructure.giga.config import GigaConfig
from infrastructure.giga.token_manager import GigaTokenManager
from infrastructure.exceptions import AppException

logger = logging.getLogger(__name__)

class GigaAPIException(AppException):
    """Giga API异常"""
    def __init__(self, message: str, status_code: int = None, response_body: dict = None):
        super().__init__(message, code="GIGA_API_ERROR")
        self.status_code = status_code
        self.response_body = response_body

class GigaAPIClient:
    """Giga API客户端"""
    
    def __init__(self):
        GigaConfig.validate()
        self.token_manager = GigaTokenManager()
        self.max_retries = 3
    
    def execute(
        self,
        endpoint_name: str,
        payload: Optional[Dict[str, Any]] = None,
        method: str = 'POST'
    ) -> Dict[str, Any]:
        """执行API请求"""
        url = GigaConfig.get_endpoint_url(endpoint_name)
        
        # 记录请求详情
        logger.info(f"API请求: {method} {url}")
        logger.debug(f"请求参数: {json.dumps(payload, ensure_ascii=False)[:500]}")
        
        for attempt in range(self.max_retries + 1):
            try:
                # 获取Token
                token_data = self.token_manager.get_token()
                headers = {
                    'Authorization': f"{token_data['token_type']} {token_data['access_token']}",
                    'Content-Type': 'application/json'
                }
                
                # 发送请求
                if method.upper() == 'GET':
                    response = requests.get(url, params=payload, headers=headers, timeout=30)
                else:
                    response = requests.post(url, json=payload, headers=headers, timeout=30)
                
                # 记录响应详情
                logger.debug(f"响应状态码: {response.status_code}")
                logger.debug(f"响应头: {dict(response.headers)}")
                
                # 处理401 Token过期
                if response.status_code == 401:
                    logger.warning("Token过期，尝试刷新...")
                    token_data = self.token_manager.force_refresh()
                    headers['Authorization'] = f"{token_data['token_type']} {token_data['access_token']}"
                    
                    # 重试请求
                    if method.upper() == 'GET':
                        response = requests.get(url, params=payload, headers=headers, timeout=30)
                    else:
                        response = requests.post(url, json=payload, headers=headers, timeout=30)
                
                response.raise_for_status()
                
                # 解析响应
                try:
                    response_data = response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {e}")
                    logger.error(f"原始响应: {response.text[:1000]}")
                    raise GigaAPIException("响应格式错误", response.status_code)
                
                # 记录完整响应（用于调试）
                logger.debug(f"响应内容: {json.dumps(response_data, ensure_ascii=False)[:1000]}")
                
                # 检查业务状态
                if not response_data.get('success'):
                    # 提取所有可能的错误信息
                    error_msg = (
                        response_data.get('message') or 
                        response_data.get('error') or 
                        response_data.get('detail') or 
                        response_data.get('msg') or
                        '未知API错误'
                    )
                    
                    # 记录完整错误响应
                    logger.error(f"API业务错误详情:")
                    logger.error(f"  URL: {url}")
                    logger.error(f"  状态码: {response.status_code}")
                    logger.error(f"  错误消息: {error_msg}")
                    logger.error(f"  完整响应: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
                    
                    raise GigaAPIException(error_msg, response.status_code, response_data)
                
                return {
                    'headers': dict(response.headers),
                    'body': response_data
                }
                
            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"请求超时，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                raise GigaAPIException("请求超时")
                
            except requests.exceptions.RequestException as e:
                logger.error(f"请求异常: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"响应状态: {e.response.status_code}")
                    logger.error(f"响应内容: {e.response.text[:1000]}")
                    
                if attempt < self.max_retries and hasattr(e, 'response') and e.response:
                    if e.response.status_code in [429, 500, 503]:
                        wait_time = 2 ** attempt
                        logger.warning(f"可重试错误({e.response.status_code})，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                raise GigaAPIException(f"请求失败: {e}")
        
        raise GigaAPIException(f"超过最大重试次数({self.max_retries})")
