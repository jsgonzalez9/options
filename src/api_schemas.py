from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
import datetime

# --- OptionLeg Schemas ---

class OptionLegBase(BaseModel):
    option_type: str = Field(..., pattern="^(CALL|PUT)$") # "CALL" or "PUT"
    strike_price: float
    expiry_date: datetime.date
    quantity: int # Positive for long, negative for short
    entry_price_per_unit: float
    current_price_per_unit: Optional[float] = None
    closing_price_per_unit: Optional[float] = None
    entry_date_leg: Optional[datetime.datetime] = None

class OptionLegCreate(OptionLegBase):
    pass

class OptionLegDisplay(OptionLegBase):
    id: int
    position_id: int

    class Config:
        from_attributes = True # Pydantic V2 ORM mode


# --- Position Schemas ---

class PositionBase(BaseModel):
    spread_type: str
    status: str = Field(default="OPEN", pattern="^(OPEN|CLOSED|ROLLED|EXPIRED)$")
    notes: Optional[str] = None
    cost_basis: Optional[float] = None
    closing_price: Optional[float] = None
    unrealized_pnl: Optional[float] = Field(default=0.0)
    realized_pnl: Optional[float] = Field(default=0.0)
    entry_date: Optional[datetime.datetime] = None


class PositionCreate(PositionBase):
    legs_data: List[OptionLegCreate]

    @validator('status', pre=True, always=True)
    def set_default_status(cls, v):
        return v or "OPEN"


class PositionDisplay(PositionBase):
    id: int
    legs: List[OptionLegDisplay] = []
    days_to_expiration: Optional[int] = None

    @validator('legs', pre=True, always=True)
    def empty_list_if_none(cls, v):
        return v if v is not None else []

    class Config:
        from_attributes = True


# --- Portfolio Schemas ---

class CashUpdate(BaseModel):
    amount: float = Field(..., gt=0) # Ensure amount is positive
    is_deposit: bool = True

class PortfolioSettingBase(BaseModel):
    key: str
    value: float

class PortfolioSettingCreate(PortfolioSettingBase):
    pass

class PortfolioSettingDisplay(PortfolioSettingBase):
    class Config:
        from_attributes = True

class PortfolioSummary(BaseModel):
    cash_balance: float
    total_open_positions_market_value: float
    total_portfolio_value: float
    overall_portfolio_pnl: float


# --- Analytics Schemas ---

class AnalyticsReport(BaseModel):
    total_closed_trades: int
    win_rate_percent: float
    average_pnl_per_trade: float
    profit_factor: float
    total_gross_profit: float
    total_gross_loss: float
    number_of_winning_trades: int
    number_of_losing_trades: int
    average_profit_per_winning_trade: float
    average_loss_per_losing_trade: float


# --- Other Utility Schemas ---

class LegPricesUpdate(BaseModel):
    leg_current_prices: Dict[int, float]

class PositionDeltaParams(BaseModel):
    volatility: Optional[float] = Field(None, ge=0.0001, description="Annualized volatility (e.g., 0.20 for 20%)")
    risk_free_rate: Optional[float] = Field(None, ge=0.0, description="Annualized risk-free rate (e.g., 0.05 for 5%)")
    underlying_price_override: Optional[float] = Field(None, description="Override for current underlying price")

class NotesUpdate(BaseModel):
    notes: str

class PositionDetailDisplay(PositionDisplay):
    calculated_position_delta: Optional[float] = None

    @validator('calculated_position_delta', pre=True, always=True) # always=True in case it's None
    def round_delta(cls, v):
        if v is not None:
            return round(v, 4)
        return v


if __name__ == "__main__":
    # Example usage of the schemas
    leg_create_data = {
        "option_type": "CALL", "strike_price": 150.0,
        "expiry_date": "2025-01-17", "quantity": 1, "entry_price_per_unit": 2.50
    }
    leg = OptionLegCreate(**leg_create_data)
    print("OptionLegCreate:", leg.model_dump_json(indent=2))

    position_create_data = {
        "spread_type": "Bull Call Spread",
        "legs_data": [leg_create_data],
        "notes": "My first API position"
    }
    pos_create = PositionCreate(**position_create_data)
    print("\nPositionCreate:", pos_create.model_dump_json(indent=2))

    notes_upd = NotesUpdate(notes="Updated note.")
    print("\nNotesUpdate:", notes_upd.model_dump_json(indent=2))

    # Example for PositionDisplay (data would typically come from an ORM model)
    pos_display_data = {
        "id": 1, "spread_type": "Iron Condor", "status": "OPEN",
        "cost_basis": -150.0, "unrealized_pnl": 25.0, "realized_pnl": 0.0,
        "entry_date": datetime.datetime.now(),
        "legs": [
            {"id": 101, "position_id": 1, **leg_create_data, "expiry_date": datetime.date(2025,1,17)},
            {"id": 102, "position_id": 1, "option_type": "CALL", "strike_price": 155.0,
             "expiry_date": datetime.date(2025,1,17), "quantity": -1, "entry_price_per_unit": 1.00}
        ]
    }
    pos_display = PositionDisplay(**pos_display_data)
    print("\nPositionDisplay:", pos_display.model_dump_json(indent=2))

    cash_update_data = {"amount": 1000.0, "is_deposit": True} # Ensure float for amount
    cash_upd = CashUpdate(**cash_update_data)
    print("\nCashUpdate:", cash_upd.model_dump_json(indent=2))

    print(f"\nUsing Pydantic from_attributes for PositionDisplay: {PositionDisplay.model_config.get('from_attributes')}")
    print(f"Using Pydantic from_attributes for OptionLegDisplay: {OptionLegDisplay.model_config.get('from_attributes')}")
