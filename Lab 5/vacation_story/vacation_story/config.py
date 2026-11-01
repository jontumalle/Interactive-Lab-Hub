"""All relative configuration paths are relative to the project folder."""
import os
from pathlib import Path
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path | None = None) -> dict:
    selected = path or Path(os.environ.get("VACATION_STORY_CONFIG", PROJECT_ROOT / "config.toml"))
    with selected.open("rb") as source:
        config = tomllib.load(source)
    for section, field in (("storage", "runtime_dir"), ("generation", "prompts_dir"), ("narration", "voice_path")):
        config[section][field] = str((PROJECT_ROOT / config[section][field]).resolve())
    config['narration']['executable'] = str((PROJECT_ROOT / config['narration']['executable']).resolve())
    return config
