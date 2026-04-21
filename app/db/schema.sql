-- cs4750-finance-tracker schema
-- Creates core entities and relationship tables for a multi-user finance tracker.

CREATE DATABASE IF NOT EXISTS cs4750_finance_tracker
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE cs4750_finance_tracker;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS applies_to;
DROP TABLE IF EXISTS user_sets;
DROP TABLE IF EXISTS defines;
DROP TABLE IF EXISTS categorized_as;
DROP TABLE IF EXISTS records;
DROP TABLE IF EXISTS posts_to;
DROP TABLE IF EXISTS owns;
DROP TABLE IF EXISTS recurring_transaction;
DROP TABLE IF EXISTS budget;
DROP TABLE IF EXISTS category;
DROP TABLE IF EXISTS `transaction`;
DROP TABLE IF EXISTS account;
DROP TABLE IF EXISTS `user`;
SET FOREIGN_KEY_CHECKS = 1;

-- Table: user
-- Stores application users and login identity metadata.
CREATE TABLE `user` (
  user_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_user_email UNIQUE (email)
) COMMENT = 'Application users with unique login emails.';

-- Table: account
-- Stores financial accounts (checking, savings, credit, cash, etc.).
CREATE TABLE account (
  account_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  account_name VARCHAR(100) NOT NULL,
  account_type ENUM('checking', 'savings', 'credit', 'cash', 'investment') NOT NULL,
  currency_code CHAR(3) NOT NULL DEFAULT 'USD',
  current_balance DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) COMMENT = 'Financial accounts that can receive posted transactions.';

-- Table: transaction
-- Stores money movement records before user/account/category relationship mapping.
CREATE TABLE `transaction` (
  transaction_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  transaction_type ENUM('income', 'expense', 'transfer') NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  description VARCHAR(255) NULL,
  transaction_date DATE NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT chk_transaction_amount_positive CHECK (amount > 0)
) COMMENT = 'Canonical transaction records; linked to users/accounts/categories via relationship tables.';

-- Table: category
-- Stores transaction categories for budgeting and reporting.
CREATE TABLE category (
  category_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  category_name VARCHAR(100) NOT NULL,
  category_type ENUM('income', 'expense') NOT NULL,
  is_system_category TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) COMMENT = 'Transaction categories for classifying spending and income.';

-- Table: budget
-- Stores monthly budget definitions that are later assigned to users/categories.
CREATE TABLE budget (
  budget_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  budget_name VARCHAR(100) NOT NULL,
  budget_month DATE NOT NULL,
  monthly_limit DECIMAL(12,2) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT chk_budget_limit_non_negative CHECK (monthly_limit >= 0)
) COMMENT = 'Monthly budget definitions applied to categories for a user.';

-- Table: recurring_transaction
-- Stores recurring transaction templates for future automation.
CREATE TABLE recurring_transaction (
  recurring_transaction_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  transaction_type ENUM('income', 'expense') NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  description VARCHAR(255) NULL,
  frequency ENUM('daily', 'weekly', 'biweekly', 'monthly', 'yearly') NOT NULL,
  start_date DATE NOT NULL,
  next_run_date DATE NOT NULL,
  end_date DATE NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT chk_recurring_amount_positive CHECK (amount > 0)
) COMMENT = 'Recurring transaction templates used for scheduled inserts.';

-- Table: owns
-- Relationship table mapping users to the accounts they own or can view.
CREATE TABLE owns (
  user_id INT UNSIGNED NOT NULL,
  account_id INT UNSIGNED NOT NULL,
  ownership_role ENUM('owner', 'viewer') NOT NULL DEFAULT 'owner',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, account_id),
  CONSTRAINT fk_owns_user
    FOREIGN KEY (user_id) REFERENCES `user` (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_owns_account
    FOREIGN KEY (account_id) REFERENCES account (account_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT = 'Associates users to accessible accounts.';

-- Table: posts_to
-- Relationship table mapping transactions to destination/source accounts.
CREATE TABLE posts_to (
  transaction_id BIGINT UNSIGNED NOT NULL,
  account_id INT UNSIGNED NOT NULL,
  posted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (transaction_id, account_id),
  CONSTRAINT fk_posts_to_transaction
    FOREIGN KEY (transaction_id) REFERENCES `transaction` (transaction_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_posts_to_account
    FOREIGN KEY (account_id) REFERENCES account (account_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT = 'Associates transactions with accounts they affect.';

-- Table: records
-- Relationship table mapping users to the transactions they recorded.
CREATE TABLE records (
  user_id INT UNSIGNED NOT NULL,
  transaction_id BIGINT UNSIGNED NOT NULL,
  recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, transaction_id),
  CONSTRAINT fk_records_user
    FOREIGN KEY (user_id) REFERENCES `user` (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_records_transaction
    FOREIGN KEY (transaction_id) REFERENCES `transaction` (transaction_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT = 'Associates each transaction with the user who recorded it.';

-- Table: categorized_as
-- Relationship table mapping transactions to categories.
CREATE TABLE categorized_as (
  transaction_id BIGINT UNSIGNED NOT NULL,
  category_id INT UNSIGNED NOT NULL,
  categorized_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (transaction_id, category_id),
  CONSTRAINT fk_categorized_as_transaction
    FOREIGN KEY (transaction_id) REFERENCES `transaction` (transaction_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_categorized_as_category
    FOREIGN KEY (category_id) REFERENCES category (category_id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) COMMENT = 'Associates transactions to one or more categories.';

-- Table: defines
-- Relationship table mapping users to categories they define/customize.
CREATE TABLE defines (
  user_id INT UNSIGNED NOT NULL,
  category_id INT UNSIGNED NOT NULL,
  defined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, category_id),
  CONSTRAINT fk_defines_user
    FOREIGN KEY (user_id) REFERENCES `user` (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_defines_category
    FOREIGN KEY (category_id) REFERENCES category (category_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT = 'Associates custom categories with the user that created them.';

-- Table: user_sets
-- Relationship table mapping users to the budgets they configure.
CREATE TABLE user_sets (
  user_id INT UNSIGNED NOT NULL,
  budget_id INT UNSIGNED NOT NULL,
  set_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, budget_id),
  CONSTRAINT fk_user_sets_user
    FOREIGN KEY (user_id) REFERENCES `user` (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_user_sets_budget
    FOREIGN KEY (budget_id) REFERENCES budget (budget_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT = 'Associates users with monthly budget definitions.';

-- Table: applies_to
-- Relationship table mapping budgets to categories they constrain.
CREATE TABLE applies_to (
  budget_id INT UNSIGNED NOT NULL,
  category_id INT UNSIGNED NOT NULL,
  applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (budget_id, category_id),
  CONSTRAINT fk_applies_to_budget
    FOREIGN KEY (budget_id) REFERENCES budget (budget_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_applies_to_category
    FOREIGN KEY (category_id) REFERENCES category (category_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT = 'Associates budgets with covered categories.';
