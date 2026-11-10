"""Tyre performance of a driver (default: Lewis Hamilton) in the latest completed Grand Prix.

Uses the OpenF1 API (https://openf1.org): stints, laps and pit stops of the race session.
"""
import time
from datetime import datetime, timezone
from statistics import mean, median

import requests

BASE_URL = "https://api.openf1.org/v1"
HAMILTON = 44


def get(endpoint, **params):
    # OpenF1 allows max 3 requests/second
    time.sleep(0.4)
    response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_latest_race(year=None):
    year = year or datetime.now(timezone.utc).year
    now = datetime.now(timezone.utc)
    races = get("sessions", session_name="Race", year=year)
    finished = [r for r in races
                if not r.get("is_cancelled") and datetime.fromisoformat(r["date_end"]) < now]
    if not finished:
        raise RuntimeError(f"No completed race found for {year}.")
    return max(finished, key=lambda r: r["date_start"])


def degradation_per_lap(laps):
    """Least-squares slope of lap time vs lap number (seconds lost per lap)."""
    if len(laps) < 3:
        return None
    xs = [lap["lap_number"] for lap in laps]
    ys = [lap["lap_duration"] for lap in laps]
    x_mean, y_mean = mean(xs), mean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom if denom else None


def representative_laps(stint_laps, pit_laps):
    """Drop in/out laps, missing times and slow laps (SC/VSC/traffic: > 107% of stint median)."""
    laps = [lap for lap in stint_laps
            if lap.get("lap_duration")
            and not lap.get("is_pit_out_lap")
            and lap["lap_number"] not in pit_laps]
    if not laps:
        return []
    cutoff = median(lap["lap_duration"] for lap in laps) * 1.07
    return [lap for lap in laps if lap["lap_duration"] <= cutoff]


def fmt_time(seconds):
    if seconds is None:
        return "-"
    minutes, sec = divmod(seconds, 60)
    return f"{int(minutes)}:{sec:06.3f}"


def get_tyre_performance(driver_number=HAMILTON, session_key=None):
    race = get_latest_race() if session_key is None else get("sessions", session_key=session_key)[0]
    session_key = race["session_key"]

    driver = get("drivers", session_key=session_key, driver_number=driver_number)
    stints = get("stints", session_key=session_key, driver_number=driver_number)
    laps = get("laps", session_key=session_key, driver_number=driver_number)
    pits = get("pit", session_key=session_key, driver_number=driver_number)

    pit_laps = {p["lap_number"] for p in pits}
    stint_stats = []
    for stint in sorted(stints, key=lambda s: s["stint_number"]):
        stint_laps = [lap for lap in laps if stint["lap_start"] <= lap["lap_number"] <= stint["lap_end"]]
        clean = representative_laps(stint_laps, pit_laps)
        times = [lap["lap_duration"] for lap in clean]
        n_laps = stint["lap_end"] - stint["lap_start"] + 1
        stint_stats.append({
            "stint": stint["stint_number"],
            "compound": stint["compound"],
            "laps": f'{stint["lap_start"]}-{stint["lap_end"]}',
            "n_laps": n_laps,
            "tyre_age_start": stint["tyre_age_at_start"],
            "tyre_age_end": stint["tyre_age_at_start"] + n_laps,
            "clean_laps": len(clean),
            "best_lap": min(times) if times else None,
            "avg_lap": mean(times) if times else None,
            "deg_per_lap": degradation_per_lap(clean),
            "clean_lap_numbers": {lap["lap_number"] for lap in clean},
        })

    return {
        "race": race,
        "driver": driver[0] if driver else {"full_name": f"#{driver_number}"},
        "stints": stint_stats,
        "pits": sorted(pits, key=lambda p: p["lap_number"]),
        "laps": sorted((lap for lap in laps if lap.get("lap_duration")), key=lambda l: l["lap_number"]),
    }


