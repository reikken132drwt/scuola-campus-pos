from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, send_file, jsonify
import os, sys, re, datetime, random, uuid, io, csv, smtplib, qrcode, time, json, threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# Ensure Windows console never crashes on Unicode/emoji print() calls inside route handlers
for _stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from werkzeug.utils import secure_filename
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
from db_compat import DictCursorMarker, SQLiteCompatConnection, init_sqlite_db, ensure_mysql_schema

try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

try:
    import MySQLdb.cursors
except ImportError:
    class _FakeMySQLdb:
        class cursors:
            DictCursor = DictCursorMarker
    MySQLdb = _FakeMySQLdb()


# ✅ Import db from extensions
from extensions import db  

# ---------------- Flask Config ----------------
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.secret_key = os.environ.get("SECRET_KEY", "fallback_key")
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=30)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Philippine Standard Time (UTC+08:00 — no DST)
PH_TZ = datetime.timezone(datetime.timedelta(hours=8), name="Asia/Manila")


def now_pst():
    """Return current Philippine Standard Time (UTC+08:00) as a naive datetime matching MySQL session '+08:00'."""
    return datetime.datetime.now(PH_TZ).replace(tzinfo=None)


def today_pst():
    """Return current date in Philippine Standard Time (UTC+08:00)."""
    return now_pst().date()

# ✅ Configure SQLAlchemy to connect to MySQL database (with local SQLite fallback)
from urllib.parse import urlparse, unquote

_SQLITE_FALLBACK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "school_system_local.db")
_RAW_DB_URL = os.environ.get("AIVEN_DATABASE_URL") or os.environ.get("DATABASE_URL")

_MYSQL_USER = os.environ.get('MYSQL_USER', 'school_user')
_MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'qrcode12345!')
_MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
_MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
_MYSQL_DB = os.environ.get('MYSQL_DB', 'school_system')
_MYSQL_SSL = os.environ.get('MYSQL_SSL', '0') == '1'

if _RAW_DB_URL and ("mysql" in _RAW_DB_URL or "aivencloud" in _RAW_DB_URL):
    try:
        _parsed_url = urlparse(_RAW_DB_URL)
        if _parsed_url.username:
            _MYSQL_USER = unquote(_parsed_url.username)
        if _parsed_url.password:
            _MYSQL_PASSWORD = unquote(_parsed_url.password)
        if _parsed_url.hostname:
            _MYSQL_HOST = _parsed_url.hostname
        if _parsed_url.port:
            _MYSQL_PORT = int(_parsed_url.port)
        _url_path = _parsed_url.path.lstrip("/")
        if _url_path:
            _MYSQL_DB = _url_path
        if "ssl" in _RAW_DB_URL.lower() or _MYSQL_HOST not in ("localhost", "127.0.0.1"):
            _MYSQL_SSL = True
    except Exception:
        pass

if _MYSQL_HOST not in ("localhost", "127.0.0.1"):
    _MYSQL_SSL = True

_ssl_arg = "&ssl_mode=REQUIRED" if _MYSQL_SSL else ""
_MYSQL_URI = f"mysql+pymysql://{_MYSQL_USER}:{_MYSQL_PASSWORD}@{_MYSQL_HOST}:{_MYSQL_PORT}/{_MYSQL_DB}?charset=utf8mb4{_ssl_arg}"
app.config['SQLALCHEMY_DATABASE_URI'] = _MYSQL_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {'init_command': "SET time_zone = '+08:00'"}
}

# ✅ Initialize db with app
db.init_app(app)

# ✅ Import models AFTER db is initialized
from models import Student, Transaction

app.config['MYSQL_USER'] = _MYSQL_USER
app.config['MYSQL_PASSWORD'] = _MYSQL_PASSWORD
app.config['MYSQL_DB'] = _MYSQL_DB
app.config['MYSQL_HOST'] = _MYSQL_HOST
app.config['MYSQL_PORT'] = _MYSQL_PORT
app.config['MYSQL_SSL'] = _MYSQL_SSL

try:
    from flask_mysqldb import MySQL
    mysql = MySQL(app)
except ImportError:
    mysql = None


_MOBILE_HEAD_INJECTION = """
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style id="mobile-responsive-fixes">
    @media (max-width: 767px) {
      body { overflow-x: hidden; }
      body.flex.items-center.justify-center { padding: 12px; }
      .ml-64 { margin-left: 0 !important; padding: 16px !important; }
      aside.w-64.fixed, div.w-64.fixed {
        position: relative !important;
        width: 100% !important;
        height: auto !important;
      }
      table { display: block; width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
    }
  </style>
  <script id="password-eye-toggle">
    document.addEventListener("DOMContentLoaded", function() {
      function attachEyeToggles() {
        document.querySelectorAll('input[type="password"]').forEach(function(input) {
          if (input.dataset.eyeAttached) return;
          if (input.maxLength === 4 || input.name === 'pin' || input.id === 'pinInput' || input.id === 'pin') return;
          input.dataset.eyeAttached = "true";
          input.style.paddingRight = "2.75rem";
          
          var parent = input.parentElement;
          var wrapper = document.createElement("div");
          wrapper.style.position = "relative";
          wrapper.style.display = "block";
          wrapper.style.width = "100%";
          
          parent.insertBefore(wrapper, input);
          wrapper.appendChild(input);
          
          var btn = document.createElement("button");
          btn.type = "button";
          btn.tabIndex = -1;
          btn.setAttribute("aria-label", "Toggle password visibility");
          btn.style.position = "absolute";
          btn.style.right = "8px";
          btn.style.top = "50%";
          btn.style.transform = "translateY(-50%)";
          btn.style.background = "transparent";
          btn.style.border = "none";
          btn.style.cursor = "pointer";
          btn.style.padding = "6px";
          btn.style.zIndex = "10";
          btn.style.color = "#6b7280";
          btn.style.display = "flex";
          btn.style.alignItems = "center";
          btn.style.justifyContent = "center";
          
          var eyeOpen = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>';
          var eyeSlash = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"/></svg>';
          
          btn.innerHTML = eyeOpen;
          btn.addEventListener("click", function(e) {
            e.preventDefault();
            e.stopPropagation();
            if (input.type === "password") {
              input.type = "text";
              btn.innerHTML = eyeSlash;
              btn.style.color = "#7c3aed";
            } else {
              input.type = "password";
              btn.innerHTML = eyeOpen;
              btn.style.color = "#6b7280";
            }
          });
          wrapper.appendChild(btn);
        });
      }
      attachEyeToggles();
      setTimeout(attachEyeToggles, 200);
      setTimeout(attachEyeToggles, 600);
    });
  </script>
"""


import socket

def _get_local_host_ips():
    ips = {"127.0.0.1", "::1"}
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            ips.add(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return ips

_LOCAL_HOST_IPS = _get_local_host_ips()
_SESSION_HANDOFF = {}


@app.before_request
def ensure_secure_localhost_on_host_pc():
    session.permanent = True
    handoff_token = request.args.get("_sid_handoff")
    if handoff_token and handoff_token in _SESSION_HANDOFF:
        saved_session = _SESSION_HANDOFF.get(handoff_token, {})
        for k, v in saved_session.items():
            session[k] = v
        clean_args = {k: v for k, v in request.args.items() if k != "_sid_handoff"}
        qs = ("?" + "&".join(f"{k}={v}" for k, v in clean_args.items())) if clean_args else ""
        return redirect(request.path + qs)

    if request.method == "GET" and not request.path.startswith("/static/"):
        host_only = request.host.split(":")[0].lower()
        port_part = ":" + request.host.split(":")[1] if ":" in request.host else ":5000"
        ua = request.headers.get("User-Agent", "")
        is_mobile = any(m in ua for m in ("Android", "iPhone", "iPad", "iPod", "Mobile"))
        is_tunnel = bool(
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("CF-Ray")
            or "trycloudflare.com" in host_only
            or "loca.lt" in host_only
            or "ngrok" in host_only
        )
        if is_tunnel and request.headers.get("X-Forwarded-Proto") == "http":
            query = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
            return redirect(f"https://{request.host}{request.path}{query}")
        if (
            not is_tunnel
            and not is_mobile
            and host_only in _LOCAL_HOST_IPS
            and host_only not in ("127.0.0.1", "localhost")
        ):
            tok = uuid.uuid4().hex
            _SESSION_HANDOFF[tok] = dict(session)
            extra = "&open_scanner=1" if request.args.get("open_scanner") else ""
            return redirect(f"http://127.0.0.1{port_part}{request.path}?_sid_handoff={tok}{extra}")


@app.route("/switch_to_https")
def switch_to_https():
    target_path = request.args.get("next") or "/dashboard/staff"
    host_only = request.host.split(":")[0].lower()
    is_tunnel = bool(
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("CF-Ray")
        or "trycloudflare.com" in host_only
        or "loca.lt" in host_only
        or "ngrok" in host_only
        or request.is_secure
        or request.headers.get("X-Forwarded-Proto") == "https"
    )
    tok = uuid.uuid4().hex
    _SESSION_HANDOFF[tok] = dict(session)
    sep = "&" if "?" in target_path else "?"
    if is_tunnel:
        return redirect(f"https://{host_only}{target_path}{sep}_sid_handoff={tok}&open_scanner=1")
    return redirect(f"https://{host_only}:5443{target_path}{sep}_sid_handoff={tok}&open_scanner=1")


@app.after_request
def inject_mobile_responsiveness(response):
    try:
        # ⚡ Cache static assets (images, logos, scripts) for instant load
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
            return response

        if response.content_type and "text/html" in response.content_type and not response.direct_passthrough:
            html = response.get_data(as_text=True)
            if "</head>" in html and 'id="mobile-responsive-fixes"' not in html:
                if 'name="viewport"' in html:
                    style_only = _MOBILE_HEAD_INJECTION.split("\n", 2)[2]
                    html = html.replace("</head>", style_only + "\n</head>", 1)
                else:
                    html = html.replace("</head>", _MOBILE_HEAD_INJECTION + "\n</head>", 1)
                response.set_data(html)
    except Exception:
        pass
    return response



def generate_fixed_qr(student_id):
    # Create QR code with student_id (or school_id)
    qr = qrcode.make(student_id)

    # Ensure folder exists
    qr_folder = os.path.join("static", "qrcodes")
    os.makedirs(qr_folder, exist_ok=True)

    # Save QR file
    qr_path = os.path.join(qr_folder, f"{student_id}.png")
    qr.save(qr_path)

    return qr_path

                                
# ---------------- Upload Config ----------------
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# --------------- Routes ---------------

@app.route("/") 
def index():
    # Main landing page for students
    return render_template("index.html")

@app.route("/staff")
def index_staff():
    # Staff landing page
    return render_template("index_staff.html")

@app.route("/admin")
def index_admin():
    # Admin landing page
    return render_template("index_admin.html")

@app.route('/login_page')
def login_page():
    return render_template('login.html')


@app.route('/signup')
def signup():
    return render_template('signup.html')


# ---------------- Multi-Tab Role-Independent Session Helpers ----------------
def _get_logged_in_student():
    if session.get("role") != "student":
        return None
    student_id = session.get("student_id")
    student_email = session.get("student_email") or session.get("email")
    if not student_id and not student_email:
        return None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        if student_id:
            cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
        else:
            cursor.execute("SELECT * FROM students WHERE email=%s", (student_email,))
        student = cursor.fetchone()
        conn.close()
        if student:
            session["student_id"] = student["student_id"]
            session["student_email"] = student["email"]
        return student
    except Exception:
        return None


def _get_logged_in_staff():
    if session.get("role") != "staff":
        return None
    staff_id = session.get("staff_id")
    staff_email = session.get("staff_email") or session.get("email")
    if not staff_id and not staff_email:
        return None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        if staff_id:
            cursor.execute(
                "SELECT staff_id, full_name, email, contact_number, created_at, COALESCE(status, 'approved') AS status FROM staff WHERE staff_id=%s",
                (staff_id,),
            )
        else:
            cursor.execute(
                "SELECT staff_id, full_name, email, contact_number, created_at, COALESCE(status, 'approved') AS status FROM staff WHERE email=%s",
                (staff_email,),
            )
        staff = cursor.fetchone()
        conn.close()
        if staff:
            if str(staff.get("status") or "approved").strip().lower() != "approved":
                return None
            session["staff_id"] = staff["staff_id"]
            session["staff_email"] = staff["email"]
        return staff
    except Exception:
        return None


def _get_logged_in_admin():
    if session.get("role") != "admin":
        return None
    admin_id = session.get("admin_id")
    admin_email = session.get("admin_email") or session.get("email")
    if not admin_id and not admin_email:
        return None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        if admin_id:
            cursor.execute(
                "SELECT admin_id, full_name, email, contact_number, COALESCE(status, 'approved') AS status, COALESCE(is_main_admin, 0) AS is_main_admin FROM admins WHERE admin_id=%s",
                (admin_id,),
            )
        else:
            cursor.execute(
                "SELECT admin_id, full_name, email, contact_number, COALESCE(status, 'approved') AS status, COALESCE(is_main_admin, 0) AS is_main_admin FROM admins WHERE email=%s",
                (admin_email,),
            )
        admin = cursor.fetchone()
        conn.close()
        if admin:
            if str(admin.get("status") or "approved").strip().lower() != "approved":
                return None
            session["admin_id"] = admin["admin_id"]
            session["admin_email"] = admin["email"]
            session["is_main_admin"] = int(admin.get("is_main_admin") or 0)
        return admin
    except Exception:
        return None


# ---------------- Admin Pending Top-Ups ----------------
@app.route("/admin/pending_topups")
def admin_pending_topups():
    admin = _get_logged_in_admin()
    if not admin:
        flash("Unauthorized access.", "error")
        return redirect(url_for("signin_admin"))

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)


    # Fetch all pending top-ups
    cursor.execute("""
        SELECT t.topup_id, s.full_name, s.school_id, t.amount, t.payment_mode, 
               t.reference_number, t.created_at
        FROM topups t
        JOIN students s ON t.student_id = s.student_id
        WHERE t.status='pending'
        ORDER BY t.created_at DESC
    """)
    pending_topups = cursor.fetchall()
    conn.close()

    return render_template("admin_pending_topups.html", pending_topups=pending_topups)


# Registered Students
@app.route('/admin/registered')
def dashboard_registered():
    admin = _get_logged_in_admin()
    if not admin:
        flash("Unauthorized access. Admin privileges required.", "error")
        return redirect(url_for("signin_admin"))

    return redirect(url_for("dashboard_admin", section="registered"))

# Transactions
@app.route('/dashboard/transactions')
def dashboard_transactions():
    admin = _get_logged_in_admin()
    staff = _get_logged_in_staff()
    if not admin and not staff:
        flash("Unauthorized access. Admin or Staff privileges required.", "error")
        return redirect(url_for("signin_staff"))

    start = request.args.get("start_date")
    end = request.args.get("end_date")

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    query = """
        SELECT t.transaction_id, t.created_at, t.type, t.amount, t.payment_mode,
               COALESCE(s.full_name, a.full_name) AS performed_by,
               st.full_name AS customer_name, st.school_id AS id_no, t.remarks
        FROM transactions t
        LEFT JOIN staff s ON t.staff_id = s.staff_id
        LEFT JOIN admins a ON t.admin_id = a.admin_id
        LEFT JOIN students st ON t.student_id = st.student_id
        WHERE 1=1
    """
    params = []
    if start:
        query += " AND t.created_at >= %s"
        params.append(start)
    if end:
        query += " AND t.created_at <= %s"
        params.append(end)

    query += " ORDER BY t.created_at DESC"
    cursor.execute(query, params)
    transactions = cursor.fetchall()
    conn.close()

    return render_template('student_transactions.html', transactions=transactions)





# -------------------
# Authentication + Student Routes
# -------------------

@app.route("/logout")
def logout():
    ref = (request.referrer or "").lower()
    role = request.args.get("role") or session.get("role")
    if "/dashboard/staff" in ref or "/staff" in ref:
        role = "staff"
    elif "/dashboard/admin" in ref or "/admin" in ref:
        role = "admin"
    elif "/dashboard/student" in ref or "/student" in ref:
        role = "student"

    session.clear()
    flash("You have been safely logged out.", "success")
    if role == "staff":
        return redirect(url_for("signin_staff"))
    elif role == "admin":
        return redirect(url_for("signin_admin"))
    else:
        return redirect(url_for("signin_student"))

@app.route("/profile")
def profile_student():
    student = _get_logged_in_student()
    if not student:
        return redirect(url_for("login_page"))

    return render_template("profile.html", student=student)




@app.route("/db_structure")
def db_structure():
    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # Query all tables + columns in your current schema
    cursor.execute("""
        SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
               COLUMN_DEFAULT, COLUMN_KEY, EXTRA
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
        ORDER BY TABLE_NAME, ORDINAL_POSITION;
    """)
    columns = cursor.fetchall()
    conn.close()

    # Group by table
    tables = {}
    for col in columns:
        table = col["TABLE_NAME"]
        if table not in tables:
            tables[table] = []
        tables[table].append(col)

    # Render HTML
    html = "<h2>Database Structure</h2>"
    for table, cols in tables.items():
        html += f"<h3>{table}</h3>"
        html += "<table border='1' cellpadding='6' style='border-collapse:collapse;'>"
        html += "<tr><th>Column</th><th>Type</th><th>Nullable</th><th>Default</th><th>Key</th><th>Extra</th></tr>"
        for c in cols:
            html += f"<tr><td>{c['COLUMN_NAME']}</td><td>{c['COLUMN_TYPE']}</td><td>{c['IS_NULLABLE']}</td>"
            html += f"<td>{c['COLUMN_DEFAULT']}</td><td>{c['COLUMN_KEY']}</td><td>{c['EXTRA']}</td></tr>"
        html += "</table><br>"
    return html

# --------------- Password Validation Function ---------------
import re

def is_strong_password(password):
    """
    Validates password strength:
    - At least 8 characters
    - Contains at least one number
    - Contains at least one special character
    """
    if len(password) < 8:
        return False
    if not re.search(r"\d", password):  # must contain a number
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):  # must contain a special character
        return False
    return True


# ---------------- Database Connection ----------------
_SQLITE_INITIALIZED = False
_ACTIVE_DB_TYPE = "pymysql" if os.environ.get("USE_SQLITE") != "1" else "sqlite"
_ACTIVE_PYMYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
_LAST_MYSQL_CHECK = 0
_MYSQL_CHECK_COOLDOWN = 30  # Re-check MySQL every 30 seconds if offline


def get_connection():
    global _SQLITE_INITIALIZED, _ACTIVE_DB_TYPE, _ACTIVE_PYMYSQL_PORT, _LAST_MYSQL_CHECK
    now = time.time()

    # 1. Primary: Direct PyMySQL connection to MySQL (Local or Cloud Aiven)
    if _ACTIVE_DB_TYPE != "sqlite" or (now - _LAST_MYSQL_CHECK > _MYSQL_CHECK_COOLDOWN):
        try:
            import pymysql
            target_host = app.config.get("MYSQL_HOST", "localhost")
            target_port = int(app.config.get("MYSQL_PORT", 3306))
            is_remote = target_host not in ("localhost", "127.0.0.1")
            is_ssl = app.config.get("MYSQL_SSL", False) or is_remote
            ssl_kwargs = {"ssl": {"ssl_mode": "REQUIRED"}} if is_ssl else {}

            ports_to_try = [target_port] if is_remote else ([_ACTIVE_PYMYSQL_PORT] if _ACTIVE_PYMYSQL_PORT else [target_port, 3306, 3307])
            for port in set(ports_to_try):
                if not port:
                    continue
                try:
                    conn = pymysql.connect(
                        host=target_host,
                        port=port,
                        user=app.config.get("MYSQL_USER", "school_user"),
                        password=app.config.get("MYSQL_PASSWORD", "qrcode12345!"),
                        database=app.config.get("MYSQL_DB", "school_system"),
                        autocommit=True,
                        charset="utf8mb4",
                        init_command="SET time_zone = '+08:00'",
                        connect_timeout=8.0 if is_remote else 1.5,
                        **ssl_kwargs
                    )
                    ensure_mysql_schema(conn)
                    _ACTIVE_DB_TYPE = "pymysql"
                    _ACTIVE_PYMYSQL_PORT = port
                    return conn
                except Exception:
                    continue
        except ImportError:
            pass

        # Try Flask-MySQLdb if available
        if mysql is not None:
            try:
                conn = mysql.connection
                if conn is not None:
                    try:
                        _tz_cur = conn.cursor()
                        _tz_cur.execute("SET time_zone = '+08:00'")
                        _tz_cur.close()
                    except Exception:
                        pass
                    ensure_mysql_schema(conn)
                    _ACTIVE_DB_TYPE = "flask_mysql"
                    return conn
            except Exception:
                pass

    # 2. Fallback to local SQLite database ONLY if MySQL is completely offline
    _ACTIVE_DB_TYPE = "sqlite"
    _LAST_MYSQL_CHECK = now
    if not _SQLITE_INITIALIZED:
        init_sqlite_db(_SQLITE_FALLBACK_PATH)
        _SQLITE_INITIALIZED = True
    return SQLiteCompatConnection(_SQLITE_FALLBACK_PATH)


def hash_user_password(password):
    """Generate a compact PBKDF2 hash that fits inside VARCHAR(120+) columns."""
    return generate_password_hash(password, method="pbkdf2:sha256")


def verify_user_password(stored_password, entered_password):
    """Verify password against Werkzeug hash or plaintext DB entry (including mobile auto-cap tolerance)."""
    if not stored_password or entered_password is None:
        return False
    stored_str = str(stored_password).strip()
    entered_str = str(entered_password)
    entered_clean = entered_str.strip()
    candidates = [entered_str, entered_clean]
    if entered_clean:
        swapped = entered_clean[0].swapcase() + entered_clean[1:]
        if swapped not in candidates:
            candidates.append(swapped)

    for cand in candidates:
        if stored_str == cand:
            return True
        try:
            if check_password_hash(stored_str, cand):
                return True
        except Exception:
            pass
    return False


# ---------------- Email Function ----------------
FROM_EMAIL = "sanielken11@gmail.com"
REPLY_TO_EMAIL = "sanielken11@gmail.com"


def _send_email_via_http(sender_email, to_emails, subject, body_text, body_html):
    """Send email over HTTPS (port 443) when an HTTP email provider env var is configured.
    Render Free Tier blocks outbound SMTP ports (25, 465, 587), so HTTPS APIs/webhooks are required there.
    """
    import json as _json
    import urllib.request as _urllib_req

    webhook_url = (os.environ.get("EMAIL_WEBHOOK_URL") or "").strip()
    brevo_key = (os.environ.get("BREVO_API_KEY") or "").strip()
    sendgrid_key = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    resend_key = (os.environ.get("RESEND_API_KEY") or "").strip()

    sender_name = "Scuola Dei Bambini De Sta. Terisita International Montessori School Inc."

    if webhook_url:
        if "/edit" in webhook_url:
            print(f"⚠️ [HTTP Webhook Error] EMAIL_WEBHOOK_URL contains '/edit'. Please use the deployed Web App URL ending in '/exec'!", flush=True)
            return False

        payload_dict = {
            "to": ", ".join(to_emails),
            "subject": subject,
            "text": body_text or "",
            "html": body_html or "",
            "senderName": sender_name,
        }
        try:
            try:
                import requests as _requests
                resp = _requests.post(
                    webhook_url,
                    json=payload_dict,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    timeout=15,
                    allow_redirects=True,
                )
                print(f"⚡ [HTTP Webhook Email] Sent to {to_emails} (status {resp.status_code}) -> {resp.text[:80]}", flush=True)
                return resp.status_code in (200, 201, 302)
            except ImportError:
                payload = _json.dumps(payload_dict).encode("utf-8")
                req = _urllib_req.Request(
                    webhook_url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    },
                    method="POST",
                )
                with _urllib_req.urlopen(req, timeout=15) as resp:
                    resp_text = resp.read().decode("utf-8", errors="ignore")
                    print(f"⚡ [HTTP Webhook Email] Sent to {to_emails} (status {resp.status}) -> {resp_text[:80]}", flush=True)
                return True
        except Exception as e:
            print(f"❌ [HTTP Webhook Error] Failed to call webhook: {e}", flush=True)
            return False

    if brevo_key:
        payload = _json.dumps({
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": addr} for addr in to_emails],
            "subject": subject,
            "htmlContent": body_html or f"<pre>{body_text or ''}</pre>",
            "textContent": body_text or "",
        }).encode("utf-8")
        req = _urllib_req.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={"api-key": brevo_key, "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with _urllib_req.urlopen(req, timeout=15) as resp:
            print(f"⚡ [Brevo API Email] Sent to {to_emails} (status {resp.status})", flush=True)
        return True

    if sendgrid_key:
        content_list = []
        if body_text:
            content_list.append({"type": "text/plain", "value": body_text})
        if body_html:
            content_list.append({"type": "text/html", "value": body_html})
        payload = _json.dumps({
            "personalizations": [{"to": [{"email": addr} for addr in to_emails]}],
            "from": {"email": sender_email, "name": sender_name},
            "subject": subject,
            "content": content_list or [{"type": "text/plain", "value": ""}],
        }).encode("utf-8")
        req = _urllib_req.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=payload,
            headers={"Authorization": f"Bearer {sendgrid_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with _urllib_req.urlopen(req, timeout=15) as resp:
            print(f"⚡ [SendGrid API Email] Sent to {to_emails} (status {resp.status})", flush=True)
        return True

    if resend_key:
        resend_from = (os.environ.get("RESEND_FROM_EMAIL") or f"{sender_name} <onboarding@resend.dev>").strip()
        payload = _json.dumps({
            "from": resend_from,
            "to": to_emails,
            "subject": subject,
            "html": body_html or "",
            "text": body_text or "",
        }).encode("utf-8")
        req = _urllib_req.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with _urllib_req.urlopen(req, timeout=15) as resp:
            print(f"⚡ [Resend API Email] Sent to {to_emails} (status {resp.status})", flush=True)
        return True

    return False


def _send_email_thread(sender_email, password, to_emails, msg_str, subject="", body_text=None, body_html=None):
    try:
        if _send_email_via_http(sender_email, to_emails, subject, body_text, body_html):
            return
    except Exception as http_err:
        print(f"❌ [HTTP Email] Error sending to {to_emails}: {http_err}", flush=True)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)  # Gmail SMTP
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, to_emails, msg_str)
        server.quit()
        print(f"⚡ [Async Email] Sent successfully to {to_emails}", flush=True)
    except Exception as e:
        print(f"❌ [Async Email] Error sending to {to_emails}: {str(e)}", flush=True)


