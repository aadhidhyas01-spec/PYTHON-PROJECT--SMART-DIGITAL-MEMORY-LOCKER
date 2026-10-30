# Smart Digital Memory Locker

A Flask application prototype for storing and organizing records and uploaded files. It uses a local SQLite database as a development fallback and can optionally use Supabase through the Flask backend.

## Features

- Session-based admin login.
- Record creation, search, listing and deletion.
- Record analytics such as totals, averages, minimums and maximums.
- File upload, metadata listing and download.
- Local SQLite storage.
- Optional Supabase REST API integration.

## Technology

- Python 3.10+
- Flask
- SQLite
- Requests
- Supabase REST API (optional)

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set a private Flask session key and admin password hash. For a local-only run, keep `USE_SUPABASE=false`; the app will use `analyzer.db`.

Generate a password hash:

```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('change-this-password'))"
```

Paste the generated value into `ADMIN_PASSWORD_HASH` in `.env`. Change the example admin username and password to your own.

Start the app:

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Optional Supabase setup

1. Create the `records` and `files` tables using `setup_supabase.sql`.
2. Set `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in `.env`.
3. Set `USE_SUPABASE=true`.
4. Apply the SQL statements that enable RLS and deny direct `anon` / `authenticated` access.

The Supabase secret key is server-only. Never place it in browser JavaScript or commit it to source control.

## File storage note

Uploaded files are stored in the local `uploads/` directory. A deployment with ephemeral local storage may lose uploads when the instance is rebuilt or redeployed. Use durable object storage before relying on this for important files.

## Security follow-up required

An earlier public commit contained a Supabase server secret and a fixed Flask session key. Those values have been removed from the current source, but they remain in Git history. **Rotate the exposed Supabase secret in the Supabase dashboard immediately**, then update the value in your private `.env` or deployment secret settings. Also change any admin credentials previously used with this prototype.

## Development status

This repository is a prototype. Test authentication, uploads, database fallback and Supabase policies with test data before using real records or deploying publicly.
