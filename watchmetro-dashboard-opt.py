# -*- coding: utf-8 -*-
"""WatchMetro-Dashboard - Memory Optimized Version

Optimized for deployment on platforms with memory constraints like Render
"""

from dash import Dash, dcc, html, Input, Output, State, callback_context
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import MarkerCluster
from io import BytesIO
import re
import numpy as np
import json
from dash.dependencies import ALL
import gc
import os
import dash_daq as daq


# Memory optimization: Load data more efficiently
def load_and_optimize_data():
    """Load data with memory optimization"""
    # Define dtypes to reduce memory usage
    dtypes = {
        'City': 'category',
        'Location': 'string',
        'Type': 'category',
        'Involved': 'string',
        'Time': 'string',
        'Date': 'string',
        'Latitude': 'float32',  # Use float32 instead of float64
        'Longitude': 'float32'
    }
    
    try:
        df = pd.read_csv('dataset_cleaned.csv', dtype=dtypes)
        print(f"Successfully loaded {len(df)} records from dataset_cleaned.csv")
        
        # --- safe datetime parsing & integer conversion ---
        # ensure Date_datetime exists (parse from 'Date' if needed)
        if 'Date_datetime' not in df.columns:
            df['Date_datetime'] = pd.to_datetime(df.get('Date', None), errors='coerce')
        else:
            df['Date_datetime'] = pd.to_datetime(df['Date_datetime'], errors='coerce')
        
        # parse Time to datetime (coerce invalid formats)
        df['Time_datetime'] = pd.to_datetime(df.get('Time', None), format='%I:%M %p', errors='coerce')
        
        # Extract hour safely: replace infinities, fill NaN with -1, cast to int
        df['Hour'] = df['Time_datetime'].dt.hour
        df['Hour'] = df['Hour'].replace([np.inf, -np.inf], np.nan).fillna(-1).astype('int16')
        
        # Month name: fill missing with 'Unknown' to avoid NaN category issues
        df['Month_Name'] = df['Date_datetime'].dt.month_name()
        df['Month_Name'] = df['Month_Name'].fillna('Unknown').astype('category')
        # -------------------------------------------------

        
        # Optimize string operations
        df['Involved'] = df['Involved'].astype(str).str.upper().str.replace(r"[^A-Z0-9\s,]", "", regex=True)
        
        return df
    except FileNotFoundError:
        print("ERROR: dataset_cleaned.csv not found! Please ensure the file is in the same directory as your Python script.")
        raise FileNotFoundError("dataset_cleaned.csv is required for the dashboard to function")
    except Exception as e:
        print(f"Error loading data: {e}")
        raise e

df = load_and_optimize_data()

# Optimize themes (use simpler objects)
themes = {
    'light': {
        'bg': '#f9f9f9',
        'card': 'white',
        'text': '#111111',
        'plot_bg': '#f0f0f0',
        'paper_bg': 'white'
    },
    'dark': {
        'bg': '#1e1e1e',
        'card': '#2c2c2c',
        'text': 'white',
        'plot_bg': '#333333',
        'paper_bg': '#2c2c2c'
    }
}

# Create time period classifications more efficiently
time_period_map = {
    **{h: 'Morning' for h in range(6, 12)},
    **{h: 'Afternoon' for h in range(12, 18)},
    **{h: 'Evening' for h in list(range(18, 24)) + list(range(0, 6))}
}

def get_time_period(hour):
    return time_period_map.get(hour, 'All Day') if pd.notna(hour) else 'All Day'

df['Time_Period'] = df['Hour'].apply(get_time_period).astype('category')

# Optimize vehicle name cleaning (reduce string operations)
vehicle_map = {'BU': 'BUS', 'MC': 'MOTORCYCLE', 'PUJ': 'JEEP', 'AUV': 'CAR', 'SUV': 'CAR'}

def clean_vehicle_name(name):
    if not isinstance(name, str) or pd.isna(name):
        return None
    name = re.sub(r"[^A-Z0-9\s]", "", name.strip().upper())
    name = re.sub(r"\b\d+\s*", "", name)
    name = vehicle_map.get(name, name)
    return name[:-1] if name.endswith('S') and name != 'BUS' else name

