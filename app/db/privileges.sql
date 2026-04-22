-- cs4750-finance-tracker example privilege model
-- Run as a MySQL admin/root account.

USE cs4750_finance_tracker;

CREATE USER IF NOT EXISTS 'finance_app'@'%'
  IDENTIFIED BY 'place_holder_pw';

-- Grant only the privileges the app needs.
-- For a newly created user, explicit GRANTs are enough and avoid Cloud SQL
-- import failures caused by broad REVOKE statements.

-- Application CRUD access for primary entities.
GRANT SELECT, INSERT, UPDATE ON cs4750_finance_tracker.`user` TO 'finance_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.account TO 'finance_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.`transaction` TO 'finance_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.category TO 'finance_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.budget TO 'finance_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.recurring_transaction TO 'finance_app'@'%';

-- Relationship table CRUD access.
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.owns TO 'finance_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.posts_to TO 'finance_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.records TO 'finance_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.categorized_as TO 'finance_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.defines TO 'finance_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.user_sets TO 'finance_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON cs4750_finance_tracker.applies_to TO 'finance_app'@'%';

-- Permit executing approved stored logic.
GRANT EXECUTE ON PROCEDURE cs4750_finance_tracker.sp_add_transaction TO 'finance_app'@'%';

FLUSH PRIVILEGES;
