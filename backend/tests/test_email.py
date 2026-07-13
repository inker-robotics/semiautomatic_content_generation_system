#!/usr/bin/env python3
"""Quick test to verify email sending works."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("EMAIL CONFIGURATION TEST")
print("=" * 60)

sender = os.getenv("GMAIL_ADDRESS", "")
password = os.getenv("GMAIL_APP_PASSWORD", "")
recipient = os.getenv("MANAGER_EMAIL", "")

print(f"Sender: {sender or 'NOT SET'}")
print(f"Password: {'SET (' + str(len(password)) + ' chars)' if password else 'NOT SET'}")
print(f"Recipient: {recipient or 'NOT SET'}")
print()

if not all([sender, password, recipient]):
    print("❌ FAIL: Missing email configuration in .env file")
    sys.exit(1)

print("✅ Configuration looks good")
print()
print("Testing SMTP connection...")

try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "Test Email from Newsletter System"
    msg.attach(MIMEText("This is a test email to verify SMTP is working.", "plain"))
    
    # Clean up password - remove spaces
    password = password.replace(" ", "").replace("-", "")
    
    # Try multiple connection methods as fallback
    connection_methods = [
        {"name": "SMTP_SSL port 465", "func": lambda: smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)},
        {"name": "SMTP+TLS port 587", "func": lambda: smtplib.SMTP("smtp.gmail.com", 587, timeout=30)},
        {"name": "SMTP port 25", "func": lambda: smtplib.SMTP("smtp.gmail.com", 25, timeout=30)},
    ]
    
    for method in connection_methods:
        try:
            print(f"Connecting to smtp.gmail.com using {method['name']}...")
            with method["func"]() as server:
                # If using STARTTLS (ports 587 or 25), upgrade the connection
                if "TLS" in method["name"] or method["name"].endswith("25"):
                    print(f"Connected! Upgrading to TLS...")
                    server.starttls()
                
                print(f"Connected! Logging in as {sender}...")
                server.login(sender, password)
                print(f"Login successful! Sending test email...")
                server.send_message(msg)
                print(f"✅ Email sent successfully to {recipient}")
                print()
                print("Check your inbox (and spam folder) for the test email!")
                break
        except Exception as e:
            print(f"   ✗ Failed with {method['name']}: {type(e).__name__}: {e}")
            print(f"   Trying next method...")
            continue
    else:
        print(f"❌ FAIL: All connection methods failed")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ FAIL: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
