# OMDRRMO Operational Console — Phase 11B

## Design objective

The operational workspace should be visually restrained, information-dense,
and fast to scan under time pressure. Institutional identity remains visible
in the sidebar, while the working area prioritizes current situation,
exceptions, freshness, and action.

## Phase 11B1 V2 decisions

- Replace large public-website-style page hero cards with compact working
  headers.
- Replace the dark full-width event hero with a neutral white command strip.
- Keep the full-text wrapping behavior introduced by Phase 11B1.
- Use sans-serif typography throughout the operational workspace.
- Reserve the OMDRRMO serif treatment for login/formal identity and later
  formal report presentation.
- Keep the official alert name visible as text; color only reinforces it.
- Keep gold as a restrained institutional accent rather than a dominant
  interaction color.
- Do not rely on undocumented Streamlit DOM selectors.

## Next dashboard layers

Phase 11B2:
- Attention Required
- primary KPI hierarchy
- data freshness / coverage

Phase 11B3:
- operational tables
- simplified charts
- reporting and reconciliation layout
