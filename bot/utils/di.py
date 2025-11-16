from typing import Optional

from config import Config
from bot.services.container import ServiceContainer

_config: Optional[Config] = None
_services: Optional[ServiceContainer] = None


def set_config(config: Config) -> None:
    global _config
    _config = config


def get_config() -> Config:
    if _config is None:
        raise RuntimeError("Config is not initialized")
    return _config


def set_services(container: ServiceContainer) -> None:
    global _services
    _services = container


def get_services() -> ServiceContainer:
    if _services is None:
        raise RuntimeError("Services are not initialized")
    return _services

