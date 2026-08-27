-- ============================================================
-- AutoStock-AI Database Schema (SQLite)
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- inventory
-- Current on-hand inventory state per SKU, used to compute
-- stockout runway (current_stock / daily_sales_rate) and to
-- decide whether a SKU has crossed its reorder_point.
-- ------------------------------------------------------------
DROP TABLE IF EXISTS inventory;
CREATE TABLE inventory (
    sku                 TEXT PRIMARY KEY,
    item_name           TEXT NOT NULL,
    category            TEXT NOT NULL CHECK (category IN ('Electronics', 'Hardware')),
    current_stock       INTEGER NOT NULL CHECK (current_stock >= 0),
    reorder_point       INTEGER NOT NULL CHECK (reorder_point >= 0),
    daily_sales_rate    REAL NOT NULL CHECK (daily_sales_rate > 0),
    unit_holding_cost   REAL NOT NULL CHECK (unit_holding_cost >= 0)
);

-- ------------------------------------------------------------
-- vendors
-- Master vendor record. reliability_rating is on a 0-10 scale
-- and is used to enforce the minimum 6.0/10 policy threshold.
-- ------------------------------------------------------------
DROP TABLE IF EXISTS vendors;
CREATE TABLE vendors (
    vendor_id           TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    contact_email       TEXT NOT NULL,
    payment_terms       TEXT NOT NULL,
    reliability_rating  REAL NOT NULL CHECK (reliability_rating BETWEEN 0 AND 10)
);

-- ------------------------------------------------------------
-- vendor_sku_catalog
-- Cross-reference of which vendors supply which SKUs, at what
-- base unit cost, MOQ, and standard lead time. A given SKU may
-- have multiple rows (one per vendor that supplies it).
-- ------------------------------------------------------------
DROP TABLE IF EXISTS vendor_sku_catalog;
CREATE TABLE vendor_sku_catalog (
    vendor_id           TEXT NOT NULL,
    sku                 TEXT NOT NULL,
    base_unit_cost      REAL NOT NULL CHECK (base_unit_cost > 0),
    min_order_qty       INTEGER NOT NULL CHECK (min_order_qty > 0),
    standard_lead_days  INTEGER NOT NULL CHECK (standard_lead_days > 0),
    PRIMARY KEY (vendor_id, sku),
    FOREIGN KEY (vendor_id) REFERENCES vendors (vendor_id) ON DELETE CASCADE,
    FOREIGN KEY (sku)       REFERENCES inventory (sku)     ON DELETE CASCADE
);

CREATE INDEX idx_catalog_sku    ON vendor_sku_catalog (sku);
CREATE INDEX idx_catalog_vendor ON vendor_sku_catalog (vendor_id);