# Pre-compute commonly used values
month_options = ['January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December']
city_options = sorted(df['City'].dropna().unique().tolist())
time_buttons = [
    {'label': 'All Day', 'value': 'All Day'},
    {'label': 'Morning', 'value': 'Morning'},
    {'label': 'Afternoon', 'value': 'Afternoon'},
    {'label': 'Evening', 'value': 'Evening'}
]

def create_no_data_figure(title, theme_colors, message="No data available"):
    """Lightweight no-data figure"""
    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.5, xref="paper", yref="paper", text=message,
        showarrow=False, font=dict(size=16, color=theme_colors['text']),
        bgcolor=theme_colors['plot_bg'], bordercolor=theme_colors['text'],
        borderwidth=1, borderpad=20
    )
    fig.update_layout(
        title=title, height=400,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        plot_bgcolor=theme_colors['plot_bg'],
        paper_bgcolor=theme_colors['paper_bg'],
        font_color=theme_colors['text']
    )
    return fig

# Optimize map generation (reduce memory footprint)
def generate_folium_map(data, theme='light', max_markers=500):
    """Generate map with marker limit to reduce memory usage"""
    if data.empty:
        m = folium.Map(location=[14.6, 121.0], zoom_start=11)
        folium.Marker([14.6, 121.0], popup="No data for selected filters").add_to(m)
        return m

    # Limit markers for performance
    if len(data) > max_markers:
        data = data.sample(n=max_markers)

    center_lat = float(data['Latitude'].mean())
    center_lon = float(data['Longitude'].mean())
    
    tiles = 'CartoDB dark_matter' if theme == 'dark' else 'OpenStreetMap'
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles=tiles)

    # Use MarkerCluster for better performance
    cluster = MarkerCluster().add_to(m)
    
    for _, row in data.iterrows():
        popup = f"<b>{row['City']}</b><br>{row['Time']}<br>{row['Date']}"
        folium.Marker(
            location=[float(row['Latitude']), float(row['Longitude'])],
            popup=popup,
            icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')
        ).add_to(cluster)
    
    return m

def get_time_range(time_period):
    """Get time range for filtering (excludes -1 which represents missing data)"""
    ranges = {
        'Morning': list(range(6, 12)),
        'Afternoon': list(range(12, 18)),
        'Evening': list(range(18, 24)) + list(range(0, 6)),
        'All Day': list(range(24))  # 0-23, excludes -1
    }
    return ranges.get(time_period, list(range(24)))

# Initialize app with optimizations
app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "WatchMetro: Metro Manila Accidents Dashboard"

# Generate initial map (limited size)
initial_data = df.dropna(subset=['Latitude', 'Longitude']).head(200)  # Limit initial data
initial_map = generate_folium_map(initial_data, 'light')
buffer = BytesIO()
initial_map.save(buffer, close_file=False)
initial_map_html = buffer.getvalue().decode("utf-8")
buffer.close()

