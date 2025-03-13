#!/usr/bin/env python
import os
import sys

# SURVIVAL MODE FOR BUILD PHASE
# Check if this is running in a build environment
if "RAILWAY_BUILD_ID" in os.environ or "BUILD_ID" in os.environ:
    print("Detected build environment - skipping bot execution")
    sys.exit(0)

# If we're validating the install only
if len(sys.argv) > 1 and sys.argv[1] == "--validate-install":
    print("Installation validated successfully!")
    sys.exit(0)
    
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, Filters
from google_sheets import GoogleSheets
from attendance_tracker import AttendanceTracker
import json
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import pytz
import math
import telegram
from collections import defaultdict, Counter
from logger_config import setup_logging, send_logs_to_admin, schedule_daily_logs


def load_config():
    """Load config from environment variables or local file"""
    try:
        # Check for environment variables (case-insensitive)
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("telegram_bot_token")
        sheets_creds = os.getenv("GOOGLE_SHEETS_CREDENTIALS") or os.getenv("google_sheets_credentials")
        spreadsheet = os.getenv("SPREADSHEET_ID") or os.getenv("spreadsheet_id")
        threshold = os.getenv("ATTENDANCE_THRESHOLD") or os.getenv("attendance_threshold")
        admin_id = os.getenv("ADMIN_TELEGRAM_ID") or os.getenv("admin_telegram_id")
        
        # Debug environment variables
        print("==== Environment Variable Check ====")
        print(f"TELEGRAM_BOT_TOKEN: {'Present' if telegram_token else 'MISSING'}")
        print(f"GOOGLE_SHEETS_CREDENTIALS: {'Present' if sheets_creds else 'MISSING'}")
        print(f"SPREADSHEET_ID: {'Present' if spreadsheet else 'MISSING'}")
        print(f"ATTENDANCE_THRESHOLD: {'Present' if threshold else 'MISSING'}")
        print(f"ADMIN_TELEGRAM_ID: {'Present' if admin_id else 'MISSING'}")
        print("===================================")
        
        if telegram_token and sheets_creds:
            print("Loading config from environment variables")
            
            # Parse Google Sheets credentials if stored as JSON string
            try:
                google_creds = json.loads(sheets_creds)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON format in GOOGLE_SHEETS_CREDENTIALS environment variable.")
            
            return {
                "telegram_bot_token": telegram_token,
                "google_sheets_credentials": google_creds,
                "spreadsheet_id": spreadsheet,
                "attendance_threshold": float(threshold or "75.0"),
                "admin_telegram_id": admin_id or ""
            }
        else:
            # If no environment variables, use emergency fallback config
            print("WARNING: Environment variables not found!")
            print("WARNING: Using fallback minimal configuration for testing only!")
            return {
                "telegram_bot_token": "YOUR_BOT_TOKEN",
                "google_sheets_credentials": {},
                "spreadsheet_id": "YOUR_SPREADSHEET_ID",
                "attendance_threshold": 75.0,
                "admin_telegram_id": "YOUR_ADMIN_ID"
            }
    except Exception as e:
        print(f"Error loading config: {e}")
        raise

# Load configuration
config = load_config()

# Initialize the updater after we have the config
updater = Updater(config['telegram_bot_token'])

logger, telegram_handler = setup_logging()

# Initialize Google Sheets and Attendance Tracker
google_sheets = GoogleSheets(config['google_sheets_credentials'], config['spreadsheet_id'], config)
attendance_tracker = AttendanceTracker(google_sheets, config['attendance_threshold'])

# Define states for conversation handlers
SELECT_COURSE, MARK_ATTENDANCE, ADD_COURSE_NAME, GET_CHAT_ID, DELETE_COURSE_CONFIRM, EDIT_ATTENDANCE_DISPLAY,FEEDBACK_TEXT, PHONE_VERIFICATION, ANNOUNCEMENT_TEXT = range(9)

# Update these variables under your other constants
RATE_LIMIT_COMMANDS = 15  # Auto-block after this many commands per minute
RATE_LIMIT_PERIOD = 60  # Seconds
command_history = defaultdict(list)  # Track user command history
blocked_users = set()  # Store blocked user IDs

class User:
    def __init__(self, user_id, user_name, chat_id, phone_number):
        self.user_id = user_id
        self.user_name = user_name
        self.chat_id = chat_id
        self.phone_number = phone_number
        self.courses = {}
        self.present = 0
        self.absent = 0
        self.last_updated = None
        self.streak = 0

    def add_course(self, course_code, course_nickname):
        self.courses[course_code] = course_nickname

    def update_attendance(self, present, absent, last_updated, streak):
        self.present = present
        self.absent = absent
        self.last_updated = last_updated
        self.streak = streak

# Dictionary to store user objects
users = {}

# Function to get or create a user
def get_or_create_user(user_id, user_name, chat_id, phone_number):
    if user_id in users:
        user = users[user_id]
        # Update user information if necessary
        user.user_name = user_name
        user.chat_id = chat_id
        user.phone_number = phone_number
    else:
        user = User(user_id, user_name, chat_id, phone_number)
        users[user_id] = user
    return user


# Update the check rate limit function to auto-block users
def check_rate_limit(update: Update) -> bool:
    """Check if a user has exceeded rate limits."""
    user_id = update.effective_user.id
    current_time = datetime.now()
    
    # Admin bypass
    if str(user_id) == str(config.get('admin_telegram_id')):
        return False
    
    # Remove old commands from history
    command_history[user_id] = [
        timestamp for timestamp in command_history[user_id] 
        if current_time - timestamp < timedelta(seconds=RATE_LIMIT_PERIOD)
    ]
    
    # Add current command
    command_history[user_id].append(current_time)
    
    # Check if rate limited and auto-block at 33 commands per minute
    if len(command_history[user_id]) > RATE_LIMIT_COMMANDS:
        # Auto-block the user
        blocked_users.add(user_id)
        
        update.message.reply_text(
            "⚠️ You have been automatically blocked due to sending too many commands in a short period. " +
            "To appeal this block, please use the /feedback command to contact our admin."
        )
        
        # Notify admin about the auto-block
        if 'admin_telegram_id' in config:
            user = update.effective_user
            user_mention = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'
            
            admin_message = f"🚫 <b>User Auto-Blocked:</b>\n\n" \
                           f"👤 User: {user_mention} (ID: {user.id})\n" \
                           f"📊 Commands in last minute: {len(command_history[user_id])}\n" \
                           f"⏰ Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n" \
                           f"This user was automatically blocked for sending too many commands.\n" \
                           f"Use <code>/unblock {user.id}</code> to unblock this user if needed."
                           
            updater.bot.send_message(
                chat_id=config['admin_telegram_id'],
                text=admin_message,
                parse_mode=ParseMode.HTML
            )
        
        return True
    
    return False

