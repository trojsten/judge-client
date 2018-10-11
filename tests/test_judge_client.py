
from __future__ import unicode_literals

import time
import socket
import threading

from contextlib import closing
from unittest import TestCase
from judge_client.client import JudgeClient


def get_free_port_number():
    s = socket.socket(socket.AF_INET, type=socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    _, port = s.getsockname()
    s.close()
    return port


class JudgeClientTests(TestCase):
    TESTER_URL = '127.0.0.1'
    TESTER_ID = 'TEST'
    
    def setUp(self):
        self.port = get_free_port_number()

        def run_fake_server(test):
            with closing(socket.socket()) as server_sock:
                server_sock.bind((test.TESTER_URL, self.port))
                server_sock.listen(0)
                conn, addr = server_sock.accept()
                raw = conn.recv(2048)
                data = conn.recv(2048)
                test.received = raw + data
                time.sleep(100.0 / 1000.0)

        self.judge_client = JudgeClient(self.TESTER_ID, self.TESTER_URL, self.port)
        self.server_thread = threading.Thread(target=run_fake_server, args=(self,))
        self.server_thread.start()
        time.sleep(50.0 / 1000.0)  # 50ms should be enough for the server to bind

    def test_submit(self):
        self.judge_client.submit('test_id', 'test_user', 'test_task', 'test_submission ščť', 'py')
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
        self.assertEqual(request_parts[8].decode('utf-8'), 'test_submission ščť')

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
   

class ProtocolParsingTests(TestCase):
    def test_parse_protocol(self):
        self.judge_client = JudgeClient(
            'test', 'test', 0)

        protocol = '''<protokol><runLog>
        <test><name>0.sample.a.in</name><resultCode>1</resultCode><resultMsg>OK</resultMsg><time>28</time></test>
        <test><name>0.sample.b.in</name><resultCode>1</resultCode><resultMsg>OK</resultMsg><time>28</time></test>
        <test><name>1.a.in</name><resultCode>1</resultCode><resultMsg>OK</resultMsg><time>0</time></test>
        <test><name>1.b.in</name><resultCode>1</resultCode><resultMsg>OK</resultMsg><time>0</time></test>
        <test><name>2.a.in</name><resultCode>2</resultCode><resultMsg>WA</resultMsg><time>0</time></test>
        <test><name>2.b.in</name><resultCode>2</resultCode><resultMsg>WA</resultMsg><time>0</time></test>
        <test><name>3.a.in</name><resultCode>3</resultCode><resultMsg>TLE</resultMsg><time>0</time></test>
        <test><name>3.b.in</name><resultCode>3</resultCode><resultMsg>TLE</resultMsg><time>0</time></test>
        <test><name>3.a.in</name><resultCode>7</resultCode><resultMsg>IGN</resultMsg><time>0</time></test>
        <test><name>3.b.in</name><resultCode>7</resultCode><resultMsg>IGN</resultMsg><time>0</time></test>
        <score>25</score><details>
        Score: 25
        </details><finalResult>2</finalResult><finalMessage>Wrong Answer (OK: 25 %)</finalMessage></runLog></protokol>
        '''
        parsed_protocol = self.judge_client.parse_protocol(protocol, 100)

        self.assertEqual(parsed_protocol.result, 'WA')
        self.assertEqual(parsed_protocol.points, 25)
        self.assertEqual(len(parsed_protocol.tests), 10)
