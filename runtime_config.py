import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock


CONFIG_PATH = Path(os.getenv("RUNTIME_CONFIG_PATH", "runtime_config.json"))


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class RuntimeConfig:
    facility_name: str = os.getenv("DEFAULT_FACILITY_NAME", "HALIC SU SPORLARI MERKEZI")
    branch_name: str = os.getenv("DEFAULT_BRANCH_NAME", "FITNESS")
    interval_min_seconds: int = _env_int("CHECK_INTERVAL_MIN_SECONDS", 900)
    interval_max_seconds: int = _env_int("CHECK_INTERVAL_MAX_SECONDS", 1200)
    stop_after_found: bool = _env_bool("STOP_AFTER_FOUND", False)
    session_button_index: int = _env_int("SEANS_SECIM_BUTON_INDEX", 0)

    def normalized(self) -> "RuntimeConfig":
        self.interval_min_seconds = max(30, int(self.interval_min_seconds))
        self.interval_max_seconds = max(self.interval_min_seconds, int(self.interval_max_seconds))
        self.session_button_index = max(0, int(self.session_button_index))
        self.facility_name = self.facility_name.strip() or "HALIC SU SPORLARI MERKEZI"
        self.branch_name = self.branch_name.strip() or "FITNESS"
        return self


class ConfigStore:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self._lock = RLock()

    def load(self) -> RuntimeConfig:
        with self._lock:
            if not self.path.exists():
                config = RuntimeConfig().normalized()
                self.save(config)
                return config

            data = json.loads(self.path.read_text(encoding="utf-8"))
            return RuntimeConfig(**data).normalized()

    def save(self, config: RuntimeConfig) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(asdict(config.normalized()), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def update(self, **changes) -> RuntimeConfig:
        config = self.load()
        for key, value in changes.items():
            if not hasattr(config, key):
                raise ValueError(f"Unknown config key: {key}")
            setattr(config, key, value)
        self.save(config)
        return config
