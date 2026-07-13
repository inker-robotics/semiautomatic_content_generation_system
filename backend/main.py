# backend/main.py
import json
import os
from datetime import datetime, timedelta

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

import models
from config import CRON_SECRET, CORS_ORIGINS, PUBLISH_WEEKDAYS, WEEKDAY_NAMES, ALL_WEEKDAY_NAMES
from database import engine, get_db, SessionLocal
from apscheduler.schedulers.background import BackgroundScheduler
import threading
from engine import get_publish_weekday_for_generation, run_pipeline, start_scheduled_generation
from models import DayAgentConfig
from schemas import DayAgentConfigResponse, DayAgentConfigUpdate
from seed import seed_day_configs

models.Base.metadata.create_all(bind=engine)


def ensure_schema():
    inspector = inspect(engine)
    if "pipeline_executions" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("pipeline_executions")}
        with engine.begin() as conn:
            if "publish_weekday" not in columns:
                conn.execute(text("ALTER TABLE pipeline_executions ADD COLUMN publish_weekday INTEGER"))
            if "newsletter_html" not in columns:
                conn.execute(text("ALTER TABLE pipeline_executions ADD COLUMN newsletter_html TEXT"))

    if "day_agent_configs" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("day_agent_configs")}
        with engine.begin() as conn:
            if "target_time" not in columns:
                conn.execute(text("ALTER TABLE day_agent_configs ADD COLUMN target_time VARCHAR DEFAULT '09:00'"))
            if "target_phone_number" not in columns:
                conn.execute(text("ALTER TABLE day_agent_configs ADD COLUMN target_phone_number VARCHAR"))
            if "target_audiences" not in columns:
                conn.execute(text("ALTER TABLE day_agent_configs ADD COLUMN target_audiences TEXT DEFAULT '[\"student\", \"faculty\"]'"))


ensure_schema()
os.makedirs("generated_newsletters", exist_ok=True)

app = FastAPI(title="INKER Newsletter Automation API", version="2.0.0")
app.mount("/newsletters", StaticFiles(directory="generated_newsletters"), name="newsletters")
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    with open("frontend/index.html") as f:
        return f.read()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    db = next(get_db())
    try:
        seed_day_configs(db)
    finally:
        db.close()
        
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_run_agents, 'cron', minute='*')
    scheduler.start()

def check_and_run_agents():
    db = SessionLocal()
    try:
        now = datetime.now()
        current_weekday = now.weekday()
        current_time = now.strftime("%H:%M")
        
        configs = db.query(DayAgentConfig).filter(
            DayAgentConfig.publish_weekday == current_weekday,
            DayAgentConfig.target_time == current_time,
            DayAgentConfig.is_active.is_(True)
        ).all()
        
        for config in configs:
            recent = db.query(models.PipelineExecution).filter(
                models.PipelineExecution.publish_weekday == current_weekday,
                models.PipelineExecution.created_at >= now - timedelta(minutes=2)
            ).first()
            
            if not recent:
                execution = models.PipelineExecution(
                    topic=config.edition_title,
                    publish_weekday=current_weekday,
                    status="pending",
                )
                db.add(execution)
                db.commit()
                db.refresh(execution)
                
                threading.Thread(target=run_pipeline, args=(execution.id,)).start()
                print(f"⏰ Scheduler triggered agent for {config.edition_title} at {current_time}")
                
    except Exception as e:
        print(f"Scheduler Error: {e}")
    finally:
        db.close()


class RegenerateRequest(BaseModel):
    token: str
    feedback: str


class ManualGenerateRequest(BaseModel):
    publish_weekday: int | None = None


def _config_response(config: DayAgentConfig) -> DayAgentConfigResponse:
    return DayAgentConfigResponse(
        publish_weekday=config.publish_weekday,
        day_name=config.day_name,
        edition_title=config.edition_title,
        scout_system_prompt=config.scout_system_prompt,
        writer_system_prompt=config.writer_system_prompt,
        rss_feeds=json.loads(config.rss_feeds),
        is_active=config.is_active,
        target_time=config.target_time,
        target_phone_number=config.target_phone_number,
        target_audiences=json.loads(config.target_audiences) if config.target_audiences else ["student", "faculty"],
    )


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"disconnected: {str(e)}"

    next_weekday = get_publish_weekday_for_generation()
    return {
        "status": "online",
        "database": db_status,
        "next_scheduled_publish_day": WEEKDAY_NAMES.get(next_weekday) if next_weekday is not None else None,
        "publish_days": [WEEKDAY_NAMES[d] for d in sorted(PUBLISH_WEEKDAYS)],
    }


@app.get("/api/agents", response_model=list[DayAgentConfigResponse])
def list_day_agents(db: Session = Depends(get_db)):
    configs = (
        db.query(DayAgentConfig)
        .order_by(DayAgentConfig.publish_weekday)
        .all()
    )
    return [_config_response(cfg) for cfg in configs]


@app.get("/api/agents/{publish_weekday}", response_model=DayAgentConfigResponse)
def get_day_agent(publish_weekday: int, db: Session = Depends(get_db)):
    if publish_weekday < 0 or publish_weekday > 6:
        raise HTTPException(status_code=400, detail="Weekday must be between 0 (Monday) and 6 (Sunday).")
    config = db.query(DayAgentConfig).filter(DayAgentConfig.publish_weekday == publish_weekday).first()
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found.")
    return _config_response(config)


