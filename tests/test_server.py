import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server


class AttemptTests(unittest.TestCase):
    def test_attempt_has_20_main_questions_and_four_random_extras(self):
        self.assertEqual(len(server.QUESTIONS), 25)
        attempt = server.new_attempt()
        self.assertEqual(len(attempt["questions"]), 24)
        self.assertEqual(len({question["id"] for question in attempt["questions"]}), 24)
        self.assertEqual(sum(question["points"] for question in attempt["questions"]), 300)
        self.assertEqual({question["node"] for question in attempt["questions"]}, {"node1", "node2"})
        self.assertEqual(
            {question["id"] for question in attempt["questions"] if question["number"] <= 20},
            {question["id"] for question in server.QUESTIONS if question["number"] <= 20},
        )
        self.assertEqual(sum(question["number"] > 20 for question in attempt["questions"]), 4)

    def test_grading_scores_pass_threshold(self):
        attempt = {"question_ids": [question["id"] for question in server.QUESTIONS[:24]]}

        def all_pass(machine, question_ids):
            return {question_id: True for question_id in question_ids}

        with patch.object(server, "run_checks", side_effect=all_pass):
            result = server.grade_attempt(attempt)
        self.assertEqual(result["score"], 300)
        self.assertTrue(result["passed"])
        self.assertEqual(result["correct"], 24)

    def test_failed_checks_are_zero_points(self):
        attempt = {"question_ids": [question["id"] for question in server.QUESTIONS[:24]]}

        def one_pass(machine, question_ids):
            return {question_id: question_id == attempt["question_ids"][0] for question_id in question_ids}

        with patch.object(server, "run_checks", side_effect=one_pass):
            result = server.grade_attempt(attempt)
        self.assertEqual(result["score"], 12.5)
        self.assertFalse(result["passed"])

    def test_checker_scripts_cover_all_questions(self):
        self.assertEqual(set(server.CHECKS), {question["id"] for question in server.QUESTIONS})
        script = server.make_check_script(["network", "chrony"])
        self.assertIn("__EX200_RESULT__network:", script)
        self.assertIn("__EX200_RESULT__chrony:", script)

    def test_password_expiry_check_preserves_vagrant_management_account(self):
        self.assertIn('[ "$username" = vagrant ] && continue', server.CHECKS["password-expiry"])

    def test_autofs_check_requires_a_live_nfs_mount(self):
        self.assertIn("findmnt -rn -t nfs,nfs4", server.CHECKS["autofs"])

    def test_chrony_check_verifies_the_gateway_source_by_ip(self):
        self.assertIn("chronyc sources -n", server.CHECKS["chrony"])
        self.assertIn("172.25.250.254", server.CHECKS["chrony"])

    def test_swap_check_allows_mkswap_metadata_overhead(self):
        self.assertIn("total >= 536854528", server.CHECKS["swap"])

    def test_non_binary_checker_exit_codes_are_reported_as_failed(self):
        completed = server.subprocess.CompletedProcess(
            args=["ssh"],
            returncode=0,
            stdout="__EX200_RESULT__users-groups:2\n",
            stderr="",
        )
        with (
            patch.object(server, "vagrant_ssh_config", return_value={
                "HostName": "127.0.0.1",
                "User": "vagrant",
                "Port": "2222",
                "IdentityFile": "/tmp/vagrant-key",
            }),
            patch.object(server.subprocess, "run", return_value=completed),
        ):
            self.assertEqual(server.run_checks("node1", ["users-groups"]), {"users-groups": False})


