from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

Base = declarative_base()
_engine = None
_session_factory = None


def _init() -> None:
    """
    
    """
    global _engine, _session_factory
    if _engine is not None:
        return

    db_url = settings.DATABASE_URL
    if "sqlite" in db_url:
        _engine = create_engine(
            db_url, echo=False,
            connect_args={"check_same_thread": False},
        )
    else:
        _engine = create_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=20,
            connect_args={"charset": "utf8mb4"},
        )

    _session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=_engine
    )


def SessionLocal():
    """
    
    """
    _init()
    return _session_factory()


def get_db():
    """
    
    """
    _init()
    db = _session_factory()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """
    
    """
    _init()
    migrations = [
       """ALTER TABLE admin_user
              ADD COLUMN IF NOT EXISTS location
              ENUM('west','east','eastwest') NULL""",

       """ALTER TABLE vehicle
              ADD COLUMN IF NOT EXISTS stnk_exp DATE NULL""",

       """ALTER TABLE member
              ADD COLUMN IF NOT EXISTS registered_plant
              ENUM('west','east','eastwest') NOT NULL DEFAULT 'west'""",
       """ALTER TABLE member
              ADD COLUMN IF NOT EXISTS category
              ENUM('Employee','Vendor','Visitor') NOT NULL DEFAULT 'Employee'""",
       """ALTER TABLE member
              ADD COLUMN IF NOT EXISTS sim_exp DATE NULL""",
       """ALTER TABLE member
              ADD COLUMN IF NOT EXISTS created_at
              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP""",
       """ALTER TABLE member
              ADD COLUMN IF NOT EXISTS updated_at
              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
              ON UPDATE CURRENT_TIMESTAMP""",

       """ALTER TABLE parking_zone
              ADD COLUMN IF NOT EXISTS zone_key
              VARCHAR(50) NOT NULL DEFAULT ''""",
       """ALTER TABLE parking_zone
              ADD COLUMN IF NOT EXISTS employee_capacity INT NOT NULL DEFAULT 0""",
       """ALTER TABLE parking_zone
              ADD COLUMN IF NOT EXISTS vendor_capacity   INT NOT NULL DEFAULT 0""",
       """ALTER TABLE parking_zone
              ADD COLUMN IF NOT EXISTS visitor_capacity  INT NOT NULL DEFAULT 0""",
       """ALTER TABLE parking_zone
              ADD COLUMN IF NOT EXISTS employee_used INT NOT NULL DEFAULT 0""",
       """ALTER TABLE parking_zone
              ADD COLUMN IF NOT EXISTS vendor_used   INT NOT NULL DEFAULT 0""",
       """ALTER TABLE parking_zone
              ADD COLUMN IF NOT EXISTS visitor_used  INT NOT NULL DEFAULT 0""",
       """ALTER TABLE parking_zone
              ADD COLUMN IF NOT EXISTS updated_at
              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
              ON UPDATE CURRENT_TIMESTAMP""",

       """ALTER TABLE parking_slot
              ADD COLUMN IF NOT EXISTS category
              ENUM('Employee','Vendor','Visitor') NOT NULL DEFAULT 'Employee'""",
       """ALTER TABLE parking_slot
              ADD COLUMN IF NOT EXISTS updated_at
              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
              ON UPDATE CURRENT_TIMESTAMP""",

       """ALTER TABLE analytics_data
              ADD COLUMN IF NOT EXISTS predicted_employee INT NOT NULL DEFAULT 0""",
       """ALTER TABLE analytics_data
              ADD COLUMN IF NOT EXISTS predicted_vendor   INT NOT NULL DEFAULT 0""",
       """ALTER TABLE analytics_data
              ADD COLUMN IF NOT EXISTS predicted_visitor  INT NOT NULL DEFAULT 0""",
       """ALTER TABLE analytics_data
              ADD COLUMN IF NOT EXISTS created_at
              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP""",

       """ALTER TABLE entry_exit_log
              ADD COLUMN IF NOT EXISTS zone_id
              BIGINT NOT NULL DEFAULT 1""",
    ]

    with _engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()

    print("[DB] Migrations applied")


def create_tables() -> None:
    """
    
    """
    _init()
    import app.core.models as _  

    Base.metadata.create_all(bind=_engine)
    run_migrations()
    print("Tables ready")


def check_connection() -> bool:
    """
    
    """
    try:
        _init()
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        print(f"Connection failed: {exc}")
        return False