# Optimized app layout (same structure, but with memory considerations)
app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.H1("WatchMetro: Metro Manila Accidents Dashboard", 
                   id='title', style={'margin': '0', 'fontSize': '2em', 'fontWeight': 'bold'}),
            html.H3("Traffic Incidents Visualization", 
                   id='subtitle', style={'margin': '5px 0 0 0', 'color': '#666', 'fontSize': '1.2em'})
        ], style={'flex': '1'}),
        
        html.Div([
            html.Div([
                html.Span("☀️", style={'fontSize': '20px', 'marginRight': '8px'}),
                daq.ToggleSwitch(
                    id="theme-toggle",
                    value=False,   # False = light, True = dark
                    color="#2c3e50"
                ),
                html.Span("🌙", style={'fontSize': '20px', 'marginLeft': '8px'})
            ])
        ])
    ], style={
        'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
        'padding': '20px 40px', 'marginBottom': '20px'
    }),

    # Controls
    html.Div([
        html.Div([
            html.Label("Time of Day", style={'fontWeight': 'bold', 'marginBottom': '10px', 'display': 'block'}),
            html.Div([
                html.Button(btn['label'],
                           id={'type': 'time-btn', 'index': btn['value']},
                           n_clicks=1 if btn['value'] == 'All Day' else 0,
                           style={'padding': '8px 12px', 'margin': '2px', 'border': 'none', 'borderRadius': '6px',
                                 'cursor': 'pointer', 'backgroundColor': '#2c3e50' if btn['value'] == 'All Day' else '#e0e0e0',
                                 'color': 'white' if btn['value'] == 'All Day' else 'black'})
                for btn in time_buttons
            ])
        ], className='card', style={'flex': '2', 'margin': '10px'}),

        html.Div([
            html.Label("Month", style={'fontWeight': 'bold', 'marginBottom': '10px', 'display': 'block'}),
            dcc.Dropdown(
                id='month-dropdown',
                options=[{'label': m, 'value': m} for m in month_options] + [{'label': 'All Months', 'value': 'All Months'}],
                value='All Months'
            )
        ], className='card', style={'flex': '1', 'margin': '10px'}),

        html.Div([
            html.Label("City", style={'fontWeight': 'bold', 'marginBottom': '10px', 'display': 'block'}),
            dcc.Dropdown(
                id='city-dropdown',
                options=[{'label': c, 'value': c} for c in city_options] + [{'label': 'All Cities', 'value': 'All Cities'}],
                value='All Cities'
            )
        ], className='card', style={'flex': '1', 'margin': '10px'}),

        html.Div([
            html.Button("Apply Filters", id='apply-filters-btn', n_clicks=0,
                       style={'padding': '12px 20px', 'background': '#3498db', 'color': 'white',
                             'border': 'none', 'borderRadius': '8px', 'cursor': 'pointer', 'width': '100%'})
        ], className='card', style={'flex': '0.8', 'margin': '10px', 'display': 'flex', 'alignItems': 'center'})
    ], style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'center'}),

    # Map
    html.Div([
        html.Div([
            html.H3("Accident Locations", style={'textAlign': 'center', 'marginBottom': '15px'}),
            html.Iframe(id='leaflet-map', srcDoc=initial_map_html, width='100%', height='450')
        ], className='card', style={'width': '95%', 'margin': '10px auto'})
    ]),

    # Charts row 1
    html.Div([
        html.Div([dcc.Graph(id='vehicle-bar-chart')], className='card', style={'flex': '1', 'margin': '10px'}),
        html.Div([dcc.Graph(id='monthly-accidents-chart')], className='card', style={'flex': '1', 'margin': '10px'})
    ], style={'display': 'flex', 'flexWrap': 'wrap'}),

    # Charts row 2
    html.Div([
        html.Div([dcc.Graph(id='hourly-accidents-chart')], className='card', style={'width': '95%', 'margin': '10px auto'})
    ]),

    # Loading indicator
    html.Div(id='loading-div', children='', style={'textAlign': 'center', 'padding': '10px'}),

    # Stores
    dcc.Store(id='theme-store', data='light'),
    dcc.Store(id='selected-time-store', data='All Day'),

    # Footer
    html.Div([
        html.Hr(style={'margin': '40px 0 20px 0', 'opacity': '0.3'}),
        html.P("DISCLAIMER: Dashboard presents MMDA traffic incidents (2018-2020).", 
               style={'textAlign': 'center', 'fontSize': '14px', 'opacity': '0.8'}),
        html.Div([
            html.Div("Authors: Jan Robee Feliciano, Alphonse Juanito Sese", 
                    style={'textAlign': 'center', 'fontSize': '14px'})
        ])
    ], style={'padding': '20px'})

], id='main-container', className='light-theme')

