def format_message(student_name, course_name, attendance_percentage):
    return f"Attendance Alert for {student_name} in {course_name}: {attendance_percentage}%"

def validate_input(input_data):
    if not isinstance(input_data, dict):
        raise ValueError("Input data must be a dictionary.")
    if 'student_name' not in input_data or 'course_name' not in input_data:
        raise ValueError("Input data must contain 'student_name' and 'course_name' keys.")
    return True

def calculate_attendance_percentage(attended_classes, total_classes):
    if total_classes == 0:
        return 0
    return (attended_classes / total_classes) * 100

def is_attendance_below_threshold(attendance_percentage, threshold=80):
    return attendance_percentage < threshold