import csv
import io
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from pydantic import ValidationError

from src.database import crud, models
from src.api_schemas import StockPositionCsvRow

def import_stock_positions_from_csv(db: Session, csv_file_content: bytes) -> Dict[str, Any]:
    """
    Parses a CSV file content and imports stock positions.

    Args:
        db: The SQLAlchemy session.
        csv_file_content: The byte content of the CSV file.

    Returns:
        A dictionary with import summary: {"success_count": int, "failure_count": int, "errors": List[str]}
    """
    successful_imports = 0
    failed_imports = 0
    errors_list = []

    # Decode bytes to string and use StringIO to treat it like a file
    try:
        csv_text = csv_file_content.decode('utf-8')
    except UnicodeDecodeError:
        return {
            "success_count": 0,
            "failure_count": 1, # Count the whole file as one failure here
            "errors": ["CSV file is not valid UTF-8 encoded text."]
        }

    reader = csv.DictReader(io.StringIO(csv_text))

    if not reader.fieldnames:
        errors_list.append("CSV file is empty or has no header row.")
        return {"success_count": 0, "failure_count": 0, "errors": errors_list}

    # Expected headers (case-insensitive check, but actual parsing uses exact header from file)
    expected_headers = {"underlying_symbol", "stock_quantity", "entry_price_per_unit", "entry_date"}
    # notes is optional

    missing_headers = expected_headers - set(h.lower().strip() for h in reader.fieldnames)
    if missing_headers:
        errors_list.append(f"CSV is missing required headers: {', '.join(missing_headers)}")
        # No point proceeding if essential headers are missing. Count all potential rows as failed.
        # This is a bit tricky as we don't know row count yet.
        # Alternative: just return this error.
        return {"success_count": 0, "failure_count": 0, "errors": errors_list}


    for row_num, row_dict in enumerate(reader, start=1): # Start from 1 for user-friendly row numbers
        try:
            # Map CSV headers to Pydantic field names if they differ (currently they don't)
            # Ensure all required fields for StockPositionCsvRow are present in row_dict
            # Pydantic will raise error if required fields are missing from the dict it receives.

            # Pre-process row_dict to handle potential empty strings for optional fields like notes
            processed_row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row_dict.items()}
            if 'notes' not in processed_row or processed_row['notes'] == '':
                processed_row['notes'] = None # Pydantic expects None for optional fields if not provided

            # Validate row data using Pydantic schema
            stock_data = StockPositionCsvRow(**processed_row)

            # Create a "leg-like" structure for the stock to pass to existing CRUD
            # This is a simplification as discussed.
            # OptionLeg requires option_type, strike_price, expiry_date.
            # We can use placeholder/sentinel values for these for "STOCK" type legs.
            stock_leg_data = {
                "option_type": "STOCK", # Special type to denote it's a stock holding
                "strike_price": 0, # Not applicable
                "expiry_date": stock_data.entry_date.date(), # Use entry date, or a far future date, or None if model allows
                "quantity": stock_data.stock_quantity, # This is stock quantity, not contract quantity
                "entry_price_per_unit": stock_data.entry_price_per_unit
            }

            # The cost_basis for the Position will be calculated by crud.create_position
            # based on stock_quantity and entry_price_per_unit when is_stock_position is True.
            # The legs_data here provides the entry_price_per_unit for that calculation.
            crud.create_position(
                db=db,
                underlying_symbol=stock_data.underlying_symbol,
                spread_type="Stock", # Or use a more generic type like "Equity Holding"
                is_stock_position=True,
                stock_quantity=stock_data.stock_quantity,
                legs_data=[stock_leg_data], # Pass the "representative" leg
                entry_date=stock_data.entry_date,
                notes=stock_data.notes,
                status="OPEN" # Default status for imported positions
            )
            successful_imports += 1
        except ValidationError as ve:
            failed_imports += 1
            errors_list.append(f"Row {row_num + 1}: Validation Error - {ve.errors()}") # row_num from reader starts at 0 for first data row
        except ValueError as ve: # From crud.create_position for example
            failed_imports += 1
            errors_list.append(f"Row {row_num + 1}: Value Error - {str(ve)}")
        except Exception as e:
            failed_imports += 1
            errors_list.append(f"Row {row_num + 1}: Unexpected Error - {type(e).__name__}: {str(e)}")
            # import traceback; traceback.print_exc() # For server debugging

    # Note: db.commit() should be handled by the calling API route after this function returns.
    # If there are failures, the route might decide to rollback all or commit successes.
    # For now, this function assumes operations are part of a larger transaction.

    return {
        "success_count": successful_imports,
        "failure_count": failed_imports,
        "errors": errors_list
    }

