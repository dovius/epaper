"""
Digest Scene - News headlines Claude writes with web search (Claude API)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import anthropic
from PIL import Image
from pydantic import BaseModel, Field

from layout import HeaderBlock, ListBlock, TextBlock, render_layout
from .base import Scene, SceneConfig

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
# If the model declines, the API retries on Anthropic's recommended fallback model
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Scheduled runs that were missed (server down) are caught up within this window
CATCH_UP = timedelta(hours=3)

RESEARCH_PROMPT = """\
Today is {today}. Search the web for the most important news of the last 24 hours \
about: {topics}.

Write a short plain-text briefing: 6 to 8 items, one or two factual sentences each, \
most important first. Skip opinion pieces and anything older than two days."""

FORMAT_PROMPT = """\
Turn this news briefing into 5 headlines for a tiny black-and-white e-paper display. \
Write them in {language}. Each headline is at most 32 characters: a few words with \
the key fact or number, no emoji, no trailing period. Most important first.

<briefing>
{briefing}
</briefing>"""


class Digest(BaseModel):
    """Structured output of the formatting call"""
    items: list[str] = Field(description="5 headlines of at most 32 characters each, most important first")


class DigestScene(Scene):
    """Headlines written by Claude, refreshed on a schedule or on demand"""

    id = "digest"
    name = "AI Digest"
    description = "News headlines Claude writes with web search"
    icon = "📰"

    settings_schema = [
        {
            'key': 'anthropic_api_key',
            'label': 'Anthropic API Key',
            'type': 'password',
            'default': '',
            'description': 'From console.anthropic.com. A run costs roughly $0.15-0.30',
        },
        {
            'key': 'topics',
            'label': 'Topics',
            'type': 'text',
            'default': 'Lithuania, technology, markets',
        },
        {
            'key': 'language',
            'label': 'Language',
            'type': 'select',
            'options': ['lt', 'en'],
            'default': 'lt',
        },
        {
            'key': 'run_at',
            'label': 'Run At',
            'type': 'text',
            'default': '07:30',
            'description': 'HH:MM, comma-separated for several runs a day',
        },
        {
            'key': 'auto_run',
            'label': 'Run on Schedule',
            'type': 'checkbox',
            'default': True,
        },
        {
            'key': 'model',
            'label': 'Model',
            'type': 'text',
            'default': DEFAULT_MODEL,
        },
    ]

    STATE_FILE = "digest.json"

    def __init__(self, config: Optional[SceneConfig] = None):
        # New scenes start outside the rotation
        super().__init__(config or SceneConfig(enabled=False))
        # {"items", "generated_at", "model", "usage", "last_attempt_at", "error"}
        self._state: dict = self.load_state(self.STATE_FILE, {})
        self._lock = asyncio.Lock()

    def _setting(self, key: str):
        """A setting, or its default when unset or empty"""
        value = self.config.settings.get(key)
        if value is None or value == '':
            return next(f['default'] for f in self.settings_schema if f['key'] == key)
        return value

    # --- Writing the digest --------------------------------------------------

    def not_ready(self) -> Optional[str]:
        """Why run() can't start right now, or None"""
        if not self._setting('anthropic_api_key'):
            return "Set an Anthropic API key in the AI Digest scene settings"
        if self._lock.locked():
            return "A digest is already being written"
        return None

    async def run(self) -> dict:
        """Write a new digest now. Errors are raised and also kept for the web UI."""
        problem = self.not_ready()
        if problem:
            raise RuntimeError(problem)

        async with self._lock:
            self._state['last_attempt_at'] = datetime.now().isoformat(timespec='seconds')
            try:
                items, usage, model = await self._write(self._setting('anthropic_api_key'))
            except Exception as e:
                self._state['error'] = str(e) or type(e).__name__
                self.save_state(self.STATE_FILE, self._state)
                logger.error(f"Digest failed: {self._state['error']}")
                raise
            self._state.update({
                'items': items,
                'generated_at': datetime.now().isoformat(timespec='seconds'),
                'model': model,
                'usage': usage,
                'error': None,
            })
            self.save_state(self.STATE_FILE, self._state)
            logger.info(f"Digest written: {len(items)} headlines, {usage}")
            return self._state

    async def _write(self, api_key: str) -> tuple[list[str], dict, str]:
        """Two calls: research with web search, then headlines as structured output"""
        client = anthropic.AsyncAnthropic(api_key=api_key)
        model = self._setting('model')
        usage = {'input_tokens': 0, 'output_tokens': 0, 'web_searches': 0}

        def count(response):
            usage['input_tokens'] += response.usage.input_tokens
            usage['output_tokens'] += response.usage.output_tokens
            if response.usage.server_tool_use:
                usage['web_searches'] += response.usage.server_tool_use.web_search_requests or 0
            if response.stop_reason == "refusal":
                category = response.stop_details.category if response.stop_details else None
                raise RuntimeError(f"Claude declined to write the digest ({category or 'no category'})")
            if response.stop_reason == "max_tokens":
                raise RuntimeError("Claude's answer was cut off (max_tokens)")

        # 1. Research. A long server-side search loop can pause; resend to continue.
        prompt = RESEARCH_PROMPT.format(today=datetime.now().strftime("%A, %Y-%m-%d"),
                                        topics=self._setting('topics'))
        messages = [{"role": "user", "content": prompt}]
        briefing = []
        for _ in range(4):
            response = await client.beta.messages.create(
                model=model,
                max_tokens=16000,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                output_config={"effort": "medium"},
                tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
                messages=messages,
            )
            count(response)
            briefing += [block.text for block in response.content if block.type == "text"]
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
        else:
            raise RuntimeError("The web search didn't finish")

        # 2. Headlines short enough for the display
        language = "Lithuanian" if self._setting('language') == 'lt' else "English"
        response = await client.beta.messages.parse(
            model=model,
            max_tokens=4000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "low"},
            output_format=Digest,
            messages=[{"role": "user", "content": FORMAT_PROMPT.format(
                language=language, briefing="".join(briefing).strip())}],
        )
        count(response)
        if response.parsed_output is None:
            raise RuntimeError("Claude's headlines couldn't be read")
        items = [item.strip() for item in response.parsed_output.items if item.strip()]
        return items[:6], usage, response.model

    # --- Schedule ------------------------------------------------------------

    def _due(self, now: datetime) -> bool:
        """A run_at time has passed (within CATCH_UP) without a run or attempt since"""
        if not (self.config.enabled and self._setting('auto_run') and self._setting('anthropic_api_key')):
            return False
        last = max(self._state.get('generated_at') or '', self._state.get('last_attempt_at') or '')
        for slot in str(self._setting('run_at')).split(','):
            try:
                at = datetime.strptime(slot.strip(), "%H:%M").time()
            except ValueError:
                continue
            scheduled = datetime.combine(now.date(), at)
            if scheduled <= now < scheduled + CATCH_UP and last < scheduled.isoformat(timespec='seconds'):
                return True
        return False

    async def schedule_loop(self):
        """Background task: write the digest at the run_at times"""
        while True:
            try:
                if self._due(datetime.now()):
                    await self.run()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # Already logged and shown in the web UI; next try at the next slot
            await asyncio.sleep(30)

    # --- Scene ---------------------------------------------------------------

    async def fetch_data(self) -> dict:
        """The last digest (writing one is run(), not a render)"""
        return self._state

    def render(self, data: dict, generator) -> Image.Image:
        title = "Naujienos" if self._setting('language') == 'lt' else "News"
        if not data.get('items'):
            hint = (f"Last run failed: {data['error']}" if data.get('error')
                    else "No digest yet. Set an Anthropic API key in the scene settings, then Run now.")
            blocks = [HeaderBlock(text=title), TextBlock(text=hint[:500], size="s")]
        else:
            generated = datetime.fromisoformat(data['generated_at'])
            stamp = generated.strftime("%H:%M" if generated.date() == datetime.now().date() else "%m-%d")
            blocks = [
                HeaderBlock(text=title, right=stamp),
                ListBlock(items=[item[:60] for item in data['items']][:12]),
            ]
        return render_layout(blocks, generator)[0]

    def get_info(self) -> dict:
        info = super().get_info()
        if self._state.get('error') and not info['last_error']:
            info['last_error'] = f"Last run failed: {self._state['error']}"
        info['digest'] = {k: self._state.get(k) for k in ('generated_at', 'last_attempt_at', 'model', 'usage')}
        return info