def send_email(to_emails=None, subject="", body_text=None, body_html=None, to=None, body=None, async_send=True):
    sender_email = "sanielken11@gmail.com"
    password = "puan lwgw pwtq rezt"  # Use Gmail/Outlook App Password

    if to and not to_emails:
        to_emails = [to] if isinstance(to, str) else list(to)
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    if not to_emails:
        return False
    if body and not body_text:
        body_text = body

    from email.utils import formataddr
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.image import MIMEImage

    msg_root = MIMEMultipart("related")
    msg_root["From"] = formataddr(("Scuola Dei Bambini De Sta. Terisita International Montessori School Inc.", sender_email))
    msg_root["To"] = ", ".join(to_emails)
    msg_root["Subject"] = subject

    msg_alt = MIMEMultipart("alternative")
    msg_root.attach(msg_alt)

    if body_text:
        msg_alt.attach(MIMEText(body_text, "plain"))
    if body_html:
        msg_alt.attach(MIMEText(body_html, "html"))

    # Auto-embed Scuola dei Bambini Logo as CID for inline display in email clients
    logo_path = os.path.join(BASE_DIR, "static", "images", "bambini_logo.png")
    if os.path.exists(logo_path) and ("cid:school_logo" in (body_html or "")):
        try:
            with open(logo_path, "rb") as f:
                img_data = f.read()
            img_part = MIMEImage(img_data, _subtype="png")
            img_part.add_header("Content-ID", "<school_logo>")
            img_part.add_header("Content-Disposition", "inline", filename="bambini_logo.png")
            msg_root.attach(img_part)
        except Exception as img_err:
            print(f"Warning attaching school logo CID: {img_err}")

    msg_str = msg_root.as_string()
    if async_send:
        # ⚡ Run in background thread so the HTTP request completes in <20ms instead of waiting 3-5 seconds!
        threading.Thread(
            target=_send_email_thread,
            args=(sender_email, password, to_emails, msg_str, subject, body_text, body_html),
            daemon=True,
        ).start()
        return True
    else:
        try:
            _send_email_thread(sender_email, password, to_emails, msg_str, subject, body_text, body_html)
            return True
        except Exception:
            return False


# ---------------- OTP Function ----------------
def generate_and_send_otp(email, subject="Your Secure Login OTP", role="student"):
    email = (email or "").strip()
    otp = str(random.randint(100000, 999999))
    expires = now_pst() + datetime.timedelta(minutes=10)

    # Always store in session (including role-specific keys so multi-tab OTP logins never collide)
    session["pending_otp"] = otp
    session["pending_email"] = email
    session["role"] = role
    session[f"pending_otp_{role}"] = otp
    session[f"pending_email_{role}"] = email

    # Also store in the otps table in the database
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO otps (email, otp_code, expires_at) VALUES (%s,%s,%s)",
            (email, otp, expires),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Warning saving OTP to DB: {e}")

    print(f"\n==========================================", flush=True)
    print(f"🔐 [OTP GENERATED] Role: {role.upper()} | Email: {email} | OTP: {otp}", flush=True)
    print(f"==========================================\n", flush=True)

    # Role-specific body text
    if role == "student":
        body_text = f"Hello Student,\n\nYour OTP is: {otp} (expires in 10 minutes).\n\nUse this to access your student dashboard."
    elif role == "admin":
        body_text = f"Hello Admin,\n\nYour OTP is: {otp} (expires in 10 minutes).\n\nUse this to access the admin dashboard securely."
    elif role == "staff":
        body_text = f"Hello Staff,\n\nYour OTP is: {otp} (expires in 10 minutes).\n\nUse this to access the staff dashboard securely."
    else:
        body_text = f"Your OTP is: {otp} (expires in 10 minutes)."

    # Load HTML template with Jinja2
    try:
        template_dir = os.path.join(BASE_DIR, "templates")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("otp_template.html")
        body_html = template.render(otp=otp, role=role)
    except Exception as e:
        print(f"⚠️ Warning: Could not render otp_template.html ({e}). Using formatted HTML fallback.")
        body_html = f"<div style='font-family:Arial,sans-serif;padding:24px;border:1px solid #e2e8f0;border-radius:12px;max-width:480px;margin:auto;text-align:center;'><img src='cid:school_logo' alt='Scuola dei Bambini' width='64' height='64' style='border-radius:50%;margin-bottom:8px;'><h2 style='color:#6366f1;margin:0 0 8px;'>Campus E-Wallet OTP</h2><p style='font-size:15px;color:#334155;'>{body_text.replace(chr(10), '<br>')}</p><div style='text-align:center;margin:20px 0;'><span style='font-size:32px;font-weight:bold;letter-spacing:6px;background:#f3e8ff;color:#6b21a8;padding:12px 24px;border-radius:8px;display:inline-block;border:1px dashed #c084fc;'>{otp}</span></div><p style='color:#64748b;font-size:12px;'>Expires in 10 minutes. Do not share this code with anyone.</p></div>"

    send_email([email], subject, body_text, body_html)
    return otp


def is_valid_otp(email, entered_otp):
    """Validate entered OTP against both Flask session and the otps database table."""
    entered_clean = (entered_otp or "").strip()
    if not entered_clean:
        return False

    session_otp = str(session.get("pending_otp") or "").strip()
    if session_otp and entered_clean == session_otp:
        return True

    for r in ("student", "staff", "admin"):
        role_otp = str(session.get(f"pending_otp_{r}") or "").strip()
        if role_otp and entered_clean == role_otp:
            return True

    if email:
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT otp_code, expires_at FROM otps WHERE email=%s ORDER BY id DESC LIMIT 5",
                (email.strip(),),
            )
            records = cursor.fetchall() or []
            conn.close()
            for rec in records:
                db_otp = str(rec[0] if not isinstance(rec, dict) else rec.get("otp_code", "")).strip()
                if db_otp and entered_clean == db_otp:
                    return True
        except Exception as e:
            print(f"Warning checking OTP in DB: {e}")

    return False


# ---------------- Forgot Password (Student) ----------------
@app.route("/forgot_password/student", methods=["GET", "POST"])
def forgot_password_student():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        session.pop("security_verified_student", None)

        conn = get_connection()
        cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        cursor.execute(
            "SELECT email, security_q1, security_q2, security_q3 FROM students WHERE LOWER(email)=LOWER(%s)",
            (email,),
        )
        student = cursor.fetchone()
        conn.close()

        if not student:
            flash("No student account found with that email.", "error")
            return redirect(url_for("forgot_password_student"))

        # Store canonical email in session for later steps
        session["reset_email"] = student["email"]
        session["pending_email"] = student["email"]
        return render_template("answer_security.html", student=student)

    return render_template("forgot_password_student.html")


@app.route("/verify_security_answers", methods=["POST"])
def verify_security_answers():
    email = session.get("reset_email") or session.get("pending_email")
    if not email:
        flash("Your password reset session expired. Please enter your email again.", "error")
        return redirect(url_for("forgot_password_student"))

    a1 = (request.form.get("security_a1") or "").strip().lower()
    a2 = (request.form.get("security_a2") or "").strip().lower()
    a3 = (request.form.get("security_a3") or "").strip().lower()

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
    cursor.execute(
        "SELECT security_q1, security_q2, security_q3, security_a1, security_a2, security_a3 FROM students WHERE LOWER(email)=LOWER(%s)",
        (email,),
    )
    student = cursor.fetchone()
    conn.close()

    if (
        student
        and (student["security_a1"] or "").strip().lower() == a1
        and (student["security_a2"] or "").strip().lower() == a2
        and (student["security_a3"] or "").strip().lower() == a3
    ):
        session["security_verified_student"] = True
        return redirect(url_for("reset_password_student"))
    else:
        flash("One or more security answers did not match. Please try again.", "error")
        if student:
            return render_template("answer_security.html", student=student)
        return redirect(url_for("forgot_password_student"))


@app.route("/reset_password/student", methods=["GET", "POST"])
def reset_password_student():
    email = session.get("reset_email") or session.get("pending_email")
    if not email or not session.get("security_verified_student"):
        flash("Please verify your email and security questions first.", "error")
        return redirect(url_for("forgot_password_student"))

    if request.method == "POST":
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        password_regex = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$")
        if not password_regex.match(new_password):
            flash("Password must be at least 8 characters with uppercase, lowercase, number, and special character.", "error")
            return redirect(url_for("reset_password_student"))

        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("reset_password_student"))

        hashed_pass = hash_user_password(new_password)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE students SET password=%s WHERE LOWER(email)=LOWER(%s)", (hashed_pass, email))
        conn.commit()
        conn.close()

        session.pop("security_verified_student", None)
        session["password_reset_flow"] = True
        generate_and_send_otp(email, subject="Confirm Your Password Reset", role="student")

        flash("Password updated. Please check your email for OTP confirmation.", "success")
        return redirect(url_for("verify_otp"))

    return render_template("reset_password_student.html")


# ---------------- Forgot Password (Admin) ----------------
@app.route("/forgot_admin", methods=["GET", "POST"])
@app.route("/forgot_password/admin", methods=["GET", "POST"])
def forgot_password_admin():
    if request.method == "POST":
        if "email" in request.form:
            # Step 1: user entered their email
            email = (request.form.get("email") or "").strip()
            session.pop("security_verified_admin", None)
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT email, security_q1, security_q2, security_q3
                   FROM admins WHERE LOWER(email)=LOWER(%s)""",
                (email,),
            )
            record = cursor.fetchone()
            conn.close()

            if record:
                session["pending_email"] = record[0]
                return render_template(
                    "forgot_admin_questions.html",
                    question1=record[1],
                    question2=record[2],
                    question3=record[3],
                )
            else:
                flash("Admin email not found.", "error")
                return redirect(url_for("forgot_password_admin"))
        else:
            # Step 2: user answered questions
            email = session.get("pending_email")
            if not email:
                flash("Your password reset session expired. Please enter your email again.", "error")
                return redirect(url_for("forgot_password_admin"))

            a1 = (request.form.get("answer1") or "").strip().lower()
            a2 = (request.form.get("answer2") or "").strip().lower()
            a3 = (request.form.get("answer3") or "").strip().lower()

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT security_q1, security_q2, security_q3, security_a1, security_a2, security_a3
                   FROM admins WHERE LOWER(email)=LOWER(%s)""",
                (email,),
            )
            record = cursor.fetchone()
            conn.close()

            if (
                record
                and (record[3] or "").strip().lower() == a1
                and (record[4] or "").strip().lower() == a2
                and (record[5] or "").strip().lower() == a3
            ):
                session["security_verified_admin"] = True
                return redirect(url_for("reset_password_admin"))
            else:
                flash("Incorrect security answers. Please try again.", "error")
                if record:
                    return render_template(
                        "forgot_admin_questions.html",
                        question1=record[0],
                        question2=record[1],
                        question3=record[2],
                    )
                return redirect(url_for("forgot_password_admin"))

    return render_template("forgot_admin.html")


# ---------------- Forgot Password (Staff) ----------------
@app.route("/forgot_staff", methods=["GET", "POST"])
@app.route("/forgot_password/staff", methods=["GET", "POST"])
def forgot_password_staff():
    if request.method == "POST":
        if "email" in request.form:
            # Step 1: user entered their email
            email = (request.form.get("email") or "").strip()
            session.pop("security_verified_staff", None)
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT email, security_q1, security_q2, security_q3
                   FROM staff WHERE LOWER(email)=LOWER(%s)""",
                (email,),
            )
            record = cursor.fetchone()
            conn.close()

            if record:
                session["pending_email"] = record[0]
                return render_template(
                    "forgot_staff_questions.html",
                    question1=record[1],
                    question2=record[2],
                    question3=record[3],
                )
            else:
                flash("Staff email not found.", "error")
                return redirect(url_for("forgot_password_staff"))
        else:
            # Step 2: user answered questions
            email = session.get("pending_email")
            if not email:
                flash("Your password reset session expired. Please enter your email again.", "error")
                return redirect(url_for("forgot_password_staff"))

            a1 = (request.form.get("answer1") or "").strip().lower()
            a2 = (request.form.get("answer2") or "").strip().lower()
            a3 = (request.form.get("answer3") or "").strip().lower()

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT security_q1, security_q2, security_q3, security_a1, security_a2, security_a3
                   FROM staff WHERE LOWER(email)=LOWER(%s)""",
                (email,),
            )
            record = cursor.fetchone()
            conn.close()

            if (
                record
                and (record[3] or "").strip().lower() == a1
                and (record[4] or "").strip().lower() == a2
                and (record[5] or "").strip().lower() == a3
            ):
                session["security_verified_staff"] = True
                return redirect(url_for("reset_password_staff"))
            else:
                flash("Incorrect security answers. Please try again.", "error")
                if record:
                    return render_template(
                        "forgot_staff_questions.html",
                        question1=record[0],
                        question2=record[1],
                        question3=record[2],
                    )
                return redirect(url_for("forgot_password_staff"))

    return render_template("forgot_staff.html")


# ---------------- Login ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        conn = get_connection()
        cursor = conn.cursor()

        # Check Student
        cursor.execute("SELECT student_id, email, password FROM students WHERE email=%s", (email,))
        student = cursor.fetchone()
        if student and verify_user_password(student[2], password):
            conn.close()
            session.clear()
            session["role"] = "student"
            session["student_id"] = student[0]
            session["student_email"] = student[1]
            session["pending_email"] = student[1]
            generate_and_send_otp(email, subject="Your Student OTP Code", role="student")
            return redirect(url_for("verify_otp"))

        # Check Admin
        cursor.execute("SELECT admin_id, email, password FROM admins WHERE email=%s", (email,))
        admin = cursor.fetchone()
        if admin and verify_user_password(admin[2], password):
            conn.close()
            session.clear()
            session["role"] = "admin"
            session["admin_id"] = admin[0]
            session["admin_email"] = admin[1]
            session["pending_email"] = admin[1]
            generate_and_send_otp(email, subject="Your Admin OTP Code", role="admin")
            return redirect(url_for("verify_otp"))

        # Check Staff
        cursor.execute("SELECT staff_id, email, password FROM staff WHERE email=%s", (email,))
        staff = cursor.fetchone()
        if staff and verify_user_password(staff[2], password):
            conn.close()
            session.clear()
            session["role"] = "staff"
            session["staff_id"] = staff[0]
            session["staff_email"] = staff[1]
            session["pending_email"] = staff[1]
            generate_and_send_otp(email, subject="Your Staff OTP Code", role="staff")
            return redirect(url_for("verify_otp"))

        conn.close()
        flash("Invalid credentials.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


# ---------------- Student Sign Up ----------------
@app.route("/signup/student", methods=["GET","POST"])
def signup_student():
    if request.method == "POST":
        try:
            # Collect and validate form data
            full_name = (request.form.get("full_name") or "").strip()
            school_id = (request.form.get("school_id") or "").strip()
            email = (request.form.get("email") or "").strip()
            parent_email = (request.form.get("parent_email") or "").strip()
            contact_number = (request.form.get("contact_number") or "").strip()
            strand = (request.form.get("strand") or "").strip()
            guardian_name = (request.form.get("guardian_name") or "").strip()
            grade_level = (request.form.get("grade_level") or "").strip()
            password = request.form.get("password") or ""
            confirm_password = request.form.get("confirm_password") or ""

            # 🔹 Validations
            if not re.match(r"^\d{7}$", school_id):
                flash("❌ School ID must be exactly 7 digits.", "error")
                return redirect(url_for("signup_student"))
            if not re.match(r"^09\d{9}$", contact_number):
                flash("❌ Phone number must start with 09 and be 11 digits.", "error")
                return redirect(url_for("signup_student"))
            if not email.endswith("@gmail.com") or not parent_email.endswith("@gmail.com"):
                flash("❌ Emails must be Gmail addresses.", "error")
                return redirect(url_for("signup_student"))
            password_regex = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$")
            if not password_regex.match(password):
                flash("❌ Password must meet complexity requirements.", "error")
                return redirect(url_for("signup_student"))
            if password != confirm_password:
                flash("❌ Passwords do not match.", "error")
                return redirect(url_for("signup_student"))
            if len(request.form.get("security_a1","").strip()) < 3 or len(request.form.get("security_a2","").strip()) < 3 or len(request.form.get("security_a3","").strip()) < 3:
                flash("❌ Security answers must be at least 3 characters long.", "error")
                return redirect(url_for("signup_student"))

            # Check if email or school_id is already registered
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT student_id FROM students WHERE email=%s OR school_id=%s", (email, school_id))
            existing = cursor.fetchone()
            conn.close()
            if existing:
                flash("❌ A student with that Email or School ID already exists.", "error")
                return redirect(url_for("signup_student"))

            # 🔹 Save data temporarily in session
            session["pending_signup"] = {
                "full_name": full_name,
                "school_id": school_id,
                "email": email,
                "parent_email": parent_email,
                "contact_number": contact_number,
                "strand": strand,
                "guardian_name": guardian_name,
                "grade_level": grade_level,
                "hashed_pass": hash_user_password(password),
                "security_q1": request.form["security_q1"],
                "security_a1": request.form["security_a1"].strip(),
                "security_q2": request.form["security_q2"],
                "security_a2": request.form["security_a2"].strip(),
                "security_q3": request.form["security_q3"],
                "security_a3": request.form["security_a3"].strip(),
            }
            session["role"] = "student"
            session["student_signup"] = True
            session["pending_email"] = email

            # 🔹 Generate OTP and send email
            generate_and_send_otp(email, subject="Your Secure OTP Code", role="student")

            flash("We sent an OTP to your email. Please verify.", "info")
            return redirect(url_for("verify_otp"))

        except Exception as e:
            flash(f"General error: {str(e)}", "error")
            return redirect(url_for("signup_student"))

    return render_template("signup_student.html")


@app.route("/generate_all_qr")
def generate_all_qr():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT student_id FROM students WHERE qr_code IS NULL OR qr_code=''")
        students = cursor.fetchall()

        count = 0
        for (student_id,) in students:
            qr_path = generate_fixed_qr(student_id)
            cursor.execute("UPDATE students SET qr_code=%s WHERE student_id=%s", (qr_path, student_id))
            count += 1

        conn.commit()
        conn.close()
        return f"✅ Generated QR codes for {count} students."
    except Exception as e:
        return f"❌ Error generating QR codes: {str(e)}"


@app.route("/setup_pin", methods=["GET","POST"])
def setup_pin():
    try:
        if request.method == "POST":
            pin = (request.form.get("pin") or "").strip()
            if not re.match(r"^\d{4}$", pin):
                flash("❌ PIN must be 4 digits.", "error")
                return redirect(url_for("setup_pin"))

            data = session.get("pending_signup")
            email = (data.get("email") if data else None) or session.get("pending_email") or session.get("email")
            if not data and not email:
                flash("❌ No signup data found.", "error")
                return redirect(url_for("signup_student"))

            conn = get_connection()
            cursor = conn.cursor()

            # Check if verify_otp already inserted the student record
            cursor.execute("SELECT student_id, school_id FROM students WHERE email=%s", (email,))
            existing_student = cursor.fetchone()

            if existing_student:
                student_id = existing_student[0]
                school_id = existing_student[1]
                qr_path = generate_fixed_qr(school_id or student_id)
                cursor.execute(
                    "UPDATE students SET pin=%s, qr_code=%s WHERE student_id=%s",
                    (pin, qr_path, student_id),
                )
                conn.commit()
            elif data:
                qr_path = generate_fixed_qr(data["school_id"])
                cursor.execute(
                    """INSERT INTO students 
                    (full_name, school_id, email, contact_number, strand, guardian_name, parent_email, grade_level,
                     password, pin, security_q1, security_a1, security_q2, security_a2, security_q3, security_a3, qr_code)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        data["full_name"], data["school_id"], data["email"], data["contact_number"], data["strand"],
                        data["guardian_name"], data["parent_email"], data["grade_level"], data["hashed_pass"], pin,
                        data["security_q1"], data["security_a1"], data["security_q2"], data["security_a2"],
                        data["security_q3"], data["security_a3"], qr_path,
                    ),
                )
                conn.commit()

            conn.close()

            flash("🎉 Account created successfully! Please sign in.", "success")
            session.pop("pending_signup", None)
            session.pop("student_signup", None)
            session.pop("pending_otp", None)
            return redirect(url_for("signin_student"))

        return render_template("setup_pin.html")
    except Exception as e:
        flash(f"Error setting PIN: {str(e)}", "error")
        return redirect(url_for("signup_student"))


@app.route("/confirm_signup", methods=["GET","POST"])
def confirm_signup():
    email = session.get("pending_email")
    if not email:
        flash("No pending signup found.", "error")
        return redirect(url_for("signup_student"))

    if request.method == "POST":
        otp = (request.form.get("otp") or "").strip()
        if is_valid_otp(email, otp):
            flash("Signup confirmed! Please log in.", "success")
            return redirect(url_for("signin_student"))
        else:
            flash("Invalid or expired confirmation code.", "error")
            return redirect(url_for("confirm_signup"))

    return render_template("confirm_signup.html", email=email)


# ---------------- Admin Sign Up ----------------
@app.route("/signup/admin", methods=["GET", "POST"])
def signup_admin():
    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        contact_number = (request.form.get("contact_number") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        # Security questions
        security_q1 = request.form.get("security_q1")
        security_a1 = (request.form.get("security_a1") or "").strip()
        security_q2 = request.form.get("security_q2")
        security_a2 = (request.form.get("security_a2") or "").strip()
        security_q3 = request.form.get("security_q3")
        security_a3 = (request.form.get("security_a3") or "").strip()

        # Hash password
        hashed_pw = hash_user_password(password)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT admin_id, LOWER(COALESCE(status, 'approved')) FROM admins WHERE LOWER(email)=LOWER(%s)",
                (email,),
            )
            existing = cursor.fetchone()
            if existing:
                ex_id, ex_status = existing[0], str(existing[1] or "approved").lower()
                if ex_status == "pending":
                    conn.close()
                    flash("⏳ An Admin registration for this email is already pending approval by the Main Administrator.", "info")
                    return redirect(url_for("signin_admin"))
                elif ex_status == "approved":
                    conn.close()
                    flash("⚠️ An active Admin account with this email already exists. Please sign in.", "error")
                    return redirect(url_for("signin_admin"))
                else:
                    cursor.execute(
                        """
                        UPDATE admins
                        SET full_name=%s, contact_number=%s, password=%s, status='pending', is_main_admin=0,
                            security_q1=%s, security_a1=%s, security_q2=%s, security_a2=%s,
                            security_q3=%s, security_a3=%s
                        WHERE admin_id=%s
                        """,
                        (
                            full_name, contact_number, hashed_pw,
                            security_q1, security_a1, security_q2, security_a2,
                            security_q3, security_a3, ex_id,
                        ),
                    )
                    conn.commit()
                    conn.close()
                    flash("✅ Admin registration re-submitted! Your account is pending approval by the Main Administrator.", "success")
                    return redirect(url_for("signin_admin"))

            cursor.execute("SELECT COUNT(*) FROM admins WHERE LOWER(COALESCE(status, 'approved')) = 'approved'")
            approved_count = (cursor.fetchone() or [0])[0] or 0
            initial_status = "approved" if int(approved_count) == 0 else "pending"
            initial_main = 1 if int(approved_count) == 0 else 0

            cursor.execute(
                """
                INSERT INTO admins (full_name, contact_number, email, password, status, is_main_admin,
                                    security_q1, security_a1, security_q2, security_a2,
                                    security_q3, security_a3)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    full_name, contact_number, email, hashed_pw, initial_status, initial_main,
                    security_q1, security_a1, security_q2, security_a2,
                    security_q3, security_a3,
                ),
            )
            conn.commit()
            conn.close()
            if initial_status == "approved":
                flash("Main Admin account created successfully. Please log in.", "success")
            else:
                flash("✅ Admin registration submitted! Your account is pending approval by the Main Administrator before you can sign in.", "success")
            return redirect(url_for("signin_admin"))
        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for("signup_admin"))

    return render_template("signup_admin.html")


