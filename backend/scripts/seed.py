import json
from sqlalchemy.orm import Session
from core.models import DayAgentConfig
from core.config import DEFAULT_RSS_FEEDS, WEEKDAY_NAMES, ALL_WEEKDAY_NAMES


DEFAULT_CONFIGS = [
    {
        "publish_weekday": 0,
        "edition_title": "Monday Innovation Brief",
        "scout_system_prompt": (
            "Find the most important AI and machine learning research breakthroughs from the last 48 hours. "
            "Prioritize papers, lab announcements, and hard technical milestones from reputed institutions."
        ),
        "writer_system_prompt": (
            "Write an engaging tech newsletter for Monday that teaches readers about recent AI/ML research innovations. "
            "Use clear explanations, cite sources, and help students understand why each breakthrough matters. "
            "Faculty edition should emphasize methodology, benchmarks, and academic implications."
        ),
    },
    {
        "publish_weekday": 1,
        "edition_title": "Tuesday Product & Industry Pulse",
        "scout_system_prompt": (
            "Find the most significant AI product launches, engineering deployments, and industry shifts from reputed tech firms "
            "in the last 48 hours. Ignore listicles and hype without substance."
        ),
        "writer_system_prompt": (
            "Write an engaging Tuesday newsletter about real AI product and industry innovations. "
            "Explain what changed, who built it, and what developers should learn from it. "
            "Faculty edition should analyze architecture choices, market impact, and research-to-product translation."
        ),
    },
    {
        "publish_weekday": 2,
        "edition_title": "Wednesday Deep Dive",
        "scout_system_prompt": (
            "Find in-depth technical articles, research papers, and engineering deep dives from reputed sources "
            "in the last 48 hours. Focus on fundamental concepts and architectural patterns."
        ),
        "writer_system_prompt": (
            "Write a technical Wednesday newsletter that dives deep into engineering concepts and research methodologies. "
            "Student edition should break down complex topics into digestible lessons. "
            "Faculty edition should explore theoretical foundations and pedagogical applications."
        ),
    },
    {
        "publish_weekday": 3,
        "edition_title": "Thursday Frontier Report",
        "scout_system_prompt": (
            "Find cutting-edge AI research, emerging technologies, and paradigm-shifting innovations from top labs "
            "and universities in the last 48 hours. Prioritize novel approaches and breakthrough results."
        ),
        "writer_system_prompt": (
            "Write an insightful Thursday newsletter about emerging tech frontiers and novel research directions. "
            "Student edition should spark curiosity and highlight learning opportunities. "
            "Faculty edition should analyze research gaps, methodology innovations, and future implications."
        ),
    },
    {
        "publish_weekday": 4,
        "edition_title": "Friday Tech Awareness Digest",
        "scout_system_prompt": (
            "Find engaging, educational tech stories from the last week: breakthroughs, clever engineering, "
            "surprising applications, and awareness-worthy innovations from trusted sources."
        ),
        "writer_system_prompt": (
            "Write a lively Friday newsletter that makes readers aware of fascinating recent tech innovations. "
            "Include practical learning angles, interesting insights, and conversational tone for students. "
            "Faculty edition should connect stories to broader trends, ethics, and classroom discussion prompts."
        ),
    },
    {
        "publish_weekday": 5,
        "edition_title": "Saturday Weekend Workshop",
        "scout_system_prompt": (
            "Find hands-on tutorials, open-source projects, weekend-friendly learning resources, and practical "
            "tech skills from reputed sources published in the last week."
        ),
        "writer_system_prompt": (
            "Write an actionable Saturday newsletter focused on practical skills and weekend learning projects. "
            "Student edition should include step-by-step guides and project ideas. "
            "Faculty edition should suggest curriculum integrations and lab exercises."
        ),
    },
    {
        "publish_weekday": 6,
        "edition_title": "Sunday Strategic Review",
        "scout_system_prompt": (
            "Find strategic tech analyses, industry trend reports, policy updates, and big-picture technology "
            "assessments from reputable think tanks and publications in the last week."
        ),
        "writer_system_prompt": (
            "Write a reflective Sunday newsletter that connects weekly tech developments into larger narratives. "
            "Student edition should build strategic thinking and industry awareness. "
            "Faculty edition should provide discussion frameworks and strategic context for classroom use."
        ),
    },
]


def seed_day_configs(db: Session, default_user_id: int = None):
    feeds_json = json.dumps(DEFAULT_RSS_FEEDS)
    for cfg in DEFAULT_CONFIGS:
        existing = (
            db.query(DayAgentConfig)
            .filter(DayAgentConfig.publish_weekday == cfg["publish_weekday"])
            .first()
        )
        if existing:
            continue
        db.add(
            DayAgentConfig(
                publish_weekday=cfg["publish_weekday"],
                day_name=ALL_WEEKDAY_NAMES[cfg["publish_weekday"]],
                edition_title=cfg["edition_title"],
                scout_system_prompt=cfg["scout_system_prompt"],
                writer_system_prompt=cfg["writer_system_prompt"],
                rss_feeds=feeds_json,
                is_active=cfg["publish_weekday"] in {0, 2, 4},
                user_id=default_user_id
            )
        )
    db.commit()
