# backend/main.py
import json
import os
import shutil
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jwt
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from core import models
from core.config import CRON_SECRET, CORS_ORIGINS, PUBLISH_WEEKDAYS, WEEKDAY_NAMES, ALL_WEEKDAY_NAMES
from core.database import engine, get_db, SessionLocal
from apscheduler.schedulers.background import BackgroundScheduler
import threading
from engine import get_publish_weekday_for_generation, run_pipeline, start_scheduled_generation
from core.models import DayAgentConfig, User
from core.schemas import DayAgentConfigResponse, DayAgentConfigUpdate, DayAgentConfigCreate, UserCreate, Token
from scripts.seed import seed_day_configs

# Ensure directories
os.makedirs("generated_newsletters", exist_ok=True)
os.makedirs("../frontend/logos", exist_ok=True)

models.Base.metadata.create_all(bind=engine)

def ensure_schema():
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "hashed_password" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN hashed_password VARCHAR DEFAULT 'default'"))
                
    if "pipeline_executions" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("pipeline_executions")}
        with engine.begin() as conn:
            if "publish_weekday" not in columns:
                conn.execute(text("ALTER TABLE pipeline_executions ADD COLUMN publish_weekday INTEGER"))
            if "newsletter_html" not in columns:
                conn.execute(text("ALTER TABLE pipeline_executions ADD COLUMN newsletter_html TEXT"))
            if "user_id" not in columns:
                conn.execute(text("ALTER TABLE pipeline_executions ADD COLUMN user_id INTEGER"))

    if "day_agent_configs" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("day_agent_configs")}
        with engine.begin() as conn:
            if "target_time" not in columns:
                conn.execute(text("ALTER TABLE day_agent_configs ADD COLUMN target_time VARCHAR DEFAULT '09:00'"))
            if "target_phone_number" not in columns:
                conn.execute(text("ALTER TABLE day_agent_configs ADD COLUMN target_phone_number VARCHAR"))
            if "target_audiences" not in columns:
                conn.execute(text("ALTER TABLE day_agent_configs ADD COLUMN target_audiences TEXT DEFAULT '[\"student\", \"faculty\"]'"))
            if "user_id" not in columns:
                conn.execute(text("ALTER TABLE day_agent_configs ADD COLUMN user_id INTEGER DEFAULT 1"))
            if "client_logo_url" not in columns:
                conn.execute(text("ALTER TABLE day_agent_configs ADD COLUMN client_logo_url VARCHAR"))

        # Drop the old global unique index on publish_weekday and create a multi-tenant one
        with engine.begin() as conn:
            try:
                # First check if the old unique index exists
                indexes = conn.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_day_agent_configs_publish_weekday'")).fetchall()
                if indexes:
                    # Drop it because it blocks multi-tenant agents
                    conn.execute(text("DROP INDEX ix_day_agent_configs_publish_weekday"))
                    # Recreate it as a non-unique index
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_day_agent_configs_publish_weekday ON day_agent_configs (publish_weekday)"))
                
                # Add a proper unique index for (user_id, publish_weekday) if it doesn't exist
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_day_agent_configs_user_weekday ON day_agent_configs (user_id, publish_weekday)"))
            except Exception as e:
                # Only print actual errors, not 'already exists' from SQLite
                if "already exists" not in str(e):
                    print(f"Index migration error: {e}")

ensure_schema()

