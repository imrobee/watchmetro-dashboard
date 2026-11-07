# -*- coding: utf-8 -*-
"""WatchMetro: Metro Manila Accidents Dashboard.

Full-featured build. Every accident in the dataset is mapped, with complete
popups (type, location, city, date, time, vehicles involved).

Run locally:   python app.py            -> http://127.0.0.1:8050
Gunicorn:      gunicorn app:app
Vercel:        zero-config Flask entrypoint; `app` below is the WSGI server.
"""

import re
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import folium
import pandas as pd
import plotly.graph_objects as go
from branca.element import Element, MacroElement
from dash import ALL, Dash, Input, Output, State, clientside_callback, ctx, dcc, html
from dash.exceptions import PreventUpdate
from folium.plugins import FastMarkerCluster
from jinja2 import Template

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "dataset_cleaned.csv"

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
TIME_PERIODS = ["All Day", "Morning", "Afternoon", "Evening"]
TIME_RANGES = {
    "Morning": list(range(6, 12)),
    "Afternoon": list(range(12, 18)),
    "Evening": list(range(18, 24)) + list(range(0, 6)),
    "All Day": list(range(24)),
}
TIME_HINTS = {
    "All Day": "All hours",
    "Morning": "6 AM to 12 PM",
    "Afternoon": "12 PM to 6 PM",
    "Evening": "6 PM to 6 AM",
}
VEHICLE_ALIASES = {"BU": "BUS", "MC": "MOTORCYCLE", "PUJ": "JEEP", "AUV": "CAR", "SUV": "CAR"}

FONT_STACK = '-apple-system, system-ui, "Segoe UI", Roboto, sans-serif'


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def normalize_type(raw):
    """Fold the dataset's typo variants ('VEHCICULAR ACCIDENT', trailing spaces) into three types."""
    t = re.sub(r"\s+", " ", str(raw or "")).strip().upper()
    if "MULTIPLE" in t:
        return "Multiple collision"
    if "SELF" in t:
        return "Self accident"
    if t.startswith("VEH") or "ACCIDENT" in t:
        return "Vehicular accident"
    return t.capitalize() or "Unknown"


def clean_vehicle_name(name):
    """Normalize one vehicle mention: drop counts, singularize, and map abbreviations."""
    if not isinstance(name, str):
        return None
    name = re.sub(r"[^A-Z0-9\s]", "", name.strip().upper())
    name = re.sub(r"\b\d+\s*", "", name).strip()
    name = re.sub(r"\s+", " ", name)
    if not name or name in ("NAN", "NONE", "NA"):
        return None
    if name.endswith("ES") and name[:-2] in VEHICLE_ALIASES.values() | VEHICLE_ALIASES.keys():
        name = name[:-2]                       # BUSES -> BUS
    elif name.endswith("S") and not name.endswith("SS") and name != "BUS":
        name = name[:-1]                       # CARS -> CAR, MCS -> MC (but EXPRESS stays)
    name = name.replace("PICK UP", "PICKUP")
    return VEHICLE_ALIASES.get(name, name)


def hour_label(hour):
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour % 12 or 12} {suffix}"


def load_data():
    cols = ["Date", "Time", "City", "Location", "Latitude", "Longitude", "Type", "Involved"]
    df = pd.read_csv(DATA_FILE, usecols=cols)
    date = pd.to_datetime(df["Date"], errors="coerce")
    time = pd.to_datetime(df["Time"], format="%I:%M %p", errors="coerce")

    df["Hour"] = time.dt.hour.fillna(-1).astype(int)
    df["Month_Name"] = date.dt.month_name().fillna("Unknown")
    df["Date_Label"] = date.dt.strftime("%d %b %Y").fillna(df["Date"].astype(str))
    df["Time_Period"] = df["Hour"].map(
        lambda h: next((p for p in ("Morning", "Afternoon", "Evening") if h in TIME_RANGES[p]), "All Day")
    )
    df["Type_Label"] = df["Type"].map(normalize_type)
    df["Involved"] = (df["Involved"].fillna("").astype(str).str.upper()
                      .str.replace(r"[^A-Z0-9\s,]", "", regex=True).str.strip())
    for col in ("City", "Location", "Time"):
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


df = load_data()
CITIES = sorted(c for c in df["City"].unique() if c)
DATE_MIN = pd.to_datetime(df["Date"], errors="coerce").min()
DATE_MAX = pd.to_datetime(df["Date"], errors="coerce").max()
print(f"Loaded {len(df):,} records from {DATA_FILE.name}")


