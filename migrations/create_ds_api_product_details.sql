-- LLM生成的商品详情表
CREATE TABLE IF NOT EXISTS ds_api_product_details (
    id SERIAL PRIMARY KEY,
    sku_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    selling_point_1 TEXT,
    selling_point_2 TEXT,
    selling_point_3 TEXT,
    selling_point_4 TEXT,
    selling_point_5 TEXT,
    product_description TEXT NOT NULL,
    calling_agent TEXT NOT NULL,
    raw_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_ds_api_product_details_sku_id ON ds_api_product_details(sku_id);
CREATE INDEX IF NOT EXISTS idx_ds_api_product_details_created_at ON ds_api_product_details(created_at);
CREATE INDEX IF NOT EXISTS idx_ds_api_product_details_json ON ds_api_product_details USING GIN(raw_json);

COMMENT ON TABLE ds_api_product_details IS 'LLM生成的商品详情表';
