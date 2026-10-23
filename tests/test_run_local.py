import re
from pathlib import Path

import yaml

from scripts import run_local

COMPOSE = yaml.safe_load((Path(__file__).parents[1] / "docker-compose.yml").read_text())


def outside_docker(key: str, value: str) -> str:
    if key == "DB_PATH":
        return str(run_local.LOCAL / Path(value).name)
    value = re.sub(r"\$\{\w+:-(.*)\}", r"\1", value)
    return re.sub(r"//(glue|shop|emag|warehouse|ollama):", "//127.0.0.1:", value)


def test_the_local_runner_gives_each_service_what_compose_gives_it():
    assert set(run_local.SERVICES) == set(COMPOSE["services"]) - {"ollama"}
    for name, (port, env) in run_local.SERVICES.items():
        service = COMPOSE["services"][name]

        assert service["command"].endswith(f"--port {port}")
        assert env == {
            key: outside_docker(key, value) for key, value in service["environment"].items()
        }
