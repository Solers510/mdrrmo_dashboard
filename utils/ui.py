from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESIGN_SYSTEM_STYLESHEET = (
    PROJECT_ROOT
    / "styles"
    / "mdrrmo.css"
)

OMDRRMO_SEAL_PATH = (
    PROJECT_ROOT
    / "assets"
    / "branding"
    / "OMDRRMO.png"
)
NAIC_SEAL_PATH = (
    PROJECT_ROOT
    / "assets"
    / "branding"
    / "bayannaic.png"
)

STATUS_TONES = {
    "neutral",
    "info",
    "success",
    "warning",
    "danger",
}


def load_design_system() -> None:
    """
    Load application-owned CSS only.

    No external font/CDN dependency is required, which keeps the interface
    usable when internet connectivity is degraded.
    """
    css = DESIGN_SYSTEM_STYLESHEET.read_text(
        encoding="utf-8"
    )
    st.html(
        f"<style>{css}</style>"
    )


def render_login_header() -> None:
    left, center, right = st.columns(
        [1, 4, 1],
        vertical_alignment="center",
    )

    with left:
        st.image(
            OMDRRMO_SEAL_PATH,
            width=105,
        )

    with center:
        st.html(
            """
            <section class="mdrrmo-login-shell">
              <p class="mdrrmo-login-shell__eyebrow">
                Municipality of Naic · Cavite
              </p>
              <h1 class="mdrrmo-login-shell__title">
                OMDRRMO Operations Information System
              </h1>
              <p class="mdrrmo-login-shell__subtitle">
                Disaster operations reporting, validation, evacuation-center
                monitoring, incident coordination, and situation reporting
                for authorized municipal personnel.
              </p>
            </section>
            """
        )

    with right:
        st.image(
            NAIC_SEAL_PATH,
            width=105,
        )

    st.html(
        """
        <p class="mdrrmo-login-note">
          Office of the Municipal Disaster Risk Reduction and Management
          Officer · Municipality of Naic, Cavite
        </p>
        """
    )


def render_sidebar_brand() -> None:
    with st.sidebar:
        logo_column, text_column = st.columns(
            [1, 3],
            vertical_alignment="center",
        )

        with logo_column:
            st.image(
                OMDRRMO_SEAL_PATH,
                width=52,
            )

        with text_column:
            st.html(
                """
                <p class="mdrrmo-sidebar-title">OMDRRMO</p>
                <p class="mdrrmo-sidebar-subtitle">
                  Operations Information System<br>
                  Naic, Cavite
                </p>
                """
            )

        st.html(
            '<div class="mdrrmo-sidebar-gold-rule"></div>'
        )


def render_identity_card(
    *,
    display_name: str,
    email: str,
    role: str,
) -> None:
    safe_name = escape(
        display_name
    )
    safe_email = escape(
        email
    )
    safe_role = escape(
        role
    )

    st.html(
        f"""
        <section class="mdrrmo-identity-card">
          <p class="mdrrmo-identity-card__label">Signed in as</p>
          <p class="mdrrmo-identity-card__name">{safe_name}</p>
          <p class="mdrrmo-identity-card__meta">
            {safe_role}<br>{safe_email}
          </p>
        </section>
        """
    )


def render_page_header(
    *,
    title: str,
    subtitle: str,
    eyebrow: str = "OMDRRMO Naic Operations",
) -> None:
    st.html(
        f"""
        <header class="mdrrmo-page-header">
          <p class="mdrrmo-page-header__eyebrow">
            {escape(eyebrow)}
          </p>
          <h1 class="mdrrmo-page-header__title">
            {escape(title)}
          </h1>
          <p class="mdrrmo-page-header__subtitle">
            {escape(subtitle)}
          </p>
        </header>
        """
    )


