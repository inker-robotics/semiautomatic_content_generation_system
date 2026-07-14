from pydantic import BaseModel, Field, EmailStr
from typing import List

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class NewsletterSection(BaseModel):
    title: str = Field(description="Engaging section headline.")
    body: str = Field(description="A single, highly engaging, very short and informative paragraph (2-3 sentences max) that hooks the reader and delivers crucial information. NO walls of text. Make it interesting and thrilling.")
    source: str = Field(description="Reputed source name, e.g. MIT Technology Review.")
    source_url: str = Field(description="The actual URL link to the original article or paper.", default="#")
    # NEW: Requesting a caricature to be interesting at first sight
    image_prompt: str = Field(description="A highly visual prompt for an AI image generator. IMPORTANT: Request an engaging, eye-catching CARICATURE or stylized illustration that tells the core story at a single glance. No text in the image.")

class NewsletterEdition(BaseModel):
    subject_line: str = Field(description="Compelling email subject line.")
    preheader: str = Field(description="Short preview text shown in inbox.")
    intro: str = Field(description="Engaging opening paragraph hooking the reader.")
    # NEW: Forcing exactly 1 top story to maximize impact
    sections: List[NewsletterSection] = Field(description="Exactly 1 single most interesting, relevant, and thrilling top story of the day.", min_length=1, max_length=1)
    closing: str = Field(description="Closing paragraph tying themes together.")
    call_to_action: str = Field(description="Inspiring call to action.")

class DynamicNewsletterPayload(BaseModel):
    editions: dict[str, NewsletterEdition] = Field(description="Dictionary where the key is the audience name (in lowercase, e.g. 'student', 'faculty', 'alumni') and the value is their tailored edition.")

class DayAgentConfigCreate(BaseModel):
    publish_weekday: int
    day_name: str
    edition_title: str
    scout_system_prompt: str
    writer_system_prompt: str
    rss_feeds: List[str]
    is_active: bool = True
    target_time: str = "09:00"
    target_phone_number: str | None = None
    target_audiences: List[str] = ["student", "faculty"]
    client_logo_url: str | None = None

class DayAgentConfigUpdate(BaseModel):
    publish_weekday: int
    day_name: str
    edition_title: str
    scout_system_prompt: str
    writer_system_prompt: str
    rss_feeds: List[str]
    is_active: bool = True
    target_time: str = "09:00"
    target_phone_number: str | None = None
    target_audiences: List[str] = ["student", "faculty"]
    client_logo_url: str | None = None


class DayAgentConfigResponse(BaseModel):
    id: int
    user_id: int
    publish_weekday: int
    day_name: str
    edition_title: str
    scout_system_prompt: str
    writer_system_prompt: str
    rss_feeds: List[str]
    is_active: bool
    target_time: str
    target_phone_number: str | None
    target_audiences: List[str]
    client_logo_url: str | None

    class Config:
        from_attributes = True