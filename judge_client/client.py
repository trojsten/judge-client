import datetime
from collections.abc import Iterable
from sys import version as python_version
from typing import IO

import requests

from judge_client import __version__ as judge_client_version
from judge_client.exceptions import (
    JudgeConnectionError,
    NotFoundError,
    ProtocolCorruptedError,
    UnknownLanguageError,
)
from judge_client.util import JudgeClientIterator

from .types import Language, Namespace, Priority, Submit, Task, TaskLanguage, TaskShort
from .util import _convert


class JudgeClient:
    def __init__(self, judge_token: str, judge_url: str = "https://judge.ksp.sk"):
        """
        Initializes JudgeClient instance.

        :param judge_token: API Token for Judge
        :param judge_url: Judge URL
        """
        self.judge_token = judge_token
        self.judge_url = judge_url

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": f"trojsten-judge-client/{judge_client_version} (Python {python_version})",
                "X-API-Token": self.judge_token,
            }
        )

    #
    # Helpers
    #

    _known_exceptions = {
        "filename: Could not detect language.": UnknownLanguageError,
        "Not Found": NotFoundError,
    }

    def _handle_exception(self, url: str, response: requests.Response) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            detail: str = f"Failed to connect to judge system ({self.judge_url}{url})"
            try:
                details = response.json()
                if "detail" in details:
                    detail = details["detail"]
            except Exception:
                pass

            exception = self._known_exceptions.get(detail, JudgeConnectionError)

            raise exception(detail) from e

    def _get(self, url: str, *args, **kwargs) -> requests.Response:
        response = self.session.get(self.judge_url + url, *args, **kwargs)

        self._handle_exception(url, response)

        return response

    def _post(self, url: str, *args, **kwargs) -> requests.Response:
        response = self.session.post(self.judge_url + url, *args, **kwargs)

        self._handle_exception(url, response)

        return response

    def _delete(self, url: str, *args, **kwargs) -> requests.Response:
        response = self.session.delete(self.judge_url + url, *args, **kwargs)

        self._handle_exception(url, response)

        return response

    #
    # Misc
    #

    @property
    def embed_script_url(self) -> str:
        """
        Returns the URL of script for <judge-embed-protocol> custom element.

        :returns: URL of the embed script
        """
        return f"{self.judge_url}/static/js/protocol-embed.min.js"

    #
    # Submits
    #

    def submit(
        self,
        task: str,
        external_user_id: str,
        filename: str,
        program: str | bytes | bytearray | IO,
        language: str = "",
        ip: str | None = None,
        namespace: str | None = None,
    ) -> Submit:
        """
        Submits a file to the judge system.

        :param task: task slug
        :param external_user_id: string to identify the user for your reference
        :param filename: name of the file (used to auto detect the language)
        :param program: content of the file
        :param language: language ID or empty string to autodetect based on filename
        :param ip: IP address of the user for your reference and some reports
        :param namespace: namespace slug (needed in case of one token being usable in multiple namespaces)

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: Submit
        """

        response = self._post(
            "/api/submits/",
            files={
                "task": (None, task),
                "external_user_id": (None, external_user_id),
                "program": (filename, program),
                "language": (None, language),
                "ip": (None, ip),
                "namespace": (None, namespace),
            },
        )

        try:
            ret = Submit(**response.json())
            ret._judge_client = self

            return ret
        except Exception as e:
            raise ProtocolCorruptedError(
                "Failed to parse response from the judge system",
                response.text,
            ) from e

    def get_submit(self, public_id: str) -> Submit:
        """
        Gets a submit by its public ID.

        :param public_id: public ID of the submit

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: Submit
        """

        response = self._get(
            f"/api/submits/{public_id}/",
        )

        try:
            ret = Submit(**response.json())
            ret._judge_client = self

            return ret
        except Exception as e:
            raise ProtocolCorruptedError(
                "Failed to parse response from the judge system",
                response.text,
            ) from e

    def download_submit_program(self, public_id: str) -> bytes:
        """
        Downloads program from the given submit

        :param public_id:

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: Program as bytes
        """

        response = self._get(f"/api/submits/{public_id}/program/")

        return response.content

    def get_submits(
        self,
        namespace: str | None = None,
        task: str | None = None,
        external_user_id: str | None = None,
        offset: int = 0,
        batch_size: int = 25,
    ) -> Iterable[Submit]:
        """
        Get all submit matching specified criteria.

        :param namespace: only include submits in namespace with that name
        :param task: only include submits of task with that name
        :param external_user_id: only include submits with that external_user_id
        :param offset: offset of the first submit to return
        :param batch_size: number of submits to fetch at once

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: Iterable of Submits
        """

        def fetch_data(offset) -> tuple[int, list[Submit]]:
            response = self._get(
                "/api/submits/",
                params={
                    "namespace": namespace,
                    "task": task,
                    "external_user_id": external_user_id,
                    "limit": batch_size,
                    "offset": offset,
                },
            )

            data = response.json()
            return data["count"], _convert(Submit, data["items"])

        return JudgeClientIterator(offset, fetch_data)

    def rejudge_submit(self, public_id: str):
        """
        Rejudges a submit by its public ID.

        :param public_id: public ID of the submit

        :raises JudgeConnectionError: If the connection to the judge system fails.
        """

        self._post(
            f"/api/submits/{public_id}/rejudge/",
        )

    #
    # Languages
    #

    def get_languages(self) -> list[Language]:
        """
        Gets all languages supported by Judge.

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: list of Languages
        """

        response = self._get(
            "/api/languages/",
        )

        return _convert(Language, response.json())

    #
    # Namespaces
    #

    def get_namespaces(self) -> list[Namespace]:
        """
        Gets all namespaces accessible by the token.

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: list of namespaces
        """

        response = self._get(
            "/api/namespaces/",
        )

        return _convert(Namespace, response.json())

    #
    # Tasks
    #

    def get_tasks(
        self,
        query: str | None = None,
        namespace: str | None = None,
        offset: int = 0,
        batch_size: int = 25,
    ) -> Iterable[TaskShort]:
        """
        Gets all tasks accessible by the token matching specified criteria.

        :param query: only include tasks with that contains the query in the name
        :param namespace: only include tasks in namespace with that name
        :param offset: offset of the first task to return
        :param batch_size: number of tasks to fetch at once

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: Iterable of tasks
        """

        def fetch_data(offset) -> tuple[int, list[TaskShort]]:
            response = self._get(
                "/api/tasks/",
                params={
                    "query": query,
                    "namespace": namespace,
                    "limit": batch_size,
                    "offset": offset,
                },
            )

            data = response.json()
            return data["count"], _convert(TaskShort, data["items"])

        return JudgeClientIterator(offset, fetch_data)

    def get_task(self, namespace: str, task: str) -> Task:
        """
        Gets a task by its namespace and name.

        :param namespace:
        :param task:

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: Task
        """

        response = self._get(
            f"/api/tasks/{namespace}/{task}/",
        )

        ret = Task(**response.json())
        ret._judge_client = self

        return ret

    def update_task(self, task: Task):
        """
        Updates task options by its namespace and name.
        To update task languages or task data, use specialized functions

        :param task:

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: Task
        """

        response = self._post(
            f"/api/tasks/{task.namespace}/{task.name}/",
            json=task.dict(),
        )

        ret = Task(**response.json())
        ret._judge_client = self

        return ret

    def delete_task(self, namespace: str, task: str):
        """
        Permanently deletes a task by its namespace and name along with its data.

        :param namespace:
        :param task:

        :raises JudgeConnectionError: If the connection to the judge system fails.
        """

        self._delete(f"/api/tasks/{namespace}/{task}/")

    def create_task(self, task: Task):
        """
        Creates task.
        To upload data or change task languages, use specialized functions.

        :param task:

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: The created task
        """

        response = self._post(
            f"/api/tasks/{task.namespace}/",
            json=task.dict(),
        )

        ret = Task(**response.json())
        ret._judge_client = self

        return ret

    def rejudge_task(
        self,
        namespace: str,
        task: str,
        only_newer: datetime.date | None = None,
        priority: Priority | None = None,
    ):
        """
        Rejudges all finished submits for the task.

        :param namespace:
        :param task:
        :param only_newer: Rejudge only submits newer than this date (or all if None)
        :param priority: Rejudge with this priority (or default priority if None)

        :raises JudgeConnectionError: If the connection to the judge system fails.
        """

        data: dict = {}

        if only_newer is not None:
            data["only_newer"] = only_newer.isoformat()
        if priority is not None:
            data["priority"] = priority.value

        self._post(f"/api/tasks/{namespace}/{task}/rejudge/", json=data)

    #
    # Task data
    #

    def download_task_data(self, namespace: str, task: str) -> bytes:
        """
        Downloads task data.

        :param namespace:
        :param task:

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: ZIP of data as bytes
        """

        response = self._get(f"/api/tasks/{namespace}/{task}/data/")

        return response.content

    def upload_task_data(self, namespace: str, task: str, data: IO):
        """
        Uploads task data.

        :param namespace:
        :param task:
        :param data: TAR or ZIP of data as bytes

        :raises JudgeConnectionError: If the connection to the judge system fails.
        """

        self._post(
            f"/api/tasks/{namespace}/{task}/data/",
            files={"archive": (data.name, data)},
        )

    #
    # Task languages
    #

    def get_task_languages(self, namespace: str, task: str) -> list[TaskLanguage]:
        """
        Gets all task languages for the task.

        :param namespace:
        :param task:

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: list of task languages
        """

        response = self._get(
            f"/api/tasks/{namespace}/{task}/languages/",
        )

        return _convert(TaskLanguage, response.json())

    def add_task_language(self, namespace: str, task: str, task_language: TaskLanguage):
        """
        Creates task language.

        :param namespace:
        :param task:
        :param task_language: task language to create

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: TaskLanguage
        """

        response = self._post(
            f"/api/tasks/{namespace}/{task}/languages/",
            json=task_language.dict(),
        )

        return TaskLanguage(**response.json())

    def update_task_language(
        self, namespace: str, task: str, task_language: TaskLanguage
    ):
        """
        Updates task language.

        :param namespace:
        :param task:
        :param task_language: task language to update

        :raises JudgeConnectionError: If the connection to the judge system fails.

        :returns: TaskLanguage
        """

        response = self._post(
            f"/api/tasks/{namespace}/{task}/languages/{task_language.language_id}/",
            json=task_language.dict(),
        )

        return TaskLanguage(**response.json())

    def delete_task_language(self, namespace: str, task: str, language_id: str):
        """
        Deletes task language.

        :param namespace:
        :param task:
        :param language_id: language ID

        :raises JudgeConnectionError: If the connection to the judge system fails.
        """

        self._delete(
            f"/api/tasks/{namespace}/{task}/languages/{language_id}/",
        )

    def set_task_languages(
        self, namespace: str, task: str, task_languages: list[TaskLanguage]
    ) -> None:
        """
        Sets task languages - creates missing languages, updates changed and deletes
        all other.

        This is shortcut to calling `get_task_languages`, `add_task_language`,
        `update_task_language` and `delete_task_language`.

        :param namespace:
        :param task:
        :param task_languages: list of task languages to set

        :raises JudgeConnectionError: If the connection to the judge system fails.
        """

        current_languages = self.get_task_languages(namespace, task)

        current_language_ids = {language.language_id for language in current_languages}

        for lang in task_languages:
            if lang.language_id not in current_language_ids:
                self.add_task_language(namespace, task, lang)
            else:
                self.update_task_language(namespace, task, lang)

        new_language_ids = {language.language_id for language in task_languages}

        for lang in current_languages:
            if lang.language_id not in new_language_ids:
                self.delete_task_language(namespace, task, lang.language_id)
