import logging
import json
from datetime import datetime
import pytz
import math

class AttendanceTracker:
    def __init__(self, google_sheets, attendance_threshold):
        self.google_sheets = google_sheets
        self.attendance_threshold = attendance_threshold

    def get_user_data(self, user_id):
        """Retrieves user data from the Google Sheet."""
        try:
            data = self.google_sheets.get_all_data()
            for row in data:
                if str(row['User ID']).strip() == str(user_id).strip():
                    return row
            return None  # User not found
        except Exception as e:
            print(f"Error retrieving user data: {e}")

    def update_user_chat_id(self, user_id, chat_id):
        """Updates the chat ID for a specific user in the Google Sheet."""
        try:
            data = self.google_sheets.get_all_data()
            for i, row in enumerate(data):
                if str(row['User ID']).strip() == str(user_id).strip():
                    row_index = i + 2  # Add 2 to account for header row and 0-based indexing
                    self.google_sheets.update_cell(row_index, 'Chat ID', chat_id)
                    print(f"Chat ID updated for user {user_id} to {chat_id}")
                    return
            print(f"User {user_id} not found.")
        except Exception as e:
            print(f"Error updating chat ID: {e}")

    def update_user_phone(self, user_id, phone_number):
        """Updates a user's phone number in the Google Sheet."""
        try:
            data = self.google_sheets.get_all_data()
            for i, row in enumerate(data):
                if str(row['User ID']).strip() == str(user_id).strip():
                    row_index = i + 2  # Add 2 to account for header row and 0-based indexing
                    self.google_sheets.update_cell(row_index, 'Phone Number', phone_number)
                    print(f"Phone number updated for user {user_id}: {phone_number}")
                    return True
            return False
        except Exception as e:
            print(f"Error updating phone number: {e}")
            return False

    def add_new_user(self, user_id, user_name, chat_id, phone_number=''):
        """Adds a new user to the Google Sheet."""
        try:
            # Add a new row with phone number (add an extra empty field for Streak)
            self.google_sheets.add_row([user_id, user_name, '', '', '', '', user_id, '', '', phone_number])
            print(f"New user added: {user_id, user_name, phone_number}")
        except Exception as e:
            print(f"Error adding new user: {e}")

    def get_user_courses(self, user_id):
        """Retrieves all courses for a specific user from the Google Sheet."""
        try:
            data = self.google_sheets.get_all_data()
            user_courses = []
            for row in data:
                if str(row['User ID']).strip() == str(user_id).strip():
                    user_courses.append(row)
            return user_courses
        except Exception as e:
            print(f"Error retrieving user courses: {e}")
            return []

    def add_new_course(self, user_id, user_name, course_code, course_nickname, present, absent, phone_number,streak=0):
        """Adds a new course for a user to the Google Sheet."""
        try:
            self.google_sheets.add_row([user_id, user_name, course_code, course_nickname, present, absent, user_id, streak,phone_number])
            print(f"New course added for user {user_id}: Course Code={course_code}, Nickname={course_nickname}")
        except Exception as e:
            print(f"Error adding new course: {e}")

    def delete_course(self, user_id, course_code):
        """Deletes a course for a user from the Google Sheet."""
        try:
            data = self.google_sheets.get_all_data()
            for i, row in enumerate(data):
                if str(row['User ID']).strip() == str(user_id).strip() and str(row['Course Code']).strip() == str(course_code).strip():
                    row_index = i + 2  # Add 2 to account for header row and 0-based indexing
                    self.google_sheets.delete_row(row_index)
                    print(f"Course deleted for user {user_id}: Course Code={course_code}")
                    return
            print(f"Course not found for user {user_id}: Course Code={course_code}")
        except Exception as e:
            print(f"Error deleting course: {e}")

    def update_attendance(self, user_id, user_name, course_code, course_nickname, present_today):
        """Updates attendance for a specific course."""
        try:
            data = self.google_sheets.get_all_data()
            now = datetime.now(pytz.timezone('Asia/Kolkata'))
            timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
            
            for i, row in enumerate(data):
                # Use the same string comparison approach as update_attendance_manual
                row_user_id = str(row['User ID']).strip()
                user_id_str = str(user_id).strip()
                row_course_code = str(row['Course Code']).strip()
                course_code_str = str(course_code).strip()
                
                if row_user_id == user_id_str and row_course_code == course_code_str:
                    row_index = i + 2  # Add 2 to account for header row and 0-based indexing
                    
                    # Safely convert Present and Absent values to integers
                    present_val = row.get('Present', '0')
                    present = 0 if present_val == '' or present_val is None else int(present_val)
                    
                    absent_val = row.get('Absent', '0')
                    absent = 0 if absent_val == '' or absent_val is None else int(absent_val)
                    
                    # Get current streak
                    streak_val = row.get('Streak', '0')
                    streak = 0 if streak_val == '' or streak_val is None else int(streak_val)
                    
                    # Update Present or Absent count
                    if present_today == 1:
                        present += 1
                        streak += 1  # Increment streak for attendance
                    else:
                        absent += 1
                        streak = 0   # Reset streak for absence
                    
                    # Update the values in the Google Sheet
                    self.google_sheets.update_cell(row_index, 'Present', present)
                    self.google_sheets.update_cell(row_index, 'Absent', absent)
                    self.google_sheets.update_cell(row_index, 'Last Updated', timestamp)
                    self.google_sheets.update_cell(row_index, 'Streak', streak)
                    
                    print(f"Attendance updated for user {user_id} and {course_nickname}: Present={present}, Absent={absent}")
                    return True
                
            print(f"No matching course found for user {user_id} and course {course_code}")
            return False
        except Exception as e:
            print(f"Error updating attendance: {e}")
            # Don't raise the exception - this is another key difference
            return False  # Return False instead of raising

    def update_attendance_manual(self, user_id, course_code, present, absent):
        """Updates the attendance for a specific course in the Google Sheet manually."""
        try:
            data = self.google_sheets.get_all_data()
            now = datetime.now(pytz.timezone('Asia/Kolkata'))
            timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
            for i, row in enumerate(data):
                row_user_id = str(row['User ID']).strip()
                user_id_str = str(user_id).strip()

                if row_user_id == user_id_str and row['Course Code'] == course_code:
                    row_index = i + 2
                    self.google_sheets.update_cell(row_index, 'Present', present)
                    self.google_sheets.update_cell(row_index, 'Absent', absent)
                    self.google_sheets.update_cell(row_index, 'Last Updated', timestamp)

                    print(f"Attendance updated manually for user {user_id}, course {course_code}, present={present}, absent={absent}")
                    return True

            print(f"No matching course found for user {user_id} and course {course_code}")
            return False
        except Exception as e:
            print(f"Error updating attendance manually: {e}")

    def calculate_safe_skip(self, user_id):
        """Calculates which course can be skipped safely."""
        try:
            user_courses = self.get_user_courses(user_id)
            safe_courses = []

            for course in user_courses:
                present = int(course['Present'])
                absent = int(course['Absent'])
                total_classes = present + absent

                if total_classes > 0:
                    attendance_percentage = (present / total_classes) * 100
                else:
                    attendance_percentage = 100.0

                # Check if skipping this course would bring attendance below the threshold
                if (present) / (total_classes+1) * 100 >= self.attendance_threshold:
                    safe_courses.append({
                        'Course Nickname': course['Course Nickname'],
                        'Attendance': attendance_percentage
                    })

            return safe_courses
        except Exception as e:
            print(f"Error calculating safe skip: {e}")
            return []