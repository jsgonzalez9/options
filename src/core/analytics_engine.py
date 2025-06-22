from sqlalchemy.orm import Session
from src.database import models, crud # crud might not be directly needed here, but models is.
from typing import List, Tuple

def get_realized_pnls_for_analytics(db: Session) -> List[float]:
    """
    Fetches the realized_pnl from all 'CLOSED' positions
    where realized_pnl is not None.
    """
    closed_positions = db.query(models.Position.realized_pnl)\
                         .filter(models.Position.status == "CLOSED",
                                 models.Position.realized_pnl.isnot(None))\
                         .all()
    # The query returns a list of tuples, e.g., [(100.0,), (-50.0,)]
    return [pnl[0] for pnl in closed_positions]

def calculate_win_rate(pnls: List[float]) -> float:
    """
    Calculates the win rate (percentage of P&Ls > 0).
    Returns 0.0 if there are no P&Ls.
    """
    if not pnls:
        return 0.0

    wins = sum(1 for pnl in pnls if pnl > 0)
    return (wins / len(pnls)) * 100.0

def calculate_average_pnl(pnls: List[float]) -> float:
    """
    Calculates the average P&L.
    Returns 0.0 if there are no P&Ls.
    """
    if not pnls:
        return 0.0
    return sum(pnls) / len(pnls)

def calculate_profit_factor(pnls: List[float]) -> float:
    """
    Calculates the profit factor (Gross Profit / Absolute Gross Loss).
    Returns 0.0 if Gross Loss is zero or no P&Ls.
    Returns float('inf') if Gross Loss is zero but Gross Profit is positive.
    """
    if not pnls:
        return 0.0

    gross_profit = sum(pnl for pnl in pnls if pnl > 0)
    gross_loss = sum(pnl for pnl in pnls if pnl < 0)

    if gross_loss == 0:
        if gross_profit > 0:
            return float('inf') # Infinite profit factor if no losses but profits exist
        else:
            return 0.0 # No profits and no losses, or only profits of 0

    return gross_profit / abs(gross_loss)

def get_performance_summary(db: Session) -> dict:
    """
    Calculates and returns a dictionary of performance metrics.
    """
    realized_pnls = get_realized_pnls_for_analytics(db)

    total_trades = len(realized_pnls)
    win_rate = calculate_win_rate(realized_pnls)
    avg_pnl = calculate_average_pnl(realized_pnls)
    profit_factor = calculate_profit_factor(realized_pnls)

    total_profit = sum(pnl for pnl in realized_pnls if pnl > 0)
    total_loss = sum(pnl for pnl in realized_pnls if pnl < 0) # Will be negative or zero

    num_winning_trades = sum(1 for pnl in realized_pnls if pnl > 0)
    num_losing_trades = sum(1 for pnl in realized_pnls if pnl < 0)

    avg_profit_per_winning_trade = (total_profit / num_winning_trades) if num_winning_trades > 0 else 0.0
    avg_loss_per_losing_trade = (total_loss / num_losing_trades) if num_losing_trades > 0 else 0.0


    return {
        "total_closed_trades": total_trades,
        "realized_pnls": realized_pnls, # Optional: for detailed view or further custom calcs
        "win_rate_percent": win_rate,
        "average_pnl_per_trade": avg_pnl,
        "profit_factor": profit_factor,
        "total_gross_profit": total_profit,
        "total_gross_loss": total_loss, # This is sum of negative P&Ls
        "number_of_winning_trades": num_winning_trades,
        "number_of_losing_trades": num_losing_trades,
        "average_profit_per_winning_trade": avg_profit_per_winning_trade,
        "average_loss_per_losing_trade": avg_loss_per_losing_trade # This will be negative or zero
    }

if __name__ == '__main__':
    from src.database import setup as db_setup
    # This example requires a database with some closed positions and realized P&L data.
    # We'll mock the pnls list for direct function testing.

    print("--- Analytics Engine Examples ---")

    sample_pnls_1 = [100, -50, 200, -80, 120] # 3 wins, 2 losses
    print(f"\nSample P&Ls 1: {sample_pnls_1}")
    print(f"  Win Rate: {calculate_win_rate(sample_pnls_1):.2f}%") # (3/5)*100 = 60%
    print(f"  Average P&L: {calculate_average_pnl(sample_pnls_1):.2f}") # (100-50+200-80+120)/5 = 290/5 = 58
    # Gross Profit = 100+200+120 = 420. Gross Loss = -50-80 = -130.
    # Profit Factor = 420 / |-130| = 420 / 130 = 3.23
    print(f"  Profit Factor: {calculate_profit_factor(sample_pnls_1):.2f}")

    sample_pnls_2 = [50, 70, 100] # All wins
    print(f"\nSample P&Ls 2 (all wins): {sample_pnls_2}")
    print(f"  Win Rate: {calculate_win_rate(sample_pnls_2):.2f}%") # 100%
    print(f"  Average P&L: {calculate_average_pnl(sample_pnls_2):.2f}") # 220/3 = 73.33
    print(f"  Profit Factor: {calculate_profit_factor(sample_pnls_2)}") # inf

    sample_pnls_3 = [-20, -30, -10] # All losses
    print(f"\nSample P&Ls 3 (all losses): {sample_pnls_3}")
    print(f"  Win Rate: {calculate_win_rate(sample_pnls_3):.2f}%") # 0%
    print(f"  Average P&L: {calculate_average_pnl(sample_pnls_3):.2f}") # -60/3 = -20
    print(f"  Profit Factor: {calculate_profit_factor(sample_pnls_3):.2f}") # 0.0

    sample_pnls_4 = [] # No trades
    print(f"\nSample P&Ls 4 (no trades): {sample_pnls_4}")
    print(f"  Win Rate: {calculate_win_rate(sample_pnls_4):.2f}%") # 0%
    print(f"  Average P&L: {calculate_average_pnl(sample_pnls_4):.2f}") # 0.0
    print(f"  Profit Factor: {calculate_profit_factor(sample_pnls_4):.2f}") # 0.0

    # Example with get_performance_summary (requires DB session and data)
    # To run this part, you'd need to set up a test DB and populate it.
    # For now, we are testing the individual calculation functions.
    print("\n--- get_performance_summary (conceptual - requires DB data) ---")
    # db_gen = db_setup.get_db_session()
    # test_db = next(db_gen)
    # try:
    #     # Populate test_db with some closed positions...
    #     # Example:
    #     # crud.create_position(test_db, "Test Spread", legs_data=[...], status="CLOSED", realized_pnl=100)
    #     # crud.create_position(test_db, "Test Spread 2", legs_data=[...], status="CLOSED", realized_pnl=-50)
    #     # test_db.commit()
    #
    #     summary = get_performance_summary(test_db)
    #     print("Performance Summary from DB (mocked data):")
    #     for key, value in summary.items():
    #         if isinstance(value, float):
    #             print(f"  {key}: {value:.2f}")
    #         else:
    #             print(f"  {key}: {value}")
    # except Exception as e:
    #     print(f"DB dependent summary test skipped or failed: {e}")
    # finally:
    #     test_db.close()

    print("\nAnalytics Engine examples finished.")
