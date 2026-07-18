# Inker Robotics Poster Automation Platform

This repository contains the completely finalized, streamlined architecture for the Inker Robotics automated newsletter and poster generator. 

## Project Architecture

This project is a single unified FastAPI backend that also serves the HTML dashboard UI directly. There is no separate bloated frontend framework.

### `backend/` - The Core Engine
* **`main.py`** - The FastAPI entrypoint. Handles the API routes, serves the Web UI dashboard, and launches background tasks for image generation.
* **`engine.py`** - The heart of the AI. It uses CrewAI to write the newsletter, requests image generation via Together API (FLUX), and coordinates the workflow.
* **`.env`** - Your single source of truth for API keys. It contains Groq, OpenAI, Tavily, and your Meta WhatsApp keys.

### `backend/frontend/` - The Web UI
* **`index.html`** - A lightweight, ultra-fast vanilla HTML/JS dashboard styled with Tailwind CSS. This is the interface you use to schedule and configure the agents.
* **`logos/`** - Contains the Inker Robotics logos used in the posters.

### `backend/services/` - Independent Modules
* **`newsletter_renderer.py`** - Takes the raw JSON newsletter output and uses Playwright (a headless browser) to take a high-resolution screenshot of the poster template.
* **`whatsapp_meta_service.py`** - Uploads the generated posters to Meta and dispatches them directly to the target WhatsApp number using the official Meta Graph API.

### `backend/core/` - Configuration & Database
* **`config.py`** - Loads the `.env` variables.
* **`database.py`** & **`models.py`** - Sets up the SQLite database (`app.db`) to store your scheduled days and past executions.
* **`schemas.py`** - Pydantic models for API validation.

---

## Deployment (Render.com)

This repository is ready to be pushed to GitHub and deployed on Hugging Face Spaces using the provided \Dockerfile\.

### Steps to Deploy:
1. Push this repository to your company's GitHub.
2. On Render.com, create a new **Web Service** and connect your GitHub repository.

4. Add all the keys from your \.env\ file as **Secrets** in the Hugging Face Space settings.
4. Render will automatically detect the Dockerfile, build it, and launch your dashboard!

> **Important Note:** Render Free Tier goes to sleep after 15 minutes of inactivity. To keep the time-scheduler running 24/7 for free, set up a cron job (e.g., via cron-job.org) to ping your Render URL every 10 minutes.

## Telegram Bot Fallback (Fail-safe)

Because Meta's anti-spam Sandbox is extremely strict, the system includes a **Telegram Bot integration** that automatically sends a backup copy of every poster to your Telegram.

**To set up Telegram:**
1. Open Telegram and search for **@BotFather**.
2. Type `/newbot` and follow the prompts to get your **HTTP API Token**.
3. Create a new Telegram Group, add your new bot to it, and use [IDBot](https://t.me/myidbot) or a similar tool to get the Group's **Chat ID** (usually starts with a minus sign, e.g., `-10012345678`).
4. Add these two variables to your Render Environment Variables:
   - `TELEGRAM_BOT_TOKEN`: *your_bot_token*
   - `TELEGRAM_CHAT_ID`: *your_chat_id*

Once added, the AI will dual-dispatch every poster to both WhatsApp and Telegram simultaneously!

## WhatsApp Production Configuration (Permanent Token)

Currently, the system uses a 24-hour Temporary Access Token for development. For the final 24/7 production deployment, a Permanent System User Token must be generated and added to the Render Environment Variables.

**Steps to Generate Permanent Token:**
1. Navigate to [Meta Business Settings -> System Users](https://business.facebook.com/settings/system-users).
2. Click **Add** to create a new System User (e.g., "Inker News Bot") and set the role to **Admin**.
3. Click **Add Assets**, select **Apps**, choose the WhatsApp App, and enable **Full Control (Manage App)**.
4. Click **Generate New Token**.
5. **CRITICAL:** Set Token Expiration to **Never**.
6. Check the following permissions:
   - whatsapp_business_messaging
   - whatsapp_business_management
7. Click **Generate Token**. Copy this token immediately.
8. Add this token as the META_WHATSAPP_TOKEN environment variable in Render.

### Adding the Token Later (If Deploying Today)
If you deploy the application to Render today without the permanent token, the web app and AI scheduler will still function normally (it will just skip sending the WhatsApp message). 

When the permanent token is generated later, you can add it to the live server without touching the code:
1. Log into your Render.com dashboard.
2. Select the `inker-news-bot` Web Service.
3. On the left sidebar, click **Environment**.
4. Click **Add Environment Variable**.
5. Key: `META_WHATSAPP_TOKEN` | Value: *(Paste the permanent token)*
6. Click **Save Changes**. 

Render will automatically restart the server, and the WhatsApp dispatcher will instantly become active!

### Going Live (Messaging Any Client Number)
Currently, your Meta App is in **Development Mode** (Sandbox). In this mode, Meta strictly prevents spam by only allowing the AI to send messages to the 5 specific phone numbers you manually verified in the API Setup page. 

To make the app "client-friendly" so it can send newsletters to **any** phone number on Earth, you must take the app out of the Sandbox:

1. **Complete Business Verification**: Your manager must upload official legal documents (business registration, utility bills, etc.) to Meta via the Business Settings dashboard to prove Inker Robotics is a legally registered company.
2. **Switch to Live Mode**: Once Meta approves the documents, go to the Meta Developer Dashboard (`developers.facebook.com/apps`). At the very top of the screen, click the toggle switch to change the **App Mode** from **Development** to **Live**.

Once the app is in Live Mode, all sandbox restrictions are permanently lifted. The AI will instantly be able to dispatch posters to whatever phone numbers your future clients enter on the frontend dashboard!
