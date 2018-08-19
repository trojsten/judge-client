trojsten_judge_client
=====================

.. image:: https://img.shields.io/pypi/v/trojsten_judge_client.svg
    :target: https://pypi.python.org/pypi/trojsten_judge_client
    :alt: Latest PyPI version

Client for Trojsten Judge System.

Usage
-----

.. code:: python

    from judge_client.client import JudgeClient

    judge_cient = JudgeClient(tester_id, tester_url, tester_port)
    judge_client.submit(submit_id, user_id, task_id, submission_content, language)

Installation
------------
`pip install trojsten-judge-client`

Compatibility
-------------
- Python 2.7
- Python 3.6
- Python 3.7

Licence
-------
MIT

Authors
-------
`Michal Hozza <mhozza@gmail.com>`.
