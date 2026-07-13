# backend/email_service.py
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import os

from dotenv import load_dotenv
from newsletter_renderer import render_dual_newsletter_email_html
from config import BACKEND_URL, FRONTEND_URL

# Load .env from the project root (parent of backend directory)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path, override=True)
print(f"📧 Email service loaded .env from: {env_path}")
print(f"   .env exists: {os.path.exists(env_path)}")


def dispatch_manager_email(edition_title: str, token: str, payload: dict, publish_day: str, student_png_path: str | None = None, faculty_png_path: str | None = None):
    # Reload .env to ensure we have the latest values
    load_dotenv(env_path, override=True)
    
    sender_email = os.getenv("GMAIL_ADDRESS", "")
    app_password = os.getenv("GMAIL_APP_PASSWORD", "")
    manager_email = os.getenv("MANAGER_EMAIL", "")
    
    print(f"\n{'='*60}")
    print(f"📧 EMAIL DISPATCH STARTED")
    print(f"{'='*60}")
    print(f"📧 Email config check:")
    print(f"   GMAIL_ADDRESS: {sender_email or 'NOT SET'}")
    print(f"   GMAIL_APP_PASSWORD: {'SET (' + str(len(app_password)) + ' chars)' if app_password else 'NOT SET'}")
    print(f"   MANAGER_EMAIL: {manager_email or 'NOT SET'}")
    print(f"   Edition: {edition_title}")
    print(f"   Publish Day: {publish_day}")
    
    # Clean up app password - remove spaces/dashes that might have been added for readability
    if app_password:
        app_password = app_password.replace(" ", "").replace("-", "")
    print(f"   Cleaned app password length: {len(app_password) if app_password else 0} chars")

    if not sender_email or not app_password or not manager_email:
        print("❌ Email credentials missing from .env file!")
        print("   Required: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, MANAGER_EMAIL")
        print("   Note: GMAIL_APP_PASSWORD must be a Google App Password, not your regular password.")
        print("   Generate at: https://myaccount.google.com/apppasswords")
        return "failed_missing_credentials"

    approve_url = f"{BACKEND_URL}/api/webhook/approve?token={token}"
    edit_url = f"{FRONTEND_URL}/review?token={token}"

    backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    share_url = f"{backend_url}/newsletters/edition_latest.html"

    html_content = render_dual_newsletter_email_html(
        payload=payload,
        edition_title=edition_title,
        edit_url=edit_url,
        approve_url=approve_url,
        share_url=share_url,
    )

    # Create the root message with "mixed" type for attachments
    msg = MIMEMultipart("mixed")
    msg["From"] = sender_email
    msg["To"] = manager_email
    msg["Subject"] = f"Review Required: {edition_title} ({publish_day})"
    
    # Create the "alternative" part for text and HTML versions
    alternative_part = MIMEMultipart("alternative")
    alternative_part.attach(MIMEText(f"Your {publish_day} newsletter is ready for review. Two separate PNGs are attached for WhatsApp distribution: Student Edition and Faculty Edition.", "plain"))
    alternative_part.attach(MIMEText(html_content, "html"))
    
    # Attach the alternative part to the root message
    msg.attach(alternative_part)

    # Attach Student Edition PNG
    if student_png_path and os.path.exists(student_png_path):
        try:
            file_size = os.path.getsize(student_png_path)
            print(f"📎 Student PNG found: {student_png_path} ({file_size} bytes)")
            with open(student_png_path, "rb") as f:
                img_data = f.read()
            if len(img_data) == 0:
                print(f"⚠️ Student PNG is empty, skipping attachment")
            else:
                image = MIMEImage(img_data)
                image.add_header("Content-Disposition", "attachment", filename=f"newsletter_{publish_day}_student.png")
                msg.attach(image)
                print(f"✅ Student PNG attached successfully")
        except Exception as e:
            print(f"⚠️ Failed to attach student PNG: {e}")
            import traceback
            traceback.print_exc()
    else:
        if student_png_path:
            print(f"⚠️ Student PNG not found at: {student_png_path}")
        else:
            print(f"ℹ️ No student PNG path provided")
    
    # Attach Faculty Edition PNG
    if faculty_png_path and os.path.exists(faculty_png_path):
        try:
            file_size = os.path.getsize(faculty_png_path)
            print(f"📎 Faculty PNG found: {faculty_png_path} ({file_size} bytes)")
            with open(faculty_png_path, "rb") as f:
                img_data = f.read()
            if len(img_data) == 0:
                print(f"⚠️ Faculty PNG is empty, skipping attachment")
            else:
                image = MIMEImage(img_data)
                image.add_header("Content-Disposition", "attachment", filename=f"newsletter_{publish_day}_faculty.png")
                msg.attach(image)
                print(f"✅ Faculty PNG attached successfully")
        except Exception as e:
            print(f"⚠️ Failed to attach faculty PNG: {e}")
            import traceback
            traceback.print_exc()
    else:
        if faculty_png_path:
            print(f"⚠️ Faculty PNG not found at: {faculty_png_path}")
        else:
            print(f"ℹ️ No faculty PNG path provided")
    
    print(f"📧 Email message structure: {msg.get_content_type()} with {len(msg.get_payload())} parts")

    # Order by most reliable modern standard methods first (SSL -> TLS -> Port 25)
    connection_methods = [
        {"name": "SMTP_SSL port 465", "func": lambda: smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)},
        {"name": "SMTP+TLS port 587", "func": lambda: smtplib.SMTP("smtp.gmail.com", 587, timeout=30)},
        {"name": "SMTP port 25", "func": lambda: smtplib.SMTP("smtp.gmail.com", 25, timeout=30)},
    ]
    
    for method in connection_methods:
        try:
            print(f"📧 Connecting to Gmail SMTP server via {method['name']}...")
            
            with method["func"]() as server:
                # If using STARTTLS (ports 587 or 25), explicitly upgrade the connection
                if "TLS" in method["name"] or method["name"].endswith("25"):
                    server.ehlo()  # Explicitly greet the server
                    server.starttls()
                    server.ehlo()  # Re-greet to establish secure state
                
                print(f"   ✓ Connected! Logging in as {sender_email}...")
                server.login(sender_email, app_password)
                
                print(f"   ✓ Login successful! Sending message...")
                server.send_message(msg)
                print(f"   ✓ Message sent!")
            
            print(f"✅ Newsletter review email dispatched successfully to {manager_email}")
            print(f"   Subject: {msg['Subject']}")
            print(f"{'='*60}\n")
            return "success"
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Gmail authentication failed: {e}")
            print(f"   This usually means:")
            print(f"   1. GMAIL_APP_PASSWORD is not a valid Google App Password")
            print(f"   2. 2-Factor Authentication is not enabled on the Google account")
            print(f"   Fix: Visit https://myaccount.google.com/apppasswords to make a fresh key.")
            print(f"{'='*60}\n")
            return "failed_auth"  # Fail early; changing ports won't fix bad passwords
            
        except smtplib.SMTPException as e:
            print(f"   ✗ SMTP Protocol error with {method['name']}: {e}")
            print(f"     Trying next method...")
            continue  # FIXED: Now loops to the next configuration instead of exiting
            
        except (ConnectionError, TimeoutError, OSError) as e:
            print(f"   ✗ Network/Connection failed with {method['name']}: {e}")
            print(f"     Trying next method...")
            continue  # FIXED: Loops to next configuration
            
        except Exception as e:
            print(f"   ✗ Unexpected error during {method['name']}: {type(e).__name__}: {e}")
            print(f"     Trying next method...")
            continue

    # If the loop naturally finishes without returning a "success"
    print(f"❌ All connection methods failed completely.")
    print(f"   This is almost always caused by hosting environment restrictions:")
    print(f"   1. Your Cloud Hosting Provider (AWS, DigitalOcean, GCP, etc.) is blocking outbound SMTP ports.")
    print(f"   2. A local network firewall or antivirus is blocking connection hooks.")
    print(f"{'='*60}\n")
    return "failed_connection"