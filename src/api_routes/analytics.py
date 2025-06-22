from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.database import setup as db_setup
from src.core import analytics_engine
from src.api_schemas import AnalyticsReport

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
    responses={404: {"description": "Not found"}}, # Though less likely for a summary endpoint
)

@router.get("/summary", response_model=AnalyticsReport)
def get_analytics_summary(db: Session = Depends(db_setup.get_db_session)):
    """
    Retrieves a summary of trading performance analytics,
    such as win rate, average P&L, and profit factor,
    based on closed positions.
    """
    summary_data_dict = analytics_engine.get_performance_summary(db)
    # The analytics_engine.get_performance_summary already returns a dict
    # that should match the AnalyticsReport schema.
    return AnalyticsReport(**summary_data_dict)