# Optimized callbacks with memory management
@app.callback(
    [Output({'type': 'time-btn', 'index': ALL}, 'style'),
     Output('selected-time-store', 'data')],
    [Input({'type': 'time-btn', 'index': ALL}, 'n_clicks')],
    [State({'type': 'time-btn', 'index': ALL}, 'id')],
    prevent_initial_call=True
)
def update_time_buttons(clicks, ids):
    """Update time button styles and store selection"""
    ctx = callback_context
    time_filter = 'All Day'
    
    if ctx.triggered:
        try:
            prop_id = ctx.triggered[0]['prop_id']
            if 'Morning' in prop_id: time_filter = 'Morning'
            elif 'Afternoon' in prop_id: time_filter = 'Afternoon'
            elif 'Evening' in prop_id: time_filter = 'Evening'
            else: time_filter = 'All Day'
        except:
            time_filter = 'All Day'
    
    # Create button styles
    styles = []
    for id_dict in ids:
        is_active = id_dict['index'] == time_filter
        style = {
            'padding': '8px 12px', 'margin': '2px', 'border': 'none', 'borderRadius': '6px',
            'cursor': 'pointer', 'backgroundColor': '#2c3e50' if is_active else '#e0e0e0',
            'color': 'white' if is_active else 'black'
        }
        styles.append(style)
    
    return styles, time_filter

@app.callback(
    [Output('main-container', 'className'), Output('theme-store', 'data')],
    [Input('theme-toggle', 'value')]
)
def update_theme(theme_value):
    """Update theme"""
    theme = 'dark' if 'dark' in theme_value else 'light'
    return f'{theme}-theme', theme

def create_vehicle_chart(filtered_df, filters, theme_colors):
    """Create vehicle involvement chart with memory optimization"""
    if filtered_df.empty:
        return create_no_data_figure(f"Vehicle Types ({', '.join(filters)})", theme_colors)
    
    # Process vehicles efficiently
    vehicles = filtered_df['Involved'].str.split(r"\s+AND\s+|\s*,\s*").explode()
    vehicles = vehicles.apply(clean_vehicle_name).dropna()
    
    if vehicles.empty:
        return create_no_data_figure(f"Vehicle Types ({', '.join(filters)})", theme_colors)
    
    # Get top vehicles (limit for performance)
    vehicle_counts = vehicles.value_counts().head(10)
    
    fig = px.bar(
        x=vehicle_counts.values, y=vehicle_counts.index, orientation='h',
        title=f"Vehicle Types ({', '.join(filters)})",
        labels={'x': 'Count', 'y': 'Vehicle'}
    )
    fig.update_layout(
        plot_bgcolor=theme_colors['plot_bg'], paper_bgcolor=theme_colors['paper_bg'],
        font_color=theme_colors['text'], height=400, yaxis={'categoryorder': 'total ascending'}
    )
    return fig

def create_monthly_chart(data, filters, theme_colors):
    """Create monthly accidents chart"""
    if data.empty:
        return create_no_data_figure(f"Monthly Accidents ({', '.join(filters)})", theme_colors)
    
    monthly = data['Month_Name'].value_counts().reindex(month_options, fill_value=0)
    
    fig = px.bar(x=monthly.index, y=monthly.values, 
                title=f"Monthly Accidents ({', '.join(filters)})")
    fig.update_layout(
        plot_bgcolor=theme_colors['plot_bg'], paper_bgcolor=theme_colors['paper_bg'],
        font_color=theme_colors['text'], xaxis_tickangle=-45
    )
    return fig

def create_hourly_chart(data, time_filter, filters, theme_colors):
    """Create hourly accidents chart"""
    if data.empty:
        return create_no_data_figure(f"Hourly Pattern ({', '.join(filters)})", theme_colors)
    
    time_range = get_time_range(time_filter)
    hourly = data['Hour'].value_counts().sort_index()
    
    # Create hourly data for selected time range
    hours, counts = [], []
    for hour in time_range:
        hours.append(f"{hour:02d}:00")
        counts.append(hourly.get(hour, 0))
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hours, y=counts, mode='lines+markers', name='Accidents'))
    fig.update_layout(
        title=f"Hourly Pattern ({', '.join(filters)})",
        plot_bgcolor=theme_colors['plot_bg'], paper_bgcolor=theme_colors['paper_bg'],
        font_color=theme_colors['text'], xaxis_tickangle=-45
    )
    return fig

