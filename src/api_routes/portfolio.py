from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database import setup as db_setup # Renamed to avoid conflict with 'setup' variable
from src.core import portfolio_manager
from src.api_schemas import PortfolioSummary, CashUpdate, PortfolioSettingDisplay

router = APIRouter(
    prefix="/portfolio",
    tags=["Portfolio"],
    responses={404: {"description": "Not found"}},
)

@router.get("/summary", response_model=PortfolioSummary)
def get_portfolio_summary(db: Session = Depends(db_setup.get_db_session)):
    """
    Retrieves a summary of the portfolio including cash balance,
    total market value of open positions, total portfolio value,
    and overall portfolio P&L.
    """
    summary_data = portfolio_manager.get_portfolio_summary_data(db)
    return PortfolioSummary(**summary_data)


@router.post("/cash", response_model=PortfolioSettingDisplay)
def manage_cash_balance(cash_update: CashUpdate, db: Session = Depends(db_setup.get_db_session)):
    """
    Updates the cash balance by adding a deposit or subtracting a withdrawal.
    `amount` should always be positive. `is_deposit` (True/False) determines action.
    """
    try:
        new_balance = portfolio_manager.update_cash_balance(
            db,
            amount_change=cash_update.amount,
            is_deposit=cash_update.is_deposit
        )
        db.commit() # Commit transaction after successful cash update
        return PortfolioSettingDisplay(key=portfolio_manager.CASH_BALANCE_KEY, value=new_balance)
    except ValueError as e:
        db.rollback() # Rollback on error (e.g., overdraw attempt)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        # Log the exception e
        raise HTTPException(status_code=500, detail="An internal server error occurred while updating cash balance.")


@router.get("/cash", response_model=PortfolioSettingDisplay)
def read_cash_balance(db: Session = Depends(db_setup.get_db_session)):
    """
    Retrieves the current cash balance.
    """
    cash = portfolio_manager.get_cash_balance(db)
    return PortfolioSettingDisplay(key=portfolio_manager.CASH_BALANCE_KEY, value=cash)
