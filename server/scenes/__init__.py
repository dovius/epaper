"""
Scene system for E-Paper Display
================================
Each scene represents a different view that can be displayed on the e-paper.
"""

from .base import Scene, SceneConfig
from .stocks import StocksScene
from .bitcoin import BitcoinScene
from .weather import WeatherScene
from .notifications import NotificationsScene
from .network import NetworkScene
from .system import SystemScene
from .agent import AgentScene
from .digest import DigestScene

__all__ = [
    'Scene',
    'SceneConfig',
    'StocksScene',
    'BitcoinScene',
    'WeatherScene',
    'NotificationsScene',
    'NetworkScene',
    'SystemScene',
    'AgentScene',
    'DigestScene',
]

