-- 添加UNIQUE约束到giga_sku
ALTER TABLE giga_product_base_prices 
ADD CONSTRAINT unique_giga_product_base_prices_sku UNIQUE (giga_sku);

-- 验证
SELECT 
    constraint_name, 
    constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'giga_product_base_prices';