def render_status_badge(
    label: str,
    *,
    tone: str = "neutral",
) -> None:
    if tone not in STATUS_TONES:
        raise ValueError(
            f"Unsupported status tone: {tone}"
        )

    st.html(
        f"""
        <span
          class="mdrrmo-status mdrrmo-status--{tone}"
          role="status"
        >
          {escape(label)}
        </span>
        """
    )


def render_info_strip(
    text: str,
) -> None:
    st.html(
        f"""
        <div class="mdrrmo-info-strip">
          {escape(text)}
        </div>
        """
    )

def _status_tone_from_label(
    label: str,
) -> str:
    normalized = label.strip().upper()

    if "RED" in normalized:
        return "danger"

    if "BLUE" in normalized:
        return "info"

    if (
        "GREEN" in normalized
        or "NORMAL" in normalized
    ):
        return "success"

    if (
        "YELLOW" in normalized
        or "ORANGE" in normalized
        or "AMBER" in normalized
    ):
        return "warning"

    return "neutral"


def _operational_field(
    *,
    label: str,
    value: str,
) -> str:
    return f"""
      <div class="mdrrmo-ops-field">
        <span class="mdrrmo-ops-field__label">
          {escape(label)}
        </span>
        <span class="mdrrmo-ops-field__value">
          {escape(value)}
        </span>
      </div>
    """


def _alert_pill(
    alert_code: str,
) -> str:
    alert_text = (
        f"{alert_code.strip()} ALERT"
        if alert_code.strip()
        else "ALERT NOT SET"
    )
    tone = _status_tone_from_label(
        alert_text
    )

    return f"""
      <span
        class="mdrrmo-ops-alert
               mdrrmo-ops-alert--{tone}"
        role="status"
      >
        {escape(alert_text)}
      </span>
    """


def render_operational_page_header(
    *,
    title: str,
    subtitle: str,
) -> None:
    """
    Compact working-page header for operational screens.

    Institutional identity remains in the persistent sidebar, so the page
    header prioritizes task context instead of repeating a large hero card.
    """
    st.html(
        f"""
        <header class="mdrrmo-ops-page-header">
          <p class="mdrrmo-ops-page-header__eyebrow">
            OMDRRMO Naic Operations
          </p>
          <h1 class="mdrrmo-ops-page-header__title">
            {escape(title)}
          </h1>
          <p class="mdrrmo-ops-page-header__subtitle">
            {escape(subtitle)}
          </p>
        </header>
        """
    )

def render_operational_event_strip(
    *,
    event_name: str,
    hazard_type: str,
    alert_code: str,
    eoc_status: str,
    sitrep: str,
    official_reference: str | None = None,
) -> None:
    """
    Compact active-event common-operating-picture strip.

    Long event names, SitRep labels, references, and status values wrap
    normally. No operational identifier is intentionally ellipsized.
    """
    # Clean the raw database text for the Dashboard UI
    alert_code = str(alert_code).replace(" ALERT", "").strip()
    eoc_status = str(eoc_status).replace("EOCStatus.", "").replace("EOC_STATUS.", "").title()

    reference_html = ""

    if (
        official_reference is not None
        and official_reference.strip()
    ):
        reference_html = _operational_field(
            label="Official Reference",
            value=official_reference.strip(),
        )

    st.html(
        f"""
        <section class="mdrrmo-ops-event">
          <div class="mdrrmo-ops-event__top">
            <div class="mdrrmo-ops-event__identity">
              <p class="mdrrmo-ops-event__eyebrow">
                Active disaster event
              </p>
              <h2 class="mdrrmo-ops-event__name">
                {escape(event_name)}
              </h2>
            </div>
            <div class="mdrrmo-ops-event__alert">
              {_alert_pill(alert_code)}
            </div>
          </div>

          <div class="mdrrmo-ops-event__fields">
            {_operational_field(
                label="Hazard",
                value=hazard_type,
            )}
            {_operational_field(
                label="EOC Status",
                value=eoc_status,
            )}
            {_operational_field(
                label="Current SitRep",
                value=sitrep,
            )}
            {reference_html}
          </div>
        </section>
        """
    )