@app.put("/api/agents/{publish_weekday}", response_model=DayAgentConfigResponse)
def update_day_agent(
    publish_weekday: int,
    body: DayAgentConfigUpdate,
    db: Session = Depends(get_db),
):
    if publish_weekday < 0 or publish_weekday > 6:
        raise HTTPException(status_code=400, detail="Weekday must be between 0 (Monday) and 6 (Sunday).")

    config = db.query(DayAgentConfig).filter(DayAgentConfig.publish_weekday == publish_weekday).first()
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found.")

    config.edition_title = body.edition_title
    config.scout_system_prompt = body.scout_system_prompt
    config.writer_system_prompt = body.writer_system_prompt
    config.rss_feeds = json.dumps(body.rss_feeds)
    config.is_active = body.is_active
    config.target_time = body.target_time
    config.target_phone_number = body.target_phone_number
    config.target_audiences = json.dumps(body.target_audiences)
    db.commit()
    db.refresh(config)
    return _config_response(config)


@app.post("/api/generate/scheduled")
def generate_scheduled(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_cron_secret: str | None = Header(default=None),
):
    if CRON_SECRET and x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Invalid cron secret.")

    result = start_scheduled_generation(db)
    if not result["started"]:
        return result

    background_tasks.add_task(run_pipeline, result["execution_id"])
    return result


@app.post("/api/generate/manual")
def generate_manual(
    body: ManualGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    weekday = body.publish_weekday
    if weekday is None:
        weekday = get_publish_weekday_for_generation()
    if weekday is None or weekday not in PUBLISH_WEEKDAYS:
        raise HTTPException(status_code=400, detail="No valid publish day selected.")

    result = start_scheduled_generation(db, publish_weekday=weekday)
    if not result["started"]:
        raise HTTPException(status_code=400, detail=result["reason"])

    background_tasks.add_task(run_pipeline, result["execution_id"])
    return result


@app.get("/api/executions")
def get_executions(db: Session = Depends(get_db)):
    rows = (
        db.query(models.PipelineExecution)
        .order_by(models.PipelineExecution.created_at.desc())
        .limit(10)
        .all()
    )
    return rows


@app.get("/api/preview")
def preview_by_token(token: str, db: Session = Depends(get_db)):
    approval = (
        db.query(models.SecureApproval)
        .filter(models.SecureApproval.secure_token == token)
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="Invalid token.")

    execution = (
        db.query(models.PipelineExecution)
        .filter(models.PipelineExecution.id == approval.execution_id)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found.")

    payload = {}
    if execution.execution_log and not execution.execution_log.startswith("REGENERATION INITIATED:"):
        try:
            payload = json.loads(execution.execution_log)
        except json.JSONDecodeError:
            payload = {"error": execution.execution_log}

    agent_config = None
    if execution.publish_weekday is not None:
        cfg = db.query(DayAgentConfig).filter(DayAgentConfig.publish_weekday == execution.publish_weekday).first()
        if cfg:
            agent_config = _config_response(cfg).model_dump()

    return {
        "execution_id": execution.id,
        "edition_title": execution.topic,
        "publish_weekday": execution.publish_weekday,
        "publish_day": WEEKDAY_NAMES.get(execution.publish_weekday),
        "status": execution.status,
        "payload": payload,
        "newsletter_html": execution.newsletter_html,
        "agent_config": agent_config,
    }


@app.post("/api/webhook/regenerate")
def regenerate_webhook(
    req: RegenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    approval = (
        db.query(models.SecureApproval)
        .filter(models.SecureApproval.secure_token == req.token)
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="Invalid token.")

    execution = (
        db.query(models.PipelineExecution)
        .filter(models.PipelineExecution.id == approval.execution_id)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found.")

    execution.execution_log = f"REGENERATION INITIATED: {req.feedback}"
    execution.status = "pending"
    approval.status = "awaiting_review"
    db.commit()

    background_tasks.add_task(run_pipeline, execution.id)
    return {"message": "Regeneration started.", "execution_id": execution.id}


@app.get("/api/webhook/approve", response_class=HTMLResponse)
def approve_webhook(token: str, db: Session = Depends(get_db)):
    approval = (
        db.query(models.SecureApproval)
        .filter(models.SecureApproval.secure_token == token)
        .first()
    )
    if not approval or approval.status != "awaiting_review":
        raise HTTPException(status_code=404, detail="Invalid or already processed token.")

    approval.status = "approved"
    execution = (
        db.query(models.PipelineExecution)
        .filter(models.PipelineExecution.id == approval.execution_id)
        .first()
    )
    execution.status = "complete"
    db.commit()

    return f"""
    <div style="font-family: sans-serif; padding: 40px; text-align: center; background-color: #0f172a; color: white; min-height: 100vh;">
        <h1 style="color: #10b981;">Newsletter Approved</h1>
        <p>{execution.topic} is cleared for publishing.</p>
        <p style="color: #64748b;">You may close this tab.</p>
    </div>
    """


@app.get("/api/schedule")
def get_schedule():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    next_weekday = get_publish_weekday_for_generation(now)

    upcoming = []
    for offset in range(1, 8):
        day = now + timedelta(days=offset)
        weekday = day.weekday()
        if weekday in PUBLISH_WEEKDAYS:
            upcoming.append(
                {
                    "publish_date": day.strftime("%Y-%m-%d"),
                    "publish_day": WEEKDAY_NAMES[weekday],
                    "generation_date": (day - timedelta(days=1)).strftime("%Y-%m-%d"),
                    "is_next": weekday == next_weekday,
                }
            )

    return {
        "publish_days": [ALL_WEEKDAY_NAMES[d] for d in sorted(ALL_WEEKDAY_NAMES.keys())],
        "scheduled_publish_days": [WEEKDAY_NAMES[d] for d in sorted(PUBLISH_WEEKDAYS)],
        "next_generation": (tomorrow - timedelta(days=1)).strftime("%Y-%m-%d") if next_weekday is not None else None,
        "next_publish_day": WEEKDAY_NAMES.get(next_weekday),
        "upcoming": upcoming,
    }
