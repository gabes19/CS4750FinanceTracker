-- Adds per-category allocation amounts to budget-category mappings.
-- Run this once if your database was created before this feature.

USE cs4750_finance_tracker;

ALTER TABLE applies_to
  ADD COLUMN allocated_limit DECIMAL(12,2) NOT NULL DEFAULT 0.00 AFTER category_id;

ALTER TABLE applies_to
  ADD CONSTRAINT chk_applies_to_allocated_non_negative CHECK (allocated_limit >= 0);

-- Backfill legacy rows:
-- If a budget had only one category, map full monthly_limit to that category.
-- If a budget had multiple categories, leave allocations at 0.00 so users can set them explicitly.
UPDATE applies_to ap
INNER JOIN (
  SELECT budget_id, COUNT(*) AS category_count
  FROM applies_to
  GROUP BY budget_id
) counts ON counts.budget_id = ap.budget_id
INNER JOIN budget b ON b.budget_id = ap.budget_id
SET ap.allocated_limit = CASE
  WHEN counts.category_count = 1 THEN b.monthly_limit
  ELSE 0.00
END;