def filter_df(time_filter, month, city, use_month=True):
    mask = pd.Series(True, index=df.index)
    if use_month and month != "All Months":
        mask &= df["Month_Name"] == month
    if city != "All Cities":
        mask &= df["City"] == city
    if time_filter != "All Day":
        mask &= df["Time_Period"] == time_filter
    return df[mask]


# --------------------------------------------------------------------------- #
# Map (Folium + FastMarkerCluster: every point, built in the browser)
# --------------------------------------------------------------------------- #
MARKER_CALLBACK = """
(function () {
  var icon = L.AwesomeMarkers.icon({icon: 'exclamation-triangle', prefix: 'fa',
                                    markerColor: 'red', iconColor: 'white'});
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
    });
  }
  function row(label, value) {
    return value ? '<dt>' + label + '</dt><dd>' + esc(value) + '</dd>' : '';
  }
  return function (r) {
    // r = [lat, lon, type, location, city, date, time, involved]
    var marker = L.marker(new L.LatLng(r[0], r[1]), {icon: icon, title: r[2]});
    marker.bindPopup(
      '<div class="wm-pop"><p class="wm-pop-type">' + esc(r[2]) + '</p><dl>' +
      row('Location', r[3]) + row('City', r[4]) +
      row('When', [r[5], r[6]].filter(Boolean).join(', ')) +
      row('Involved', r[7]) + '</dl></div>', {maxWidth: 280});
    return marker;
  };
})()
"""

MAP_CSS = """
<style>
  html, body { font-family: -apple-system, system-ui, "Segoe UI", Roboto, sans-serif; }
  .leaflet-container { font: inherit; background: #e9ebe8; }
  html[data-theme="dark"] .leaflet-container { background: #1d2024; }
  .wm-pop { font-size: 13px; line-height: 1.4; color: #16191d; min-width: 200px; }
  .wm-pop-type { margin: 0 0 8px; font-size: 15px; font-weight: 650; }
  .wm-pop dl { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; }
  .wm-pop dt { color: #5b6168; }
  .wm-pop dd { margin: 0; }
  html[data-theme="dark"] .leaflet-popup-content-wrapper,
  html[data-theme="dark"] .leaflet-popup-tip { background: #23272c; color: #eef0f1; }
  html[data-theme="dark"] .wm-pop { color: #eef0f1; }
  html[data-theme="dark"] .wm-pop dt { color: #a9afb5; }
  html[data-theme="dark"] .leaflet-popup-close-button { color: #a9afb5; }
  /* Dark basemap: OpenStreetMap tiles inverted (no API key needed). Markers are untouched. */
  html[data-theme="dark"] .leaflet-tile-pane {
    filter: invert(1) hue-rotate(180deg) brightness(.92) contrast(.88) saturate(.5);
  }
  html[data-theme="dark"] .leaflet-control-zoom a,
  html[data-theme="dark"] .leaflet-control-attribution { background: #23272c; color: #d6d9dc; }
  html[data-theme="dark"] .leaflet-control-attribution a { color: #8fb8ee; }
  html[data-theme="dark"] .leaflet-control-scale-line { background: rgba(35,39,44,.8); color: #d6d9dc; border-color: #8b9198; }
  /* Cluster size: one blue ramp (sequential), instead of the default traffic-light colors */
  .leaflet-container .marker-cluster div { font: 650 12px/30px -apple-system, system-ui, "Segoe UI", Roboto, sans-serif; color: #fff; }
  .leaflet-container .marker-cluster-small  { background-color: rgba(57, 135, 229, .35); }
  .leaflet-container .marker-cluster-small div  { background-color: #3987e5; }
  .leaflet-container .marker-cluster-medium { background-color: rgba(37, 106, 191, .38); }
  .leaflet-container .marker-cluster-medium div { background-color: #256abf; }
  .leaflet-container .marker-cluster-large  { background-color: rgba(16, 66, 129, .40); }
  .leaflet-container .marker-cluster-large div  { background-color: #104281; }
  .wm-empty { background: #fff; color: #16191d; padding: 10px 14px; border-radius: 8px;
              font-size: 14px; box-shadow: 0 1px 4px rgba(0,0,0,.2); }
  html[data-theme="dark"] .wm-empty { background: #23272c; color: #eef0f1; }
</style>
"""


