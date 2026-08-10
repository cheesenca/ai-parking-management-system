import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None

Base = declarative_base()

def _init() -> None:
    """
    Initialize database engine and session factory
    """
    global _engine, _session_factory
    if _engine is not None:
        return
    
    db_url = settings.DATABASE_URL
    if "sqlite" in db_url:
        _engine = create_engine(
            db_url, 
            echo=False,
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

    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    logger.info("Database engine initialized (%s)", "sqlite" if "sqlite" in db_url else "mysql")


def SessionLocal():
    """
    Create and return one database session object
    """
    _init()
    return _session_factory()


def get_db():
    """
    Provide and manage secure database sessions for each request
    """
    _init()
    db = _session_factory()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """
    Run a manual database migration
    """
    _init()
    migrations = [
        # Admin User
        "ALTER TABLE admin_user ADD COLUMN IF NOT EXISTS location ENUM('west','east','eastwest') NULL",

        # Vehicle
        "ALTER TABLE vehicle ADD COLUMN IF NOT EXISTS stnk_exp DATE NULL",

        # Member
        "ALTER TABLE member ADD COLUMN IF NOT EXISTS registered_plant ENUM('west','east','eastwest') NOT NULL DEFAULT 'west'",
        "ALTER TABLE member ADD COLUMN IF NOT EXISTS category ENUM('Employee','Vendor','Visitor') NOT NULL DEFAULT 'Employee'",
        "ALTER TABLE member ADD COLUMN IF NOT EXISTS sim_exp DATE NULL",
        "ALTER TABLE member ADD COLUMN IF NOT EXISTS location VARCHAR(255) NULL",
        "ALTER TABLE member ADD COLUMN IF NOT EXISTS created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE member ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",

        # Parking Zone
        "ALTER TABLE parking_zone ADD COLUMN IF NOT EXISTS zone_key VARCHAR(50) NOT NULL DEFAULT ''",
        "ALTER TABLE parking_zone ADD COLUMN IF NOT EXISTS employee_capacity INT NOT NULL DEFAULT 0",
        "ALTER TABLE parking_zone ADD COLUMN IF NOT EXISTS vendor_capacity INT NOT NULL DEFAULT 0",
        "ALTER TABLE parking_zone ADD COLUMN IF NOT EXISTS visitor_capacity INT NOT NULL DEFAULT 0",
        "ALTER TABLE parking_zone ADD COLUMN IF NOT EXISTS employee_used INT NOT NULL DEFAULT 0",
        "ALTER TABLE parking_zone ADD COLUMN IF NOT EXISTS vendor_used INT NOT NULL DEFAULT 0",
        "ALTER TABLE parking_zone ADD COLUMN IF NOT EXISTS visitor_used INT NOT NULL DEFAULT 0",
        "ALTER TABLE parking_zone ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",

        # Parking Slot
        "ALTER TABLE parking_slot ADD COLUMN IF NOT EXISTS current_status ENUM('Available','Occupied') NOT NULL DEFAULT 'Available'",
        "ALTER TABLE parking_slot ADD COLUMN IF NOT EXISTS category ENUM('Employee','Vendor','Visitor') NOT NULL DEFAULT 'Employee'",
        "ALTER TABLE parking_slot ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",

        # Analytics Data
        "ALTER TABLE analytics_data ADD COLUMN IF NOT EXISTS peak_hour_start TIME NOT NULL", 
        "ALTER TABLE analytics_data ADD COLUMN IF NOT EXISTS predicted_employee INT NOT NULL DEFAULT 0",
        "ALTER TABLE analytics_data ADD COLUMN IF NOT EXISTS predicted_vendor INT NOT NULL DEFAULT 0",
        "ALTER TABLE analytics_data ADD COLUMN IF NOT EXISTS predicted_visitor INT NOT NULL DEFAULT 0",
        "ALTER TABLE analytics_data ADD COLUMN IF NOT EXISTS created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",

        "ALTER TABLE analytics_data ADD COLUMN IF NOT EXISTS period_type VARCHAR(10) NOT NULL DEFAULT 'daily'",
        "ALTER TABLE analytics_data ADD COLUMN IF NOT EXISTS area_code VARCHAR(10) NULL",
        "ALTER TABLE analytics_data ADD COLUMN IF NOT EXISTS period_label VARCHAR(20) NULL",
        "ALTER TABLE analytics_data ADD COLUMN IF NOT EXISTS predicted_available INT NULL",
        "ALTER TABLE analytics_data ADD COLUMN IF NOT EXISTS status VARCHAR(10) NULL DEFAULT 'Normal'",

        "ALTER TABLE analytics_data DROP INDEX uq_analytics_zone_date",
        "ALTER TABLE analytics_data ADD UNIQUE KEY uq_analytics_zone_date_area (zone_id, record_date, period_type, area_code)",

        # Entry Exit Log
        "ALTER TABLE entry_exit_log ADD COLUMN IF NOT EXISTS zone_id BIGINT NOT NULL DEFAULT 1",
    ]
    with _engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as exc:
                conn.rollback()
                logger.debug("Migration skipped/failed: %s (%s)", sql, exc)
    logger.info("Database migrations applied successfully")


def create_tables() -> None:
    """
    Create the table structure
    """
    _init()
    import app.core.models as _  

    Base.metadata.create_all(bind=_engine)
    run_migrations()
    logger.info("Tables and verification checks initialized")


def check_connection() -> bool:
    """
    Check whether the application successfully connected to the database
    """
    try:
        _init()
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database connection check failed: %s", exc)
        return False
    