class LabOperationTests(unittest.TestCase):
    class FakeProcess:
        def __init__(self, *args, **kwargs):
            self.args = args[0]
            self.stdout = iter(["Vagrant output\n"])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def wait(self):
            return 0

    def setUp(self):
        self.previous_operation = {**server.LAB_OPERATION, "output": list(server.LAB_OPERATION["output"])}
        server.LAB_OPERATION.update(
            id="test-operation",
            action="reset",
            provider="virtualbox",
            phase="starting",
            running=True,
            success=None,
            error=None,
            output=[],
        )

    def tearDown(self):
        server.LAB_OPERATION.clear()
        server.LAB_OPERATION.update(self.previous_operation)

    def test_machine_states_parses_vagrant_machine_readable_output(self):
        output = "\n".join(
            [
                "1,gateway,provider-name,virtualbox",
                "1,gateway,state,running",
                "1,node1,provider-name,virtualbox",
                "1,node1,state,poweroff",
                "1,node2,provider-name,virtualbox",
                "1,node2,state,running",
            ]
        )
        with patch.object(
            server.subprocess,
            "run",
            return_value=server.subprocess.CompletedProcess([], 0, output, ""),
        ):
            states, provider = server.machine_status()
        self.assertEqual(
            states,
            {"gateway": "running", "node1": "poweroff", "node2": "running"},
        )
        self.assertEqual(provider, "virtualbox")

    def test_vmware_deploys_machines_sequentially(self):
        with patch.object(server.subprocess, "Popen", side_effect=self.FakeProcess) as popen:
            server.run_lab_operation("test-operation", "deploy", "vmware_desktop")

        self.assertEqual(
            [call.args[0] for call in popen.call_args_list],
            [
                [server.VAGRANT, "up", "gateway", "--provider=vmware_desktop"],
                [server.VAGRANT, "up", "node1", "--provider=vmware_desktop"],
                [server.VAGRANT, "up", "node2", "--provider=vmware_desktop"],
            ],
        )
        self.assertFalse(server.LAB_OPERATION["running"])
        self.assertTrue(server.LAB_OPERATION["success"])

    def test_vmware_reset_destroys_and_deploys_machines_sequentially(self):
        with patch.object(server.subprocess, "Popen", side_effect=self.FakeProcess) as popen:
            server.run_lab_operation("test-operation", "reset", "vmware_desktop")

        self.assertEqual(
            [call.args[0] for call in popen.call_args_list],
            [
                [server.VAGRANT, "destroy", "-f", "gateway"],
                [server.VAGRANT, "destroy", "-f", "node1"],
                [server.VAGRANT, "destroy", "-f", "node2"],
                [server.VAGRANT, "up", "gateway", "--provider=vmware_desktop"],
                [server.VAGRANT, "up", "node1", "--provider=vmware_desktop"],
                [server.VAGRANT, "up", "node2", "--provider=vmware_desktop"],
            ],
        )
        self.assertFalse(server.LAB_OPERATION["running"])
        self.assertTrue(server.LAB_OPERATION["success"])

    def test_vmware_destroy_removes_machines_sequentially_without_deploying(self):
        with patch.object(server.subprocess, "Popen", side_effect=self.FakeProcess) as popen:
            server.run_lab_operation("test-operation", "destroy", "vmware_desktop")

        self.assertEqual(
            [call.args[0] for call in popen.call_args_list],
            [
                [server.VAGRANT, "destroy", "-f", "gateway"],
                [server.VAGRANT, "destroy", "-f", "node1"],
                [server.VAGRANT, "destroy", "-f", "node2"],
            ],
        )
        self.assertFalse(server.LAB_OPERATION["running"])
        self.assertTrue(server.LAB_OPERATION["success"])

    def test_destroy_removes_all_machines_with_selected_provider(self):
        with patch.object(server.subprocess, "Popen", side_effect=self.FakeProcess) as popen:
            server.run_lab_operation("test-operation", "destroy", "hyperv")

        self.assertEqual(
            [call.args[0] for call in popen.call_args_list],
            [[server.VAGRANT, "destroy", "-f"]],
        )
        self.assertFalse(server.LAB_OPERATION["running"])
        self.assertTrue(server.LAB_OPERATION["success"])

    def test_reset_destroys_then_deploys_with_selected_provider(self):
        with patch.object(server.subprocess, "Popen", side_effect=self.FakeProcess) as popen:
            server.run_lab_operation("test-operation", "reset", "hyperv")

        self.assertEqual(
            [call.args[0] for call in popen.call_args_list],
            [
                [server.VAGRANT, "destroy", "-f"],
                [server.VAGRANT, "up", "--provider=hyperv"],
            ],
        )
        self.assertFalse(server.LAB_OPERATION["running"])
        self.assertTrue(server.LAB_OPERATION["success"])

    def test_invalid_provider_is_rejected_before_starting_operation(self):
        with self.assertRaises(ValueError):
            server.start_lab_operation("deploy", [])
        self.assertEqual(server.LAB_OPERATION["id"], "test-operation")

    def test_destroy_operation_is_accepted(self):
        server.LAB_OPERATION["running"] = False
        with patch.object(server.threading.Thread, "start"):
            operation = server.start_lab_operation("destroy", "vmware_desktop")

        self.assertEqual(operation["action"], "destroy")
        self.assertTrue(operation["running"])

    def test_console_urls_accept_only_web_urls_without_embedded_credentials(self):
        configured = (
            '{"virtualbox":{"node1":"http://127.0.0.1:8081/console"},'
            '"hyperv":{"node2":"https://wac.example.test"}}'
        )
        with patch.dict("os.environ", {"EX200_CONSOLE_URLS": configured}):
            self.assertEqual(
                server.configured_console_urls(),
                {
                    "virtualbox": {"node1": "http://127.0.0.1:8081/console"},
                    "hyperv": {"node2": "https://wac.example.test"},
                },
            )

        invalid = '{"vmware_desktop":{"node1":"javascript:alert(1)"}}'
        with patch.dict("os.environ", {"EX200_CONSOLE_URLS": invalid}):
            with self.assertRaises(RuntimeError):
                server.configured_console_urls()

        credential_url = '{"hyperv":{"node1":"https://admin:secret@wac.example.test"}}'
        with patch.dict("os.environ", {"EX200_CONSOLE_URLS": credential_url}):
            with self.assertRaises(RuntimeError):
                server.configured_console_urls()


class WebApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def test_allowed_frontend_origin_can_read_status_and_console_links(self):
        origin = "http://127.0.0.1:8080"
        with (
            patch.object(
                server,
                "machine_status",
                return_value=(
                    {"gateway": "running", "node1": "running", "node2": "running"},
                    "virtualbox",
                ),
            ),
            patch.dict(
                "os.environ",
                {"EX200_CONSOLE_URLS": '{"virtualbox":{"node1":"http://127.0.0.1:8081/console"}}'},
            ),
        ):
            request = Request(f"{self.base_url}/api/lab/status", headers={"Origin": origin})
            with urlopen(request, timeout=5) as response:
                body = json.load(response)
                self.assertEqual(response.headers["Access-Control-Allow-Origin"], origin)
        self.assertTrue(body["ready"])
        self.assertEqual(body["consoles"]["node1"], "http://127.0.0.1:8081/console")

    def test_untrusted_web_origin_cannot_start_lab_operations(self):
        request = Request(
            f"{self.base_url}/api/lab/reset",
            data=b'{"provider":"virtualbox"}',
            headers={
                "Origin": "https://untrusted.example",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=5)
        raised.exception.close()
        self.assertEqual(raised.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
