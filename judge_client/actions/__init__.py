import os
from glob import glob
from pathlib import Path
from typing import Any

from loguru import logger

from judge_client.client import JudgeClient


class Action:
    """
    Base Action class to be used as template for other actions for deployment
    through GitHub Actions.
    """

    class Options:
        """
        Options class that should handle loading all the options from the environment
        variables
        ."""

        logger = logger

        def _env(self, name: str, default: Any = None, required: bool = False) -> str:
            val = os.environ.get(name, default)
            if val is None and required:
                self.logger.error(f"Missing environment variable: {name}")
                exit(1)
            return val

        def __init__(self):
            self.TOKEN = self._env("JUDGE_TOKEN", required=True)
            self.API_ORIGIN = self._env("JUDGE_API_ORIGIN", "https://judge.ksp.sk")

    options: Options
    logger = logger

    def __init__(self):
        self.options = self.Options()

        self.judge_client = JudgeClient(self.options.TOKEN, self.options.API_ORIGIN)

    def run(self, *args, **kwargs) -> None:
        raise NotImplementedError


class TasksAction(Action):
    class Options(Action.Options):
        def __init__(self):
            super().__init__()

            self.TASK_DIR = Path(self._env("TASK_DIR", ".")).absolute()

            self.TRACK_CHANGED_FILES = (
                self._env("JUDGE_TRACK_CHANGED_FILES", "false").lower() == "true"
            )

            if self.TRACK_CHANGED_FILES:
                self.CHANGED_FILES = [
                    x.removeprefix("problems/")
                    for x in self._env("JUDGE_CHANGED_FILES", "").split(" ")
                ]

    options: Options  # type: ignore

    def get_tasks(self) -> list[Path]:
        return [
            self.options.TASK_DIR / task
            for task in glob("**/task", root_dir=self.options.TASK_DIR, recursive=True)
        ]

    def should_process_task(self, task: Path) -> bool:
        if self.options.TRACK_CHANGED_FILES and not any(
            [(str(task) + os.path.sep).startswith(str(x)) for x in self.changed_paths]
        ):
            return False

        return True

    def process_task(self, task: Path) -> None:
        raise NotImplementedError

    def run(self, *args, **kwargs):
        self.changed_paths = set[Path]()

        if self.options.TRACK_CHANGED_FILES:
            self.logger.info("Changed files:")

            for file in self.options.CHANGED_FILES:
                self.logger.info(f" - {file}")

                path = Path("/".join(file.split("/")[:2]))
                if path.is_file():
                    path = path.parent

                self.changed_paths.add(path)

            self.logger.info("Extracted changed paths:")
            for path in self.changed_paths:
                self.logger.info(f" - {path}")

        for task in self.get_tasks():
            if not self.should_process_task(task):
                self.logger.info(f"Skipping task {task}")
                continue

            try:
                self.process_task(task)
            except Exception:
                self.logger.exception(f"Failed to process task {task}")
                exit(1)


__all__ = ["Action", "TasksAction"]
