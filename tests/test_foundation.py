import unittest

from platform_app.api import app
from platform_app.models import Base
from platform_app.workflow import HUMAN_GATES, STAGE_ORDER, WorkflowStage


class FoundationTests(unittest.TestCase):
    def test_workflow_has_required_approval_gates(self):
        self.assertEqual(
            HUMAN_GATES,
            {
                WorkflowStage.HYPOTHESIS_REVIEW,
                WorkflowStage.CONTENT_REVIEW,
                WorkflowStage.PUBLISH_REVIEW,
            },
        )

    def test_publish_requires_review_stage(self):
        self.assertLess(
            STAGE_ORDER.index(WorkflowStage.PUBLISH_REVIEW),
            STAGE_ORDER.index(WorkflowStage.PUBLISHING),
        )

    def test_core_models_registered(self):
        self.assertIn("research_runs", Base.metadata.tables)
        self.assertIn("literature_chunks", Base.metadata.tables)
        self.assertIn("clinical_observations", Base.metadata.tables)
        self.assertIn("concepts", Base.metadata.tables)

    def test_health_route_exists(self):
        self.assertTrue(any(route.path == "/health" for route in app.routes))


if __name__ == "__main__":
    unittest.main()
