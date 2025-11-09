-- ============================================
-- 1. 创建最终售价表
-- ============================================
CREATE TABLE IF NOT EXISTS product_final_prices (
    id SERIAL PRIMARY KEY,
    meow_sku VARCHAR(255) NOT NULL,
    final_price NUMERIC(10,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    cost_at_pricing NUMERIC(10,2) NOT NULL,
    pricing_formula_version VARCHAR(50) NOT NULL,
    pricing_params_snapshot JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meow_sku) REFERENCES meow_sku_map(meow_sku) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS product_final_prices_meow_sku_key 
    ON product_final_prices(meow_sku);

COMMENT ON TABLE product_final_prices IS '存储每个SKU最终计算售价的表';

-- ============================================
-- 2. 检查并创建品类映射表（如果不存在）
-- ============================================
CREATE TABLE IF NOT EXISTS supplier_categories_map (
    id SERIAL PRIMARY KEY,
    supplier_platform VARCHAR(50) NOT NULL,
    supplier_category_code VARCHAR(20) NOT NULL,
    supplier_category_name VARCHAR(255) NOT NULL,
    standard_category_name VARCHAR(255) NOT NULL,
    created_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_platform_code_ci 
    ON supplier_categories_map(supplier_platform, LOWER(supplier_category_code));

COMMENT ON TABLE supplier_categories_map IS '供应商类目映射表（平台+编码唯一）';

-- ============================================
-- 3. 清空并导入品类映射数据
-- ============================================
TRUNCATE TABLE supplier_categories_map RESTART IDENTITY CASCADE;

INSERT INTO supplier_categories_map (
    supplier_platform, 
    supplier_category_code, 
    supplier_category_name, 
    standard_category_name
) VALUES
    ('giga', 'HOME001', 'Mirror', 'home_mirror'),
    ('giga', 'HOME002', 'Cabinet', 'cabinet'),
    ('giga', 'FURN001', 'Furniture', 'furniture'),
    ('giga', 'HOME003', 'Home Decor', 'home_decor');

-- 验证导入
SELECT 
    supplier_platform,
    supplier_category_code,
    supplier_category_name,
    standard_category_name
FROM supplier_categories_map
ORDER BY id;

SELECT '✅ 品类映射数据导入完成，共' || COUNT(*) || '条记录' as result
FROM supplier_categories_map;

