# cs4750-finance-tracker

A Flask + MySQL web application scaffold for a multi-user personal finance and budget tracking system.

## Project Goals

- Support multiple authenticated users
- Track accounts, transactions, budgets, and categories
- Provide dashboard insights for personal finance management

## Tech Stack

- Python + Flask (Blueprint architecture)
- MySQL (`mysql-connector-python`)
- Environment-based configuration with `.env`

This project was originally deployed on Google Cloud Platform (Cloud Run + Cloud SQL). That hosted setup is no longer the primary workflow, and the app should now be run locally for development.

The previous Cloud Run URL is kept here for historical reference: https://cs4750-finance-tracker-172887184506.us-east4.run.app/

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start a local MySQL server.
4. Create a local `.env` file in the project root with values like:

   ```env
   FLASK_ENV=development
   FLASK_DEBUG=1
   SECRET_KEY=change-me
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=your_mysql_password
   MYSQL_DATABASE=cs4750_finance_tracker
   ```

   Leave `INSTANCE_CONNECTION_NAME` and `MYSQL_UNIX_SOCKET` unset for normal local development.

5. Create the database in MySQL if it does not already exist:
   - `CREATE DATABASE cs4750_finance_tracker;`
6. Initialize the database schema and seed data in this order:
   - `mysql -u root -p cs4750_finance_tracker < app/db/schema.sql`
   - `mysql -u root -p cs4750_finance_tracker < app/db/procedures.sql`
   - `mysql -u root -p cs4750_finance_tracker < app/db/seed.sql`
   - `mysql -u root -p cs4750_finance_tracker < app/db/privileges.sql`
7. If your local database was created before category-allocation budgets were added, run:
   - `mysql -u root -p cs4750_finance_tracker < app/db/patch_budget_allocations.sql`
   - `mysql -u root -p cs4750_finance_tracker < app/db/procedures.sql`
8. Start the Flask app:
   - `python run.py`
9. Open `http://127.0.0.1:5001` and sign in via `Auth`.

## Demo Login Accounts

After running `seed.sql`, you can use:

- `alice@example.com` / `alice123`
- `bob@example.com` / `bob123`
- `carla@example.com` / `carla123`

## Database SQL Files

- `app/db/schema.sql`: Creates all core and relationship tables with keys/constraints.
- `app/db/seed.sql`: Inserts multi-user development sample data.
- `app/db/procedures.sql`: Defines stored procedures and triggers.
- `app/db/privileges.sql`: Example least-privilege grants/revokes for app DB user.

## Project Structure

```text
cs4750-finance-tracker/
├── app/
│   ├── __init__.py
│   ├── db/
│   │   ├── schema.sql
│   │   ├── seed.sql
│   │   ├── procedures.sql
│   │   └── privileges.sql
│   ├── routes/
│   ├── services/
│   ├── static/
│   ├── templates/
│   └── utils/
├── docs/
├── tests/
├── .env
├── .gitignore
├── config.py
├── requirements.txt
└── run.py
```

## Collaboration Notes

- Route modules are split by domain (`auth`, `accounts`, `transactions`, etc.) so teammates can work in parallel.
- `services/` is reserved for business logic; `db/` contains reusable data access utilities.
- Add feature-specific tests in `tests/` as modules are implemented.