def render_event_control_strip(
    *,
    event_name: str,
    hazard_type: str,
    classification: str,
    alert_code: str,
    eoc_status: str,
    sitrep: str,
    started_at: str,
    official_reference: str | None = None,
) -> None:
    alert_code = str(alert_code).replace(" ALERT", "").strip()
    eoc_status = str(eoc_status).replace("EOCStatus.", "").replace("EOC_STATUS.", "").title()
    """
    Compact Event Control identity strip with full wrapping values.
    """
    reference_html = ""

    if (
        official_reference is not None
        and official_reference.strip()
    ):
        reference_html = _operational_field(
            label="Official Reference",
            value=official_reference.strip(),
        )

    st.html(
        f"""
        <section class="mdrrmo-ops-event">
          <div class="mdrrmo-ops-event__top">
            <div class="mdrrmo-ops-event__identity">
              <p class="mdrrmo-ops-event__eyebrow">
                Current active event
              </p>
              <h2 class="mdrrmo-ops-event__name">
                {escape(event_name)}
              </h2>
            </div>
            <div class="mdrrmo-ops-event__alert">
              {_alert_pill(alert_code)}
            </div>
          </div>

          <div class="mdrrmo-ops-event__fields
                      mdrrmo-ops-event__fields--control">
            {_operational_field(
                label="Hazard",
                value=hazard_type,
            )}
            {_operational_field(
                label="Classification",
                value=classification,
            )}
            {_operational_field(
                label="EOC Status",
                value=eoc_status,
            )}
            {_operational_field(
                label="Current SitRep",
                value=sitrep,
            )}
            {_operational_field(
                label="Started",
                value=started_at,
            )}
            {reference_html}
          </div>
        </section>
        """
    )
def render_dashboard_mode_status(
    *,
    mode: str,
) -> None:
    if mode == "Official Validated":
        tone = "success"
        title = "Official validated view"
        detail = (
            "Figures use only reports that have completed validation."
        )
    else:
        tone = "warning"
        title = "Provisional operational view"
        detail = (
            "Latest submitted operational reports are included; "
            "some figures may still be awaiting formal validation."
        )

    st.html(
        f"""
        <div class="mdrrmo-mode-strip mdrrmo-mode-strip--{tone}">
          <strong>{escape(title)}</strong>
          <span>{escape(detail)}</span>
        </div>
        """
    )


def render_dashboard_section_header(
    *,
    title: str,
    subtitle: str | None = None,
) -> None:
    subtitle_html = ""

    if subtitle:
        subtitle_html = (
            f'<p class="mdrrmo-dashboard-section__subtitle">'
            f'{escape(subtitle)}</p>'
        )

    st.html(
        f"""
        <header class="mdrrmo-dashboard-section">
          <h2 class="mdrrmo-dashboard-section__title">
            {escape(title)}
          </h2>
          {subtitle_html}
        </header>
        """
    )


def render_attention_required(
    items: list[dict[str, object]],
) -> None:
    """
    Render only current non-zero operational exceptions.

    Each item must contain label, value, and tone. Color reinforces the
    explicit text; it never carries the meaning by itself.
    """
    if not items:
        st.html(
            """
            <section class="mdrrmo-attention mdrrmo-attention--clear">
              <div class="mdrrmo-attention__clear-title">
                No immediate operational concern currently recorded
              </div>
              <div class="mdrrmo-attention__clear-detail">
                Continue monitoring incoming barangay, evacuation-center,
                validation, and reconciliation updates.
              </div>
            </section>
            """
        )
        return

    cards = []

    for item in items:
        tone = str(
            item.get(
                "tone",
                "warning",
            )
        )

        if tone not in {
            "warning",
            "danger",
            "info",
        }:
            tone = "warning"

        cards.append(
            f"""
            <div class="mdrrmo-attention-card
                        mdrrmo-attention-card--{tone}">
              <span class="mdrrmo-attention-card__value">
                {escape(str(item["value"]))}
              </span>
              <span class="mdrrmo-attention-card__label">
                {escape(str(item["label"]))}
              </span>
            </div>
            """
        )

    st.html(
        f"""
        <section class="mdrrmo-attention">
          <div class="mdrrmo-attention__grid">
            {''.join(cards)}
          </div>
        </section>
        """
    )