# Update the rate limit decorator to check if user is blocked first
# Update the rate_limit_decorator to also check phone verification
def rate_limit_decorator(func):
    """Decorator to apply rate limiting, block checking, and phone verification to command handlers."""
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        
        # First check if user is blocked
        if user_id in blocked_users:
            update.message.reply_text(
                "⛔ You are blocked due to suspected spam. To appeal this decision, please use the /feedback command to contact our admin."
            )
            return
        
        # Next check if user has verified their phone
        user_data = attendance_tracker.get_user_data(user_id)
        has_phone = user_data and 'Phone Number' in user_data and user_data['Phone Number']
        
        # Get command name for allowing exceptions
        command = update.message.text.split()[0] if update.message and hasattr(update.message, 'text') else ""
        
        # Allow certain commands even without phone verification
        allowed_without_phone = ['/start', '/help', '/verify', '/feedback']
        
        if not has_phone and not any(command.startswith(cmd) for cmd in allowed_without_phone):
            update.message.reply_text(
                "⚠️ For security reasons, you need to verify your phone number before using this command.\n\n"
                "Please use /start or /verify to verify your phone number first."
            )
            return
            
        # Then check rate limits
        if check_rate_limit(update):
            return
            
        return func(update, context, *args, **kwargs)
    return wrapper

