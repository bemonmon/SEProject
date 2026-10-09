import dash
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output, State
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime as dt
from datetime import timedelta
import numpy as np
from sklearn.linear_model import LinearRegression
import time

# --- Configuration for Flask API ---
FLASK_API_URL = "http://127.0.0.1:5000"

# --- Data Fetching Functions ---
# Fetching data function for the plot "Average Values per Day per Pollutant and Comune"
global df
df = pd.DataFrame(columns=['nome_tipo_sensore', 'provincia','comune', 'day', 'avg_value'])

def load_data_1():
        """Load data from Flask endpoint with retry logic"""
        global df
        if df.empty:
            for attempt in range(5):  # Try 5 times
                try:
                    url = f"http://localhost:5000/data_1"
                    response = requests.get(url, timeout=5)
                    response.raise_for_status()
                    data = response.json()
                    df = pd.DataFrame(data)
                    print("Data loaded successfully from Flask endpoint")
                    break
                except Exception as e:
                    print(f"Attempt {attempt + 1}: Error loading data from Flask /data_1:", e)
                    if attempt < 4:  # Don't sleep on last attempt
                        time.sleep(1)  # Wait 1 second before retry
        return df


def fetch_sensors_data():
    """Fetches sensor metadata from the Flask API."""
    try:
        response = requests.get(f"{FLASK_API_URL}/sensors")
        response.raise_for_status()
        sensor_data = response.json()
        df = pd.DataFrame(sensor_data)
        if not df.empty:
            df['id_sensore'] = df['id_sensore'].astype(int)
        return df
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to Flask API at {FLASK_API_URL}.")
        print("Using demo sensor locations for the map/dropdown (for fetch_sensors_data).")
        return pd.DataFrame({
            "id_sensore": [1, 2, 3, 4],
            "nome_stazione": ["Demo North", "Demo North", "Demo South", "Demo South"],
            "provincia": ["XX", "XX", "YY", "YY"],
            "comune": ["Foo", "Foo", "Bar", "Bar"],
            "latitude": [45.47, 45.47, 45.45, 45.45],
            "longitude": [9.18, 9.18, 9.20, 9.20],
            "nome_tipo_sensore": ["PM2.5", "PM10", "NO2", "CO"],
            "unita_misura": ["µg/m³", "µg/m³", "µg/m³", "mg/m³"]
        })
    except Exception as e:
        print(f"An unexpected error occurred while fetching sensor data: {e}")
        return pd.DataFrame()

def fetch_air_quality_history(sensor_id):
    """Fetches air quality data for a specific sensor from the Flask API."""
    try:
        data_response = requests.get(f"{FLASK_API_URL}/air_quality/{sensor_id}")
        data_response.raise_for_status()
        historical_data = data_response.json()
        df = pd.DataFrame(historical_data)
        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
            df = df.sort_values(by='data')
        return df
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to Flask API at {FLASK_API_URL} for air quality data.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error fetching air quality data for sensor {sensor_id}: {e}")
        return pd.DataFrame()

def group_sensors_by_station(sensor_df, status_df):
    """Group sensors by station and aggregate information."""
    if sensor_df.empty:
        return pd.DataFrame()
    
    # Create a station identifier (could be nome_stazione + comune for uniqueness)
    sensor_df['station_key'] = sensor_df['nome_stazione'] + '_' + sensor_df['comune']
    
    # Group by station
    station_groups = sensor_df.groupby('station_key').agg({
        'id_sensore': lambda x: list(x),  # List of all sensor IDs
        'nome_stazione': 'first',
        'provincia': 'first',
        'comune': 'first',
        'latitude': 'first',
        'longitude': 'first',
        'nome_tipo_sensore': lambda x: list(x),  # List of sensor types
        'unita_misura': lambda x: list(x)  # List of units
    }).reset_index()
    
    # Add sensor count
    station_groups['sensor_count'] = station_groups['id_sensore'].apply(len)
    
    # Merge with status data if available
    if not status_df.empty:
        # For each station, check if any sensor has data
        station_groups['has_data'] = False
        station_groups['total_data_count'] = 0
        
        for idx, row in station_groups.iterrows():
            sensor_ids = row['id_sensore']
            station_status = status_df[status_df['id_sensore'].isin(sensor_ids)]
            
            if not station_status.empty:
                station_groups.at[idx, 'has_data'] = station_status['has_data'].any()
                station_groups.at[idx, 'total_data_count'] = station_status['data_count_2019'].sum()
    else:
        station_groups['has_data'] = False
        station_groups['total_data_count'] = 0
    
    station_groups['has_data_str'] = station_groups['has_data'].apply(
        lambda x: 'Available Data' if x else 'No Data'
    )
    
    return station_groups

