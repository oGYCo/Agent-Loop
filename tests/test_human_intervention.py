"""Tests for HumanIntervention module"""

import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state_manager import StateManager
from agent.human_intervention import HumanIntervention


class TestHumanIntervention:
    """Test cases for HumanIntervention"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def state_manager(self, temp_agent_dir):
        """Create StateManager with temporary directory"""
        return StateManager(agent_dir=temp_agent_dir)

    @pytest.fixture
    def human_intervention(self, state_manager):
        """Create HumanIntervention with test state manager"""
        return HumanIntervention(state_manager)

    def test_should_intervene_error_threshold(self, human_intervention):
        """Test intervention when error threshold reached"""
        # Default max_errors is 3
        result = human_intervention.should_intervene(error_count=3)
        assert result is True

    def test_should_intervene_below_threshold(self, human_intervention):
        """Test intervention when below error threshold"""
        result = human_intervention.should_intervene(error_count=2)
        assert result is False

    def test_should_intervene_irreversible_operation(self, human_intervention):
        """Test intervention for irreversible operations"""
        result = human_intervention.should_intervene(
            error_count=1,
            error_type="delete operation"
        )
        assert result is True

    def test_should_intervene_no_trigger(self, human_intervention):
        """Test no intervention needed"""
        result = human_intervention.should_intervene(
            error_count=1,
            error_type="simple error"
        )
        assert result is False

    def test_should_intervene_drop_operation(self, human_intervention):
        """Test intervention for drop operation"""
        result = human_intervention.should_intervene(
            error_count=1,
            error_type="DROP TABLE"
        )
        assert result is True

    def test_should_intervene_destroy_operation(self, human_intervention):
        """Test intervention for destroy operation"""
        result = human_intervention.should_intervene(
            error_count=1,
            error_type="destroy resources"
        )
        assert result is True

    def test_request_intervention(self, human_intervention):
        """Test requesting intervention"""
        result = human_intervention.request_intervention(
            reason="Test intervention",
            context={"test": "data"},
            task_id="feature-001"
        )
        assert result["reason"] == "Test intervention"
        assert result["status"] == "pending"
        assert result["task_id"] == "feature-001"
        assert "timestamp" in result

    def test_request_intervention_saved(self, human_intervention, temp_agent_dir):
        """Test intervention request is saved to file"""
        human_intervention.request_intervention(
            reason="Test",
            task_id="feature-001"
        )

        request_file = Path(temp_agent_dir) / "intervention_requests.json"
        assert request_file.exists()

        with open(request_file) as f:
            requests = json.load(f)
        assert len(requests) >= 1

    def test_check_and_notify_no_need(self, human_intervention):
        """Test check_and_notify when no intervention needed"""
        state = {
            "error_count": 1,
            "last_error": "simple error"
        }
        result = human_intervention.check_and_notify(state)
        assert result is None

    def test_check_and_notify_needed(self, human_intervention):
        """Test check_and_notify when intervention needed"""
        state = {
            "error_count": 3,
            "last_error": "Test error",
            "current_task": "feature-001"
        }
        result = human_intervention.check_and_notify(state)
        assert result is not None
        assert result["status"] == "pending"

    def test_custom_max_errors(self, temp_agent_dir):
        """Test custom max errors from config"""
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({"max_errors_before_intervention": 5})

        hi = HumanIntervention(sm)
        assert hi.max_errors == 5

    def test_default_max_errors(self, human_intervention):
        """Test default max errors"""
        # Default should be 3 (from config)
        assert human_intervention.max_errors == 3

    def test_multiple_intervention_requests(self, human_intervention):
        """Test multiple intervention requests are appended"""
        human_intervention.request_intervention(reason="First")
        human_intervention.request_intervention(reason="Second")

        request_file = human_intervention.state_manager.agent_dir / "intervention_requests.json"
        with open(request_file) as f:
            requests = json.load(f)

        assert len(requests) == 2

    def test_notify_completion(self, human_intervention, temp_agent_dir):
        """Test notify completion"""
        summary = {
            "completed": 5,
            "errors": 2
        }
        human_intervention.notify_completion(summary)

        completion_file = Path(temp_agent_dir) / "session_summary.txt"
        assert completion_file.exists()

        with open(completion_file) as f:
            content = f.read()
        assert "completed: 5" in content
        assert "Errors encountered: 2" in content
