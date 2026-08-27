-- ============================================================
-- AutoStock-AI Seed Data (SQLite)
-- Consistent with vendor_techcorp_pricing_sla.md,
-- vendor_globalparts_pricing_sla.md, vendor_apex_pricing_sla.md,
-- and internal_procurement_policy.md
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- inventory (10 SKUs: 5 Electronics, 5 Hardware)
-- reorder_point is set at daily_sales_rate * 14 (the 14-day
-- target safety stock buffer from internal_procurement_policy.md).
-- Five SKUs are seeded at or below reorder_point to trigger
-- reorder evaluation (SKU-1001, SKU-1003, SKU-1005, SKU-2001,
-- SKU-2005) -- exceeding the required minimum of 3.
-- ------------------------------------------------------------
INSERT INTO inventory (sku, item_name, category, current_stock, reorder_point, daily_sales_rate, unit_holding_cost) VALUES
('SKU-1001', 'Optical Sensor',               'Electronics',  95, 112,  8.0, 0.45),  -- below reorder point
('SKU-1002', 'Microcontroller Board',        'Electronics', 240, 210, 15.0, 0.30),
('SKU-1003', 'Lithium-Ion Battery Pack',     'Electronics',  18, 140, 10.0, 0.55),  -- below reorder point (critical)
('SKU-1004', 'USB-C Interface Module',       'Electronics', 410, 350, 25.0, 0.15),
('SKU-1005', 'OLED Display 128x64',          'Electronics', 150, 168, 12.0, 0.35),  -- below reorder point
('SKU-2001', 'NEMA 17 Stepper Motor',        'Hardware',     70,  84,  6.0, 0.60),  -- below reorder point
('SKU-2002', 'Linear Rail 300mm',            'Hardware',     95,  70,  5.0, 0.50),
('SKU-2003', 'Aluminum Extrusion 2020',      'Hardware',    305, 280, 20.0, 0.10),
('SKU-2004', 'Ball Bearing 8mm',             'Hardware',    600, 560, 40.0, 0.03),
('SKU-2005', 'Timing Belt GT2',              'Hardware',    230, 252, 18.0, 0.12);  -- below reorder point

-- ------------------------------------------------------------
-- vendors (3 vendors)
-- reliability_rating matches internal_procurement_policy.md
-- Section 6 (VEND-002 sits just above the 6.0/10 policy floor).
-- ------------------------------------------------------------
INSERT INTO vendors (vendor_id, name, contact_email, payment_terms, reliability_rating) VALUES
('VEND-001', 'TechCorp Logistics',  'accounts@techcorplogistics.com', 'Net 30',       8.7),
('VEND-002', 'GlobalParts Direct',  'sales@globalpartsdirect.com',    '2/10 Net 60',  6.4),
('VEND-003', 'Apex Supply Co.',     'orders@apexsupplyco.com',        'Net 45',       7.5);

-- ------------------------------------------------------------
-- vendor_sku_catalog
-- base_unit_cost = Tier 1 / Standard Tier unit price from each
-- vendor's Master Pricing & SLA Schedule. standard_lead_days
-- uses the low end of each vendor's standard lead time window
-- (or the specific per-SKU value where the SLA doc lists one).
-- ------------------------------------------------------------

-- VEND-001 (TechCorp Logistics) -- SKU-1001 through SKU-1005 only
INSERT INTO vendor_sku_catalog (vendor_id, sku, base_unit_cost, min_order_qty, standard_lead_days) VALUES
('VEND-001', 'SKU-1001', 18.50, 25, 4),
('VEND-001', 'SKU-1002', 12.75, 20, 4),
('VEND-001', 'SKU-1003',  9.40, 30, 5),
('VEND-001', 'SKU-1004',  4.20, 50, 4),
('VEND-001', 'SKU-1005',  6.85, 40, 4);

-- VEND-002 (GlobalParts Direct) -- full 10-SKU catalog
INSERT INTO vendor_sku_catalog (vendor_id, sku, base_unit_cost, min_order_qty, standard_lead_days) VALUES
('VEND-002', 'SKU-1001', 14.80, 100, 14),
('VEND-002', 'SKU-1002', 10.20, 100, 14),
('VEND-002', 'SKU-1003',  7.55, 150, 18),
('VEND-002', 'SKU-1004',  3.35, 200, 14),
('VEND-002', 'SKU-1005',  5.48, 150, 15),
('VEND-002', 'SKU-2001', 11.90, 100, 16),
('VEND-002', 'SKU-2002',  8.75, 100, 16),
('VEND-002', 'SKU-2003',  2.15, 250, 14),
('VEND-002', 'SKU-2004',  0.62, 250, 14),
('VEND-002', 'SKU-2005',  1.95, 200, 15);

-- VEND-003 (Apex Supply Co.) -- SKU-2001 through SKU-2005 only
INSERT INTO vendor_sku_catalog (vendor_id, sku, base_unit_cost, min_order_qty, standard_lead_days) VALUES
('VEND-003', 'SKU-2001', 10.15, 50, 8),
('VEND-003', 'SKU-2002',  7.60, 50, 9),
('VEND-003', 'SKU-2003',  2.85, 50, 7),
('VEND-003', 'SKU-2004',  0.79, 50, 7),
('VEND-003', 'SKU-2005',  2.35, 50, 10);