def render_kpi_grid(
    items: list[dict[str, object]],
    *,
    compact: bool = False,
) -> None:
    """
    Render a restrained operational summary grid.

    Primary cards use a single institutional blue accent. Compact cards are
    intentionally quieter for secondary breakdowns and freshness metadata.
    """
    grid_class = (
        "mdrrmo-kpi-grid mdrrmo-kpi-grid--compact"
        if compact
        else "mdrrmo-kpi-grid"
    )
    card_class = (
        "mdrrmo-kpi-card mdrrmo-kpi-card--compact"
        if compact
        else "mdrrmo-kpi-card"
    )

    cards = []

    for item in items:
        meta = item.get(
            "meta"
        )
        meta_html = ""

        if meta not in {
            None,
            "",
        }:
            meta_html = (
                '<span class="mdrrmo-kpi-card__meta">'
                + escape(
                    str(meta)
                )
                + "</span>"
            )

        cards.append(
            f"""
            <div class="{card_class}">
              <span class="mdrrmo-kpi-card__label">
                {escape(str(item["label"]))}
              </span>
              <span class="mdrrmo-kpi-card__value">
                {escape(str(item["value"]))}
              </span>
              {meta_html}
            </div>
            """
        )

    st.html(
        f"""
        <section class="{grid_class}">
          {''.join(cards)}
        </section>
        """
    )

