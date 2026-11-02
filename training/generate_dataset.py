import json
import random

SYSTEM_PROMPT = (
    "You are sql-doctor, an expert Database Administrator and SQL performance engineer. "
    "Analyze the query and provide: 1) Diagnosis, 2) Optimized Query, and 3) Recommended Index."
)

# Column type definitions
COLUMN_TYPES = [
    "BIGINT", "INTEGER", "VARCHAR", "TEXT", "NUMERIC", "BOOLEAN",
    "TIMESTAMP", "DATE", "JSONB"
]

# Table name prefixes
TABLE_PREFIXES = [
    "users", "orders", "products", "customers", "transactions",
    "payments", "invoices", "audit_logs", "events", "sessions",
    "accounts", "profiles", "items", "categories", "reviews"
]

# Column name patterns
COLUMN_PATTERNS = {
    "id": ["id", "user_id", "customer_id", "order_id", "product_id", "account_id"],
    "text": ["name", "email", "username", "title", "description", "status", "category"],
    "numeric": ["amount", "price", "balance", "total", "quantity", "score", "rating"],
    "timestamp": ["created_at", "updated_at", "order_date", "processed_at", "due_date"],
    "boolean": ["is_active", "is_verified", "is_published", "is_available", "is_deleted"]
}

TEMPLATES = [
    {
        "table": "users",
        "schema": "users (id BIGINT, email VARCHAR, first_name VARCHAR, last_name VARCHAR, status VARCHAR, created_at TIMESTAMP)",
        "slow_query": "SELECT * FROM users WHERE status = 'active' AND email LIKE 'john%' ORDER BY created_at DESC;",
        "diagnosis": "1. `SELECT *` retrieves all columns, preventing index-only scans.\n2. Filtering on `status` and `email` without a composite index requires filtering rows in memory.",
        "optimized_query": "SELECT id, email, first_name, last_name FROM users WHERE status = 'active' AND email LIKE 'john%' ORDER BY created_at DESC;",
        "index": "CREATE INDEX CONCURRENTLY idx_users_status_email_created ON users (status, email, created_at DESC);"
    },
    {
        "table": "orders",
        "schema": "orders (id BIGINT, user_id BIGINT, total NUMERIC, status VARCHAR, order_date DATE)",
        "slow_query": "SELECT * FROM orders WHERE YEAR(order_date) = 2024;",
        "diagnosis": "Wrapping the indexed column `order_date` in the function `YEAR()` invalidates B-Tree index range scans, forcing a full table scan.",
        "optimized_query": "SELECT id, user_id, total, status, order_date FROM orders WHERE order_date >= '2024-01-01' AND order_date < '2025-01-01';",
        "index": "CREATE INDEX CONCURRENTLY idx_orders_order_date ON orders (order_date);"
    },
    {
        "table": "payments",
        "schema": "payments (id BIGINT, order_id BIGINT, amount NUMERIC, payment_method VARCHAR, status VARCHAR, processed_at TIMESTAMP)",
        "slow_query": "SELECT * FROM payments WHERE payment_method = 'credit_card' AND status = 'settled';",
        "diagnosis": "Filtering across two columns (`payment_method`, `status`) without a composite index forces a sequential scan or expensive bitmap index merge.",
        "optimized_query": "SELECT id, order_id, amount, processed_at FROM payments WHERE payment_method = 'credit_card' AND status = 'settled';",
        "index": "CREATE INDEX CONCURRENTLY idx_payments_method_status ON payments (payment_method, status);"
    },
    {
        "table": "products",
        "schema": "products (id BIGINT, category_id INT, name VARCHAR, price NUMERIC, is_available BOOLEAN)",
        "slow_query": "SELECT * FROM products WHERE is_available = true AND category_id = 5 ORDER BY price ASC;",
        "diagnosis": "1. `SELECT *` reads unnecessary columns from disk.\n2. Missing composite index on `(category_id, is_available, price)` prevents an indexed lookup and requires an expensive sort in memory.",
        "optimized_query": "SELECT id, name, price FROM products WHERE category_id = 5 AND is_available = true ORDER BY price ASC;",
        "index": "CREATE INDEX CONCURRENTLY idx_products_cat_avail_price ON products (category_id, is_available, price ASC);"
    },
    {
        "table": "audit_logs",
        "schema": "audit_logs (id BIGINT, action VARCHAR, entity_type VARCHAR, entity_id BIGINT, created_at TIMESTAMP)",
        "slow_query": "SELECT * FROM audit_logs WHERE action LIKE '%login_failed%' ORDER BY created_at DESC LIMIT 50;",
        "diagnosis": "1. `LIKE '%pattern%'` with a leading wildcard cannot use a standard B-Tree index, forcing a full sequential scan.\n2. High I/O overhead reading wide log columns.",
        "optimized_query": "SELECT id, action, entity_id, created_at FROM audit_logs WHERE action LIKE '%login_failed%' ORDER BY created_at DESC LIMIT 50;",
        "index": "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE INDEX CONCURRENTLY idx_audit_logs_action_gin ON audit_logs USING gin (action gin_trgm_ops);"
    },
    {
        "table": "customers",
        "schema": "customers (id BIGINT, country_code VARCHAR, account_status VARCHAR, balance NUMERIC, updated_at TIMESTAMP)",
        "slow_query": "SELECT id, country_code, balance FROM customers WHERE country_code = 'US' AND account_status = 'delinquent' ORDER BY balance DESC LIMIT 100;",
        "diagnosis": "Missing a composite index on filter columns (`country_code`, `account_status`) and sorting column (`balance`). Database must sort matches in a temporary memory buffer (work_mem).",
        "optimized_query": "SELECT id, country_code, balance FROM customers WHERE country_code = 'US' AND account_status = 'delinquent' ORDER BY balance DESC LIMIT 100;",
        "index": "CREATE INDEX CONCURRENTLY idx_customers_status_balance ON customers (country_code, account_status, balance DESC);"
    },
    {
        "table": "invoices",
        "schema": "invoices (id BIGINT, customer_id BIGINT, status VARCHAR, amount NUMERIC, due_date DATE)",
        "slow_query": "SELECT * FROM invoices WHERE customer_id IN (SELECT id FROM customers WHERE account_status = 'suspended');",
        "diagnosis": "Using an un-indexed `IN (SELECT ...)` subquery can cause the query engine to execute sub-optimal sub-plans for each outer row.",
        "optimized_query": "SELECT i.id, i.customer_id, i.status, i.amount, i.due_date FROM invoices i JOIN customers c ON i.customer_id = c.id WHERE c.account_status = 'suspended';",
        "index": "CREATE INDEX CONCURRENTLY idx_invoices_customer_id ON invoices (customer_id);"
    }
]

