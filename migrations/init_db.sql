CREATE TABLE IF NOT EXISTS amz_all_listing_report (
    "listing-id" VARCHAR(50) PRIMARY KEY,
    "seller-sku" VARCHAR(50),
    asin1 VARCHAR(50) NOT NULL,
    "item-name" VARCHAR(255),
    price NUMERIC(10, 2),
    quantity INTEGER,
    "open-date" TIMESTAMP,
    status VARCHAR(50),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_amz_asin1 ON amz_all_listing_report(asin1);
CREATE INDEX IF NOT EXISTS idx_amz_status ON amz_all_listing_report(status);
