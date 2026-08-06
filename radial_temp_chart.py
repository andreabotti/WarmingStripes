"""
radial_temp_chart.py -- poster-style radial daily temperature chart.

One wedge per day, arranged clockwise from the top, running from the day's
min to its max temperature and filled with a gradient that tracks the actual
temperature along the band. Weekends get a pale backing band, months are
separated by radial rules, and °C rings are labelled up the 12 o'clock spoke.

Modelled on Julian Hoffmann Anton's "temperature & sunshine" posters, minus
the sunshine layer.

    from radial_temp_chart import radial_temperature_chart
    fig = radial_temperature_chart(df, city="London")   # df: date, tmin, tmax
    fig.savefig("london.png", dpi=200)

In Streamlit:  st.pyplot(fig, use_container_width=True)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

__all__ = ["radial_temperature_chart", "TEMP_CMAP"]

# ── look & feel ───────────────────────────────────────────────────────────────
BG          = "#e3f0fb"   # pale blue page
INK         = "#2f3b45"   # body text
MUTED       = "#8a98a6"   # ticks, rules, secondary text
WEEKEND     = "#ffffff"   # weekend backing band
SERIF       = ["Georgia", "Iowan Old Style", "Times New Roman", "DejaVu Serif"]
SANS        = ["Arial", "Helvetica Neue", "DejaVu Sans"]

# warm ramp: pale gold -> orange -> deep red (the poster's temperature scale)
TEMP_CMAP = LinearSegmentedColormap.from_list(
    "poster_warm",
    ["#ffe98a", "#fdd05a", "#f9a63f", "#f47b33", "#e8492a", "#c0161d", "#7d0d18"],
)

N_SEG      = 24     # radial slices per day -> gradient smoothness
HOLE       = 0.42   # inner hole as a fraction of the outer radius
BAR_FRAC   = 0.78   # wedge width as a fraction of one day's angular slot


# ── helpers ───────────────────────────────────────────────────────────────────
def _prepare(data: pd.DataFrame, date="date", tmin="tmin", tmax="tmax") -> pd.DataFrame:
    df = data[[date, tmin, tmax]].copy()
    df.columns = ["date", "tmin", "tmax"]
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna().sort_values("date").reset_index(drop=True)
    if df.empty:
        raise ValueError("no rows with both tmin and tmax")
    return df


def _nice_ticks(lo: float, hi: float, step: float = 5.0) -> np.ndarray:
    """Ring values at `step` intervals, skipping the innermost one so the
    labels don't crowd the hub."""
    first = np.ceil(lo / step) * step
    ticks = np.arange(first, hi + 1e-9, step)
    return ticks[ticks > lo + step * 0.4]