def start(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    chat_id = user.id
    update.message.reply_text(f'Welcome to Attendio Bot, {user.first_name}!')

    try:
        user_data = attendance_tracker.get_user_data(user.id)
        
        # Check if user has verified phone
        if user_data and 'Phone Number' in user_data and user_data['Phone Number']:
            # User has verified phone
            attendance_tracker.update_user_chat_id(user.id, chat_id)
            update.message.reply_text(f"Welcome back! Your chat ID has been updated to {chat_id}.")
            return ConversationHandler.END
        else:
            # New user or user hasn't verified phone yet
            return request_phone_number(update, context)
            
    except Exception as e:
        update.message.reply_text(f"Error: {str(e)}")
        logger.error(f"Error in start: {str(e)}")
        return ConversationHandler.END

def get_chat_id(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    user = update.message.from_user
    try:
        user_data = attendance_tracker.get_user_data(user.id)
        if user_data:
            attendance_tracker.update_user_chat_id(user.id, chat_id)
            update.message.reply_text(f"Your chat ID has been updated to {chat_id}.")
        else:
            phone_number = user_data.get('Phone Number', '') if user_data else ''
            attendance_tracker.add_new_user(user.id, user.first_name,phone_number)
            update.message.reply_text(f"Your chat ID has been saved as {chat_id}.")
    except Exception as e:
        update.message.reply_text(f"Error saving chat ID: {str(e)}")
        logger.error(f"Error saving chat ID: {str(e)}")

# Update help_command function to use monospace for admin commands
def help_command(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    help_text = (
        "/start - Start your journey with Attendio Bot\n"
        "/check_attendance - Get a list of attendance in all courses you have registered for\n"
        "/mark_attendance - Mark attendance for a course\n"
        "/edit_attendance - Edit a mistake done while marking attendance for a course\n"
        "/add_course - Add a new course which you have registered for\n"
        "/delete_course - Delete a course which you have dropped\n"
        "/manage_absences - Get suggestions for safe classes to skip\n"
        "/feedback - Provide feedback to help us improve Attendio\n"
        "/help - Check out all the commands which Attendio can help you into\n"
    )
    
    # Update admin commands in help_command
    if str(user_id) == str(config.get('admin_telegram_id')):
        admin_text = (
            "\n<b>Admin Commands:</b>\n"
            "<code>/block [user_id]</code> - Block a user from using the bot\n"
            "<code>/unblock [user_id]</code> - Unblock a previously blocked user\n"
            "<code>/reply [user_id] [message]</code> - Reply directly to a user\n"
            "<code>/announce</code> - Send an announcement to all users\n"
            "<code>/logs [hours]</code> - Get logs for the last N hours (default: 24)\n"
        )
        help_text += admin_text
        update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
    else:
        update.message.reply_text(help_text)

# Mark attendance flow
def mark_attendance_start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user_courses = attendance_tracker.get_user_courses(user_id)

    if not user_courses:
        update.message.reply_text('No courses found. Please add a new course first using /add_course command.')
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(course['Course Nickname'], callback_data=course['Course Code'])] for course in user_courses if course['Course Code']]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Please choose a course:', reply_markup=reply_markup)
    return SELECT_COURSE

def course_selected(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    context.user_data['course_code'] = query.data

    keyboard = [
        [InlineKeyboardButton("Present", callback_data=f"{query.data}:1")],
        [InlineKeyboardButton("Absent", callback_data=f"{query.data}:0")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=f"Mark attendance for {query.data}:", reply_markup=reply_markup)
    return MARK_ATTENDANCE

# functions for the announcement feature
def announce_start(update: Update, context: CallbackContext) -> int:
    """Starts the announcement conversation for admin."""
    user = update.effective_user
    
    # Check if admin
    if str(user.id) != str(config.get('admin_telegram_id')):
        update.message.reply_text("⚠️ You don't have permission to use this command.")
        return ConversationHandler.END
    
    update.message.reply_text(
        "📣 Please enter the announcement message you want to send to all users.\n\n"
        "This will be sent to everyone using the bot. Use /cancel to abort."
    )
    return ANNOUNCEMENT_TEXT

def send_announcement(update: Update, context: CallbackContext) -> int:
    """Sends the announcement to all users."""
    announcement_text = update.message.text
    user = update.effective_user
    
    if str(user.id) != str(config.get('admin_telegram_id')):
        update.message.reply_text("⚠️ You don't have permission to complete this action.")
        return ConversationHandler.END
    
    try:
        # Get all unique users
        data = attendance_tracker.google_sheets.get_all_data()
        unique_users = {}
        
        # First, collect unique users and their chat IDs
        for row in data:
            user_id = str(row['User ID']).strip()
            chat_id = str(row['Chat ID']).strip()
            
            if user_id and chat_id and user_id not in unique_users:
                unique_users[user_id] = chat_id
        
        # Format the announcement
        formatted_announcement = (
            f"📣 <b>ANNOUNCEMENT FROM ADMIN</b> 📣\n\n"
            f"{announcement_text}\n\n"
            f"<i>If you have questions, use /feedback to contact the admin.</i>"
        )
        
        # Send to each user
        success_count = 0
        failed_count = 0
        
        update.message.reply_text(f"Sending announcement to {len(unique_users)} users...")
        
        for user_id, chat_id in unique_users.items():
            try:
                context.bot.send_message(
                    chat_id=chat_id,
                    text=formatted_announcement,
                    parse_mode=ParseMode.HTML
                )
                success_count += 1
            except Exception:
                failed_count += 1
        
        # Report results
        results_message = (
            f"✅ Announcement sent successfully!\n\n"
            f"📊 <b>Statistics:</b>\n"
            f"• Total users: {len(unique_users)}\n"
            f"• Successfully delivered: {success_count}\n"
            f"• Failed to deliver: {failed_count}"
        )
        
        update.message.reply_text(results_message, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        update.message.reply_text(f"❌ Error sending announcement: {str(e)}")
        logger.error(f"Error in send_announcement: {str(e)}")
    
    return ConversationHandler.END


def attendance_response(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    response = query.data.split(':')
    course_code = response[0]
    present_today = int(response[1])

    user = update.callback_query.from_user
    user_id = user.id

    try:
        # Get course data before update
        user_courses = attendance_tracker.get_user_courses(user_id)
        course_before = next((course for course in user_courses if course['Course Code'] == course_code), None)
        
        if not course_before:
            query.edit_message_text(text="Course not found.")
            return ConversationHandler.END
            
        course_nickname = course_before['Course Nickname']
        present_before = int(course_before.get('Present', 0) or 0)
        absent_before = int(course_before.get('Absent', 0) or 0)
        if(present_before+absent_before >0): 
            initial_attendance = (present_before/(absent_before+present_before))*100
        else:
            initial_attendance = 100
        
        # Update attendance
        attendance_tracker.update_attendance(user_id, user.first_name, course_code, course_nickname, present_today)
        
        # Get updated course data
        updated_courses = attendance_tracker.get_user_courses(user_id)
        course_after = next((course for course in updated_courses if course['Course Code'] == course_code), None)
        
        present_after = int(course_after.get('Present', 0) or 0)
        absent_after = int(course_after.get('Absent', 0) or 0)
        streak = int(course_after.get('Streak', 0) or 0)
        
        # Calculate attendance percentage
        total_classes = present_after + absent_after
        attendance_percentage = (present_after / total_classes) * 100 if total_classes > 0 else 100.0
        
        # Format response message
        response_text = f"✅ *Attendance marked for {course_nickname}*\n\n"
        
        if present_today == 1:
            response_text += f"*Present:* {present_before} → {present_after} ✅\n"
            response_text += f"*Absent:* {absent_before} ❌\n"
        else:
            response_text += f"*Present:* {present_before} ✅\n"
            response_text += f"*Absent:* {absent_before} → {absent_after} ❌\n"
            
        response_text += f"*Total Classes:* {total_classes}\n"
        response_text += f"*Attendance:* {initial_attendance: .2f}% → {attendance_percentage:.2f}%\n"
        
        # Add streak if applicable
        if streak > 0:
            response_text += f"🔥 You're on a {streak}-day streak for this course! Keep it up!\n"
            
        # Add advice based on attendance percentage
        if attendance_percentage < 80:
            classes_needed = max(0, 4*absent_after - present_after)
            response_text += f"\nYou need to attend *at least {classes_needed} more* classes to cross the 80% threshold."
        else:
            classes_left = max(0, math.floor((present_after - 4*absent_after)/4))
            if classes_left >= 1:
                response_text += f"\nYou can leave *{classes_left} more* classes & still cross the 80% threshold."
            else:
                response_text += "\nBe careful: Leaving even 1 more class can put you in low attendance."
        
        query.edit_message_text(text=response_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        query.edit_message_text(text=f"Error marking attendance: {str(e)}")
        logger.error(f"Error in attendance_response: {str(e)}")
    return ConversationHandler.END

# Add course flow
def add_course_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Please enter the course nickname:')
    return ADD_COURSE_NAME

def save_course(update: Update, context: CallbackContext) -> int:
    context.user_data['course_nickname'] = update.message.text
    user = update.message.from_user
    user_id = user.id
    course_nickname = context.user_data['course_nickname']
    course_code = f"{user_id}-{course_nickname}"

    try:
        user_data = attendance_tracker.get_user_data(user_id)
        phone_number = user_data.get('Phone Number', '') if user_data else ''

        user_courses = attendance_tracker.get_user_courses(user_id)
        if any(course['Course Nickname'].lower() == course_nickname.lower() for course in user_courses):
            update.message.reply_text(
                "This course nickname already exists. Please choose a different nickname by selecting /add_course or delete the currently existing course by /delete_course."
            )
            return ConversationHandler.END

        attendance_tracker.add_new_course(
            user_id, user.first_name, course_code, course_nickname, 0, 0, phone_number
        )
        
        # Get updated course list after adding
        updated_courses = attendance_tracker.get_user_courses(user_id)
        
        # Build response message
        response = f"Course '{course_nickname}' added successfully.\n\n"
        response += "📋 *Your registered courses:*\n"
        for i, course in enumerate(updated_courses):
            response += f"{i+1}. {course['Course Nickname']}\n"
        
        update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        update.message.reply_text(f"Error adding course: {str(e)}")
        logger.error(f"Error in save_course: {str(e)}")
    return ConversationHandler.END

# Add delete course flow
def delete_course_start(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    user_id = user.id

    try:
        user_courses = attendance_tracker.get_user_courses(user_id)

        if not user_courses:
            update.message.reply_text("No courses found. Please add a course first using /add_course.")
            return ConversationHandler.END

        keyboard = [[InlineKeyboardButton(f"Delete {course['Course Nickname']}", callback_data=f"delete_confirm:{course['Course Code']}")] for course in user_courses]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Please choose a course to delete:', reply_markup=reply_markup)
        return SELECT_COURSE

    except Exception as e:
        update.message.reply_text(f"Error listing courses: {str(e)}")
        logger.error(f"Error in delete_course_start: {str(e)}")
        return ConversationHandler.END

def delete_course_confirm(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    course_code = query.data.split(':')[1]
    context.user_data['course_code_to_delete'] = course_code

    keyboard = [
        [InlineKeyboardButton("Yes, Delete", callback_data=f"delete:{course_code}"),
         InlineKeyboardButton("No, Cancel", callback_data="cancel_delete")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text=f"Are you sure you want to delete course {course_code}?",
        reply_markup=reply_markup
    )
    return MARK_ATTENDANCE

def delete_course(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    course_code = query.data.split(':')[1]
    user = update.callback_query.from_user
    user_id = user.id

    try:
        # Get course nickname before deleting
        user_courses = attendance_tracker.get_user_courses(user_id)
        deleted_course_name = next((course['Course Nickname'] for course in user_courses 
                                    if course['Course Code'] == course_code), course_code)
        
        # Delete the course
        attendance_tracker.delete_course(user_id, course_code)
        
        # Get updated course list after deletion
        updated_courses = attendance_tracker.get_user_courses(user_id)
        
        # Build response message
        response = f"Course '{deleted_course_name}' deleted successfully.\n\n"
        
        if updated_courses:
            response += "📋 *Your remaining courses:*\n"
            for i, course in enumerate(updated_courses):
                response += f"{i+1}. {course['Course Nickname']}\n"
        else:
            response += "You have no courses registered. Use /add_course to add a new course."
        
        query.edit_message_text(text=response, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        query.edit_message_text(text=f"Error deleting course: {str(e)}")
        logger.error(f"Error in delete_course: {str(e)}")
    return ConversationHandler.END

def cancel_delete(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    query.edit_message_text(text="Course deletion cancelled.")
    return ConversationHandler.END

# Add edit attendance flow
def edit_attendance_start(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    user_id = user.id

    try:
        user_courses = attendance_tracker.get_user_courses(user_id)

        if not user_courses:
            update.message.reply_text("No courses found. Please add a course first using /add_course.")
            return ConversationHandler.END

        keyboard = [[InlineKeyboardButton(f"Edit Attendance {course['Course Nickname']}", callback_data=f"edit_attendance:{course['Course Code']}")] for course in user_courses]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Please choose a course to edit attendance:', reply_markup=reply_markup)
        return SELECT_COURSE

    except Exception as e:
        update.message.reply_text(f"Error listing courses: {str(e)}")
        logger.error(f"Error in edit_attendance_start: {str(e)}")
        return ConversationHandler.END

def edit_attendance_display(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    course_code = query.data.split(':')[1]
    context.user_data['course_code_to_edit'] = course_code

    user = update.callback_query.from_user
    user_id = user.id

    try:
        course = next((course for course in attendance_tracker.get_user_courses(user_id) if course['Course Code'] == course_code), None)

        if not course:
            query.edit_message_text("Course not found.")
            return ConversationHandler.END

        # Store initial values for comparison when "Done" is clicked
        present = int(course['Present'])
        absent = int(course['Absent'])
        context.user_data['initial_present'] = present
        context.user_data['initial_absent'] = absent

        keyboard = []
        present_row = []
        absent_row = []

        present_row.append(InlineKeyboardButton(f"Present ➖", callback_data=f"decrease_present:{course_code}"))
        present_row.append(InlineKeyboardButton(f"Present ➕", callback_data=f"increase_present:{course_code}"))
        keyboard.append(present_row)

        absent_row.append(InlineKeyboardButton(f"Absent ➖", callback_data=f"decrease_absent:{course_code}"))
        absent_row.append(InlineKeyboardButton(f"Absent ➕", callback_data=f"increase_absent:{course_code}"))
        keyboard.append(absent_row)

        keyboard.append([InlineKeyboardButton("✅ Done", callback_data=f"done:{course_code}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text=f"Current Attendance for {course['Course Nickname']}:\nPresent: {present}\nAbsent: {absent}\n\nChoose an option to edit:",
            reply_markup=reply_markup
        )
        return MARK_ATTENDANCE

    except Exception as e:
        query.edit_message_text(f"Error displaying attendance: {str(e)}")
        logger.error(f"Error in edit_attendance_display: {str(e)}")
        return ConversationHandler.END

def edit_attendance_update(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    data = query.data.split(':')
    action = data[0]
    course_code = data[1]

    user = update.callback_query.from_user
    user_id = user.id

    try:
        # Get current course data
        user_courses = attendance_tracker.get_user_courses(user_id)
        course = next((course for course in user_courses if course['Course Code'] == course_code), None)
        
        if not course:
            query.edit_message_text(text="Course not found.")
            return ConversationHandler.END
            
        course_nickname = course['Course Nickname']
        present = int(course.get('Present', 0) or 0)
        absent = int(course.get('Absent', 0) or 0)

        # Perform the requested action
        if action == 'increase_present':
            present += 1
        elif action == 'decrease_present':
            present = max(0, present - 1)
        elif action == 'increase_absent':
            absent += 1
        elif action == 'decrease_absent':
            absent = max(0, absent - 1)
        elif action == 'done':
            # Get initial values stored when editing began
            initial_present = context.user_data.get('initial_present', 0)
            initial_absent = context.user_data.get('initial_absent', 0)
            if(initial_present+initial_absent >0): 
                initial_attendance = (initial_present/(initial_absent+initial_present))*100
            else:
                initial_attendance = 100
            # Update attendance
            attendance_tracker.update_attendance_manual(user_id, course_code, present, absent)
            
            # Calculate attendance percentage
            total_classes = present + absent
            attendance_percentage = (present / total_classes) * 100 if total_classes > 0 else 100.0
            
            # Format final response with cumulative changes
            response_text = f"✅ *Attendance updated for {course_nickname}*\n\n"
            
            # Only show the arrows when there's actually been a change
            if present != initial_present:
                response_text += f"*Present:* {initial_present} → {present} ✅\n"
            else:
                response_text += f"*Present:* {present} ✅\n"
                
            if absent != initial_absent:
                response_text += f"*Absent:* {initial_absent} → {absent} ❌\n"
            else:
                response_text += f"*Absent:* {absent} ❌\n"
                
            response_text += f"*Total Classes:* {total_classes}\n"
            response_text += f"*Attendance:* {initial_attendance: .2f}% → {attendance_percentage:.2f}%"
            
            query.edit_message_text(text=response_text, parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END

        # Update attendance in database for immediate reflection
        attendance_tracker.update_attendance_manual(user_id, course_code, present, absent)
        
        # Just show the current values during editing (no arrows, no streak)
        keyboard = []
        present_row = []
        absent_row = []

        present_row.append(InlineKeyboardButton(f"Present ➖", callback_data=f"decrease_present:{course_code}"))
        present_row.append(InlineKeyboardButton(f"Present ➕", callback_data=f"increase_present:{course_code}"))
        keyboard.append(present_row)

        absent_row.append(InlineKeyboardButton(f"Absent ➖", callback_data=f"decrease_absent:{course_code}"))
        absent_row.append(InlineKeyboardButton(f"Absent ➕", callback_data=f"increase_absent:{course_code}"))
        keyboard.append(absent_row)

        keyboard.append([InlineKeyboardButton("✅ Done", callback_data=f"done:{course_code}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text=f"Editing Attendance for {course_nickname}:\nPresent: {present}\nAbsent: {absent}\n\nContinue editing or click '✅ Done':",
            reply_markup=reply_markup
        )
        return MARK_ATTENDANCE

    except Exception as e:
        query.edit_message_text(text=f"Error updating attendance: {str(e)}")
        logger.error(f"Error in edit_attendance_update: {str(e)}")
        return ConversationHandler.END

def send_reminders():
    """Sends reminders to all users."""
    try:
        all_data = attendance_tracker.google_sheets.get_all_data()
        user_courses = {}
        for row in all_data:
            user_id = str(row['User ID']).strip()
            if user_id not in user_courses:
                user_courses[user_id] = []
            user_courses[user_id].append(row)

        for user_id, courses in user_courses.items():
            attendance_status = "<b>Attendance Status:</b>\n"
            for i, course in enumerate(courses):
                course_nickname = course['Course Nickname']
                present = int(course['Present'])
                absent = int(course['Absent'])

                total_classes = present + absent
                attendance_percentage = (present / total_classes) * 100 if total_classes > 0 else 100.0

                if attendance_percentage < attendance_tracker.attendance_threshold:
                    attendance_status += f"<b>{i + 1}. {course_nickname}:</b> ⚠️\n"
                    attendance_status += f"  <b>Attendance:</b> {attendance_percentage:.2f}%\n"
                    attendance_status += f"  You need to attend <b>at least {4*absent - present} more</b> classes to cross the 80% threshold.\n"
                    attendance_status += "\n"
                else:
                    attendance_status += f"<b>{i + 1}. {course_nickname}:</b> ✅\n"
                    attendance_status += f"  <b>Attendance:</b> {attendance_percentage:.2f}%\n"
                    classes_left=max(0,math.floor((present- 4*absent)/4))
                    if classes_left >= 1:
                        attendance_status += f"  You can leave <b>{classes_left} more</b> classes & still cross the 80% threshold.\n"
                    else:
                        attendance_status += f"  You are in the safe zone. Keep up the good work! ✅ \n <i>Be Alert:</i> Leaving even 1 class can put you in low attendance.\n"
                    attendance_status += "\n"

            attendance_status += f"Please mark your attendance using /mark_attendance command if not updated for {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d.%B')}.\n"
            chat_id = courses[0].get('Chat ID')
            if chat_id:
                try:
                    attendance_tracker.google_sheets.send_message(chat_id, attendance_status, parse_mode=ParseMode.HTML)
                except Exception as e:
                    print(f"Error sending reminder to user {user_id}: {e}")
            else:
                print(f"No chat ID found for user {user_id}. Skipping reminder.")

    except Exception as e:
        print(f"Error sending reminders: {e}")

def calculate_classes_needed(present, absent, safe_zone_attendance):
    total_classes = present + absent
    classes_needed = max(0,4*absent - present)
    classes_left = max(0,math.floor((present- 4*absent)/4))
    return classes_needed, classes_left

@rate_limit_decorator
def check_attendance(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id

    try:
        user_courses = attendance_tracker.get_user_courses(user_id)

        if not user_courses:
            update.message.reply_text("No courses found. Please add a course first using /add_course.")
            return

        attendance_status = "*Attendance Status:*\n"
        for i, course in enumerate(user_courses):
            course_nickname = course['Course Nickname']
            
            # Handle empty strings or None values for Present
            present_val = course.get('Present', '0')
            present = 0 if present_val == '' or present_val is None else int(present_val)
            
            # Handle empty strings or None values for Absent
            absent_val = course.get('Absent', '0')
            absent = 0 if absent_val == '' or absent_val is None else int(absent_val)
            
            last_updated = course.get('Last Updated', 'Never')
            
            # Handle empty strings or None values for Streak
            streak_val = course.get('Streak', '0')
            streak = 0 if streak_val == '' or streak_val is None else int(streak_val)

            total_classes = present + absent
            attendance_percentage = (present / total_classes) * 100 if total_classes > 0 else 100.0

            classes_needed, classes_left = calculate_classes_needed(present, absent, 80)
            status_emoji = "⚠️" if attendance_percentage < 80 else "✅"

            attendance_status += f"*{i + 1}. {course_nickname}:* {status_emoji}\n"
            attendance_status += f"  *Present:* {present} ✅\n"
            attendance_status += f"  *Absent:* {absent} ❌\n"
            attendance_status += f"  *Total Classes:* {total_classes}\n"
            attendance_status += f"  *Attendance:* {attendance_percentage:.2f}%\n"
            attendance_status += f"  *Last Updated:* {last_updated}\n"

            # Streak System
            if streak > 0:
                attendance_status += f"  🔥 You're on a {streak}-class streak! Keep it up!\n"

            if classes_needed > 0:
                attendance_status += f"  *Classes Needed:* You need to be present in at least {classes_needed} more classes to cross the 80% threshold.\n"
            else:
                attendance_status += "  You are in the safe zone. Keep up the good work! ✅\n"
                if classes_left >= 1:
                    attendance_status += f"  You can leave {classes_left} more classes & still cross the 80% threshold.\n"
                else:
                    attendance_status += f"  Be Careful: Leaving even 1 more class can put you in low attendance.\n"

            # Visual Progress Bar
            bar_length = 20
            if total_classes > 0:
                filled_length = int(round(bar_length * present / total_classes))
            # else:
            #     filled_length = 0  # Or any other default value you want to use when total_classes is zero
                bar = '█' * filled_length + '-' * (bar_length - filled_length)
                attendance_status += f"  📈 [{bar}] {attendance_percentage:.0f}%\n\n"

        update.message.reply_text(attendance_status, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        update.message.reply_text(f"Error checking attendance: {str(e)}")
        logger.error(f"Error in check_attendance: {str(e)}")

# Update the feedback handling functions to work for blocked users
def feedback_start(update: Update, context: CallbackContext) -> int:
    """Starts the feedback conversation - available even to blocked users."""
    user_id = update.effective_user.id
    logger.info(f"Starting feedback conversation with user {user_id}")
    
    # Special message for blocked users
    if user_id in blocked_users:
        message = "You have been blocked due to suspected spam. You can use this feedback form to contact our admin and appeal your block. Please explain why you believe your block should be removed:"
    else:
        message = "Please share your feedback about Attendio bot. Your insights help us improve!"
    
    # Try both ways to send the message
    try:
        update.message.reply_text(message)
        logger.info(f"Initial feedback prompt sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error sending feedback prompt: {str(e)}")
        try:
            # Alternative method to send message
            context.bot.send_message(chat_id=user_id, text=message)
            logger.info(f"Initial feedback prompt sent via alternative method to user {user_id}")
        except Exception as e2:
            logger.error(f"Second error sending feedback prompt: {str(e2)}")
    
    return FEEDBACK_TEXT

# Update save_feedback function for monospace formatting in admin message
def save_feedback(update: Update, context: CallbackContext) -> int:
    """Forwards user feedback to admin and confirms receipt to user."""
    feedback_text = update.message.text
    user = update.message.from_user
    user_id = user.id
    
    logger.info(f"Received feedback from user {user_id}")
    
    try:
        now = datetime.now(pytz.timezone('Asia/Kolkata'))
        timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
        
        # Forward to admin
        if 'admin_telegram_id' in config:
            user_mention = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'

            # Special marking for messages from blocked users
            if user_id in blocked_users:
                admin_message = f"📬 <b>Message from BLOCKED User:</b>\n\n" \
                               f"👤 From: {user_mention} (ID: {user.id})\n" \
                               f"⏰ Time: {timestamp}\n\n" \
                               f"📝 <b>Message:</b>\n{feedback_text}\n\n" \
                               f" Reply {user.name} using <code>/reply {user_id} [message]</code>\n\n" \
                               f"<i>This user is currently blocked. Use <code>/unblock {user.id}</code> to unblock them.</i>"
                user_reply = "Your message has been sent to our admin. We will reach you back soon."
            else:
                admin_message = f"📬 <b>New Feedback Received:</b>\n\n" \
                               f"👤 From: {user_mention} (ID: {user.id})\n" \
                               f"⏰ Time: {timestamp}\n\n" \
                               f"📝 <b>Feedback:</b>\n{feedback_text}\n\n" \
                               f" Reply {user.name} using <code>/reply {user_id} [message]</code>\n\n"
                user_reply = "Your feedback has been recorded! We appreciate your help in making Attendio better."
            
            # Send to admin
            try:
                context.bot.send_message(
                    chat_id=config['admin_telegram_id'],
                    text=admin_message,
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"Feedback from user {user_id} forwarded to admin")
            except Exception as e:
                logger.error(f"Error sending feedback to admin: {str(e)}")
            
            # Reply to user - try both methods
            try:
                update.message.reply_text(user_reply)
                logger.info(f"Feedback confirmation sent to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending feedback confirmation: {str(e)}")
                # Try direct message as backup
                try:
                    context.bot.send_message(chat_id=user_id, text=user_reply)
                    logger.info(f"Feedback confirmation sent via alternative method to user {user_id}")
                except Exception as e2:
                    logger.error(f"Second error sending feedback confirmation: {str(e2)}")
        else:
            logger.error("Admin telegram ID not configured for feedback forwarding")
            try:
                update.message.reply_text("Thanks for your feedback! However, our admin notification system is not configured yet.")
            except Exception as e:
                logger.error(f"Error sending feedback config error message: {str(e)}")
    except Exception as e:
        logger.error(f"Major error in save_feedback: {str(e)}")
        try:
            update.message.reply_text("Sorry, there was a problem processing your feedback. Please try again later.")
        except:
            pass
    
    return ConversationHandler.END

# Invalid input handling
def handle_invalid_input(update: Update, context: CallbackContext) -> None:
    """Handle messages that aren't recognized commands."""
    update.message.reply_text(
        "I'm sorry, I didn't understand that command. Here are the available commands:\n\n"
        "/start - Start your journey with Attendio Bot\n"
        "/check_attendance - Get a list of attendance in all courses\n"
        "/mark_attendance - Mark attendance for a course\n"
        "/edit_attendance - Edit a mistake done while marking attendance\n"
        "/add_course - Add a new course\n"
        "/delete_course - Delete a course\n"
        "/manage_absences - Get suggestions for safe classes to skip\n"
        "/feedback - Provide feedback about the bot\n"
        "/help - Check out all the commands Attendio can help you with"
    )
    
def manage_absences(update: Update, context: CallbackContext) -> None:
    """Suggests courses that can be safely skipped."""
    user = update.message.from_user
    user_id = user.id

    try:
        safe_courses = attendance_tracker.calculate_safe_skip(user_id)

        if not safe_courses:
            update.message.reply_text("Sorry, you can't skip any class safely right now.")
            return

        message = "You can afford to skip these classes today:\n"
        for course in safe_courses:
            message += f"- {course['Course Nickname']} ({course['Attendance']:.0f}%)\n"

        update.message.reply_text(message)

    except Exception as e:
        update.message.reply_text(f"Error managing absences: {str(e)}")
        logger.error(f"Error in manage_absences: {str(e)}")

def cancel(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('Bye! Hope to see you around.')
    return ConversationHandler.END

def request_phone_number(update: Update, context: CallbackContext) -> int:
    """Request the user's phone number for verification."""
    keyboard = [[KeyboardButton("Share Contact", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text(
        "📱 To verify your identity and prevent spam, please share your contact information by clicking the button below.", 
        reply_markup=reply_markup
    )
    return PHONE_VERIFICATION

def handle_phone_number(update: Update, context: CallbackContext) -> int:
    """Handle the shared contact information."""
    user = update.message.from_user
    phone_number = update.message.contact.phone_number
    user_id = user.id
    chat_id = user.id

    try:
        user_data = attendance_tracker.get_user_data(user_id)
        if user_data:
            # Update existing user with phone
            attendance_tracker.update_user_chat_id(user_id, chat_id)
            attendance_tracker.update_user_phone(user_id, phone_number)
            update.message.reply_text(
                "✅ Your phone number has been verified successfully! You can now use all features of Attendio Bot.",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            # New user, create account with phone
            attendance_tracker.add_new_user(user_id, user.first_name, chat_id, phone_number)
            update.message.reply_text(
                "✅ Thank you! Your account has been created. Please add your first course using /add_course.",
                reply_markup=ReplyKeyboardRemove()
            )
        
        # Notify admin about new user verification
        if 'admin_telegram_id' in config:

            user_mention = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'

            admin_message = f"✅ New User Verified:\n\n" \
                           f"👤 User: {user_mention} (ID:{user.id})\n" \
                           f"⏰ Time: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')}\n\n" \
                           f"📞 Phone: {phone_number}\n"
            
            context.bot.send_message(
                chat_id=config['admin_telegram_id'],
                text=admin_message,
                parse_mode=ParseMode.HTML
            )
            
        return ConversationHandler.END
    except Exception as e:
        update.message.reply_text(f"❌ Error verifying phone: {str(e)}", reply_markup=ReplyKeyboardRemove())
        logger.error(f"Error in handle_phone_number: {str(e)}")
        return ConversationHandler.END
def verify_command(update: Update, context: CallbackContext) -> int:
    """Command to manually re-verify phone number."""
    return request_phone_number(update, context)


# Schedule daily logs to admin
if 'admin_telegram_id' in config:
    schedule_daily_logs(updater.bot, config['admin_telegram_id'])

# Add this function for the admin to get logs
def get_logs(update: Update, context: CallbackContext) -> None:
    """Admin command to get logs."""
    user = update.effective_user
    
    # Check if admin
    if str(user.id) != str(config.get('admin_telegram_id')):
        update.message.reply_text("⚠️ You don't have permission to use this command.")
        return
    
    # Get hours parameter (default 24)
    hours = 24
    if context.args and context.args[0].isdigit():
        hours = int(context.args[0])
    
    update.message.reply_text(f"Fetching logs from the last {hours} hours...")
    send_logs_to_admin(context.bot, user.id, hours)


# Block user function
def block_user(update: Update, context: CallbackContext) -> None:
    """Admin command to block a user."""
    user = update.effective_user
    
    # Check if admin
    if str(user.id) != str(config.get('admin_telegram_id')):
        update.message.reply_text("⚠️ You don't have permission to use this command.")
        return
    
    # Get user ID to block
    try:
        user_id = int(context.args[0])
        blocked_users.add(user_id)
        update.message.reply_text(f"User {user_id} has been blocked.")
        
        # Try to notify the user they've been blocked
        try:
            context.bot.send_message(
                chat_id=user_id,
                text="You have been blocked from using this bot due to suspicious activity. Contact the administrator if you believe this is an error."
            )
        except:
            pass
            
    except (IndexError, ValueError):
        update.message.reply_text("Usage: <code>/block [user_id]</code>", parse_mode=ParseMode.HTML)

# Unblock user function
def unblock_user(update: Update, context: CallbackContext) -> None:
    """Admin command to unblock a user."""
    user = update.effective_user
    
    # Check if admin
    if str(user.id) != str(config.get('admin_telegram_id')):
        update.message.reply_text("⚠️ You don't have permission to use this command.")
        return
    
    # Get user ID to unblock
    try:
        user_id = int(context.args[0])
        if user_id in blocked_users:
            blocked_users.remove(user_id)
            update.message.reply_text(f"User {user_id} has been unblocked.")
            
            # Try to notify the user they've been unblocked
            try:
                context.bot.send_message(
                    chat_id=user_id,
                    text="You have been unblocked and can now use the bot again."
                )
            except:
                pass
        else:
            update.message.reply_text(f"User {user_id} is not blocked.")
    except (IndexError, ValueError):
        update.message.reply_text("Usage: <code>/unblock [user_id]</code>", parse_mode=ParseMode.HTML)


def reply_to_user(update: Update, context: CallbackContext) -> None:
    """Admin command to reply to a user."""
    user = update.effective_user
    
    # Check if admin
    if str(user.id) != str(config.get('admin_telegram_id')):
        update.message.reply_text("⚠️ You don't have permission to use this command.")
        return
    
    try:
        # Extract user_id and message from the command
        if len(context.args) < 2:
            update.message.reply_text(
                "Usage: <code>/reply [user_id] [message]</code>", 
                parse_mode=ParseMode.HTML
            )
            return
            
        try:
            # Convert user_id to integer
            user_id = int(context.args[0])
        except ValueError:
            update.message.reply_text("❌ Invalid user ID format. User ID must be a number.")
            return
            
        # Join all remaining args as the message
        message = ' '.join(context.args[1:])
        
        # Format the reply
        admin_reply = f"📬 <b>Reply from Admin:</b>\n\n{message}\n\n<i>To respond, use the /feedback command.</i>"
        
        # Check if user exists in our database
        user_data = attendance_tracker.get_user_data(user_id)
        if not user_data:
            update.message.reply_text(f"⚠️ Warning: User {user_id} doesn't exist in database, but trying to send message anyway.")
        
        # Send the message to the user
        context.bot.send_message(
            chat_id=user_id,
            text=admin_reply,
            parse_mode=ParseMode.HTML
        )
        
        # Confirm to admin
        update.message.reply_text(f"✅ Reply sent to user {user_id}.")
        
    except telegram.error.BadRequest as e:
        if "chat not found" in str(e).lower():
            update.message.reply_text(f"❌ Error: User {context.args[0]} hasn't interacted with the bot or has blocked it.")
        else:
            update.message.reply_text(f"❌ Telegram error: {str(e)}")
        logger.error(f"BadRequest in reply_to_user: {str(e)}")
    except Exception as e:
        update.message.reply_text(f"❌ Error sending reply: {str(e)}")
        logger.error(f"Error in reply_to_user: {str(e)}")


def main() -> None:
    updater = Updater(config['telegram_bot_token'])
    dispatcher = updater.dispatcher

    # Start handler needs to be a conversation handler now
    start_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],  # Don't rate limit start - new users need access
        states={
            PHONE_VERIFICATION: [MessageHandler(Filters.contact, handle_phone_number)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Add separate verify command
    verify_handler = ConversationHandler(
        entry_points=[CommandHandler('verify', rate_limit_decorator(verify_command))],
        states={
            PHONE_VERIFICATION: [MessageHandler(Filters.contact, handle_phone_number)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Define the feedback handler BEFORE adding it to the dispatcher
    feedback_handler = ConversationHandler(
        entry_points=[CommandHandler('feedback', feedback_start)],
        states={
            FEEDBACK_TEXT: [MessageHandler(Filters.text & ~Filters.command, save_feedback)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add handlers at the beginning
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(verify_handler)
    
    # Register feedback handler next
    dispatcher.add_handler(feedback_handler)
    
    # Apply rate limits to other conversation handlers
    mark_attendance_handler = ConversationHandler(
        entry_points=[CommandHandler('mark_attendance', rate_limit_decorator(mark_attendance_start))],
        states={
            SELECT_COURSE: [CallbackQueryHandler(course_selected)],
            MARK_ATTENDANCE: [CallbackQueryHandler(attendance_response, pattern='^[A-Za-z0-9-]+:[01]$')]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    add_course_handler = ConversationHandler(
        entry_points=[CommandHandler('add_course', rate_limit_decorator(add_course_start))],
        states={
            ADD_COURSE_NAME: [MessageHandler(Filters.text & ~Filters.command, save_course)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    delete_course_handler = ConversationHandler(
        entry_points=[CommandHandler('delete_course', rate_limit_decorator(delete_course_start))],
        states={
            SELECT_COURSE: [CallbackQueryHandler(delete_course_confirm, pattern='^delete_confirm:.*$')],
            MARK_ATTENDANCE: [CallbackQueryHandler(delete_course, pattern='^delete:.*$'),
                              CallbackQueryHandler(cancel_delete, pattern='^cancel_delete$')]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    edit_attendance_handler = ConversationHandler(
        entry_points=[CommandHandler('edit_attendance', rate_limit_decorator(edit_attendance_start))],
        states={
            SELECT_COURSE: [CallbackQueryHandler(edit_attendance_display, pattern='^edit_attendance:.*$')],
            MARK_ATTENDANCE: [CallbackQueryHandler(edit_attendance_update, pattern='^(increase_present|decrease_present|increase_absent|decrease_absent|done):.*$')],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Phone verification also needs to be accessible
    phone_verification_handler = ConversationHandler(
        entry_points=[CommandHandler('verify_phone', request_phone_number)],
        states={
            PHONE_VERIFICATION: [MessageHandler(Filters.contact, handle_phone_number)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    # Add the announcement handler in main()
    announce_handler = ConversationHandler(
        entry_points=[CommandHandler('announce', announce_start)],
        states={
            ANNOUNCEMENT_TEXT: [MessageHandler(Filters.text & ~Filters.command, send_announcement)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    dispatcher.add_handler(mark_attendance_handler)
    dispatcher.add_handler(add_course_handler)
    dispatcher.add_handler(delete_course_handler)
    dispatcher.add_handler(edit_attendance_handler)
    dispatcher.add_handler(phone_verification_handler)  # No rate limit
    dispatcher.add_handler(CommandHandler("check_attendance", rate_limit_decorator(check_attendance)))
    dispatcher.add_handler(CommandHandler("get_chat_id", rate_limit_decorator(get_chat_id)))
    dispatcher.add_handler(CommandHandler("help", rate_limit_decorator(help_command)))
    dispatcher.add_handler(CommandHandler("manage_absences", rate_limit_decorator(manage_absences)))
    
    # Add these handlers in the main() function
    dispatcher.add_handler(CommandHandler("block", block_user))
    dispatcher.add_handler(CommandHandler("unblock", unblock_user))
    dispatcher.add_handler(CommandHandler("reply", reply_to_user))
    dispatcher.add_handler(announce_handler)
    dispatcher.add_handler(CommandHandler("logs", get_logs))
    # Add handler for invalid inputs - this should be the last handler
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_invalid_input))

    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Kolkata'))
    scheduler.add_job(send_reminders, 'cron', hour=20, minute=15, timezone=pytz.timezone('Asia/Kolkata'))  # Example time
#     scheduler.start()

#     updater.start_polling()
#     updater.idle()

# if __name__ == '__main__':
#     main()

# def main() -> None:
#     updater = Updater(config['telegram_bot_token'])
#     dispatcher = updater.dispatcher

#     # Start handler needs to be a conversation handler now
#     start_handler = ConversationHandler(
#         entry_points=[CommandHandler('start', start)],  # Don't rate limit start - new users need access
#         states={
#             PHONE_VERIFICATION: [MessageHandler(Filters.contact, handle_phone_number)]
#         },
#         fallbacks=[CommandHandler('cancel', cancel)]
#     )
    
#     # Add separate verify command
#     verify_handler = ConversationHandler(
#         entry_points=[CommandHandler('verify', rate_limit_decorator(verify_command))],
#         states={
#             PHONE_VERIFICATION: [MessageHandler(Filters.contact, handle_phone_number)]
#         },
#         fallbacks=[CommandHandler('cancel', cancel)]
#     )
    
#     # Define the feedback handler BEFORE adding it to the dispatcher
#     feedback_handler = ConversationHandler(
#         entry_points=[CommandHandler('feedback', feedback_start)],
#         states={
#             FEEDBACK_TEXT: [MessageHandler(Filters.text & ~Filters.command, save_feedback)]
#         },
#         fallbacks=[CommandHandler('cancel', cancel)],
#     )
    
#     # Add handlers at the beginning
#     dispatcher.add_handler(start_handler)
#     dispatcher.add_handler(verify_handler)
    
#     # Register feedback handler next
#     dispatcher.add_handler(feedback_handler)
    
#     # Apply rate limits to other conversation handlers
#     mark_attendance_handler = ConversationHandler(
#         entry_points=[CommandHandler('mark_attendance', rate_limit_decorator(mark_attendance_start))],
#         states={
#             SELECT_COURSE: [CallbackQueryHandler(course_selected)],
#             MARK_ATTENDANCE: [CallbackQueryHandler(attendance_response, pattern='^[A-Za-z0-9-]+:[01]$')]
#         },
#         fallbacks=[CommandHandler('cancel', cancel)],
#     )

#     add_course_handler = ConversationHandler(
#         entry_points=[CommandHandler('add_course', rate_limit_decorator(add_course_start))],
#         states={
#             ADD_COURSE_NAME: [MessageHandler(Filters.text & ~Filters.command, save_course)]
#         },
#         fallbacks=[CommandHandler('cancel', cancel)],
#     )

#     delete_course_handler = ConversationHandler(
#         entry_points=[CommandHandler('delete_course', rate_limit_decorator(delete_course_start))],
#         states={
#             SELECT_COURSE: [CallbackQueryHandler(delete_course_confirm, pattern='^delete_confirm:.*$')],
#             MARK_ATTENDANCE: [CallbackQueryHandler(delete_course, pattern='^delete:.*$'),
#                               CallbackQueryHandler(cancel_delete, pattern='^cancel_delete$')]
#         },
#         fallbacks=[CommandHandler('cancel', cancel)],
#     )

#     edit_attendance_handler = ConversationHandler(
#         entry_points=[CommandHandler('edit_attendance', rate_limit_decorator(edit_attendance_start))],
#         states={
#             SELECT_COURSE: [CallbackQueryHandler(edit_attendance_display, pattern='^edit_attendance:.*$')],
#             MARK_ATTENDANCE: [CallbackQueryHandler(edit_attendance_update, pattern='^(increase_present|decrease_present|increase_absent|decrease_absent|done):.*$')],
#         },
#         fallbacks=[CommandHandler('cancel', cancel)],
#     )

#     # Phone verification also needs to be accessible
#     phone_verification_handler = ConversationHandler(
#         entry_points=[CommandHandler('verify_phone', request_phone_number)],
#         states={
#             PHONE_VERIFICATION: [MessageHandler(Filters.contact, handle_phone_number)]
#         },
#         fallbacks=[CommandHandler('cancel', cancel)],
#     )
#     # Add the announcement handler in main()
#     announce_handler = ConversationHandler(
#         entry_points=[CommandHandler('announce', announce_start)],
#         states={
#             ANNOUNCEMENT_TEXT: [MessageHandler(Filters.text & ~Filters.command, send_announcement)]
#         },
#         fallbacks=[CommandHandler('cancel', cancel)],
#     )

#     dispatcher.add_handler(mark_attendance_handler)
#     dispatcher.add_handler(add_course_handler)
#     dispatcher.add_handler(delete_course_handler)
#     dispatcher.add_handler(edit_attendance_handler)
#     dispatcher.add_handler(phone_verification_handler)  # No rate limit
#     dispatcher.add_handler(CommandHandler("check_attendance", rate_limit_decorator(check_attendance)))
#     dispatcher.add_handler(CommandHandler("get_chat_id", rate_limit_decorator(get_chat_id)))
#     dispatcher.add_handler(CommandHandler("help", rate_limit_decorator(help_command)))
#     dispatcher.add_handler(CommandHandler("manage_absences", rate_limit_decorator(manage_absences)))
    
#     # Add these handlers in the main() function
#     dispatcher.add_handler(CommandHandler("block", block_user))
#     dispatcher.add_handler(CommandHandler("unblock", unblock_user))
#     dispatcher.add_handler(CommandHandler("reply", reply_to_user))
#     dispatcher.add_handler(announce_handler)
#     # Add handler for invalid inputs - this should be the last handler
#     dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_invalid_input))
#     # Set up scheduler
#     scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Kolkata'))
    scheduler.add_job(send_reminders, 'cron', hour=20, minute=35, timezone=pytz.timezone('Asia/Kolkata'))
    scheduler.start()
    
    # Start the bot differently based on environment
    if os.getenv("RAILWAY_STATIC_URL"):
        # We're on Railway, use webhook
        print("Starting bot with webhook")
        PORT = int(os.getenv('PORT', '8080'))
        WEBHOOK_URL = os.getenv('RAILWAY_STATIC_URL') + "/" + config['telegram_bot_token']
        
        # Start webhook
        updater.start_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=config['telegram_bot_token'],
            webhook_url=WEBHOOK_URL
        )
        print(f"Webhook set up on {WEBHOOK_URL}")
    else:
        # Local development - use polling
        print("Starting bot with polling")
        updater.start_polling()
        
    updater.idle()

    
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Kolkata'))
    scheduler.add_job(send_reminders, 'cron', hour=20, minute=15, timezone=pytz.timezone('Asia/Kolkata'))  # Example time
    scheduler.start()

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
