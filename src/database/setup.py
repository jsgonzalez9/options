from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base # Import Base from models.py

# Define the database URL. For SQLite, it's a path to the database file.
# Example: "sqlite:///./trading_journal.db" for a file in the current directory.
# For testing, one might use "sqlite:///:memory:"
DATABASE_URL = "sqlite:///./trading_journal.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} # Needed only for SQLite if used with threads (e.g. web apps)
)

# sessionmaker returns a class, SessionLocal is an instance of that class when called
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_db_tables():
    """
    Creates all database tables defined by models inheriting from Base.
    It's important to ensure all model modules are imported before calling this
    so that Base.metadata is populated.
    """
    # In a larger application, you might need to import all your model modules here
    # e.g., from . import models (if all models are defined/imported in models.py)
    # or from .models_user import User, from .models_post import Post etc.
    # For now, assuming all models will be in 'models.py' and Base is imported from there.
    Base.metadata.create_all(bind=engine)
    print(f"Database tables created (or already exist) for {DATABASE_URL}")

def get_db_session():
    """
    Provides a database session.
    Usage:
        db = get_db_session()
        try:
            # ... do database operations ...
            db.commit()
        except:
            db.rollback()
            raise
        finally:
            db.close()

    This is a simple way. For web frameworks like FastAPI, dependency injection is common.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    print(f"Setting up database at {DATABASE_URL}")
    create_db_tables()

    # Example of getting a session
    print("\nAttempting to get a DB session...")
    db_gen = get_db_session()
    try:
        db = next(db_gen)
        print("DB Session acquired.")
        # You can try a simple query if tables/models exist
        # For example, if a User model existed:
        # print(db.query(User).all())
    except Exception as e:
        print(f"Error during session test: {e}")
    finally:
        if 'db' in locals() and db.is_active:
            db.close()
            print("DB Session closed.")
    print("Database setup script finished.")
