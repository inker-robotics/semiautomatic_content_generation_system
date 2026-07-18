import os
import requests

def send_poster_to_telegram(image_path: str, caption_text: str):
    """
    Sends the generated poster and caption to a Telegram chat via Bot API.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("[TELEGRAM] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. Skipping Telegram dispatch.")
        return False
        
    print(f"[TELEGRAM] Dispatching poster to Telegram chat {chat_id}...")
    
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    # Telegram captions have a 1024 character limit
    safe_caption = caption_text[:1000]
    
    try:
        with open(image_path, "rb") as image_file:
            payload = {
                "chat_id": chat_id,
                "caption": safe_caption,
                "parse_mode": "HTML"
            }
            files = {
                "photo": image_file
            }
            
            response = requests.post(url, data=payload, files=files)
            
            if response.status_code == 200:
                print("[TELEGRAM] Successfully delivered poster to Telegram!")
                return True
            else:
                print(f"[TELEGRAM] Failed to send: {response.text}")
                return False
    except Exception as e:
        print(f"[TELEGRAM] Exception occurred during dispatch: {str(e)}")
        return False
