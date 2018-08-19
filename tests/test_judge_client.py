import time

import socket
import threading
from contextlib import closing

from unittest import TestCase

from judge_client.client import JudgeClient


class SubmitHelpersTests(TestCase):
    TESTER_URL = '127.0.0.1'
    TESTER_PORT = 7777
    TESTER_ID = 'TEST'

    def setUp(self):
        def run_fake_server(test):
            with closing(socket.socket()) as server_sock:
                server_sock.bind((self.TESTER_URL, self.TESTER_PORT))
                server_sock.listen(0)
                conn, addr = server_sock.accept()
                raw = conn.recv(2048)
                data = conn.recv(2048)
                test.received = raw + data
                time.sleep(100.0 / 1000.0)

        self.judge_client = JudgeClient(self.TESTER_ID, self.TESTER_URL, self.TESTER_PORT)
        self.server_thread = threading.Thread(target=run_fake_server, args=(self,))
        self.server_thread.start()
        time.sleep(50.0 / 1000.0)  # 50ms should be enough for the server to bind

    def test_submit(self):
        self.judge_client.submit('test_id', 'test_user', 'test_task', 'test_submission', 'py')
        self.server_thread.join()

        request_parts = self.received.split(b'\n')
        # Header
        self.assertEqual(request_parts[0], b'submit1.3')
        self.assertEqual(request_parts[1], b'TEST')
        self.assertEqual(request_parts[2], b'test_id')
        self.assertEqual(request_parts[3], b'test_user')
        self.assertEqual(request_parts[4], b'test_task')
        self.assertEqual(request_parts[5], b'py')
        self.assertEqual(request_parts[6], b'0')
        self.assertEqual(request_parts[7], b'magic_footer')
        # Submission
        self.assertEqual(request_parts[8], b'test_submission')

    def test_submit_with_priority(self):
        self.judge_client.submit('test_id', 'test_user', 'test_task', 'test_submission', 'py', 1)
        self.server_thread.join()

        request_parts = self.received.split(b'\n')
        # Header
        self.assertEqual(request_parts[0], b'submit1.3')
        self.assertEqual(request_parts[1], b'TEST')
        self.assertEqual(request_parts[2], b'test_id')
        self.assertEqual(request_parts[3], b'test_user')
        self.assertEqual(request_parts[4], b'test_task')
        self.assertEqual(request_parts[5], b'py')
        self.assertEqual(request_parts[6], b'1')
        self.assertEqual(request_parts[7], b'magic_footer')
        # Submission
        self.assertEqual(request_parts[8], b'test_submission')
