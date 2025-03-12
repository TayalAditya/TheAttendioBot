import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import logging
import telegram

logger = logging.getLogger(__name__)

class GoogleSheets:
    def __init__(self, credentials_path, spreadsheet_id, config):
        """Initializes the Google Sheets connection."""
        try:
            # Load credentials from the specified path
            self.credentials = Credentials.from_service_account_file(
                credentials_path,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            self.client = gspread.authorize(self.credentials)
            self.spreadsheet = self.client.open_by_key(spreadsheet_id)
            self.sheet = self.spreadsheet.sheet1  # Or use a specific sheet name
            self.headers = self.get_headers()
            self.config = config  # Store the config
            self.bot = telegram.Bot(token=config['telegram_bot_token'])  # Initialize the bot
            print("Google Sheets connection initialized successfully.")
        except Exception as e:
            print(f"Error initializing Google Sheets: {e}")
            raise

    def get_headers(self):
        """Retrieves the headers from the Google Sheet."""
        try:
            headers = self.sheet.row_values(1)
            return headers
        except Exception as e:
            print(f"Error getting headers: {e}")
            raise

    def get_attendance_data(self):
        try:
            return self.sheet.get_all_records()
        except Exception as e:
            logger.error(f"Error getting attendance data: {e}")
            return []

    def read_data(self):
        try:
            values = self.sheet.get_all_values()
            return pd.DataFrame(values[1:], columns=values[0]) if values else pd.DataFrame()
        except Exception as e:
            logger.error(f"Error reading data: {e}")
            return pd.DataFrame()

    def write_data(self, data):
        try:
            self.sheet.clear()
            self.sheet.update([data.columns.values.tolist()] + data.values.tolist())
        except Exception as e:
            logger.error(f"Error writing data: {e}")

    def append_row(self, data):
        """Appends a row to the Google Sheet."""
        try:
            # Get the next available row
            next_row = len(self.sheet.get_all_values()) + 1
            # Prepare the values to be written
            values = [data.get(col) for col in self.headers]  # Use self.headers

            # Write the values to the next row
            self.sheet.append_row(values)
            print(f"Row appended successfully: {values}")
        except Exception as e:
            print(f"Error appending row: {e}")

    def get_all_data(self):
        """Retrieves all data from the Google Sheet."""
        try:
            list_of_dicts = self.sheet.get_all_records()
            return list_of_dicts
        except Exception as e:
            print(f"Error getting all data: {e}")
            raise

    def update_cell(self, row_index, column_name, value):
        """Updates a single cell in the Google Sheet."""
        try:
            col_index = self.headers.index(column_name) + 1  # Column index is 1-based
            self.sheet.update_cell(row_index, col_index, value)
            print(f"Cell updated at row {row_index}, column {column_name} with value {value}")
        except ValueError as e:
            print(f"Column name '{column_name}' not found in headers.")
            raise e
        except Exception as e:
            print(f"Error updating cell: {e}")

    def send_message(self, user_id, chat_id, text, parse_mode=None):
        """Sends a message to a Telegram user."""
        try:
            self.bot.send_message(chat_id=user_id, text=text, parse_mode=parse_mode)
            print(f"Message sent to chat ID {chat_id}: {text}")
        except Exception as e:
            print(f"Error sending message to chat ID {chat_id}: {e}")

    def add_row(self, row_data):
        """Adds a new row to the Google Sheet."""
        try:
            self.sheet.append_row(row_data)
            print(f"New row added: {row_data}")
        except Exception as e:
            print(f"Error adding row: {e}")
            raise

    def delete_row(self, row_index):
        """Deletes a row from the Google Sheet."""
        try:
            self.sheet.delete_rows(row_index)
            print(f"Row deleted at index {row_index}")
        except Exception as e:
            print(f"Error deleting row: {e}")
            raise
