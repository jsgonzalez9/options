from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any # Added Any
import datetime

from src.database import setup as db_setup, crud, models
from src.api_schemas import (
    PositionCreate, PositionDisplay, OptionLegDisplay, PositionBase,
    LegPricesUpdate, PositionDetailDisplay, NotesUpdate
)
from src.core import derivatives_calculator, csv_importer
from src.api.alpha_vantage import AlphaVantageAPI

router = APIRouter(
    prefix="/positions",
    tags=["Positions"],
    responses={404: {"description": "Position or related resource not found"}},
)

# Dependency for AlphaVantageAPI client
def get_price_fetcher():
    return AlphaVantageAPI()

def _prepare_position_display(db_position: models.Position, calculated_delta: Optional[float] = None) -> PositionDetailDisplay:
    """Helper to convert ORM Position to Pydantic PositionDetailDisplay including DTE and delta."""

    display_legs = []
    if db_position.legs:
        for leg_orm in db_position.legs:
            leg_data = {column.name: getattr(leg_orm, column.name) for column in leg_orm.__table__.columns}
            display_legs.append(OptionLegDisplay(**leg_data))

    dte = None
    if display_legs and db_position.status == "OPEN":
        valid_expiry_dates = [leg.expiry_date for leg in display_legs if leg.expiry_date]
        if valid_expiry_dates:
            earliest_expiry = min(valid_expiry_dates)
            dte = (earliest_expiry - datetime.date.today()).days
        else:
            dte = None

    orm_data = {column.name: getattr(db_position, column.name) for column in db_position.__table__.columns}
    orm_data['legs'] = display_legs

    return PositionDetailDisplay(
        **orm_data,
        days_to_expiration=dte,
        calculated_position_delta=calculated_delta
    )


@router.post("/", response_model=PositionDetailDisplay, status_code=201)
def create_new_position(position_in: PositionCreate, db: Session = Depends(db_setup.get_db_session)):
    try:
        legs_data_dicts = [leg.model_dump(mode='python') for leg in position_in.legs_data]

        created_position = crud.create_position(
            db=db,
            underlying_symbol=position_in.underlying_symbol,
            spread_type=position_in.spread_type,
            legs_data=legs_data_dicts,
            status=position_in.status,
            notes=position_in.notes,
            is_stock_position=position_in.is_stock_position, # Pass new fields
            stock_quantity=position_in.stock_quantity      # Pass new fields
        )
        db.commit()
        db.refresh(created_position)
        if created_position.legs:
             for leg in created_position.legs:
                 db.refresh(leg)

        return _prepare_position_display(created_position)
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during position creation: {e}")


@router.get("/", response_model=List[PositionDetailDisplay])
def list_all_positions(
    status: Optional[str] = Query(None, description="Filter by position status"),
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(db_setup.get_db_session)
):
    db_positions = crud.get_all_positions(db, status=status, skip=skip, limit=limit)
    return [_prepare_position_display(pos) for pos in db_positions]


@router.get("/{position_id}", response_model=PositionDetailDisplay)
def get_specific_position(
    position_id: int,
    db: Session = Depends(db_setup.get_db_session),
    price_fetcher: AlphaVantageAPI = Depends(get_price_fetcher),
    volatility: Optional[float] = Query(None, description="Override volatility for delta (e.g., 0.20)"),
    risk_free_rate: Optional[float] = Query(None, description="Override risk-free rate for delta (e.g., 0.05)")
):
    db_position = crud.get_position_by_id(db, position_id)
    if not db_position:
        raise HTTPException(status_code=404, detail="Position not found")

    position_delta = None
    if db_position.status == "OPEN" and not db_position.is_stock_position : # Delta for options, not simple stocks
        try:
            position_delta = derivatives_calculator.calculate_position_delta(
                db=db, position=db_position, price_fetcher=price_fetcher,
                volatility_override=volatility, risk_free_rate_override=risk_free_rate
            )
        except Exception as delta_error:
            print(f"Warning: Could not calculate delta for position {position_id}: {delta_error}")

    return _prepare_position_display(db_position, calculated_delta=position_delta)


