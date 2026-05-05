from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"


class TelegramConfig(BaseModel):
    token: str = ""
    chat_id: str = ""


class WordPressConfig(BaseModel):
    url: str = ""
    username: str = ""
    password: str = ""


class ClaudeConfig(BaseModel):
    api_key: str = ""
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 8192


class GitConfig(BaseModel):
    blog_repo_path: str = "../blog"


class HubSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    log_level: str = "INFO"
    json_logs: bool = False

    telegram: TelegramConfig = TelegramConfig()
    wordpress: WordPressConfig = WordPressConfig()
    claude: ClaudeConfig = ClaudeConfig()
    git: GitConfig = GitConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        secrets_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # 우선순위 (높음→낮음): 환경변수 > .env > config.local.yaml > config.yaml
        return (
            env_settings,
            dotenv_settings,
            _YamlSource(settings_cls, _CONFIG_DIR / "config.local.yaml"),
            _YamlSource(settings_cls, _CONFIG_DIR / "config.yaml"),
        )


class _YamlSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings], path: Path) -> None:
        super().__init__(settings_cls)
        self._data: dict[str, Any] = {}
        if path.exists():
            with path.open(encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._data


_settings: HubSettings | None = None


def get_settings() -> HubSettings:
    global _settings
    if _settings is None:
        _settings = HubSettings()
    return _settings


def reset_settings() -> None:
    """테스트에서 설정을 초기화할 때 사용."""
    global _settings
    _settings = None
