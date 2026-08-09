ROLE_VIEWER = "Viewer"
ROLE_EXECUTIVE = "Executive"
ROLE_ENCODER = "Encoder"
ROLE_VALIDATOR = "Validator"
ROLE_OPERATIONS_OFFICER = "Operations Officer"
ROLE_ADMINISTRATOR = "Administrator"


APP_ROLES = (
    ROLE_VIEWER,
    ROLE_EXECUTIVE,
    ROLE_ENCODER,
    ROLE_VALIDATOR,
    ROLE_OPERATIONS_OFFICER,
    ROLE_ADMINISTRATOR,
)


PERMISSION_VIEW_DASHBOARD = "view_dashboard"
PERMISSION_MANAGE_EVENTS = "manage_events"
PERMISSION_SUBMIT_BARANGAY_UPDATES = (
    "submit_barangay_updates"
)
PERMISSION_VALIDATE_BARANGAY_REPORTS = (
    "validate_barangay_reports"
)
PERMISSION_MANAGE_EVACUATION_CENTERS = (
    "manage_evacuation_centers"
)
PERMISSION_SUBMIT_EVACUATION_UPDATES = (
    "submit_evacuation_updates"
)
PERMISSION_MANAGE_INCIDENTS = "manage_incidents"
PERMISSION_VIEW_REPORTS = "view_reports"
PERMISSION_MANAGE_USERS = "manage_users"


ALL_PERMISSIONS = frozenset(
    {
        PERMISSION_VIEW_DASHBOARD,
        PERMISSION_MANAGE_EVENTS,
        PERMISSION_SUBMIT_BARANGAY_UPDATES,
        PERMISSION_VALIDATE_BARANGAY_REPORTS,
        PERMISSION_MANAGE_EVACUATION_CENTERS,
        PERMISSION_SUBMIT_EVACUATION_UPDATES,
        PERMISSION_MANAGE_INCIDENTS,
        PERMISSION_VIEW_REPORTS,
        PERMISSION_MANAGE_USERS,
    }
)


ROLE_PERMISSIONS = {
    ROLE_VIEWER: frozenset(
        {
            PERMISSION_VIEW_DASHBOARD,
        }
    ),

    ROLE_EXECUTIVE: frozenset(
        {
            PERMISSION_VIEW_DASHBOARD,
            PERMISSION_VIEW_REPORTS,
        }
    ),

    ROLE_ENCODER: frozenset(
        {
            PERMISSION_VIEW_DASHBOARD,
            PERMISSION_SUBMIT_BARANGAY_UPDATES,
            PERMISSION_SUBMIT_EVACUATION_UPDATES,
        }
    ),

    ROLE_VALIDATOR: frozenset(
        {
            PERMISSION_VIEW_DASHBOARD,
            PERMISSION_VALIDATE_BARANGAY_REPORTS,
            PERMISSION_VIEW_REPORTS,
        }
    ),

    ROLE_OPERATIONS_OFFICER: frozenset(
        {
            PERMISSION_VIEW_DASHBOARD,
            PERMISSION_MANAGE_EVENTS,
            PERMISSION_SUBMIT_BARANGAY_UPDATES,
            PERMISSION_VALIDATE_BARANGAY_REPORTS,
            PERMISSION_MANAGE_EVACUATION_CENTERS,
            PERMISSION_SUBMIT_EVACUATION_UPDATES,
            PERMISSION_MANAGE_INCIDENTS,
            PERMISSION_VIEW_REPORTS,
        }
    ),

    ROLE_ADMINISTRATOR: ALL_PERMISSIONS,
}


def permissions_for_role(
    role: str,
) -> frozenset[str]:
    """
    Return the permissions assigned to one application role.
    """
    return ROLE_PERMISSIONS.get(
        role,
        frozenset(),
    )