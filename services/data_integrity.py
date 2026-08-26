from dataclasses import dataclass
from uuid import UUID


class DataIntegrityValidationError(ValueError):
    """Raised when operational figures contradict each other."""


@dataclass(frozen=True)
class PopulationReconciliation:
    affected_families: int
    affected_individuals: int
    inside_ec_families: int
    inside_ec_individuals: int
    outside_ec_families: int
    outside_ec_individuals: int

    @property
    def displaced_families(self) -> int:
        return self.inside_ec_families + self.outside_ec_families

    @property
    def displaced_individuals(self) -> int:
        return self.inside_ec_individuals + self.outside_ec_individuals

    @property
    def remaining_families(self) -> int:
        return self.affected_families - self.displaced_families

    @property
    def remaining_individuals(self) -> int:
        return self.affected_individuals - self.displaced_individuals


def _ensure_nonnegative(label: str, value: int | float) -> None:
    if value < 0:
        raise DataIntegrityValidationError(
            f"{label} cannot be negative."
        )


def validate_submission_key(value: str) -> str:
    """Return a canonical UUID string for idempotent form submissions."""
    try:
        return str(UUID(value.strip()))
    except (AttributeError, TypeError, ValueError) as error:
        raise DataIntegrityValidationError(
            "The submission token is invalid. Refresh the page and try again."
        ) from error


def reconcile_population(
    *,
    affected_families: int,
    affected_individuals: int,
    inside_ec_families: int,
    inside_ec_individuals: int,
    outside_ec_families: int,
    outside_ec_individuals: int,
) -> PopulationReconciliation:
    values = {
        "Affected families": affected_families,
        "Affected individuals": affected_individuals,
        "Families inside evacuation centers": inside_ec_families,
        "Individuals inside evacuation centers": inside_ec_individuals,
        "Families outside evacuation centers": outside_ec_families,
        "Individuals outside evacuation centers": outside_ec_individuals,
    }

    for label, value in values.items():
        _ensure_nonnegative(label, value)

    if affected_families > affected_individuals:
        raise DataIntegrityValidationError(
            "Affected families cannot exceed affected individuals."
        )

    if inside_ec_families > inside_ec_individuals:
        raise DataIntegrityValidationError(
            "Families inside evacuation centers cannot exceed "
            "individuals inside evacuation centers."
        )

    if outside_ec_families > outside_ec_individuals:
        raise DataIntegrityValidationError(
            "Families outside evacuation centers cannot exceed "
            "individuals outside evacuation centers."
        )

    result = PopulationReconciliation(
        affected_families=affected_families,
        affected_individuals=affected_individuals,
        inside_ec_families=inside_ec_families,
        inside_ec_individuals=inside_ec_individuals,
        outside_ec_families=outside_ec_families,
        outside_ec_individuals=outside_ec_individuals,
    )

    if result.displaced_families > affected_families:
        raise DataIntegrityValidationError(
            f"Total displaced families ({result.displaced_families}) cannot "
            f"exceed affected families ({affected_families})."
        )

    if result.displaced_individuals > affected_individuals:
        raise DataIntegrityValidationError(
            f"Total displaced individuals ({result.displaced_individuals}) "
            f"cannot exceed affected individuals ({affected_individuals})."
        )

    if result.remaining_families > result.remaining_individuals:
        raise DataIntegrityValidationError(
            "The figures would leave more remaining affected families "
            f"({result.remaining_families}) than remaining individuals "
            f"({result.remaining_individuals}). Reconcile the population "
            "figures before submitting."
        )

    return result


def validate_flood_consistency(
    *,
    flood_status: str,
    flood_depth_cm: float,
) -> None:
    _ensure_nonnegative("Flood depth", flood_depth_cm)

    if flood_status == "No Flooding" and flood_depth_cm > 0:
        raise DataIntegrityValidationError(
            "Flood depth must be 0 cm when flood status is No Flooding."
        )


def validate_evacuation_occupancy(
    *,
    status: str,
    families: int,
    individuals: int,
    children: int,
    senior_citizens: int,
    pwd: int,
    pregnant_women: int,
    medical_cases: int,
    safe_capacity: int,
) -> None:
    counts = {
        "Families": families,
        "Individuals": individuals,
        "Children": children,
        "Senior citizens": senior_citizens,
        "Persons with disabilities": pwd,
        "Pregnant women": pregnant_women,
        "Medical cases": medical_cases,
    }

    for label, value in counts.items():
        _ensure_nonnegative(label, value)

    if families > individuals:
        raise DataIntegrityValidationError(
            "Families cannot exceed individuals in an evacuation center."
        )

    for label, value in {
        "Children": children,
        "Senior citizens": senior_citizens,
        "Persons with disabilities": pwd,
        "Pregnant women": pregnant_women,
        "Medical cases": medical_cases,
    }.items():
        if value > individuals:
            raise DataIntegrityValidationError(
                f"{label} cannot exceed total individuals."
            )

    if status in {"Standby", "Closed"}:
        if any(
            value > 0
            for value in (
                families,
                individuals,
                children,
                senior_citizens,
                pwd,
                pregnant_women,
                medical_cases,
            )
        ):
            raise DataIntegrityValidationError(
                f"A center marked {status} must report zero occupants."
            )

    if safe_capacity > 0:
        if individuals > safe_capacity and status != "Over Capacity":
            raise DataIntegrityValidationError(
                f"Occupancy ({individuals}) exceeds the official safe "
                f"capacity ({safe_capacity}). Select Over Capacity or "
                "correct the occupancy figure."
            )

        if status == "Over Capacity" and individuals <= safe_capacity:
            raise DataIntegrityValidationError(
                "A center can only be marked Over Capacity when reported "
                "individuals exceed its official safe capacity."
            )
