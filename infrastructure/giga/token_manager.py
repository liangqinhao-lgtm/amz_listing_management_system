"""Giga API Token管理器（线程安全）"""
import time
import logging
from threading import Lock
from typing import Dict, Optional
import requests
from infrastructure.giga.config import GigaConfig

logger = logging.getLogger(__name__)

class GigaTokenManager:
    """Token管理器 - 单例模式"""
    
    _instance: Optional['GigaTokenManager'] = None
    _lock = Lock()
    _token_cache: Dict = {
        'token_data': None,
        'expires_at': 0
    }
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_token(self) -> Dict:
        """获取有效Token（自动刷新）"""
        # 提前5分钟刷新
        if time.time() < self._token_cache['expires_at'] - 300:
            return self._token_cache['token_data']
        
        return self._refresh_token()
    
    def _refresh_token(self) -> Dict:
        """刷新Token"""
        with self._lock:
            # 双重检查
            if time.time() < self._token_cache['expires_at'] - 300:
                return self._token_cache['token_data']
            
            logger.info("正在刷新Giga API Token...")
            
            try:
                response = requests.post(
                    url=GigaConfig.get_endpoint_url('token'),
                    data={
                        'grant_type': 'client_credentials',
                        'client_id': GigaConfig.CLIENT_ID,
                        'client_secret': GigaConfig.CLIENT_SECRET
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=10
                )
                response.raise_for_status()
                token_data = response.json()
                
                # 更新缓存
                self._token_cache = {
                    'token_data': token_data,
                    'expires_at': time.time() + token_data['expires_in']
                }
                
                logger.info("Token刷新成功")
                return token_data
                
            except Exception as e:
                logger.error(f"Token刷新失败: {e}")
                raise
    
    def force_refresh(self) -> Dict:
        """强制刷新Token"""
        self._token_cache['expires_at'] = 0
        return self.get_token()
