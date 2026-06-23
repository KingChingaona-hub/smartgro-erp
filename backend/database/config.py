# backend/database/config.py
import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from dotenv import load_dotenv
from typing import Generator
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Database configuration with connection pooling"""
    
    def __init__(self):
        # Get database URL from environment
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:password@localhost:5432/smartgro"
        )
        
        # Connection pool settings
        self.pool_size = int(os.getenv("DATABASE_POOL_SIZE", "5"))
        self.max_overflow = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))
        self.pool_timeout = int(os.getenv("DATABASE_POOL_TIMEOUT", "30"))
        self.pool_recycle = int(os.getenv("DATABASE_POOL_RECYCLE", "3600"))
        self.echo = os.getenv("SQL_ECHO", "false").lower() == "true"
        
        self._engine = None
        self._session_factory = None
    
    @property
    def engine(self):
        """Get database engine with connection pooling"""
        if self._engine is None:
            self._engine = create_engine(
                self.database_url,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_timeout=self.pool_timeout,
                pool_recycle=self.pool_recycle,
                pool_pre_ping=True,
                poolclass=QueuePool,
                echo=self.echo
            )
            
            # Add query logging for slow queries
            @event.listens_for(self._engine, "before_cursor_execute")
            def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                conn.info.setdefault("query_start_time", []).append(datetime.utcnow())
            
            @event.listens_for(self._engine, "after_cursor_execute")
            def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                if "query_start_time" in conn.info:
                    total = datetime.utcnow() - conn.info["query_start_time"].pop()
                    if total.total_seconds() > 1.0:
                        logger.warning(f"Slow query ({total.total_seconds():.2f}s): {statement[:100]}...")
            
            logger.info(f"✅ Database engine initialized")
        
        return self._engine
    
    @property
    def session_factory(self):
        """Get session factory"""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
        return self._session_factory
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session with context manager"""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

# Create global instance
db_config = DatabaseConfig()
Base = declarative_base()