# ---------------- Staff Sign Up ----------------
@app.route("/signup/staff", methods=["GET", "POST"])
def signup_staff():
    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        contact_number = (request.form.get("contact_number") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        # Security questions
        security_q1 = request.form.get("security_q1")
        security_a1 = (request.form.get("security_a1") or "").strip()
        security_q2 = request.form.get("security_q2")
        security_a2 = (request.form.get("security_a2") or "").strip()
        security_q3 = request.form.get("security_q3")
        security_a3 = (request.form.get("security_a3") or "").strip()

        # Hash password
        hashed_pw = hash_user_password(password)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT staff_id, LOWER(COALESCE(status, 'approved')) FROM staff WHERE LOWER(email)=LOWER(%s)",
                (email,),
            )
            existing = cursor.fetchone()
            if existing:
                ex_id, ex_status = existing[0], str(existing[1] or "approved").lower()
                if ex_status == "pending":
                    conn.close()
                    flash("⏳ A Canteen Staff registration for this email is already pending approval by the Main Administrator.", "info")
                    return redirect(url_for("signin_staff"))
                elif ex_status == "approved":
                    conn.close()
                    flash("⚠️ An active Canteen Staff account with this email already exists. Please sign in.", "error")
                    return redirect(url_for("signin_staff"))
                else:
                    cursor.execute(
                        """
                        UPDATE staff
                        SET full_name=%s, contact_number=%s, password=%s, status='pending',
                            security_q1=%s, security_a1=%s, security_q2=%s, security_a2=%s,
                            security_q3=%s, security_a3=%s
                        WHERE staff_id=%s
                        """,
                        (
                            full_name, contact_number, hashed_pw,
                            security_q1, security_a1, security_q2, security_a2,
                            security_q3, security_a3, ex_id,
                        ),
                    )
                    conn.commit()
                    conn.close()
                    flash("✅ Canteen Staff registration re-submitted! Your account is pending approval by the Main Administrator.", "success")
                    return redirect(url_for("signin_staff"))

            cursor.execute(
                """
                INSERT INTO staff (full_name, contact_number, email, password, status,
                                   security_q1, security_a1, security_q2, security_a2,
                                   security_q3, security_a3)
                VALUES (%s,%s,%s,%s,'pending',%s,%s,%s,%s,%s,%s)
                """,
                (
                    full_name, contact_number, email, hashed_pw,
                    security_q1, security_a1, security_q2, security_a2,
                    security_q3, security_a3,
                ),
            )
            conn.commit()
            conn.close()
            flash("✅ Canteen Staff registration submitted! Your account is pending approval by the Main Administrator before you can sign in.", "success")
            return redirect(url_for("signin_staff"))
        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for("signup_staff"))

    return render_template("signup_staff.html")


