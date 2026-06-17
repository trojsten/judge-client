import secrets
from collections import defaultdict

from judge_client.actions import Action


class CommentAction(Action):
    class Options(Action.Options):
        def __init__(self):
            super().__init__()

            self.NAMESPACE = self._env("JUDGE_NAMESPACE", required=True)
            self.COMMENT_OUTPUT = self._env(
                "JUDGE_COMMENT_OUTPUT", "/tmp/judge-comment-out.txt"
            )

            self.TASK_PREFIX = self._env("JUDGE_TASK_PREFIX", "")

    options: Options

    def run(self, *args, **kwargs) -> None:
        with open(self.options.COMMENT_OUTPUT, "w") as f:
            tasks = list(
                self.judge_client.get_tasks(
                    namespace=self.options.NAMESPACE, query=self.options.TASK_PREFIX
                )
            )

            if len(tasks) == 0:
                f.write("No modified tasks found\n")
                exit(0)

            f.write(
                "🚀 Tasks deployed\n\nFollowing tasks were successfully deployed to the staging environment:\n"
            )

            for task in tasks:
                if not task.name.startswith(self.options.TASK_PREFIX):
                    continue

                self.logger.info(f"Processing task {task.name}")

                task_detail = self.judge_client.get_task(
                    self.options.NAMESPACE, task.name
                )
                task_detail.public_submit_key = secrets.token_hex(16)
                self.judge_client.update_task(task_detail)

                f.write(
                    f"- [{task.name.removeprefix(self.options.TASK_PREFIX)}]({self.options.API_ORIGIN}/public/submit/{task_detail.public_submit_key}/) ([admin]({self.options.API_ORIGIN}/tasks/{task_detail.id}/))\n"
                )

                grouped_submits = defaultdict(list)
                for submit in self.judge_client.get_submits(
                    self.options.NAMESPACE, task.name
                ):
                    filename = ":".join(submit.external_user_id.split(":")[:-1])
                    grouped_submits[filename].append(submit)

                for filename, submits in grouped_submits.items():
                    f.write(f"  - `{filename}`:\n")
                    for submit in sorted(submits, key=lambda x: x.created_at):
                        f.write(
                            f"    - {submit.created_at.strftime('%Y-%m-%d %H:%M')} ({submit.external_user_id.split(':')[-1]}): [{submit.public_id}]({submit.public_protocol_url})\n"
                        )

            f.write("\n🔍 You can now test your changes")


__all__ = ["CommentAction"]
