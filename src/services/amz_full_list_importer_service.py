"""Service层"""
import logging
import pandas as pd
from sqlalchemy.orm import Session
from src.repositories.amz_full_list_report_repository import AmzFullListReportRepository
from infrastructure.validators import validate_file_path

logger = logging.getLogger(__name__)

class AmzFullListImporterService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AmzFullListReportRepository(db)
    
    def import_report_from_file(self, file_path: str) -> None:
        """导入文件"""
        try:
            file_path = validate_file_path(file_path)
            logger.info(f"开始解析: {file_path}")
            
            df = self._read_file(file_path)
            logger.info(f"读取 {len(df)} 行")
            
            df = self._clean_data(df)
            logger.info(f"清洗后 {len(df)} 行")
            
            self.repository.upsert_from_dataframe(df)
            self.db.commit()
            
            stats = self.repository.get_statistics()
            print(f"\n✅ 导入完成！")
            print(f"总记录: {stats['total']}")
            print(f"Active: {stats['active']}")
            print(f"唯一ASIN: {stats['unique_asins']}\n")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"导入失败: {e}")
            raise
    
    def _read_file(self, file_path: str) -> pd.DataFrame:
        for encoding in ['utf-8', 'utf-8-sig', 'gbk']:
            try:
                if file_path.endswith('.csv'):
                    return pd.read_csv(file_path, encoding=encoding)
                else:
                    return pd.read_csv(file_path, sep='\t', encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("无法解析文件")
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        required = ['listing-id', 'seller-sku', 'asin1', 'item-name', 'price', 
                   'quantity', 'open-date', 'status']
        
        df = df[[col for col in required if col in df.columns]].copy()
        
        if 'price' in df.columns:
            df['price'] = pd.to_numeric(df['price'], errors='coerce')
        if 'quantity' in df.columns:
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
        if 'open-date' in df.columns:
            df['open-date'] = pd.to_datetime(df['open-date'], errors='coerce')
        
        df = df.dropna(subset=['listing-id', 'asin1'])
        df = df[df['listing-id'].astype(str).str.strip() != '']
        df = df.drop_duplicates(subset=['listing-id'], keep='first')
        
        return df