class ThemedTiles(MacroElement):
    """Adds the OpenStreetMap basemap and follows the parent page's data-theme attribute.

    The map lives in a srcdoc iframe (same origin as the dashboard), so it can watch the
    parent <html> element and restyle instantly without a server round trip.
    """

    _template = Template("""
{% macro script(this, kwargs) %}
(function () {
  var map = {{ this._parent.get_name() }};
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
  }).addTo(map);
  function apply() {
    var t = 'light';
    try { t = parent.document.documentElement.getAttribute('data-theme') || 'light'; } catch (e) {}
    document.documentElement.setAttribute('data-theme', t);  // CSS darkens the tiles
  }
  apply();
  try {
    new MutationObserver(apply).observe(parent.document.documentElement,
                                        {attributes: true, attributeFilter: ['data-theme']});
  } catch (e) {}
  {% if this.empty_message %}
  var Empty = L.Control.extend({onAdd: function () {
    var d = L.DomUtil.create('div', 'wm-empty'); d.textContent = {{ this.empty_message|tojson }}; return d;
  }});
  new Empty({position: 'topright'}).addTo(map);
  {% endif %}
})();
{% endmacro %}
""")

    def __init__(self, empty_message=None):
        super().__init__()
        self._name = "ThemedTiles"
        self.empty_message = empty_message


@lru_cache(maxsize=64)
def build_map_html(time_filter, month, city):
    data = filter_df(time_filter, month, city).dropna(subset=["Latitude", "Longitude"])
    if data.empty:
        m = folium.Map(location=[14.58, 121.03], zoom_start=11, tiles=None, control_scale=True, maxZoom=19, minZoom=9)
        ThemedTiles("No accidents match these filters. Try another city, month or time of day.").add_to(m)
    else:
        m = folium.Map(location=[float(data["Latitude"].mean()), float(data["Longitude"].mean())],
                       zoom_start=11, tiles=None, control_scale=True, maxZoom=19, minZoom=9)
        rows = [
            [round(float(r.Latitude), 5), round(float(r.Longitude), 5), r.Type_Label,
             r.Location, r.City, r.Date_Label, r.Time, r.Involved]
            for r in data.itertuples(index=False)
        ]
        FastMarkerCluster(rows, callback=MARKER_CALLBACK,
                          options={"showCoverageOnHover": True, "maxClusterRadius": 60,
                                   "polygonOptions": {"color": "#2a78d6", "weight": 2, "opacity": 0.9,
                                                      "fillColor": "#2a78d6", "fillOpacity": 0.12}}).add_to(m)
        ThemedTiles().add_to(m)
        if len(data) > 1:
            m.fit_bounds([[float(data["Latitude"].min()), float(data["Longitude"].min())],
                          [float(data["Latitude"].max()), float(data["Longitude"].max())]],
                         padding=(20, 20))
    m.get_root().header.add_child(Element(MAP_CSS))
    buffer = BytesIO()
    m.save(buffer, close_file=False)
    return buffer.getvalue().decode("utf-8"), len(data)


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
CHART_THEME = {
    "light": {"ink": "#16191d", "ink2": "#545a61", "muted": "#7a8087", "grid": "#e8eae7",
              "axis": "#c9cdc8", "data": "#2a78d6", "soft": "#b7d3f6", "other": "#b4b9be",
              "surface": "#ffffff", "hover": "#ffffff"},
    "dark": {"ink": "#eef0f1", "ink2": "#b6bbc0", "muted": "#8b9198", "grid": "#2b2f34",
             "axis": "#3a3f45", "data": "#3987e5", "soft": "#1c4a80", "other": "#5a6066",
             "surface": "#1a1d21", "hover": "#23272c"},
}
GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


def base_layout(fig, c, height=340):
    fig.update_layout(
        height=height, margin=dict(l=8, r=24, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_STACK, size=13, color=c["ink2"]),
        showlegend=False, bargap=0.42,
        hoverlabel=dict(bgcolor=c["hover"], bordercolor=c["axis"],
                        font=dict(family=FONT_STACK, size=13, color=c["ink"])),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=c["axis"], tickcolor=c["axis"],
                     tickfont=dict(color=c["muted"]), fixedrange=True)
    fig.update_yaxes(gridcolor=c["grid"], gridwidth=1, zeroline=False, tickfont=dict(color=c["muted"]),
                     fixedrange=True, separatethousands=True)
    return fig


def empty_figure(c, message="No accidents match these filters."):
    fig = base_layout(go.Figure(), c)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                       font=dict(size=14, color=c["ink2"]))
    return fig