def get_second_page_layout():
    # Fetch sensor data
    sensor_df = fetch_sensors_data()
    
    # Load sensor status data
    status_df = pd.DataFrame()
    try:
        status_df = pd.read_csv('sensor_status_cache.csv')
        status_df['id_sensore'] = status_df['id_sensore'].astype(int)
        print("Successfully loaded sensor status from sensor_status_cache.csv.")
    except FileNotFoundError:
        print("Error: 'sensor_status_cache.csv' not found. Using default status.")
        # Create dummy status data for demo
        if not sensor_df.empty:
            status_df = pd.DataFrame({
                'id_sensore': sensor_df['id_sensore'].tolist(),
                'has_data': [True] * len(sensor_df),
                'data_count_2019': [100 + i * 50 for i in range(len(sensor_df))],
                'status': ['active'] * len(sensor_df)
            })
    except Exception as e:
        print(f"Error loading sensor_status_cache.csv: {e}")
        status_df = pd.DataFrame()

    # Group sensors by station
    station_df = group_sensors_by_station(sensor_df, status_df)
    
    # Create map
    MAP_CENTER_LAT = 45.4642
    MAP_CENTER_LON = 9.1900
    MARKER_SIZE = 12

    # Filter data for layering
    df_available = station_df[station_df['has_data_str'] == 'Available Data']
    df_no_data = station_df[station_df['has_data_str'] == 'No Data']

    # Create map traces
    trace_no_data = go.Scattermap(
        lat=df_no_data['latitude'],
        lon=df_no_data['longitude'],
        mode='markers',
        marker=dict(size=MARKER_SIZE, color='gray'),
        hoverinfo='text',
        text=[
            f"Station: {row['nome_stazione']}<br>"
            f"Comune: {row['comune']}<br>"
            f"Provincia: {row['provincia']}<br>"
            f"Sensors: {row['sensor_count']}<br>"
            f"Sensor Types: {', '.join(row['nome_tipo_sensore'])}<br>"
            f"Status: {row['has_data_str']}<br>"
            f"Total 2019 Data: {int(row['total_data_count'])}"
            for _, row in df_no_data.iterrows()
        ],
        name='No Data'
    )

    trace_available = go.Scattermap(
        lat=df_available['latitude'],
        lon=df_available['longitude'],
        mode='markers',
        marker=dict(size=MARKER_SIZE, color='blue'),
        hoverinfo='text',
        text=[
            f"Station: {row['nome_stazione']}<br>"
            f"Comune: {row['comune']}<br>"
            f"Provincia: {row['provincia']}<br>"
            f"Sensors: {row['sensor_count']}<br>"
            f"Sensor Types: {', '.join(row['nome_tipo_sensore'])}<br>"
            f"Status: {row['has_data_str']}<br>"
            f"Total 2019 Data: {int(row['total_data_count'])}"
            for _, row in df_available.iterrows()
        ],
        name='Available Data'
    )

    # Create map figure
    fig = go.Figure(data=[trace_no_data, trace_available])
    fig.update_layout(
        map_style="open-street-map",
        map_zoom=6,
        map_center={"lat": MAP_CENTER_LAT, "lon": MAP_CENTER_LON},
        margin={"r":0,"t":0,"l":0,"b":0},
        showlegend=True,
        title=None
    )

    # Create bar chart for stations
    filtered_station_df = station_df[
        (station_df['has_data_str'] == 'Available Data') &
        (station_df['total_data_count'] > 0)
    ].copy()

    bar_fig = px.bar(
        filtered_station_df.sort_values('total_data_count', ascending=False),
        x='nome_stazione',
        y='total_data_count',
        labels={'nome_stazione': 'Station Name', 'total_data_count': 'Total 2019 Data Count'},
        title='2019 Total Data Count per Station (All Sensors Combined - Click to Select Station)',
        hover_data={'sensor_count': True}
    )
    bar_fig.update_layout(xaxis_title="Station", yaxis_title="Total Data Count", showlegend=False)

    # Prepare dropdown options
    dropdown_options = [
        {
            'label': f"{row['nome_stazione']} ({row['sensor_count']} sensors)", 
            'value': row['station_key']
        }
        for _, row in filtered_station_df.iterrows()
    ]
    initial_dropdown_value = dropdown_options[0]['value'] if dropdown_options else None

    return html.Div([
        # Logout link
        html.Div(
            dcc.Link('Log out', href='/', style={
                'color': '#007bff',
                'fontFamily': 'serif',
                'fontWeight': 'bold',
                "textDecoration": "none",
                'fontSize': '20px',
                'padding': '15px 20px',
                'borderRadius': '5px',
                'border': '1px solid #007bff',
                'display': 'inline-block',
                'transition': 'all 0.3s ease'
            }),
            style={'paddingLeft': '80%', 'paddingTop': '10px'}
        ),

        html.H1("Multi-Sensor Station Dashboard", style={'textAlign': 'center', 'marginTop': '30px', 'color': '#333'}),

        # Map Component
        html.Div([
            dcc.Graph(id='sensor-map', figure=fig)
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'margin': '20px auto', 'width': '90%'}),

        # Bar Chart for Station Selection
        html.Div([
            html.H2("Station Data Availability (2019)", style={'textAlign': 'center', 'marginBottom': '20px', 'color': '#555'}),
            dcc.Graph(id='station-bar-chart', figure=bar_fig)
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'margin': '20px auto', 'width': '90%'}),

        # Station and Date Range Selection
        html.Div([
            html.H2("Explore Multi-Sensor Station Data", style={'textAlign': 'center', 'marginBottom': '20px', 'color': '#555'}),
            html.Div([
                html.Label("Select Station:", style={'marginRight': '10px', 'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id='station-dropdown',
                    options=dropdown_options,
                    value=initial_dropdown_value,
                    placeholder="Select a station",
                    style={'width': '400px', 'marginRight': '20px'}
                ),
                html.Label("Select 2019 Date Range:", style={'marginRight': '10px', 'fontWeight': 'bold'}),
                dcc.DatePickerRange(
                    id='date-range-picker',
                    min_date_allowed=dt(2019, 1, 1),
                    max_date_allowed=dt(2019, 12, 31),
                    initial_visible_month=dt(2019, 1, 1),
                    start_date=dt(2019, 1, 1).date(),
                    end_date=dt(2019, 12, 31).date(),
                    display_format='YYYY-MM-DD',
                    style={'width': 'auto'}
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'flexWrap': 'wrap', 'padding': '10px'}),
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'margin': '20px auto', 'width': '90%', 'backgroundColor': '#f8f8f8'}),

        # Station Info Display
        html.Div(id='station-info-display', style={'textAlign': 'center', 'margin': '20px', 'fontSize': '16px', 'color': '#666'}),

        # Multi-sensor plot
        html.Div([
            html.H2("All Sensors Data for Selected Station", style={'textAlign': 'center', 'marginBottom': '20px', 'color': '#555'}),
            html.Div([
                html.Button(
                    "Download All Plots as PNG", 
                    id="download-plot-btn", 
                    n_clicks=0,
                    style={
                        'backgroundColor': '#28a745',
                        'color': 'white',
                        'border': 'none',
                        'padding': '10px 20px',
                        'borderRadius': '5px',
                        'cursor': 'pointer',
                        'fontSize': '14px',
                        'marginBottom': '10px',
                        'marginRight': '10px'
                    }
                ),
                html.Button(
                    "Download All Plots as HTML", 
                    id="download-plot-html-btn", 
                    n_clicks=0,
                    style={
                        'backgroundColor': '#007bff',
                        'color': 'white',
                        'border': 'none',
                        'padding': '10px 20px',
                        'borderRadius': '5px',
                        'cursor': 'pointer',
                        'fontSize': '14px',
                        'marginBottom': '10px'
                    }
                )
            ], style={'textAlign': 'center'}),
            dcc.Graph(
                id='multi-sensor-plot',
                config={
                    'displayModeBar': True,
                    'displaylogo': False,
                    'modeBarButtonsToAdd': ['downloadPlot'],
                    'toImageButtonOptions': {
                        'format': 'png',
                        'filename': 'multi_sensor_station_plot',
                        'height': 800,
                        'width': 1400,
                        'scale': 2
                    }
                }
            ),
            dcc.Download(id="download-plot-png"),
            dcc.Download(id="download-plot-html")
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'margin': '20px auto', 'width': '90%', 'minHeight': '600px'}),

        # Combined data table for all sensors
        html.Div([
            html.H2("Combined Data Table for All Station Sensors", style={'textAlign': 'center', 'marginBottom': '20px', 'color': '#555'}),
            html.Div(id='combined-data-info', style={'textAlign': 'center', 'marginBottom': '15px', 'fontSize': '16px', 'color': '#666'}),
            dash_table.DataTable(
                id='combined-sensor-table',
                columns=[],
                data=[],
                style_table={'overflowX': 'auto', 'margin': '20px auto', 'width': '95%'},
                style_cell={
                    'height': 'auto',
                    'minWidth': '100px', 'width': '150px', 'maxWidth': '200px',
                    'whiteSpace': 'normal',
                    'textAlign': 'left',
                    'padding': '10px',
                    'fontFamily': 'Arial, sans-serif'
                },
                style_header={
                    'backgroundColor': 'rgb(230, 230, 230)',
                    'fontWeight': 'bold',
                    'textAlign': 'center'
                },
                style_data_conditional=[
                    {
                        'if': {'row_index': 'odd'},
                        'backgroundColor': 'rgb(248, 248, 248)'
                    }
                ],
                export_format='xlsx',
                export_headers='display',
                filter_action="native",
                sort_action="native",
                page_action="native",
                page_size=20,
            )
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'margin': '20px auto', 'width': '90%'}),

        # Average values per day per pollutant and comune
        html.H2("Average Values per Day per Pollutant and Comune", style={'textAlign': 'center', 'marginBottom': '20px', 'color': '#555'}),
        html.Div([
            html.H5("Choose the pollutant type"),
            dcc.Dropdown(
                id="nome_tipo_sensore",
                options=[],
                value=None,
                clearable=False,
            ),

            html.H5("Choose the province"),
            dcc.Dropdown(id="provincia", clearable=False),

            html.H5("Choose the comune"),
            dcc.Dropdown(id="comune", clearable=False),

            dcc.Graph(id="line"),
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'margin': '20px auto', 'width': '90%'}),

        # Store station data for callbacks
        dcc.Store(id='station-data-store', data=station_df.to_dict('records')),
        dcc.Store(id='sensor-data-store', data=sensor_df.to_dict('records'))
    ])

def calculate_trend_line(df, date_col='data', value_col='valore'):
    """Calculate linear regression trend line for time series data."""
    clean_df = df[[date_col, value_col]].dropna()
    
    if len(clean_df) < 2:
        return None, None, None, None
    
    start_date = clean_df[date_col].min()
    x_numeric = (clean_df[date_col] - start_date).dt.days.values.reshape(-1, 1)
    y_values = clean_df[value_col].values
    
    model = LinearRegression()
    model.fit(x_numeric, y_values)
    
    trend_y = model.predict(x_numeric)
    
    ss_res = np.sum((y_values - trend_y) ** 2)
    ss_tot = np.sum((y_values - np.mean(y_values)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    
    return clean_df[date_col], trend_y, model.coef_[0], r_squared

def register_second_page_callbacks(app):
    @app.callback(
        [Output('multi-sensor-plot', 'figure'),
         Output('combined-sensor-table', 'data'),
         Output('combined-sensor-table', 'columns'),
         Output('combined-data-info', 'children'),
         Output('station-info-display', 'children')],
        [Input('station-bar-chart', 'clickData'),
         Input('station-dropdown', 'value'),
         Input('date-range-picker', 'start_date'),
         Input('date-range-picker', 'end_date')],
        [State('station-data-store', 'data'),
         State('sensor-data-store', 'data')]
    )
    def update_multi_sensor_plot_and_table(bar_chart_clickData, dropdown_station_key, 
                                         start_date, end_date, station_data, sensor_data):
        # Convert stored data back to DataFrames
        station_df = pd.DataFrame(station_data)
        sensor_df = pd.DataFrame(sensor_data)
        
        # Empty returns
        empty_fig = go.Figure().update_layout(
            title="Select a station to see all sensor data",
            xaxis_visible=False, yaxis_visible=False,
            height=400
        )
        empty_table_data = []
        empty_table_columns = []
        empty_info = "No station selected"
        empty_station_info = ""

        # Determine selected station
        ctx = dash.callback_context
        if not ctx.triggered:
            return empty_fig, empty_table_data, empty_table_columns, empty_info, empty_station_info

        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        selected_station_key = None

        if trigger_id == 'station-bar-chart' and bar_chart_clickData:
            # Get station name from bar chart click
            clicked_station_name = bar_chart_clickData['points'][0]['x']
            matching_stations = station_df[station_df['nome_stazione'] == clicked_station_name]
            if not matching_stations.empty:
                selected_station_key = matching_stations.iloc[0]['station_key']
        elif trigger_id == 'station-dropdown' and dropdown_station_key:
            selected_station_key = dropdown_station_key

        if not selected_station_key:
            return empty_fig, empty_table_data, empty_table_columns, empty_info, empty_station_info

        # Get station info
        station_info = station_df[station_df['station_key'] == selected_station_key].iloc[0]
        sensor_ids = station_info['id_sensore']
        sensor_types = station_info['nome_tipo_sensore']
        sensor_units = station_info['unita_misura']
        
        # Create station info display
        station_info_text = (
            f"Station: {station_info['nome_stazione']} | "
            f"Location: {station_info['comune']}, {station_info['provincia']} | "
            f"Sensors: {len(sensor_ids)} ({', '.join(sensor_types)})"
        )

        # Validate date range
        if not (start_date and end_date):
            return go.Figure().update_layout(
                title="Please select a valid date range",
                xaxis_visible=False, yaxis_visible=False, height=400
            ), empty_table_data, empty_table_columns, "Please select a valid date range", station_info_text

        start_dt = dt.strptime(start_date, '%Y-%m-%d')
        end_dt = dt.strptime(end_date, '%Y-%m-%d')

        # Fetch data for all sensors
        all_sensor_data = []
        successful_sensors = []
        
        for i, sensor_id in enumerate(sensor_ids):
            sensor_data_df = fetch_air_quality_history(sensor_id)
            
            if not sensor_data_df.empty:
                # Filter by date range
                filtered_df = sensor_data_df[
                    (sensor_data_df['data'] >= start_dt) &
                    (sensor_data_df['data'] < end_dt + pd.Timedelta(days=1))
                ].copy()
                
                if not filtered_df.empty:
                    # Add sensor metadata
                    filtered_df['sensor_id'] = sensor_id
                    filtered_df['sensor_type'] = sensor_types[i]
                    filtered_df['unit'] = sensor_units[i]
                    all_sensor_data.append(filtered_df)
                    successful_sensors.append((sensor_id, sensor_types[i], sensor_units[i]))

        if not all_sensor_data:
            return go.Figure().update_layout(
                title=f"No data available for any sensor at {station_info['nome_stazione']} in the selected date range",
                xaxis_visible=False, yaxis_visible=False, height=400
            ), empty_table_data, empty_table_columns, f"No data available for {station_info['nome_stazione']}", station_info_text

        # Combine all sensor data
        combined_df = pd.concat(all_sensor_data, ignore_index=True)
        
        # Create subplots - one per sensor type
        n_sensors = len(successful_sensors)
        subplot_titles = [f"{sensor_type} (ID: {sensor_id})" for sensor_id, sensor_type, unit in successful_sensors]
        
        fig = make_subplots(
            rows=n_sensors, cols=1,
            subplot_titles=subplot_titles,
            vertical_spacing=0.08,
            shared_xaxes=True
        )

        # Color palette for different sensors
        colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
        
        # Plot each sensor's data
        for i, (sensor_id, sensor_type, unit) in enumerate(successful_sensors):
            sensor_data = combined_df[combined_df['sensor_id'] == sensor_id].sort_values('data')
            color = colors[i % len(colors)]
            
            # Add main data trace
            fig.add_trace(
                go.Scatter(
                    x=sensor_data['data'],
                    y=sensor_data['valore'],
                    mode='lines+markers',
                    name=f'{sensor_type} Data',
                    line=dict(color=color, width=2),
                    marker=dict(size=3),
                    showlegend=True
                ),
                row=i+1, col=1
            )
            
            # Calculate and add trend line
            trend_dates, trend_values, slope, r_squared = calculate_trend_line(sensor_data)
            
            if trend_dates is not None:
                fig.add_trace(
                    go.Scatter(
                        x=trend_dates,
                        y=trend_values,
                        mode='lines',
                        name=f'{sensor_type} Trend',
                        line=dict(color=color, width=2, dash='dash'),
                        showlegend=True,
                        hovertemplate=f'<b>{sensor_type} Trend</b><br>' +
                                     'Date: %{x}<br>' +
                                     'Trend Value: %{y:.2f}<br>' +
                                     f'Slope: {slope:.4f}<br>' +
                                     f'R²: {r_squared:.3f}<extra></extra>'
                    ),
                    row=i+1, col=1
                )
            
            # Update y-axis title for each subplot
            fig.update_yaxes(title_text=f"{sensor_type} ({unit})", row=i+1, col=1)

        # Update layout
        fig.update_layout(
            title=f'All Sensor Data for Station: {station_info["nome_stazione"]} | {start_date} to {end_date}',
            height=max(400, 200 * n_sensors),  # Dynamic height based on number of sensors
            hovermode="x unified",
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            )
        )
        
        # Update x-axis title for bottom subplot only
        fig.update_xaxes(title_text="Date", row=n_sensors, col=1)

        # Prepare combined table data
        table_df = combined_df.copy()
        table_df['data'] = table_df['data'].dt.strftime('%Y-%m-%d %H:%M:%S')
        table_df = table_df.sort_values(['sensor_type', 'data'])
        
        # Create table columns
        table_columns = [
            {"name": "Date", "id": "data", "type": "text"},
            {"name": "Sensor Type", "id": "sensor_type", "type": "text"},
            {"name": "Sensor ID", "id": "sensor_id", "type": "numeric"},
            {"name": "Value", "id": "valore", "type": "numeric", "format": {"specifier": ".3f"}},
            {"name": "Unit", "id": "unit", "type": "text"},
        ]
        
        # Create info text
        total_records = len(table_df)
        sensor_summary = ", ".join([f"{st}: {len(combined_df[combined_df['sensor_type']==st])}" 
                                   for _, st, _ in successful_sensors])
        info_text = (
            f"Station: {station_info['nome_stazione']} | Date Range: {start_date} to {end_date} | "
            f"Total Records: {total_records} | Records per sensor: {sensor_summary}"
        )

        return fig, table_df.to_dict('records'), table_columns, info_text, station_info_text

    # Download callbacks (similar to before but for multi-sensor plots)
    @app.callback(
        Output("download-plot-png", "data"),
        Input("download-plot-btn", "n_clicks"),
        State('multi-sensor-plot', 'figure'),
        prevent_initial_call=True,
    )
    def download_plot_png(n_clicks, figure):
        if n_clicks > 0 and figure:
            import plotly.io as pio
            img_bytes = pio.to_image(figure, format="png", width=1400, height=800, scale=2)
            return dcc.send_bytes(img_bytes, "multi_sensor_station_plot.png")

    @app.callback(
        Output("download-plot-html", "data"),
        Input("download-plot-html-btn", "n_clicks"),
        State('multi-sensor-plot', 'figure'),
        prevent_initial_call=True,
    )
    def download_plot_html(n_clicks, figure):
        if n_clicks > 0 and figure:
            import plotly.io as pio
            html_str = pio.to_html(figure, include_plotlyjs='cdn')
            return dict(content=html_str, filename="multi_sensor_station_plot.html")
    


    @app.callback(
        Output("nome_tipo_sensore", "options"),
        Output("nome_tipo_sensore", "value"),
        Input("nome_tipo_sensore", "id"),  # Triggers on page load
    )
    def load_pollutant_options(_id):
        df_current = load_data_1()
        if df_current.empty:
            return [], None
        pollutants = sorted(df_current["nome_tipo_sensore"].unique())
        return [{"label": p, "value": p} for p in pollutants], pollutants[0]
    @app.callback(
        Output("provincia", "options"),
        Output("provincia", "value"),
        Input("nome_tipo_sensore", "value"),
    )

    def update_province_options(selected_pollutant):
        if not selected_pollutant:
            return [], None
        df_current = load_data_1()
        dff = df_current[df_current["nome_tipo_sensore"] == selected_pollutant]
        provinces = sorted(dff["provincia"].unique())
        value = provinces[0] if provinces else None
        return [{"label": p, "value": p} for p in provinces], value

    @app.callback(
        Output("comune", "options"),
        Output("comune", "value"),
        Input("nome_tipo_sensore", "value"),
        Input("provincia", "value"),
    )
    def update_comune_options(selected_pollutant, selected_province):
        if not selected_pollutant or not selected_province:
            return [], None
        df_current = load_data_1()
        dff = df_current[(df_current["nome_tipo_sensore"] == selected_pollutant) & (df_current["provincia"] == selected_province)]
        communes = sorted(dff["comune"].unique())
        value = communes[0] if communes else None
        return [{"label": c, "value": c} for c in communes], value

    @app.callback(
        Output("line", "figure"),
        Input("nome_tipo_sensore", "value"),
        Input("provincia", "value"),
        Input("comune", "value"),
    )
    def update_line_chart(nome_tipo_sensore, provincia, comune):
        if not all([nome_tipo_sensore, provincia, comune]):
            return px.line(title="Please select all parameters")

        df_current = load_data_1()
        dff = df_current[
            (df_current["nome_tipo_sensore"] == nome_tipo_sensore) &
            (df_current["provincia"] == provincia) &
            (df_current["comune"] == comune)
        ]
        if dff.empty:
            fig = px.line(title="No data available")
        else:
            dff["day"] = pd.to_datetime(dff["day"]).dt.strftime("%d %b %Y")
            fig = px.line(
                dff,
                x="day",
                y=["avg_value"],
                labels={"avg_value": "Value", "day": "Day"},
                title=f"Pollution level of {nome_tipo_sensore} in {comune}, {provincia}",
            )
        return fig

# Main application setup
if __name__ == '__main__':
    app = dash.Dash(__name__, suppress_callback_exceptions=True)
    app.layout = get_second_page_layout()
    register_second_page_callbacks(app)
    print("🚀 Multi-Sensor Dashboard running...")
    app.run_server(debug=True)