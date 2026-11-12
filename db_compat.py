import os
import re
import sqlite3
import datetime
from decimal import Decimal

# Ensure PyMySQL Connection.cursor accepts cursorclass= keyword argument
try:
    import pymysql
    import pymysql.connections
    _orig_pymysql_cursor = pymysql.connections.Connection.cursor
    def _compat_pymysql_cursor(self, cursor=None, cursorclass=None, **kwargs):
        c = cursor if cursor is not None else cursorclass
        if c is not None:
            return _orig_pymysql_cursor(self, cursor=c, **kwargs)
        return _orig_pymysql_cursor(self, **kwargs)
    pymysql.connections.Connection.cursor = _compat_pymysql_cursor
except Exception:
    pass


class DictCursorMarker:
    """Marker class for DictCursor compatibility when MySQLdb is not installed."""
    pass


class SQLiteCompatCursor:
    def __init__(self, sqlite_conn, is_dict=False):
        self._conn = sqlite_conn
        self._cursor = sqlite_conn.cursor()
        self._is_dict = is_dict
        self._last_rows = []
        self._idx = 0

    def _translate_query(self, query):
        q = query
        # Translate MySQL %s placeholders to SQLite ?
        q = q.replace("%s", "?")
        # Translate DEFAULT CURRENT_TIMESTAMP / DEFAULT CURRENT_DATE with required parens in SQLite DDL
        q = re.sub(r"\bDEFAULT\s+CURRENT_TIMESTAMP\b", "DEFAULT (datetime('now', 'localtime'))", q, flags=re.IGNORECASE)
        q = re.sub(r"\bDEFAULT\s+CURRENT_DATE\b", "DEFAULT (date('now', 'localtime'))", q, flags=re.IGNORECASE)
        # Translate MySQL NOW() and CURDATE()
        q = re.sub(r"\bNOW\(\)", "datetime('now', 'localtime')", q, flags=re.IGNORECASE)
        q = re.sub(r"\bCURDATE\(\)", "date('now', 'localtime')", q, flags=re.IGNORECASE)
        q = re.sub(r"\bCURRENT_DATE\b", "date('now', 'localtime')", q, flags=re.IGNORECASE)
        q = re.sub(r"\bCURRENT_TIMESTAMP\b", "datetime('now', 'localtime')", q, flags=re.IGNORECASE)
        q = re.sub(r"\bCURRENT_TIME\b", "time('now', 'localtime')", q, flags=re.IGNORECASE)
        q = re.sub(
            r"DATEDIFF\(\s*date\('now',\s*'localtime'\)\s*,\s*last_active\s*\)",
            "CAST(julianday('now', 'localtime') - julianday(COALESCE(last_active, datetime('now', 'localtime'))) AS INTEGER)",
            q,
            flags=re.IGNORECASE,
        )
        # Translate MySQL INT AUTO_INCREMENT PRIMARY KEY to SQLite
        q = re.sub(r"\bINT\s+AUTO_INCREMENT\s+PRIMARY\s+KEY\b", "INTEGER PRIMARY KEY AUTOINCREMENT", q, flags=re.IGNORECASE)
        q = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "INTEGER PRIMARY KEY AUTOINCREMENT", q, flags=re.IGNORECASE)
        return q

    def _convert_params(self, params):
        if params is None:
            return ()
        converted = []
        for p in params:
            if isinstance(p, Decimal):
                converted.append(float(p))
            elif isinstance(p, datetime.datetime):
                converted.append(p.strftime("%Y-%m-%d %H:%M:%S"))
            elif isinstance(p, datetime.date):
                converted.append(p.strftime("%Y-%m-%d"))
            else:
                converted.append(p)
        return tuple(converted)

    def _enrich_value(self, col_name, val):
        if val is None:
            return None
        if col_name in ("date",) and isinstance(val, str):
            try:
                return datetime.datetime.strptime(val[:10], "%Y-%m-%d").date()
            except Exception:
                return val
        if col_name in ("expires_at", "created_at") and isinstance(val, str):
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.datetime.strptime(val, fmt)
                except Exception:
                    pass
        if col_name in ("balance", "amount", "previous_balance", "new_balance") and isinstance(val, (int, float)):
            return Decimal(str(round(val, 2)))
        return val

    def execute(self, query, params=None):
        # Handle information_schema query for /db_structure
        if "information_schema.columns" in query.lower():
            self._last_rows = []
            tables = self._cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            for (tname,) in tables:
                cols = self._cursor.execute(f"PRAGMA table_info({tname})").fetchall()
                for c in cols:
                    row_dict = {
                        "TABLE_NAME": tname,
                        "COLUMN_NAME": c[1],
                        "COLUMN_TYPE": c[2],
                        "IS_NULLABLE": "NO" if c[3] else "YES",
                        "COLUMN_DEFAULT": c[4],
                        "COLUMN_KEY": "PRI" if c[5] else "",
                        "EXTRA": "auto_increment" if c[5] else "",
                    }
                    self._last_rows.append(row_dict if self._is_dict else tuple(row_dict.values()))
            self._idx = 0
            return

        sql = self._translate_query(query)
        conv_params = self._convert_params(params)
        self._cursor.execute(sql, conv_params)

        if self._cursor.description:
            col_names = [d[0] for d in self._cursor.description]
            raw_rows = self._cursor.fetchall()
            self._last_rows = []
            for r in raw_rows:
                enriched = [self._enrich_value(col_names[i], r[i]) for i in range(len(col_names))]
                if self._is_dict:
                    self._last_rows.append(dict(zip(col_names, enriched)))
                else:
                    self._last_rows.append(tuple(enriched))
        else:
            self._last_rows = []
        self._idx = 0

    def fetchone(self):
        if self._idx < len(self._last_rows):
            row = self._last_rows[self._idx]
            self._idx += 1
            return row
        return None

    def fetchall(self):
        rows = self._last_rows[self._idx :]
        self._idx = len(self._last_rows)
        return rows

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)

    @property
    def rowcount(self):
        return getattr(self._cursor, "rowcount", -1)

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass


class SQLiteCompatConnection:
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)

    def cursor(self, cursorclass=None, dictionary=False):
        is_dict = bool(dictionary or cursorclass is not None)
        return SQLiteCompatCursor(self._conn, is_dict=is_dict)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


def init_sqlite_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_id VARCHAR(50) UNIQUE NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            parent_email VARCHAR(120),
            contact_number VARCHAR(20),
            strand VARCHAR(50),
            guardian_name VARCHAR(100),
            grade_level VARCHAR(20),
            password VARCHAR(255) NOT NULL,
            pin VARCHAR(10) DEFAULT '1234',
            security_q1 VARCHAR(255),
            security_a1 VARCHAR(255),
            security_q2 VARCHAR(255),
            security_a2 VARCHAR(255),
            security_q3 VARCHAR(255),
            security_a3 VARCHAR(255),
            balance NUMERIC(10, 2) DEFAULT 0.00,
            qr_code VARCHAR(255),
            profile_pic VARCHAR(255),
            status VARCHAR(20) DEFAULT 'active',
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name VARCHAR(100) NOT NULL,
            contact_number VARCHAR(20),
            email VARCHAR(120) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            security_q1 VARCHAR(255),
            security_a1 VARCHAR(255),
            security_q2 VARCHAR(255),
            security_a2 VARCHAR(255),
            security_q3 VARCHAR(255),
            security_a3 VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS staff (
            staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name VARCHAR(100) NOT NULL,
            contact_number VARCHAR(20),
            email VARCHAR(120) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            staff_qr VARCHAR(255),
            security_q1 VARCHAR(255),
            security_a1 VARCHAR(255),
            security_q2 VARCHAR(255),
            security_a2 VARCHAR(255),
            security_q3 VARCHAR(255),
            security_a3 VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(120) NOT NULL,
            otp_code VARCHAR(20) NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS topups (
            topup_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            payment_mode VARCHAR(50) DEFAULT 'gcash',
            method VARCHAR(50),
            gcash_number VARCHAR(30),
            gcash_owner VARCHAR(100),
            amount NUMERIC(10, 2) NOT NULL,
            reference_number VARCHAR(100),
            screenshot_path VARCHAR(255),
            proof_image VARCHAR(255),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            staff_id INTEGER,
            admin_id INTEGER,
            customer_name VARCHAR(100),
            amount NUMERIC(10, 2) NOT NULL,
            previous_balance NUMERIC(10, 2),
            new_balance NUMERIC(10, 2),
            status VARCHAR(20) DEFAULT 'completed',
            remarks TEXT,
            type VARCHAR(30) DEFAULT 'purchase',
            payment_mode VARCHAR(30) DEFAULT 'cash',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS unregistered_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER,
            customer_name VARCHAR(100),
            contact_number VARCHAR(20),
            amount NUMERIC(10, 2),
            payment_mode VARCHAR(30) DEFAULT 'cash',
            qr_code VARCHAR(255),
            status VARCHAR(20) DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS staff_totals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER,
            amount NUMERIC(10, 2),
            mode VARCHAR(30),
            category VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS canteen_products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            description VARCHAR(255) DEFAULT 'Fresh canteen item',
            category VARCHAR(30) DEFAULT 'Main',
            price NUMERIC(10, 2) NOT NULL,
            image_path VARCHAR(255),
            icon VARCHAR(20) DEFAULT '🍽️',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()


_MYSQL_SCHEMA_CHECKED = False


def ensure_mysql_schema(conn):
    """Ensure otps table exists and password columns are wide enough in MySQL."""
    global _MYSQL_SCHEMA_CHECKED
    if _MYSQL_SCHEMA_CHECKED:
        return
    _MYSQL_SCHEMA_CHECKED = True
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS otps (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(120) NOT NULL,
                otp_code VARCHAR(20) NOT NULL,
                expires_at DATETIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS canteen_products (
                product_id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description VARCHAR(255) DEFAULT 'Fresh canteen item',
                category VARCHAR(30) DEFAULT 'Main',
                price NUMERIC(10, 2) NOT NULL,
                image_path VARCHAR(255),
                icon VARCHAR(20) DEFAULT '🍽️',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for tbl in ("students", "admins", "staff"):
            try:
                cur.execute(f"ALTER TABLE {tbl} MODIFY COLUMN password VARCHAR(255) NOT NULL")
            except Exception:
                pass
        try:
            cur.execute("ALTER TABLE students ADD COLUMN profile_pic VARCHAR(255) DEFAULT NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE canteen_products ADD COLUMN stock INT DEFAULT 0")
        except Exception:
            pass
        conn.commit()
        cur.close()
    except Exception:
        pass