def vehicle_label(name):
    return name.title().replace("Uv ", "UV ")


def vehicle_chart(data, c):
    """Returns (figure, footnote listing what 'Others' contains)."""
    vehicles = data["Involved"].str.split(r"\s+AND\s+|\s*,\s*").explode().map(clean_vehicle_name).dropna()
    if vehicles.empty:
        return empty_figure(c), ""
    counts = vehicles.value_counts()
    share = counts / counts.sum()
    shown = counts[share >= 0.02]
    rest = counts[share < 0.02]
    names = [vehicle_label(n) for n in shown.index]
    values = shown.tolist()
    colors = [c["data"]] * len(values)
    note = ""
    if len(rest):
        names.append("Others*")
        values.append(int(rest.sum()))
        colors.append(c["other"])
        top = [vehicle_label(n) for n in rest.index[:6]]
        listed = ", ".join(top[:-1]) + (" and " + top[-1] if len(top) > 1 else top[0])
        more = len(rest) - len(top)
        note = f"* Others includes {listed}" + (f", plus {more:,} less common types" if more > 0 else "") + \
               ". Each is under 2% of all vehicles involved."

    fig = go.Figure(go.Bar(
        x=values, y=names, orientation="h", marker=dict(color=colors, cornerradius=4),
        text=[f"{v:,}" for v in values], textposition="outside", cliponaxis=False,
        textfont=dict(color=c["ink2"]),
        hovertemplate="%{y}: %{x:,} involvements<extra></extra>",
    ))
    base_layout(fig, c)  # same height as the monthly chart so the two plots line up
    fig.update_layout(margin=dict(r=56))  # room for the value at each bar tip
    fig.update_xaxes(visible=False)
    fig.update_yaxes(showgrid=False, autorange="reversed", tickfont=dict(color=c["ink2"]), ticksuffix="  ")
    return fig, note


def monthly_chart(data, month, c):
    counts = data["Month_Name"].value_counts().reindex(MONTHS, fill_value=0)
    if counts.sum() == 0:
        return empty_figure(c)
    colors = [c["data"] if month in ("All Months", m) else c["soft"] for m in MONTHS]
    fig = go.Figure(go.Bar(
        x=[m[:3] for m in MONTHS], y=counts.tolist(), customdata=MONTHS,
        marker=dict(color=colors, cornerradius=4),
        hovertemplate="%{customdata}: %{y:,} accidents<extra></extra>",
    ))
    base_layout(fig, c)
    return fig


def hourly_chart(data, time_filter, c):
    hours = TIME_RANGES[time_filter]
    counts = data["Hour"].value_counts()
    values = [int(counts.get(h, 0)) for h in hours]
    if sum(values) == 0:
        return empty_figure(c)
    fig = go.Figure(go.Scatter(
        x=[hour_label(h) for h in hours], y=values, mode="lines+markers",
        line=dict(color=c["data"], width=2, shape="spline", smoothing=0.4),
        marker=dict(size=8, color=c["data"], line=dict(width=2, color=c["surface"])),
        fill="tozeroy", fillcolor="rgba(42,120,214,0.10)" if c is CHART_THEME["light"] else "rgba(57,135,229,0.14)",
        hovertemplate="%{x}: %{y:,} accidents<extra></extra>",
    ))
    base_layout(fig, c)
    fig.update_layout(hovermode="x")
    fig.update_xaxes(showspikes=True, spikemode="across", spikethickness=1, spikecolor=c["axis"],
                     spikedash="solid")
    return fig


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
dash_app = Dash(__name__, title="WatchMetro: Metro Manila Accidents Dashboard",
                update_title=None, assets_folder=str(BASE_DIR / "assets"))
app = dash_app.server  # WSGI entrypoint for Vercel and gunicorn


def spinner(text):
    return html.Div([html.Div(className="spinner"), html.P(text, className="spinner-text")],
                    className="spinner-wrap", role="status")


def loading(children, text, target):
    return dcc.Loading(children, custom_spinner=spinner(text), delay_show=150,
                       overlay_style={"visibility": "visible", "opacity": 0.35, "filter": "blur(1px)"},
                       target_components=target, parent_className="loading-parent")


def card_head(title, extra=None):
    return html.Div([html.H2(title, className="card-title"), extra], className="card-head")


period_text = f"{DATE_MIN:%B %Y} to {DATE_MAX:%B %Y}" if pd.notna(DATE_MIN) else "2018 to 2020"