def _attempt_role_login(email_input, password, preferred_role="student"):
    """Strictly authenticate against preferred_role only to enforce role isolation and prevent cross-role access."""
    email_clean = (email_input or "").strip()
    conn = get_connection()
    cursor = conn.cursor()

    if preferred_role == "student":
        cursor.execute(
            "SELECT student_id, email, password FROM students WHERE LOWER(email)=LOWER(%s) OR school_id=%s",
            (email_clean, email_clean),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            flash(f"❌ No student account found for '{email_clean}'.", "error")
            return redirect(url_for("signin_student"))
        if not verify_user_password(row[2], password):
            flash(f"❌ Incorrect password for {email_clean}. Please check your password or use Forgot Password.", "error")
            return redirect(url_for("signin_student"))

        session.clear()
        session["role"] = "student"
        session["student_id"] = row[0]
        session["student_email"] = row[1]
        session["pending_email"] = row[1]
        generate_and_send_otp(row[1], subject="Your Secure Login OTP", role="student")
        flash("OTP sent to your email. Please verify.", "info")
        return redirect(url_for("verify_otp"))

    elif preferred_role == "staff":
        cursor.execute(
            "SELECT staff_id, email, password, COALESCE(status, 'approved') FROM staff WHERE LOWER(email)=LOWER(%s)",
            (email_clean,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            flash(f"❌ Access Denied: No Canteen Staff account registered for '{email_clean}'.", "error")
            return redirect(url_for("signin_staff"))
        if not verify_user_password(row[2], password):
            flash(f"❌ Incorrect password for {email_clean}. Please check your password or use Forgot Password.", "error")
            return redirect(url_for("signin_staff"))

        staff_status = str(row[3] or "approved").strip().lower()
        if staff_status == "pending":
            flash("⏳ Account Pending Approval: Your Canteen Staff registration is awaiting approval from the Main Administrator.", "error")
            return redirect(url_for("signin_staff"))
        if staff_status != "approved":
            flash("🚫 Access Denied: Your Canteen Staff account registration was rejected or deactivated by the Main Administrator.", "error")
            return redirect(url_for("signin_staff"))

        session.clear()
        session["role"] = "staff"
        session["staff_id"] = row[0]
        session["staff_email"] = row[1]
        session["pending_email"] = row[1]
        generate_and_send_otp(row[1], subject="Your Staff Secure Login OTP", role="staff")
        flash("OTP sent to your email. Please verify.", "info")
        return redirect(url_for("verify_otp"))

    elif preferred_role == "admin":
        cursor.execute(
            "SELECT admin_id, email, password, COALESCE(status, 'approved'), COALESCE(is_main_admin, 0) FROM admins WHERE LOWER(email)=LOWER(%s)",
            (email_clean,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            flash(f"❌ Access Denied: No Admin account registered for '{email_clean}'.", "error")
            return redirect(url_for("signin_admin"))
        if not verify_user_password(row[2], password):
            flash(f"❌ Incorrect password for {email_clean}. Please check your password or use Forgot Password.", "error")
            return redirect(url_for("signin_admin"))

        admin_status = str(row[3] or "approved").strip().lower()
        if admin_status == "pending":
            flash("⏳ Account Pending Approval: Your Admin registration is awaiting approval from the Main Administrator.", "error")
            return redirect(url_for("signin_admin"))
        if admin_status != "approved":
            flash("🚫 Access Denied: Your Admin account registration was rejected or deactivated by the Main Administrator.", "error")
            return redirect(url_for("signin_admin"))

        session.clear()
        session["role"] = "admin"
        session["admin_id"] = row[0]
        session["admin_email"] = row[1]
        session["is_main_admin"] = int(row[4] or 0)
        session["pending_email"] = row[1]
        generate_and_send_otp(row[1], subject="Your Admin Secure Login OTP", role="admin")
        flash("OTP sent to your email. Please verify.", "info")
        return redirect(url_for("verify_otp"))

    conn.close()
    flash("Invalid portal selection.", "error")
    return redirect(url_for("signin_student"))


# ---------------- Student Sign In ----------------
@app.route("/signin/student", methods=["GET","POST"])
def signin_student():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        try:
            resp = _attempt_role_login(email, password, preferred_role="student")
            if resp:
                return resp
        except Exception as e:
            flash(f"Error signing in: {str(e)}", "error")
        return redirect(url_for("signin_student"))

    return render_template("signin_student.html")


# ---------------- Admin Sign In ----------------
@app.route("/signin/admin", methods=["GET","POST"])
def signin_admin():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        try:
            resp = _attempt_role_login(email, password, preferred_role="admin")
            if resp:
                return resp
        except Exception as e:
            flash(f"Error signing in: {str(e)}", "error")
        return redirect(url_for("signin_admin"))

    return render_template("signin_admin.html")


# ---------------- Staff Sign In ----------------
@app.route("/signin/staff", methods=["GET","POST"])
def signin_staff():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        try:
            resp = _attempt_role_login(email, password, preferred_role="staff")
            if resp:
                return resp
        except Exception as e:
            flash(f"Error signing in: {str(e)}", "error")
        return redirect(url_for("signin_staff"))

    return render_template("signin_staff.html")


# ---------------- Reset Password (Admin) ----------------
@app.route("/reset_password/admin", methods=["GET","POST"])
def reset_password_admin():
    email = session.get("pending_email")
    if not email or not session.get("security_verified_admin"):
        flash("Please verify your admin email and security questions first.", "error")
        return redirect(url_for("forgot_password_admin"))

    if request.method == "POST":
        new_pass = request.form.get("new_password") or ""
        confirm_pass = request.form.get("confirm_password") or ""

        password_regex = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$")
        if not password_regex.match(new_pass):
            flash("Password must be at least 8 characters with uppercase, lowercase, number, and special character.", "error")
            return redirect(url_for("reset_password_admin"))

        if new_pass == confirm_pass:
            hashed_pass = hash_user_password(new_pass)

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE admins SET password=%s WHERE LOWER(email)=LOWER(%s)",
                    (hashed_pass, email),
                )
                conn.commit()
                conn.close()

                session.pop("security_verified_admin", None)
                flash("Password reset successful. Please log in.", "success")
                return redirect(url_for("signin_admin"))
            except Exception as e:
                flash(f"Database error: {str(e)}", "error")
                return redirect(url_for("reset_password_admin"))
        else:
            flash("Passwords do not match.", "error")
            return redirect(url_for("reset_password_admin"))

    return render_template("reset_password_admin.html")


# ---------------- Reset Password (Staff) ----------------
@app.route("/reset_password/staff", methods=["GET","POST"])
def reset_password_staff():
    email = session.get("pending_email")
    if not email or not session.get("security_verified_staff"):
        flash("Please verify your staff email and security questions first.", "error")
        return redirect(url_for("forgot_password_staff"))

    if request.method == "POST":
        new_pass = request.form.get("new_password") or ""
        confirm_pass = request.form.get("confirm_password") or ""

        password_regex = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$")
        if not password_regex.match(new_pass):
            flash("Password must be at least 8 characters with uppercase, lowercase, number, and special character.", "error")
            return redirect(url_for("reset_password_staff"))

        if new_pass == confirm_pass:
            hashed_pass = hash_user_password(new_pass)

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE staff SET password=%s WHERE LOWER(email)=LOWER(%s)",
                    (hashed_pass, email),
                )
                conn.commit()
                conn.close()

                session.pop("security_verified_staff", None)
                flash("Password reset successful. Please log in.", "success")
                return redirect(url_for("signin_staff"))
            except Exception as e:
                flash(f"Database error: {str(e)}", "error")
                return redirect(url_for("reset_password_staff"))
        else:
            flash("Passwords do not match.", "error")
            return redirect(url_for("reset_password_staff"))

    return render_template("reset_password_staff.html")


# ---------------- Verify OTP ----------------
@app.route("/verify_otp", methods=["GET","POST"])
def verify_otp():
    try:
        if request.method == "POST":
            entered_otp = (request.form.get("otp") or "").strip()
            email = (
                session.get("pending_email")
                or (session.get("pending_signup") or {}).get("email")
                or session.get("reset_email")
                or session.get("email")
            )
            matched_role = None
            for r in ("student", "staff", "admin"):
                if str(session.get(f"pending_otp_{r}") or "").strip() == entered_otp and entered_otp:
                    matched_role = r
                    email = session.get(f"pending_email_{r}") or email
                    break

            if is_valid_otp(email, entered_otp):
                role = matched_role or session.get("role") or ("student" if session.get("pending_signup") else None)
                session.pop("pending_otp", None)
                if role:
                    session.pop(f"pending_otp_{role}", None)

                # Case 0: Student Password Reset confirmation flow
                if session.pop("password_reset_flow", None):
                    flash("✅ Password reset confirmed! Please sign in.", "success")
                    return redirect(url_for("signin_student"))

                # Case 1: Student Signup flow
                if (role == "student" and session.get("student_signup")) or session.get("pending_signup"):
                    student_data = session.get("pending_signup")
                    if student_data:
                        student_id = student_data["school_id"]
                        qr_path = generate_fixed_qr(student_id)

                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT student_id FROM students WHERE email=%s", (student_data["email"],))
                        already = cursor.fetchone()
                        if not already:
                            cursor.execute(
                                """
                                INSERT INTO students (full_name, school_id, email, parent_email, contact_number,
                                                      strand, guardian_name, grade_level, password, security_q1,
                                                      security_a1, security_q2, security_a2, security_q3, security_a3, qr_code)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                """,
                                (
                                    student_data["full_name"], student_data["school_id"], student_data["email"],
                                    student_data["parent_email"], student_data["contact_number"], student_data["strand"],
                                    student_data["guardian_name"], student_data["grade_level"], student_data["hashed_pass"],
                                    student_data["security_q1"], student_data["security_a1"], student_data["security_q2"],
                                    student_data["security_a2"], student_data["security_q3"], student_data["security_a3"],
                                    qr_path,
                                ),
                            )
                            conn.commit()
                        conn.close()

                    flash("✅ OTP verified! Please set your 4-digit PIN.", "success")
                    return redirect(url_for("setup_pin"))

                # Case 2: Student Signin flow
                elif role == "student":
                    session["email"] = email
                    session["student_email"] = email
                    flash("✅ OTP verified! Please enter your PIN.", "success")
                    return redirect(url_for("verify_pin"))

                # Case 3: Admin Signin flow
                elif role == "admin":
                    session["email"] = email
                    session["admin_email"] = email
                    flash("✅ Admin OTP verified! Redirecting to dashboard...", "success")
                    return redirect(url_for("dashboard_admin"))

                # Case 4: Staff Signin flow
                elif role == "staff":
                    session["email"] = email
                    session["staff_email"] = email
                    flash("✅ Staff OTP verified! Redirecting to dashboard...", "success")
                    return redirect(url_for("dashboard_staff"))

                else:
                    flash("⚠️ No signup or signin context found.", "error")
                    return redirect(url_for("login"))

            else:
                flash("❌ Invalid OTP. Try again.", "error")
                return redirect(url_for("verify_otp"))

        target_email = (
            session.get("pending_email")
            or (session.get("pending_signup") or {}).get("email")
            or session.get("email")
        )
        return render_template("verify_otp.html", target_email=target_email)
    except Exception as e:
        flash(f"Error verifying OTP: {str(e)}", "error")
        return redirect(url_for("login"))


@app.route("/forgot_pin", methods=["GET", "POST"])
def forgot_pin():
    email = session.get("student_email") or session.get("email") or session.get("pending_email")
    if not email:
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("signin_student"))

    if request.method == "POST":
        user_answer = (request.form.get("answer") or "").strip().lower()
        expected_answer = (session.get("pin_reset_answer") or "").strip().lower()
        if expected_answer and user_answer == expected_answer:
            return redirect(url_for("reset_pin"))
        else:
            flash("Incorrect answer.", "error")
            return redirect(url_for("forgot_pin"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT security_q1, security_a1, security_q2, security_a2, security_q3, security_a3 
           FROM students WHERE email=%s""",
        (email,),
    )
    record = cursor.fetchone()
    conn.close()

    if not record:
        flash("No security questions found.", "error")
        return redirect(url_for("verify_pin"))

    # Pick one random question on GET only
    questions = [(record[0], record[1]), (record[2], record[3]), (record[4], record[5])]
    question, answer = random.choice(questions)
    session["pin_reset_answer"] = answer

    return render_template("forgot_pin.html", question=question)


@app.route("/reset_pin", methods=["GET", "POST"])
def reset_pin():
    if request.method == "POST":
        new_pin = (request.form.get("new_pin") or "").strip()
        if not new_pin.isdigit() or len(new_pin) != 4:
            flash("PIN must be exactly 4 numeric digits.", "error")
            return redirect(url_for("reset_pin"))

        email = session.get("student_email") or session.get("email") or session.get("pending_email")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE students SET pin=%s WHERE email=%s", (new_pin, email))
        conn.commit()
        conn.close()

        if "student_id" in session:
            flash("PIN reset successful! You can now use your new PIN.", "success")
            return redirect(url_for("dashboard_student"))

        flash("PIN reset successful. Please enter your new PIN.", "success")
        return redirect(url_for("verify_pin"))

    return render_template("reset_pin.html")


@app.route("/verify_pin", methods=["GET", "POST"])
def verify_pin():
    if request.method == "POST":
        entered_pin = (request.form.get("pin") or "").strip()
        if not entered_pin and request.is_json:
            entered_pin = str((request.get_json() or {}).get("pin") or "").strip()

        email = (
            session.get("pending_email_student")
            or session.get("student_email")
            or session.get("pending_email")
            or session.get("email")
        )
        if not email and session.get("student_id"):
            st = _get_logged_in_student()
            if st:
                email = st.get("email")

        # If called via fetch/AJAX from dashboard to unlock Fixed QR
        is_ajax = bool(request.is_json 
                       or (request.headers.get("Accept") and "application/json" in request.headers.get("Accept"))
                       or request.headers.get("X-Requested-With") == "XMLHttpRequest")

        if not email:
            if is_ajax:
                return jsonify(success=False, message="Session expired. Please log in again."), 401
            flash("Session expired. Please log in again.", "error")
            return redirect(url_for("signin_student"))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT student_id, pin, qr_code, school_id FROM students WHERE email=%s", (email,))
        record = cursor.fetchone()
        conn.close()

        if is_ajax:
            if record and str(record[1] or "").strip() == entered_pin:
                student_id = record[0]
                qr_code = record[2]
                school_id = record[3] or str(student_id)
                qr_filename = f"{student_id}.png"
                if qr_code and not os.path.isabs(qr_code):
                    qr_filename = os.path.basename(qr_code)
                # Ensure QR file exists on disk
                qr_folder = os.path.join("static", "qrcodes")
                os.makedirs(qr_folder, exist_ok=True)
                full_qr_path = os.path.join(qr_folder, qr_filename)
                if not os.path.exists(full_qr_path):
                    img = qrcode.make(str(school_id))
                    img.save(full_qr_path)
                return jsonify(success=True, qr_filename=qr_filename)
            else:
                return jsonify(success=False, message="Incorrect PIN. Please try again."), 400

        if record and str(record[1] or "").strip() == entered_pin:
            session["student_id"] = record[0]
            session["student_email"] = email
            session["email"] = email
            session["role"] = "student"
            return redirect(url_for("dashboard_student"))
        else:
            flash("Invalid PIN. Try again.", "error")
            return redirect(url_for("verify_pin"))

    return render_template("verify_pin.html")


@app.route("/resend_otp")
def resend_otp():
    email = (
        session.get("pending_email")
        or (session.get("pending_signup") or {}).get("email")
        or session.get("reset_email")
    )
    role = session.get("role") or ("student" if session.get("pending_signup") else "student")

    if not email:
        flash("No pending OTP request.", "error")
        return redirect(url_for("login"))

    generate_and_send_otp(email, subject=f"Resent {role.capitalize()} OTP Code", role=role)
    flash("A new OTP has been sent to your email.", "success")
    return redirect(url_for("verify_otp"))



# ---------------- Student Dashboard ----------------
@app.route("/student/dashboard")
@app.route("/dashboard/student")
def dashboard_student():
    student = _get_logged_in_student()
    if not student:
        return redirect(url_for("signin_student"))

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # Transaction history
    cursor.execute("""
        SELECT
            CASE
                WHEN t.type = 'topup' THEN 'Top-Up'
                WHEN t.type = 'purchase' THEN 'Purchase'
                ELSE t.type
            END AS type,
            t.amount,
            t.created_at,
            t.status,
            COALESCE(s.full_name, a.full_name) AS performed_by
        FROM transactions t
        LEFT JOIN staff s ON t.staff_id = s.staff_id
        LEFT JOIN admins a ON t.admin_id = a.admin_id
        WHERE t.student_id = %s
        ORDER BY t.created_at DESC
    """, (student["student_id"],))
    transactions = cursor.fetchall()

    # Balance trend
    cursor.execute("""
        SELECT DATE(created_at) AS date, new_balance
        FROM transactions
        WHERE student_id=%s AND status='completed'
        ORDER BY created_at
    """, (student["student_id"],))
    balance_data = cursor.fetchall()

    balance_dates = [row["date"].strftime("%Y-%m-%d") for row in balance_data]
    balance_values = [float(row["new_balance"]) if row["new_balance"] is not None else 0.0 for row in balance_data]

    # ⚠️ Do not manually close conn here — Flask handles teardown
    # Pending top-ups
    cursor.execute("""
        SELECT topup_id, amount, reference_number, status, created_at
        FROM topups
        WHERE student_id=%s AND status='pending'
        ORDER BY created_at DESC
    """, (student["student_id"],))
    pending_topups = cursor.fetchall() or []

    # ✅ Safe render_template return
    return render_template(
        "dashboard_student.html",
        student=student,
        transactions=transactions,
        pending_topups=pending_topups,
        balance_dates=balance_dates,
        balance_values=balance_values
    )


# ---------------- Fixed QR ----------------
@app.route("/fixed_qr", methods=["POST"])
def fixed_qr():
    pin = request.form.get("pin")
    student_id = session.get("student_id")

    if not student_id:
        return "No student logged in", 401

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pin, qr_code FROM students WHERE student_id=%s", (student_id,))
    record = cursor.fetchone()
    # ⚠️ Do not manually close conn here — Flask handles teardown

    if not record:
        return "Student not found", 404

    # Debug logs
    print("Entered PIN:", pin)
    print("DB PIN:", record[0])
    print("QR Path:", record[1])

    if str(record[0]).strip() == str(pin).strip():
        qr_path = record[1]
        if not qr_path or not os.path.exists(qr_path):
            return "QR file not found", 404
        return send_file(qr_path, mimetype="image/png")
    else:
        return "Invalid PIN", 401



@app.route("/download_fixed_qr")
def download_fixed_qr():
    try:
        student_id = session.get("student_id")
        if not student_id:
            flash("⚠️ No student logged in.", "error")
            return redirect(url_for("signin_student"))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT qr_code FROM students WHERE student_id=%s", (student_id,))
        record = cursor.fetchone()
        conn.close()

        qr_folder = os.path.join("static", "qrcodes")
        os.makedirs(qr_folder, exist_ok=True)
        qr_path = record[0] if (record and record[0]) else None
        if qr_path and not os.path.isabs(qr_path):
            qr_path = os.path.join(os.getcwd(), qr_path)

        if not qr_path or not os.path.exists(qr_path):
            qr_filename = f"{student_id}.png"
            qr_path = os.path.join(qr_folder, qr_filename)
            img = qrcode.make(str(student_id))
            img.save(qr_path)
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE students SET qr_code=%s WHERE student_id=%s", (qr_path, student_id))
            conn.commit()
            conn.close()

        return send_file(
            qr_path,
            mimetype="image/png",
            as_attachment=True,   # 🔹 forces download
            download_name=f"{student_id}_fixed_qr.png"
        )
    except Exception as e:
        flash(f"Error downloading QR: {str(e)}", "error")
        return redirect(url_for("dashboard_student"))




# ---------------- Staff Fixed QR & Scan Staff QR ----------------
@app.route("/fixed_qr/<int:staff_id>")
def staff_fixed_qr_image(staff_id):
    qr_payload = f"STAFF-{staff_id}"
    qr_folder = os.path.join("static", "staff_qrcodes")
    os.makedirs(qr_folder, exist_ok=True)
    qr_path = os.path.join(qr_folder, f"{staff_id}.png")
    if not os.path.exists(qr_path):
        qr_img = qrcode.make(qr_payload)
        qr_img.save(qr_path)
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE staff SET staff_qr=%s WHERE staff_id=%s", (qr_payload, staff_id))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return send_file(qr_path, mimetype="image/png")


@app.route("/scan_staff_qr", methods=["POST"])
def scan_staff_qr():
    data = request.get_json() if request.is_json else (request.form or {})
    qr_value = (data.get("staff_qr") or data.get("staffQr") or data.get("qr") or "").strip()

    if not qr_value:
        return jsonify(success=False, message="Empty QR code"), 400

    parsed_id = qr_value
    if qr_value.upper().startswith("STAFF-"):
        parsed_id = qr_value.split("-", 1)[1].strip()

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
    cursor.execute(
        """SELECT staff_id, full_name, email, contact_number
           FROM staff
           WHERE staff_qr=%s OR CAST(staff_id AS CHAR)=%s OR email=%s""",
        (qr_value, parsed_id, qr_value),
    )
    staff = cursor.fetchone()
    conn.close()

    if staff:
        return jsonify(success=True, staff={
            "staff_id": staff["staff_id"],
            "full_name": staff["full_name"],
            "email": staff["email"],
            "contact_number": staff.get("contact_number", ""),
        })
    else:
        return jsonify(success=False, message="Staff member not found. Please scan an authorized staff QR."), 400


# ---------------- Student Direct Payment to Staff ----------------
@app.route("/student_pay_staff", methods=["POST"])
def student_pay_staff():
    student = _get_logged_in_student()
    if not student:
        return jsonify(success=False, message="Unauthorized access."), 403

    data = request.get_json() if request.is_json else (request.form or {})
    staff_id = data.get("staff_id")
    try:
        amount = Decimal(str(data.get("amount") or 0))
    except Exception:
        return jsonify(success=False, message="Invalid payment amount."), 400

    pin = str(data.get("pin") or "").strip()
    remarks = str(data.get("remarks") or "Canteen Purchase").strip()

    if not staff_id or amount <= 0:
        return jsonify(success=False, message="Please specify a valid staff ID and positive amount."), 400

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # 1. Verify student PIN
    if pin and str(student.get("pin") or "").strip() != pin:
        conn.close()
        return jsonify(success=False, message="Incorrect 4-digit PIN. Transaction cancelled."), 400

    current_balance = Decimal(str(student["balance"] or 0))
    if current_balance < amount:
        conn.close()
        return jsonify(success=False, message=f"Insufficient wallet balance. You only have ₱{current_balance:.2f}."), 400

    # 2. Verify staff member
    cursor.execute("SELECT staff_id, full_name FROM staff WHERE staff_id=%s", (staff_id,))
    staff = cursor.fetchone()
    if not staff:
        conn.close()
        return jsonify(success=False, message="Staff member not found."), 404

    # 3. Deduct balance and record transaction
    new_balance = current_balance - amount
    cursor.execute("UPDATE students SET balance=%s WHERE student_id=%s", (new_balance, student["student_id"]))
    cursor.execute("""
        INSERT INTO transactions (student_id, staff_id, amount, previous_balance, new_balance,
                                  status, type, payment_mode, remarks, created_at)
        VALUES (%s, %s, %s, %s, %s, 'completed', 'purchase', 'cashless', %s, NOW())
    """, (student["student_id"], staff["staff_id"], amount, current_balance, new_balance, remarks))
    conn.commit()
    conn.close()

    return jsonify(
        success=True,
        message=f"₱{amount:.2f} successfully paid to {staff['full_name']}!",
        new_balance=float(new_balance)
    )


@app.route("/download_transactions_pdf")
def download_transactions_pdf():
    student = _get_logged_in_student()
    if not student:
        return redirect(url_for("signin_student"))

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT 
            CASE 
                WHEN t.type = 'Top-Up' THEN 'Top-Up'
                WHEN t.type = 'Purchase' THEN 'Purchase'
                ELSE t.type
            END AS txn_type,
            t.created_at,
            t.amount,
            COALESCE(s.full_name, a.full_name) AS performed_by
        FROM transactions t
        LEFT JOIN staff s ON t.staff_id = s.staff_id
        LEFT JOIN admins a ON t.admin_id = a.admin_id
        WHERE t.student_id = %s
        ORDER BY t.created_at DESC
    """, (student["student_id"],))
    rows = cursor.fetchall()
    conn.close()

    # 🔹 Generate PDF without crashing on Unicode peso symbol
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=14)

    pdf.cell(190, 10, txt="Scuola dei Bambini - Student Transaction Statement", ln=True, align="C")
    pdf.set_font("helvetica", size=9)
    pdf.cell(190, 6, txt=f"Generated for: {student.get('email', '')}", ln=True, align="C")
    pdf.ln(6)

    # Table header
    pdf.set_font("helvetica", 'B', 10)
    pdf.cell(35, 8, "Type", 1)
    pdf.cell(50, 8, "Date", 1)
    pdf.cell(40, 8, "Amount (PHP)", 1)
    pdf.cell(65, 8, "Handled By", 1)
    pdf.ln()

    # Table rows
    pdf.set_font("helvetica", size=9)
    for row in rows:
        pdf.cell(35, 7, str(row["txn_type"] or ""), 1)
        pdf.cell(50, 7, str(row["created_at"] or "")[:19], 1)
        pdf.cell(40, 7, f"PHP {float(row['amount']):.2f}", 1)
        pdf.cell(65, 7, str(row["performed_by"] if row["performed_by"] else "-")[:28], 1)
        pdf.ln()

    # Output PDF bytes safely
    response = Response(bytes(pdf.output()))
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=transactions.pdf"
    return response


# ---------------- Student Top-Up ----------------
@app.route("/topup", methods=["POST"])
def topup():
    student = _get_logged_in_student()
    if not student:
        return redirect(url_for("signin_student"))

    reference_number = request.form.get("reference_number")
    amount = Decimal(str(request.form.get("amount") or 0))
    payment_mode = request.form.get("payment_mode", "gcash")
    screenshot = request.files.get("screenshot") or request.files.get("proof")

    student_id = student["student_id"]
    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # Save screenshot safely with unique timestamp
    screenshot_filename = None
    if screenshot and screenshot.filename:
        screenshot_filename = f"{student_id}_{int(time.time())}_{secure_filename(screenshot.filename)}"
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        screenshot.save(os.path.join(app.config["UPLOAD_FOLDER"], screenshot_filename))

    # Insert into topups table only (pending)
    cursor.execute("""
        INSERT INTO topups (student_id, payment_mode, amount, reference_number, screenshot_path, status, created_at)
        VALUES (%s, %s, %s, %s, %s, 'pending', NOW())
    """, (student_id, payment_mode, amount, reference_number, screenshot_filename))

    conn.commit()
    conn.close()

    flash("Top-up submitted successfully and awaiting admin approval.", "info")
    return redirect(url_for("dashboard_student"))

@app.route("/submit_topup", methods=["POST"])
def submit_topup():
    student = _get_logged_in_student()
    student_id = student["student_id"] if student else session.get("student_id")
    gcash_number = request.form.get("gcash_number")
    gcash_owner = request.form.get("gcash_owner")
    reference_number = request.form.get("reference_number")
    amount = request.form.get("amount")
    proof = request.files.get("proof")

    if not all([reference_number, amount, proof]):
        flash("Please provide the deposit amount, GCash reference number, and payment receipt.", "error")
        return redirect(url_for("dashboard_student"))

    filename = f"{student_id or 'stu'}_{int(time.time())}_{secure_filename(proof.filename)}"
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    proof.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO topups (student_id, gcash_number, gcash_owner, reference_number, amount, proof_image, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, 'pending', NOW())
    """, (student_id, gcash_number, gcash_owner, reference_number, amount, filename))
    conn.commit()
    conn.close()

    flash("Top-up request submitted. Please wait for admin approval.", "success")
    return redirect(url_for("dashboard_student"))




# ---------------- Parent Top-Up ----------------
@app.route("/parent_topup/<int:student_id>", methods=["GET","POST"])
def parent_topup(student_id):
    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # Get student info
    cursor.execute("SELECT student_id, full_name FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()

    if not student:
        conn.close()
        flash("Student not found.", "error")
        return redirect(url_for("signup_student"))

    if request.method == "POST":
        amount = request.form["amount"]
        payment_mode = request.form["payment_mode"]
        reference_number = request.form["reference_number"]

        # Insert into topups table with pending status
        cursor.execute("""
            INSERT INTO topups (student_id, amount, payment_mode, reference_number, status, created_at)
            VALUES (%s, %s, %s, %s, 'pending', NOW())
        """, (student_id, amount, payment_mode, reference_number))
        conn.commit()
        conn.close()

        flash("Top-up request submitted successfully! Awaiting admin approval.", "success")
        return redirect(url_for("parent_topup", student_id=student_id))

    conn.close()
    return render_template("parent_topup.html", student=student)


# ---------------- Generate QR (unique each time) ----------------
@app.route("/generate_qr")
def generate_qr():
    student = _get_logged_in_student()
    student_id = student["student_id"] if student else session.get("student_id")

    if not student_id:
        # Generate a placeholder error QR instead of returning HTML redirect which breaks <img>
        qr_img = qrcode.make("PLEASE-LOGIN")
        img_io = io.BytesIO()
        qr_img.save(img_io, 'PNG')
        img_io.seek(0)
        resp = send_file(img_io, mimetype='image/png')
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return resp

    # Add timestamp + unique nonce to make QR single-use and overwrite any previously active token
    now_ts = int(time.time())
    token_nonce = uuid.uuid4().hex[:8]
    token = f"{now_ts}-{token_nonce}"
    expires_at = now_ts + 35  # 30s student rotation cycle + 5s network grace
    unique_data = f"{student_id}-{token}"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE students SET dynamic_qr_token=%s, dynamic_qr_expires_at=%s WHERE student_id=%s",
        (token, expires_at, student_id),
    )
    conn.commit()
    conn.close()

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=14,
        border=2,
    )
    qr.add_data(unique_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#1e1b4b", back_color="#ffffff")
    img_io = io.BytesIO()
    qr_img.save(img_io, 'PNG')
    img_io.seek(0)

    response = send_file(img_io, mimetype='image/png')
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response

def generate_staff_qr(staff_id):
    qr_img = qrcode.make(staff_id)
    qr_path = f"static/staff_qrcodes/{staff_id}.png"
    os.makedirs("static/staff_qrcodes", exist_ok=True)
    qr_img.save(qr_path)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE staff SET staff_qr=%s WHERE staff_id=%s", (qr_path, staff_id))
    conn.commit()
    conn.close()
# ---------------- Phase 1: Trending Canteen Recommendations & Staff Analytics Helpers ----------------
def _get_trending_canteen_recommendations(cursor):
    try:
        cursor.execute("SELECT product_id, name, category, price, COALESCE(stock, 0) AS stock, icon FROM canteen_products")
        products = cursor.fetchall() or []
    except Exception:
        products = []

    prod_map = {}
    for p in products:
        key = str(p.get("name") or "").strip().lower()
        if key:
            prod_map[key] = p

    try:
        cursor.execute("""
            SELECT transaction_id, remarks, amount, created_at
            FROM transactions
            WHERE status = 'completed' AND LOWER(COALESCE(type, 'purchase')) != 'topup'
            ORDER BY created_at DESC
        """)
        txns = cursor.fetchall() or []
    except Exception:
        txns = []

    today_date = today_pst()
    latest_tx_date = today_date
    for t in txns:
        dt = t.get("created_at")
        if hasattr(dt, "date"):
            latest_tx_date = dt.date()
            break
        elif dt:
            try:
                latest_tx_date = datetime.datetime.strptime(str(dt)[:10], "%Y-%m-%d").date()
                break
            except Exception:
                pass

    week_cutoff = latest_tx_date - datetime.timedelta(days=7)

    stats_today = {}
    stats_week = {}
    stats_all = {}

    def add_stat(bucket, name_raw, qty, est_rev):
        k = name_raw.strip().lower()
        matched_p = prod_map.get(k)
        if not matched_p:
            for pk, pv in prod_map.items():
                if pk in k or k in pk:
                    matched_p = pv
                    break
        display_name = matched_p["name"] if matched_p else name_raw.strip().title()
        canon_key = display_name.lower()
        unit_price = float(matched_p["price"]) if matched_p and matched_p.get("price") else 0.0
        stock_val = int(matched_p["stock"]) if matched_p and matched_p.get("stock") is not None else None
        cat_val = matched_p.get("category") if matched_p else "Canteen Item"
        icon_val = matched_p.get("icon") if matched_p and matched_p.get("icon") else "🍽️"

        if canon_key not in bucket:
            bucket[canon_key] = {
                "name": display_name,
                "qty": 0,
                "orders": 0,
                "revenue": 0.0,
                "stock": stock_val,
                "category": cat_val,
                "icon": icon_val
            }
        bucket[canon_key]["qty"] += qty
        bucket[canon_key]["orders"] += 1
        bucket[canon_key]["revenue"] += (qty * unit_price) if unit_price > 0 else est_rev

    for t in txns:
        raw_rem = str(t.get("remarks") or "").strip()
        if not raw_rem or raw_rem.lower() in ("none", "canteen purchase", "canteen pos purchase", "quick pos sale"):
            continue
        clean_rem = re.sub(r"\s*\((?:GCash\s+)?Ref:[^)]*\)", "", raw_rem, flags=re.IGNORECASE).strip()
        if not clean_rem:
            continue

        dt = t.get("created_at")
        if hasattr(dt, "date"):
            tx_date = dt.date()
        else:
            try:
                tx_date = datetime.datetime.strptime(str(dt)[:10], "%Y-%m-%d").date()
            except Exception:
                tx_date = today_date

        tx_amt = float(t.get("amount") or 0)
        parts = [p.strip() for p in clean_rem.split(",") if p.strip()]
        parsed_items = []
        for part in parts:
            m = re.match(r"^(\d+)\s*[×xX*]\s*(.+)$", part)
            if m:
                parsed_items.append((int(m.group(1)), m.group(2).strip()))
            elif part.lower() in prod_map:
                parsed_items.append((1, part))

        if not parsed_items:
            continue

        total_units = sum(q for q, _ in parsed_items) or 1
        for qty, iname in parsed_items:
            share_rev = tx_amt * (qty / total_units)
            add_stat(stats_all, iname, qty, share_rev)
            if tx_date == today_date:
                add_stat(stats_today, iname, qty, share_rev)
            if tx_date >= week_cutoff:
                add_stat(stats_week, iname, qty, share_rev)

    has_today = len(stats_today) > 0
    active_bucket = stats_today if has_today else (stats_week if len(stats_week) > 0 else stats_all)
    window_label = "Today's Live Best-Sellers" if has_today else f"Trending Best-Sellers (as of {latest_tx_date.strftime('%b %d')})"

    ranked = sorted(active_bucket.values(), key=lambda x: (x["qty"], x["revenue"]), reverse=True)
    total_qty_sold = sum(x["qty"] for x in ranked) or 1
    for idx, item in enumerate(ranked):
        item["rank"] = idx + 1
        item["share_pct"] = round((item["qty"] / total_qty_sold) * 100, 1)
        item["revenue"] = round(item["revenue"], 2)

    top_seller = ranked[0] if ranked else {
        "name": "Tapsilog", "qty": 0, "orders": 0, "revenue": 0.0, "stock": 50, "category": "Main", "icon": "🍳", "rank": 1, "share_pct": 0
    }

    low_stock_alerts = []
    for p in products:
        st = int(p.get("stock") or 0)
        if st <= 10:
            pname = p.get("name") or "Item"
            sold_info = active_bucket.get(pname.strip().lower(), {})
            low_stock_alerts.append({
                "name": pname,
                "stock": st,
                "qty_sold": sold_info.get("qty", 0),
                "severity": "critical" if st == 0 else ("warning" if st <= 5 else "notice")
            })
    low_stock_alerts.sort(key=lambda x: (x["stock"], -x["qty_sold"]))

    recommendations = []
    if ranked:
        t1 = ranked[0]
        recommendations.append({
            "type": "best_seller",
            "badge": "🏆 #1 Best Seller",
            "item": t1["name"],
            "text": f"{t1['name']} leads with {t1['qty']} units sold ({t1['share_pct']}% of volume). Keep front-counter stock ready!"
        })
    if len(ranked) > 1:
        t2 = ranked[1]
        recommendations.append({
            "type": "trending",
            "badge": "📈 #2 High Demand",
            "item": t2["name"],
            "text": f"{t2['name']} is trending #2 ({t2['qty']} units sold). Great candidate for meal combo pairing."
        })
    if low_stock_alerts:
        lsa = low_stock_alerts[0]
        if lsa["stock"] == 0:
            recommendations.append({
                "type": "restock",
                "badge": "🚨 Out of Stock",
                "item": lsa["name"],
                "text": f"{lsa['name']} has 0 stock left! Immediate restock recommended."
            })
        else:
            recommendations.append({
                "type": "restock",
                "badge": "⚠️ Low Stock Alert",
                "item": lsa["name"],
                "text": f"{lsa['name']} only has {lsa['stock']} units left. Restock before peak break hours."
            })

    return {
        "success": True,
        "window_label": window_label,
        "has_today_sales": has_today,
        "top_seller": top_seller,
        "top_items": ranked[:5],
        "low_stock_alerts": low_stock_alerts[:4],
        "recommendations": recommendations
    }


def _get_staff_sales_analytics(cursor, requested_tf="daily"):
    requested_tf = str(requested_tf or "daily").strip().lower()
    if requested_tf not in ("daily", "weekly", "monthly"):
        requested_tf = "daily"

    cursor.execute("""
        SELECT t.transaction_id, t.created_at, t.amount, t.payment_mode, t.previous_balance, t.new_balance,
               t.remarks, t.student_id, t.type, t.status,
               s.full_name AS student_name, t.customer_name,
               COALESCE(s.full_name, t.customer_name, 'Walk-in Customer') AS display_name,
               s.school_id, s.email AS student_email
        FROM transactions t
        LEFT JOIN students s ON t.student_id = s.student_id
        WHERE t.status = 'completed' AND LOWER(COALESCE(t.type, 'purchase')) != 'topup'
        ORDER BY t.created_at DESC
    """)
    all_rows = cursor.fetchall() or []

    today_date = today_pst()
    latest_active_date = today_date
    for r in all_rows:
        dt = r.get("created_at")
        if hasattr(dt, "date"):
            latest_active_date = dt.date()
            break
        elif dt:
            try:
                latest_active_date = datetime.datetime.strptime(str(dt)[:10], "%Y-%m-%d").date()
                break
            except Exception:
                pass

    processed_rows = []
    for r in all_rows:
        raw_dt = r.get("created_at")
        if hasattr(raw_dt, "strftime"):
            tx_date = raw_dt.date()
            tx_hour = raw_dt.hour
            time_str = raw_dt.strftime("%I:%M %p")
            dt_str = raw_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            dt_str = str(raw_dt or "")
            try:
                parsed_dt = datetime.datetime.strptime(dt_str[:19], "%Y-%m-%d %H:%M:%S")
                tx_date = parsed_dt.date()
                tx_hour = parsed_dt.hour
                time_str = parsed_dt.strftime("%I:%M %p")
            except Exception:
                tx_date = today_date
                tx_hour = 12
                time_str = dt_str

        pm = str(r.get("payment_mode") or "").strip().lower()
        prev_b = r.get("previous_balance")
        new_b = r.get("new_balance")
        has_wallet_deduction = (
            r.get("student_id") is not None
            and prev_b is not None
            and new_b is not None
            and float(prev_b) > float(new_b)
        )
        if pm in ("gcash", "ewallet", "e-wallet"):
            rmode = "gcash"
        elif pm in ("wallet", "cashless") or has_wallet_deduction:
            rmode = "wallet"
        else:
            rmode = "cash"

        buyer_name = r.get("student_name") or r.get("customer_name") or r.get("display_name") or "Walk-in Customer"
        processed_rows.append({
            "transaction_id": r["transaction_id"],
            "tx_date": tx_date,
            "tx_hour": tx_hour,
            "time": time_str,
            "created_at": dt_str,
            "amount": float(r["amount"] or 0),
            "payment_mode": pm,
            "resolved_mode": rmode,
            "previous_balance": float(r["previous_balance"]) if r.get("previous_balance") is not None else None,
            "new_balance": float(r["new_balance"]) if r.get("new_balance") is not None else None,
            "remarks": r.get("remarks") or "Canteen POS Purchase",
            "customer_name": buyer_name,
            "student_name": r.get("student_name") or "",
            "school_id": r.get("school_id") or "",
            "student_id": r.get("student_id"),
            "student_email": r.get("student_email") or ""
        })

    recent_7_cal = [x for x in processed_rows if x["tx_date"] >= (today_date - datetime.timedelta(days=6))]
    week_anchor = today_date if len(recent_7_cal) > 0 else latest_active_date
    week_start = week_anchor - datetime.timedelta(days=6)

    recent_30_cal = [x for x in processed_rows if x["tx_date"] >= (today_date - datetime.timedelta(days=29))]
    month_anchor = today_date if len(recent_30_cal) > 0 else latest_active_date
    month_start = month_anchor - datetime.timedelta(days=29)

    daily_rows = [x for x in processed_rows if x["tx_date"] == today_date]
    weekly_rows = [x for x in processed_rows if week_start <= x["tx_date"] <= week_anchor]
    monthly_rows = [x for x in processed_rows if month_start <= x["tx_date"] <= month_anchor]

    def calc_kpis(subset):
        tot = 0.0
        w_tot, w_cnt = 0.0, 0
        c_tot, c_cnt = 0.0, 0
        g_tot, g_cnt = 0.0, 0
        for x in subset:
            amt = x["amount"]
            tot += amt
            rm = x["resolved_mode"]
            if rm == "wallet":
                w_tot += amt
                w_cnt += 1
            elif rm == "gcash":
                g_tot += amt
                g_cnt += 1
            else:
                c_tot += amt
                c_cnt += 1
        return {
            "total_sales": round(tot, 2),
            "total_orders": len(subset),
            "wallet_sales": round(w_tot, 2),
            "wallet_count": w_cnt,
            "cash_sales": round(c_tot, 2),
            "cash_count": c_cnt,
            "gcash_sales": round(g_tot, 2),
            "gcash_count": g_cnt
        }

    kpis_by_tf = {
        "daily": calc_kpis(daily_rows),
        "weekly": calc_kpis(weekly_rows),
        "monthly": calc_kpis(monthly_rows)
    }

    daily_chart_source = daily_rows if len(daily_rows) > 0 else [x for x in processed_rows if x["tx_date"] == latest_active_date]
    daily_chart_date = today_date if len(daily_rows) > 0 else latest_active_date
    chart_hours = [x["tx_hour"] for x in daily_chart_source if isinstance(x.get("tx_hour"), int) and 0 <= x["tx_hour"] <= 23]
    min_hour = min([7] + chart_hours)
    max_hour = max([18] + chart_hours)
    hour_slots = list(range(min_hour, max_hour + 1))
    daily_labels = [datetime.time(h, 0).strftime("%I %p").lstrip("0") for h in hour_slots]
    d_wallet, d_cash, d_gcash, d_total, d_orders = [], [], [], [], []
    for h in hour_slots:
        h_rows = [x for x in daily_chart_source if x["tx_hour"] == h]
        w = round(sum(x["amount"] for x in h_rows if x["resolved_mode"] == "wallet"), 2)
        c = round(sum(x["amount"] for x in h_rows if x["resolved_mode"] == "cash"), 2)
        g = round(sum(x["amount"] for x in h_rows if x["resolved_mode"] == "gcash"), 2)
        d_wallet.append(w)
        d_cash.append(c)
        d_gcash.append(g)
        d_total.append(round(w + c + g, 2))
        d_orders.append(len(h_rows))

    daily_chart = {
        "title": "Daily Hourly Sales Velocity",
        "subtitle": f"Hourly breakdown for {daily_chart_date.strftime('%b %d, %Y')}",
        "labels": daily_labels,
        "wallet": d_wallet,
        "cash": d_cash,
        "gcash": d_gcash,
        "totals": d_total,
        "orders": d_orders
    }

    w_dates = [week_start + datetime.timedelta(days=i) for i in range(7)]
    w_labels = [d.strftime("%a (%b %d)") for d in w_dates]
    w_wallet, w_cash, w_gcash, w_total, w_orders = [], [], [], [], []
    for d in w_dates:
        day_rows = [x for x in weekly_rows if x["tx_date"] == d]
        w = round(sum(x["amount"] for x in day_rows if x["resolved_mode"] == "wallet"), 2)
        c = round(sum(x["amount"] for x in day_rows if x["resolved_mode"] == "cash"), 2)
        g = round(sum(x["amount"] for x in day_rows if x["resolved_mode"] == "gcash"), 2)
        w_wallet.append(w)
        w_cash.append(c)
        w_gcash.append(g)
        w_total.append(round(w + c + g, 2))
        w_orders.append(len(day_rows))

    weekly_chart = {
        "title": "Weekly Sales Performance (7-Day Breakdown)",
        "subtitle": f"{week_start.strftime('%b %d')} - {week_anchor.strftime('%b %d, %Y')}",
        "labels": w_labels,
        "wallet": w_wallet,
        "cash": w_cash,
        "gcash": w_gcash,
        "totals": w_total,
        "orders": w_orders
    }

    m_labels, m_wallet, m_cash, m_gcash, m_total, m_orders = [], [], [], [], [], []
    for wk_idx in range(4):
        b_start = month_start + datetime.timedelta(days=wk_idx * 7)
        b_end = month_anchor if wk_idx == 3 else (b_start + datetime.timedelta(days=6))
        lbl = f"Wk {wk_idx + 1} ({b_start.strftime('%b %d')}-{b_end.strftime('%d')})"
        m_labels.append(lbl)
        b_rows = [x for x in monthly_rows if b_start <= x["tx_date"] <= b_end]
        w = round(sum(x["amount"] for x in b_rows if x["resolved_mode"] == "wallet"), 2)
        c = round(sum(x["amount"] for x in b_rows if x["resolved_mode"] == "cash"), 2)
        g = round(sum(x["amount"] for x in b_rows if x["resolved_mode"] == "gcash"), 2)
        m_wallet.append(w)
        m_cash.append(c)
        m_gcash.append(g)
        m_total.append(round(w + c + g, 2))
        m_orders.append(len(b_rows))

    monthly_chart = {
        "title": "Monthly Sales Performance (4-Week Trend)",
        "subtitle": f"{month_start.strftime('%b %d')} - {month_anchor.strftime('%b %d, %Y')}",
        "labels": m_labels,
        "wallet": m_wallet,
        "cash": m_cash,
        "gcash": m_gcash,
        "totals": m_total,
        "orders": m_orders
    }

    charts_by_tf = {
        "daily": daily_chart,
        "weekly": weekly_chart,
        "monthly": monthly_chart
    }

    subset_map = {
        "daily": daily_rows,
        "weekly": weekly_rows,
        "monthly": monthly_rows
    }
    selected_orders = []
    for x in subset_map[requested_tf][:150]:
        copy_x = dict(x)
        copy_x.pop("tx_date", None)
        copy_x.pop("tx_hour", None)
        selected_orders.append(copy_x)

    return {
        "success": True,
        "timeframe": requested_tf,
        "kpis": kpis_by_tf[requested_tf],
        "all_kpis": kpis_by_tf,
        "chart": charts_by_tf[requested_tf],
        "daily_chart": daily_chart,
        "weekly_chart": weekly_chart,
        "monthly_chart": monthly_chart,
        "orders": selected_orders
    }

# ---------------- Admin Dashboard ----------------

@app.route('/admin/dashboard')
@app.route('/dashboard/admin')
def dashboard_admin():
    admin = _get_logged_in_admin()
    if not admin:
        return redirect(url_for("signin_admin"))

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # Totals
    cursor.execute("SELECT SUM(amount) AS total FROM transactions WHERE type='topup' AND status='completed'")
    total_topups = cursor.fetchone()["total"] or 0

    cursor.execute("SELECT SUM(amount) AS total FROM transactions WHERE status='completed'")
    total_received = cursor.fetchone()["total"] or 0

    cursor.execute("SELECT SUM(amount) AS total FROM transactions WHERE type='purchase' AND status='completed'")
    total_sales = cursor.fetchone()["total"] or 0

    # Chart data: Top-Ups vs Purchases
    cursor.execute("""
        SELECT DATE(created_at) AS date,
               COALESCE(SUM(CASE WHEN type='topup' THEN amount ELSE 0 END), 0) AS topups,
               COALESCE(SUM(CASE WHEN type='purchase' THEN amount ELSE 0 END), 0) AS purchases
        FROM transactions
        WHERE status='completed'
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    rows = cursor.fetchall() or []
    txn_dates = [row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]) for row in rows]
    txn_topups = [float(row["topups"] or 0) for row in rows]
    txn_purchases = [float(row["purchases"] or 0) for row in rows]

    # Registered students chart (unified across timeline dates + cumulative total)
    cursor.execute("""
        SELECT DATE(created_at) AS date, COUNT(*) AS count
        FROM students
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    reg_rows = cursor.fetchall() or []
    raw_reg_map = {
        (r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else str(r["date"])): int(r["count"] or 0)
        for r in reg_rows
    }
    all_reg_dates = sorted(set(txn_dates) | set(raw_reg_map.keys()))
    reg_dates = all_reg_dates
    reg_counts = [raw_reg_map.get(d, 0) for d in reg_dates]
    reg_cumulative = []
    _running_reg = 0
    for c_val in reg_counts:
        _running_reg += c_val
        reg_cumulative.append(_running_reg)

    # Active vs inactive students
    cursor.execute("SELECT COUNT(*) AS active_count FROM students WHERE LOWER(COALESCE(status, 'active')) = 'active'")
    active_count = int((cursor.fetchone() or {}).get("active_count") or 0)
    cursor.execute("SELECT COUNT(*) AS inactive_count FROM students WHERE LOWER(COALESCE(status, 'active')) != 'active'")
    inactive_count = int((cursor.fetchone() or {}).get("inactive_count") or 0)

    # Payment distribution totals (Canteen Purchases only: Campus Wallet vs Cash vs GCash)
    cursor.execute("""
        SELECT DATE(created_at) AS date,
               COALESCE(SUM(CASE WHEN LOWER(COALESCE(payment_mode, '')) IN ('wallet', 'cashless')
                    OR (student_id IS NOT NULL AND previous_balance IS NOT NULL AND new_balance IS NOT NULL AND previous_balance > new_balance AND LOWER(COALESCE(payment_mode, '')) NOT IN ('cash', 'gcash', 'ewallet', 'e-wallet'))
                    THEN amount ELSE 0 END), 0) AS cashless,
               COALESCE(SUM(CASE WHEN LOWER(COALESCE(payment_mode, '')) = 'cash'
                    AND NOT (student_id IS NOT NULL AND previous_balance IS NOT NULL AND new_balance IS NOT NULL AND previous_balance > new_balance)
                    THEN amount ELSE 0 END), 0) AS manual,
               COALESCE(SUM(CASE WHEN LOWER(COALESCE(payment_mode, '')) IN ('gcash', 'ewallet', 'e-wallet')
                    THEN amount ELSE 0 END), 0) AS others
        FROM transactions
        WHERE status='completed' AND type != 'topup'
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    dist_rows = cursor.fetchall() or []
    totals_dates = [r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else str(r["date"]) for r in dist_rows]
    manual_totals = [float(r["manual"] or 0) for r in dist_rows]
    cashless_totals = [float(r["cashless"] or 0) for r in dist_rows]
    other_totals = [float(r["others"] or 0) for r in dist_rows]

    # Registered students list
    cursor.execute("SELECT student_id, school_id, full_name, grade_level, strand, balance, status, created_at FROM students ORDER BY created_at DESC")
    registered_students = cursor.fetchall()

    # Pending top-ups
    cursor.execute("SELECT * FROM topups WHERE status='pending' ORDER BY created_at DESC")
    pending_topups = cursor.fetchall()

    # Transactions list (Complete master financial audit log)
    cursor.execute("""
        SELECT t.transaction_id, t.created_at, t.type, t.amount, t.payment_mode,
               t.previous_balance, t.new_balance,
               COALESCE(s.full_name, a.full_name, 'Canteen Cashier') AS staff_name,
               COALESCE(st.full_name, t.customer_name, 'Walk-in Customer') AS customer_name,
               COALESCE(st.school_id, '') AS student_name,
               t.status, t.remarks, t.student_id
        FROM transactions t
        LEFT JOIN staff s ON t.staff_id = s.staff_id
        LEFT JOIN admins a ON t.admin_id = a.admin_id
        LEFT JOIN students st ON t.student_id = st.student_id
        ORDER BY t.created_at DESC
    """)
    transactions = cursor.fetchall()

    # Walk-In & Counter Sales (Cash, GCash, and Walk-in POS purchases)
    cursor.execute("""
        SELECT t.transaction_id, t.created_at, t.amount, t.payment_mode,
               t.status, t.remarks,
               COALESCE(s.full_name, a.full_name, 'Canteen Cashier') AS staff_name,
               COALESCE(st.full_name, t.customer_name, 'Walk-in Customer') AS customer_name,
               COALESCE(st.school_id, '') AS school_id,
               t.student_id
        FROM transactions t
        LEFT JOIN staff s ON t.staff_id = s.staff_id
        LEFT JOIN admins a ON t.admin_id = a.admin_id
        LEFT JOIN students st ON t.student_id = st.student_id
        WHERE t.type != 'topup'
          AND (t.student_id IS NULL OR LOWER(COALESCE(t.payment_mode, '')) IN ('cash', 'gcash', 'ewallet', 'e-wallet'))
        ORDER BY t.created_at DESC
    """)
    unregistered_transactions = cursor.fetchall() or []


    cursor.execute("""
        SELECT admin_id, full_name, email, contact_number,
               COALESCE(status, 'approved') AS status,
               COALESCE(is_main_admin, 0) AS is_main_admin,
               created_at
        FROM admins
        ORDER BY CASE WHEN LOWER(COALESCE(status, 'approved')) = 'pending' THEN 0 ELSE 1 END, admin_id DESC
    """)
    all_admins = cursor.fetchall() or []

    cursor.execute("""
        SELECT staff_id, full_name, email, contact_number,
               COALESCE(status, 'approved') AS status,
               created_at
        FROM staff
        ORDER BY CASE WHEN LOWER(COALESCE(status, 'approved')) = 'pending' THEN 0 ELSE 1 END, staff_id DESC
    """)
    all_staff = cursor.fetchall() or []

    pending_account_approvals = [
        {
            "account_type": "admin",
            "account_id": a["admin_id"],
            "full_name": a.get("full_name") or "Admin Applicant",
            "email": a.get("email") or "",
            "contact_number": a.get("contact_number") or "---",
            "status": a.get("status") or "pending",
            "created_at": a.get("created_at"),
        }
        for a in all_admins if str(a.get("status") or "").lower() == "pending"
    ] + [
        {
            "account_type": "staff",
            "account_id": s["staff_id"],
            "full_name": s.get("full_name") or "Staff Applicant",
            "email": s.get("email") or "",
            "contact_number": s.get("contact_number") or "---",
            "status": s.get("status") or "pending",
            "created_at": s.get("created_at"),
        }
        for s in all_staff if str(s.get("status") or "").lower() == "pending"
    ]

    return render_template(
        "dashboard_admin.html",
        admin=admin,  # ✅ pass the single admin record
        total_topups=total_topups,
        total_received=total_received,
        total_sales=total_sales,
        txn_dates=txn_dates,
        txn_topups=txn_topups,
        txn_purchases=txn_purchases,
        reg_dates=reg_dates,
        reg_counts=reg_counts,
        reg_cumulative=reg_cumulative,
        active_count=active_count,
        inactive_count=inactive_count,
        totals_dates=totals_dates,
        manual_totals=manual_totals,
        cashless_totals=cashless_totals,
        other_totals=other_totals,
        registered_students=registered_students,
        pending_topups=pending_topups,
        transactions=transactions,
        unregistered_transactions=unregistered_transactions,
        all_admins=all_admins,
        all_staff=all_staff,
        pending_account_approvals=pending_account_approvals,
        trending_recommendations=_get_trending_canteen_recommendations(cursor)
    )


@app.route("/admin/account_approval", methods=["POST"])
def admin_account_approval():
    admin = _get_logged_in_admin()
    if not admin:
        return jsonify({"success": False, "message": "Unauthorized. Please sign in as Admin."}), 403

    if int(admin.get("is_main_admin") or 0) != 1:
        return jsonify({
            "success": False,
            "message": "Access Denied: Only the Main Administrator can approve, reject, or modify Admin and Staff accounts."
        }), 403

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    account_type = str(data.get("account_type") or "").strip().lower()
    action = str(data.get("action") or "").strip().lower()
    try:
        account_id = int(data.get("account_id") or 0)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid account ID."}), 400

    if account_type not in ("admin", "staff") or action not in ("approve", "reject", "promote_main", "demote_regular") or account_id <= 0:
        return jsonify({"success": False, "message": "Invalid approval parameters."}), 400

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    if account_type == "admin":
        if account_id == int(admin["admin_id"]) and action in ("reject", "demote_regular"):
            conn.close()
            return jsonify({"success": False, "message": "You cannot reject or demote your own Main Admin account."}), 400

        cursor.execute("SELECT admin_id, full_name, email, status, is_main_admin FROM admins WHERE admin_id=%s", (account_id,))
        target = cursor.fetchone()
        if not target:
            conn.close()
            return jsonify({"success": False, "message": "Admin account not found."}), 404

        if action == "approve":
            cursor.execute("UPDATE admins SET status='approved' WHERE admin_id=%s", (account_id,))
            new_status, new_main = "approved", int(target.get("is_main_admin") or 0)
            msg = f"Admin account for {target['full_name']} has been approved!"
        elif action == "reject":
            cursor.execute("UPDATE admins SET status='rejected', is_main_admin=0 WHERE admin_id=%s", (account_id,))
            new_status, new_main = "rejected", 0
            msg = f"Admin account for {target['full_name']} has been rejected."
        elif action == "promote_main":
            cursor.execute("UPDATE admins SET status='approved', is_main_admin=1 WHERE admin_id=%s", (account_id,))
            new_status, new_main = "approved", 1
            msg = f"{target['full_name']} has been promoted to Main Administrator."
        else:  # demote_regular
            cursor.execute("UPDATE admins SET is_main_admin=0 WHERE admin_id=%s", (account_id,))
            new_status, new_main = str(target.get("status") or "approved"), 0
            msg = f"{target['full_name']} is now a Standard Administrator."

        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "message": msg,
            "account_type": "admin",
            "account_id": account_id,
            "new_status": new_status,
            "is_main_admin": new_main
        })

    else:  # staff
        cursor.execute("SELECT staff_id, full_name, email, status FROM staff WHERE staff_id=%s", (account_id,))
        target = cursor.fetchone()
        if not target:
            conn.close()
            return jsonify({"success": False, "message": "Staff account not found."}), 404

        if action == "approve":
            cursor.execute("UPDATE staff SET status='approved' WHERE staff_id=%s", (account_id,))
            new_status = "approved"
            msg = f"Canteen Staff account for {target['full_name']} has been approved!"
        elif action == "reject":
            cursor.execute("UPDATE staff SET status='rejected' WHERE staff_id=%s", (account_id,))
            new_status = "rejected"
            msg = f"Canteen Staff account for {target['full_name']} has been rejected."
        else:
            conn.close()
            return jsonify({"success": False, "message": "Unsupported action for staff account."}), 400

        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "message": msg,
            "account_type": "staff",
            "account_id": account_id,
            "new_status": new_status,
            "is_main_admin": 0
        })