def generate_random_table_schema() -> dict:
    """Generate a random table schema with columns."""
    table_name = random.choice(TABLE_PREFIXES) + "_" + str(random.randint(1, 999))
    
    columns = []
    columns.append(("id", "BIGINT"))
    
    num_columns = random.randint(4, 8)
    for _ in range(num_columns):
        col_type = random.choice(COLUMN_TYPES)
        if col_type == "VARCHAR":
            col_type = f"VARCHAR({random.randint(50, 255)})"
        
        if random.random() < 0.3:
            col_category = random.choice(list(COLUMN_PATTERNS.keys()))
            col_name = random.choice(COLUMN_PATTERNS[col_category])
        else:
            col_name = f"col_{random.randint(1, 100)}"
        
        columns.append((col_name, col_type))
    
    schema_str = ", ".join([f"{name} {dtype}" for name, dtype in columns])
    return {
        "table": table_name,
        "schema": f"{table_name} ({schema_str})",
        "columns": columns
    }

def anti_pattern_select_star(schema: dict) -> dict:
    """Generate SELECT * with missing index."""
    table = schema["table"]
    columns = schema["columns"]
    
    # Pick 2 filter columns
    filterable_cols = [col for col in columns if col[0] != "id" and col[1] in ["VARCHAR", "TEXT", "BOOLEAN"]]
    if len(filterable_cols) < 2:
        # Fallback: use any non-id columns
        filterable_cols = [col for col in columns if col[0] != "id"]
    
    filter_cols = random.choice(filterable_cols)
    filter_col2 = random.choice([col for col in filterable_cols if col[0] != filter_cols[0]])
    
    slow_query = f"SELECT * FROM {table} WHERE {filter_cols[0]} = 'value' AND {filter_col2[0]} = 'value2';"
    
    # Select specific columns
    select_cols = [col[0] for col in columns[:4]]
    optimized_query = f"SELECT {', '.join(select_cols)} FROM {table} WHERE {filter_cols[0]} = 'value' AND {filter_col2[0]} = 'value2';"
    
    diagnosis = f"1. `SELECT *` retrieves all columns, preventing index-only scans.\n2. Filtering on `{filter_cols[0]}` and `{filter_col2[0]}` without a composite index requires filtering rows in memory."
    
    index = f"CREATE INDEX CONCURRENTLY idx_{table}_{filter_cols[0]}_{filter_col2[0]} ON {table} ({filter_cols[0]}, {filter_col2[0]});"
    
    return {
        "table": table,
        "schema": schema["schema"],
        "slow_query": slow_query,
        "diagnosis": diagnosis,
        "optimized_query": optimized_query,
        "index": index
    }

