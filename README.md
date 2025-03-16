# Attendio Bot - Smart Attendance Tracker 📊

## Overview
Attendio Bot is a **Telegram-based attendance management system** designed to help students effortlessly track their attendance across multiple courses. With smart alerts, automated tracking, and seamless integration with Google Sheets, Attendio ensures you never miss an update about your attendance status.

## 🔥 Features
- 📌 **Multi-Course Tracking** – Manage attendance across multiple subjects.
- 🚨 **Automated Alerts** – Get notified when attendance falls below 80%.
- 🛠️ **Modify Attendance** – Adjust records for canceled or extra classes.
- 📊 **Google Sheets Integration** – Secure and organized data storage.
- ⚡ **Easy-to-Use Commands** – Intuitive Telegram commands for quick actions.

---
## 📁 Project Structure
```
TheAttendioBot
├── src
│   ├── bot.py                # Main entry point for the Telegram bot
│   ├── google_sheets.py      # Google Sheets API interaction
│   ├── attendance_tracker.py  # Attendance tracking logic
│   └── utils
│       └── helpers.py        # Utility functions
├── requirements.txt          # List of dependencies
├── config.json               # Bot configuration settings
└── README.md                 # Documentation
```

---
## 🚀 Setup Instructions
### 1️⃣ Clone the Repository:
```bash
git clone https://github.com/TayalAditya/TheAttendioBot.git
cd TheAttendioBot
```
### 2️⃣ Install Dependencies:
```bash
pip install -r requirements.txt
```
### 3️⃣ Configure the Bot:
- Open `config.json`
- Add your **Telegram Bot Token** & **Google Sheets API Credentials**

### 4️⃣ Run the Bot:
```bash
python src/bot.py
```

---
## 📌 Usage Guidelines
- **Start the Bot** on Telegram and type `/start`
- **Use Commands** to mark attendance, check records, or modify entries
- **Receive Alerts** when attendance falls below 80%
- **Manage Subjects** by adding or deleting courses anytime

---
## 🤝 Contributing
We welcome contributions! 🚀 Feel free to submit **issues** or **pull requests** to improve the bot’s functionality.

---
## 📲 Try Attendio Bot Now
🔗 **Telegram Bot:** [Click Here](https://telegram.me/TheAttendioBot)  
🔗 **GitHub Repo:** [Click Here](https://github.com/TayalAditya/TheAttendioBot)  

📌 Stay ahead. Plan smart. Never stress about attendance again! 😎

