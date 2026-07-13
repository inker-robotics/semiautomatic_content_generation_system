# backend/whatsapp_meta_service.py
import os
import requests
from dotenv import load_dotenv

# Load .env from the project root
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path, override=True)

def format_whatsapp_message(edition: dict, label: str) -> str:
    """Formats the JSON edition payload into native WhatsApp markdown."""
    msg = f"*{label}: {edition.get('subject_line', '')}*\n"
    msg += f"_{edition.get('preheader', '')}_\n\n"
    msg += f"{edition.get('intro', '')}\n\n"
    
    for idx, section in enumerate(edition.get('sections', []), 1):
        msg += f"*{idx}. {section.get('title', '')}*\n"
        msg += f"{section.get('body', '')}\n"
        msg += f"📡 *Source:* {section.get('source', '')}\n"
        msg += f"🔗 {section.get('source_url', '')}\n"
        msg += f"💡 *Takeaway:* {section.get('key_takeaway', '')}\n\n"
        
    msg += f"{edition.get('closing', '')}\n"
    msg += f"🚀 *{edition.get('call_to_action', '')}*"
    return msg

def dispatch_whatsapp_meta_newsletter(
    payload: dict,
    edition_title: str,
    png_paths: dict,
    edit_url: str,
    approve_url: str,
    target_phone_number: str | None = None
) -> dict:
    """
    Dispatches the newsletter via the official Meta WhatsApp Graph API.
    """
    print("\n" + "="*60)
    print("📱 META WHATSAPP DISPATCH STARTED")
    print("="*60)

    # Note to successor: These must be filled in your .env file
    access_token = os.getenv("META_ACCESS_TOKEN", "YOUR_META_TOKEN_HERE")
    phone_number_id = os.getenv("META_PHONE_NUMBER_ID", "YOUR_PHONE_NUMBER_ID_HERE")
    recipient_number = target_phone_number or os.getenv("META_RECIPIENT_NUMBER", "YOUR_TARGET_PHONE_NUMBER_HERE")
    
    if access_token == "YOUR_META_TOKEN_HERE":
        print("⚠️ META_ACCESS_TOKEN is not set! Skipping Meta dispatch.")
        return "skipped_missing_credentials"

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Meta API limits standard messages to 4096 characters, so we must truncate if necessary
    student_text = format_whatsapp_message(payload.get('student_edition', {}), "⚡ Student Edition")[:4000]
    faculty_text = format_whatsapp_message(payload.get('faculty_edition', {}), "🎓 Faculty Edition")[:4000]

    # For this professional template, we are sending text messages. 
    # If media (PNGs) is needed, the successor must upload them to Meta's media endpoint first,
    # retrieve a Media ID, and send a 'type': 'image' message with the ID.
    messages_to_send = [student_text, faculty_text]

    for msg_text in messages_to_send:
        if len(msg_text.strip()) < 10:
            continue

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": msg_text
            }
        }
        
        try:
            print(f"📤 Sending Meta API Request to {recipient_number}...")
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code in [200, 201]:
                print(f"✅ Meta WhatsApp Message Sent Successfully!")
            else:
                print(f"❌ Meta API Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"❌ Network error while calling Meta API: {e}")

    print("="*60 + "\n")
    return "completed"