dash_app.layout = html.Div([
    html.Header([
        html.Div([
            html.H1("WatchMetro", className="title"),
            html.P(f"Traffic accidents reported by the MMDA across Metro Manila, {period_text}.",
                   className="subtitle"),
        ]),
        html.Button(html.Span(className="theme-icon", **{"aria-hidden": "true"}),
                    id="theme-toggle", n_clicks=0, className="theme-toggle",
                    title="Switch theme", **{"aria-label": "Switch to dark mode"}),
    ], className="header"),

    html.Main([
        html.Section([
            html.Div([
                html.Span("Time of day", className="label", id="time-label"),
                html.Div([
                    html.Button(p, id={"type": "time-btn", "index": p}, n_clicks=0,
                                className="seg active" if p == "All Day" else "seg",
                                title=TIME_HINTS[p])
                    for p in TIME_PERIODS
                ], className="segmented", role="group", **{"aria-labelledby": "time-label"}),
            ], className="field field-time"),
            html.Div([
                html.Label("Month", htmlFor="month-dropdown", className="label"),
                dcc.Dropdown(id="month-dropdown", value="All Months", clearable=False, searchable=False,
                             options=[{"label": "All months", "value": "All Months"}]
                             + [{"label": m, "value": m} for m in MONTHS]),
            ], className="field"),
            html.Div([
                html.Label("City", htmlFor="city-dropdown", className="label"),
                dcc.Dropdown(id="city-dropdown", value="All Cities", clearable=False,
                             options=[{"label": "All cities", "value": "All Cities"}]
                             + [{"label": c, "value": c} for c in CITIES]),
            ], className="field"),
            html.Div([
                html.Button("Apply filters", id="apply-filters-btn", n_clicks=0, className="apply"),
                html.Button(html.Span(className="reset-icon", **{"aria-hidden": "true"}),
                            id="reset-filters-btn", n_clicks=0, className="reset",
                            title="Reset filters", **{"aria-label": "Reset filters"}),
            ], className="field field-apply"),
        ], className="card controls", **{"aria-label": "Filters"}),

        html.Section([
            card_head("Accident locations", html.P(id="map-count", className="count")),
            loading(html.Iframe(id="leaflet-map", className="map-frame", title="Map of accident locations"),
                    "Loading map", {"leaflet-map": "srcDoc"}),
        ], className="card map-card"),

        html.Div([
            html.Section([
                card_head("Vehicles involved"),
                loading(dcc.Graph(id="vehicle-bar-chart", config=GRAPH_CONFIG), "Loading chart",
                        {"vehicle-bar-chart": "figure"}),
                html.P(id="vehicle-note", className="card-note"),
            ], className="card chart-card"),
            html.Section([
                card_head("Accidents by month"),
                loading(dcc.Graph(id="monthly-accidents-chart", config=GRAPH_CONFIG), "Loading chart",
                        {"monthly-accidents-chart": "figure"}),
            ], className="card chart-card"),
        ], className="row-2"),

        html.Section([
            card_head("Accidents by hour of day"),
            loading(dcc.Graph(id="hourly-accidents-chart", config=GRAPH_CONFIG), "Loading chart",
                    {"hourly-accidents-chart": "figure"}),
        ], className="card chart-card"),
    ], className="grid"),

    html.Footer([
        html.P(["Data: MMDA traffic incident reports compiled by Panji Brotoisworo, ",
                html.A("available on Kaggle", href="https://www.kaggle.com/datasets/esparko/mmda-traffic-incident-data/",
                       target="_blank", rel="noopener"),
                ". Only incidents classified as collisions or accidents are shown."]),
        html.P(["Made by Jan Robee Feliciano (",
                html.A("jan_feliciano@dlsu.edu.ph", href="mailto:jan_feliciano@dlsu.edu.ph"), ")."]),
    ], className="footer"),

    dcc.Store(id="theme-store"),
    dcc.Store(id="selected-time-store", data="All Day"),
], className="page")


# --------------------------------------------------------------------------- #
# Callbacks
# --------------------------------------------------------------------------- #
# Theme: starts from the browser's light/dark setting on every load; the button flips it.
clientside_callback(
    """
    function (n, theme) {
        if (!n) {
            return (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
        }
        return (theme === 'dark') ? 'light' : 'dark';
    }
    """,
    Output("theme-store", "data"),
    Input("theme-toggle", "n_clicks"),
    State("theme-store", "data"),
)