# ── main entry point ──────────────────────────────────────────────────────────
def radial_temperature_chart(
    data: pd.DataFrame,
    city: str = "",
    *,
    date_col: str = "date",
    tmin_col: str = "tmin",
    tmax_col: str = "tmax",
    title: str | None = None,
    subtitle: str | None = None,
    footer: str | None = "Weather data: Open-Meteo (CC BY 4.0)",
    label_every: int = 7,
    vmin: float | None = None,
    vmax: float | None = None,
    figsize: tuple[float, float] = (8.0, 10.0),
    dpi: int = 120,
    show_weekends: bool = True,
    legend: bool = True,
):
    """Draw the radial chart and return the matplotlib Figure.

    `data` needs one row per day with a date and that day's min/max
    temperature. `vmin`/`vmax` pin the colour scale (pass the same values
    across several charts to make them comparable); by default they follow
    the data. `label_every` sets the date-label spacing in days.
    """
    df = _prepare(data, date_col, tmin_col, tmax_col)
    n = len(df)

    # --- scales -------------------------------------------------------------
    t_lo = float(np.floor(df.tmin.min() / 5) * 5)
    t_hi = float(np.ceil(df.tmax.max() / 5) * 5)
    norm = Normalize(
        vmin=df.tmin.min() if vmin is None else vmin,
        vmax=df.tmax.max() if vmax is None else vmax,
    )
    # temperature -> radius, with a hole punched in the middle
    span   = t_hi - t_lo
    origin = t_lo - span * HOLE / (1 - HOLE)

    # day i occupies the angular slot [i, i+1) / n, clockwise from 12 o'clock
    slot   = 2 * np.pi / n
    theta  = (np.arange(n) + 0.5) * slot
    width  = slot * BAR_FRAC

    # --- canvas -------------------------------------------------------------
    fig = plt.figure(figsize=figsize, dpi=dpi, facecolor=BG)
    ax = fig.add_axes([0.15, 0.20, 0.70, 0.58], projection="polar", facecolor=BG)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rorigin(origin)
    ax.set_ylim(t_lo, t_hi)
    # set_visible(False) doesn't stick on polar spines (the hole's 'inner'
    # spine gets re-enabled on draw) -- clear the colour instead.
    for spine in ax.spines.values():
        spine.set_color("none")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)

    # --- weekend backing bands ---------------------------------------------
    if show_weekends:
        we = df.date.dt.dayofweek >= 5
        if we.any():
            ax.bar(
                theta[we.values], height=t_hi - origin, bottom=origin,
                width=slot, color=WEEKEND, alpha=0.85, linewidth=0, zorder=1,
            )

    # --- rings --------------------------------------------------------------
    ring_theta = np.linspace(0, 2 * np.pi, 361)
    ticks = _nice_ticks(t_lo, t_hi)
    for v in ticks:
        ax.plot(ring_theta, np.full_like(ring_theta, v),
                color=MUTED, lw=0.5, alpha=0.55, zorder=2)

    # --- the day wedges -----------------------------------------------------
    lo = df.tmin.to_numpy()
    hi = df.tmax.to_numpy()
    for seg in range(N_SEG):
        f0, f1 = seg / N_SEG, (seg + 1) / N_SEG
        base = lo + f0 * (hi - lo)
        top  = lo + f1 * (hi - lo)
        ax.bar(
            theta, height=np.maximum(top - base, 1e-9), bottom=base, width=width,
            color=TEMP_CMAP(norm((base + top) / 2)), linewidth=0, zorder=3,
        )

    # ring labels sit on top of the bars, up the 12 o'clock spoke
    for v in ticks:
        ax.text(np.pi / 200, v, f"{v:.0f}°C", ha="center", va="center",
                fontsize=6.5, color=MUTED, family=SANS, zorder=6,
                bbox=dict(boxstyle="round,pad=0.12", fc=BG, ec="none", alpha=0.55))

    # --- month rules & labels ----------------------------------------------
    starts = np.flatnonzero(df.date.dt.day.to_numpy() == 1)
    if len(df) and df.date.iloc[0].day != 1:
        starts = np.insert(starts, 0, 0)
    for i in starts:
        a = i * slot
        ax.plot([a, a], [t_lo, t_hi + span * 0.16],
                color=MUTED, lw=0.6, alpha=0.7, zorder=2, clip_on=False)
        ax.text(a, t_hi + span * 0.20, df.date.iloc[i].strftime("%b").upper(),
                ha="center", va="center", fontsize=7.5, color=MUTED,
                family=SANS, fontweight="bold", zorder=6)

    # --- date labels --------------------------------------------------------
    for i in range(0, n, label_every):
        a = (i + 0.5) * slot
        ax.text(a, t_hi + span * 0.34, df.date.iloc[i].strftime("%d %b"),
                ha="center", va="center", fontsize=6.5, color=MUTED,
                family=SANS, zorder=6)

    # --- hub ----------------------------------------------------------------
    ax.fill_between(ring_theta, origin, t_lo, color="#ffffff", alpha=0.5,
                    linewidth=0, zorder=4)
    if city:
        ax.text(0, origin, city, ha="center", va="center", transform=ax.transData,
                fontsize=17, color=INK, family=SERIF, zorder=7)

    # --- titles -------------------------------------------------------------
    d0, d1 = df.date.iloc[0], df.date.iloc[-1]
    fig.text(0.5, 0.945, title or (f"{city} — daily temperature" if city
                                   else "Daily temperature"),
             ha="center", va="center", fontsize=23, color="#1d262e", family=SERIF)
    fig.text(0.5, 0.905,
             subtitle if subtitle is not None else
             f"{d0:%d %b %Y} – {d1:%d %b %Y} · {n} days",
             ha="center", va="center", fontsize=11, color=MUTED, family=SANS)

    # --- legend -------------------------------------------------------------
    if legend:
        cax = fig.add_axes([0.30, 0.105, 0.13, 0.016])
        cax.imshow(np.linspace(0, 1, 256).reshape(1, -1), aspect="auto",
                   cmap=TEMP_CMAP, extent=(0, 1, 0, 1))
        cax.set_xticks([]); cax.set_yticks([])
        for s in cax.spines.values():
            s.set_visible(False)
        fig.text(0.445, 0.113, "Min–max temperature", ha="left", va="center",
                 fontsize=9, color=INK, family=SANS)
        if show_weekends:
            fig.legend(
                handles=[Patch(facecolor=WEEKEND, edgecolor="none", label="Weekend")],
                loc="center", bbox_to_anchor=(0.76, 0.113), frameon=False,
                handlelength=1.6, handleheight=1.0,
                prop={"family": SANS[0], "size": 9}, labelcolor=INK,
            )

    if footer:
        fig.text(0.5, 0.045, footer, ha="center", va="center",
                 fontsize=8.5, color=MUTED, family=SANS)

    return fig


# ── demo ──────────────────────────────────────────────────────────────────────
def _sample(start="2026-05-01", days=91, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=days, freq="D")
    seasonal = np.sin(np.linspace(0, 1, days) * np.pi) ** 0.6
    tmax = 15 + 12 * seasonal + rng.normal(0, 2.0, days)
    tmin = 8 + 7 * seasonal + rng.normal(0, 1.5, days)
    return pd.DataFrame({"date": dates, "tmin": np.minimum(tmin, tmax - 2),
                         "tmax": tmax})


if __name__ == "__main__":
    fig = radial_temperature_chart(_sample(), city="London")
    fig.savefig("radial_temp_chart_demo.png", dpi=200, facecolor=fig.get_facecolor())
    print("wrote radial_temp_chart_demo.png")
