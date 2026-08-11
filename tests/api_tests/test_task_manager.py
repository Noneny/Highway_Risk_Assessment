import time
import unittest

from src.api.task_manager import AssessmentTaskManager, TaskStatus
from src.application import AssessmentCommand, AssessmentResult


class SuccessfulRunner:
    def run(self, command, progress=None):
        if progress:
            progress("RISK_ASSESSMENT")
        return AssessmentResult(elapsed_seconds=0.01, artifacts=())


class FailingRunner:
    def run(self, command, progress=None):
        raise RuntimeError("test failure")


def wait_for_terminal_state(manager, task_id, timeout=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = manager.get(task_id)
        if task.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED):
            return task
        time.sleep(0.01)
    raise AssertionError("task did not finish")


class AssessmentTaskManagerTest(unittest.TestCase):
    def test_successful_task_exposes_result(self):
        manager = AssessmentTaskManager(runner=SuccessfulRunner())
        self.addCleanup(manager.shutdown)

        submitted = manager.submit(AssessmentCommand(prepare_input=False))
        finished = wait_for_terminal_state(manager, submitted.task_id)

        self.assertEqual(TaskStatus.SUCCEEDED, finished.status)
        self.assertEqual("COMPLETED", finished.phase)
        self.assertIsNotNone(finished.result)
        self.assertIsNone(finished.error)

    def test_failure_is_recorded_instead_of_lost_in_worker(self):
        manager = AssessmentTaskManager(runner=FailingRunner())
        self.addCleanup(manager.shutdown)

        submitted = manager.submit(AssessmentCommand(prepare_input=False))
        finished = wait_for_terminal_state(manager, submitted.task_id)

        self.assertEqual(TaskStatus.FAILED, finished.status)
        self.assertIn("test failure", finished.error)

    def test_invalid_compare_only_command_is_rejected(self):
        manager = AssessmentTaskManager(runner=SuccessfulRunner())
        self.addCleanup(manager.shutdown)

        with self.assertRaises(ValueError):
            manager.submit(AssessmentCommand(recalculate=False, compare=False))


if __name__ == "__main__":
    unittest.main()
