"""
Amazon Template Repository
数据仓库层，负责亚马逊品类模板规则的查询和管理
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
import json
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class AmzTemplateRepository:
    """
    亚马逊品类模板数据仓库
    
    职责：
    - 查询品类模板规则（字段定义、有效值、变体映射等）
    - 管理模板配置的更新和版本
    """
    
    def __init__(self, db: Session):
        """
        初始化Repository
        
        Args:
            db: SQLAlchemy Session实例
        """
        self.db = db
    
    # ========================================================================
    # 数据保存方法
    # ========================================================================
    
    def save_parsed_data(
        self, 
        category: str, 
        template_name: str, 
        results: Dict[str, Any]
    ) -> Optional[int]:
        """
        保存解析结果到数据库
        
        Args:
            category: 品类名称
            template_name: 模板文件名
            results: 从解析器和服务层获取的完整结果字典，包含：
                - fields: 字段列表
                - field_definitions: 字段定义
                - valid_values: 有效值
                - variation_mapping: 变体映射
                - priority_themes: 优先级主题
                
        Returns:
            插入的记录ID，如果失败则返回None
        """
        insert_query = text("""
            INSERT INTO amazon_cat_templates
            (
                category, 
                template_name, 
                fields, 
                field_definitions, 
                valid_values, 
                variation_mapping, 
                priority_themes, 
                created_at
            )
            VALUES (
                :category, 
                :template_name, 
                :fields, 
                :field_defs, 
                :valid_values, 
                :variation_mapping, 
                :priority_themes, 
                NOW()
            ) 
            RETURNING id;
        """)

        try:
            # 将数据结构转换为JSON字符串
            fields_json = json.dumps(results.get("fields", []))
            field_defs_json = json.dumps(results.get("field_definitions", {}))
            valid_values_json = json.dumps(results.get("valid_values", []))
            variation_mapping_json = json.dumps(
                results.get("variation_mapping", {})
            )
            priority_themes_json = json.dumps(
                results.get("priority_themes", [])
            )

            result = self.db.execute(insert_query, {
                "category": category,
                "template_name": template_name,
                "fields": fields_json,
                "field_defs": field_defs_json,
                "valid_values": valid_values_json,
                "variation_mapping": variation_mapping_json,
                "priority_themes": priority_themes_json
            })

            inserted_id = result.scalar_one()
            self.db.commit()

            logger.info(
                f"✅ 解析结果已成功保存到数据库。记录ID: {inserted_id}"
            )
            return inserted_id

        except Exception as e:
            logger.exception(f"❌ 保存数据到数据库时发生错误: {e}")
            self.db.rollback()
            return None
    
    # ========================================================================
    # 数据查询方法
    # ========================================================================
    
    def find_template_by_category(self, category_name: str) -> Optional[Dict[str, Any]]:
        """
        根据品类名称查询最新的模板规则
        
        Args:
            category_name: 标准品类名称（如 'CABINET', 'HOME_MIRROR'）
            
        Returns:
            模板规则字典，包含：
            {
                'fields': [...],                  # 字段列表
                'field_definitions': {...},       # 字段定义
                'valid_values': [...],            # 有效值列表
                'variation_mapping': {...},       # 变体映射
                'priority_themes': [...]          # 高优先级主题
            }
            如果未找到返回None
        """
        query = text("""
            SELECT 
                fields, 
                field_definitions, 
                valid_values, 
                variation_mapping, 
                priority_themes
            FROM amazon_cat_templates
            WHERE LOWER(category) = LOWER(:category)
            ORDER BY id DESC 
            LIMIT 1;
        """)
        
        try:
            logger.info(f"查询品类 '{category_name}' 的模板规则...")
            result = self.db.execute(query, {"category": category_name}).fetchone()
            
            if result:
                logger.info(f"✅ 成功找到品类 '{category_name}' 的模板规则")
                
                # 解析JSONB字段
                def _load_json_if_needed(data: Any) -> Any:
                    """将字符串类型的JSON转为Python对象"""
                    if isinstance(data, str):
                        try:
                            return json.loads(data)
                        except json.JSONDecodeError:
                            logger.warning(f"JSON解析失败，返回None")
                            return None
                    return data if data is not None else None
                
                fields, field_defs, valid_values, variation_mapping, priority_themes = result
                
                return {
                    "fields": _load_json_if_needed(fields) or [],
                    "field_definitions": _load_json_if_needed(field_defs) or {},
                    "valid_values": _load_json_if_needed(valid_values) or [],
                    "variation_mapping": _load_json_if_needed(variation_mapping) or {},
                    "priority_themes": _load_json_if_needed(priority_themes) or []
                }
            else:
                logger.warning(f"⚠️ 未找到品类 '{category_name}' 的模板规则")
                return None
                
        except Exception as e:
            logger.error(f"❌ 查询品类 '{category_name}' 模板时失败: {e}", exc_info=True)
            raise
    
    def find_latest_template_id_and_defs(self, category_name: str) -> Optional[Tuple[int, Dict]]:
        """
        查询最新模板记录的ID和字段定义
        
        用于模板更新场景。
        
        Args:
            category_name: 标准品类名称
            
        Returns:
            元组 (record_id, field_definitions_dict)
            如果未找到返回None
        """
        query = text("""
            SELECT id, field_definitions
            FROM amazon_cat_templates
            WHERE LOWER(category) = LOWER(:category)
            ORDER BY id DESC 
            LIMIT 1;
        """)
        
        try:
            logger.info(f"查询品类 '{category_name}' 的最新ID和字段定义...")
            result = self.db.execute(query, {"category": category_name}).fetchone()
            
            if result and result[0] is not None:
                record_id, field_defs = result
                
                # 解析字段定义
                defs_dict = json.loads(field_defs) if isinstance(field_defs, str) else (field_defs or {})
                
                logger.info(f"✅ 找到记录 ID: {record_id}")
                return record_id, defs_dict
            else:
                logger.warning(f"⚠️ 未找到品类 '{category_name}' 的模板记录")
                return None
                
        except Exception as e:
            logger.error(f"❌ 查询失败: {e}", exc_info=True)
            raise
    
    def update_field_definitions_by_id(self, record_id: int, new_definitions: Dict) -> bool:
        """
        更新指定记录的字段定义
        
        用于模板纠正功能。
        
        Args:
            record_id: 记录ID
            new_definitions: 新的字段定义字典
            
        Returns:
            操作是否成功
        """
        query = text("""
            UPDATE amazon_cat_templates
            SET field_definitions = :defs
            WHERE id = :id;
        """)
        
        try:
            logger.info(f"更新记录 ID: {record_id} 的字段定义...")
            
            # 转为JSON字符串
            new_defs_json = json.dumps(new_definitions, indent=2)
            
            self.db.execute(query, {"id": record_id, "defs": new_defs_json})
            
            # 注意：不在这里commit，由调用方决定
            logger.info(f"✅ 记录 ID: {record_id} 的字段定义已更新（未提交）")
            return True
            
        except Exception as e:
            logger.error(f"❌ 更新记录 ID: {record_id} 失败: {e}", exc_info=True)
            return False
    
    def find_latest_priority_themes_by_category(self, category_name: str) -> Optional[List[str]]:
        """
        查询最新记录的高优先级主题
        
        用于沿用上一版本的优先主题配置。
        
        Args:
            category_name: 标准品类名称
            
        Returns:
            高优先级主题列表
            如果未找到或为空返回None
        """
        query = text("""
            SELECT priority_themes
            FROM amazon_cat_templates
            WHERE LOWER(category) = LOWER(:category)
            ORDER BY created_at DESC, id DESC 
            LIMIT 1;
        """)
        
        try:
            logger.info(f"查询品类 '{category_name}' 的优先主题...")
            result = self.db.execute(query, {"category": category_name}).scalar_one_or_none()
            
            if result and isinstance(result, list) and len(result) > 0:
                logger.info(f"✅ 找到优先主题: {result}")
                return result
            else:
                logger.info(f"ℹ️ 品类 '{category_name}' 没有优先主题配置")
                return None
                
        except Exception as e:
            logger.error(f"❌ 查询失败: {e}", exc_info=True)
            raise