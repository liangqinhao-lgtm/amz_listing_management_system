"""Giga商品库存同步服务"""
import os
import json
import logging
import time
from typing import List, Dict, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from infrastructure.giga.api_client import GigaAPIClient, GigaAPIException
from infrastructure.db_pool import SessionLocal
from src.repositories.giga_product_inventory_repository import GigaProductInventoryRepository

logger = logging.getLogger(__name__)

class GigaInventorySyncService:
    """Giga商品库存同步服务"""
    
    def __init__(
        self,
        db: Session,
        batch_size: int = 200,
        max_retries: int = 3,
        max_threads: int = 5,
        api_rate_limit: int = 9,
        wait_time: int = 10,
        save_api_response: bool = False
    ):
        self.db = db
        self.repository = GigaProductInventoryRepository(db)
        self.api_client = GigaAPIClient()
        
        # 配置参数
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.max_threads = max_threads
        self.api_rate_limit = api_rate_limit
        self.wait_time = wait_time
        self.save_api_response = save_api_response
        
        # API响应保存目录
        if self.save_api_response:
            self.response_dir = "api_responses/inventory"
            os.makedirs(self.response_dir, exist_ok=True)
    
    def _save_api_response(self, batch_idx: int, skus: List[str], response_data: Dict):
        """保存API响应到文件"""
        if not self.save_api_response:
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(
                self.response_dir,
                f"inventory_response_{timestamp}_batch_{batch_idx}.json"
            )
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "request": {
                        "timestamp": timestamp,
                        "batch_index": batch_idx,
                        "skus": skus,
                        "count": len(skus)
                    },
                    "response": response_data
                }, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"保存API响应失败: {e}")
    
    def fetch_batch_inventory(self, skus: List[str]) -> Dict:
        """
        获取批次商品库存（带重试）
        
        Args:
            skus: SKU列表
            
        Returns:
            API响应数据
        """
        for attempt in range(self.max_retries):
            try:
                payload = {"skus": skus}
                response = self.api_client.execute(
                    "inventory_qty",
                    payload,
                    method="POST"
                )
                
                body = response.get('body', {})
                if not body:
                    raise ValueError("API响应结构无效")
                
                return body
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = 2 ** attempt
                    logger.warning(f"API调用失败，{delay}秒后重试 ({attempt+1}/{self.max_retries}): {e}")
                    time.sleep(delay)
                else:
                    logger.error(f"API调用失败，已达最大重试次数: {e}")
                    raise
    
    def process_batch(self, batch_idx: int, skus: List[str]) -> Tuple[int, int]:
        """
        处理单个批次（线程安全）
        
        Returns:
            (处理数量, 更新数量)
        """
        # 使用独立的数据库会话
        with SessionLocal() as thread_db:
            thread_repo = GigaProductInventoryRepository(thread_db)
            
            try:
                # 1. 调用API
                response = self.fetch_batch_inventory(skus)
                self._save_api_response(batch_idx, skus, response)
                
                # 2. 解析数据
                inventory_data = []
                for item in response.get("data", []):
                    try:
                        inventory_data.append(thread_repo.parse_inventory_item(item))
                    except Exception as e:
                        logger.error(f"解析库存项失败: {e}")
                        continue
                
                # 3. 批量更新
                processed, upserted = thread_repo.bulk_upsert_inventory(inventory_data)
                
                logger.info(f"批次 {batch_idx}: 处理 {processed} 条, 更新 {upserted} 条")
                return processed, upserted
                
            except Exception as e:
                logger.error(f"处理批次 {batch_idx} 失败: {e}")
                return 0, 0
    
    def sync_all_inventory(self) -> Dict[str, int]:
        """
        同步全量商品库存
        
        Returns:
            统计信息: {'total_skus': x, 'processed': y, 'upserted': z}
        """
        logger.info("🚀 开始库存同步流程...")
        start_time = time.time()
        
        stats = {
            'total_skus': 0,
            'batches': 0,
            'processed': 0,
            'upserted': 0,
            'success_batches': 0,
            'failed_batches': 0
        }
        
        try:
            # 1. 获取所有SKU
            all_skus = self.repository.get_all_skus()
            stats['total_skus'] = len(all_skus)
            
            if not stats['total_skus']:
                logger.info("没有需要更新的SKU")
                print("✅ 没有需要更新的SKU")
                return stats
            
            # 2. 分批
            batches = [
                all_skus[i:i + self.batch_size]
                for i in range(0, stats['total_skus'], self.batch_size)
            ]
            stats['batches'] = len(batches)
            
            logger.info(f"待同步SKU总数: {stats['total_skus']}, 批次数: {stats['batches']}")
            print(f"\n📊 待同步SKU总数: {stats['total_skus']}")
            print(f"📦 批次大小: {self.batch_size}")
            print(f"🧵 线程数: {self.max_threads}\n")
            
            # 3. 使用线程池处理
            with ThreadPoolExecutor(max_workers=min(self.max_threads, len(batches))) as executor:
                futures = {
                    executor.submit(self.process_batch, idx + 1, batch): idx
                    for idx, batch in enumerate(batches)
                }
                
                for future in as_completed(futures):
                    batch_idx = futures[future] + 1
                    
                    try:
                        processed, upserted = future.result()
                        stats['processed'] += processed
                        stats['upserted'] += upserted
                        stats['success_batches'] += 1
                        
                        print(f"✔️ 批次 {batch_idx}/{stats['batches']}: 更新 {upserted} 条")
                        
                    except Exception as e:
                        stats['failed_batches'] += 1
                        logger.error(f"批次 {batch_idx} 处理失败: {e}")
                        print(f"❌ 批次 {batch_idx}/{stats['batches']}: 失败")
                    
                    # 进度报告
                    progress = batch_idx / stats['batches'] * 100
                    logger.info(f"进度: {progress:.1f}% | 批次: {batch_idx}/{stats['batches']}")
                    
                    # API限流
                    if batch_idx % self.api_rate_limit == 0:
                        time.sleep(self.wait_time)
        
        except Exception as e:
            logger.error(f"同步流程异常: {e}")
        
        finally:
            # 最终报告
            elapsed = time.time() - start_time
            
            print("\n" + "="*60)
            print("✅ 库存同步完成！")
            print("="*60)
            print(f"SKU总数: {stats['total_skus']}")
            print(f"处理批次: {stats['batches']}")
            print(f"成功批次: {stats['success_batches']}")
            print(f"失败批次: {stats['failed_batches']}")
            print(f"更新记录: {stats['upserted']}/{stats['processed']}")
            print(f"耗时: {elapsed:.2f}秒 ({elapsed/60:.2f}分钟)")
            print("="*60 + "\n")
            
            logger.info(f"库存同步完成 | SKU总数: {stats['total_skus']}")
            logger.info(f"更新记录: {stats['upserted']}/{stats['processed']}")
            logger.info(f"总耗时: {elapsed:.2f}秒")
        
        return stats
