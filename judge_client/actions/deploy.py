import json
import shutil
import subprocess
import tarfile
import tempfile
from copy import deepcopy
from pathlib import Path
from shutil import copytree, rmtree

from loguru import logger

from judge_client.actions import TasksAction
from judge_client.exceptions import NotFoundError
from judge_client.types import Task, TaskLanguage


class DeployAction(TasksAction):
    class Options(TasksAction.Options):
        def __init__(self):
            super().__init__()

            self.NAMESPACE = self._env("JUDGE_NAMESPACE", required=True)
            self.TESTCASES_DIR = self._env("TESTCASES_DIR")
            self.REJUDGE = self._env("JUDGE_REJUDGE", "false").lower() == "true"

            self.TASK_PREFIX = self._env("JUDGE_TASK_PREFIX", "")

            self.SUBMIT_SOLS = self._env("JUDGE_SUBMIT_SOLS", "false").lower() == "true"

    options: Options  # type:ignore

    def get_task_name(self, task: Path) -> str:
        # KSP-school
        # return str(task.relative_to(self.options.TASK_DIR)).split("/")[1]
        return self.options.TASK_PREFIX + str(
            task.relative_to(self.options.TASK_DIR)
        ).replace("/", "-")

    def get_task_problem_statement_path(self, task: Path) -> Path | None:
        if (path := task.parent / "zadanie.md").exists():
            return path
        elif (path := task.parent / "zadania" / f"{task.name}.md").exists():
            return path

    def get_config(self, task: Path) -> dict | None:
        current_dir = task

        while current_dir != Path(self.options.TASK_DIR).parent:
            task_file = current_dir / "task.json"

            if task_file.exists():
                with open(task_file, "r") as f:
                    return json.load(f)

            current_dir = current_dir.parent

        return None

    _input_tool_updates_checked = False

    def build_task(self, task: Path) -> bool:
        if (task / "idf").exists():
            logger.info("Building task")
            logger.info(" - Pulling sample data")

            extra_args = []

            if shutil.which("input-sample") is None:
                extra_args = ["uv", "run"]

            problem_statement_path = self.get_task_problem_statement_path(task)

            if problem_statement_path is None:
                logger.warning(
                    "No problem statement found in standard paths. Samples will NOT be extracted."
                )

            else:
                subprocess.run(
                    extra_args
                    + ["input-sample", str(problem_statement_path.absolute())],
                    cwd=task,
                    check=True,
                )

            logger.info(" - Generating inputs")
            if not self._input_tool_updates_checked:
                logger.info("Checking for input tool updates")
                subprocess.run(
                    extra_args + ["itool", "checkupdates"],
                    cwd=task,
                    check=True,
                )
                self._input_tool_updates_checked = True

            subprocess.run(
                extra_args + ["input-generator", "--no-update-check", "idf"],
                cwd=task,
                check=True,
            )
            logger.info(" - Running solutions to generate outputs")
            cmdline = extra_args + [
                "input-tester",
                "--pythoncmd",
                "pypy3",
                "-t",
                "5",
            ]

            if (task / "checker.py").exists():
                cmdline.extend(["-d", "checker.py"])

            for sol in (task / "sols").iterdir():
                if sol.is_file() and sol.match("sol.*"):
                    cmdline.append(str(sol.relative_to(task)))

            subprocess.run(
                cmdline,
                cwd=task,
                check=True,
            )

            if (task / "prog").exists():
                logger.info("Deleting 'prog' dir")
                rmtree(task / "prog")

            return True

        elif (
            self.options.TESTCASES_DIR is not None
            and (
                src := self.options.TESTCASES_DIR
                / task.relative_to(self.options.TASK_DIR)
                / "test"
            ).exists()
        ):
            logger.info(
                f"Not building task (no generator found), using data from '{self.options.TESTCASES_DIR}'"
            )
            copytree(
                src,
                task / "test",
            )

            return True

        elif (task / "test").exists():
            logger.warning("Using data from 'test' folder")
            return True

        return False

    def upload_task_data(self, task: Path, task_name: str) -> None:
        # TODO: maybe use zstd when Python 3.14 is released and ready for use + supported by judge-ui
        with tempfile.NamedTemporaryFile(suffix=".tar.gz") as tmp:
            with tarfile.open(tmp.name, "w:gz", tmp) as tf:
                tf.add(task, "")

            tmp.seek(0)

            logger.info("Uploading data")
            self.judge_client.upload_task_data(
                self.options.NAMESPACE,
                task_name,
                tmp,
            )

    def process_task(self, task: Path) -> None:
        task_name = self.get_task_name(task)
        logger.info(f"Processing task {task_name}")

        task_config = self.get_config(task)

        if task_config is None:
            logger.error(f"Failed to load task config for {task_name}")
            exit(1)

        if not self.build_task(task):
            logger.error(f"Failed to build task {task_name}")
            exit(1)

        # Get old task
        try:
            old_task = self.judge_client.get_task(self.options.NAMESPACE, task_name)
        except NotFoundError:
            old_task = None
            pass

        if not old_task:
            logger.info("Creating task")

            new_task = deepcopy(task_config)

            if "default_limit_language" in new_task:
                del new_task["default_limit_language"]
            if "languages" in new_task:
                del new_task["languages"]

            old_task = self.judge_client.create_task(
                Task(
                    name=task_name,
                    namespace=self.options.NAMESPACE,
                    **new_task,
                )
            )

        task_languages: list[TaskLanguage] = []
        find_default_language = False

        for _, language in enumerate(task_config["languages"]):
            key = "relative_measurement_solution"
            if key in language and not (task / language[key]).exists():
                logger.warning(
                    f"Ignoring language {language['language_id']} - it has relative measurement but solution '{language[key]}' was not found"
                )

                if task_config["default_limit_language"] == language["language_id"]:
                    logger.warning(
                        f"That was the 'default_limit_language'. Please create '{language[key]}' or change 'default_limit_language'."
                    )
                    find_default_language = True
            else:
                task_languages.append(TaskLanguage(**language))

        if len(task_languages) == 0:
            logger.error(
                f"No valid languages found in task {task_name}. Please add at least one language."
            )
            exit(1)

        if find_default_language:
            task_config["default_limit_language"] = task_languages[0].language_id
            logger.warning(
                f"Changed default_limit_language to {task_config['default_limit_language']}"
            )

        self.judge_client.set_task_languages(
            self.options.NAMESPACE,
            task_name,
            task_languages,
        )

        # Update task settings
        logger.info("Updating task")

        updated_task = deepcopy(task_config)

        del updated_task["languages"]

        self.judge_client.update_task(
            Task(namespace=self.options.NAMESPACE, name=task_name, **updated_task)
        )

        # Upload task data
        logger.info("Compressing task data")
        self.upload_task_data(task, task_name)

        if self.options.REJUDGE:
            logger.info("Rejudging task")
            self.judge_client.rejudge_task(self.options.NAMESPACE, task_name)

        if self.options.SUBMIT_SOLS:
            logger.info("Uploading submits")
            submit_dir = task / "sols"
            if not submit_dir.exists():
                logger.warning("No solutions to submit")
            else:
                for sol in submit_dir.iterdir():
                    if sol.is_file() and sol.match("sol.*"):
                        logger.info(f"Submitting solution {sol.name}")
                        self.judge_client.submit(
                            namespace=self.options.NAMESPACE,
                            task=task_name,
                            external_user_id=f"{self.options.TASK_PREFIX}-github-action",
                            filename=sol.name,
                            program=sol.read_bytes(),
                        )
