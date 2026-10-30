from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
import sqlite3
import datetime
import os
import requests as http_requests

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "").strip()
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY is required. Copy .env.example to .env and set a private value.")
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'analyzer.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv', 'ppt', 'pptx', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =======================================================
#  SUPABASE CONFIG — Cloud database for records
# =======================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
SUPABASE_REST = f"{SUPABASE_URL}/rest/v1" if SUPABASE_URL else ""
SUPABASE_HEADERS = {
    "apikey": SUPABASE_SECRET_KEY,
    "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
} if SUPABASE_URL and SUPABASE_SECRET_KEY else {}
TIMEOUT = 8

# Supabase is disabled unless both server-side settings are present.
# The app falls back to its local SQLite database for development.
USE_SUPABASE = (
    os.environ.get("USE_SUPABASE", "true").lower() == "true"
    and bool(SUPABASE_URL and SUPABASE_SECRET_KEY)
)
if not USE_SUPABASE:
    print("[Config] Supabase is not configured; using local SQLite storage.")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin").strip()
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()

def supa_get(table, params=""):
    """GET records from Supabase"""
    try:
        r = http_requests.get(f"{SUPABASE_REST}/{table}?{params}", headers=SUPABASE_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Supabase GET error] {e}")
        return None

def supa_post(table, data):
    """INSERT a record into Supabase"""
    try:
        r = http_requests.post(f"{SUPABASE_REST}/{table}", json=data, headers=SUPABASE_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Supabase POST error] {e}")
        return False

def supa_delete(table, record_id):
    """DELETE a record from Supabase"""
    try:
        r = http_requests.delete(f"{SUPABASE_REST}/{table}?id=eq.{record_id}", headers=SUPABASE_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Supabase DELETE error] {e}")
        return False

def supa_get_files(params=""):
    """GET files from Supabase"""
    try:
        r = http_requests.get(f"{SUPABASE_REST}/files?{params}", headers=SUPABASE_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Supabase GET files error] {e}")
        return None

def supa_post_file(data):
    """INSERT file metadata to Supabase"""
    try:
        r = http_requests.post(f"{SUPABASE_REST}/files", json=data, headers=SUPABASE_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Supabase POST file error] {e}")
        return False

def supa_delete_file(file_id):
    """DELETE file metadata from Supabase"""
    try:
        r = http_requests.delete(f"{SUPABASE_REST}/files?id=eq.{file_id}", headers=SUPABASE_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Supabase DELETE file error] {e}")
        return False

# =======================================================
#  LOCAL SQLite — Fallback + File storage
# =======================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            value REAL NOT NULL,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            category TEXT DEFAULT 'General',
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()

init_db()