def render_current_evacuation_picture(
    *,
    affected_barangays: int,
    affected_families: int,
    affected_individuals: int,
    operational_centers: int,
    inside_ec_families: int,
    inside_ec_individuals: int,
    outside_ec_families: int,
    outside_ec_individuals: int,
    non_displaced_families: int = 0,
    non_displaced_individuals: int = 0,
    mode_label: str = "Official Validated",
    barangay_as_of: str = "Not available",
    center_as_of: str = "Not available",
) -> None:
    total_evacuated_families = inside_ec_families + outside_ec_families
    total_evacuated_individuals = inside_ec_individuals + outside_ec_individuals

    # Context status header matching app design
    st.html(
        f"""
        <div class="mdrrmo-evacuation-picture__context" style="margin-bottom: 8px;">
          <strong>{escape(mode_label)}</strong>
          <span>
            Barangay reports as of {escape(barangay_as_of)} &middot;
            Center reports as of {escape(center_as_of)}
          </span>
        </div>
        """
    )

    # Top KPI Container - Total Affected Population
    st.markdown(f"""
    <div style="border: 1px solid #DDE3EF; border-radius: 8px; padding: 16px; background-color: #FFFFFF; margin-bottom: 12px;">
        <div style="font-weight: 600; text-align: center; margin-bottom: 4px; color: #1A2540; font-size: 16px;">Total Reported Affected Population</div>
        <div style="font-size: 12px; text-align: center; color: #6B7A99; margin-bottom: 12px;">
          Includes evacuees and affected residents who have not evacuated. Affected does not automatically mean injured, homeless, or staying in an evacuation center.
        </div>
        <div style="display: flex; justify-content: space-around; text-align: center;">
            <div><small style="color: #6B7A99; font-weight: 600;">AFFECTED BARANGAYS</small><div style="font-size: 22px; font-weight: 700; color: #1549A8;">{affected_barangays:,}</div></div>
            <div><small style="color: #6B7A99; font-weight: 600;">AFFECTED FAMILIES</small><div style="font-size: 22px; font-weight: 700; color: #1549A8;">{affected_families:,}</div></div>
            <div><small style="color: #6B7A99; font-weight: 600;">AFFECTED INDIVIDUALS</small><div style="font-size: 22px; font-weight: 700; color: #1549A8;">{affected_individuals:,}</div></div>
        </div>
        <div style="background-color: #EEF2F8; border-radius: 4px; padding: 6px; text-align: center; margin-top: 12px; font-size: 13px; font-weight: 600; color: #0D2461;">
            CURRENTLY EVACUATED: {total_evacuated_families:,} families &middot; {total_evacuated_individuals:,} individuals
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Symmetrical 3-Column Breakdown (Inside EC | Outside EC | Non-Displaced)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div style="border: 1px solid #DDE3EF; border-top: 3px solid #0F7E4A; border-radius: 6px; padding: 12px; background-color: #FFFFFF; text-align: center; height: 100%;">
            <div style="font-weight: 600; color: #1A2540; margin-bottom: 8px;">Inside Evacuation Centers</div>
            <div style="display: flex; justify-content: space-around;">
                <div><small style="color: #6B7A99;">CENTERS</small><div style="font-weight: 700; font-size: 16px;">{operational_centers:,}</div></div>
                <div><small style="color: #6B7A99;">FAMILIES</small><div style="font-weight: 700; font-size: 16px;">{inside_ec_families:,}</div></div>
                <div><small style="color: #6B7A99;">INDIVIDUALS</small><div style="font-weight: 700; font-size: 16px;">{inside_ec_individuals:,}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="border: 1px solid #DDE3EF; border-top: 3px solid #B45309; border-radius: 6px; padding: 12px; background-color: #FFFFFF; text-align: center; height: 100%;">
            <div style="font-weight: 600; color: #1A2540; margin-bottom: 8px;">Outside Evacuation Centers</div>
            <div style="display: flex; justify-content: space-around;">
                <div><small style="color: #6B7A99;">FAMILIES</small><div style="font-weight: 700; font-size: 16px;">{outside_ec_families:,}</div></div>
                <div><small style="color: #6B7A99;">INDIVIDUALS</small><div style="font-weight: 700; font-size: 16px;">{outside_ec_individuals:,}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="border: 1px solid #DDE3EF; border-top: 3px solid #1549A8; border-radius: 6px; padding: 12px; background-color: #FFFFFF; text-align: center; height: 100%;">
            <div style="font-weight: 600; color: #1A2540; margin-bottom: 8px;">Non-Displaced (Home-Based)</div>
            <div style="display: flex; justify-content: space-around;">
                <div><small style="color: #6B7A99;">FAMILIES</small><div style="font-weight: 700; font-size: 16px;">{non_displaced_families:,}</div></div>
                <div><small style="color: #6B7A99;">INDIVIDUALS</small><div style="font-weight: 700; font-size: 16px;">{non_displaced_individuals:,}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.html(
        """
        <p class="mdrrmo-evacuation-picture__source" style="margin-top: 12px; font-size: 11px; color: #6B7A99; text-align: center;">
          Population figures: current barangay reports &middot;
          Operational-center count: current evacuation-center reports
        </p>
        """
    )
def render_workflow_section(
    *,
    step: int,
    title: str,
    subtitle: str,
) -> None:
    """
    Render a compact numbered workflow heading for operational data-entry
    screens. The number communicates sequence; the text remains the primary
    accessible cue.
    """
    if step < 1:
        raise ValueError(
            "Workflow step must be at least 1."
        )

    st.html(
        f"""
        <header class="mdrrmo-workflow-section">
          <span
            class="mdrrmo-workflow-section__step"
            aria-hidden="true"
          >
            {step}
          </span>
          <div class="mdrrmo-workflow-section__copy">
            <h2 class="mdrrmo-workflow-section__title">
              {escape(title)}
            </h2>
            <p class="mdrrmo-workflow-section__subtitle">
              {escape(subtitle)}
            </p>
          </div>
        </header>
        """
    )