@app.callback(
    [Output('vehicle-bar-chart', 'figure'),
     Output('monthly-accidents-chart', 'figure'), 
     Output('hourly-accidents-chart', 'figure'),
     Output('loading-div', 'children')],
    [Input('theme-store', 'data'), Input('apply-filters-btn', 'n_clicks')],
    [State('selected-time-store', 'data'), State('month-dropdown', 'value'), State('city-dropdown', 'value')]
)
def update_charts(theme, apply_clicks, time_filter, month, city):
    """Update all charts with memory optimization"""
    try:
        theme_colors = themes.get(theme, themes['light'])
        
        # Default values
        time_filter = time_filter or 'All Day'
        month = month or 'All Months'
        city = city or 'All Cities'
        
        # Filter data efficiently
        mask = pd.Series([True] * len(df))
        if month != 'All Months':
            mask &= (df['Month_Name'] == month)
        if city != 'All Cities':
            mask &= (df['City'] == city)
        if time_filter != 'All Day':
            mask &= (df['Time_Period'] == time_filter)
        
        filtered_df = df[mask].copy()
        
        # Create filter description
        filters = [f for f in [time_filter, month, city] if f not in ['All Day', 'All Months', 'All Cities']]
        if not filters:
            filters = ['All Data']
        
        # Generate charts
        vehicle_chart = create_vehicle_chart(filtered_df, filters, theme_colors)
        
        # For monthly chart, don't filter by month
        monthly_mask = pd.Series([True] * len(df))
        if city != 'All Cities':
            monthly_mask &= (df['City'] == city)
        if time_filter != 'All Day':
            monthly_mask &= (df['Time_Period'] == time_filter)
        monthly_data = df[monthly_mask]
        monthly_filters = [f for f in [time_filter, city] if f not in ['All Day', 'All Cities']]
        
        monthly_chart = create_monthly_chart(monthly_data, monthly_filters or ['All Data'], theme_colors)
        hourly_chart = create_hourly_chart(filtered_df, time_filter, filters, theme_colors)
        
        # Force garbage collection
        gc.collect()
        
        return vehicle_chart, monthly_chart, hourly_chart, ""
        
    except Exception as e:
        # Return error charts if something goes wrong
        error_fig = create_no_data_figure("Error", theme_colors, f"Error: {str(e)}")
        return error_fig, error_fig, error_fig, f"Error: {str(e)}"

@app.callback(
    Output('leaflet-map', 'srcDoc'),
    [Input('apply-filters-btn', 'n_clicks')],
    [State('selected-time-store', 'data'), State('month-dropdown', 'value'), 
     State('city-dropdown', 'value'), State('theme-store', 'data')]
)
def update_map(apply_clicks, time_filter, month, city, theme):
    """Update map with memory optimization"""
    try:
        # Default values
        time_filter = time_filter or 'All Day'
        month = month or 'All Months'
        city = city or 'All Cities'
        
        # Filter data efficiently
        mask = pd.Series([True] * len(df))
        if month != 'All Months':
            mask &= (df['Month_Name'] == month)
        if city != 'All Cities':
            mask &= (df['City'] == city)
        if time_filter != 'All Day':
            mask &= (df['Time_Period'] == time_filter)
        
        filtered_df = df[mask].dropna(subset=['Latitude', 'Longitude'])
        
        # Generate map with limited markers
        updated_map = generate_folium_map(filtered_df, theme, max_markers=300)
        
        buffer = BytesIO()
        updated_map.save(buffer, close_file=False)
        map_html = buffer.getvalue().decode("utf-8")
        buffer.close()
        
        # Force cleanup
        del updated_map
        gc.collect()
        
        return map_html
        
    except Exception as e:
        print(f"Map update error: {e}")
        return initial_map_html

# Simple CSS (embedded to reduce external dependencies)
app.index_string = '''
<!DOCTYPE html>
<html>
<head>
{%metas%}
<title>WatchMetro Dashboard</title>
{%favicon%}
{%css%}
<style>
body { margin: 0; font-family: Arial, sans-serif; }
.card { background: white; border-radius: 8px; padding: 15px; margin: 5px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.light-theme { background: #f5f5f5; color: #333; }
.dark-theme { background: #1a1a1a; color: white; }
.dark-theme .card { background: #2a2a2a; }
</style>
</head>
<body>
{%app_entry%}
{%config%}
{%scripts%}
{%renderer%}
</body>
</html>
'''

server = app.server

if __name__ == '__main__':
    # Production optimizations
    app.run(debug=False, dev_tools_ui=False, dev_tools_props_check=False)
