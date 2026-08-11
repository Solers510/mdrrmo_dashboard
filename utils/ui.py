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
