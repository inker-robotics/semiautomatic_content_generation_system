import json
import os
import secrets
import time
import requests
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import DayAgentConfig, PipelineExecution, SecureApproval
from services.newsletter_renderer import render_dual_newsletter_email_html, render_single_edition_poster
from core.config import PUBLISH_WEEKDAYS, WEEKDAY_NAMES


def _config_to_dict(config: DayAgentConfig) -> dict:
    return {
        "publish_weekday": config.publish_weekday,
        "day_name": config.day_name,
        "edition_title": config.edition_title,
        "scout_system_prompt": config.scout_system_prompt,
        "writer_system_prompt": config.writer_system_prompt,
        "rss_feeds": json.loads(config.rss_feeds),
        "is_active": config.is_active,
        "target_time": config.target_time,
        "target_phone_number": config.target_phone_number,
        "client_logo_url": getattr(config, "client_logo_url", None),
    }


def get_publish_weekday_for_generation(reference: datetime | None = None) -> int | None:
    """Return the publish weekday to generate for (tomorrow by default)."""
    ref = reference or datetime.now()
    tomorrow = ref + timedelta(days=1)
    weekday = tomorrow.weekday()
    return weekday if weekday in PUBLISH_WEEKDAYS else None


def get_day_config(db: Session, publish_weekday: int, user_id: int) -> DayAgentConfig | None:
    return (
        db.query(DayAgentConfig)
        .filter(
            DayAgentConfig.publish_weekday == publish_weekday,
            DayAgentConfig.user_id == user_id,
            DayAgentConfig.is_active.is_(True),
        )
        .first()
    )


def generate_dynamic_image(prompt: str) -> str:
    """Calls Together AI to generate a unique image based on the specific news prompt."""
    api_key = os.getenv("TOGETHER_API_KEY")
    fallback_urls = [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/Artificial_intelligence_prompt_image.jpg/1200px-Artificial_intelligence_prompt_image.jpg"
    ]
    import random
    fallback_url = random.choice(fallback_urls)
    
    if not api_key:
        print("⚠️ TOGETHER_API_KEY not set. Falling back to generic Unsplash image.")
        return fallback_url
        
    try:
        url = "https://api.together.xyz/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # Force a highly visual, bold style with no text
        enhanced_prompt = f"Breathtaking, highly detailed, photorealistic cinematic lighting. Focus tightly on the specific subject. Extremely high quality, masterpiece. No text anywhere. {prompt}"
        
        print(f"🎨 Calling Together AI for: {prompt[:50]}...")
        payload = {
            "model": "black-forest-labs/FLUX.1-schnell",
            "prompt": enhanced_prompt,
            "steps": 4,
            "width": 1024,
            "height": 512,
            "n": 1
        }
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["url"]
                
        print(f"⚠️ Together AI API error: {response.text}")
        return fallback_url
    except Exception as e:
        print(f"⚠️ Image generation failed: {e}")
        return fallback_url


def render_html_to_png(html_str: str, output_path: str) -> bool:
    """Uses Playwright to render an HTML string exactly as it would appear in a browser."""
    from playwright.sync_api import sync_playwright
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            # Perfect square 1080x1080 for uncropped WhatsApp chat preview
            context = browser.new_context(
                viewport={"width": 1080, "height": 1080},
                device_scale_factor=2,
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
            )
            page = context.new_page()
            page.set_content(html_str, wait_until="networkidle")
            # Use JPEG for maximum compression to stay under Twilio 5MB limit
            page.screenshot(path=output_path, full_page=True, type="jpeg", quality=80)
            browser.close()
        
        print(f"🖼️ Ultra-high-DPI JPEG rendered: {output_path}")
        return True
    except Exception as e:
        print(f"⚠️ JPEG rendering failed: {e}")
        return False


