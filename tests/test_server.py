import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