@app.route("/admin/export/<export_type>")
def admin_export_csv(export_type):
    admin = _get_logged_in_admin()
    if not admin:
        return jsonify({"success": False, "message": "Unauthorized. Admin privileges required."}), 403

    export_key = (export_type or "").strip().lower()
    start_date = (request.args.get("start_date") or "").strip()
    end_date = (request.args.get("end_date") or "").strip()

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM for Excel compatibility
    writer = csv.writer(output)
    today_str = now_pst().strftime("%Y-%m-%d")

    if export_key == "transactions":
        sql = """
            SELECT t.transaction_id, t.created_at, t.type, t.amount, t.payment_mode,
                   t.previous_balance, t.new_balance,
                   COALESCE(s.full_name, a.full_name, 'Admin / Cashier') AS staff_name,
                   COALESCE(st.full_name, t.customer_name, 'Walk-in Customer') AS customer_name,
                   COALESCE(st.school_id, '') AS school_id,
                   t.status, t.remarks
            FROM transactions t
            LEFT JOIN staff s ON t.staff_id = s.staff_id
            LEFT JOIN admins a ON t.admin_id = a.admin_id
            LEFT JOIN students st ON t.student_id = st.student_id
            WHERE 1=1
        """
        params = []
        if start_date:
            sql += " AND DATE(t.created_at) >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND DATE(t.created_at) <= %s"
            params.append(end_date)
        sql += " ORDER BY t.created_at DESC"
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall() or []

        writer.writerow([
            "Transaction ID", "Date & Time", "Student / Customer", "School ID",
            "Type", "Payment Method", "Amount (PHP)", "Previous Balance (PHP)",
            "New Balance (PHP)", "Status", "Handled By", "Remarks"
        ])
        topup_sum = 0.0
        purchase_sum = 0.0
        for r in rows:
            amt = float(r.get("amount") or 0)
            ttype = str(r.get("type") or "purchase").lower()
            rem = str(r.get("remarks") or "")
            status_label = "Reversed" if ("reversal" in rem.lower() or "reversed" in rem.lower() or amt < 0) else str(r.get("status") or "completed")
            if ttype == "topup":
                topup_sum += amt
            else:
                purchase_sum += amt
            writer.writerow([
                f"#{r['transaction_id']}",
                str(r.get("created_at") or ""),
                r.get("customer_name") or "Walk-in Customer",
                r.get("school_id") or "N/A",
                ttype.upper(),
                str(r.get("payment_mode") or "cash").upper(),
                f"{amt:.2f}",
                f"{float(r['previous_balance']):.2f}" if r.get("previous_balance") is not None else "N/A",
                f"{float(r['new_balance']):.2f}" if r.get("new_balance") is not None else "N/A",
                status_label,
                r.get("staff_name") or "Admin",
                rem or "---"
            ])
        writer.writerow([])
        writer.writerow(["--- TRANSACTION LEDGER SUMMARY ---"])
        writer.writerow(["Net Top-Ups (PHP):", f"PHP {topup_sum:.2f}"])
        writer.writerow(["Total Purchases (PHP):", f"PHP {purchase_sum:.2f}"])
        writer.writerow(["Total Records Exported:", len(rows)])
        filename = f"scuola_admin_transactions_{today_str}.csv"

    elif export_key in ("counter_sales", "unregistered"):
        sql = """
            SELECT t.transaction_id, t.created_at, t.amount, t.payment_mode,
                   t.status, t.remarks,
                   COALESCE(s.full_name, a.full_name, 'Canteen Cashier') AS staff_name,
                   COALESCE(st.full_name, t.customer_name, 'Walk-in Customer') AS customer_name,
                   COALESCE(st.school_id, '') AS school_id
            FROM transactions t
            LEFT JOIN staff s ON t.staff_id = s.staff_id
            LEFT JOIN admins a ON t.admin_id = a.admin_id
            LEFT JOIN students st ON t.student_id = st.student_id
            WHERE t.type != 'topup'
              AND (t.student_id IS NULL OR LOWER(COALESCE(t.payment_mode, '')) IN ('cash', 'gcash', 'ewallet', 'e-wallet'))
        """
        params = []
        if start_date:
            sql += " AND DATE(t.created_at) >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND DATE(t.created_at) <= %s"
            params.append(end_date)
        sql += " ORDER BY t.created_at DESC"
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall() or []

        writer.writerow([
            "Transaction ID", "Date & Time", "Customer / Student", "School ID",
            "Payment Tender", "Amount (PHP)", "Items / Remarks", "Status", "Cashier Staff"
        ])
        cash_sum = 0.0
        gcash_sum = 0.0
        for r in rows:
            amt = float(r.get("amount") or 0)
            pm = str(r.get("payment_mode") or "cash").lower()
            if pm in ("gcash", "ewallet", "e-wallet"):
                gcash_sum += amt
                pm_label = "GCash"
            else:
                cash_sum += amt
                pm_label = "Cash"
            writer.writerow([
                f"#{r['transaction_id']}",
                str(r.get("created_at") or ""),
                r.get("customer_name") or "Walk-in Customer",
                r.get("school_id") or "Direct / Walk-In",
                pm_label,
                f"{amt:.2f}",
                r.get("remarks") or "---",
                r.get("status") or "completed",
                r.get("staff_name") or "Canteen Cashier"
            ])
        writer.writerow([])
        writer.writerow(["--- COUNTER & WALK-IN SALES SUMMARY ---"])
        writer.writerow(["Physical Cash Sales (PHP):", f"PHP {cash_sum:.2f}"])
        writer.writerow(["GCash Counter Sales (PHP):", f"PHP {gcash_sum:.2f}"])
        writer.writerow(["Total Counter Sales (PHP):", f"PHP {(cash_sum + gcash_sum):.2f}"])
        writer.writerow(["Total Orders Exported:", len(rows)])
        filename = f"scuola_admin_counter_sales_{today_str}.csv"

    elif export_key == "students":
        cursor.execute("""
            SELECT student_id, school_id, full_name, grade_level, strand, balance, status, created_at
            FROM students
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall() or []
        writer.writerow([
            "Internal ID", "School ID", "Full Name", "Grade Level", "Strand",
            "Available Balance (PHP)", "Account Status", "Registered At"
        ])
        total_bal = 0.0
        for s in rows:
            bal = float(s.get("balance") or 0)
            total_bal += bal
            writer.writerow([
                f"#{s['student_id']}",
                s.get("school_id") or "",
                s.get("full_name") or "",
                s.get("grade_level") or "---",
                s.get("strand") or "---",
                f"{bal:.2f}",
                s.get("status") or "active",
                str(s.get("created_at") or "")
            ])
        writer.writerow([])
        writer.writerow(["--- REGISTERED STUDENTS SUMMARY ---"])
        writer.writerow(["Total Enrolled Students:", len(rows)])
        writer.writerow(["Combined Wallet Float (PHP):", f"PHP {total_bal:.2f}"])
        filename = f"scuola_admin_students_{today_str}.csv"

    else:
        conn.close()
        return jsonify({"success": False, "message": "Invalid export type."}), 400

    conn.close()
    csv_data = output.getvalue()
    output.close()
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )



# Manual Top-Up
@app.route('/manual_topup', methods=['POST'])
def manual_topup():
    admin = _get_logged_in_admin()
    if not admin:
        return jsonify(success=False, message="Unauthorized"), 403

    data = request.get_json() or {}
    student_id = data.get("student_id")   # school_id from frontend
    try:
        amount = Decimal(str(data.get("amount", 0)))
    except Exception:
        return jsonify(success=False, message="Invalid top-up amount."), 400

    if not student_id or amount <= 0:
        return jsonify(success=False, message="Please provide a valid student and positive amount."), 400

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT student_id, balance FROM students WHERE school_id=%s", (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify(success=False, message="Student not found."), 404

    prev_bal = Decimal(str(student["balance"] if student.get("balance") is not None else "0.00"))
    new_bal = prev_bal + amount

    cursor.execute("UPDATE students SET balance = %s WHERE student_id=%s", (new_bal, student["student_id"]))

    cursor.execute("""
        INSERT INTO transactions (student_id, type, amount, previous_balance, new_balance, payment_mode, status, remarks, created_at, admin_id)
        VALUES (%s, 'topup', %s, %s, %s, 'cash', 'completed', 'Manual top-up', NOW(), %s)
    """, (student["student_id"], amount, prev_bal, new_bal, admin.get("admin_id")))

    conn.commit()
    conn.close()
    return jsonify(success=True, message="Manual top-up successful", new_balance=float(new_bal))




# ---------------- Search Students ----------------
@app.route('/admin/search_students')
def search_students():
    admin = _get_logged_in_admin()
    if not admin:
        flash("Unauthorized access. Admin privileges required.", "error")
        return redirect(url_for("signin_admin"))

    query = request.args.get("q", "")
    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT student_id, full_name, school_id, balance FROM students WHERE full_name LIKE %s", ("%" + query + "%",))
    results = cursor.fetchall()
    conn.close()
    return render_template('dashboard_admin.html', section='search', admin=admin, students=results)





@app.route("/admin/topup", methods=["POST"])
def admin_topup():
    admin = _get_logged_in_admin()
    if not admin:
        return jsonify({"success": False, "message": "Unauthorized access. Admin privileges required."}), 401

    data = request.get_json() or {}
    student_id = data.get("student_id")
    amount = float(data.get("amount") or 0)
    if not student_id or amount <= 0:
        return jsonify({"success": False, "message": "Invalid topup parameters."}), 400

    conn = get_connection()
    cursor = conn.cursor()

    # Insert into topups table as pending (for approval)
    cursor.execute("""
        INSERT INTO topups (student_id, method, amount, status)
        VALUES (%s, 'manual', %s, 'pending')
    """, (student_id, amount))
    conn.commit()

    # Get current balance for preview
    cursor.execute("SELECT balance FROM students WHERE student_id=%s", (student_id,))
    current_balance = cursor.fetchone()[0]

    new_balance = current_balance + amount

    conn.close()

    return jsonify({"success": True, "new_balance": new_balance})


# ---------------- Approve Top-Up ----------------
@app.route("/admin/approve_topup/<int:topup_id>", methods=["POST"])
@app.route("/approve_topup/<int:topup_id>", methods=["POST"])
def approve_topup(topup_id):
    admin = _get_logged_in_admin()
    if not admin:
        if request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify({"success": False, "message": "Unauthorized access."}), 403
        flash("Unauthorized access.", "error")
        return redirect(url_for("signin_admin"))

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # Get top-up info
    cursor.execute("""
        SELECT t.topup_id, t.student_id, t.amount, t.reference_number, s.full_name, s.parent_email, s.balance
        FROM topups t
        JOIN students s ON t.student_id = s.student_id
        WHERE t.topup_id=%s AND t.status='pending'
    """, (topup_id,))
    topup = cursor.fetchone()

    if topup:
        prev_balance = Decimal(str(topup.get("balance") or 0))
        topup_amount = Decimal(str(topup.get("amount") or 0))
        new_balance = prev_balance + topup_amount

        # Update student balance
        cursor.execute("UPDATE students SET balance = %s WHERE student_id=%s",
                       (new_balance, topup["student_id"]))
        # Mark top-up as completed
        cursor.execute("UPDATE topups SET status='completed' WHERE topup_id=%s", (topup_id,))

        # Record into transactions ledger so it reflects on student dashboard & PDF
        cursor.execute("""
            INSERT INTO transactions (student_id, admin_id, amount, previous_balance, new_balance,
                                      status, type, payment_mode, remarks, created_at)
            VALUES (%s, %s, %s, %s, %s, 'completed', 'topup', 'gcash', %s, NOW())
        """, (
            topup["student_id"],
            admin.get("admin_id"),
            topup_amount,
            prev_balance,
            new_balance,
            f"GCash Top-Up (Ref: {topup.get('reference_number') or 'N/A'})"
        ))
        conn.commit()
        conn.close()

        # 🔹 Notify parent
        try:
            send_email(
                to=topup["parent_email"],
                subject="Top-Up Approved",
                body=f"Dear Parent,\n\nYour top-up request of ₱{topup['amount']} for {topup['full_name']} has been approved and credited.\n\nRegards,\nScuola Dei Bambini De Sta. Terisita International Montessori School Inc."
            )
        except Exception as e:
            print("Email notification skipped or failed:", e)

        if request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify({"success": True, "message": "Top-up approved successfully."})
        flash("Top-up approved successfully.", "success")
    else:
        conn.close()
        if request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify({"success": False, "message": "Top-up not found or already processed."}), 404
        flash("Top-up not found or already processed.", "error")

    return redirect(url_for("admin_pending_topups"))


@app.route("/admin/reject_topup/<int:topup_id>", methods=["POST"])
@app.route("/reject_topup/<int:topup_id>", methods=["POST"])
def reject_topup(topup_id):
    admin = _get_logged_in_admin()
    if not admin:
        if request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify({"success": False, "message": "Unauthorized access."}), 403
        flash("Unauthorized access.", "error")
        return redirect(url_for("signin_admin"))

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # Get top-up info
    cursor.execute("""
        SELECT t.topup_id, t.amount, s.full_name, s.parent_email
        FROM topups t
        JOIN students s ON t.student_id = s.student_id
        WHERE t.topup_id=%s AND t.status='pending'
    """, (topup_id,))
    topup = cursor.fetchone()

    if topup:
        cursor.execute("UPDATE topups SET status='rejected' WHERE topup_id=%s", (topup_id,))
        conn.commit()
        conn.close()

        # 🔹 Notify parent
        try:
            send_email(
                to=topup["parent_email"],
                subject="Top-Up Rejected",
                body=f"Dear Parent,\n\nYour top-up request of ₱{topup['amount']} for {topup['full_name']} has been rejected by the admin. Please contact the school office for assistance.\n\nRegards,\nScuola Dei Bambini De Sta. Terisita International Montessori School Inc."
            )
        except Exception as e:
            print("Email notification skipped or failed:", e)

        if request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify({"success": True, "message": "Top-up rejected successfully."})
        flash("Top-up rejected.", "info")
    else:
        conn.close()
        if request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify({"success": False, "message": "Top-up not found or already processed."}), 404
        flash("Top-up not found or already processed.", "error")

    return redirect(url_for("admin_pending_topups"))



# ---------------- Reverse Top-Up ----------------
from decimal import Decimal

@app.route("/reverse_topup/<int:transaction_id>", methods=["POST"])
def reverse_topup(transaction_id):
    admin = _get_logged_in_admin()
    if not admin:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # 1. Get the original top-up transaction
    cursor.execute("""
        SELECT transaction_id, student_id, amount, new_balance, payment_mode, status, remarks
        FROM transactions
        WHERE transaction_id=%s AND type='topup' AND status='completed'
    """, (transaction_id,))
    original = cursor.fetchone()

    if not original:
        conn.close()
        return jsonify({"success": False, "message": "Top-up transaction not found."}), 404

    orig_remarks = str(original.get("remarks") or "").strip()
    amount = Decimal(str(original.get("amount") or "0.00"))

    # 2. Prevent reversing an already-reversed top-up or a negative reversal entry
    if amount <= Decimal("0.00") or "reversal" in orig_remarks.lower() or "reversed" in orig_remarks.lower():
        conn.close()
        return jsonify({"success": False, "message": "This top-up has already been reversed."}), 400

    student_id = original["student_id"]

    # 3. Always query the student's CURRENT LIVE balance from the students table
    cursor.execute("SELECT student_id, school_id, full_name, balance FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student account not found."}), 404

    current_balance = Decimal(str(student["balance"] if student.get("balance") is not None else "0.00"))

    # 4. Guard against insufficient balance (when student already spent the top-up funds)
    if current_balance < amount:
        conn.close()
        return jsonify({
            "success": False,
            "message": f"Insufficient balance to undo this top-up. {student.get('full_name') or 'Student'} only has ₱{current_balance:.2f} available, which is less than the ₱{amount:.2f} top-up amount."
        }), 400

    new_balance = current_balance - amount

    # 5. Mark the original transaction's remarks so it cannot be reversed a second time
    updated_orig_remarks = f"{orig_remarks} [Reversal Applied]" if orig_remarks else "Top-Up [Reversal Applied]"
    cursor.execute(
        "UPDATE transactions SET remarks=%s WHERE transaction_id=%s",
        (updated_orig_remarks, transaction_id)
    )

    # 6. Insert reversal transaction into audit ledger
    cursor.execute("""
        INSERT INTO transactions (student_id, admin_id, amount, previous_balance, new_balance,
                                  status, remarks, created_at, type, payment_mode)
        VALUES (%s,%s,%s,%s,%s,'completed',%s,NOW(),'topup',%s)
    """, (
        student_id,
        admin.get("admin_id"),
        -amount,
        current_balance,
        new_balance,
        f"Reversal of mistaken top-up (Txn #{transaction_id})",
        original["payment_mode"]
    ))

    # 7. Update live student balance
    cursor.execute("UPDATE students SET balance=%s WHERE student_id=%s", (new_balance, student_id))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Top-up of ₱{amount:.2f} reversed. New student balance: ₱{new_balance:.2f}",
        "new_balance": float(new_balance),
        "school_id": student.get("school_id")
    })





@app.route("/edit_transaction/<int:transaction_id>", methods=["POST"])
def edit_transaction(transaction_id):
    admin = _get_logged_in_admin()
    if not admin:
        return redirect(url_for("signin_admin"))

    new_amount = float(request.form["amount"])
    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT student_id, amount FROM transactions WHERE transaction_id=%s", (transaction_id,))
    txn = cursor.fetchone()
    if not txn:
        conn.close()
        return jsonify({"error": "Transaction not found"}), 404

    student_id = txn["student_id"]
    old_amount = float(txn["amount"])

    # Update transaction amount
    cursor.execute("UPDATE transactions SET amount=%s WHERE transaction_id=%s", (new_amount, transaction_id))

    # Adjust student balance
    difference = new_amount - old_amount
    cursor.execute("UPDATE students SET balance = balance + %s WHERE student_id=%s", (difference, student_id))

    conn.commit()

    # Fetch updated student info
    cursor.execute("SELECT full_name, school_id, balance FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()
    conn.close()

    return jsonify(student)



@app.route("/delete_transaction/<int:transaction_id>", methods=["POST"])
def delete_transaction(transaction_id):
    admin = _get_logged_in_admin()
    if not admin:
        return redirect(url_for("signin_admin"))

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
    cursor.execute("DELETE FROM transactions WHERE transaction_id=%s", (transaction_id,))
    conn.commit()
    conn.close()

    flash("Transaction deleted.", "success")
    return redirect(url_for("dashboard_admin"))




# ---------------- Staff QR Generation ----------------
@app.route("/staff/dashboard")
@app.route("/dashboard/staff")
def dashboard_staff():
    staff = _get_logged_in_staff()
    if not staff:
        return redirect(url_for("signin_staff"))

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # Normalize historical student wallet deductions that were labeled 'cash' before the modal upgrade
    try:
        cursor.execute("""
            UPDATE transactions
            SET payment_mode = 'wallet'
            WHERE student_id IS NOT NULL
              AND previous_balance IS NOT NULL
              AND new_balance IS NOT NULL
              AND previous_balance > new_balance
              AND LOWER(COALESCE(payment_mode, '')) = 'cash'
        """)
        conn.commit()
    except Exception:
        pass

    # All completed canteen purchase transactions across the canteen
    cursor.execute("""
        SELECT t.transaction_id, t.student_id, st.full_name AS student_name, st.school_id, st.email AS student_email,
               t.amount, t.previous_balance, t.new_balance, t.payment_mode, t.remarks,
               t.type, t.status, t.created_at, t.customer_name
        FROM transactions t
        LEFT JOIN students st ON t.student_id = st.student_id
        WHERE t.status = 'completed' AND LOWER(COALESCE(t.type, 'purchase')) != 'topup'
        ORDER BY t.created_at DESC
    """)
    staff_transactions = cursor.fetchall() or []

    # ✅ Today’s transactions only (canteen purchases today)
    cursor.execute("""
        SELECT t.transaction_id, t.student_id, st.full_name AS student_name, st.school_id, st.email AS student_email,
               t.amount, t.previous_balance, t.new_balance, t.payment_mode, t.remarks,
               t.type, t.status, t.created_at, t.customer_name
        FROM transactions t
        LEFT JOIN students st ON t.student_id = st.student_id
        WHERE DATE(t.created_at) = CURRENT_DATE AND t.status = 'completed' AND t.type != 'topup'
        ORDER BY t.created_at DESC
    """)
    todays_transactions = cursor.fetchall() or []

    # Daily totals (raw table)
    cursor.execute("SELECT created_at, amount, mode, category FROM staff_totals")
    staff_totals = cursor.fetchall() or []

    # --- Chart datasets ---
    cursor.execute("""
        SELECT DATE(created_at) AS date, type, COUNT(*) AS cnt
        FROM transactions
        WHERE staff_id=%s
        GROUP BY DATE(created_at), type
        ORDER BY date
    """, (session["staff_id"],))
    txn_data = cursor.fetchall()
    txn_dates = sorted(set([row["date"].strftime("%Y-%m-%d") for row in txn_data]))
    txn_topups = [sum(row["cnt"] for row in txn_data if row["date"].strftime("%Y-%m-%d")==d and row["type"]=="topup") for d in txn_dates]
    txn_purchases = [sum(row["cnt"] for row in txn_data if row["date"].strftime("%Y-%m-%d")==d and row["type"]=="purchase") for d in txn_dates]

    cursor.execute("""
        SELECT DATE(created_at) AS date, mode, SUM(amount) AS total
        FROM staff_totals
        GROUP BY DATE(created_at), mode
        ORDER BY date
    """)
    totals_data = cursor.fetchall()
    totals_dates = sorted(set([row["date"].strftime("%Y-%m-%d") for row in totals_data]))
    manual_totals = [sum(row["total"] for row in totals_data if row["date"].strftime("%Y-%m-%d")==d and row["mode"]=="manual") for d in totals_dates]
    cashless_totals = [sum(row["total"] for row in totals_data if row["date"].strftime("%Y-%m-%d")==d and row["mode"]=="cashless") for d in totals_dates]
    other_totals = [sum(row["total"] for row in totals_data if row["date"].strftime("%Y-%m-%d")==d and row["mode"]=="others") for d in totals_dates]

    # --- Summary totals for the 4 POS KPI Cards ---
    todays_total = sum(float(t.get("amount") or 0) for t in todays_transactions)
    total_sales = sum(float(t.get("amount") or 0) for t in staff_transactions if str(t.get("type") or "").strip().lower() != "topup")

    # Set resolved_mode on staff_transactions for all-time order history
    for t in staff_transactions:
        pm = str(t.get("payment_mode") or "").strip().lower()
        prev_b = t.get("previous_balance")
        new_b = t.get("new_balance")
        has_wallet_deduction = (t.get("student_id") is not None and prev_b is not None and new_b is not None and float(prev_b) > float(new_b))
        if pm in ("gcash", "ewallet", "e-wallet"):
            t["resolved_mode"] = "gcash"
        elif pm in ("wallet", "cashless") or has_wallet_deduction:
            t["resolved_mode"] = "wallet"
        else:
            t["resolved_mode"] = "cash"

    # Calculate 4 POS KPI cards from TODAY'S transactions (consistent with /api/staff/live_sync)
    wallet_sales_total = 0.0
    wallet_orders_count = 0
    cash_sales_total = 0.0
    cash_orders_count = 0
    gcash_sales_total = 0.0
    gcash_orders_count = 0

    for t in todays_transactions:
        if str(t.get("type") or "").strip().lower() == "topup":
            continue
        amt = float(t.get("amount") or 0)
        pm = str(t.get("payment_mode") or "").strip().lower()
        prev_b = t.get("previous_balance")
        new_b = t.get("new_balance")
        has_wallet_deduction = (t.get("student_id") is not None and prev_b is not None and new_b is not None and float(prev_b) > float(new_b))

        if pm in ("gcash", "ewallet", "e-wallet"):
            gcash_sales_total += amt
            gcash_orders_count += 1
            t["resolved_mode"] = "gcash"
        elif pm in ("wallet", "cashless") or has_wallet_deduction:
            wallet_sales_total += amt
            wallet_orders_count += 1
            t["resolved_mode"] = "wallet"
        else:
            cash_sales_total += amt
            cash_orders_count += 1
            t["resolved_mode"] = "cash"

    visitors_total = cash_sales_total + gcash_sales_total

    # --- Custom Canteen Products ---
    canteen_products = []
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canteen_products (
                product_id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description VARCHAR(255) DEFAULT 'Fresh canteen item',
                category VARCHAR(30) DEFAULT 'Main',
                price NUMERIC(10, 2) NOT NULL,
                image_path VARCHAR(255),
                icon VARCHAR(20) DEFAULT '🍽️',
                stock INT DEFAULT 50,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            cursor.execute("ALTER TABLE canteen_products ADD COLUMN stock INT DEFAULT 50")
            conn.commit()
        except Exception:
            pass
        cursor.execute("SELECT product_id, name, description, category, price, image_path, icon, stock FROM canteen_products ORDER BY product_id ASC")
        canteen_products = cursor.fetchall() or []
        if not canteen_products:
            default_prods = [
                ('Tapsilog', 'Beef tapa, egg & garlic rice', 'Main', 75.00, 'images/tap_silog.jpg', '🍳', 50),
                ('Teh Ais', 'Chilled sweet milk tea', 'Drink', 25.00, None, '🧋', 50),
                ('Tiramisu Cup', 'Coffee-infused cream dessert', 'Dessert', 100.00, None, '🍰', 50),
                ('Tocilog', 'Sweet pork tocino, egg & rice', 'Main', 70.00, None, '🥓', 50),
                ('Chicken Sandwich', 'Toasted sandwich with dressing', 'Snack', 45.00, None, '🥪', 50),
                ('Bottled Water (500ml)', 'Purified drinking water', 'Drink', 15.00, None, '💧', 50),
            ]
            for dp in default_prods:
                cursor.execute(
                    "INSERT INTO canteen_products (name, description, category, price, image_path, icon, stock) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    dp
                )
            conn.commit()
            cursor.execute("SELECT product_id, name, description, category, price, image_path, icon, stock FROM canteen_products ORDER BY product_id ASC")
            canteen_products = cursor.fetchall() or []
    except Exception as e:
        print("canteen_products load notice:", e)

    return render_template("dashboard_staff.html",
                           staff=staff,
                           staff_id=session["staff_id"],
                           staff_transactions=staff_transactions,
                           todays_transactions=todays_transactions,
                           staff_totals=staff_totals,
                           txn_dates=txn_dates,
                           txn_topups=txn_topups,
                           txn_purchases=txn_purchases,
                           totals_dates=totals_dates,
                           manual_totals=manual_totals,
                           cashless_totals=cashless_totals,
                           other_totals=other_totals,
                           todays_total=todays_total,
                           total_sales=total_sales,
                           visitors_total=visitors_total,
                           wallet_sales_total=wallet_sales_total,
                           wallet_orders_count=wallet_orders_count,
                           cash_sales_total=cash_sales_total,
                           cash_orders_count=cash_orders_count,
                           gcash_sales_total=gcash_sales_total,
                           gcash_orders_count=gcash_orders_count,
                           canteen_products=canteen_products,
                           staff_analytics=_get_staff_sales_analytics(cursor, "daily"))


# Add New Canteen Product (with Picture, Name, Price, Stock)
@app.route("/staff_add_product", methods=["POST"])
def staff_add_product():
    if not _get_logged_in_staff() and not _get_logged_in_admin():
        return jsonify({"success": False, "message": "Unauthorized access. Staff privileges required."}), 401
    try:
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip() or "Freshly prepared canteen item"
        category = (request.form.get("category") or "Main").strip()
        price_raw = request.form.get("price") or "0"
        price = float(price_raw)
        stock_raw = request.form.get("stock")
        try:
            stock = max(0, int(stock_raw)) if stock_raw not in (None, "") else 50
        except (ValueError, TypeError):
            stock = 50

        if not name or price <= 0:
            return jsonify({"success": False, "message": "Please provide a valid product name and price."})

        category_icons = {
            "Main": "🍱",
            "Snack": "🥪",
            "Drink": "🧋",
            "Dessert": "🍰"
        }
        icon = category_icons.get(category, "🍽️")

        image_rel_path = None
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            safe_name = secure_filename(image_file.filename)
            ext = os.path.splitext(safe_name)[1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                ext = ".jpg"
            unique_filename = f"prod_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
            products_dir = os.path.join(app.root_path, "static", "images", "products")
            os.makedirs(products_dir, exist_ok=True)
            save_path = os.path.join(products_dir, unique_filename)
            image_file.save(save_path)
            image_rel_path = f"images/products/{unique_filename}"

        conn = get_connection()
        cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canteen_products (
                product_id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description VARCHAR(255) DEFAULT 'Fresh canteen item',
                category VARCHAR(30) DEFAULT 'Main',
                price NUMERIC(10, 2) NOT NULL,
                image_path VARCHAR(255),
                icon VARCHAR(20) DEFAULT '🍽️',
                stock INT DEFAULT 50,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            """INSERT INTO canteen_products (name, description, category, price, image_path, icon, stock)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (name, description, category, price, image_rel_path, icon, stock)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()

        return jsonify({
            "success": True,
            "product": {
                "product_id": new_id,
                "name": name,
                "description": description,
                "category": category,
                "price": price,
                "image_url": url_for("static", filename=image_rel_path) if image_rel_path else None,
                "icon": icon,
                "stock": stock
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to add product: {e}"})


# Edit Existing Canteen Product (with Picture, Name, Price, Description, Category, Stock)
@app.route("/staff_edit_product/<int:product_id>", methods=["POST"])
def staff_edit_product(product_id):
    if not _get_logged_in_staff() and not _get_logged_in_admin():
        return jsonify({"success": False, "message": "Unauthorized access. Staff privileges required."}), 401
    try:
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip() or "Freshly prepared canteen item"
        category = (request.form.get("category") or "Main").strip()
        price_raw = request.form.get("price") or "0"
        price = float(price_raw)
        stock_raw = request.form.get("stock")
        try:
            stock = max(0, int(stock_raw)) if stock_raw not in (None, "") else 0
        except (ValueError, TypeError):
            stock = 0

        if not name or price <= 0:
            return jsonify({"success": False, "message": "Please provide a valid product name and price."})

        category_icons = {
            "Main": "🍱",
            "Snack": "🥪",
            "Drink": "🧋",
            "Dessert": "🍰"
        }
        icon = category_icons.get(category, "🍽️")

        conn = get_connection()
        cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM canteen_products WHERE product_id=%s", (product_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            return jsonify({"success": False, "message": "Product not found."})

        image_rel_path = existing.get("image_path")
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            safe_name = secure_filename(image_file.filename)
            ext = os.path.splitext(safe_name)[1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                ext = ".jpg"
            unique_filename = f"prod_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
            products_dir = os.path.join(app.root_path, "static", "images", "products")
            os.makedirs(products_dir, exist_ok=True)
            save_path = os.path.join(products_dir, unique_filename)
            image_file.save(save_path)
            image_rel_path = f"images/products/{unique_filename}"

        cursor.execute(
            """UPDATE canteen_products 
               SET name=%s, description=%s, category=%s, price=%s, image_path=%s, icon=%s, stock=%s 
               WHERE product_id=%s""",
            (name, description, category, price, image_rel_path, icon, stock, product_id)
        )
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "product": {
                "product_id": product_id,
                "name": name,
                "description": description,
                "category": category,
                "price": price,
                "image_url": url_for("static", filename=image_rel_path) if image_rel_path else None,
                "icon": icon,
                "stock": stock
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to update product: {e}"})


@app.route("/staff_delete_product/<int:product_id>", methods=["POST"])
def staff_delete_product(product_id):
    if not _get_logged_in_staff() and not _get_logged_in_admin():
        return jsonify({"success": False, "message": "Unauthorized access. Staff privileges required."}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM canteen_products WHERE product_id=%s", (product_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


def _resolve_and_validate_student_qr(cursor, raw_qr):
    """
    Resolves a student from a scanned QR code or School ID string.
    Returns (student_dict, error_message, is_dynamic_qr).
    - Fixed QR / direct School ID lookup (no hyphen, or matches school_id/qr_code directly):
      returns (student, None, False).
    - Dynamic QR ("<student_id>-<token>"):
      Validates that <token> equals students.dynamic_qr_token AND time.time() <= students.dynamic_qr_expires_at.
    """
    student_qr = str(raw_qr or "").strip()
    if not student_qr:
        return None, "No QR data provided", False

    # 1. Fixed QR or direct School ID without hyphen
    if "-" not in student_qr:
        cursor.execute(
            """SELECT student_id, full_name, school_id, email, parent_email, balance,
                      dynamic_qr_token, dynamic_qr_expires_at
               FROM students
               WHERE school_id=%s OR CAST(student_id AS CHAR)=%s OR qr_code=%s""",
            (student_qr, student_qr, student_qr),
        )
        student = cursor.fetchone()
        if not student:
            return None, "Student record not found!", False
        return student, None, False

    # 2. Check if an enrolled school_id or qr_code literally matches the hyphenated string
    cursor.execute(
        """SELECT student_id, full_name, school_id, email, parent_email, balance,
                  dynamic_qr_token, dynamic_qr_expires_at
           FROM students
           WHERE school_id=%s OR qr_code=%s""",
        (student_qr, student_qr),
    )
    exact_student = cursor.fetchone()
    if exact_student:
        return exact_student, None, False

    # 3. Dynamic QR format: "<student_id>-<token>"
    parsed_student_id, scanned_token = student_qr.split("-", 1)
    parsed_student_id = parsed_student_id.strip()
    scanned_token = scanned_token.strip()

    cursor.execute(
        """SELECT student_id, full_name, school_id, email, parent_email, balance,
                  dynamic_qr_token, dynamic_qr_expires_at
           FROM students
           WHERE CAST(student_id AS CHAR)=%s OR school_id=%s""",
        (parsed_student_id, parsed_student_id),
    )
    student = cursor.fetchone()
    if not student:
        return None, "Student record not found!", False

    active_token = str(student.get("dynamic_qr_token") or "").strip()
    try:
        expires_at = int(student.get("dynamic_qr_expires_at") or 0)
    except (ValueError, TypeError):
        expires_at = 0

    now_ts = int(time.time())

    if not active_token or scanned_token != active_token:
        return (
            None,
            "Invalid or expired Dynamic QR Code! A newer QR code has already been generated or this code was already used.",
            True,
        )

    if expires_at <= 0 or now_ts > expires_at:
        return (
            None,
            "Dynamic QR Code has expired! Please ask the student to regenerate their QR code.",
            True,
        )

    return student, None, True


# Preview Student Details upon QR scan
@app.route("/staff_preview_student_qr", methods=["POST"])
def staff_preview_student_qr():
    if not _get_logged_in_staff() and not _get_logged_in_admin():
        return jsonify({"success": False, "message": "Unauthorized access. Staff privileges required."}), 401
    try:
        data = request.get_json() or {}
        student_qr = str(data.get("studentQr") or "").strip()
        if not student_qr:
            return jsonify({"success": False, "message": "No QR data provided"})

        conn = get_connection()
        cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        student, err_msg, is_dynamic = _resolve_and_validate_student_qr(cursor, student_qr)
        if not student:
            conn.close()
            return jsonify({"success": False, "expired_qr": is_dynamic, "message": err_msg})

        # Ensure at least a 15s window from preview to auto-pay completion if token is still the active one
        if is_dynamic:
            now_ts = int(time.time())
            cur_exp = int(student.get("dynamic_qr_expires_at") or 0)
            if cur_exp - now_ts < 15:
                cursor.execute(
                    "UPDATE students SET dynamic_qr_expires_at=%s WHERE student_id=%s AND dynamic_qr_token=%s",
                    (now_ts + 15, student["student_id"], student.get("dynamic_qr_token")),
                )
                conn.commit()

        conn.close()
        return jsonify({
            "success": True,
            "student_id": student["student_id"],
            "full_name": student["full_name"],
            "school_id": student["school_id"],
            "balance": float(student["balance"] or 0),
            "is_dynamic_qr": is_dynamic
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


def send_student_pos_receipt_email(
    to_email,
    txn_id,
    customer_name,
    school_id,
    items_summary,
    amount,
    payment_mode,
    prev_balance=None,
    new_balance=None,
    staff_name="Canteen Cashier",
    created_at=None,
):
    to_email = str(to_email or "").strip()
    if not to_email or "@" not in to_email:
        return False

    amt_val = float(amount or 0)
    dt_str = str(created_at or now_pst().strftime("%Y-%m-%d %H:%M:%S"))
    items_str = str(items_summary or "Canteen POS Purchase")
    pm = str(payment_mode or "wallet").lower()
    if pm == "wallet":
        mode_label = "Campus Wallet (Balance Deduction)"
    elif pm == "gcash":
        mode_label = "GCash / E-Wallet"
    else:
        mode_label = "Physical Cash"

    wallet_html = ""
    wallet_text = ""
    if pm == "wallet" and prev_balance is not None and new_balance is not None:
        p_val = float(prev_balance)
        n_val = float(new_balance)
        wallet_text = f"\nPrevious Wallet Balance: PHP {p_val:.2f}\nRemaining Wallet Balance: PHP {n_val:.2f}\n"
        wallet_html = f"""
        <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:10px;padding:10px 12px;margin-top:10px;font-family:monospace;font-size:12px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="color:#475569;">Previous Wallet Balance:</span>
            <strong style="color:#1e293b;">&#8369;{p_val:.2f}</strong>
          </div>
          <div style="display:flex;justify-content:space-between;">
            <span style="color:#475569;">Remaining Wallet Balance:</span>
            <strong style="color:#4338ca;">&#8369;{n_val:.2f}</strong>
          </div>
        </div>
        """

    school_id_line_text = f"Student ID: {school_id}\n" if school_id else ""
    school_id_line_html = f"""
      <tr>
        <td style="padding:3px 0;color:#64748b;">Student ID:</td>
        <td style="padding:3px 0;text-align:right;font-weight:bold;color:#4338ca;">{school_id}</td>
      </tr>
    """ if school_id else ""

    subject = f"🧾 Official Canteen E-Receipt #{txn_id} — ₱{amt_val:.2f}"
    body_text = (
        f"Scuola Dei Bambini De Sta. Terisita International Montessori School Inc.\n"
        f"Official Campus Canteen & E-Wallet POS Receipt\n"
        f"--------------------------------------------------\n"
        f"Receipt No: #{txn_id}\n"
        f"Date & Time: {dt_str}\n"
        f"Cashier: {staff_name}\n"
        f"Student / Customer: {customer_name}\n"
        f"{school_id_line_text}"
        f"--------------------------------------------------\n"
        f"Items Ordered: {items_str}\n"
        f"Payment Method: {mode_label}\n"
        f"TOTAL PAID: PHP {amt_val:.2f}\n"
        f"{wallet_text}"
        f"--------------------------------------------------\n"
        f"Thank you for your purchase!"
    )

    body_html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:440px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.05);">
      <div style="background:linear-gradient(135deg,#6b21a8,#db2777);color:#ffffff;padding:20px;text-align:center;">
        <img src="cid:school_logo" alt="Scuola dei Bambini" width="68" height="68" style="width:68px;height:68px;border-radius:50%;border:3px solid #ffffff;box-shadow:0 4px 10px rgba(0,0,0,0.18);display:inline-block;margin-bottom:8px;background:#ffffff;">
        <h2 style="margin:0;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;line-height:1.35;color:#ffffff;">Scuola Dei Bambini De Sta. Terisita International Montessori School Inc.</h2>
        <p style="margin:4px 0 0;font-size:11px;opacity:0.9;color:#f3e8ff;">Official Campus Canteen &amp; E-Wallet POS E-Receipt</p>
      </div>
      <div style="padding:18px 20px;font-size:13px;color:#334155;">
        <table style="width:100%;border-collapse:collapse;font-size:12px;border-bottom:1px dashed #cbd5e1;padding-bottom:10px;margin-bottom:12px;">
          <tr>
            <td style="padding:3px 0;color:#64748b;">Receipt No:</td>
            <td style="padding:3px 0;text-align:right;font-weight:bold;color:#0f172a;">#{txn_id}</td>
          </tr>
          <tr>
            <td style="padding:3px 0;color:#64748b;">Date &amp; Time:</td>
            <td style="padding:3px 0;text-align:right;color:#1e293b;">{dt_str}</td>
          </tr>
          <tr>
            <td style="padding:3px 0;color:#64748b;">Cashier:</td>
            <td style="padding:3px 0;text-align:right;color:#1e293b;">{staff_name}</td>
          </tr>
          <tr>
            <td style="padding:3px 0;color:#64748b;">Student / Customer:</td>
            <td style="padding:3px 0;text-align:right;font-weight:bold;color:#0f172a;">{customer_name}</td>
          </tr>
          {school_id_line_html}
        </table>

        <div style="margin-bottom:12px;">
          <div style="font-size:10px;font-weight:bold;text-transform:uppercase;color:#64748b;margin-bottom:4px;">Items / Order Details</div>
          <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:10px 12px;font-weight:600;color:#0f172a;">
            {items_str}
          </div>
        </div>

        <div style="border-top:1px dashed #cbd5e1;padding-top:10px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:12px;">
            <span style="color:#64748b;">Payment Method:</span>
            <strong style="color:#6b21a8;">{mode_label}</strong>
          </div>
          {wallet_html}
          <div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:12px;padding-top:10px;border-top:1px solid #f1f5f9;">
            <span style="font-size:14px;font-weight:800;color:#0f172a;">TOTAL PAID:</span>
            <span style="font-size:20px;font-weight:800;color:#6b21a8;">&#8369;{amt_val:.2f}</span>
          </div>
        </div>

        <p style="text-align:center;font-size:11px;color:#94a3b8;margin:16px 0 0;">
          This is an official paperless e-receipt automatically sent to your registered student email.
        </p>
      </div>
    </div>
    """

    return send_email(
        to_emails=[to_email],
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        async_send=True,
    )


@app.route("/staff_send_receipt_email", methods=["POST"])
def staff_send_receipt_email():
    staff = _get_logged_in_staff()
    admin = _get_logged_in_admin()
    if not staff and not admin:
        return jsonify({"success": False, "message": "Unauthorized access. Staff privileges required."}), 401
    try:
        data = request.get_json() or {}
        txn_id = data.get("txn_id")
        recipient_email = str(data.get("email") or "").strip()

        staff_name = staff["full_name"] if staff else (admin["full_name"] if admin else "Canteen Staff")

        conn = get_connection()
        cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        cursor.execute(
            """
            SELECT t.transaction_id, t.student_id, st.full_name AS student_name, st.school_id,
                   st.email AS student_email, st.parent_email AS student_parent_email,
                   t.amount, t.previous_balance, t.new_balance, t.payment_mode, t.remarks,
                   t.created_at, t.customer_name
            FROM transactions t
            LEFT JOIN students st ON t.student_id = st.student_id
            WHERE t.transaction_id = %s
            """,
            (txn_id,),
        )
        txn = cursor.fetchone()
        conn.close()

        if not txn:
            return jsonify({"success": False, "message": "Transaction record not found."})

        target_email = (
            recipient_email
            or str(txn.get("student_email") or "").strip()
            or str(txn.get("student_parent_email") or "").strip()
        )
        if not target_email or "@" not in target_email:
            return jsonify({
                "success": False,
                "message": "No student email on file for this order. Please enter a recipient email address."
            })

        pm = str(txn.get("payment_mode") or "").strip().lower()
        prev_b = txn.get("previous_balance")
        new_b = txn.get("new_balance")
        has_wallet_deduction = (txn.get("student_id") is not None and prev_b is not None and new_b is not None and float(prev_b) > float(new_b))
        if pm in ("gcash", "ewallet", "e-wallet"):
            resolved_mode = "gcash"
        elif pm in ("wallet", "cashless") or has_wallet_deduction:
            resolved_mode = "wallet"
        else:
            resolved_mode = "cash"

        send_student_pos_receipt_email(
            to_email=target_email,
            txn_id=txn["transaction_id"],
            customer_name=txn.get("student_name") or txn.get("customer_name") or "Student",
            school_id=txn.get("school_id") or "",
            items_summary=txn.get("remarks") or "Canteen POS Purchase",
            amount=txn.get("amount") or 0,
            payment_mode=resolved_mode,
            prev_balance=prev_b,
            new_balance=new_b,
            staff_name=staff_name,
            created_at=txn.get("created_at"),
        )

        return jsonify({
            "success": True,
            "email": target_email,
            "message": f"Official e-receipt sent to {target_email}!"
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Error sending receipt email: {e}"})


def _deduct_canteen_product_stock(cursor, cart_items):
    """Safely decrement canteen product stock when cart items are purchased."""
    if not isinstance(cart_items, list):
        return
    for item in cart_items:
        if not isinstance(item, dict):
            continue
        p_id = item.get("product_id")
        if not p_id and str(item.get("id", "")).startswith("prod_"):
            try:
                p_id = int(str(item["id"]).split("_")[1])
            except (ValueError, IndexError):
                p_id = None
        if p_id:
            try:
                qty = max(1, int(item.get("qty") or 1))
                cursor.execute(
                    "UPDATE canteen_products SET stock = CASE WHEN stock >= %s THEN stock - %s ELSE 0 END WHERE product_id = %s",
                    (qty, qty, p_id)
                )
            except Exception as e:
                print(f"[STOCK DEDUCT NOTICE] Failed to deduct product {p_id}: {e}")


# Scan QR & Registered Student Checkout
@app.route("/staff_qr_transaction", methods=["POST"])
def staff_qr_transaction():
    staff = _get_logged_in_staff()
    admin = _get_logged_in_admin()
    if not staff and not admin:
        return jsonify({"success": False, "message": "Unauthorized access. Staff privileges required."}), 401
    try:
        data = request.get_json() or {}
        student_qr = str(data.get("studentQr") or "").strip()
        amount = Decimal(str(data.get("amount") or 0))
        mode = (data.get("mode") or "wallet").lower()
        staff_id = staff["staff_id"] if staff else None
        staff_name = staff["full_name"] if staff else (admin["full_name"] if admin else "Canteen Cashier")

        if not student_qr or amount <= 0:
            return jsonify({"success": False, "message": "Invalid QR or order amount!"})

        # Build cart items summary for remarks
        explicit_remarks = str(data.get("remarks") or "").strip()
        cart_items = data.get("cart") or []
        cart_summary = ""
        if isinstance(cart_items, list) and cart_items:
            parts = []
            for item in cart_items:
                if isinstance(item, dict) and item.get("name"):
                    qty = int(item.get("qty") or 1)
                    parts.append(f"{qty}× {item.get('name')}")
            cart_summary = ", ".join(parts)
        remarks_val = explicit_remarks or cart_summary or None

        # Validate fixed/school ID or single-use dynamic QR ("<student_id>-<token>")
        conn = get_connection()
        cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        student, err_msg, is_dynamic = _resolve_and_validate_student_qr(cursor, student_qr)
        if not student:
            conn.close()
            return jsonify({"success": False, "expired_qr": is_dynamic, "message": err_msg})

        current_balance = Decimal(str(student["balance"] or 0))
        student_email = str(student.get("email") or student.get("parent_email") or "").strip()

        # Upgrade B Fallback 1: Registered student pays full amount in Cash at Counter (wallet untouched)
        if mode in ("cash_counter", "cash"):
            new_balance = current_balance
            cursor.execute(
                """INSERT INTO transactions
                   (student_id, customer_name, staff_id, amount, previous_balance, new_balance, status, remarks, type, payment_mode, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,'completed',%s,'purchase','cash',NOW())""",
                (student["student_id"], student["full_name"], staff_id, amount, current_balance, new_balance, remarks_val),
            )
            txn_id = getattr(cursor, "lastrowid", None)
            _deduct_canteen_product_stock(cursor, cart_items)
            if is_dynamic:
                cursor.execute(
                    "UPDATE students SET dynamic_qr_token=NULL, dynamic_qr_expires_at=NULL WHERE student_id=%s",
                    (student["student_id"],),
                )
            conn.commit()
            conn.close()

            if student_email:
                send_student_pos_receipt_email(
                    to_email=student_email,
                    txn_id=txn_id or "POS",
                    customer_name=student["full_name"],
                    school_id=student.get("school_id") or "",
                    items_summary=remarks_val,
                    amount=amount,
                    payment_mode="cash",
                    prev_balance=current_balance,
                    new_balance=new_balance,
                    staff_name=staff_name,
                )

            return jsonify({
                "success": True,
                "payment_type": "cash_counter",
                "student_name": student["full_name"],
                "student_email": student_email,
                "previous_balance": float(current_balance),
                "new_balance": float(new_balance),
                "amount": float(amount)
            })

        # Upgrade B Fallback 2: Registered student pays full amount via GCash / E-Wallet (wallet untouched)
        if mode in ("gcash_counter", "gcash"):
            new_balance = current_balance
            cursor.execute(
                """INSERT INTO transactions
                   (student_id, customer_name, staff_id, amount, previous_balance, new_balance, status, remarks, type, payment_mode, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,'completed',%s,'purchase','gcash',NOW())""",
                (student["student_id"], student["full_name"], staff_id, amount, current_balance, new_balance, remarks_val),
            )
            txn_id = getattr(cursor, "lastrowid", None)
            _deduct_canteen_product_stock(cursor, cart_items)
            if is_dynamic:
                cursor.execute(
                    "UPDATE students SET dynamic_qr_token=NULL, dynamic_qr_expires_at=NULL WHERE student_id=%s",
                    (student["student_id"],),
                )
            conn.commit()
            conn.close()

            if student_email:
                send_student_pos_receipt_email(
                    to_email=student_email,
                    txn_id=txn_id or "POS",
                    customer_name=student["full_name"],
                    school_id=student.get("school_id") or "",
                    items_summary=remarks_val,
                    amount=amount,
                    payment_mode="gcash",
                    prev_balance=current_balance,
                    new_balance=new_balance,
                    staff_name=staff_name,
                )

            return jsonify({
                "success": True,
                "payment_type": "gcash_counter",
                "student_name": student["full_name"],
                "student_email": student_email,
                "previous_balance": float(current_balance),
                "new_balance": float(new_balance),
                "amount": float(amount)
            })

        if current_balance < amount:
            conn.close()
            shortfall = float(amount - current_balance)
            return jsonify({
                "success": False,
                "insufficient": True,
                "balance": float(current_balance),
                "required": float(amount),
                "shortfall": shortfall,
                "message": f"Insufficient Balance! {student['full_name']} only has ₱{float(current_balance):.2f} (Short by ₱{shortfall:.2f})."
            })

        new_balance = current_balance - amount
        if is_dynamic:
            cursor.execute(
                "UPDATE students SET balance=%s, dynamic_qr_token=NULL, dynamic_qr_expires_at=NULL WHERE student_id=%s",
                (new_balance, student["student_id"]),
            )
        else:
            cursor.execute(
                "UPDATE students SET balance=%s WHERE student_id=%s",
                (new_balance, student["student_id"]),
            )
        cursor.execute(
            """INSERT INTO transactions
               (student_id, customer_name, staff_id, amount, previous_balance, new_balance, status, remarks, type, payment_mode, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,'completed',%s,'purchase','wallet',NOW())""",
            (student["student_id"], student["full_name"], staff_id, amount, current_balance, new_balance, remarks_val),
        )
        txn_id = getattr(cursor, "lastrowid", None)
        _deduct_canteen_product_stock(cursor, cart_items)
        conn.commit()
        conn.close()

        if student_email:
            send_student_pos_receipt_email(
                to_email=student_email,
                txn_id=txn_id or "POS",
                customer_name=student["full_name"],
                school_id=student.get("school_id") or "",
                items_summary=remarks_val,
                amount=amount,
                payment_mode="wallet",
                prev_balance=current_balance,
                new_balance=new_balance,
                staff_name=staff_name,
            )

        return jsonify({
            "success": True,
            "payment_type": "wallet",
            "student_name": student["full_name"],
            "student_email": student_email,
            "previous_balance": float(current_balance),
            "new_balance": float(new_balance),
            "amount": float(amount)
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})


# Search Student
@app.route("/staff_search_student_transaction", methods=["POST"])
def staff_search_student_transaction():
    if not _get_logged_in_staff() and not _get_logged_in_admin():
        return jsonify({"success": False, "message": "Unauthorized access. Staff privileges required."}), 401
    try:
        data = request.get_json()
        print("Incoming payload:", data)  # ✅ Debug print

        school_id = data.get("school_id")
        amount = float(data.get("amount", 0))
        cart = data.get("cart", [])

        # Lookup student by school_id
        student = Student.query.filter_by(school_id=school_id).first()
        if not student:
            return jsonify({"success": False, "message": "Student not found!"})

        # Ensure balance is numeric
        if student.balance is None:
            student.balance = 0

        if student.balance < amount:
            return jsonify({"success": False, "message": "Insufficient balance!"})

        # Deduct balance
        student.balance -= amount

        # Record transaction
        txn = Transaction(
            student_id=student.id,
            amount=amount,
            items=json.dumps(cart)  # ✅ cart must be serializable
        )
        db.session.add_all([student, txn])
        db.session.commit()

        return jsonify({"success": True, "student_name": student.full_name})

    except Exception as e:
        print("Error in staff_search_student_transaction:", e)  # ✅ Debug print
        db.session.rollback()
        return jsonify({"success": False, "message": "Server error"})


# Unregistered Student
@app.route("/staff_unregistered_transaction", methods=["POST"])
def staff_unregistered_transaction():
    if not _get_logged_in_staff() and not _get_logged_in_admin():
        return jsonify({"success": False, "message": "Unauthorized access. Staff privileges required."}), 401
    data = request.get_json()
    school_id = data.get("schoolId")
    amount = data.get("amount")
    mode = data.get("mode")
    cart = data.get("cart", [])

    txn = Transaction(unregistered_id=school_id, amount=amount, mode=mode, items=json.dumps(cart))
    db.session.add(txn)
    db.session.commit()

    return jsonify({"success": True, "message": "Unregistered transaction recorded!"})

# Visitor/Personnel
@app.route("/staff_visitor_transaction", methods=["POST"])
def staff_visitor_transaction():
    if not _get_logged_in_staff() and not _get_logged_in_admin():
        return jsonify({"success": False, "message": "Unauthorized access. Staff privileges required."}), 401
    data = request.get_json()
    amount = data.get("amount")
    mode = data.get("mode")
    cart = data.get("cart", [])

    txn = Transaction(visitor=True, amount=amount, mode=mode, items=json.dumps(cart))
    db.session.add(txn)
    db.session.commit()

    return jsonify({"success": True, "message": "Visitor transaction recorded!"})


@app.route("/purchase_unregistered", methods=["POST"])
def purchase_unregistered():
    staff = _get_logged_in_staff()
    admin = _get_logged_in_admin()
    if not staff and not admin:
        flash("Unauthorized access. Staff privileges required.", "error")
        return redirect(url_for("signin_staff"))

    customer_name = request.form["customer_name"]
    amount = float(request.form["amount"])
    staff_id = staff["staff_id"] if staff else None

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    cursor.execute("""
        INSERT INTO transactions (student_id, customer_name, staff_id, amount, status, type, payment_mode, created_at)
        VALUES (NULL, %s, %s, %s, 'completed', 'purchase', 'cash', NOW())
    """, (customer_name, staff_id, amount))

    conn.commit()
    conn.close()

    flash("Unregistered purchase recorded successfully.", "success")
    return redirect(url_for("dashboard_staff") if staff else url_for("dashboard_admin"))


@app.route("/staff_students")
def staff_students():
    staff = _get_logged_in_staff()
    admin = _get_logged_in_admin()
    if not staff and not admin:
        return jsonify(success=False, message="Unauthorized access. Staff or Admin privileges required."), 401

    school_id = request.args.get("id")
    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)


    if school_id:
        cursor.execute("SELECT student_id, full_name, school_id, grade_level, strand, balance FROM students WHERE school_id=%s", (school_id,))
        student = cursor.fetchone()
        conn.close()
        if student:
            return jsonify(success=True, student=student)
        else:
            return jsonify(success=False, message="Not found")
    else:
        cursor.execute("SELECT student_id, full_name, school_id, grade_level, strand, balance FROM students")
        students = cursor.fetchall()
        conn.close()
        return jsonify(success=True, students=students)


@app.route("/staff_calculator_sale", methods=["POST"])
def staff_calculator_sale():
    staff = _get_logged_in_staff()
    admin = _get_logged_in_admin()
    if not staff and not admin:
        return jsonify({"success": False, "message": "Unauthorized access. Staff privileges required."}), 401
    try:
        data = request.get_json() or {}
        amount = Decimal(str(data.get("amount") or 0))
        raw_mode = str(data.get("mode") or "cash").strip().lower()
        mode = "gcash" if raw_mode in ("gcash", "e-wallet", "ewallet") else "cash"
        customer_name = str(data.get("customer_name") or "").strip() or "Quick POS Sale"
        remarks = str(data.get("remarks") or "").strip() or None

        if amount <= 0:
            return jsonify({"success": False, "message": "Please calculate or enter an amount greater than ₱0.00."})

        staff_id = staff["staff_id"] if staff else None
        staff_name = staff["full_name"] if staff else (admin["full_name"] if admin else "Canteen Cashier")
        now_dt = now_pst()

        conn = get_connection()
        cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

        # Check if customer_name matches a registered student (by School ID, Full Name, or Email)
        matched_student = None
        if customer_name and customer_name not in ("Quick POS Sale", "Walk-in Customer", "Walk-in (Cash)", "Walk-in (GCash)"):
            clean_lookup = customer_name.strip()
            candidate_id = clean_lookup
            if " — " in clean_lookup:
                candidate_id = clean_lookup.split(" — ")[0].strip()
            elif " - " in clean_lookup:
                candidate_id = clean_lookup.split(" - ")[0].strip()

            cursor.execute(
                """SELECT student_id, full_name, school_id, email, parent_email, balance
                   FROM students
                   WHERE school_id=%s OR CAST(student_id AS CHAR)=%s OR LOWER(full_name)=LOWER(%s) OR LOWER(email)=LOWER(%s)""",
                (candidate_id, candidate_id, clean_lookup, clean_lookup),
            )
            matched_student = cursor.fetchone()
            if not matched_student and candidate_id != clean_lookup:
                cursor.execute(
                    """SELECT student_id, full_name, school_id, email, parent_email, balance
                       FROM students
                       WHERE school_id=%s OR LOWER(full_name)=LOWER(%s)""",
                    (clean_lookup, candidate_id),
                )
                matched_student = cursor.fetchone()

        matched_student_id = matched_student["student_id"] if matched_student else None
        resolved_customer_name = matched_student["full_name"] if matched_student else customer_name

        cursor.execute(
            """
            INSERT INTO transactions
                (student_id, customer_name, staff_id, amount, status, remarks, type, payment_mode, created_at)
            VALUES (%s, %s, %s, %s, 'completed', %s, 'purchase', %s, %s)
            """,
            (matched_student_id, resolved_customer_name, staff_id, amount, remarks, mode, now_dt),
        )
        txn_id = getattr(cursor, "lastrowid", None)
        conn.commit()
        conn.close()

        student_email = ""
        if matched_student:
            student_email = str(matched_student.get("email") or matched_student.get("parent_email") or "").strip()
        elif "@" in customer_name:
            student_email = customer_name

        if student_email:
            send_student_pos_receipt_email(
                to_email=student_email,
                txn_id=txn_id or "POS",
                customer_name=resolved_customer_name,
                school_id=(matched_student.get("school_id") if matched_student else ""),
                items_summary=remarks or "Quick POS Calculator Sale",
                amount=amount,
                payment_mode=mode,
                staff_name=staff_name,
                created_at=now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            )

        return jsonify({
            "success": True,
            "student_email": student_email,
            "transaction": {
                "customer_name": resolved_customer_name,
                "amount": float(amount),
                "payment_mode": mode,
                "remarks": remarks or "Quick POS Calculator Sale",
                "type": "purchase",
                "status": "completed",
                "created_at": now_dt.strftime("%Y-%m-%d %H:%M:%S")
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Error saving sale: {e}"})


@app.route("/staff_record_transaction", methods=["POST"])
def staff_record_transaction():
    data = request.get_json() or {}
    txn_type = data.get("type")
    staff = _get_logged_in_staff()
    staff_id = staff["staff_id"] if staff else session.get("staff_id")
    staff_name = staff["full_name"] if staff else "Canteen Cashier"

    # Build optional remarks from cart or explicit remarks field
    explicit_remarks = str(data.get("remarks") or "").strip()
    cart_items = data.get("cart") or []
    cart_summary = ""
    if isinstance(cart_items, list) and cart_items:
        parts = []
        for item in cart_items:
            if isinstance(item, dict) and item.get("name"):
                qty = int(item.get("qty") or 1)
                parts.append(f"{qty}× {item.get('name')}")
        cart_summary = ", ".join(parts)
    remarks_val = explicit_remarks or cart_summary or None

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    try:
        # ✅ Case 1: QR Scan (registered student)
        if txn_type == "qr":
            qr_code = data.get("qr_code")
            amount = Decimal(str(data.get("amount", 0)))

            student, err_msg, is_dynamic = _resolve_and_validate_student_qr(cursor, qr_code)

            if student:
                if student["balance"] >= amount:
                    new_balance = student["balance"] - amount
                    now_dt = now_pst()
                    if is_dynamic:
                        cursor.execute(
                            "UPDATE students SET balance=%s, dynamic_qr_token=NULL, dynamic_qr_expires_at=NULL WHERE student_id=%s",
                            (new_balance, student["student_id"]),
                        )
                    else:
                        cursor.execute(
                            "UPDATE students SET balance=%s WHERE student_id=%s",
                            (new_balance, student["student_id"]),
                        )
                    cursor.execute("""
                        INSERT INTO transactions (student_id, customer_name, staff_id, amount, previous_balance, new_balance,
                                                  status, remarks, type, payment_mode, created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,'completed',%s,'purchase','wallet',%s)
                    """, (student["student_id"], student["full_name"], staff_id, amount, student["balance"], new_balance,
                          remarks_val, now_dt))
                    txn_id = getattr(cursor, "lastrowid", None)
                    _deduct_canteen_product_stock(cursor, cart_items)
                    conn.commit()
                    student_email = str(student.get("email") or student.get("parent_email") or "").strip()
                    if student_email:
                        send_student_pos_receipt_email(
                            to_email=student_email,
                            txn_id=txn_id or "POS",
                            customer_name=student["full_name"],
                            school_id=student.get("school_id") or "",
                            items_summary=remarks_val,
                            amount=amount,
                            payment_mode="wallet",
                            prev_balance=student["balance"],
                            new_balance=new_balance,
                            staff_name=staff_name,
                            created_at=now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        )
                    return jsonify(success=True, student_email=student_email, transaction={
                        "student_name": student["full_name"],
                        "amount": float(amount),
                        "type": "purchase",
                        "status": "completed",
                        "created_at": now_dt.strftime("%Y-%m-%d %H:%M:%S")
                    })
                else:
                    return jsonify(success=False, message="Insufficient balance.")
            else:
                return jsonify(success=False, message=err_msg or "Student not found.")

        # ✅ Case 2: Search Student (manual entry)
        elif txn_type == "student":
            student_id = data.get("student_id")
            amount = Decimal(str(data.get("amount", 0)))

            cursor.execute("SELECT student_id, full_name, school_id, email, parent_email, balance FROM students WHERE school_id=%s", (student_id,))
            student = cursor.fetchone()

            if student:
                if student["balance"] >= amount:
                    new_balance = student["balance"] - amount
                    now_dt = now_pst()
                    cursor.execute("UPDATE students SET balance=%s WHERE student_id=%s",
                                   (new_balance, student["student_id"]))
                    cursor.execute("""
                        INSERT INTO transactions (student_id, customer_name, staff_id, amount, previous_balance, new_balance,
                                                  status, remarks, type, payment_mode, created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,'completed',%s,'purchase','wallet',%s)
                    """, (student["student_id"], student["full_name"], staff_id, amount, student["balance"], new_balance,
                          remarks_val, now_dt))
                    txn_id = getattr(cursor, "lastrowid", None)
                    _deduct_canteen_product_stock(cursor, cart_items)
                    conn.commit()
                    student_email = str(student.get("email") or student.get("parent_email") or "").strip()
                    if student_email:
                        send_student_pos_receipt_email(
                            to_email=student_email,
                            txn_id=txn_id or "POS",
                            customer_name=student["full_name"],
                            school_id=student.get("school_id") or "",
                            items_summary=remarks_val,
                            amount=amount,
                            payment_mode="wallet",
                            prev_balance=student["balance"],
                            new_balance=new_balance,
                            staff_name=staff_name,
                            created_at=now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        )
                    return jsonify(success=True, student_email=student_email, transaction={
                        "student_name": student["full_name"],
                        "amount": float(amount),
                        "type": "purchase",
                        "status": "completed",
                        "created_at": now_dt.strftime("%Y-%m-%d %H:%M:%S")
                    })
                else:
                    return jsonify(success=False, message="Insufficient balance.")
            else:
                return jsonify(success=False, message="Student not found.")

        # ✅ Case 3: Unregistered Student / Direct Cash or GCash
        elif txn_type == "unregistered":
            school_id = str(data.get("student_id") or "").strip() or "Walk-in Customer"
            amount = Decimal(str(data.get("amount", 0)))
            raw_mode = str(data.get("mode") or "cash").strip().lower()
            mode = "gcash" if raw_mode in ("gcash", "e-wallet", "ewallet") else "cash"
            now_dt = now_pst()

            # Check if school_id / customer_name matches a registered student so we can auto-email their receipt too!
            matched_student = None
            if school_id and school_id not in ("Walk-in Customer", "Walk-in (Cash)", "Walk-in (GCash)"):
                clean_lookup = school_id.strip()
                candidate_id = clean_lookup
                if " — " in clean_lookup:
                    candidate_id = clean_lookup.split(" — ")[0].strip()
                elif " - " in clean_lookup:
                    candidate_id = clean_lookup.split(" - ")[0].strip()

                cursor.execute(
                    """SELECT student_id, full_name, school_id, email, parent_email, balance
                       FROM students
                       WHERE school_id=%s OR CAST(student_id AS CHAR)=%s OR LOWER(full_name)=LOWER(%s) OR LOWER(email)=LOWER(%s)""",
                    (candidate_id, candidate_id, clean_lookup, clean_lookup),
                )
                matched_student = cursor.fetchone()
                if not matched_student and candidate_id != clean_lookup:
                    cursor.execute(
                        """SELECT student_id, full_name, school_id, email, parent_email, balance
                           FROM students
                           WHERE school_id=%s OR LOWER(full_name)=LOWER(%s)""",
                        (clean_lookup, candidate_id),
                    )
                    matched_student = cursor.fetchone()

            matched_student_id = matched_student["student_id"] if matched_student else None
            resolved_name = matched_student["full_name"] if matched_student else school_id

            cursor.execute("""
                INSERT INTO transactions (student_id, customer_name, staff_id, amount, status, remarks, type, payment_mode, created_at)
                VALUES (%s,%s,%s,%s,'completed',%s,'purchase',%s,%s)
            """, (matched_student_id, resolved_name, staff_id, amount, remarks_val, mode, now_dt))
            txn_id = getattr(cursor, "lastrowid", None)
            _deduct_canteen_product_stock(cursor, cart_items)
            conn.commit()

            student_email = ""
            if matched_student:
                student_email = str(matched_student.get("email") or matched_student.get("parent_email") or "").strip()
            elif "@" in school_id:
                student_email = school_id

            if student_email:
                send_student_pos_receipt_email(
                    to_email=student_email,
                    txn_id=txn_id or "POS",
                    customer_name=resolved_name,
                    school_id=(matched_student.get("school_id") if matched_student else ""),
                    items_summary=remarks_val,
                    amount=amount,
                    payment_mode=mode,
                    staff_name=staff_name,
                    created_at=now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                )

            return jsonify(success=True, student_email=student_email, transaction={
                "customer_name": resolved_name,
                "amount": float(amount),
                "payment_mode": mode,
                "remarks": remarks_val,
                "type": "purchase",
                "status": "completed",
                "created_at": now_dt.strftime("%Y-%m-%d %H:%M:%S")
            })

        # ✅ Case 4: Visitor/Personnel
        elif txn_type == "visitor":
            amount = Decimal(str(data.get("amount", 0)))
            raw_mode = str(data.get("mode") or "cash").strip().lower()
            mode = "gcash" if raw_mode in ("gcash", "e-wallet", "ewallet") else "cash"
            customer_name = str(data.get("customer_name") or "").strip() or "Visitor"
            now_dt = now_pst()

            cursor.execute("""
                INSERT INTO transactions (customer_name, staff_id, amount, status, remarks, type, payment_mode, created_at)
                VALUES (%s,%s,%s,'completed',%s,'purchase',%s,%s)
            """, (customer_name, staff_id, amount, remarks_val, mode, now_dt))
            _deduct_canteen_product_stock(cursor, cart_items)
            conn.commit()
            return jsonify(success=True, transaction={
                "customer_name": customer_name,
                "amount": float(amount),
                "payment_mode": mode,
                "remarks": remarks_val,
                "type": "purchase",
                "status": "completed",
                "created_at": now_dt.strftime("%Y-%m-%d %H:%M:%S")
            })

        else:
            return jsonify(success=False, message="Invalid transaction type.")

    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=str(e))
    finally:
        conn.close()



# ---------------- Staff Registered Student Purchase ----------------
@app.route("/staff_transaction", methods=["POST"])
def staff_transaction():
    staff = _get_logged_in_staff()
    if not staff:
        return redirect(url_for("signin_staff"))

    student_id = request.form["student_id"]
    amount = float(request.form["amount"])

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # Check balance
    cursor.execute("SELECT balance FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()
    if not student:
        flash("Student not found.", "error")
        conn.close()
        return redirect(url_for("dashboard_staff"))

    balance = student["balance"] if isinstance(student, dict) else student[0]
    if balance < amount:
        flash("Insufficient balance.", "error")
        conn.close()
        return redirect(url_for("dashboard_staff"))

    # Deduct balance
    cursor.execute("UPDATE students SET balance = balance - %s WHERE student_id=%s", (amount, student_id))
    conn.commit()

    # ✅ Record the purchase transaction with proper casing
    cursor.execute("""INSERT INTO transactions (student_id, staff_id, amount, type, created_at)
                      VALUES (%s,%s,%s,'Purchase',NOW())""",
                   (student_id, staff["staff_id"], amount))
    conn.commit()

    conn.close()
    flash("Purchase recorded successfully!", "success")
    return redirect(url_for("dashboard_staff"))



# ---------------- Manual Input for Unregistered Students ----------------


@app.route("/unregistered_transactions")
def unregistered_transactions():
    admin = _get_logged_in_admin()
    if not admin:
        return redirect(url_for("signin_admin"))

    return redirect(url_for("dashboard_admin", section="unregistered"))



# ---------------- Real-Time QR Scanning (token lookup) ----------------






# ---------------- Confirm Transaction ----------------
@app.route("/confirm_transaction", methods=["GET","POST"])
def confirm_transaction():
    if "pending_txn" not in session:
        return "No transaction pending"

    txn_id = session["pending_txn"]
    if request.method == "POST":
        pin_entered = request.form["pin"]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT student_id, amount FROM transactions WHERE transaction_id=%s", (txn_id,))
        txn = cursor.fetchone()
        student_id, amount = txn

        cursor.execute("SELECT pin, balance, email FROM students WHERE student_id=%s", (student_id,))
        student = cursor.fetchone()
        pin, balance, email = student

        if pin_entered == pin and balance >= amount:
            new_balance = balance - amount
            cursor.execute("UPDATE students SET balance=%s WHERE student_id=%s", (new_balance, student_id))
            cursor.execute("UPDATE transactions SET status='confirmed' WHERE transaction_id=%s", (txn_id,))
            conn.commit()
            conn.close()

            send_email(email, "Transaction Confirmed",
                       f"Your purchase of {amount} has been confirmed. Remaining balance: {new_balance}.")
            session.pop("pending_txn", None)
            return "Transaction successful!"
        else:
            cursor.execute("UPDATE transactions SET status='failed' WHERE transaction_id=%s", (txn_id,))
            conn.commit()
            conn.close()
            session.pop("pending_txn", None)
            return "Invalid PIN or insufficient balance"

    return '''
        <h2>Confirm Transaction</h2>
        <form method="POST">
            <label>Enter 4-digit PIN:</label>
            <input type="password" name="pin" maxlength="4" required><br><br>
            <button type="submit">Confirm</button>
        </form>
    '''

def _ensure_persistent_ssl_cert():
    cert_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile_cert.pem")
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile_key.pem")
    if os.path.exists(cert_file) and os.path.exists(key_file):
        return cert_file, key_file
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import ipaddress

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Scuola dei Bambini QR System"),
            x509.NameAttribute(NameOID.COMMON_NAME, u"Scuola Local Server"),
        ])
        san_list = [x509.DNSName(u"localhost"), x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]
        for ip_str in _LOCAL_HOST_IPS:
            try:
                san_list.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
            except Exception:
                pass

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
            .sign(key, hashes.SHA256())
        )
        with open(key_file, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        return cert_file, key_file
    except Exception as e:
        print("SSL cert generation fallback:", e)
        return "adhoc"


def _start_https_companion_server():
    try:
        from werkzeug.serving import make_server
        ssl_ctx = _ensure_persistent_ssl_cert()
        https_srv = make_server("0.0.0.0", 5443, app, threaded=True, ssl_context=ssl_ctx)
        print("🔒 Mobile Live-Camera HTTPS Server active on https://0.0.0.0:5443")
        https_srv.serve_forever()
    except Exception as e:
        print("HTTPS companion notice:", e)


# =====================================================================
# 🔄 REAL-TIME LIVE SYNC APIs (Zero-Refresh Background Sync)
# =====================================================================

@app.route("/api/admin/live_sync")
def api_admin_live_sync():
    admin = _get_logged_in_admin()
    if not admin:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    # 1. Pending top-ups
    cursor.execute("""
        SELECT t.topup_id, t.student_id, t.amount, t.payment_mode, t.method,
               t.reference_number, t.screenshot_path, t.proof_image, t.created_at,
               s.school_id, s.full_name
        FROM topups t
        JOIN students s ON t.student_id = s.student_id
        WHERE t.status = 'pending'
        ORDER BY t.created_at DESC
    """)
    rows = cursor.fetchall() or []
    pending_list = []
    for r in rows:
        proof = r.get("screenshot_path") or r.get("proof_image") or ""
        created_str = r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if hasattr(r.get("created_at"), "strftime") else str(r.get("created_at") or "")
        pending_list.append({
            "topup_id": r["topup_id"],
            "student_id": r["student_id"],
            "school_id": r.get("school_id") or f"Student #{r['student_id']}",
            "full_name": r.get("full_name") or "Student",
            "amount": float(r.get("amount") or 0),
            "method": r.get("method") or r.get("payment_mode") or "GCash",
            "reference_number": r.get("reference_number") or "---",
            "proof": proof,
            "created_at": created_str
        })

    # 2. Key totals
    cursor.execute("SELECT SUM(amount) AS total FROM transactions WHERE type='topup' AND status='completed'")
    total_topups = float((cursor.fetchone() or {}).get("total") or 0)

    cursor.execute("SELECT SUM(amount) AS total FROM transactions WHERE type='purchase' AND status='completed'")
    total_sales = float((cursor.fetchone() or {}).get("total") or 0)

    cursor.execute("SELECT SUM(amount) AS total FROM transactions WHERE status='completed'")
    total_received = float((cursor.fetchone() or {}).get("total") or 0)

    cursor.execute("SELECT MAX(transaction_id) AS max_id FROM transactions")
    max_tx_row = cursor.fetchone()
    latest_tx_id = max_tx_row["max_id"] if max_tx_row and max_tx_row.get("max_id") else 0

    # 3. Live chart series
    cursor.execute("""
        SELECT DATE(created_at) AS date,
               COALESCE(SUM(CASE WHEN type='topup' THEN amount ELSE 0 END), 0) AS topups,
               COALESCE(SUM(CASE WHEN type='purchase' THEN amount ELSE 0 END), 0) AS purchases
        FROM transactions
        WHERE status='completed'
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    c_rows = cursor.fetchall() or []
    txn_dates = [r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else str(r["date"]) for r in c_rows]
    txn_topups = [float(r["topups"] or 0) for r in c_rows]
    txn_purchases = [float(r["purchases"] or 0) for r in c_rows]

    cursor.execute("""
        SELECT DATE(created_at) AS date,
               COALESCE(SUM(CASE WHEN LOWER(COALESCE(payment_mode, '')) IN ('wallet', 'cashless')
                    OR (student_id IS NOT NULL AND previous_balance IS NOT NULL AND new_balance IS NOT NULL AND previous_balance > new_balance AND LOWER(COALESCE(payment_mode, '')) NOT IN ('cash', 'gcash', 'ewallet', 'e-wallet'))
                    THEN amount ELSE 0 END), 0) AS cashless,
               COALESCE(SUM(CASE WHEN LOWER(COALESCE(payment_mode, '')) = 'cash'
                    AND NOT (student_id IS NOT NULL AND previous_balance IS NOT NULL AND new_balance IS NOT NULL AND previous_balance > new_balance)
                    THEN amount ELSE 0 END), 0) AS manual,
               COALESCE(SUM(CASE WHEN LOWER(COALESCE(payment_mode, '')) IN ('gcash', 'ewallet', 'e-wallet')
                    THEN amount ELSE 0 END), 0) AS others
        FROM transactions
        WHERE status='completed' AND type != 'topup'
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    d_rows = cursor.fetchall() or []
    totals_dates = [r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else str(r["date"]) for r in d_rows]
    manual_totals = [float(r["manual"] or 0) for r in d_rows]
    cashless_totals = [float(r["cashless"] or 0) for r in d_rows]
    other_totals = [float(r["others"] or 0) for r in d_rows]

    cursor.execute("""
        SELECT DATE(created_at) AS date, COUNT(*) AS count
        FROM students
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    reg_rows = cursor.fetchall() or []
    reg_map = {
        (r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else str(r["date"])): int(r["count"] or 0)
        for r in reg_rows
    }
    all_reg_dates = sorted(set(txn_dates) | set(reg_map.keys()))
    reg_dates = all_reg_dates if all_reg_dates else list(reg_map.keys())
    reg_counts = [reg_map.get(d, 0) for d in reg_dates]
    reg_cumulative = []
    running_reg = 0
    for c in reg_counts:
        running_reg += c
        reg_cumulative.append(running_reg)

    cursor.execute("SELECT COUNT(*) AS active_count FROM students WHERE LOWER(COALESCE(status, 'active')) = 'active'")
    active_count = int((cursor.fetchone() or {}).get("active_count") or 0)
    cursor.execute("SELECT COUNT(*) AS inactive_count FROM students WHERE LOWER(COALESCE(status, 'active')) != 'active'")
    inactive_count = int((cursor.fetchone() or {}).get("inactive_count") or 0)
    cursor.execute("SELECT COALESCE(SUM(balance), 0) AS total_wallet_float FROM students")
    total_wallet_float = float((cursor.fetchone() or {}).get("total_wallet_float") or 0)

    trending_recommendations = _get_trending_canteen_recommendations(cursor)

    cursor.execute("""
        SELECT
            (SELECT COUNT(*) FROM admins WHERE LOWER(COALESCE(status, 'approved')) = 'pending')
            + (SELECT COUNT(*) FROM staff WHERE LOWER(COALESCE(status, 'approved')) = 'pending')
            AS pending_accounts_count
    """)
    pending_accounts_count = int((cursor.fetchone() or {}).get("pending_accounts_count") or 0)

    conn.close()

    return jsonify({
        "success": True,
        "pending_count": len(pending_list),
        "pending_accounts_count": pending_accounts_count,
        "pending_topups": pending_list,
        "total_topups": total_topups,
        "total_sales": total_sales,
        "total_received": total_received,
        "latest_tx_id": latest_tx_id,
        "trending_recommendations": trending_recommendations,
        "charts": {
            "txn_dates": txn_dates,
            "txn_topups": txn_topups,
            "txn_purchases": txn_purchases,
            "totals_dates": totals_dates,
            "cashless_totals": cashless_totals,
            "manual_totals": manual_totals,
            "other_totals": other_totals,
            "reg_dates": reg_dates,
            "reg_counts": reg_counts,
            "reg_cumulative": reg_cumulative,
            "active_count": active_count,
            "inactive_count": inactive_count,
            "total_wallet_float": total_wallet_float
        }
    })


@app.route("/api/staff/live_sync")
def api_staff_live_sync():
    staff = _get_logged_in_staff()
    admin = _get_logged_in_admin()
    if not staff and not admin:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN DATE(created_at) = CURRENT_DATE AND type != 'topup' THEN amount ELSE 0 END), 0) AS todays_total,
            COALESCE(SUM(CASE WHEN DATE(created_at) = CURRENT_DATE AND type != 'topup' AND (payment_mode='wallet' OR (type='purchase' AND payment_mode NOT IN ('cash', 'gcash'))) THEN amount ELSE 0 END), 0) AS wallet_sales_total,
            COALESCE(SUM(CASE WHEN DATE(created_at) = CURRENT_DATE AND type != 'topup' AND payment_mode='cash' THEN amount ELSE 0 END), 0) AS cash_sales_total,
            COALESCE(SUM(CASE WHEN DATE(created_at) = CURRENT_DATE AND type != 'topup' AND payment_mode='gcash' THEN amount ELSE 0 END), 0) AS gcash_sales_total,
            COUNT(CASE WHEN DATE(created_at) = CURRENT_DATE AND type != 'topup' THEN 1 END) AS todays_count,
            COUNT(CASE WHEN DATE(created_at) = CURRENT_DATE AND type != 'topup' AND (payment_mode='wallet' OR (type='purchase' AND payment_mode NOT IN ('cash', 'gcash'))) THEN 1 END) AS wallet_count,
            COUNT(CASE WHEN DATE(created_at) = CURRENT_DATE AND type != 'topup' AND payment_mode='cash' THEN 1 END) AS cash_count,
            COUNT(CASE WHEN DATE(created_at) = CURRENT_DATE AND type != 'topup' AND payment_mode='gcash' THEN 1 END) AS gcash_count,
            COALESCE(MAX(transaction_id), 0) AS latest_tx_id
        FROM transactions
        WHERE status = 'completed'
    """)
    row = cursor.fetchone() or {}

    cursor.execute("SELECT SUM(amount) AS total FROM transactions WHERE type='purchase' AND status='completed'")
    all_time_sales = float((cursor.fetchone() or {}).get("total") or 0)

    # Fetch recent today orders (Purchases only)
    cursor.execute("""
        SELECT t.transaction_id, t.created_at, t.amount, t.payment_mode, t.previous_balance, t.new_balance,
               t.remarks, t.student_id, s.full_name AS student_name, t.customer_name,
               COALESCE(s.full_name, t.customer_name, 'Walk-in Customer') AS display_name,
               s.school_id, s.email AS student_email
        FROM transactions t
        LEFT JOIN students s ON t.student_id = s.student_id
        WHERE DATE(t.created_at) = CURRENT_DATE AND t.status = 'completed' AND t.type != 'topup'
        ORDER BY t.transaction_id DESC
        LIMIT 100
    """)
    recent_rows = cursor.fetchall() or []
    recent_orders = []
    for r in recent_rows:
        raw_dt = r.get("created_at")
        if hasattr(raw_dt, "strftime"):
            time_str = raw_dt.strftime("%I:%M %p")
            dt_str = raw_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            dt_str = str(raw_dt or "")
            time_str = dt_str[11:16] if len(dt_str) >= 16 else dt_str

        pm = str(r.get("payment_mode") or "").strip().lower()
        prev_b = r.get("previous_balance")
        new_b = r.get("new_balance")
        has_wallet_deduction = (r.get("student_id") is not None and prev_b is not None and new_b is not None and float(prev_b) > float(new_b))
        if pm in ("gcash", "ewallet", "e-wallet"):
            rmode = "gcash"
        elif pm in ("wallet", "cashless") or has_wallet_deduction:
            rmode = "wallet"
        else:
            rmode = "cash"

        buyer_name = r.get("student_name") or r.get("customer_name") or r.get("display_name") or "Walk-in Customer"

        recent_orders.append({
            "transaction_id": r["transaction_id"],
            "time": time_str,
            "created_at": dt_str,
            "amount": float(r["amount"] or 0),
            "payment_mode": pm,
            "resolved_mode": rmode,
            "previous_balance": float(r["previous_balance"]) if r.get("previous_balance") is not None else None,
            "new_balance": float(r["new_balance"]) if r.get("new_balance") is not None else None,
            "remarks": r.get("remarks") or "Canteen POS Purchase",
            "customer_name": buyer_name,
            "student_name": r.get("student_name") or "",
            "school_id": r.get("school_id") or "",
            "student_id": r.get("student_id"),
            "student_email": r.get("student_email") or ""
        })

    conn.close()

    return jsonify({
        "success": True,
        "todays_total": float(row.get("todays_total") or 0),
        "todays_count": int(row.get("todays_count") or 0),
        "all_time_sales": all_time_sales,
        "wallet_sales_total": float(row.get("wallet_sales_total") or 0),
        "wallet_count": int(row.get("wallet_count") or 0),
        "cash_sales_total": float(row.get("cash_sales_total") or 0),
        "cash_count": int(row.get("cash_count") or 0),
        "gcash_sales_total": float(row.get("gcash_sales_total") or 0),
        "gcash_count": int(row.get("gcash_count") or 0),
        "latest_tx_id": int(row.get("latest_tx_id") or 0),
        "recent_orders": recent_orders
    })


@app.route("/api/admin/trending_recommendations")
def api_admin_trending_recommendations():
    admin = _get_logged_in_admin()
    staff = _get_logged_in_staff()
    if not admin and not staff:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
    data = _get_trending_canteen_recommendations(cursor)
    conn.close()
    return jsonify(data)


@app.route("/api/staff/sales_analytics")
def api_staff_sales_analytics():
    staff = _get_logged_in_staff()
    admin = _get_logged_in_admin()
    if not staff and not admin:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    tf = request.args.get("timeframe", "daily")
    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
    data = _get_staff_sales_analytics(cursor, tf)
    conn.close()
    return jsonify(data)


@app.route("/api/student/live_sync")
def api_student_live_sync():
    student = _get_logged_in_student()
    if not student:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT balance, status FROM students WHERE student_id = %s", (student["student_id"],))
    st_row = cursor.fetchone() or {}

    cursor.execute("SELECT COUNT(*) AS pending_count FROM topups WHERE student_id = %s AND status = 'pending'", (student["student_id"],))
    p_count = (cursor.fetchone() or {}).get("pending_count") or 0

    cursor.execute("""
        SELECT transaction_id, type, amount, new_balance, remarks, created_at, status
        FROM transactions
        WHERE student_id = %s
        ORDER BY transaction_id DESC
        LIMIT 1
    """, (student["student_id"],))
    last_tx = cursor.fetchone()
    if last_tx and hasattr(last_tx.get("created_at"), "strftime"):
        last_tx["created_at"] = last_tx["created_at"].strftime("%Y-%m-%d %H:%M:%S")

    conn.close()

    return jsonify({
        "success": True,
        "balance": float(st_row.get("balance") or 0),
        "status": st_row.get("status") or "active",
        "pending_count": int(p_count),
        "last_transaction": last_tx
    })


@app.route("/api/student/update_profile", methods=["POST"])
def api_student_update_profile():
    student = _get_logged_in_student()
    if not student:
        return jsonify({"success": False, "message": "Unauthorized. Please log in."}), 401

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    current_pin = str(data.get("current_pin") or "").strip()

    if not current_pin:
        return jsonify({"success": False, "message": "Current 4-digit Security PIN is required to authorize changes."}), 400

    # 1. Verify student current PIN
    stored_pin = str(student.get("pin") or "").strip()
    if not stored_pin:
        stored_pin = "1234"

    if current_pin != stored_pin:
        return jsonify({"success": False, "message": "Incorrect 4-digit Security PIN. Profile updates rejected."}), 403

    # 2. Extract and sanitize inputs
    full_name = str(data.get("full_name") or "").strip()
    grade_level = str(data.get("grade_level") or "").strip()
    strand = str(data.get("strand") or "").strip()
    contact_number = str(data.get("contact_number") or "").strip()
    parent_email = str(data.get("parent_email") or "").strip()
    new_password = str(data.get("new_password") or "").strip()
    new_pin = str(data.get("new_pin") or "").strip()

    if not full_name:
        return jsonify({"success": False, "message": "Full Name cannot be empty."}), 400

    conn = get_connection()
    cursor = conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    updates = [
        "full_name = %s",
        "grade_level = %s",
        "strand = %s",
        "contact_number = %s",
        "parent_email = %s"
    ]
    params = [full_name, grade_level, strand, contact_number, parent_email]

    # Handle Password update if requested
    if new_password:
        if len(new_password) < 6:
            conn.close()
            return jsonify({"success": False, "message": "New password must be at least 6 characters long."}), 400
        hashed = hash_user_password(new_password)
        updates.append("password = %s")
        params.append(hashed)

    # Handle PIN update if requested
    if new_pin:
        if len(new_pin) != 4 or not new_pin.isdigit():
            conn.close()
            return jsonify({"success": False, "message": "New PIN must be exactly 4 numeric digits."}), 400
        updates.append("pin = %s")
        params.append(new_pin)

    # Handle Profile Picture upload or removal
    file = request.files.get("profile_pic")
    remove_photo = str(data.get("remove_photo") or "").strip().lower() == "true"
    if file and file.filename and allowed_file(file.filename):
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        ext = file.filename.rsplit(".", 1)[1].lower()
        new_pic_filename = f"student_{student['student_id']}_{int(time.time())}.{ext}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], new_pic_filename)
        file.save(filepath)
        updates.append("profile_pic = %s")
        params.append(new_pic_filename)
    elif remove_photo:
        updates.append("profile_pic = NULL")

    params.append(student["student_id"])
    sql = f"UPDATE students SET {', '.join(updates)} WHERE student_id = %s"
    cursor.execute(sql, tuple(params))
    conn.commit()

    # Re-fetch updated student row
    cursor.execute("SELECT * FROM students WHERE student_id = %s", (student["student_id"],))
    updated_st = cursor.fetchone() or {}
    conn.close()

    # Update session name cache
    session["student_name"] = updated_st.get("full_name")

    return jsonify({
        "success": True,
        "message": "Profile and credentials updated successfully!",
        "student": {
            "student_id": updated_st.get("student_id"),
            "full_name": updated_st.get("full_name"),
            "school_id": updated_st.get("school_id"),
            "grade_level": updated_st.get("grade_level"),
            "strand": updated_st.get("strand"),
            "contact_number": updated_st.get("contact_number"),
            "parent_email": updated_st.get("parent_email"),
            "email": updated_st.get("email"),
            "profile_pic": updated_st.get("profile_pic")
        }
    })


# ---------------- Run App ----------------
if __name__ == "__main__":
    os.makedirs("static/topups", exist_ok=True)
    os.makedirs("static/qrcodes", exist_ok=True)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        t = threading.Thread(target=_start_https_companion_server, daemon=True)
        t.start()
    print("Starting Flask server on http://0.0.0.0:5000 ...")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)


