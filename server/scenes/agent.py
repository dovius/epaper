"""
Agent Scene - A screen Claude keeps up to date over MCP (set_agent_scene)
"""

from datetime import datetime
from typing import Optional

from PIL import Image

from layout import HeaderBlock, TextBlock, parse_block, render_layout
from .base import Scene, SceneConfig


class AgentScene(Scene):
    """Shows the layout last set with the set_agent_scene MCP tool"""

    id = "agent"
    name = "Agent Board"
    description = "A screen Claude keeps up to date over MCP"
    icon = "🤖"

    STATE_FILE = "agent_scene.json"

    def __init__(self, config: Optional[SceneConfig] = None):
        # New scenes start outside the rotation
        super().__init__(config or SceneConfig(enabled=False))
        # {"title", "blocks": [...], "updated_at"} or None
        self._content: Optional[dict] = self.load_state(self.STATE_FILE)

    def set_content(self, title: str, blocks: list):
        """Replace the board's layout (blocks as models or dicts)"""
        self._content = {
            'title': title,
            'blocks': [parse_block(b).model_dump() for b in blocks],
            'updated_at': datetime.now().isoformat(timespec='seconds'),
        }
        self.save_state(self.STATE_FILE, self._content)

    def clear(self):
        """Empty the board"""
        self._content = None
        self.save_state(self.STATE_FILE, None)

    async def fetch_data(self) -> dict:
        return self._content or {}

    def blocks(self, data: dict) -> list:
        """The blocks to render: the stored layout under a header with the update time"""
        if not data:
            return [
                HeaderBlock(text=self.name),
                TextBlock(text="Nothing here yet. Ask Claude to put something on this board.", size="s"),
            ]

        updated = datetime.fromisoformat(data['updated_at'])
        stamp = updated.strftime("%H:%M" if updated.date() == datetime.now().date() else "%m-%d")
        blocks = [parse_block(b) for b in data['blocks']]
        if blocks and blocks[0].type == "header":
            if not blocks[0].right:
                blocks[0] = blocks[0].model_copy(update={'right': stamp})
        else:
            blocks.insert(0, HeaderBlock(text=data.get('title') or self.name, right=stamp))
        return blocks

    def render(self, data: dict, generator) -> Image.Image:
        return render_layout(self.blocks(data), generator)[0]
