# backend/orchestrator.py
import json
from typing import TypedDict
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

import feedparser
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from core.schemas import DynamicNewsletterPayload
from core.database import SessionLocal
from core.models import NewsHistory

load_dotenv()


class GraphState(TypedDict):
    day_config: dict
    feedback: str
    raw_news: list
    draft_payload: dict
    status: str


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
structured_llm = llm.with_structured_output(DynamicNewsletterPayload, method='function_calling')


def fetch_news_node(state: GraphState):
    """Fetch recent articles from configured RSS feeds."""
    config = state["day_config"]
    feeds = config.get("rss_feeds") or []
    
    # Add massive list of reputed feeds and research paper sources to ensure we have the best pool
    extra_feeds = [
        "https://hnrss.org/frontpage",
        "https://www.artificialintelligence-news.com/feed/",
        "https://spectrum.ieee.org/rss/fulltext",
        "https://venturebeat.com/category/ai/feed/",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.technologyreview.com/feed/",
        "https://www.wired.com/feed/category/science/latest/rss",
        "https://arstechnica.com/feed/",
        "http://export.arxiv.org/rss/cs.AI",
        "http://export.arxiv.org/rss/cs.LG",
        "http://export.arxiv.org/rss/cs.RO"
    ]
    for ef in extra_feeds:
        if ef not in feeds:
            feeds.append(ef)
            
    print(f"🕵️ [Scout] Fetching news for {config.get('edition_title')} from {len(feeds)} feeds...")

    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    recent_articles = []

    # Get historical links from DB to prevent repetition
    db = SessionLocal()
    try:
        past_news = db.query(NewsHistory.link).all()
        past_links = {row[0] for row in past_news}
    except Exception as e:
        print(f"⚠️ DB Error fetching news history: {e}")
        past_links = set()

    for feed_url in feeds:
        try:
            parsed_feed = feedparser.parse(feed_url)
            for entry in parsed_feed.entries:
                try:
                    pub_tuple = entry.published_parsed
                    pub_date = datetime(*pub_tuple[:6], tzinfo=timezone.utc)
                    link = entry.get("link", "")
                    
                    if pub_date >= three_days_ago and link and link not in past_links:
                        recent_articles.append(
                            {
                                "title": entry.title,
                                "source": feed_url.split("/")[2],
                                "summary": entry.get("summary", "")[:400],
                                "link": link,
                            }
                        )
                        # Add to past_links so we don't pick it twice in the same run
                        past_links.add(link)
                except Exception:
                    continue
                if len(recent_articles) >= 30:
                    break
        except Exception as e:
            print(f"⚠️ Feed error on {feed_url}: {e}")

    # Save the newly selected articles to history
    if recent_articles:
        try:
            for article in recent_articles:
                new_hist = NewsHistory(link=article["link"], title=article["title"])
                db.add(new_hist)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"⚠️ Error saving to NewsHistory: {e}")
    db.close()

    if not recent_articles:
        recent_articles = [
            {
                "title": "No major headlines in the last 72 hours",
                "source": "System",
                "summary": "Use recent reputable tech context and explain ongoing trends clearly.",
                "link": "",
            }
        ]

    return {"raw_news": recent_articles[:30]}


def write_newsletter_node(state: GraphState):
    """Turn fetched news into student + faculty newsletter editions."""
    config = state["day_config"]
    print(f"✍️ [Writer] Composing newsletter for {config.get('edition_title')}...")

    scout_prompt = config.get("scout_system_prompt", "")
    writer_prompt = config.get("writer_system_prompt", "")

    # INDENTATION FIXED HERE
    target_audiences_raw = config.get("target_audiences")
    target_audiences = json.loads(target_audiences_raw) if target_audiences_raw else ["student", "faculty"]
    target_audiences_str = ", ".join(target_audiences)

    system_prompt = (
        "You are an elite tech newsletter editor.\n"
        "Your job is to TEACH profound, mind-blowing insights from recent tech innovations.\n"
        "STRICT RULES:\n"
        "- NO listicles ('Top 10...') and NO boring corporate news summaries.\n"
        "- Dive deep into the 'HOW' and 'WHY'. Explain the underlying physics, math, or computer science concept that makes this possible.\n"
        "- Treat the reader as an intelligent learner who wants to be fascinated, not just informed. Make them go 'Wow, I never knew that!'.\n"
        "- Every section must cite a source and include a concrete, educational takeaway.\n"
        "- CRITICAL: Each edition must contain EXACTLY 1 section. You must aggressively filter the news and pick ONLY the absolute most interesting, thrilling, and highly relevant story of the day.\n"
        "- The headings MUST be irresistibly interesting, almost clickbait-style but highly professional, to hook the reader immediately.\n\n"
        "TARGET AUDIENCES:\n"
        f"You must create a distinct edition for each of the following audiences: {target_audiences_str}.\n"
        "Automatically adapt the vocabulary, tone, depth, and length for each specific audience. "
        "The dictionary keys in your JSON response MUST strictly match the audience names provided above (in lowercase).\n\n"
        f"Scout focus: {scout_prompt}\n\n"
        f"Writer focus: {writer_prompt}"
    )

    user_message = f"Edition: {config.get('edition_title')}\n\nRecent articles:\n{json.dumps(state['raw_news'], indent=2)}"
    if state.get("feedback"):
        user_message += f"\n\n🚨 MANAGER REVISION DIRECTIVE:\n{state['feedback']}"

    response = structured_llm.invoke(
        [
            ("system", system_prompt),
            ("user", user_message),
        ]
    )

    return {"draft_payload": response.model_dump(), "status": "drafted"}


workflow = StateGraph(GraphState)
workflow.add_node("scout", fetch_news_node)
workflow.add_node("writer", write_newsletter_node)
workflow.set_entry_point("scout")
workflow.add_edge("scout", "writer")
workflow.add_edge("writer", END)

production_pipeline = workflow.compile()