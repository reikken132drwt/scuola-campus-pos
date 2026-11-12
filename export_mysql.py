import sqlite3

sqlite_conn = sqlite3.connect("school_system_local.db")
cursor = sqlite_conn.cursor()

sql_lines = [
    "-- ========================================================================",
    "-- Scuola Dei Bambini De Sta. Terisita International Montessori School Inc.",
    "-- Campus E-Wallet & Canteen POS System Database Dump",
    "-- Ready for MySQL Workbench / MySQL Server 8.0+",
    "-- ========================================================================",
    "",
    "CREATE DATABASE IF NOT EXISTS school_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
    "USE school_system;",
    "",
    "SET FOREIGN_KEY_CHECKS = 0;",
    "",
]

table_defs = {
    "students": """CREATE TABLE IF NOT EXISTS students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    school_id VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    parent_email VARCHAR(120),
    contact_number VARCHAR(20),
    grade_level VARCHAR(20),
    strand VARCHAR(50),
    guardian_name VARCHAR(100),
    pin VARCHAR(255) DEFAULT '1234',
    password VARCHAR(255) NOT NULL,
    security_q1 VARCHAR(255),
    security_a1 VARCHAR(255),
    security_q2 VARCHAR(255),
    security_a2 VARCHAR(255),
    security_q3 VARCHAR(255),
    security_a3 VARCHAR(255),
    balance DECIMAL(10, 2) DEFAULT 0.00,
    qr_code VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active',
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "admins": """CREATE TABLE IF NOT EXISTS admins (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "staff": """CREATE TABLE IF NOT EXISTS staff (
    staff_id INT AUTO_INCREMENT PRIMARY KEY,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "otps": """CREATE TABLE IF NOT EXISTS otps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(120) NOT NULL,
    otp_code VARCHAR(20) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "topups": """CREATE TABLE IF NOT EXISTS topups (
    topup_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    payment_mode VARCHAR(50) DEFAULT 'gcash',
    method VARCHAR(50),
    gcash_number VARCHAR(30),
    gcash_owner VARCHAR(100),
    amount DECIMAL(10, 2) NOT NULL,
    reference_number VARCHAR(100),
    screenshot_path VARCHAR(255),
    proof_image VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_topups_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "transactions": """CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    staff_id INT,
    admin_id INT,
    customer_name VARCHAR(100),
    amount DECIMAL(10, 2) NOT NULL,
    previous_balance DECIMAL(10, 2),
    new_balance DECIMAL(10, 2),
    status VARCHAR(20) DEFAULT 'completed',
    remarks TEXT,
    type VARCHAR(30) DEFAULT 'purchase',
    payment_mode VARCHAR(30) DEFAULT 'cash',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_transactions_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE SET NULL,
    CONSTRAINT fk_transactions_staff FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL,
    CONSTRAINT fk_transactions_admin FOREIGN KEY (admin_id) REFERENCES admins(admin_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "unregistered_transactions": """CREATE TABLE IF NOT EXISTS unregistered_transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    staff_id INT,
    customer_name VARCHAR(100),
    contact_number VARCHAR(20),
    amount DECIMAL(10, 2),
    payment_mode VARCHAR(30) DEFAULT 'cash',
    qr_code VARCHAR(255),
    status VARCHAR(20) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_unregistered_staff FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "staff_totals": """CREATE TABLE IF NOT EXISTS staff_totals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    staff_id INT,
    amount DECIMAL(10, 2),
    mode VARCHAR(30),
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_staff_totals_staff FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "canteen_products": """CREATE TABLE IF NOT EXISTS canteen_products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255) DEFAULT 'Fresh canteen item',
    category VARCHAR(30) DEFAULT 'Main',
    price DECIMAL(10, 2) NOT NULL,
    image_path VARCHAR(255),
    icon VARCHAR(20) DEFAULT '🍽️',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"""
}

def escape_sql(val):
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"

for tbl, create_sql in table_defs.items():
    sql_lines.append(f"-- Table structure for `{tbl}`")
    sql_lines.append(f"DROP TABLE IF EXISTS `{tbl}`;")
    sql_lines.append(create_sql)
    sql_lines.append("")
    
    rows = cursor.execute(f"SELECT * FROM `{tbl}`").fetchall()
    if rows:
        cols = [d[0] for d in cursor.description]
        col_list = ", ".join([f"`{c}`" for c in cols])
        sql_lines.append(f"-- Dumping data for `{tbl}` ({len(rows)} rows)")
        sql_lines.append(f"INSERT INTO `{tbl}` ({col_list}) VALUES")
        val_rows = []
        for r in rows:
            val_strs = [escape_sql(v) for v in r]
            val_rows.append(f"  ({', '.join(val_strs)})")
        sql_lines.append(",\n".join(val_rows) + ";")
        sql_lines.append("")

sql_lines.append("SET FOREIGN_KEY_CHECKS = 1;")
sql_lines.append("")

output_file = "school_system.sql"
with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(sql_lines))

print("Generated school_system.sql successfully!")
