import os
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Load .env from the project root
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path, override=True)

print("=" * 60)
print("WHATSAPP (TWILIO) CONFIGURATION TEST")
print("=" * 60)

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_whatsapp = os.getenv("TWILIO_WHATSAPP_SENDER")
to_whatsapp = os.getenv("MANAGER_WHATSAPP_NUMBER")

print(f"Account SID: {'SET' if account_sid else 'NOT SET'}")
print(f"Auth Token:  {'SET' if auth_token else 'NOT SET'}")
print(f"Sender:      {from_whatsapp or 'NOT SET'}")
print(f"Recipient:   {to_whatsapp or 'NOT SET'}")
print()

if not all([account_sid, auth_token, from_whatsapp, to_whatsapp]):
    print("❌ FAIL: Missing Twilio configuration in .env file")
    exit(1)

print("✅ Configuration looks good")
print("Testing Twilio connection and sending a test message...")

try:
    client = Client(account_sid, auth_token)
    
    message = client.messages.create(
        body="👋 Hello from your *INKER Newsletter System*!\n\nIf you are reading this natively formatted message, your WhatsApp integration is working perfectly! 🚀",
        from_=from_whatsapp,
        to=to_whatsapp
    )
    
    print(f"✅ Message queued successfully! Message SID: {message.sid}")
    print("\nCheck your WhatsApp! If you are using a Twilio Sandbox, make sure you have joined the sandbox first by sending the join code to the Twilio number.")
    
except TwilioRestException as e:
    print(f"\n❌ Twilio API Error:")
    print(f"   {e.msg}")
    print("\nMake sure your Twilio Sandbox is active and you have sent the 'join <word>' message from your phone to the Twilio number.")
except Exception as e:
    print(f"\n❌ Unexpected error: {type(e).__name__}: {e}")
