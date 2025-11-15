-- ============================================================================
-- 表名: amz_listing_log
-- 用途: 记录亚马逊发品操作的日志，追踪父子关系和变体属性
-- 版本: v2.0 (改进版)
-- 日期: 2025-11-15
-- ============================================================================

-- 删除旧表（如果存在）
DROP TABLE IF EXISTS public.amz_listing_log CASCADE;

-- 创建表
CREATE TABLE public.amz_listing_log (
    -- 主键（使用SERIAL自动创建序列）
    id SERIAL PRIMARY KEY,
    
    -- 业务字段
    meow_sku VARCHAR(255) NOT NULL UNIQUE,           -- 我们内部的、被发布的子体SKU
    parent_sku VARCHAR(255) NOT NULL,                -- 该子体被关联到的父体SKU
    variation_attributes JSONB,                      -- 子体的变体属性，例如: {"color_name": "Red", "size_name": "L"}
    listing_batch_id UUID NOT NULL,                  -- 同一次发品操作的唯一批次ID
    variation_theme VARCHAR(255),                    -- 变体主题，例如: Color-Size
    
    -- 状态字段
    status VARCHAR(50) NOT NULL DEFAULT 'GENERATED', -- 发品状态: GENERATED, UPLOADED, PUBLISHED, FAILED等
    
    -- 时间戳（使用TIMESTAMPTZ保留时区信息）
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE UNIQUE INDEX idx_amz_listing_log_meow_sku ON public.amz_listing_log(meow_sku);
CREATE INDEX idx_amz_listing_log_parent_sku ON public.amz_listing_log(parent_sku);
CREATE INDEX idx_amz_listing_log_batch_id ON public.amz_listing_log(listing_batch_id);
CREATE INDEX idx_amz_listing_log_status ON public.amz_listing_log(status);

-- 添加注释
COMMENT ON TABLE public.amz_listing_log IS '记录亚马逊发品操作的日志表，用于追踪父子关系和变体属性';
COMMENT ON COLUMN public.amz_listing_log.id IS '主键ID';
COMMENT ON COLUMN public.amz_listing_log.meow_sku IS '我们内部的、被发布的子体SKU（唯一）';
COMMENT ON COLUMN public.amz_listing_log.parent_sku IS '该子体被关联到的父体SKU';
COMMENT ON COLUMN public.amz_listing_log.variation_attributes IS '变体属性JSON对象，例如: {"color_name": "Red", "size_name": "L"}';
COMMENT ON COLUMN public.amz_listing_log.listing_batch_id IS '同一次发品操作的唯一批次ID';
COMMENT ON COLUMN public.amz_listing_log.variation_theme IS '变体主题，例如: Color-Size（用于指导LLM提取正确属性）';
COMMENT ON COLUMN public.amz_listing_log.status IS '发品状态: GENERATED(已生成), UPLOADED(已上传), PUBLISHED(已发布), FAILED(失败)等';
COMMENT ON COLUMN public.amz_listing_log.created_at IS '记录创建时间';
COMMENT ON COLUMN public.amz_listing_log.updated_at IS '记录更新时间';

-- 设置表的所有者
ALTER TABLE public.amz_listing_log OWNER TO mars_user;

-- ============================================================================
-- 示例数据（可选）
-- ============================================================================
/*
INSERT INTO public.amz_listing_log 
(meow_sku, parent_sku, variation_attributes, listing_batch_id, variation_theme, status)
VALUES 
('MEOW-TSHIRT-RED-L', 'MEOW-TSHIRT-PARENT', 
 '{"color_name": "Red", "size_name": "L"}'::jsonb,
 '123e4567-e89b-12d3-a456-426614174000'::uuid,
 'Color-Size',
 'GENERATED');
*/