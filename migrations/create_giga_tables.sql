-- ========================================
-- Giga商品同步记录表（改名加giga前缀）
-- ========================================
CREATE TABLE IF NOT EXISTS giga_product_sync_records (
    id SERIAL PRIMARY KEY,
    giga_sku VARCHAR(100) NOT NULL UNIQUE,
    category_code VARCHAR(100),
    is_oversize BOOLEAN DEFAULT FALSE,
    raw_data JSONB NOT NULL,
    sync_status VARCHAR(50) DEFAULT 'synced',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_giga_product_sync_sku ON giga_product_sync_records(giga_sku);
CREATE INDEX IF NOT EXISTS idx_giga_product_sync_category ON giga_product_sync_records(category_code);
CREATE INDEX IF NOT EXISTS idx_giga_product_sync_raw_data ON giga_product_sync_records USING GIN(raw_data);

COMMENT ON TABLE giga_product_sync_records IS 'Giga商品同步记录表';

-- ========================================
-- SKU映射表
-- ========================================
CREATE TABLE IF NOT EXISTS meow_sku_map (
    id SERIAL PRIMARY KEY,
    meow_sku VARCHAR(100) NOT NULL UNIQUE,
    vendor_sku VARCHAR(100) NOT NULL,
    vendor_source VARCHAR(50) NOT NULL DEFAULT 'giga',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vendor_sku, vendor_source)
);

CREATE INDEX IF NOT EXISTS idx_meow_sku_map_meow ON meow_sku_map(meow_sku);
CREATE INDEX IF NOT EXISTS idx_meow_sku_map_vendor ON meow_sku_map(vendor_sku, vendor_source);

COMMENT ON TABLE meow_sku_map IS 'SKU映射表：内部SKU与供应商SKU的映射关系';

-- ========================================
-- 商品基础价格表
-- ========================================
CREATE TABLE IF NOT EXISTS product_base_prices (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(100) NOT NULL UNIQUE,
    cost_price NUMERIC(10, 2),
    suggested_price NUMERIC(10, 2),
    sku_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_product_base_prices_sku ON product_base_prices(sku);
CREATE INDEX IF NOT EXISTS idx_product_base_prices_available ON product_base_prices(sku_available);

COMMENT ON TABLE product_base_prices IS '商品基础价格表';

-- ========================================
-- 供应商分类映射表
-- ========================================
CREATE TABLE IF NOT EXISTS supplier_categories_map (
    id SERIAL PRIMARY KEY,
    supplier_platform VARCHAR(50) NOT NULL,
    supplier_category_code VARCHAR(100) NOT NULL,
    standard_category_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(supplier_platform, supplier_category_code)
);

CREATE INDEX IF NOT EXISTS idx_supplier_cat_platform ON supplier_categories_map(supplier_platform);
CREATE INDEX IF NOT EXISTS idx_supplier_cat_code ON supplier_categories_map(supplier_category_code);

COMMENT ON TABLE supplier_categories_map IS '供应商分类映射表：供应商分类与标准分类的映射';