def anti_pattern_function_wrap(schema: dict) -> dict:
    """Generate query with function-wrapped column."""
    table = schema["table"]
    columns = schema["columns"]
    
    # Find a timestamp/date column
    date_col = None
    for col in columns:
        if "date" in col[0].lower() or col[1] in ["TIMESTAMP", "DATE"]:
            date_col = col
            break
    
    if not date_col:
        date_col = ("created_at", "TIMESTAMP")
    
    year = random.randint(2020, 2025)
    slow_query = f"SELECT * FROM {table} WHERE YEAR({date_col[0]}) = {year};"
    
    optimized_query = f"SELECT * FROM {table} WHERE {date_col[0]} >= '{year}-01-01' AND {date_col[0]} < '{year + 1}-01-01';"
    
    diagnosis = f"Wrapping the indexed column `{date_col[0]}` in the function `YEAR()` invalidates B-Tree index range scans, forcing a full table scan."
    
    index = f"CREATE INDEX CONCURRENTLY idx_{table}_{date_col[0]} ON {table} ({date_col[0]});"
    
    return {
        "table": table,
        "schema": schema["schema"],
        "slow_query": slow_query,
        "diagnosis": diagnosis,
        "optimized_query": optimized_query,
        "index": index
    }

def anti_pattern_like_leading_wildcard(schema: dict) -> dict:
    """Generate query with leading wildcard in LIKE."""
    table = schema["table"]
    columns = schema["columns"]
    
    # Find a text column
    text_col = None
    for col in columns:
        if col[1] in ["VARCHAR", "TEXT"]:
            text_col = col
            break
    
    if not text_col:
        text_col = ("name", "VARCHAR")
    
    pattern = random.choice(["error", "failed", "pending", "active"])
    slow_query = f"SELECT * FROM {table} WHERE {text_col[0]} LIKE '%{pattern}%' ORDER BY id DESC LIMIT 50;"
    
    select_cols = [col[0] for col in columns[:3]]
    optimized_query = f"SELECT {', '.join(select_cols)} FROM {table} WHERE {text_col[0]} LIKE '%{pattern}%' ORDER BY id DESC LIMIT 50;"
    
    diagnosis = f"1. `LIKE '%pattern%'` with a leading wildcard cannot use a standard B-Tree index, forcing a full sequential scan.\n2. High I/O overhead reading wide columns."
    
    index = f"CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE INDEX CONCURRENTLY idx_{table}_{text_col[0]}_gin ON {table} USING gin ({text_col[0]} gin_trgm_ops);"
    
    return {
        "table": table,
        "schema": schema["schema"],
        "slow_query": slow_query,
        "diagnosis": diagnosis,
        "optimized_query": optimized_query,
        "index": index
    }

def anti_pattern_missing_sort_index(schema: dict) -> dict:
    """Generate query with ORDER BY without proper index."""
    table = schema["table"]
    columns = schema["columns"]
    
    # Find filter and sort columns
    filterable_cols = [col for col in columns if col[1] in ["VARCHAR", "BOOLEAN"]]
    if not filterable_cols:
        filterable_cols = [col for col in columns if col[0] != "id"]
    filter_col = random.choice(filterable_cols)
    
    sortable_cols = [col for col in columns if col[1] in ["NUMERIC", "TIMESTAMP", "DATE", "BIGINT"]]
    if not sortable_cols:
        sortable_cols = [col for col in columns if col[0] != filter_col[0]]
    sort_col = random.choice(sortable_cols)
    
    direction = random.choice(["ASC", "DESC"])
    slow_query = f"SELECT * FROM {table} WHERE {filter_col[0]} = 'value' ORDER BY {sort_col[0]} {direction} LIMIT 100;"
    
    select_cols = [col[0] for col in columns[:4]]
    optimized_query = f"SELECT {', '.join(select_cols)} FROM {table} WHERE {filter_col[0]} = 'value' ORDER BY {sort_col[0]} {direction} LIMIT 100;"
    
    diagnosis = f"Missing a composite index on filter column (`{filter_col[0]}`) and sorting column (`{sort_col[0]}`). Database must sort matches in a temporary memory buffer."
    
    index = f"CREATE INDEX CONCURRENTLY idx_{table}_{filter_col[0]}_{sort_col[0]} ON {table} ({filter_col[0]}, {sort_col[0]} {direction});"
    
    return {
        "table": table,
        "schema": schema["schema"],
        "slow_query": slow_query,
        "diagnosis": diagnosis,
        "optimized_query": optimized_query,
        "index": index
    }

