from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define the location of the SQLite database file.
# It will be created in the root directory of the project.
SQLALCHEMY_DATABASE_URL = "sqlite:///./crawler.db"

# Create the SQLAlchemy engine.
# The 'check_same_thread' argument is needed for SQLite.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Create a SessionLocal class. Each instance of a SessionLocal
# will be a new database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class. Our database models will inherit from this class.
Base = declarative_base()