def run_pipeline(execution_id: int):
    db: Session = SessionLocal()
    try:
        execution = db.query(PipelineExecution).filter(PipelineExecution.id == execution_id).first()
        if not execution:
            return

        feedback_str = ""
        if execution.execution_log and execution.execution_log.startswith("REGENERATION INITIATED:"):
            feedback_str = execution.execution_log.replace("REGENERATION INITIATED: ", "")

        execution.status = "processing"
        db.commit()

        day_config = get_day_config(db, execution.publish_weekday, execution.user_id)
        if not day_config:
            raise ValueError(f"No active agent config for weekday {execution.publish_weekday}")

        config_dict = _config_to_dict(day_config)
        
        # Set a professional, generic title instead of day-specific
        config_dict["edition_title"] = "Inker Tech Brief"
        
        # DENSE KNOWLEDGE CONSTRAINT FOR WHATSAPP
        config_dict["writer_system_prompt"] += (
            "\n\nCRITICAL CONSTRAINT: You are writing a highly scannable WhatsApp message. "
            "For all audiences, keep the content STRICTLY UNDER 75 words total. Break down the science using short, punchy bullet points. No exhausting walls of text. "
        )

        print(f"\n🚀 [SYSTEM] Running newsletter pipeline #{execution_id} → {config_dict['edition_title']}")

        from orchestrator import production_pipeline

        final_state = production_pipeline.invoke(
            {
                "day_config": config_dict,
                "feedback": feedback_str,
                "raw_news": [],
                "draft_payload": {},
                "status": "init",
            }
        )

        payload = final_state.get("draft_payload", {})

        # --- 1. GENERATE DYNAMIC IMAGES FOR EACH SECTION ---
        print("🎨 Generating Together AI images for news items...")
        image_count = 0
        editions = payload.get("editions", payload)
        for aud_name, edition in editions.items():
            sections = edition.get("sections", [])
            for i, section in enumerate(sections):
                img_prompt = section.get("image_prompt", config_dict["edition_title"])
                print(f"  📸 Image {image_count + 1}...")
                section["image_url"] = generate_dynamic_image(img_prompt)
                image_count += 1
                # Delay between images to respect rate limits
                if image_count < 6:
                    time.sleep(3)
        
        print(f"✅ Generated {image_count} images (some may be fallbacks if rate limited)")

        # --- 2. GENERATE SECURE APPROVAL TOKEN ---
        existing_approval = (
            db.query(SecureApproval)
            .filter(
                SecureApproval.execution_id == execution.id,
                SecureApproval.status == "awaiting_review",
            )
            .first()
        )

        token = str(existing_approval.secure_token if existing_approval else secrets.token_urlsafe(32))
        if not existing_approval:
            db.add(SecureApproval(execution_id=execution.id, secure_token=token))
            db.commit()

        # --- 3. BUILD INTERACTIVE URLS ---
        from core.config import FRONTEND_URL, BACKEND_URL
        
        edit_url = f"{FRONTEND_URL}/review?token={token}"
        approve_url = f"{BACKEND_URL}/api/webhook/approve?token={token}"
        share_url = f"{BACKEND_URL}/newsletters/edition_{execution.id}.html"

        # --- 4. RENDER AND SAVE COMBINED HTML ---
        newsletter_html = render_dual_newsletter_email_html(
            payload=payload, 
            edition_title=config_dict["edition_title"],
            edit_url=edit_url,
            approve_url=approve_url,
            share_url=share_url
        )

        os.makedirs("generated_newsletters", exist_ok=True)
        html_path = f"generated_newsletters/edition_{execution_id}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(newsletter_html)

        # --- 5. DOWNLOAD RAW AI IMAGE FOR WHATSAPP ---
        base_dir = os.path.dirname(os.path.abspath(__file__))
        png_paths = {}
        
        for aud_name, edition_data in editions.items():
            png_path = os.path.join(base_dir, "generated_newsletters", f"edition_{execution_id}_{aud_name}.jpeg")
            
            # Use the first section's image as the poster
            sections = edition_data.get("sections", [])
            if sections and sections[0].get("image_url"):
                img_url = sections[0]["image_url"]
                try:
                    import urllib.request
                    req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response, open(png_path, 'wb') as out_file:
                        out_file.write(response.read())
                    png_paths[aud_name] = png_path
                    print(f"📥 Downloaded raw AI image for {aud_name}: {png_path}")
                except Exception as e:
                    print(f"⚠️ Failed to download raw image for {aud_name}: {e}")

        execution.execution_log = json.dumps(payload)
        execution.newsletter_html = newsletter_html
        execution.topic = config_dict["edition_title"]
        execution.status = "awaiting_review"
        db.commit()

                # --- 6. DISPATCH WHATSAPP DIRECTLY ---
        print("?? Starting WhatsApp direct dispatch...")
        try:
            from dotenv import load_dotenv
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
            load_dotenv(env_path, override=True)
            target_phone = config_dict.get("target_phone_number")
            meta_token = os.getenv("META_WHATSAPP_TOKEN")
            
            if meta_token and meta_token != "YOUR_META_TOKEN_HERE":
                from services.whatsapp_meta_service import dispatch_whatsapp_meta_newsletter
                wa_result = dispatch_whatsapp_meta_newsletter(
                    payload=payload,
                    edition_title=config_dict["edition_title"],
                    png_paths=png_paths,
                    edit_url=edit_url,
                    approve_url=approve_url,
                    target_phone_number=target_phone
                )
            else:
                wa_result = "failed: META_WHATSAPP_TOKEN is missing in .env!"
                print("? META WHATSAPP TOKEN IS MISSING! Cannot send via Meta Graph API.")

            # --- 7. TELEGRAM FALLBACK ---
            from services.telegram_service import send_poster_to_telegram
            
            # Since png_paths is a dictionary {audience: path}, we'll dispatch all audiences
            for aud_key, img_path in png_paths.items():
                if img_path:
                    # Create a nice Telegram caption
                    caption = f"🚀 <b>New AI Poster: {config_dict['edition_title']}</b>\n\n"
                    caption += "The AI has finished writing the newsletter. Check it out on the web dashboard!\n"
                    caption += f"<a href='{share_url}'>🌐 Read Full Newsletter</a>"
                    
                    send_poster_to_telegram(img_path, caption)
            print(f"? WhatsApp dispatch completed with result: {wa_result}")
        except Exception as e:
            print(f"❌ WHATSAPP DISPATCH FAILED: {type(e).__name__}: {e}")
            import traceback
            print(f"   Full traceback:\n{traceback.format_exc()}")
            # Don't fail the whole pipeline if email fails

    except Exception as e:
        print(f"\n❌ [CRITICAL ERROR] Pipeline failed: {str(e)}")
        execution = db.query(PipelineExecution).filter(PipelineExecution.id == execution_id).first()
        if execution:
            execution.status = "failed"
            execution.execution_log = json.dumps({"error": str(e)})
            db.commit()
    finally:
        db.close()


def start_scheduled_generation(db: Session, publish_weekday: int | None = None, user_id: int = 1) -> dict:
    weekday = publish_weekday if publish_weekday is not None else get_publish_weekday_for_generation()
    if weekday is None:
        return {"started": False, "reason": "Tomorrow is not a configured publish day (Mon/Tue/Fri only)."}

    config = get_day_config(db, weekday, user_id)
    if not config:
        return {"started": False, "reason": f"No active config for {WEEKDAY_NAMES.get(weekday, weekday)}."}

    execution = PipelineExecution(
        topic=config.edition_title,
        publish_weekday=weekday,
        user_id=user_id,
        status="pending",
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    return {
        "started": True,
        "execution_id": execution.id,
        "publish_weekday": weekday,
        "edition_title": config.edition_title,
    }