if __name__ == '__main__':
    # Example usage (requires a mock DB session and CSV content)
    print("--- CSV Importer Examples ---")

    # Mock DB session
    class MockDBSession:
        def add(self, obj): pass
        def commit(self): pass
        def flush(self): pass
        def refresh(self, obj): pass
        def query(self, *args): return self # Simplistic mock
        def filter(self, *args): return self
        def first(self): return None

    mock_db = MockDBSession()

    # Example 1: Valid CSV content
    csv_content_valid = b"""underlying_symbol,stock_quantity,entry_price_per_unit,entry_date,notes
AAPL,100,150.00,2023-01-15,Bought on dip
MSFT,50,280.50,2023-03-10,Long term hold
GOOG,,120.00,2023-05-20,Typo in quantity should fail
"""
    # GOOG line will fail due to empty stock_quantity, which cannot be cast to int by Pydantic

    print("\nTesting with valid and one invalid row CSV:")
    results_valid = import_stock_positions_from_csv(mock_db, csv_content_valid)
    print(f"  Success: {results_valid['success_count']}")
    print(f"  Failures: {results_valid['failure_count']}")
    print(f"  Errors: {results_valid['errors']}")
    # Expected: 2 success, 1 failure. Error for GOOG line.

    # Example 2: CSV with missing required header
    csv_content_missing_header = b"""underlying_symbol,quantity,entry_price_per_unit,entry_date
TSLA,10,700.00,2023-01-01""" # Missing 'stock_quantity' (using 'quantity' instead)
    print("\nTesting with missing header CSV:")
    results_missing_header = import_stock_positions_from_csv(mock_db, csv_content_missing_header)
    print(f"  Success: {results_missing_header['success_count']}")
    print(f"  Failures: {results_missing_header['failure_count']}")
    print(f"  Errors: {results_missing_header['errors']}")
    # Expected: 0 success, 0 failures (as it fails before processing rows), error message about missing header.

    # Example 3: CSV with invalid date format
    csv_content_bad_date = b"""underlying_symbol,stock_quantity,entry_price_per_unit,entry_date
NVDA,20,500.00,2023/06/15,Bad date format"""
    print("\nTesting with bad date format CSV:")
    results_bad_date = import_stock_positions_from_csv(mock_db, csv_content_bad_date)
    print(f"  Success: {results_bad_date['success_count']}")
    print(f"  Failures: {results_bad_date['failure_count']}")
    print(f"  Errors: {results_bad_date['errors']}")
    # Expected: 0 success, 1 failure. Error for NVDA line due to date.

    # Example 4: Empty CSV
    csv_empty = b""
    print("\nTesting with empty CSV:")
    results_empty = import_stock_positions_from_csv(mock_db, csv_empty)
    print(f"  Success: {results_empty['success_count']}")
    print(f"  Failures: {results_empty['failure_count']}")
    print(f"  Errors: {results_empty['errors']}")

    # Example 5: CSV with only headers
    csv_only_headers = b"underlying_symbol,stock_quantity,entry_price_per_unit,entry_date,notes"
    print("\nTesting with only headers CSV:")
    results_only_headers = import_stock_positions_from_csv(mock_db, csv_only_headers)
    print(f"  Success: {results_only_headers['success_count']}")
    print(f"  Failures: {results_only_headers['failure_count']}")
    print(f"  Errors: {results_only_headers['errors']}") # Should be 0,0,[] as no data rows

    print("\nCSV Importer examples finished.")
