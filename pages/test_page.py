"""
test_page.py -- Restyled variant of the Warming Stripes viewer.

Streamlit auto-registers any non-underscore .py in pages/ as a route, so this
file is reachable at /test_page. It loads the SAME interactive HTML as the main
app (pages/_thermachrome.html) and injects a thin "restyle layer" over the CSS
design tokens instead of duplicating the 3116-line document. That way the test
page keeps inheriting every future fix to the real app; only typography and the
colour palette differ.

The distinctive look of the original (Playfair Display display serif + brick-red
accent) is what reads as the Thermachrome identity. Swapping the serif to Source
Serif Pro and the accent to a desaturated terracotta gives this page its own
visual voice. The RdBu stripe spectrum is left untouched -- it is the scientific
standard shared by all warming-stripes visualisations, not a borrowed design.
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_PAGES_DIR = Path(__file__).parent
_HTML = _PAGES_DIR / "_thermachrome.html"

# ── Pick the identity here ──────────────────────────────────────────────────
# Flip this single string to switch the whole palette. "orange" is the default
# terracotta identity; "purple" is a muted plum alternative.
PALETTE_NAME = "orange"

PALETTES = {
    # Desaturated terracotta on warm charcoal
    "orange": {
        "accent_dark":  "#cc7a4a",
        "accent_paper": "#b3673c",
        "bg":           "#100d0b",
        "panel_bg":     "rgba(20,17,14,.9)",
        "surface":      "#191512",
    },
    # Muted plum on cool charcoal
    "purple": {
        "accent_dark":  "#9079b0",
        "accent_paper": "#7a5f97",
        "bg":           "#0e0d12",
        "panel_bg":     "rgba(17,16,22,.9)",
        "surface":      "#161520",
    },
}
P = PALETTES[PALETTE_NAME]

# Source Serif Pro's static Google Fonts set has no weight 800, so we request
# 700 (and let the restyle drop title weights from 800 to 700 for crisp text).
_FONT_LINK_OLD = (
    "family=Inter:wght@400;500;600;700"
    "&family=Playfair+Display:ital,wght@0,700;0,800;1,400"
)
_FONT_LINK_NEW = (
    "family=Inter:wght@400;500;600;700"
    "&family=Source+Serif+Pro:ital,wght@0,400;0,600;0,700;1,400"
)

_RESTYLE = f"""
<style id="test-page-restyle">
  :root {{
    --font-serif:"Source Serif Pro",Georgia,serif;
    --accent:{P['accent_dark']};
    --bg:{P['bg']}; --panel-bg:{P['panel_bg']}; --surface:{P['surface']};
  }}
  html[data-theme=paper] {{ --accent:{P['accent_paper']}; }}
  /* Source Serif Pro is a text serif, not a display face: relax the tight
     display tracking and step titles down from 800 to 700 so glyphs stay crisp. */
  .masthead__title, .cover__title, .present-title__name, .barchart-panel__title {{
    font-weight:700; letter-spacing:0;
  }}
  /* Colour the titles in the accent hue. */
  .masthead__title, .section__label {{ color:var(--accent); }}
  /* Format the 01/02/03 counters like their section titles instead of the
     original serif prominence: same font, size, weight, and tracking, so the
     number and label read as one line. Colour comes from .section__label above. */
  .section__label::before {{
    font-family:var(--font-sans); font-size:10px; font-weight:600; letter-spacing:.16em;
  }}
</style>
"""


def _restyled_html() -> str:
    html = _HTML.read_text(encoding="utf-8")
    html = html.replace(_FONT_LINK_OLD, _FONT_LINK_NEW, 1)
    # Keep PNG/SVG canvas exports consistent with the new on-screen serif.
    html = html.replace(
        "'\"Playfair Display\", Georgia, serif'",
        "'\"Source Serif Pro\", Georgia, serif'",
        1,
    )
    return html.replace("</head>", _RESTYLE + "</head>", 1)


st.set_page_config(
    page_title="Warming Stripes -- Test Page",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Same full-bleed shell as the main app, with the warm-charcoal backdrop so the
# brief pre-iframe flash matches the restyled page instead of showing #0b0b0c.
st.markdown(
    f"""
<style>
header[data-testid="stHeader"], footer, #MainMenu, .stDeployButton {{ display:none!important }}
html, body, .stApp {{ background:{P['bg']}!important; margin:0; padding:0; overflow:hidden }}
[data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="stMain"] > div, .stMainBlockContainer, .block-container {{
  padding:0!important; margin:0!important; max-width:100%!important; overflow:hidden!important }}
iframe {{ position:fixed!important; top:0!important; left:0!important;
         width:100vw!important; height:100vh!important; border:none!important; z-index:9999!important }}
</style>""",
    unsafe_allow_html=True,
)

components.html(_restyled_html(), height=1000, scrolling=False)
