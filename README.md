# 📌 **Attendio Bot** – Your Smart Attendance Tracker  

[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue)](https://t.me/TheAttendioBot)
[![Contributors](https://img.shields.io/github/contributors/TayalAditya/TheAttendioBot)](https://github.com/TayalAditya/TheAttendioBot/graphs/contributors)  

## 🚀 **About Attendio Bot**  

Attendio Bot is a **Telegram-based attendance tracker** designed to help students manage their attendance efficiently. It allows users to track their attendance, receive alerts when attendance drops below a threshold, modify records, and plan smartly to avoid falling short. The bot integrates seamlessly with **Google Sheets**, ensuring secure and structured data management.  

## ✨ **Key Features**  

✅ **Instant Attendance Logging** – Mark attendance with a single command.  
📊 **Real-Time Dashboard** – View attendance stats across all subjects with progress bars.  
🚀 **Smart Bunk Planner** – Know how many classes you can skip before hitting the danger zone.  
⏰ **Automated Reminders** – Never forget to log your attendance.  
📚 **Course Management** – Add, delete, or modify courses anytime.  
🔄 **Edit Attendance** – Correct errors in attendance records with ease.  
📅 **Daily & Weekly Reports** – Get automated summaries of your attendance trends.  
🛡️ **Spam Protection** – Prevent duplicate or accidental entries.  
⚡ **Admin Commands** – Manage users and send notifications effortlessly.  
💬 **Feedback System** – Users can submit suggestions to improve the bot.  

---

## 🏗 **Project Structure**  

```
TheAttendioBot
├── src
│   ├── bot.py                # Main entry point for the Telegram bot
│   ├── google_sheets.py      # Google Sheets API integration
│   ├── attendance_tracker.py # Handles attendance records
│   ├── commands.py           # Defines Telegram bot commands
│   └── utils
│       ├── helpers.py        # Utility functions for the bot
│       ├── config_loader.py  # Loads configuration settings
│       └── logger.py         # Handles logging
├── config.json               # Stores bot and API configurations
├── requirements.txt          # List of required dependencies
└── README.md                 # Documentation
```

---

## 🛠 **Installation & Setup**  

### **1️⃣ Clone the Repository**  

```bash
git clone https://github.com/TayalAditya/TheAttendioBot.git
cd TheAttendioBot
```

### **2️⃣ Install Dependencies**  

```bash
pip install -r requirements.txt
```

### **3️⃣ Configure the Bot**  

Update `config.json` with:  
- **Your Telegram Bot Token** (from @BotFather)  
- **Google Sheets API Credentials**  

### **4️⃣ Run the Bot**  

```bash
python src/bot.py
```

---

## 🚀 **Usage Guide**  

1️⃣ **Start a chat with the bot** on Telegram.  
2️⃣ Use `/start` to register and set up your attendance.  
3️⃣ Use `/add_course` to add your subjects.  
4️⃣ Use `/mark_attendance` to log attendance.  
5️⃣ Check attendance stats anytime using `/check_attendance`.  
6️⃣ Edit or delete records if needed using `/edit_attendance`.  

For a complete list of commands, type `/help` in the bot.  

---

## 🤝 **Contributing**  

🔹 Fork this repository.  
🔹 Create a new branch (`git checkout -b feature-name`).  
🔹 Commit your changes (`git commit -m "Added a new feature"`).  
🔹 Push to your branch (`git push origin feature-name`).  
🔹 Open a Pull Request.  

Your contributions are always welcome! 🚀   

---

## 📞 **Contact**  

👨‍💻 **Developed by:** Aditya Tayal  
📩 **Email:** [adityatayal404@gmail.com](mailto:adityatayal404@gmail.com)  
🔗 **LinkedIn:** [tayal-aditya](https://www.linkedin.com/in/tayal-aditya)  
📲 **Telegram:** [Attendio Bot](https://t.me/TheAttendioBot)  

---
