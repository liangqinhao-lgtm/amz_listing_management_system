-- ========================================
-- Giga商品基础价格表（新表名）
-- ========================================
CREATE TABLE IF NOT EXISTS giga_product_base_prices (
    id SERIAL PRIMARY KEY,
    giga_sku VARCHAR(100) NOT NULL,
    currency CHAR(3) NOT NULL,
    base_price NUMERIC(10,2),
    shipping_fee NUMERIC(10,2),
    shipping_fee_min NUMERIC(10,2),
    shipping_fee_max NUMERIC(10,2),
    exclusive_price NUMERIC(10,2),
    discounted_price NUMERIC(10,2),
    promotion_start TIMESTAMP WITH TIME ZONE,
    promotion_end TIMESTAMP WITH TIME ZONE,
    map_price NUMERIC(10,2),
    future_map_price NUMERIC(10,2),
    effect_map_time TIMESTAMP WITH TIME ZONE,
    sku_available BOOLEAN NOT NULL DEFAULT TRUE,
    seller_info JSONB NOT NULL,
    full_response JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_giga_product_base_prices_sku 
    ON giga_product_base_prices(giga_sku);
CREATE INDEX IF NOT EXISTS idx_giga_product_base_prices_seller_code 
    ON giga_product_base_prices((seller_info->>'sellerCode'));
CREATE INDEX IF NOT EXISTS idx_giga_product_base_prices_available 
    ON giga_product_base_prices(sku_available);
CREATE INDEX IF NOT EXISTS idx_giga_product_base_prices_created 
    ON giga_product_base_prices(created_at);
CREATE INDEX IF NOT EXISTS idx_giga_product_base_prices_updated 
    ON giga_product_base_prices(updated_at);
CREATE INDEX IF NOT EXISTS idx_giga_product_base_prices_seller_info 
    ON giga_product_base_prices USING GIN(seller_info);
CREATE INDEX IF NOT EXISTS idx_giga_product_base_prices_full_response 
    ON giga_product_base_prices USING GIN(full_response);

COMMENT ON TABLE giga_product_base_prices IS 'Giga商品基础价格表';

-- ========================================
-- Giga价格梯度表（新表名）
-- ========================================
CREATE TABLE IF NOT EXISTS giga_price_tiers (
    id SERIAL PRIMARY KEY,
    base_price_id INTEGER NOT NULL,
    tier_type VARCHAR(10) NOT NULL,
    min_quantity INTEGER NOT NULL,
    max_quantity INTEGER NOT NULL,
    price NUMERIC(10,2) NOT NULL,
    discounted_price NUMERIC(10,2),
    effective_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (base_price_id) 
        REFERENCES giga_product_base_prices(id) 
        ON DELETE CASCADE
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_giga_price_tiers_base_price 
    ON giga_price_tiers(base_price_id);
CREATE INDEX IF NOT EXISTS idx_giga_price_tiers_type 
    ON giga_price_tiers(tier_type);
CREATE INDEX IF NOT EXISTS idx_giga_price_tiers_quantity_range 
    ON giga_price_tiers(min_quantity, max_quantity);
CREATE INDEX IF NOT EXISTS idx_giga_price_tiers_price 
    ON giga_price_tiers(price);

COMMENT ON TABLE giga_price_tiers IS 'Giga商品价格梯度表';

-- ========================================
-- Giga库存表
-- ========================================
CREATE TABLE IF NOT EXISTS giga_inventory (
    giga_sku VARCHAR(100) PRIMARY KEY NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    buyer_qty NUMERIC(12,2) NOT NULL DEFAULT 0,
    buyer_partner_qty NUMERIC(12,2) NOT NULL DEFAULT 0,
    seller_qty NUMERIC(12,2) NOT NULL DEFAULT 0,
    buyer_distribution JSONB NOT NULL DEFAULT '[]'::jsonb,
    seller_distribution JSONB NOT NULL DEFAULT '[]'::jsonb,
    next_arrival_date DATE NOT NULL DEFAULT '1970-01-01',
    next_arrival_date_end DATE NOT NULL DEFAULT '1970-01-01',
    next_arrival_qty NUMERIC(12,2) NOT NULL DEFAULT 0,
    next_arrival_qty_max NUMERIC(12,2) NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_giga_inventory_quantity 
    ON giga_inventory(quantity);
CREATE INDEX IF NOT EXISTS idx_giga_inventory_updated 
    ON giga_inventory(last_updated);
CREATE INDEX IF NOT EXISTS idx_giga_inventory_buyer_distribution 
    ON giga_inventory USING GIN(buyer_distribution);
CREATE INDEX IF NOT EXISTS idx_giga_inventory_seller_distribution 
    ON giga_inventory USING GIN(seller_distribution);

COMMENT ON TABLE giga_inventory IS 'Giga商品库存表';
