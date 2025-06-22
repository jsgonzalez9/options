from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from .database import setup, models # Use your existing setup and models

# Create all database tables (if they don't exist)
# This should ideally be run once at startup, not on every import or app creation.
# For a simple app, this is okay here. For production, consider Alembic migrations.
models.Base.metadata.create_all(bind=setup.engine)


app = FastAPI(
    title="Trading Journal API",
    description="API for managing trading positions, journal entries, and analytics.",
    version="0.1.0"
)

# Dependency for getting a DB session
def get_db():
    db = setup.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", tags=["Root"])
async def read_root():
    """
    Root endpoint providing a welcome message.
    """
    return {"message": "Welcome to the Trading Journal API!"}

@app.get("/health", tags=["Health Check"])
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint.
    Verifies database connectivity by trying to execute a simple query.
    """
    try:
        # Try to execute a simple query to check DB connection
        db.execute(models.Position.__table__.select().limit(1)) # Example query
        db_status = "ok"
    except Exception as e:
        # print(f"Health check DB error: {e}") # For debugging
        db_status = "error"

    return {"status": "ok", "database_status": db_status}

# Import and include routers
from .api_routes import portfolio, positions, analytics

app.include_router(positions.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    # This is for running the app directly using `python src/main.py`
    # For production, you would typically use: `uvicorn src.main:app --reload` (for dev)
    # or a process manager like Gunicorn with Uvicorn workers.
    print("Starting Uvicorn server for Trading Journal API...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
