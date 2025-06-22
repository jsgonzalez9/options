from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from src.database import setup as db_setup, crud, models
from src.api_schemas import (
    PositionCreate, PositionDisplay, OptionLegDisplay, PositionBase, # PositionBase for notes before
    LegPricesUpdate, PositionDetailDisplay, NotesUpdate # Added NotesUpdate
)
# PositionDeltaParams might be used by a dedicated delta endpoint later or if params are complex for GET
from src.core import derivatives_calculator
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
    if db_position.legs: # Ensure legs relationship is loaded and not None
        for leg_orm in db_position.legs:
            # Manually create a dict from the ORM object's attributes
            leg_data = {
                "id": leg_orm.id,
                "position_id": leg_orm.position_id,
                "option_type": leg_orm.option_type,
                "strike_price": leg_orm.strike_price,
                "expiry_date": leg_orm.expiry_date,
                "quantity": leg_orm.quantity,
                "entry_price_per_unit": leg_orm.entry_price_per_unit,
                "current_price_per_unit": leg_orm.current_price_per_unit,
                "closing_price_per_unit": leg_orm.closing_price_per_unit,
                "entry_date_leg": leg_orm.entry_date_leg,
            }
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
        # Use mode='python' to keep datetime.date objects as is from Pydantic model, not strings
        legs_data_dicts = [leg.model_dump(mode='python') for leg in position_in.legs_data]

        created_position = crud.create_position(
            db=db,
            underlying_symbol=position_in.underlying_symbol, # Pass underlying_symbol
            spread_type=position_in.spread_type,
            legs_data=legs_data_dicts,
            status=position_in.status,
            notes=position_in.notes
        )
        db.commit()
        # Refresh is crucial to get DB-generated IDs and relationships correctly loaded
        db.refresh(created_position)
        # Eager load/refresh legs after commit if they are not automatically loaded/updated by the main refresh
        # This ensures that _prepare_position_display gets the full leg data
        if created_position.legs: # Accessing .legs might trigger a load if not already loaded
             for leg in created_position.legs:
                 db.refresh(leg) # Ensure each leg's data is fresh from DB

        return _prepare_position_display(created_position)
    except ValueError as ve: # Catch validation errors from CRUD or spread_validator
        db.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        db.rollback()
        # import traceback; traceback.print_exc(); # For server-side debugging
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during position creation: {e}")


@router.get("/", response_model=List[PositionDetailDisplay])
def list_all_positions(
    status: Optional[str] = Query(None, description="Filter by position status"),
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(db_setup.get_db_session)
):
    db_positions = crud.get_all_positions(db, status=status, skip=skip, limit=limit)
    # _prepare_position_display expects legs to be loaded. get_all_positions uses joinedload.
    return [_prepare_position_display(pos) for pos in db_positions]


@router.get("/{position_id}", response_model=PositionDetailDisplay)
def get_specific_position(
    position_id: int,
    db: Session = Depends(db_setup.get_db_session),
    price_fetcher: AlphaVantageAPI = Depends(get_price_fetcher),
    volatility: Optional[float] = Query(None, description="Override volatility for delta (e.g., 0.20)"),
    risk_free_rate: Optional[float] = Query(None, description="Override risk-free rate for delta (e.g., 0.05)")
):
    db_position = crud.get_position_by_id(db, position_id) # This uses joinedload for legs
    if not db_position:
        raise HTTPException(status_code=404, detail="Position not found")

    position_delta = None
    if db_position.status == "OPEN":
        try:
            position_delta = derivatives_calculator.calculate_position_delta(
                db=db, position=db_position, price_fetcher=price_fetcher,
                volatility_override=volatility, risk_free_rate_override=risk_free_rate
            )
        except Exception as delta_error:
            print(f"Warning: Could not calculate delta for position {position_id}: {delta_error}")
            # position_delta remains None

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
    position_id: int, notes_in: NotesUpdate, # Use new NotesUpdate schema
    append: bool = Query(True, description="False to overwrite, True to append."),
    db: Session = Depends(db_setup.get_db_session)
):
    # notes_in.notes will be validated by Pydantic to be a string
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
