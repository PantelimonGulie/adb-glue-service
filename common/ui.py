from pathlib import Path

from fastapi.staticfiles import StaticFiles

static = StaticFiles(directory=Path(__file__).with_name("static"))
mock_templates_dir = Path(__file__).with_name("templates")
