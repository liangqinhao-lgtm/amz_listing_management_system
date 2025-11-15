-- ============================================
-- 1. 创建发品日志表 (amz_listing_log)
-- (基于您提供的DDL)
-- ============================================
CREATE TABLE IF NOT EXISTS public.amz_listing_log (
  id SERIAL PRIMARY KEY,
  meow_sku VARCHAR(255) NOT NULL,
  parent_sku VARCHAR(255) NOT NULL,
  variation_attributes JSONB,
  listing_batch_id UUID NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'GENERATED',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  variation_theme VARCHAR(255)
);

CREATE UNIQUE INDEX IF NOT EXISTS amz_listing_log_meow_sku_key ON public.amz_listing_log(meow_sku);
CREATE INDEX IF NOT EXISTS idx_amz_listing_log_parent_sku ON public.amz_listing_log(parent_sku);
CREATE INDEX IF NOT EXISTS idx_amz_listing_log_batch_id ON public.amz_listing_log(listing_batch_id);

COMMENT ON TABLE public.amz_listing_log IS '记录亚马逊发品操作的日志表，用于追踪父子关系和变体属性';
COMMENT ON COLUMN public.amz_listing_log.meow_sku IS '我们内部的、被发布的子体SKU';
COMMENT ON COLUMN public.amz_listing_log.parent_sku IS '该子体被关联到的父体SKU';
COMMENT ON COLUMN public.amz_listing_log.variation_attributes IS '一个JSON对象，存储该子体具体的变体属性，例如: {"color_name": "Red", "size_name": "L"}';
COMMENT ON COLUMN public.amz_listing_log.listing_batch_id IS '用于标识同一次发品操作的唯一批次ID';
COMMENT ON COLUMN public.amz_listing_log.variation_theme IS '该变体家族的变体主题，例如: Color-Size。用于在增补新成员时，指导LLM提取正确的属性。';

-- 验证
\echo '✅ 表 amz_listing_log 已创建/验证'
\d public.amz_listing_log
