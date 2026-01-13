#!/usr/bin/env python3
"""
Script to import TimeEdit CSV calendar events into Canvas
This version uses only Python standard library (no external dependencies)

INSTRUCTIONS:
1. Save this script to your computer
2. Make sure the TimeEdit .csv file is in the same folder
3. Edit the configuration section below with your API token
4. Edit the COURSE_ID and CSV_FILE path if needed (course id is found in Canvas URL)
5. Edit the csv file separately if something should be removed, for example exam periods or such
6. Set summer/winter time offset if needed (see comments in configuration)
7. Set Swedish or English language for event descriptions
4. Run: python3 timeedit_csv_to_canvas.py
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
import csv
import sys

# ============================================================================
# CONFIGURATION - EDIT THESE VALUES
# ============================================================================
CANVAS_DOMAIN = "chalmers.instructure.com"
API_TOKEN = "ADD YOUR API TOKEN HERE"  # Paste your API token here
COURSE_ID = "ADD YOUR COURSE ID HERE"  # e.g., "12345"

CSV_FILE = "ADD YOUR CSV FILE PATH HERE"  # Update path if needed
LANGUAGE = "en"  # "en" for English or "sv" for Swedish
TIMEZONE_OFFSET = 1  # Hours offset from UTC (CET = UTC+1, CEST = UTC+2)
# NOTE: Change TIMEZONE_OFFSET to 2 during summer time (late March to late October)
# ============================================================================

# Canvas API endpoint
BASE_URL = f"https://{CANVAS_DOMAIN}/api/v1"

# Translations
TRANSLATIONS = {
    "en": {
        "course": "Course",
        "courses": "Courses",
        "activity": "Activity",
        "title": "Title",
        "location": "Location",
        "room": "Room",
        "campus": "Campus",
        "classes": "Classes"
    },
    "sv": {
        "course": "Kurs",
        "courses": "Kurser",
        "activity": "Aktivitet",
        "title": "Titel",
        "location": "Plats",
        "room": "Rum",
        "campus": "Campus",
        "classes": "Klasser"
    }
}

def t(key):
    """Get translation for a key based on selected language"""
    return TRANSLATIONS[LANGUAGE].get(key, key)

def parse_csv_file(file_path):
    """Parse the CSV file and extract events"""
    events = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        # Skip first 3 lines (header info)
        for _ in range(3):
            next(f)
        
        reader = csv.DictReader(f)
        
        for row in reader:
            # Skip empty rows
            if not row.get('Begin date') or not row.get('Begin time'):
                continue
            
            # Parse datetime in local timezone and convert to UTC
            begin_date = row['Begin date'].strip()
            begin_time = row['Begin time'].strip()
            end_date = row['End date'].strip()
            end_time = row['End time'].strip()
            
            # Parse as naive datetime (local Swedish time)
            start_dt_local = datetime.strptime(f"{begin_date} {begin_time}", "%Y-%m-%d %H:%M")
            end_dt_local = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
            
            # Convert to UTC by subtracting the timezone offset
            start_dt = start_dt_local - timedelta(hours=TIMEZONE_OFFSET)
            end_dt = end_dt_local - timedelta(hours=TIMEZONE_OFFSET)
            
            # Extract course codes (may be multiple, comma-separated)
            course_codes_raw = row.get('Course code', '').strip()
            course_codes = [code[:6] for code in course_codes_raw.split(',') if code.strip()]
            
            # Extract course names (may be multiple, comma-separated)
            course_names_raw = row.get('Course name', '').strip()
            course_names = [name.strip() for name in course_names_raw.split(',') if name.strip()]
            
            # Extract activity (may be multiple, comma-separated)
            activity_raw = row.get('Activity', '').strip()
            activities = [act.strip() for act in activity_raw.split(',') if act.strip()]
            
            # Extract title
            title = row.get('Title', '').strip()
            
            # Extract room
            room = row.get('Room', '').strip()
            
            # Extract class codes and names
            class_codes_raw = row.get('class code', '').strip()
            class_codes = [code.strip() for code in class_codes_raw.split(',') if code.strip()]
            
            class_names_raw = row.get('Name', '').strip()
            class_names = [name.strip() for name in class_names_raw.split(',') if name.strip()]
            
            event = {
                'start': start_dt,
                'end': end_dt,
                'course_codes': course_codes,
                'course_names': course_names,
                'activities': activities,
                'title': title,
                'room': room,
                'class_codes': class_codes,
                'class_names': class_names
            }
            
            events.append(event)
    
    return events

def format_event_title(event):
    """Create a concise title for the Canvas event"""
    # Use activity if available
    if event['activities']:
        return ', '.join(event['activities'])
    elif event['title']:
        return event['title']
    elif event['course_names']:
        course = event['course_names'][0]
        if len(course) > 40:
            course = course[:37] + "..."
        return course
    else:
        return "Event"

def format_event_description(event):
    """Create a detailed description for the Canvas event"""
    parts = []
    
    # Course information
    if event['course_codes']:
        label = t("courses") if len(event['course_codes']) > 1 else t("course")
        parts.append(f"{label}:<br>")
        for i, code in enumerate(event['course_codes']):
            name = event['course_names'][i] if i < len(event['course_names']) else ''
            if name:
                parts.append(f"   {code} - {name}<br>")
            else:
                parts.append(f"   {code}<br>")
        parts.append("<br>")
    
    # Activity information
    if event['activities']:
        parts.append(f"📋 {t('activity')}: {', '.join(event['activities'])}<br>")
        parts.append("<br>")
    
    # Title (if different from activity)
    if event['title'] and event['title'] not in event['activities']:
        parts.append(f"📌 {t('title')}: {event['title']}<br>")
        parts.append("<br>")
    
    # Location
    if event['room']:
        parts.append(f"📍 {t('location')}: {event['room']}<br>")
        parts.append("<br>")
    
    return "".join(parts).strip()

def format_location(event):
    """Format location string for Canvas location field"""
    return event['room'] if event['room'] else ''

def create_canvas_event(event):
    """Create a single event in Canvas using urllib"""
    url = f"{BASE_URL}/calendar_events"
    
    # Format datetime for Canvas API
    start_at = event['start'].strftime('%Y-%m-%dT%H:%M:%SZ')
    end_at = event['end'].strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Format event data
    title = format_event_title(event)
    description = format_event_description(event)
    location = format_location(event)
    
    payload = {
        "calendar_event": {
            "context_code": f"course_{COURSE_ID}",
            "title": title,
            "start_at": start_at,
            "end_at": end_at,
            "location_name": location,
            "description": description
        }
    }
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def main():
    # Check if API token has been set
    if API_TOKEN == "YOUR_API_TOKEN_HERE":
        print("ERROR: Please edit the script and add your API token in the configuration section.")
        print("Open the script in a text editor and replace 'YOUR_API_TOKEN_HERE' with your actual token.")
        sys.exit(1)
    
    print("=" * 80)
    print("TimeEdit CSV to Canvas Import Script")
    print("=" * 80)
    print(f"Canvas domain: {CANVAS_DOMAIN}")
    print(f"Course ID: {COURSE_ID}")
    print(f"CSV file: {CSV_FILE}")
    print(f"Language: {LANGUAGE}")
    print(f"Timezone: UTC+{TIMEZONE_OFFSET} (Swedish {'Winter' if TIMEZONE_OFFSET == 1 else 'Summer'} Time)")
    print()
    print("NOTE: If your events appear at the wrong time in Canvas:")
    print("  - Winter time (late Oct - late Mar): Set TIMEZONE_OFFSET = 1")
    print("  - Summer time (late Mar - late Oct): Set TIMEZONE_OFFSET = 2")
    print()
    
    # Parse the CSV file
    try:
        print("Parsing TimeEdit CSV file...")
        events = parse_csv_file(CSV_FILE)
        print(f"Found {len(events)} events to import\n")
    except FileNotFoundError:
        print(f"ERROR: Could not find file '{CSV_FILE}'")
        print("Make sure the .csv file is in the same folder as this script,")
        print("or update the CSV_FILE path in the configuration section.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR parsing CSV file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Display events
    print("Events to be created:")
    print("-" * 80)
    for i, event in enumerate(events, 1):
        title = format_event_title(event)
        print(f"{i}. {title}")
        print(f"   Start: {event['start'].strftime('%Y-%m-%d %H:%M')}")
        print(f"   End: {event['end'].strftime('%Y-%m-%d %H:%M')}")
        if event['room']:
            print(f"   Room: {event['room']}")
        if event['course_codes']:
            print(f"   Courses: {', '.join(event['course_codes'])}")
        print()
    
    # Ask for confirmation
    confirm = input("Do you want to create these events in Canvas? (yes/no): ")
    if confirm.lower() not in ['yes', 'y']:
        print("Import cancelled.")
        return
    
    # Create events
    print("\nCreating events in Canvas...")
    print("-" * 80)
    success_count = 0
    error_count = 0
    
    for i, event in enumerate(events, 1):
        title = format_event_title(event)
        # Truncate title for display
        if len(title) > 50:
            display_title = title[:47] + "..."
        else:
            display_title = title
        
        print(f"[{i}/{len(events)}] Creating: {display_title}")
        
        status, response = create_canvas_event(event)
        
        if status == 201:
            print(f"         ✓ Success")
            success_count += 1
        else:
            print(f"         ✗ Error (Status {status})")
            try:
                error_detail = json.loads(response.decode('utf-8'))
                print(f"         Response: {error_detail}")
            except:
                print(f"         Response: {response}")
            error_count += 1
        print()
    
    # Summary
    print("=" * 80)
    print("Import Complete!")
    print("=" * 80)
    print(f"Successfully created: {success_count} events")
    print(f"Errors: {error_count} events")
    print("\nYou can now view the events in your Canvas calendar:")
    print(f"https://{CANVAS_DOMAIN}/courses/{COURSE_ID}/calendar")
    print("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nImport cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