# Conventional F1 compound colours (validated for separation); marker shape is the
# secondary encoding so compounds stay distinguishable for colour-blind readers.
COMPOUND_STYLE = {
    "SOFT":         {"color": "#e34948", "marker": "o"},
    "MEDIUM":       {"color": "#eda100", "marker": "s"},
    "HARD":         {"color": "#52514e", "marker": "D"},
    "INTERMEDIATE": {"color": "#008300", "marker": "^"},
    "WET":          {"color": "#2a78d6", "marker": "v"},
}
INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def plot_tyre_performance(data, output=None):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    race, driver = data["race"], data["driver"]
    lap_by_number = {lap["lap_number"]: lap["lap_duration"] for lap in data["laps"]}
    clean_times = [lap_by_number[n] for s in data["stints"] for n in s["clean_lap_numbers"]]

    fig, ax = plt.subplots(figsize=(12, 6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    # Zoom the y-axis on representative pace; excluded laps beyond it are clipped to the edge
    y_lo, y_hi = min(clean_times) - 1.5, max(clean_times) + 3
    excluded_x, excluded_y = [], []

    for s in data["stints"]:
        style = COMPOUND_STYLE.get(s["compound"], {"color": INK_MUTED, "marker": "o"})
        start, end = map(int, s["laps"].split("-"))
        clean = sorted(s["clean_lap_numbers"])
        xs = [n for n in clean]
        ys = [lap_by_number[n] for n in clean]
        ax.scatter(xs, ys, s=55, color=style["color"], marker=style["marker"],
                   edgecolor=SURFACE, linewidth=1.5, zorder=3,
                   label=s["compound"].title() if s["compound"].title() not in ax.get_legend_handles_labels()[1] else None)

        # Linear pace trend over clean laps
        if s["deg_per_lap"] is not None and len(xs) >= 3:
            b = mean(ys) - s["deg_per_lap"] * mean(xs)
            ax.plot([xs[0], xs[-1]], [b + s["deg_per_lap"] * xs[0], b + s["deg_per_lap"] * xs[-1]],
                    color=style["color"], linewidth=2, zorder=2)

        for n in range(start, end + 1):
            if n in lap_by_number and n not in s["clean_lap_numbers"]:
                excluded_x.append(n)
                excluded_y.append(min(lap_by_number[n], y_hi - 0.3))

        # Direct stint label just above the plot area (kept inside the figure at the edges)
        deg = f'{s["deg_per_lap"]:+.2f}s/lap' if s["deg_per_lap"] is not None else ""
        last_lap = max(lap_by_number)
        x, ha = (start - 0.5, "left") if start <= 2 else (end + 0.5, "right") if end >= last_lap - 2 \
            else ((start + end) / 2, "center")
        ax.text(x, 1.01, f'Stint {s["stint"]} · {s["compound"].title()}\navg {fmt_time(s["avg_lap"])} · {deg}',
                transform=ax.get_xaxis_transform(), ha=ha, va="bottom", fontsize=9, color=INK)

    ax.scatter(excluded_x, excluded_y, s=24, facecolor="none", edgecolor=INK_MUTED,
               linewidth=1, zorder=2, label="Excluded lap (pit in/out, SC, traffic)")

    for p in data["pits"]:
        ax.axvline(p["lap_number"] + 0.5, color=INK_MUTED, linewidth=1, linestyle=(0, (3, 3)), zorder=1)
        ax.text(p["lap_number"] + 0.5, y_lo + 0.2, f' Pit L{p["lap_number"]} · {p.get("stop_duration") or "-"}s',
                rotation=90, va="bottom", ha="right", fontsize=8, color=INK_MUTED)

    ax.set_ylim(y_lo, y_hi)
    ax.set_xlim(0.5, max(lap_by_number) + 0.5)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_time(v)[:-2]))
    ax.set_xlabel("Lap", color=INK_MUTED)
    ax.set_ylabel("Lap time", color=INK_MUTED)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, length=0)

    ax.set_title(f'{driver.get("full_name")} - tyre performance, {race["country_name"]} GP {race["year"]}',
                 loc="left", fontsize=14, color=INK, pad=40)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.09), ncol=4, frameon=False,
              fontsize=9, labelcolor=INK, handletextpad=0.3)
    ax.text(1, -0.09, "Excluded laps beyond the top edge are clipped to it", transform=ax.transAxes,
            ha="right", va="top", fontsize=8, color=INK_MUTED)
    fig.tight_layout()

    if output:
        fig.savefig(output, dpi=150, facecolor=SURFACE)
        print(f"Saved chart to {output}")
    else:
        plt.show()
    return fig


