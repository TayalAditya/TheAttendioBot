# Telegram Attendance Bot

This project is a Telegram bot designed to track student attendance across different courses. The bot sends alerts when a student's attendance falls below 80% and allows for modifications in case of cancellations or extra classes. The backend for attendance data is managed using Google Sheets.

## Features

- Track attendance for multiple students and courses.
- Send alerts when attendance drops below 80%.
- Modify attendance records for cancellations or extra classes.
- Easy integration with Google Sheets for data management.

## Project Structure

```
telegram-attendance-bot
├── src
│   ├── bot.py                # Main entry point for the Telegram bot
│   ├── google_sheets.py      # Functions to interact with Google Sheets API
│   ├── attendance_tracker.py  # Class to manage attendance records
│   └── utils
│       └── helpers.py        # Utility functions for the bot
├── requirements.txt          # List of dependencies
├── config.json               # Configuration settings for the bot
└── README.md                 # Documentation for the project
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/telegram-attendance-bot.git
   cd telegram-attendance-bot
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure the bot:
   - Update `config.json` with your Telegram bot token and Google Sheets API credentials.

4. Run the bot:
   ```
   python src/bot.py
   ```

## Usage Guidelines

- Start a chat with the bot on Telegram.
- Use commands to check attendance, report cancellations, or add extra classes.
- The bot will automatically send alerts for students whose attendance falls below the threshold.

## Contributing

Feel free to submit issues or pull requests to improve the bot's functionality or fix bugs. 

## License

This project is licensed under the MIT License.