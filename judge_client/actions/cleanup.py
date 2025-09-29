from judge_client.actions import Action


class CleanupAction(Action):
    class Options(Action.Options):
        def __init__(self):
            super().__init__()

            self.NAMESPACE = self._env("JUDGE_NAMESPACE", required=True)

            self.TASK_PREFIX = self._env("JUDGE_TASK_PREFIX", "")

    options: Options  # type:ignore

    def run(self, *args, **kwargs) -> None:
        for task in list(
            self.judge_client.get_tasks(
                namespace=self.options.NAMESPACE, query=self.options.TASK_PREFIX
            )
        ):
            if not task.name.startswith(self.options.TASK_PREFIX):
                continue

            self.logger.info(f"Deleting task {task.name}")

            self.judge_client.delete_task(self.options.NAMESPACE, task.name)


__all__ = ["CleanupAction"]