def print_report(data):
    race, driver = data["race"], data["driver"]
    print(f'\n{driver.get("full_name")} ({driver.get("team_name", "")}) - '
          f'{race["country_name"]} GP, {race["circuit_short_name"]} ({race["date_start"][:10]})\n')

    header = f'{"Stint":<6}{"Compound":<14}{"Laps":<8}{"#":>3}{"Age":>9}{"Clean":>7}{"Best":>11}{"Avg":>11}{"Deg/lap":>10}'
    print(header)
    print("-" * len(header))
    for s in data["stints"]:
        deg = f'{s["deg_per_lap"]:+.3f}s' if s["deg_per_lap"] is not None else "-"
        age = f'{s["tyre_age_start"]}->{s["tyre_age_end"]}'
        print(f'{s["stint"]:<6}{s["compound"]:<14}{s["laps"]:<8}{s["n_laps"]:>3}{age:>9}'
              f'{s["clean_laps"]:>7}{fmt_time(s["best_lap"]):>11}{fmt_time(s["avg_lap"]):>11}{deg:>10}')

    print("\nPit stops:")
    for p in data["pits"]:
        print(f'  Lap {p["lap_number"]:>2}: stationary {p.get("stop_duration") or "-"}s, '
              f'pit lane {p.get("pit_duration") or "-"}s')
    print("\nClean laps exclude in/out laps and laps > 107% of the stint median (SC/VSC, traffic).")
    print("Deg/lap is the linear lap-time trend over clean laps (includes fuel burn-off).\n")


LECLERC = 16
DRIVER_COLORS = ["#2a78d6", "#eb6834"]  # categorical slots 1-2 (both drivers are Ferrari, so no team colour)
SPEED_FIELDS = [
    ("i1_speed", "Intermediate 1"),
    ("i2_speed", "Intermediate 2"),
    ("st_speed", "Speed trap"),
]


def get_speed_comparison(driver_a=HAMILTON, driver_b=LECLERC, session_key=None):
    race = get_latest_race() if session_key is None else get("sessions", session_key=session_key)[0]
    drivers = []
    for number in (driver_a, driver_b):
        info = get("drivers", session_key=race["session_key"], driver_number=number)
        laps = get("laps", session_key=race["session_key"], driver_number=number)
        pits = get("pit", session_key=race["session_key"], driver_number=number)
        drivers.append({
            "number": number,
            "name": info[0]["last_name"].title() if info else f"#{number}",
            "laps": {lap["lap_number"]: lap for lap in laps},
            "pit_laps": sorted(p["lap_number"] for p in pits),
        })
    return {"race": race, "drivers": drivers}


def print_speed_report(data):
    print("Average speeds over the race (km/h, laps with a reading):")
    print(f'  {"":<16}' + "".join(f'{d["name"]:>12}' for d in data["drivers"]))
    for field, label in SPEED_FIELDS:
        row = []
        for d in data["drivers"]:
            values = [lap[field] for lap in d["laps"].values() if lap.get(field)]
            row.append(f"{mean(values):>12.1f}" if values else f'{"-":>12}')
        print(f"  {label:<16}" + "".join(row))
    a, b = data["drivers"]
    common = [n for n in a["laps"] if n in b["laps"]
              and a["laps"][n].get("lap_duration") and b["laps"][n].get("lap_duration")]
    faster = sum(1 for n in common if a["laps"][n]["lap_duration"] < b["laps"][n]["lap_duration"])
    print(f'\n  {a["name"]} was faster on {faster} of {len(common)} common laps.\n')


