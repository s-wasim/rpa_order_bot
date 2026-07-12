from langchain_anthropic import ChatAnthropic
from app.settings import ANTHROPIC_API_KEY

def get_llm():
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        temperature=0,
        api_key=ANTHROPIC_API_KEY,
        timeout=60,
    )
