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

## Initial Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and update local credentials.
4. Ensure MySQL is running locally.
5. Initialize the database (run in this order):
   - `mysql -u root -p < app/db/schema.sql`
   - `mysql -u root -p < app/db/procedures.sql`
   - `mysql -u root -p < app/db/seed.sql`
   - `mysql -u root -p < app/db/privileges.sql`
   - If your DB was created before category-allocation budgets were added, run:
     - `mysql -u root -p < app/db/patch_budget_allocations.sql`
     - `mysql -u root -p < app/db/procedures.sql`
6. Run the app:
   - `python run.py`
7. Open `http://127.0.0.1:5001` and sign in via `Auth`.

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
├── .env.example
├── .gitignore
├── config.py
├── requirements.txt
└── run.py
```

## Collaboration Notes

- Route modules are split by domain (`auth`, `accounts`, `transactions`, etc.) so teammates can work in parallel.
- `services/` is reserved for business logic; `db/` contains reusable data access utilities.
- Add feature-specific tests in `tests/` as modules are implemented.
