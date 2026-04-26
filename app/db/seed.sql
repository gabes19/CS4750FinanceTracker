-- cs4750-finance-tracker seed data
-- Sample multi-user development data.

USE cs4750_finance_tracker;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE applies_to;
TRUNCATE TABLE user_sets;
TRUNCATE TABLE defines;
TRUNCATE TABLE categorized_as;
TRUNCATE TABLE records;
TRUNCATE TABLE posts_to;
TRUNCATE TABLE owns;
TRUNCATE TABLE recurring_transaction;
TRUNCATE TABLE budget;
TRUNCATE TABLE category;
TRUNCATE TABLE `transaction`;
TRUNCATE TABLE account;
TRUNCATE TABLE `user`;
SET FOREIGN_KEY_CHECKS = 1;

-- Users
-- Demo credentials:
-- alice@example.com / alice123
-- bob@example.com / bob123
-- carla@example.com / carla123
INSERT INTO `user` (user_id, email, password_hash, first_name, last_name) VALUES
  (1, 'alice@example.com', 'scrypt:32768:8:1$eIGAYUSp0BiYkty9$11eea8b082f565e53eac35bd01082b013adc925df445fe02ca357f9563d645283d99470cfe368d4693ce24041962d9a6a8ad2306194108529265476a70f3f150', 'Alice', 'Nguyen'),
  (2, 'bob@example.com', 'scrypt:32768:8:1$slA4fagTZsbhFVVt$b0ce06bc757b81bbdc027c2bea10f06ec38e7b966ff65f8308b1bef8bd14fc78d0b14098103eb5b1704738fe6f24a90801b2ea9c913e616eb69b0a79214db79a', 'Bob', 'Carter'),
  (3, 'carla@example.com', 'scrypt:32768:8:1$HysL6ycDD6laeee3$384423916c81b247b10cf7d368b3a2e2239e2f7b6d336aed7f3e4e3f4bbd5a8bbcb4b5eac5a33801099d7f825d8efd7c76982f2c3fdb80664f16d3b7ae5fef8c', 'Carla', 'Patel');

-- Accounts
INSERT INTO account (account_id, account_name, account_type, currency_code, current_balance, is_active) VALUES
  (1, 'Alice Checking', 'checking', 'USD', 1882.20, 1),
  (2, 'Alice Savings', 'savings', 'USD', 5200.00, 1),
  (3, 'Bob Checking', 'checking', 'USD', 2120.00, 1),
  (4, 'Bob Credit Card', 'credit', 'USD', -140.00, 1),
  (5, 'Carla Cash Wallet', 'cash', 'USD', 265.00, 1);

-- User-account relationships
INSERT INTO owns (user_id, account_id, ownership_role) VALUES
  (1, 1, 'owner'),
  (1, 2, 'owner'),
  (2, 3, 'owner'),
  (2, 4, 'owner'),
  (3, 5, 'owner'),
  (1, 3, 'viewer');

-- Categories (mix of system + user-defined)
INSERT INTO category (category_id, category_name, category_type, is_system_category) VALUES
  (1, 'Salary', 'income', 1),
  (2, 'Groceries', 'expense', 1),
  (3, 'Rent/Mortgage', 'expense', 1),
  (4, 'Utilities', 'expense', 1),
  (5, 'Dining', 'expense', 1),
  (6, 'Freelance', 'income', 0),
  (7, 'Travel', 'expense', 0),
  (8, 'Gym', 'expense', 0),
  (9, 'Entertainment', 'expense', 1),
  (10, 'Miscellaneous', 'expense', 1);

-- Which user defined custom categories
INSERT INTO defines (user_id, category_id) VALUES
  (1, 7),
  (2, 8);

-- Budgets for April 2026
INSERT INTO budget (budget_id, budget_name, budget_month, monthly_limit) VALUES
  (1, 'Alice Groceries April 2026', '2026-04-01', 450.00),
  (2, 'Alice Rent April 2026', '2026-04-01', 1400.00),
  (3, 'Alice Dining April 2026', '2026-04-01', 250.00),
  (4, 'Bob Groceries April 2026', '2026-04-01', 300.00),
  (5, 'Bob Utilities April 2026', '2026-04-01', 200.00),
  (6, 'Carla Dining April 2026', '2026-04-01', 150.00);

INSERT INTO user_sets (user_id, budget_id) VALUES
  (1, 1),
  (1, 2),
  (1, 3),
  (2, 4),
  (2, 5),
  (3, 6);

INSERT INTO applies_to (budget_id, category_id, allocated_limit) VALUES
  (1, 2, 450.00),
  (2, 3, 1400.00),
  (3, 5, 250.00),
  (4, 2, 300.00),
  (5, 4, 200.00),
  (6, 5, 150.00);

-- Recurring transaction templates
INSERT INTO recurring_transaction
  (recurring_transaction_id, transaction_type, amount, description, frequency, start_date, next_run_date, end_date, is_active)
VALUES
  (1, 'expense', 19.99, 'Streaming Subscription', 'monthly', '2026-01-01', '2026-05-01', NULL, 1),
  (2, 'income', 500.00, 'Monthly Freelance Retainer', 'monthly', '2026-04-01', '2026-05-01', NULL, 1);

-- Transactions
INSERT INTO `transaction`
  (transaction_id, transaction_type, amount, description, transaction_date)
VALUES
  (1, 'income', 3000.00, 'April paycheck', '2026-04-01'),
  (2, 'expense', 120.45, 'Weekly groceries', '2026-04-03'),
  (3, 'expense', 950.00, 'Rent payment', '2026-04-04'),
  (4, 'expense', 62.10, 'Electric bill', '2026-04-08'),
  (5, 'expense', 45.25, 'Dinner out', '2026-04-10'),
  (6, 'income', 2200.00, 'Monthly salary', '2026-04-01'),
  (7, 'expense', 80.00, 'Groceries', '2026-04-05'),
  (8, 'expense', 35.00, 'Coffee and snacks', '2026-04-06'),
  (9, 'expense', 40.00, 'Gym membership', '2026-04-11');

-- User records each transaction
INSERT INTO records (user_id, transaction_id) VALUES
  (1, 1),
  (1, 2),
  (1, 3),
  (1, 4),
  (1, 5),
  (2, 6),
  (2, 7),
  (3, 8),
  (2, 9);

-- Posting relationships to accounts
INSERT INTO posts_to (transaction_id, account_id) VALUES
  (1, 1),
  (2, 1),
  (3, 1),
  (4, 1),
  (5, 1),
  (6, 3),
  (7, 3),
  (8, 5),
  (9, 4);

-- Category mappings
INSERT INTO categorized_as (transaction_id, category_id) VALUES
  (1, 1),
  (2, 2),
  (3, 3),
  (4, 4),
  (5, 5),
  (6, 1),
  (7, 2),
  (8, 5),
  (9, 8);
