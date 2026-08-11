import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from src.api.app import (
    AssessmentRequest,
    app,
    create_assessment,
    get_assessment,
    health,
)
from src.api.task_manager import AssessmentTaskManager
from src.application import AssessmentResult


class SuccessfulRunner:
    def run(self, command, progress=None):
        if progress:
            progress("RISK_ASSESSMENT")
        return AssessmentResult(elapsed_seconds=0.01, artifacts=())


class AssessmentApiTest(unittest.TestCase):
    def setUp(self):
        self.manager = AssessmentTaskManager(runner=SuccessfulRunner())
        self.request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(task_manager=self.manager))
        )

    def tearDown(self):
        self.manager.shutdown()

    def test_health(self):
        self.assertEqual("UP", health(self.request)["status"])

    def test_submit_and_query_assessment(self):
        submitted = create_assessment(
            AssessmentRequest(prepare_input=False, recalculate=True),
            self.request,
        )
        task = get_assessment(submitted["task_id"], self.request)
        self.assertIn(task["status"], {"QUEUED", "RUNNING", "SUCCEEDED"})

    def test_unknown_task_returns_404(self):
        with self.assertRaises(HTTPException) as context:
            get_assessment("not-found", self.request)
        self.assertEqual(404, context.exception.status_code)

    def test_openapi_contains_submit_and_query_operations(self):
        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/assessments", paths)
        self.assertIn("/api/v1/assessments/{task_id}", paths)


if __name__ == "__main__":
    unittest.main()
