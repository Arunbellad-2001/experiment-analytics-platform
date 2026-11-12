"""Steps 3 & 4: Synthetic AudienceMember generation and per-experiment eligibility partitioning."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

import numpy as np
from sqlalchemy.orm import Session

from config.settings import REFERENCE_EPOCH_ISO, DatasetScaleConfig
from database.models import AudienceMember

SEGMENTS = ("New", "Returning", "SMB", "Enterprise")
SEGMENT_PROBS = (0.35, 0.40, 0.15, 0.10)

REGIONS = ("US-East", "EU-West", "APAC-South", "LATAM")
REGION_PROBS = (0.45, 0.25, 0.20, 0.10)


def generate_audience_members(
    session: Session,
    config: DatasetScaleConfig,
) -> Dict[str, List[AudienceMember]]:
    """Generate synthetic eligible and ineligible users partitioned deterministically across experiments."""
    rng = np.random.default_rng(config.random_seed + 101)
    total_users = config.total_audience_members
    base_dt = datetime.fromisoformat(REFERENCE_EPOCH_ISO.replace("Z", "+00:00"))

    segments = rng.choice(SEGMENTS, size=total_users, replace=True, p=SEGMENT_PROBS)
    regions = rng.choice(REGIONS, size=total_users, replace=True, p=REGION_PROBS)
    reg_days_ago = rng.integers(1, 365, size=total_users)

    all_members: List[AudienceMember] = []
    experiment_user_pools: Dict[str, List[AudienceMember]] = {}

    user_counter = 1
    users_per_exp = (
        config.eligible_users_per_experiment + config.ineligible_users_per_experiment
    )

    for exp_idx in range(1, config.experiment_count + 1):
        exp_id = f"EXP-2026-{exp_idx:06d}"
        exp_pool: List[AudienceMember] = []

        for local_idx in range(users_per_exp):
            arr_idx = user_counter - 1
            is_eligible = local_idx < config.eligible_users_per_experiment
            eligibility_status = "Eligible" if is_eligible else "Ineligible"
            reg_dt = base_dt - timedelta(days=int(reg_days_ago[arr_idx]))
            reg_iso = reg_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            member = AudienceMember(
                user_id=f"USER-{user_counter:06d}",
                user_segment=str(segments[arr_idx]),
                eligibility_status=eligibility_status,
                registration_date=reg_iso,
                country_region=str(regions[arr_idx]),
                created_at=REFERENCE_EPOCH_ISO,
            )
            all_members.append(member)
            exp_pool.append(member)
            user_counter += 1

        experiment_user_pools[exp_id] = exp_pool

    session.add_all(all_members)
    session.flush()
    return experiment_user_pools


def filter_eligible_audience(
    candidates: List[AudienceMember],
) -> List[AudienceMember]:
    """Step 4: Deterministically select only Eligible users and exclude Ineligible users."""
    return [u for u in candidates if u.eligibility_status == "Eligible"]