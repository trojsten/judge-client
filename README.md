# judge-client

Client for Trojsten Judge System API.

## Instalation

### uv
```sh
uv add "git+https://github.com/trojsten/judge-client"
```

## Usage
```python
from judge_client.client import JudgeClient

judge_client = JudgeClient(token)
submit = judge_client.submit(task, external_user_id, filename, program)
```
