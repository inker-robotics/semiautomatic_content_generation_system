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

## Deployment (Hugging Face Spaces)

This repository is ready to be pushed to GitHub and deployed on Hugging Face Spaces using the provided \Dockerfile\.

### Steps to Deploy:
1. Push this repository to your company's GitHub.
2. In Hugging Face Spaces, create a new **Docker** Space.
3. Link your GitHub repository.
4. Add all the keys from your \.env\ file as **Secrets** in the Hugging Face Space settings.
5. Hugging Face will automatically build the Dockerfile and launch the dashboard!

> **Important Note:** Hugging Face Spaces go to sleep if there is no web traffic. For the time-scheduler to work 24/7 without you opening the dashboard, you may need to upgrade the Space to "Always-on".
