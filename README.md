# CampusCart

A student marketplace built with Flask, SQLite for local development, and PostgreSQL support for Render production.

## Quick start on Windows

1. Install Python 3.10 or newer.
2. Double-click `Run_CampusCart.bat`.
3. Open `http://127.0.0.1:5000`.

The first run installs dependencies automatically.

## Important testing notes

- Use two different accounts to test chat: one buyer and one seller.
- Create a seller account, add a product, then log in as a buyer and click **Chat seller**.
- The built-in sample products do not have a seller account, so they cannot be messaged.

## Render deployment

The repository includes `render.yaml` with PostgreSQL configuration. Deploy from the project root and keep:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --workers 2 --threads 4 --bind 0.0.0.0:$PORT app:app`

Set any real payment credentials and `CAMPUS_BASE_URL` in Render environment variables before using production payments.
