from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, PrivateAttr

if TYPE_CHECKING:
    from .client import JudgeClient


class SubmitStatus(Enum):
    QUEUED = 0
    """
    Submit was queued, more info may be available in testing_status
    """
    FINISHED = 1
    """
    Submit was successfully tested
    """
    FAILED = 2
    """
    Submit failed to be tested and will be attempted again
    """


class TestingStatus(Enum):
    WAITING = "waiting"
    """
    Waiting for testing in queue
    """

    PULLING_IMAGE = "pulling_image"
    """
    Pulling docker image
    """

    MEASURING_TIMELIMIT = "measuring_timelimit"
    """
    Measuring relative time limit against solution
    """

    TESTING = "testing"
    """
    Testing
    """

    DONE = "done"
    """
    Done
    """


class Verdict(Enum):
    OK = "OK"
    """
    Everything executed successfully
    """

    WA = "WA"
    """
    Wrong Answer
    """

    TLE = "TLE"
    """
    Time Limit Exceeded
    """
    EXC = "EXC"
    """
    Exception (non-zero exit code)
    """

    PRV = "PRV"
    """
    Protocol Violation

    Used mainly in interactiver to indicate incorrect format of output
    """

    IGN = "IGN"
    """
    Ignored.

    Test was not run
    """

    MEM = "MEM"
    """
    Memory Limit Exceeded

    Currently not used anywhere
    """

    CEX = "CEX"
    """
    Compilation Exception
    """

    SEX = "SEX"
    """
    Server Exception (error on Judge side)
    """

    POK = "POK"
    """
    Partially OK
    """

    @classmethod
    def is_ok(cls, verdict: "Verdict"):
        """
        Returns True if Verdict is OK or POK
        """
        return verdict in (Verdict.OK, Verdict.POK)


class Priority(Enum):
    LOW = 1
    """
    Low priority
    """

    NORMAL = 2
    """
    Normal priority
    """

    HIGH = 3
    """
    High priority
    """


class Stats(BaseModel):
    """
    Class containing stats of running process
    """

    max_rss: int
    """
    Maximum RSS memory usage in kilobytes
    """
    cpu_time: int
    """
    CPU time in milliseconds
    """
    exit_code: int
    """
    Exit code of the process
    """
    real_time: int
    """
    Real time in milliseconds
    """
    timeouted: bool
    """
    True if the process was killed because it timeouted
    """


class TestResult(BaseModel):
    log: str
    """
    Log from test
    """

    name: str
    """
    Full name of test (eg 1.a)
    """
    batch: str
    """
    Batch of test (eg 1)
    """

    verdict: Verdict
    """
    Verdict of test
    """
    score: float
    """
    Score of test as percentage (0-1)
    """

    stats: Stats | None
    """
    Stats of process run in test
    """

    extra_data: dict[Any, Any] = Field(default_factory=dict)
    """
    Any extra data passed by Judge extensions
    """


class Limits(BaseModel):
    """
    Limits for a program
    """

    cpu_limit_ms: int
    """
    CPU time limit in milliseconds
    """

    wall_limit_ms: int
    """
    Wall time limit in milliseconds
    """

    memory_limit_kb: int | None
    """
    Memory limit in kilobytes
    """

    file_access: dict[str, bool]
    """
    File access permissions

    Key is path to file, value is boolean, True if file is allowed to be writeable,
    False otherwise
    """

    file_size: int | None
    """
    Maximum file size in kilobytes

    None for unlimited.
    """

    stack_size: int
    """
    Maximum stack size in kilobytes

    -1 for unlimited.
    """

    thread_limit: int | None
    """
    Maximum number of threads

    None for unlimited.
    """


class Protocol(BaseModel):
    tests: list[TestResult] | None = None
    log: str | None = None

    final_verdict: Verdict | None = None
    """
    Final verdict of submit
    """
    final_score: float | None = None
    """
    Score as percentage (0-1)
    """

    language: str | None = None
    """
    Language ID for submit
    """

    compile_stats: Stats | None = None
    """
    Stats from compilation (if it ran)
    """

    compile_limits: Limits | None = None
    """
    Limits used for compilation
    """
    runtime_limits: Limits | None = None
    """
    Limits used for runtime
    """


