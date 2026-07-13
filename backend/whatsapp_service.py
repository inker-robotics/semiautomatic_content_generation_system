# backend/whatsapp_service.py
import os
import time
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Load .env from the project root
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path, override=True)

def format_whatsapp_message(edition: dict, label: str) -> str:
    """Formats the JSON edition payload into native WhatsApp markdown."""
    # Build the header
    msg = f"*{label}: {edition.get('subject_line', '')}*\n"
    msg += f"_{edition.get('preheader', '')}_\n\n"
    msg += f"{edition.get('intro', '')}\n\n"
    
    # Build the sections
    for idx, section in enumerate(edition.get('sections', []), 1):
        msg += f"*{idx}. {section.get('title', '')}*\n"
        msg += f"{section.get('body', '')}\n"
        msg += f"📡 *Source:* {section.get('source', '')}\n"
        msg += f"🔗 {section.get('source_url', '')}\n"
        msg += f"💡 *Takeaway:* {section.get('key_takeaway', '')}\n\n"
        
    # Build the footer
    msg += f"{edition.get('closing', '')}\n"
    msg += f"🚀 *{edition.get('call_to_action', '')}*"
    
    return msg

import requests

def upload_to_uguu(file_path: str) -> str:
    """Uploads a local file to uguu.se and returns the public URL."""
    try:
        with open(file_path, 'rb') as f:
            response = requests.post('https://uguu.se/upload', files={'files[]': f}, timeout=60)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data['files'][0]['url']
            else:
                print(f"   -> Uguu API error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"   -> Failed to upload to uguu.se: {e}")
    return ""

def dispatch_whatsapp_newsletter(
    payload: dict,
    edition_title: str,
    png_paths: dict,
    edit_url: str,
    approve_url: str,
    target_phone_number: str | None = None
) -> dict:
    """
    Uploads the high-res PNG posters to a temporary cloud and sends them directly to WhatsApp via Twilio.
    """
    # Reload .env just in case it was updated
    load_dotenv(env_path, override=True)
    
    # Read Twilio credentials
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.getenv("TWILIO_WHATSAPP_SENDER")  # e.g., 'whatsapp:+14155238886'
    to_whatsapp = target_phone_number or os.getenv("MANAGER_WHATSAPP_NUMBER")     # e.g., 'whatsapp:+1234567890'
    
    if to_whatsapp and not to_whatsapp.startswith("whatsapp:"):
        to_whatsapp = f"whatsapp:{to_whatsapp}"
    
    print(f"\n{'='*60}")
    print(f"📱 WHATSAPP POSTER DISPATCH STARTED")
    print(f"{'='*60}")
    
    if not all([account_sid, auth_token, from_whatsapp, to_whatsapp]):
        print("❌ WhatsApp credentials missing from .env file!")
        print("   Skipping WhatsApp dispatch.")
        return "failed_missing_credentials"
        
    try:
        client = Client(account_sid, auth_token)
        
        # 1. Dispatch Posters for all Audiences
        editions = payload.get("editions", {})
        for aud_name, path in png_paths.items():
            if path and os.path.exists(path):
                print(f"\n   Sending {aud_name.capitalize()} Edition Poster...")
                
                edition_data = editions.get(aud_name, {})
                caption = format_whatsapp_message(edition_data, f"✨ {edition_title} - {aud_name.capitalize()} Edition")
                
                print("   -> Uploading to cloud to bypass Twilio constraints...")
                public_url = upload_to_uguu(path)
                if public_url:
                    print(f"   -> Upload successful: {public_url}")
                    try:
                        client.messages.create(
                            body=caption.strip(),
                            media_url=[public_url],
                            from_=from_whatsapp,
                            to=to_whatsapp
                        )
                        print(f"   ✓ {aud_name.capitalize()} Poster sent successfully!")
                    except Exception as twilio_err:
                        print(f"   ❌ Twilio failed to send poster: {twilio_err}")
                else:
                    print(f"   ❌ Failed to get public URL for {aud_name} poster.")
                    
                print("   ⏳ Waiting 5 seconds to respect Twilio Sandbox rate limits...")
                time.sleep(5)
                
        # 4. Send Interactive Review Options Separately
        if edit_url and approve_url:
            print("\n   Sending Interactive Review Options...")
            actions_msg = "━━━━━━━━━━━━━━━━\n"
            actions_msg += "🛠️ *MANAGER ACTIONS*\n"
            actions_msg += "━━━━━━━━━━━━━━━━\n\n"
            actions_msg += f"✅ *APPROVE & PUBLISH:*\n{approve_url}\n\n"
            actions_msg += f"✏️ *EDIT IN WEB UI:*\n{edit_url}"
            try:
                client.messages.create(
                    body=actions_msg,
                    from_=from_whatsapp,
                    to=to_whatsapp
                )
                print("   ✓ Action buttons sent successfully!")
            except Exception as twilio_err:
                print(f"   ❌ Twilio failed to send action buttons: {twilio_err}")
            
        print(f"\n✅ WhatsApp posters dispatched to {to_whatsapp}")
        print(f"{'='*60}\n")
        return "success"
        
    except TwilioRestException as e:
        print(f"❌ Twilio API Error: {e}")
        return "failed_api_error"
    except Exception as e:
        print(f"❌ Unexpected error during WhatsApp dispatch: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return "failed_unexpected"
