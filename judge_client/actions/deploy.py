import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from shutil import copytree, rmtree

from deepmerge import always_merger

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

            self.FOLDER_SIZE_LIMIT = int(
                self._env("JUDGE_FOLDER_SIZE_LIMIT", str(50 * 1024 * 1024))
            )  # 50 MiB

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

    def get_config(self, task: Path, name: str, namespace: str) -> Task | None:
        data: dict | None = None

        current_dir = task

        while current_dir != Path(self.options.TASK_DIR).parent:
            task_file = current_dir / "task.json"

            if task_file.exists():
                with open(task_file, "r") as f:
                    d = json.load(f)

                    merge = d.get("__merge__", False)

                    if "__merge__" in d:
                        del d["__merge__"]

                    if data is None:
                        data = d
                    else:
                        data = always_merger.merge(d, data)

                    if not merge:
                        break

            current_dir = current_dir.parent

        if data is None:
            return None

        data["name"] = name
        data["namespace"] = namespace

        return Task(**data)

    _input_tool_updates_checked = False

    def build_task(self, task: Path, config: Task) -> bool:
        for prog in ("checker.cpp", "check.cpp", "checker.cc", "check.cc"):
            if (task / prog).exists():
                source = (task / prog).absolute()
                dest = (task / prog).with_suffix(".bin").absolute()

                self.logger.info(f"Compiling {source} to {dest}")

                subprocess.run(
                    [
                        "/usr/bin/g++",
                        "-static",
                        "-std=c++2b",
                        "-fmax-errors=100",
                        "-O2",
                        "-Wall",
                        "-Wextra",
                        "-o",
                        str(dest),
                        str(source),
                    ],
                    cwd=task,
                    check=True,
                )

        if (task / "idf").exists():
            self.logger.info("Building task")
            self.logger.info(" - Pulling sample data")

            extra_args = []

            if shutil.which("input-sample") is None:
                extra_args = ["uv", "run"]

            problem_statement_path = self.get_task_problem_statement_path(task)

            if problem_statement_path is None:
                self.logger.warning(
                    "No problem statement found in standard paths. Samples will NOT be extracted."
                )

            else:
                subprocess.run(
                    extra_args
                    + ["input-sample", str(problem_statement_path.absolute())],
                    cwd=task,
                    check=True,
                )

            self.logger.info(" - Generating inputs")
            if not self._input_tool_updates_checked:
                self.logger.info("Checking for input tool updates")
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

            if config.executor == "judge.default.executor.Interactive":
                self.logger.info(
                    " - Not running solutions to generate outputs as task is interactive"
                )

            else:
                self.logger.info(" - Running solutions to generate outputs")
                cmdline = extra_args + [
                    "input-tester",
                    "--pythoncmd",
                    "pypy3",
                    "-t",
                    "5",
                ]

                # TODO: maybe use checker_command from task config instead?
                for checker in (
                    "checker.py",
                    "check.py",
                    "checker.cpp",
                    "check.cpp",
                    "checker.cc",
                    "check.cc",
                ):
                    if (task / checker).exists():
                        cmdline.extend(["-d", checker])
                        break

                for sol in (task / "sols").iterdir():
                    if sol.is_file() and sol.match("sol.*"):
                        cmdline.append(str(sol.relative_to(task)))

                subprocess.run(
                    cmdline,
                    cwd=task,
                    check=True,
                )

            if (task / "prog").exists():
                self.logger.info("Deleting 'prog' dir")
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
            self.logger.info(
                f"Not building task (no generator found), using data from '{self.options.TESTCASES_DIR}'"
            )
            copytree(
                src,
                task / "test",
            )

            return True

        elif (task / "test").exists():
            self.logger.warning("Using data from 'test' folder")
            return True

        return False

    def get_folder_size(self, path: Path) -> int:
        return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())

    def upload_task_data(self, task: Path, task_name: str) -> None:
        if self.get_folder_size(task) > self.options.FOLDER_SIZE_LIMIT:
            self.logger.error(
                f"Task folder size exceeds limit of {self.options.FOLDER_SIZE_LIMIT / (1024 * 1024)} MiB, not uploading it automatically"
            )
            self.logger.warning(
                f"Consider decreasing size of task data or uploading it manually to {self.options.API_ORIGIN}"
            )
            return

        # TODO: maybe use zstd when Python 3.14 is released and ready for use + supported by judge-ui
        with tempfile.NamedTemporaryFile(suffix=".tar.gz") as tmp:
            with tarfile.open(tmp.name, "w:gz", tmp) as tf:
                tf.add(task, "")

            tmp.seek(0)

            self.logger.info("Uploading data")
            self.judge_client.upload_task_data(
                self.options.NAMESPACE,
                task_name,
                tmp,
            )

    def process_task(self, task: Path) -> None:
        task_name = self.get_task_name(task)
        self.logger.info(f"Processing task {task_name}")

        task_config = self.get_config(task, task_name, self.options.NAMESPACE)

        if task_config is None:
            self.logger.error(f"Failed to load task config for {task_name}")
            exit(1)

        if not self.build_task(task, task_config):
            self.logger.error(f"Failed to build task {task_name}")
            exit(1)

        # Get old task
        try:
            old_task = self.judge_client.get_task(self.options.NAMESPACE, task_name)
        except NotFoundError:
            old_task = None
            pass

        if not old_task:
            self.logger.info("Creating task")

            old_task = self.judge_client.create_task(task_config)

        task_languages: list[TaskLanguage] = []
        find_default_language = False

        for _, language in enumerate(task_config.languages):
            sol = language.relative_measurement_solution
            if sol is not None and not (task / sol).exists():
                self.logger.warning(
                    f"Ignoring language {language.language_id} - it has relative measurement but solution '{sol}' was not found"
                )

                if task_config.default_limit_language == language.language_id:
                    self.logger.warning(
                        f"That was the 'default_limit_language'. Please create '{sol}' or change 'default_limit_language'."
                    )
                    find_default_language = True
            else:
                task_languages.append(language)

        if len(task_languages) == 0:
            self.logger.error(
                f"No valid languages found in task {task_name}. Please add at least one language."
            )
            exit(1)

        if find_default_language:
            task_config.default_limit_language = task_languages[0].language_id
            self.logger.warning(
                f"Changed default_limit_language to {task_config.default_limit_language}"
            )

        self.judge_client.set_task_languages(
            self.options.NAMESPACE,
            task_name,
            task_languages,
        )

        # Update task settings
        self.logger.info("Updating task")

        self.judge_client.update_task(task_config)

        # Upload task data
        self.logger.info("Compressing task data")
        self.upload_task_data(task, task_name)

        if self.options.REJUDGE:
            self.logger.info("Rejudging task")
            self.judge_client.rejudge_task(self.options.NAMESPACE, task_name)

        if self.options.SUBMIT_SOLS:
            self.logger.info("Uploading submits")
            submit_dir = task / "sols"
            if not submit_dir.exists():
                self.logger.warning("No solutions to submit")
            else:
                for sol in submit_dir.iterdir():
                    if sol.is_file() and sol.match("sol.*"):
                        self.logger.info(f"Submitting solution {sol.name}")
                        self.judge_client.submit(
                            namespace=self.options.NAMESPACE,
                            task=task_name,
                            external_user_id=f"{self.options.TASK_PREFIX}-github-action",
                            filename=sol.name,
                            program=sol.read_bytes(),
                        )


__all__ = ["DeployAction"]
