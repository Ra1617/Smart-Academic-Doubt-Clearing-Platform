from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)




class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_schema_compat():
    """
    Backfill missing columns in legacy Supabase schemas so auth/profile flows work.
    This is intentionally additive and does not drop or rewrite existing columns.
    """
    statements = [
        # UUID generation for new profile IDs when legacy tables lacked an id column.
        "CREATE EXTENSION IF NOT EXISTS pgcrypto;",
        # users
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);",
        # students
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS id UUID;",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS full_name VARCHAR(255);",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS roll_number VARCHAR(50);",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS department VARCHAR(100);",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS phone VARCHAR(20);",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;",
        # teachers
        "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS id UUID;",
        "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS full_name VARCHAR(255);",
        "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS department VARCHAR(100);",
        "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS subjects JSON;",
        "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS phone VARCHAR(20);",
        "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;",
        # admins
        "ALTER TABLE admins ADD COLUMN IF NOT EXISTS id UUID;",
        "ALTER TABLE admins ADD COLUMN IF NOT EXISTS full_name VARCHAR(255);",
        "ALTER TABLE admins ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;",
        # Fill missing IDs for existing rows.
        "UPDATE students SET id = gen_random_uuid() WHERE id IS NULL;",
        "UPDATE teachers SET id = gen_random_uuid() WHERE id IS NULL;",
        "UPDATE admins SET id = gen_random_uuid() WHERE id IS NULL;",
        # Sensible defaults for new rows.
        "ALTER TABLE students ALTER COLUMN id SET DEFAULT gen_random_uuid();",
        "ALTER TABLE teachers ALTER COLUMN id SET DEFAULT gen_random_uuid();",
        "ALTER TABLE admins ALTER COLUMN id SET DEFAULT gen_random_uuid();",
    ]

    try:
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
    except Exception as e:
        # Do not prevent app boot; log and continue.
        print(f"[schema compat init] {e}")


def init_pgvector(db):
    """Ensure pgvector extension and embedding column exist."""
    try:
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        db.execute(text("""
            ALTER TABLE doubts
            ADD COLUMN IF NOT EXISTS embedding vector(1024);
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_doubts_embedding
            ON doubts USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[pgvector init] {e}")
