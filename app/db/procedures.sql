-- cs4750-finance-tracker stored routines and triggers

USE cs4750_finance_tracker;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_add_transaction $$
CREATE PROCEDURE sp_add_transaction(
  IN p_user_id INT UNSIGNED,
  IN p_account_id INT UNSIGNED,
  IN p_category_id INT UNSIGNED,
  IN p_transaction_type VARCHAR(20),
  IN p_amount DECIMAL(12,2),
  IN p_description VARCHAR(255),
  IN p_transaction_date DATE
)
BEGIN
  DECLARE v_transaction_id BIGINT UNSIGNED;
  DECLARE v_category_type VARCHAR(20);
  DECLARE v_txn_type_normalized VARCHAR(20);

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SET v_txn_type_normalized = LOWER(TRIM(p_transaction_type));

  IF p_amount IS NULL OR p_amount <= 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Transaction amount must be greater than zero.';
  END IF;

  IF v_txn_type_normalized NOT IN ('income', 'expense') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'sp_add_transaction currently supports only income/expense transaction types.';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM owns o
    WHERE o.user_id = p_user_id
      AND o.account_id = p_account_id
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'User is not authorized to post to this account.';
  END IF;

  SELECT c.category_type
  INTO v_category_type
  FROM category c
  WHERE c.category_id = p_category_id;

  IF v_category_type IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Category does not exist.';
  END IF;

  IF v_category_type <> v_txn_type_normalized THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Transaction type must match category type.';
  END IF;

  START TRANSACTION;

  INSERT INTO `transaction` (
    transaction_type,
    amount,
    description,
    transaction_date
  ) VALUES (
    v_txn_type_normalized,
    p_amount,
    p_description,
    p_transaction_date
  );

  SET v_transaction_id = LAST_INSERT_ID();

  INSERT INTO records (user_id, transaction_id)
  VALUES (p_user_id, v_transaction_id);

  INSERT INTO posts_to (transaction_id, account_id)
  VALUES (v_transaction_id, p_account_id);

  -- Trigger-based budget enforcement runs here for expense categories.
  INSERT INTO categorized_as (transaction_id, category_id)
  VALUES (v_transaction_id, p_category_id);

  IF v_txn_type_normalized = 'income' THEN
    UPDATE account
    SET current_balance = current_balance + p_amount
    WHERE account_id = p_account_id;
  ELSEIF v_txn_type_normalized = 'expense' THEN
    UPDATE account
    SET current_balance = current_balance - p_amount
    WHERE account_id = p_account_id;
  END IF;

  COMMIT;

  SELECT v_transaction_id AS transaction_id;
END $$

DROP TRIGGER IF EXISTS trg_block_budget_overage $$
CREATE TRIGGER trg_block_budget_overage
BEFORE INSERT ON categorized_as
FOR EACH ROW
BEGIN
  DECLARE v_user_id INT UNSIGNED;
  DECLARE v_transaction_type VARCHAR(20);
  DECLARE v_transaction_amount DECIMAL(12,2);
  DECLARE v_transaction_date DATE;
  DECLARE v_budget_limit DECIMAL(12,2);
  DECLARE v_spent_this_month DECIMAL(12,2);

  SELECT t.transaction_type, t.amount, t.transaction_date
  INTO v_transaction_type, v_transaction_amount, v_transaction_date
  FROM `transaction` t
  WHERE t.transaction_id = NEW.transaction_id;

  IF v_transaction_type = 'expense' THEN
    SELECT r.user_id
    INTO v_user_id
    FROM records r
    WHERE r.transaction_id = NEW.transaction_id
    ORDER BY r.recorded_at ASC
    LIMIT 1;

    IF v_user_id IS NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Transaction must be linked in records before categorization.';
    END IF;

    SELECT SUM(b.monthly_limit)
    INTO v_budget_limit
    FROM budget b
    INNER JOIN user_sets us
      ON us.budget_id = b.budget_id
    INNER JOIN applies_to a
      ON a.budget_id = b.budget_id
    WHERE us.user_id = v_user_id
      AND a.category_id = NEW.category_id
      AND b.budget_month = DATE_FORMAT(v_transaction_date, '%Y-%m-01');

    IF v_budget_limit IS NOT NULL THEN
      SELECT COALESCE(SUM(t.amount), 0)
      INTO v_spent_this_month
      FROM `transaction` t
      INNER JOIN records r
        ON r.transaction_id = t.transaction_id
      INNER JOIN categorized_as ca
        ON ca.transaction_id = t.transaction_id
      WHERE r.user_id = v_user_id
        AND ca.category_id = NEW.category_id
        AND t.transaction_type = 'expense'
        AND DATE_FORMAT(t.transaction_date, '%Y-%m-01') = DATE_FORMAT(v_transaction_date, '%Y-%m-01');

      IF v_spent_this_month + v_transaction_amount > v_budget_limit THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT = 'Budget exceeded for this category and month.';
      END IF;
    END IF;
  END IF;
END $$

DELIMITER ;
