"""Repository层"""
import logging
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class AmzFullListReportRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def upsert_from_dataframe(self, df: pd.DataFrame) -> None:
        """批量导入数据"""
        if df.empty:
            return
        
        temp_table = f"temp_amz_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            df.to_sql(temp_table, self.db.bind, if_exists='replace', index=False, method='multi')
            logger.info(f"临时表写入完成: {len(df)} 条")
            
            upsert_sql = text(f"""
                INSERT INTO amz_all_listing_report 
                SELECT * FROM {temp_table}
                ON CONFLICT ("listing-id") DO UPDATE SET
                    "seller-sku" = EXCLUDED."seller-sku",
                    asin1 = EXCLUDED.asin1,
                    "item-name" = EXCLUDED."item-name",
                    price = EXCLUDED.price,
                    quantity = EXCLUDED.quantity,
                    status = EXCLUDED.status,
                    last_updated = CURRENT_TIMESTAMP;
            """)
            self.db.execute(upsert_sql)
            self.db.execute(text(f"DROP TABLE {temp_table}"))
            logger.info("数据合并完成")
            
        except Exception as e:
            logger.error(f"导入失败: {e}")
            try:
                self.db.execute(text(f"DROP TABLE IF EXISTS {temp_table}"))
            except:
                pass
            raise
    
    def get_statistics(self) -> dict:
        """获取统计"""
        sql = text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'Active') as active,
                COUNT(DISTINCT asin1) as unique_asins
            FROM amz_all_listing_report;
        """)
        result = self.db.execute(sql).fetchone()
        return {
            'total': result[0] or 0,
            'active': result[1] or 0,
            'unique_asins': result[2] or 0,
        }
