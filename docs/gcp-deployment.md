# GCP Deployment Steps

This document records the steps used to deploy `cs4750-finance-tracker` to Google Cloud Platform with Cloud SQL and Cloud Run.

## 1. Create the GCP project

- Create or select a GCP project.
- Enable billing.
- Enable the required services:
  - Cloud SQL Admin API
  - Cloud Run Admin API
  - Cloud Build API
  - Artifact Registry API

## 2. Create the Cloud SQL instance

- Open `Cloud SQL` in the GCP console.
- Create a new `MySQL` instance.
- Use region `us-east4`.
- Create the instance `finance-tracker-db`.
- Create the database `cs4750_finance_tracker`.

## 3. Prepare database import files

- Update `app/db/privileges.sql` for Cloud SQL:
  - change the app user host to `'finance_app'@'%'`
  - remove broad `REVOKE` statements that fail during Cloud SQL import
- Keep the app user grants and stored procedure execute grant.

## 4. Create a Cloud Storage bucket for imports

- Create a private bucket in `us-east4`.
- Use:
  - `Region`
  - `Standard` storage class
  - `Uniform` access
  - public access prevention enabled

## 5. Import the SQL files into Cloud SQL

Import the SQL files in this order:

1. `app/db/schema.sql`
2. `app/db/procedures.sql`
3. `app/db/seed.sql`
4. `app/db/privileges.sql`

Notes:

- `schema.sql` creates and uses the database `cs4750_finance_tracker`.
- `patch_budget_allocations.sql` is only needed for older databases created before the current schema version.
- `privileges.sql` may require a strong password that satisfies the Cloud SQL password policy.

## 6. Configure the application environment

Create a local `.env` file for deployment-related settings:

```env
FLASK_ENV=production
SECRET_KEY=<strong-secret>
MYSQL_USER=finance_app
MYSQL_PASSWORD=<strong-db-password>
MYSQL_DATABASE=cs4750_finance_tracker
INSTANCE_CONNECTION_NAME=project-9c6fa737-3008-48ae-9ac:us-east4:finance-tracker-db
```

## 7. Update the app for Cloud Run + Cloud SQL

- Add support for `INSTANCE_CONNECTION_NAME` and optional Unix socket config in `config.py`.
- Update `app/db/connection.py` so the app connects through:
  - `/cloudsql/<INSTANCE_CONNECTION_NAME>` when deployed on Cloud Run
  - normal `MYSQL_HOST` and `MYSQL_PORT` when running outside Cloud Run
- Add `.env.example` documenting the required environment variables.

## 8. Add container deployment files

- Add `gunicorn` to `requirements.txt`.
- Create `Dockerfile` for the Flask app.
- Create `.dockerignore` to exclude local secrets, Git metadata, tests, and virtual environments.

## 9. Fix Cloud Build IAM permissions

When deploying from source, the build initially failed because the build service account did not have enough permissions.

Fix:

- Open `IAM & Admin > IAM`
- Add the principal:
  - `172887184506-compute@developer.gserviceaccount.com`
- Grant the role:
  - `Cloud Run Builder`

## 10. Build the container image

Use Cloud Shell and run the build from the repo directory:

```bash
gcloud config set project project-9c6fa737-3008-48ae-9ac
cd CS4750FinanceTracker
gcloud builds submit . --tag us-east4-docker.pkg.dev/project-9c6fa737-3008-48ae-9ac/cloud-run-source-deploy/cs4750-finance-tracker
```

## 11. Deploy the image to Cloud Run

Deploy the built image and attach the Cloud SQL instance:

```bash
gcloud run deploy cs4750-finance-tracker \
  --image us-east4-docker.pkg.dev/project-9c6fa737-3008-48ae-9ac/cloud-run-source-deploy/cs4750-finance-tracker \
  --region us-east4 \
  --allow-unauthenticated \
  --add-cloudsql-instances project-9c6fa737-3008-48ae-9ac:us-east4:finance-tracker-db \
  --set-env-vars FLASK_ENV=production,SECRET_KEY=<strong-secret>,MYSQL_USER=finance_app,MYSQL_PASSWORD=<strong-db-password>,MYSQL_DATABASE=cs4750_finance_tracker,INSTANCE_CONNECTION_NAME=project-9c6fa737-3008-48ae-9ac:us-east4:finance-tracker-db
```

url: https://cs4750-finance-tracker-172887184506.us-east4.run.app

## 12. Final deployment artifacts for submission

- Cloud Run URL for the deployed app
- Screenshot of the Cloud SQL instance
- Screenshot of the Cloud Run service
- Source code repository link
- This deployment guide for the final report