# Auth Setup
SECRET_KEY = os.getenv("JWT_SECRET", "supersecretkey_change_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 week

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


app = FastAPI(title="INKER SaaS Platform", version="3.0.0")
app.mount("/newsletters", StaticFiles(directory="generated_newsletters"), name="newsletters")
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    with open("../frontend/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

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
        # Create a default user if none exists
        if db.query(User).count() == 0:
            default_user = User(email="admin@inker.com", hashed_password=get_password_hash("password123"))
            db.add(default_user)
            db.commit()
            seed_day_configs(db) # Seed default agents for admin
            
            # Assign the seeded agents to this default user
            db.query(DayAgentConfig).update({DayAgentConfig.user_id: default_user.id})
            db.commit()
    finally:
        db.close()
        
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_run_agents, 'cron', minute='*')
    scheduler.start()

def check_and_run_agents():
    db = SessionLocal()
    try:
        now = datetime.now(ZoneInfo('Asia/Kolkata'))
        current_weekday = now.weekday()
        current_time = now.strftime("%H:%M")
        
        # Multi-tenant: Get all active configs for ALL users that match the current day/time
        configs = db.query(DayAgentConfig).filter(
            DayAgentConfig.publish_weekday == current_weekday,
            DayAgentConfig.target_time == current_time,
            DayAgentConfig.is_active.is_(True)
        ).all()
        
        for config in configs:
            recent = db.query(models.PipelineExecution).filter(
                models.PipelineExecution.publish_weekday == current_weekday,
                models.PipelineExecution.user_id == config.user_id,
                models.PipelineExecution.created_at >= now - timedelta(minutes=2)
            ).first()
            
            if not recent:
                execution = models.PipelineExecution(
                    topic=config.edition_title,
                    publish_weekday=current_weekday,
                    user_id=config.user_id,
                    status="pending",
                )
                db.add(execution)
                db.commit()
                db.refresh(execution)
                
                threading.Thread(target=run_pipeline, args=(execution.id,)).start()
                print(f"⏰ Scheduler triggered agent for User {config.user_id} - {config.edition_title} at {current_time}")
                
    except Exception as e:
        print(f"Scheduler Error: {e}")
    finally:
        db.close()


# --- AUTH ENDPOINTS ---

@app.post("/api/auth/register", response_model=Token)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_pw = get_password_hash(user_in.password)
    new_user = User(email=user_in.email, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email, "id": current_user.id}


class RegenerateRequest(BaseModel):
    token: str
    feedback: str

class ManualGenerateRequest(BaseModel):
    publish_weekday: int | None = None


def _config_response(config: DayAgentConfig) -> DayAgentConfigResponse:
    return DayAgentConfigResponse(
        id=config.id,
        user_id=config.user_id,
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
        client_logo_url=config.client_logo_url
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


# --- AGENT ENDPOINTS ---

@app.get("/api/agents", response_model=list[DayAgentConfigResponse])
def list_day_agents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    configs = (
        db.query(DayAgentConfig)
        .filter(DayAgentConfig.user_id == current_user.id)
        .order_by(DayAgentConfig.publish_weekday)
        .all()
    )
    return [_config_response(cfg) for cfg in configs]

@app.post("/api/agents", response_model=DayAgentConfigResponse)
def create_day_agent(
    body: DayAgentConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy.exc import IntegrityError
    config = DayAgentConfig(
        user_id=current_user.id,
        publish_weekday=body.publish_weekday,
        day_name=body.day_name,
        edition_title=body.edition_title,
        scout_system_prompt=body.scout_system_prompt,
        writer_system_prompt=body.writer_system_prompt,
        rss_feeds=json.dumps(body.rss_feeds),
        is_active=body.is_active,
        target_time=body.target_time,
        target_phone_number=body.target_phone_number,
        target_audiences=json.dumps(body.target_audiences),
        client_logo_url=body.client_logo_url
    )
    db.add(config)
    try:
        db.commit()
        db.refresh(config)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"You already have an agent scheduled for {body.day_name}. Please edit the existing one instead.")
        
    return _config_response(config)

@app.get("/api/agents/{agent_id}", response_model=DayAgentConfigResponse)
def get_day_agent(agent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    config = db.query(DayAgentConfig).filter(DayAgentConfig.id == agent_id, DayAgentConfig.user_id == current_user.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found.")
    return _config_response(config)


@app.put("/api/agents/{agent_id}", response_model=DayAgentConfigResponse)
def update_day_agent(
    agent_id: int,
    body: DayAgentConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy.exc import IntegrityError
    config = db.query(DayAgentConfig).filter(DayAgentConfig.id == agent_id, DayAgentConfig.user_id == current_user.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found.")

    config.publish_weekday = body.publish_weekday
    config.day_name = body.day_name
    config.edition_title = body.edition_title
    config.scout_system_prompt = body.scout_system_prompt
    config.writer_system_prompt = body.writer_system_prompt
    config.rss_feeds = json.dumps(body.rss_feeds)
    config.is_active = body.is_active
    config.target_time = body.target_time
    config.target_phone_number = body.target_phone_number
    config.target_audiences = json.dumps(body.target_audiences)
    if body.client_logo_url is not None:
        config.client_logo_url = body.client_logo_url
        
    try:
        db.commit()
        db.refresh(config)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"You already have an agent scheduled for {body.day_name}. Please edit that existing agent instead of creating a conflict.")
        
    return _config_response(config)

@app.delete("/api/agents/{agent_id}")
def delete_day_agent(agent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    config = db.query(DayAgentConfig).filter(DayAgentConfig.id == agent_id, DayAgentConfig.user_id == current_user.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found.")
    db.delete(config)
    db.commit()
    return {"status": "deleted"}

@app.post("/api/upload_logo")
async def upload_logo(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    extension = file.filename.split(".")[-1]
    filename = f"logo_{current_user.id}_{uuid.uuid4().hex}.{extension}"
    file_path = os.path.join("..", "frontend", "logos", filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"url": f"/static/logos/{filename}"}


# --- AUTO-PROMPT GENERATION ---

class AutoPromptRequest(BaseModel):
    description: str

import openai
@app.post("/api/agents/auto_prompt")
def generate_auto_prompt(req: AutoPromptRequest, current_user: User = Depends(get_current_user)):
    """
    Uses LLM to magically engineer the Scout and Writer prompts based on a simple description!
    Injects the World-Class Marketing Expert persona.
    """
    try:
        from core.config import OPENAI_API_KEY
        openai.api_key = OPENAI_API_KEY
        
        system_msg = """You are an expert AI prompt engineer and research assistant. The user will describe an AI agent they want to build to automate their newsletter. 
        You must return exactly a JSON object with three keys: "scout_system_prompt", "writer_system_prompt", and "rss_feeds".
        
        1. 'scout_system_prompt' should instruct an agent to find news articles related to their topic.
        2. 'writer_system_prompt' MUST enforce the persona of a WORLD-CLASS MARKETING EXPERT. It must instruct the writer to write highly engaging, persuasive, and click-worthy short content.
        3. 'rss_feeds' MUST be an array of strings containing 3 to 5 highly reputable, real RSS feed URLs that are highly relevant to the user's topic (e.g., TechCrunch, Wired, NYT, specific niche blogs).
        
        Do NOT wrap the JSON in markdown code blocks. Just return raw JSON.
        """
        
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Create prompts for this agent description: {req.description}"}
            ],
            response_format={ "type": "json_object" }
        )
        
        result_json = response.choices[0].message.content
        result = json.loads(result_json)
        return result
    except Exception as e:
        print(f"Auto-Prompt Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate prompts.")


# --- REMAINDER OF MAIN.PY ---

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
    current_user: User = Depends(get_current_user)
):
    weekday = body.publish_weekday
    if weekday is None:
        weekday = get_publish_weekday_for_generation()
    if weekday is None or weekday not in PUBLISH_WEEKDAYS:
        raise HTTPException(status_code=400, detail="No valid publish day selected.")

    # Modified to only run the agent for the current user manually
    result = start_scheduled_generation(db, publish_weekday=weekday, user_id=current_user.id)
    if not result["started"]:
        raise HTTPException(status_code=400, detail=result["reason"])

    background_tasks.add_task(run_pipeline, result["execution_id"])
    return result


@app.get("/api/executions")
def get_executions(weekday: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(models.PipelineExecution).filter(models.PipelineExecution.user_id == current_user.id)
    if weekday is not None:
        query = query.filter(models.PipelineExecution.publish_weekday == weekday)
    
    # 5 per day, or 10 if looking globally
    limit = 5 if weekday is not None else 10
    
    rows = query.order_by(models.PipelineExecution.created_at.desc()).limit(limit).all()
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
        # Get the config specific to this user's execution
        cfg = db.query(DayAgentConfig).filter(
            DayAgentConfig.publish_weekday == execution.publish_weekday,
            DayAgentConfig.user_id == execution.user_id
        ).first()
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