# =======================================================
#  AUTH ROUTES
# =======================================================
@app.route('/')
def home():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if (
            ADMIN_PASSWORD_HASH
            and username == ADMIN_USERNAME
            and check_password_hash(ADMIN_PASSWORD_HASH, password)
        ):
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        if not ADMIN_PASSWORD_HASH:
            return render_template(
                'login.html',
                error="Admin login is not configured. Set ADMIN_USERNAME and ADMIN_PASSWORD_HASH."
            ), 503
        return render_template('login.html', error="Invalid username or password.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard.html')

# =======================================================
#  RECORDS API — Uses Supabase first, falls back to SQLite
# =======================================================
@app.route('/api/records', methods=['GET'])
def get_records():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    search = request.args.get('search', '')

    if USE_SUPABASE:
        params = "order=id.desc"
        if search:
            params += f"&title=ilike.*{search}*"
        data = supa_get("records", params)
        if data is not None:
            return jsonify(data)
        # Fall through to SQLite if Supabase failed

    conn = get_db()
    if search:
        rows = conn.execute("SELECT * FROM records WHERE title LIKE ? OR category LIKE ? ORDER BY id DESC",
                            (f'%{search}%', f'%{search}%')).fetchall()
    else:
        rows = conn.execute("SELECT * FROM records ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/records', methods=['POST'])
def add_record():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    if not data or not data.get('title') or not data.get('value'):
        return jsonify({"error": "Title and Value are required"}), 400

    title = data['title']
    category = data.get('category', 'Performance')
    value = float(data['value'])
    date = data.get('date', datetime.date.today().isoformat())

    if USE_SUPABASE:
        ok = supa_post("records", {"title": title, "category": category, "value": value, "date": date})
        if ok:
            return jsonify({"success": True, "message": "Record saved to Supabase! ☁️"})
        # Fall through to SQLite

    conn = get_db()
    conn.execute("INSERT INTO records (title, category, value, date) VALUES (?, ?, ?, ?)",
                 (title, category, value, date))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Record saved locally 💾"})

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401

    if USE_SUPABASE:
        ok = supa_delete("records", record_id)
        if ok:
            return jsonify({"success": True, "message": "Deleted from Supabase! ☁️"})

    conn = get_db()
    conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Deleted locally 💾"})

@app.route('/api/analysis')
def analysis():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401

    # Get records (Supabase first, then SQLite fallback)
    rows = None
    if USE_SUPABASE:
        rows = supa_get("records", "select=*")

    if rows is None:
        conn = get_db()
        db_rows = conn.execute("SELECT * FROM records").fetchall()
        rows = [dict(r) for r in db_rows]
        conn.close()

    # File count from local DB
    conn = get_db()
    file_count = conn.execute("SELECT COUNT(*) as c FROM files").fetchone()['c']
    conn.close()

    if not rows:
        return jsonify({
            "total_records": 0, "average": 0, "max_val": 0,
            "min_val": 0, "performance": 0, "status": "No Data",
            "categories": {}, "file_count": file_count, "source": "supabase" if USE_SUPABASE else "local"
        })

    values = [float(r['value']) for r in rows]
    total = len(values)
    avg = round(sum(values) / total, 2)
    mx = max(values)
    mn = min(values)
    perf = min(round(avg, 2), 100)
    status = "Good" if perf >= 70 else ("Warning" if perf >= 40 else "Critical")
    cats = {}
    for r in rows:
        c = r['category']
        cats[c] = cats.get(c, 0) + 1

    return jsonify({
        "total_records": total, "average": avg, "max_val": mx,
        "min_val": mn, "performance": perf, "status": status,
        "categories": cats, "file_count": file_count,
        "source": "supabase" if USE_SUPABASE else "local"
    })

# =======================================================
#  FILES API — Always local (files stored on disk)
# =======================================================
@app.route('/api/files', methods=['GET'])
def get_files():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    
    if USE_SUPABASE:
        data = supa_get_files("order=id.desc")
        if data is not None:
            return jsonify(data)
        # Fall through to SQLite if Supabase failed
    
    conn = get_db()
    rows = conn.execute("SELECT * FROM files ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/files', methods=['POST'])
def upload_file():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    if 'file' not in request.files:
        return jsonify({"error": "No file selected"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    category = request.form.get('category', 'General')
    original_name = secure_filename(file.filename)
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    stored_name = f"{timestamp}_{original_name}"
    filepath = os.path.join(UPLOAD_FOLDER, stored_name)
    file.save(filepath)
    file_size = os.path.getsize(filepath)
    file_type = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else 'unknown'

    # Save to Supabase first
    if USE_SUPABASE:
        file_data = {
            "original_name": original_name,
            "stored_name": stored_name,
            "file_type": file_type,
            "file_size": file_size,
            "category": category
        }
        ok = supa_post_file(file_data)
        if ok:
            return jsonify({"success": True, "message": f"'{original_name}' uploaded to Supabase! ☁️"})
        # Fall through to SQLite

    # Save to SQLite as fallback
    conn = get_db()
    conn.execute("INSERT INTO files (original_name, stored_name, file_type, file_size, category) VALUES (?, ?, ?, ?, ?)",
                 (original_name, stored_name, file_type, file_size, category))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"'{original_name}' uploaded locally 💾"})

@app.route('/api/files/<int:file_id>/download')
def download_file(file_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = get_db()
    row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    conn.close()
    if not row:
        return "File not found", 404
    return send_from_directory(UPLOAD_FOLDER, row['stored_name'], as_attachment=True, download_name=row['original_name'])

@app.route('/api/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if row:
        filepath = os.path.join(UPLOAD_FOLDER, row['stored_name'])
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Delete from Supabase first
        if USE_SUPABASE:
            ok = supa_delete_file(file_id)
            if ok:
                conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
                conn.commit()
                conn.close()
                return jsonify({"success": True, "message": "File deleted from Supabase! ☁️"})
        
        # Delete from SQLite
        conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "File deleted locally 💾"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