class Submit(BaseModel):
    """
    Class representing Submit
    """

    public_id: str
    """
    Submit ID
    """
    protocol_key: str
    """
    ID for use in public protocol
    """
    external_user_id: str
    """
    External user ID for your system
    """
    status: SubmitStatus
    """
    Status of submit
    """
    testing_status: TestingStatus | str
    """
    Status of testing (usually from "waiting", "pulling_image", "measuring_timelimit", "testing", "done")
    """
    task: str
    """
    Task name
    """
    namespace: str
    """
    Namespace name
    """
    language: str
    """
    Language as string returned from testing (eg Python 3.13.2)
    """
    protocol: Protocol | None = None
    """
    Protocol (may be empty)
    """
    worker: str
    """
    String identifying the worker that tested the submit
    """
    last_queued_at: datetime
    """
    Time of last enqueueing
    """
    created_at: datetime
    """
    Time of creation
    """

    _judge_client: JudgeClient | None = PrivateAttr()

    @property
    def public_protocol_url(self):
        if self._judge_client is None:
            raise ValueError("JudgeClient is not set. Did you forget to set it?")

        return f"{self._judge_client.judge_url}/public/protocol/{self.protocol_key}/"

    @property
    def public_embed_protocol_url(self):
        if self._judge_client is None:
            raise ValueError("JudgeClient is not set. Did you forget to set it?")

        return (
            f"{self._judge_client.judge_url}/public/protocol/{self.protocol_key}/embed/"
        )

    def rejudge(self):
        """
        Rejudge the submit

        Shortcut to judge_client.rejudge_submit(submit.public_id)
        """

        if self._judge_client is None:
            raise ValueError("JudgeClient is not set. Did you forget to set it?")

        return self._judge_client.rejudge_submit(self.public_id)


class Language(BaseModel):
    """
    Class representing supported Judge languages
    """

    id: str
    """
    Language ID (eg cpp)
    """

    name: str
    """
    Human readable language name (eg C++)
    """

    extensions: list[str]
    """
    List of file extensions for this language (eg .cpp, .cc)
    """

    image: str
    """
    Custom docker image for this language or empty string for default one
    """

    class_path: str
    """
    Class path to language (eg judge.languages.Cpp)
    """

    is_special: bool
    """
    True if language is special (eg Make or Custom)
    """


class Namespace(BaseModel):
    """
    Class representing a Namespace
    """

    id: int
    """
    ID of namespace
    """

    name: str
    """
    Name of the namespace
    """

    priority: Priority | None = None
    """
    Default priority of submits in this namespace (or default if not set)
    """


class TaskShort(BaseModel):
    name: str
    """
    Task name
    """
    namespace: str
    """
    Namespace name
    """


class TaskLanguage(BaseModel):
    """
    Class representing settings for combination of task and language
    """

    id: int = -1
    """
    Task language ID
    """
    language: str = ""
    """
    Human readable language name 
    """
    language_id: str = ""
    """
    Language identifier
    """

    image: str = ""
    """
    Image to use for testing (empty for default image)
    """

    cpu_limit: int | None = None
    """
    Absolute CPU time limit or None if using relative limits 
    """
    wall_limit: int | None = None
    """
    Absolute total time limit or None if using relative limits 
    """
    relative_time_limit: float | None = None
    """
    Relative time limit multiplier (eg 2 for 2 times more time than time of solution) or None if using absolute limits 
    """
    relative_measurement_solution: str = ""
    """
    Path to solution to use to measure relative time limit or empty string if using absolute limits
    """
    relative_measurement_task_language: int | None = None
    """
    ID of task language of relative measurement solution or None for either current task language or if using absolute limits
    """
    memory_limit: int | None = None
    """
    Memory limit of language (in kilobytes)
    """

    config_overrides: dict = Field(default_factory=dict)
    """
    Any configuration options that will override task's config
    """


class Task(TaskShort, BaseModel):
    id: int = -1
    """
    Task ID
    """

    public_submit_key: str | None = None
    """
    Public submit key for task or None if task is not publicly submitable
    """

    version: str = ""
    """
    Task version used for internal versioning
    """

    default_limit_language: str | None = None
    """
    ID of language used for default limits or None if only specified languages can be used
    """

    config: dict = Field(default_factory=dict)
    """
    Task configuration
    """

    preparer: str = ""
    """
    Preparer class-path
    """
    loader: str = ""
    """
    Loader class-path
    """
    decider: str = ""
    """
    Decider class-path
    """
    executor: str = ""
    """
    Executor class-path
    """
    grader: str = ""
    """
    Grader class-path
    """
    mixer: str = ""
    """
    Mixer class-path
    """

    image: str = ""
    """
    Image to use for testing (or empty string for default image)
    """

    file_readonly_access: list[str] | None = None
    """
    List of paths that are read-only during testing
    """
    file_readwrite_access: list[str] | None = None
    """
    List of paths that are read-write during testing
    """
    file_size: int | None = None
    """
    Maximum file size in kilobytes
    """
    stack_size: int | None = None
    """
    Maximum stack size in kilobytes
    """
    thread_limit: int | None = None
    """
    Maximum number of threads
    """
    network: bool = False
    """
    True if internet access is allowed
    """

    languages: list[TaskLanguage] = Field(default_factory=list)
    """
    List of languages available for this task
    """

    _judge_client: JudgeClient | None = PrivateAttr()

    @property
    def public_submit_url(self) -> str | None:
        if self._judge_client is None:
            raise ValueError("JudgeClient is not set. Did you forget to set it?")

        if self.public_submit_key is None:
            return None

        return f"{self._judge_client.judge_url}/public/submit/{self.public_submit_key}/"