clientside_callback(
    """
    function (theme) {
        if (!theme) { return window.dash_clientside.no_update; }
        var t = theme === 'dark' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', t);
        return t === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
    }
    """,
    Output("theme-toggle", "aria-label"),
    Input("theme-store", "data"),
)

# Time-of-day segmented control and the reset button: instant, client side.
clientside_callback(
    """
    function (clicks, reset, ids) {
        var nu = window.dash_clientside.no_update;
        var trig = dash_clientside.callback_context.triggered_id;
        var isReset = trig === 'reset-filters-btn';
        var sel = isReset ? 'All Day' : ((trig && trig.index) || 'All Day');
        var classes = ids.map(function (i) { return i.index === sel ? 'seg active' : 'seg'; });
        return [classes, sel, isReset ? 'All Months' : nu, isReset ? 'All Cities' : nu];
    }
    """,
    Output({"type": "time-btn", "index": ALL}, "className"),
    Output("selected-time-store", "data"),
    Output("month-dropdown", "value"),
    Output("city-dropdown", "value"),
    Input({"type": "time-btn", "index": ALL}, "n_clicks"),
    Input("reset-filters-btn", "n_clicks"),
    State({"type": "time-btn", "index": ALL}, "id"),
    prevent_initial_call=True,
)


def current_filters(time_filter, month, city):
    """Filters for a server callback; the reset button means the defaults, whatever the controls held."""
    if ctx.triggered_id == "reset-filters-btn":
        return "All Day", "All Months", "All Cities"
    return time_filter or "All Day", month or "All Months", city or "All Cities"


@dash_app.callback(
    Output("leaflet-map", "srcDoc"),
    Output("map-count", "children"),
    Input("apply-filters-btn", "n_clicks"),
    Input("reset-filters-btn", "n_clicks"),
    State("selected-time-store", "data"),
    State("month-dropdown", "value"),
    State("city-dropdown", "value"),
)
def update_map(_apply, _reset, time_filter, month, city):
    map_html, count = build_map_html(*current_filters(time_filter, month, city))
    return map_html, f"{count:,} {'accident' if count == 1 else 'accidents'}"


@dash_app.callback(
    Output("vehicle-bar-chart", "figure"),
    Output("monthly-accidents-chart", "figure"),
    Output("hourly-accidents-chart", "figure"),
    Output("vehicle-note", "children"),
    Input("theme-store", "data"),
    Input("apply-filters-btn", "n_clicks"),
    Input("reset-filters-btn", "n_clicks"),
    State("selected-time-store", "data"),
    State("month-dropdown", "value"),
    State("city-dropdown", "value"),
)
def update_charts(theme, _apply, _reset, time_filter, month, city):
    if theme is None:  # wait until the browser's light/dark setting is known
        raise PreventUpdate
    time_filter, month, city = current_filters(time_filter, month, city)
    c = CHART_THEME["dark" if theme == "dark" else "light"]
    filtered = filter_df(time_filter, month, city)
    vehicles, note = vehicle_chart(filtered, c)
    return (
        vehicles,
        monthly_chart(filter_df(time_filter, month, city, use_month=False), month, c),
        hourly_chart(filtered, time_filter, c),
        note,
    )


# --------------------------------------------------------------------------- #
# Page shell: applies the browser's light/dark setting before first paint (no flash)
# and follows it if the system setting changes while the page is open.
# --------------------------------------------------------------------------- #
dash_app.index_string = """<!DOCTYPE html>
<html lang="en">
<head>
{%metas%}
<meta name="description" content="Where and when traffic accidents happen in Metro Manila, from MMDA incident reports.">
<meta name="color-scheme" content="light dark">
<title>{%title%}</title>
<script>
(function () {
  if (!window.matchMedia) { document.documentElement.setAttribute('data-theme', 'light'); return; }
  var mq = matchMedia('(prefers-color-scheme: dark)');
  document.documentElement.setAttribute('data-theme', mq.matches ? 'dark' : 'light');
  var onChange = function (e) {
    var want = e.matches ? 'dark' : 'light';
    var btn = document.getElementById('theme-toggle');
    if (btn && document.documentElement.getAttribute('data-theme') !== want) btn.click();
  };
  if (mq.addEventListener) mq.addEventListener('change', onChange); else if (mq.addListener) mq.addListener(onChange);
})();
</script>
{%favicon%}
{%css%}
</head>
<body>
{%app_entry%}
<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>"""


if __name__ == "__main__":
    dash_app.run(debug=False)
