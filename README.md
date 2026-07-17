# Inker Robotics Poster Automation Platform

This repository contains the completely finalized, streamlined architecture for the Inker Robotics automated newsletter and poster generator. 

## Project Architecture

This project is a single unified FastAPI backend that also serves the HTML dashboard UI directly. There is no separate bloated frontend framework.

### \ackend/\ - The Core Engine
* **\main.py\** - The FastAPI entrypoint. Handles the API routes, serves the Web UI dashboard, and launches background tasks for image generation.
* **\engine.py\** - The heart of the AI. It uses CrewAI to write the newsletter, requests image generation via Together API (FLUX), and coordinates the workflow.
* **\.env\** - Your single source of truth for API keys. It contains Groq, OpenAI, Tavily, and your Meta WhatsApp keys.

### \ackend/frontend/\ - The Web UI
* **\index.html\** - A lightweight, ultra-fast vanilla HTML/JS dashboard styled with Tailwind CSS. This is the interface you use to schedule and configure the agents.
* **\logos/\** - Contains the Inker Robotics logos used in the posters.

### \ackend/services/\ - Independent Modules
* **\
ewsletter_renderer.py\** - Takes the raw JSON newsletter output and uses Playwright (a headless browser) to take a high-resolution screenshot of the poster template.
* **\whatsapp_meta_service.py\** - Uploads the generated posters to Meta and dispatches them directly to the target WhatsApp number using the official Meta Graph API.

### \ackend/core/\ - Configuration & Database
* **\config.py\** - Loads the \.env\ variables.
* **\database.py\** & **\models.py\** - Sets up the SQLite database (\enterprise_platform.db\) to store your scheduled days and past executions.
* **\schemas.py\** - Pydantic models for API validation.

---

## Deployment (Render.com)

This repository is ready to be pushed to GitHub and deployed on Hugging Face Spaces using the provided \Dockerfile\.

### Steps to Deploy:
1. Push this repository to your company's GitHub.
2. On Render.com, create a new **Web Service** and connect your GitHub repository.

4. Add all the keys from your \.env\ file as **Secrets** in the Hugging Face Space settings.
4. Render will automatically detect the Dockerfile, build it, and launch your dashboard!

> **Important Note:** Render Free Tier goes to sleep after 15 minutes of inactivity. To keep the time-scheduler running 24/7 for free, set up a cron job (e.g., via cron-job.org) to ping your Render URL every 10 minutes.

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

### Note on `META_RECIPIENT_NUMBER` (The Sandbox Loophole)
While you are using a **Temporary Access Token**, Meta places your WhatsApp app in a strict "Sandbox Mode". In this mode, Meta will reject messages sent to dynamic numbers provided by the frontend. It will *only* send messages to the single, verified phone number registered in your Meta Developer Dashboard.

To prevent the server from crashing during this Sandbox Mode, the backend uses the `META_RECIPIENT_NUMBER` environment variable as a hardcoded fallback loophole. 

Once your manager generates the **Permanent Token**, your WhatsApp app goes into "Live Mode." At that point, you can safely remove the `META_RECIPIENT_NUMBER` environment variable from Render, and the system will dynamically deliver newsletters to whatever phone numbers your clients enter on the frontend!