def style_axis(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, length=0)


def plot_speed_comparison(data, output=None):
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    race, drivers = data["race"], data["drivers"]
    # Small multiples: one panel per measurement point + lap-time gap, all sharing the lap axis
    fig, axes = plt.subplots(len(SPEED_FIELDS) + 1, 1, figsize=(12, 11), sharex=True,
                             facecolor=SURFACE, gridspec_kw={"hspace": 0.35})

    for ax, (field, label) in zip(axes, SPEED_FIELDS):
        style_axis(ax)
        for d, color in zip(drivers, DRIVER_COLORS):
            points = [(n, lap[field]) for n, lap in sorted(d["laps"].items()) if lap.get(field)]
            xs, ys = zip(*points) if points else ([], [])
            ax.plot(xs, ys, color=color, linewidth=2, zorder=3)
            ax.scatter(xs, ys, s=16, color=color, edgecolor=SURFACE, linewidth=1, zorder=4)
        ax.set_title(f"{label} speed (km/h)", loc="left", fontsize=10, color=INK)

    # Lap-time gap: positive = driver A faster on that lap
    gap_ax = axes[-1]
    style_axis(gap_ax)
    a, b = drivers
    common = sorted(n for n in a["laps"] if n in b["laps"]
                    and a["laps"][n].get("lap_duration") and b["laps"][n].get("lap_duration"))
    gaps = [b["laps"][n]["lap_duration"] - a["laps"][n]["lap_duration"] for n in common]
    gap_ax.bar(common, gaps, width=0.8, color=[DRIVER_COLORS[0] if g > 0 else DRIVER_COLORS[1] for g in gaps],
               edgecolor=SURFACE, linewidth=1, zorder=3)
    gap_ax.axhline(0, color=INK_MUTED, linewidth=1, zorder=2)
    gap_ax.set_ylim(-3, 3)  # pit/SC laps can be huge; clip to keep racing laps readable
    gap_ax.set_title(f'Lap-time gap (s) - above 0: {a["name"]} faster, below 0: {b["name"]} faster '
                     f'(clipped at ±3s)', loc="left", fontsize=10, color=INK)
    gap_ax.set_xlabel("Lap", color=INK_MUTED)

    # Pit stops of each driver on every panel
    for ax in axes:
        for d, color in zip(drivers, DRIVER_COLORS):
            for lap in d["pit_laps"]:
                ax.axvline(lap + 0.5, color=color, linewidth=1, linestyle=(0, (3, 3)), zorder=1)

    handles = [Line2D([], [], color=c, linewidth=2, marker="o", markersize=5, label=d["name"])
               for d, c in zip(drivers, DRIVER_COLORS)]
    handles.append(Line2D([], [], color=INK_MUTED, linewidth=1, linestyle=(0, (3, 3)), label="Pit stop (driver colour)"))
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.07, 0.945), ncol=3,
               frameon=False, fontsize=9, labelcolor=INK)
    fig.suptitle(f'{a["name"]} vs {b["name"]} - speed per lap, {race["country_name"]} GP {race["year"]}',
                 x=0.07, ha="left", fontsize=14, color=INK, y=0.98)

    if output:
        fig.savefig(output, dpi=150, facecolor=SURFACE, bbox_inches="tight")
        print(f"Saved chart to {output}")
    else:
        plt.show()
    return fig


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Pass an output path (e.g. `python src/brazil.py tyres.png`) to save the charts instead of
    # opening windows; the speed chart is saved next to it as `<name>_speed.png`
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    data = get_tyre_performance(HAMILTON)
    print_report(data)
    plot_tyre_performance(data, output=output)

    speed = get_speed_comparison(HAMILTON, LECLERC)
    print_speed_report(speed)
    plot_speed_comparison(speed, output=output.with_name(f"{output.stem}_speed{output.suffix}") if output else None)