def anti_pattern_subquery(schema: dict) -> dict:
    """Generate query with un-optimized subquery."""
    table = schema["table"]
    columns = schema["columns"]
    
    # Create a second table reference
    ref_table = random.choice(TABLE_PREFIXES)
    id_col = [col for col in columns if col[0] == "id"][0]
    fk_col = f"{ref_table}_id"
    
    slow_query = f"SELECT * FROM {table} WHERE {fk_col} IN (SELECT id FROM {ref_table} WHERE status = 'active');"
    
    optimized_query = f"SELECT t.* FROM {table} t JOIN {ref_table} r ON t.{fk_col} = r.id WHERE r.status = 'active';"
    
    diagnosis = f"Using an un-indexed `IN (SELECT ...)` subquery can cause the query engine to execute sub-optimal sub-plans for each outer row."
    
    index = f"CREATE INDEX CONCURRENTLY idx_{table}_{fk_col} ON {table} ({fk_col});"
    
    return {
        "table": table,
        "schema": schema["schema"],
        "slow_query": slow_query,
        "diagnosis": diagnosis,
        "optimized_query": optimized_query,
        "index": index
    }

def generate_dynamic_sample() -> dict:
    """Generate a single dynamic SQL problem sample."""
    schema = generate_random_table_schema()
    
    anti_patterns = [
        anti_pattern_select_star,
        anti_pattern_function_wrap,
        anti_pattern_like_leading_wildcard,
        anti_pattern_missing_sort_index,
        anti_pattern_subquery
    ]
    
    anti_pattern = random.choice(anti_patterns)
    item = anti_pattern(schema)
    
    user_content = f"Query: {item['slow_query']}\nSchema: {item['schema']}"
    assistant_content = (
        f"### Diagnosis\n{item['diagnosis']}\n\n"
        f"### Optimized Query\n```sql\n{item['optimized_query']}\n```\n\n"
        f"### Recommended Index\n```sql\n{item['index']}\n```"
    )
    
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content}
        ]
    }

def generate_samples(count: int = 350, use_dynamic: bool = False) -> list[dict]:
    dataset = []
    for _ in range(count):
        if use_dynamic:
            sample = generate_dynamic_sample()
        else:
            item = random.choice(TEMPLATES)

            user_content = f"Query: {item['slow_query']}\nSchema: {item['schema']}"
            assistant_content = (
                f"### Diagnosis\n{item['diagnosis']}\n\n"
                f"### Optimized Query\n```sql\n{item['optimized_query']}\n```\n\n"
                f"### Recommended Index\n```sql\n{item['index']}\n```"
            )

            sample = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": assistant_content}
                ]
            }
        dataset.append(sample)
    return dataset

def main():
    # Generate new dynamic samples
    train_samples = generate_samples(count=200, use_dynamic=True)
    valid_samples = generate_samples(count=50, use_dynamic=True)

    # Append to existing files
    with open("/Users/kartikraktate/PythonProject/sql-doctor/training/train.jsonl", "a") as f:
        for row in train_samples:
            f.write(json.dumps(row) + "\n")

    with open("/Users/kartikraktate/PythonProject/sql-doctor/training/valid.jsonl", "a") as f:
        for row in valid_samples:
            f.write(json.dumps(row) + "\n")

    print(f"Appended {len(train_samples)} new dynamic training samples -> training/train.jsonl")
    print(f"Appended {len(valid_samples)} new dynamic validation samples -> training/valid.jsonl")

if __name__ == "__main__":
    main()
