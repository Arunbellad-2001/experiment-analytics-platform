"""Step 5: Reproducible randomized assignment generation across all configured experiments."""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy.orm import Session

from config.settings import DatasetScaleConfig
from database.models import Assignment, AudienceMember
from generator.audience_generator import filter_eligible_audience
from generator.master_data import get_blueprints_for_config
from services.experiment_service import transition_experiment_status
from services.randomization import assign_eligible_users


def generate_assignments_for_all_experiments(
    session: Session,
    config: DatasetScaleConfig,
    experiment_user_pools: Dict[str, List[AudienceMember]],
    inject_srm_on_designated: bool = False,
) -> Dict[str, List[Assignment]]:
    """Assign eligible users to variants for every experiment and advance lifecycle Draft -> Ready -> Running."""
    blueprints = {
        f"EXP-2026-{bp.index:06d}": bp for bp in get_blueprints_for_config(config)
    }
    assignments_by_exp: Dict[str, List[Assignment]] = {}

    for exp_id in sorted(experiment_user_pools.keys()):
        # Transition Draft -> Ready -> Running before assigning users
        transition_experiment_status(
            session,
            experiment_id=exp_id,
            target_status="Ready",
            actor="Marketing_Ops",
            event_timestamp="2026-01-01T00:30:00Z",
            notes="Validated variants and primary metric; marked Ready",
        )
        transition_experiment_status(
            session,
            experiment_id=exp_id,
            target_status="Running",
            actor="System_Admin",
            event_timestamp="2026-01-01T01:00:00Z",
            notes="Started experiment traffic allocation",
        )

        eligible_pool = filter_eligible_audience(experiment_user_pools[exp_id])
        bp = blueprints[exp_id]

        # If SRM anomaly injection is enabled for the designated SRM host experiment (EXP-2026-000005),
        # skew actual assignment probabilities (e.g. 62% Control / 38% Treatment vs expected 50:50)
        override_probs = None
        if inject_srm_on_designated and bp.scenario_tag == "ANOMALY_AND_SRM_HOST":
            override_probs = [0.62, 0.38]

        exp_assignments = assign_eligible_users(
            session=session,
            experiment_id=exp_id,
            candidate_users=eligible_pool,
            seed=config.random_seed,
            override_probabilities=override_probs,
            persist=True,
        )
        assignments_by_exp[exp_id] = exp_assignments

    return assignments_by_exp