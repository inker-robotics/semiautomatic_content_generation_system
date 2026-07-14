from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from core.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DayAgentConfig(Base):
    __tablename__ = "day_agent_configs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    publish_weekday = Column(Integer, index=True, nullable=False)
    day_name = Column(String, nullable=False)
    edition_title = Column(String, nullable=False)
    scout_system_prompt = Column(Text, nullable=False)
    writer_system_prompt = Column(Text, nullable=False)
    rss_feeds = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    target_time = Column(String, default="09:00")
    target_phone_number = Column(String, nullable=True)
    target_audiences = Column(Text, default='["student", "faculty"]')
    client_logo_url = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PipelineExecution(Base):
    __tablename__ = "pipeline_executions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Making it nullable for backwards compatibility
    topic = Column(String, nullable=False)
    publish_weekday = Column(Integer, nullable=True)
    status = Column(String, default="pending")
    execution_log = Column(Text, nullable=True)
    newsletter_html = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SecureApproval(Base):
    __tablename__ = "secure_approvals"
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("pipeline_executions.id"))
    secure_token = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="awaiting_review")

class NewsHistory(Base):
    __tablename__ = "news_history"
    id = Column(Integer, primary_key=True, index=True)
    link = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