@router.put("/{position_id}/status", response_model=PositionDetailDisplay)
def update_position_status_endpoint(
    position_id: int, status: str = Query(..., description="New status (e.g., OPEN, CLOSED)"),
    closing_price: Optional[float] = Query(None, description="Net credit/debit if closing"),
    db: Session = Depends(db_setup.get_db_session)
):
    updated_pos = crud.update_position_status(db, position_id, status, closing_price)
    if not updated_pos:
        raise HTTPException(status_code=404, detail="Position not found")
    db.commit()
    db.refresh(updated_pos)
    if updated_pos.legs:
        for leg in updated_pos.legs: db.refresh(leg)
    return _prepare_position_display(updated_pos)


@router.post("/{position_id}/notes", response_model=PositionDetailDisplay)
def update_position_notes(
    position_id: int, notes_in: NotesUpdate,
    append: bool = Query(True, description="False to overwrite, True to append."),
    db: Session = Depends(db_setup.get_db_session)
):
    updated_pos = crud.add_note_to_position(db, position_id, notes_in.notes, append=append)
    if not updated_pos:
        raise HTTPException(status_code=404, detail="Position not found")
    db.commit()
    db.refresh(updated_pos)
    if updated_pos.legs:
        for leg in updated_pos.legs: db.refresh(leg)
    return _prepare_position_display(updated_pos)


@router.post("/{position_id}/leg_prices", response_model=PositionDetailDisplay)
def update_leg_prices_and_upl_endpoint(
    position_id: int, leg_prices_update: LegPricesUpdate,
    db: Session = Depends(db_setup.get_db_session)
):
    updated_pos = crud.update_legs_current_prices_and_unrealized_pnl(
        db, position_id, leg_prices_update.leg_current_prices
    )
    if not updated_pos:
        raise HTTPException(status_code=404, detail="Position not found or could not be updated")
    db.commit()
    db.refresh(updated_pos)
    if updated_pos.legs:
        for leg in updated_pos.legs: db.refresh(leg)

    return _prepare_position_display(updated_pos)

@router.post("/import_csv_stock", summary="Import Stock Positions from CSV", response_model=Dict[str, Any])
async def import_stock_positions_csv(
    file: UploadFile = File(..., description="CSV file containing stock positions."),
    db: Session = Depends(db_setup.get_db_session)
):
    """
    Imports stock positions from an uploaded CSV file.

    Expected CSV Columns:
    - `underlying_symbol` (string)
    - `stock_quantity` (integer)
    - `entry_price_per_unit` (float)
    - `entry_date` (string, "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS")
    - `notes` (string, optional)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")

    try:
        contents = await file.read()

        import_results = csv_importer.import_stock_positions_from_csv(db, contents)

        if import_results["success_count"] > 0:
            db.commit()
        else:
            # If there were errors but also some successes that were part of a larger transaction
            # handled by the importer, this rollback might undo them.
            # The importer should ideally handle transactions per row or signal overall success/failure.
            # For now, if importer indicates any success, we commit. Otherwise, rollback.
            # This assumes import_stock_positions_from_csv doesn't do its own commits.
            if not import_results["errors"] or import_results["failure_count"] == 0 : # if no errors, or only successes
                 db.commit() # Should be redundant if success_count > 0 already committed.
            else:
                 db.rollback()


        return {
            "message": "CSV processing complete.",
            "filename": file.filename,
            "successful_imports": import_results["success_count"],
            "failed_imports": import_results["failure_count"],
            "errors": import_results["errors"]
        }
    except HTTPException:
        db.rollback() # Rollback on known HTTP exceptions if they occur before commit point
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred during CSV processing: {str(e)}")
    finally:
        await file.close()
