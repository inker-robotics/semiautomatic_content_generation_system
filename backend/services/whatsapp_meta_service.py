# backend/whatsapp_meta_service.py
import os
import requests
from dotenv import load_dotenv

# Load .env from the project root
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path, override=True)

def format_whatsapp_message(edition: dict, label: str) -> str:
    """Formats the JSON edition payload to fit inside the template's {{1}} body variable."""
    msg = f"*{label}*\n"
    msg += f"_{edition.get('subject_line', '')}_\n\n"
    
    sections = edition.get('sections', [])
    if sections:
        section = sections[0]  # Focus on the top story since it matches the single image
        msg += f"*{section.get('title', '')}*\n"
        msg += f"{section.get('body', '')}\n\n"
        
    return msg

def get_source_url_suffix(edition: dict) -> str:
    sections = edition.get('sections', [])
    if sections:
        url = sections[0].get("source_url", "inkerrobotics.com")
        if url.startswith("https://"):
            return url[8:]
        if url.startswith("http://"):
            return url[7:]
        return url
    return "inkerrobotics.com"

def upload_whatsapp_media(filepath: str, phone_number_id: str, access_token: str) -> str | None:
    """Uploads a media file to Meta and returns the Media ID."""
    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/media"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    try:
        mime_type = "image/jpeg" if filepath.endswith(".jpeg") else "image/png"
        with open(filepath, 'rb') as f:
            files = {
                'file': (os.path.basename(filepath), f, mime_type)
            }
            data = {
                'messaging_product': 'whatsapp'
            }
            print(f"📤 Uploading media to Meta: {filepath}")
            res = requests.post(url, headers=headers, data=data, files=files, timeout=30)
            if res.status_code == 200:
                media_id = res.json().get('id')
                print(f"✅ Media uploaded successfully. ID: {media_id}")
                return media_id
            else:
                print(f"❌ Media upload failed {res.status_code}: {res.text}")
                return None
    except Exception as e:
        print(f"❌ Exception uploading media: {e}")
        return None

def dispatch_whatsapp_meta_newsletter(
    payload: dict,
    edition_title: str,
    png_paths: dict,
    edit_url: str,
    approve_url: str,
    target_phone_number: str | None = None
) -> dict:
    """
    Dispatches the newsletter via the official Meta WhatsApp Graph API using TEMPLATES.
    """
    print("\n" + "="*60)
    print("📱 META WHATSAPP TEMPLATE DISPATCH STARTED")
    print("="*60)

    access_token = os.getenv("META_WHATSAPP_TOKEN", "YOUR_META_TOKEN_HERE")
    phone_number_id = os.getenv("META_PHONE_NUMBER_ID", "YOUR_PHONE_NUMBER_ID_HERE")
    recipient_number = target_phone_number or os.getenv("META_RECIPIENT_NUMBER", "YOUR_TARGET_PHONE_NUMBER_HERE")
    
    if access_token == "YOUR_META_TOKEN_HERE" or not access_token:
        print("⚠️ META_WHATSAPP_TOKEN is not set! Skipping Meta dispatch.")
        return "skipped_missing_credentials"

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    messages_to_send = []
    for aud_name, edition in payload.get('editions', {}).items():
        if 'student' in aud_name.lower():
            label = "⚡ Student Edition"
        else:
            label = "🎓 Faculty Edition"
            
        text = format_whatsapp_message(edition, label)[:1000]
        btn_url = get_source_url_suffix(edition)
        messages_to_send.append({"aud": aud_name, "text": text, "url": btn_url})

    import re
    for item in messages_to_send:
        # Meta templates do not allow newlines in variables. Replace them with spaces.
        msg_text = re.sub(r'\s+', ' ', item["text"]).strip()
        btn_url = item["url"]
        aud_key = item["aud"]
        
        img_path = png_paths.get(aud_key)
        media_id = None
        if img_path and os.path.exists(img_path):
            media_id = upload_whatsapp_media(img_path, phone_number_id, access_token)

        if media_id:
            data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient_number,
                "type": "template",
                "template": {
                    "name": "daily_tech_poster",
                    "language": {
                        "code": "en"
                    },
                    "components": [
                        {
                            "type": "header",
                            "parameters": [
                                {
                                    "type": "image",
                                    "image": {
                                        "id": media_id
                                    }
                                }
                            ]
                        },
                        {
                            "type": "body",
                            "parameters": [
                                {
                                    "type": "text",
                                    "text": msg_text
                                },
                                {
                                    "type": "text",
                                    "text": btn_url
                                }
                            ]
                        },
                    ]
                }
            }
            
            try:
                print(f"📤 Sending TEMPLATE to {recipient_number}...")
                response = requests.post(url, headers=headers, json=data, timeout=30)
                
                if response.status_code in [200, 201]:
                    print(f"✅ Meta WhatsApp Template Sent Successfully!")
                else:
                    print(f"❌ Meta API Error {response.status_code}: {response.text}")
            except Exception as e:
                print(f"❌ Network error while calling Meta API: {e}")

    print("="*60 + "\n")
    return "completed"
