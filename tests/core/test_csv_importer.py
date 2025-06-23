import unittest
from unittest.mock import MagicMock, patch, call
import datetime

from src.core import csv_importer
from src.api_schemas import StockPositionCsvRow # For creating test data
from sqlalchemy.orm import Session # For type hinting
from pydantic import ValidationError


class TestCsvImporter(unittest.TestCase):

    def setUp(self):
        self.mock_db_session = MagicMock(spec=Session)

    @patch('src.core.csv_importer.crud.create_position')
    def test_import_valid_csv_single_row(self, mock_create_position):
        csv_content = b"underlying_symbol,stock_quantity,entry_price_per_unit,entry_date,notes\nAAPL,100,150.00,2023-01-15,Test Note"

        results = csv_importer.import_stock_positions_from_csv(self.mock_db_session, csv_content)

        self.assertEqual(results["success_count"], 1)
        self.assertEqual(results["failure_count"], 0)
        self.assertEqual(len(results["errors"]), 0)

        mock_create_position.assert_called_once()
        args, kwargs = mock_create_position.call_args
        self.assertEqual(kwargs['underlying_symbol'], "AAPL")
        self.assertEqual(kwargs['spread_type'], "Stock")
        self.assertTrue(kwargs['is_stock_position'])
        self.assertEqual(kwargs['stock_quantity'], 100)
        self.assertEqual(kwargs['entry_date'], datetime.datetime(2023, 1, 15, 0, 0)) # Default time
        self.assertEqual(kwargs['notes'], "Test Note")

        expected_leg_data = {
            "option_type": "STOCK",
            "strike_price": 0,
            "expiry_date": datetime.date(2023, 1, 15),
            "quantity": 100, # Stock quantity here for the representative leg
            "entry_price_per_unit": 150.00
        }
        self.assertEqual(len(kwargs['legs_data']), 1)
        self.assertDictEqual(kwargs['legs_data'][0], expected_leg_data)

    @patch('src.core.csv_importer.crud.create_position')
    def test_import_csv_multiple_rows_mixed_validity(self, mock_create_position):
        csv_content = b"""underlying_symbol,stock_quantity,entry_price_per_unit,entry_date,notes
MSFT,50,200.0,2023-02-01,First stock
GOOG,,1000.0,2023-03-01,Missing quantity - should fail
TSLA,10,700.50,2023-04-01,Another stock
"""
        results = csv_importer.import_stock_positions_from_csv(self.mock_db_session, csv_content)

        self.assertEqual(results["success_count"], 2)
        self.assertEqual(results["failure_count"], 1)
        self.assertEqual(len(results["errors"]), 1)
        self.assertIn("Row 3: Validation Error", results["errors"][0]) # GOOG row is row 3 (1-indexed data rows)
        self.assertEqual(mock_create_position.call_count, 2)

    def test_import_csv_missing_required_header(self):
        # Missing 'stock_quantity' header
        csv_content = b"underlying_symbol,entry_price_per_unit,entry_date\nAAPL,150.00,2023-01-15"
        results = csv_importer.import_stock_positions_from_csv(self.mock_db_session, csv_content)

        self.assertEqual(results["success_count"], 0)
        self.assertEqual(results["failure_count"], 0) # Fails before processing rows
        self.assertEqual(len(results["errors"]), 1)
        self.assertIn("missing required headers", results["errors"][0].lower())
        self.assertIn("stock_quantity", results["errors"][0].lower())

    def test_import_csv_bad_data_type(self):
        # 'stock_quantity' is not an int
        csv_content = b"underlying_symbol,stock_quantity,entry_price_per_unit,entry_date\nAAPL,lots,150.00,2023-01-15"
        results = csv_importer.import_stock_positions_from_csv(self.mock_db_session, csv_content)

        self.assertEqual(results["success_count"], 0)
        self.assertEqual(results["failure_count"], 1)
        self.assertEqual(len(results["errors"]), 1)
        self.assertIn("Row 2: Validation Error", results["errors"][0]) # Data row 1 is "Row 2" in message
        self.assertIn("stock_quantity", results["errors"][0]) # Pydantic error will mention the field

    def test_import_csv_invalid_date_format(self):
        csv_content = b"underlying_symbol,stock_quantity,entry_price_per_unit,entry_date\nAAPL,100,150.00,2023/01/15" # Wrong date format
        results = csv_importer.import_stock_positions_from_csv(self.mock_db_session, csv_content)

        self.assertEqual(results["success_count"], 0)
        self.assertEqual(results["failure_count"], 1)
        self.assertEqual(len(results["errors"]), 1)
        self.assertIn("Row 2: Validation Error", results["errors"][0])
        self.assertIn("Invalid date/datetime format for entry_date", results["errors"][0])

    def test_import_empty_csv(self):
        csv_content = b""
        results = csv_importer.import_stock_positions_from_csv(self.mock_db_session, csv_content)
        self.assertEqual(results["success_count"], 0)
        self.assertEqual(results["failure_count"], 0)
        self.assertIn("CSV file is empty or has no header row.", results["errors"])

    def test_import_csv_only_headers(self):
        csv_content = b"underlying_symbol,stock_quantity,entry_price_per_unit,entry_date,notes"
        results = csv_importer.import_stock_positions_from_csv(self.mock_db_session, csv_content)
        self.assertEqual(results["success_count"], 0)
        self.assertEqual(results["failure_count"], 0)
        self.assertEqual(len(results["errors"]), 0) # No data rows, so no processing errors

    def test_import_csv_utf8_decode_error(self):
        csv_content = b'\xff\xfeAAPL' # Invalid start for UTF-8 (this is UTF-16 BOM)
        results = csv_importer.import_stock_positions_from_csv(self.mock_db_session, csv_content)
        self.assertEqual(results["success_count"], 0)
        self.assertEqual(results["failure_count"], 1)
        self.assertIn("CSV file is not valid UTF-8 encoded text.", results["errors"])

if __name__ == '__main__':
    unittest.main()
