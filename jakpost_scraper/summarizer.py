"""Summarize articles via the Claude Agent SDK."""

import asyncio
import shutil

from claude_agent_sdk import ClaudeAgentOptions, query

try:  # message types live in .types on most versions, top-level on some
    from claude_agent_sdk.types import AssistantMessage, TextBlock
except ImportError:  # pragma: no cover
    from claude_agent_sdk import AssistantMessage, TextBlock

from .models import Article, Summary, now_utc

SUMMARIZER_SYSTEM_PROMPT = (
    "You are a concise news summarizer for an Indonesian news digest. "
    "You write clear, factual, neutral summaries. You never invent facts "
    "beyond the provided text. Respond with summary text only — no preamble."
)
# Per-article summaries beyond this count are digested in batches.
DIGEST_BATCH_SIZE = 40


class PreflightError(Exception):
    """Raised when the environment cannot run summarization."""


def preflight_check() -> None:
    """Verify the `claude` CLI is installed (required by the Agent SDK)."""
    if shutil.which("claude") is None:
        raise PreflightError(
            "The `claude` CLI was not found on PATH. Install and authenticate "
            "Claude Code, or run with --no-summary."
        )


def summarize(articles: list[Article], mode: str, model: str,
              concurrency: int) -> list[Summary]:
    """Summarize articles in the given mode. Synchronous entry point."""
    if not articles:
        return []
    return asyncio.run(_run(articles, mode, model, concurrency))


async def _run(articles: list[Article], mode: str, model: str,
               concurrency: int) -> list[Summary]:
    semaphore = asyncio.Semaphore(max(1, concurrency))
    per_article = await asyncio.gather(
        *[_summarize_one(a, model, semaphore) for a in articles]
    )
    summaries: list[Summary] = []
    if mode in ("per-article", "both"):
        summaries.extend(per_article)
    if mode in ("digest", "both"):
        summaries.append(await _summarize_digest(per_article, model))
    return summaries


async def _summarize_one(article: Article, model: str,
                         semaphore: asyncio.Semaphore) -> Summary:
    async with semaphore:
        prompt = _per_article_prompt(article)
        try:
            text = await _retry(lambda: _ask_claude(prompt, model))
        except Exception as e:  # noqa: BLE001 - record failure, keep going
            return Summary(kind="per-article", text="", model=model,
                           generated_at=now_utc(), article_urls=[article.url],
                           error=str(e))
        return Summary(kind="per-article", text=text, model=model,
                       generated_at=now_utc(), article_urls=[article.url])


async def _ask_claude(prompt: str, model: str) -> str:
    """Send one prompt to Claude via the Agent SDK and return the text reply."""
    options = ClaudeAgentOptions(
        system_prompt=SUMMARIZER_SYSTEM_PROMPT,
        model=model,
        allowed_tools=[],
        max_turns=1,
    )
    chunks: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    chunks.append(block.text)
    return "".join(chunks).strip()


async def _retry(coro_factory, attempts: int = 2):
    """Await coro_factory(), retrying up to `attempts` times total."""
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await coro_factory()
        except Exception as e:  # noqa: BLE001 - retried below
            last_error = e
    raise last_error


def _per_article_prompt(article: Article) -> str:
    note = ""
    if article.is_paywalled:
        note = ("\n\nNote: only the article teaser is available because the "
                "full text is paywalled. Summarize what is provided.")
    return (
        "Summarize the following news article in 2-4 sentences. Focus on what "
        f"happened, who is involved, and why it matters.{note}\n\n"
        f"Title: {article.title}\n\n{article.body}"
    )
