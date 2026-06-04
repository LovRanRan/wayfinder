"""Run the enterprise workflow case-study demo on synthetic local data."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

EXAMPLE_DIR = Path(__file__).parent
REPO_SRC = EXAMPLE_DIR.parents[1] / "src"
if str(REPO_SRC) not in sys.path:
    sys.path.insert(0, str(REPO_SRC))

from wayfinder.enterprise.graph import run_enterprise_workflow  # noqa: E402
from wayfinder.enterprise.state import CandidateProfile, Contact, JobDescription  # noqa: E402


def main() -> None:
    candidates = _load_candidates(EXAMPLE_DIR / "mock_candidates.json")
    jobs = _load_jobs(EXAMPLE_DIR / "mock_jobs.json")
    contacts = _load_contacts(EXAMPLE_DIR / "mock_contacts.json")
    candidate = candidates[0]

    state = run_enterprise_workflow(
        candidate,
        jobs,
        contacts,
        run_id="run_demo_001",
        created_at=datetime(2026, 6, 4, 12, 0, 0, tzinfo=UTC),
    )
    output_dir = EXAMPLE_DIR / "expected_outputs"
    output_dir.mkdir(exist_ok=True)

    (output_dir / "sample_audit_log.json").write_text(
        json.dumps(
            [event.model_dump(mode="json") for event in state.audit_events],
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "sample_approval_task.json").write_text(
        json.dumps(
            [task.model_dump(mode="json") for task in state.approval_tasks],
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "sample_agent_report.md").write_text(
        state.final_report + "\n",
        encoding="utf-8",
    )
    print(state.final_report)


def _load_candidates(path: Path) -> list[CandidateProfile]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected list in {path}")
    return [CandidateProfile.model_validate(item) for item in payload]


def _load_jobs(path: Path) -> list[JobDescription]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected list in {path}")
    return [JobDescription.model_validate(item) for item in payload]


def _load_contacts(path: Path) -> list[Contact]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected list in {path}")
    return [Contact.model_validate(item) for item in payload]


if __name__ == "__main__":
    main()
