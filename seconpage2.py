import dash
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output, State
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime as dt # For handling date objects
from datetime import timedelta

# --- Configuration for Flask API ---
FLASK_API_URL = "http://127.0.0.1:5000"

# --- Data Fetching Functions (retained for clarity and potential reuse) ---
def fetch_sensors_data():
    """Fetches sensor metadata from the Flask API."""
    try:
        response = requests.get(f"{FLASK_API_URL}/sensors")
        response.raise_for_status() # Raise an exception for HTTP errors
        sensor_data = response.json()
        df = pd.DataFrame(sensor_data)
        if not df.empty:
            df['id_sensore'] = df['id_sensore'].astype(int)
        return df
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to Flask API at {FLASK_API_URL}.")
        print("Using demo sensor locations for the map/dropdown (for fetch_sensors_data).")
        # Fallback to a basic set of demo sensors
        return pd.DataFrame({
            "id_sensore": [1, 2],
            "nome_stazione": ["Demo North", "Demo South"],
            "provincia": ["XX", "YY"],
            "comune": ["Foo", "Bar"],
            "latitude": [45.47, 45.45], # Milan area coordinates
            "longitude": [9.18, 9.20],
        })
    except Exception as e:
        print(f"An unexpected error occurred while fetching sensor data: {e}")
        return pd.DataFrame() # Return empty DataFrame on other errors

def fetch_air_quality_history(sensor_id):
    """Fetches air quality data for a specific sensor from the Flask API."""
    try:
        data_response = requests.get(f"{FLASK_API_URL}/air_quality/{sensor_id}")
        data_response.raise_for_status()
        historical_data = data_response.json()
        df = pd.DataFrame(historical_data)
        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
            df = df.sort_values(by='data') # Ensure data is sorted
        return df
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to Flask API at {FLASK_API_URL} for air quality data.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error fetching air quality data for sensor {sensor_id}: {e}")
        return pd.DataFrame()


# --- Part 1: Function to get the layout of the second page ---
def get_second_page_layout():
    # --- Fetch Sensor Locations from Flask API ---
    sensor_df = fetch_sensors_data()

    # --- Load Sensor Status Data from CSV file ---
    status_df = pd.DataFrame() # Initialize empty DataFrame
    try:
        status_df = pd.read_csv('sensor_status_cache.csv')
        # Ensure 'id_sensore' is int for merging
        status_df['id_sensore'] = status_df['id_sensore'].astype(int)
        print("Successfully loaded sensor status from sensor_status_cache.csv.")
    except FileNotFoundError:
        print("Error: 'sensor_status_cache.csv' not found. Table will show placeholder data.")
        status_df = pd.DataFrame({'Column 1': ['Error: CSV not found'], 'Column 2': ['Please check path']})
    except Exception as e:
        print(f"Error loading sensor_status_cache.csv: {e}")
        status_df = pd.DataFrame({'Column 1': [f'Error loading CSV'], 'Column 2': [str(e)]})


    # --- Merge dataframes for comprehensive sensor information ---
    merged_df = pd.merge(sensor_df, status_df, on='id_sensore', how='left', suffixes=('_sensor', '_status'))

    # Fill NaN in 'has_data' for sensors not found in CSV (assume no data for them)
    if 'has_data' not in merged_df.columns:
        merged_df['has_data'] = False
    merged_df['has_data'] = merged_df['has_data'].fillna(False)
    # Convert 'has_data' to string for better display/coloring in Plotly
    merged_df['has_data_str'] = merged_df['has_data'].apply(lambda x: 'Available Data' if x else 'No Data')

    # Ensure 'data_count_2019' column exists for bar chart, default to 0 if not
    if 'data_count_2019' not in merged_df.columns:
        merged_df['data_count_2019'] = 0
    merged_df['data_count_2019'] = merged_df['data_count_2019'].fillna(0)


    # --- Create the Map ---
    MAP_CENTER_LAT = 45.4642 # Milan's approximate latitude
    MAP_CENTER_LON = 9.1900 # Milan's approximate longitude
    MARKER_SIZE = 12 # Define consistent marker size

    # Filter data for layering
    df_available = merged_df[merged_df['has_data_str'] == 'Available Data']
    df_no_data = merged_df[merged_df['has_data_str'] == 'No Data']

    # Create individual traces for layering
    trace_no_data = go.Scattermapbox(
        lat=df_no_data['latitude'],
        lon=df_no_data['longitude'],
        mode='markers',
        marker=dict(size=MARKER_SIZE, color='gray'),
        hoverinfo='text',
        text=[
            f"Station: {row['nome_stazione_sensor']}<br>ID: {row['id_sensore']}<br>Status: {row['has_data_str']}<br>"
            f"Comune: {row['comune_sensor']}<br>Provincia: {row['provincia_sensor']}<br>"
            f"Data Status: {row['status'] if pd.notna(row['status']) else 'N/A'}<br>"
            f"2019 Data Count: {int(row['data_count_2019']) if pd.notna(row['data_count_2019']) else 'N/A'}"
            for index, row in df_no_data.iterrows()
        ],
        name='No Data'
    )

    trace_available = go.Scattermapbox(
        lat=df_available['latitude'],
        lon=df_available['longitude'],
        mode='markers',
        marker=dict(size=MARKER_SIZE, color='blue'),
        hoverinfo='text',
        text=[
            f"Station: {row['nome_stazione_sensor']}<br>ID: {row['id_sensore']}<br>Status: {row['has_data_str']}<br>"
            f"Comune: {row['comune_sensor']}<br>Provincia: {row['provincia_sensor']}<br>"
            f"Data Status: {row['status'] if pd.notna(row['status']) else 'N/A'}<br>"
            f"2019 Data Count: {int(row['data_count_2019']) if pd.notna(row['data_count_2019']) else 'N/A'}"
            for index, row in df_available.iterrows()
        ],
        name='Available Data'
    )

    # Combine traces into a single Figure
    fig = go.Figure(data=[trace_no_data, trace_available])

    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_zoom=6, # Set zoom
        mapbox_center={"lat": MAP_CENTER_LAT, "lon": MAP_CENTER_LON},
        margin={"r":0,"t":0,"l":0,"b":0}, # Removed title space and all margins
        showlegend=True, # Keep legend for map to differentiate colors
        title=None # Explicitly ensure no title
    )

    # --- Create Bar Chart for Station Data Counts (now filtered and without legend) ---
    # Filter for stations with available data and non-zero data_count_2019
    filtered_merged_df_for_bar = merged_df[
        (merged_df['has_data_str'] == 'Available Data') &
        (merged_df['data_count_2019'] > 0)
    ].copy()

    bar_fig = px.bar(
        filtered_merged_df_for_bar.sort_values('data_count_2019', ascending=False),
        x='nome_stazione_sensor', # Use the correct column name from merged_df
        y='data_count_2019',
        labels={'nome_stazione_sensor': 'Station Name', 'data_count_2019': '2019 Data Count'},
        title='2019 Data Count per Station (Available Data Only - Click a Bar to See Detailed Plot)'
    )
    bar_fig.update_layout(xaxis_title="Station", yaxis_title="2019 Data Count", showlegend=False) # No legend for this chart

    # --- Prepare options for the station dropdown ---
    dropdown_options = [
        {'label': row['nome_stazione_sensor'], 'value': row['id_sensore']} # Use correct column name
        for _, row in filtered_merged_df_for_bar.iterrows()
    ]
    # Set an initial value if options exist
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

        html.H1("Sensor Status Dashboard Overview", style={'textAlign': 'center', 'marginTop': '30px', 'color': '#333'}),

        # --- Map Component ---
        html.Div([
            dcc.Graph(id='sensor-map', figure=fig)
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'margin': '20px auto', 'width': '90%'}),


        # --- Bar Chart for Station Selection (Available Data Only) ---
        html.Div([
            html.H2("Station Data Availability (2019)", style={'textAlign': 'center', 'marginBottom': '20px', 'color': '#555'}),
            dcc.Graph(id='station-bar-chart', figure=bar_fig)
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'margin': '20px auto', 'width': '90%'}),

        # --- Navbar for Station and Date Range Selection ---
        html.Div([
            html.H2("Explore Station Data by Range", style={'textAlign': 'center', 'marginBottom': '20px', 'color': '#555'}),
            html.Div([
                html.Label("Select Station:", style={'marginRight': '10px', 'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id='station-dropdown',
                    options=dropdown_options,
                    value=initial_dropdown_value, # Set initial value
                    placeholder="Select a station",
                    style={'width': '300px', 'marginRight': '20px'}
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
                    style={'width': 'auto'} # Adjust width automatically
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'flexWrap': 'wrap', 'padding': '10px'}),
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'margin': '20px auto', 'width': '90%', 'backgroundColor': '#f8f8f8'}),


        # --- Plot for Selected Station's Data (initially empty) ---
        html.Div([
            html.H2("Selected Station Data (2019)", style={'textAlign': 'center', 'marginBottom': '20px', 'color': '#555'}),
            dcc.Graph(id='station-data-plot') # This will be updated by callback
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'margin': '20px auto', 'width': '90%', 'minHeight': '400px'}), # minHeight to reserve space


        # --- Data Table ---
        html.Div([
            html.H2("Sensor Data Table", style={'textAlign': 'center', 'marginBottom': '20px', 'color': '#555'}),
            dash_table.DataTable(
                id='sensor-status-table',
                columns=[
                    {"name": col.replace('_sensor', '').replace('_status', ''), "id": col} # Clean up column names for display
                    for col in merged_df.columns
                    if col not in ['latitude', 'longitude', 'has_data_str', 'data_start', 'data_stop', 'id_stazione', 'location', 'nome_tipo_sensore', 'quota', 'storico', 'unita_misura', 'utm_est', 'utm_nord'] # Filter out more internal columns
                ],
                data=merged_df.to_dict('records'),
                style_table={'overflowX': 'auto', 'margin': '20px auto', 'width': '90%'},
                style_cell={
                    'height': 'auto',
                    'minWidth': '80px', 'width': '120px', 'maxWidth': '180px',
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
                    },
                    {
                        'if': {
                            'filter_query': '{has_data} eq "False"',
                        },
                        'backgroundColor': '#ffe0e0',
                        'color': 'black'
                    }
                ],
                export_format='xlsx',
                filter_action="native",
                sort_action="native",
                page_action="native",
                page_size=10,
            )
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'margin': '20px'})
    ])


# --- Part 2: Function to register Dash Callbacks ---
def register_second_page_callbacks(app):
    # Callback to update the detailed station data plot
    @app.callback(
        Output('station-data-plot', 'figure'),
        Input('station-bar-chart', 'clickData'), # Input from clicking bar chart
        Input('station-dropdown', 'value'),     # Input from dropdown selection
        Input('date-range-picker', 'start_date'),
        Input('date-range-picker', 'end_date')
    )
    def update_station_data_plot(bar_chart_clickData, dropdown_station_id, start_date, end_date):
        # Initial empty figure or message
        empty_fig = go.Figure().update_layout(
            title="Select a station from the dropdown or click a bar to see detailed 2019 data.",
            xaxis_visible=False, yaxis_visible=False,
            height=350 # Consistent height
        )

        selected_id = None
        selected_station_name = "Selected Station" # Default for titles

        ctx = dash.callback_context # Get context to see which input triggered the callback

        # If no input has triggered the callback yet (initial load), return empty figure
        if not ctx.triggered:
            print("Callback triggered by initial load (no input).")
            return empty_fig

        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        # Determine which input triggered the callback and get the station ID
        if trigger_id == 'station-bar-chart' and bar_chart_clickData:
            # Click on bar chart overrides dropdown for immediate action
            selected_station_name_from_bar = bar_chart_clickData['points'][0]['x']
            print(f"Plot Callback: Bar chart click: Station '{selected_station_name_from_bar}' clicked.")

            # Re-fetch sensor_df to ensure we have the latest mapping from nome_stazione to id_sensore
            sensor_df_for_id_lookup = fetch_sensors_data() # Use the shared fetch function
            if sensor_df_for_id_lookup.empty:
                print("Plot Callback Error: Could not fetch sensor metadata for ID lookup after bar click.")
                return go.Figure().update_layout(
                    title=f"Error: Could not retrieve station ID for '{selected_station_name_from_bar}'.",
                    xaxis_visible=False, yaxis_visible=False, height=350)

            found_sensor = sensor_df_for_id_lookup[
                sensor_df_for_id_lookup['nome_stazione'].str.lower() == selected_station_name_from_bar.lower()
            ]
            if not found_sensor.empty:
                selected_id = found_sensor['id_sensore'].iloc[0]
                selected_station_name = found_sensor['nome_stazione'].iloc[0] # Use actual station name from df
                print(f"Plot Callback: Bar chart resolved ID {selected_id} for '{selected_station_name}'.")
            else:
                print(f"Plot Callback: Bar chart: Could not resolve ID for '{selected_station_name_from_bar}'.")
                return empty_fig

        elif trigger_id == 'station-dropdown' and dropdown_station_id is not None:
            # Dropdown selected
            selected_id = dropdown_station_id

            # Get station name from ID for title
            sensor_df_for_name_lookup = fetch_sensors_data() # Use the shared fetch function
            if sensor_df_for_name_lookup.empty:
                print("Plot Callback Error: Could not fetch sensor metadata for name lookup after dropdown change.")
                selected_station_name = f"Station ID: {selected_id}" # Fallback
            else:
                found_name = sensor_df_for_name_lookup[sensor_df_for_name_lookup['id_sensore'] == selected_id]
                if not found_name.empty:
                    selected_station_name = found_name['nome_stazione'].iloc[0]
                    print(f"Plot Callback: Dropdown: Selected ID {selected_id}, name '{selected_station_name}'.")
                else:
                    selected_station_name = f"Station ID: {selected_id}"
                    print(f"Plot Callback: Dropdown: Selected ID {selected_id}, name not found (using ID).")
        else:
            # Neither bar chart nor dropdown explicitly triggered/selected a valid station
            print("Plot Callback: No valid station selection input to process or initial load with no default.")
            return empty_fig

        if selected_id is None:
            print("Plot Callback: Selected ID is None, returning empty figure.")
            return empty_fig

        # Ensure date range is valid
        if not (start_date and end_date):
            print("Plot Callback: Date range not fully selected.")
            return go.Figure().update_layout(
                title=f"Please select a valid date range for {selected_station_name}.",
                xaxis_visible=False, yaxis_visible=False, height=350)

        # Convert date strings to datetime objects
        start_dt = dt.strptime(start_date, '%Y-%m-%d')
        end_dt = dt.strptime(end_date, '%Y-%m-%d')

        print(f"Plot Callback: Fetching data for sensor ID {selected_id} from {start_date} to {end_date}...")

        # --- Fetch historical data for the selected sensor using the /air_quality endpoint ---
        historical_df = fetch_air_quality_history(selected_id)

        if historical_df.empty:
            print(f"Plot Callback: No air quality data returned from API for sensor ID {selected_id}.")
            return go.Figure().update_layout(
                title=f"No data available from API for {selected_station_name}",
                xaxis_visible=False, yaxis_visible=False, height=350)

        # Filter data within the selected 2019 date range
        filtered_df = historical_df[
            (historical_df['data'] >= start_dt) &
            (historical_df['data'] < end_dt + pd.Timedelta(days=1)) # Corrected to include entire end day
        ].copy() # Use .copy() to avoid SettingWithCopyWarning

        if filtered_df.empty:
            print(f"Plot Callback: No data found for sensor ID {selected_id} within the range {start_date} to {end_date}.")
            return go.Figure().update_layout(
                title=f"No data for {selected_station_name} in selected range: {start_date} to {end_date}",
                xaxis_visible=False, yaxis_visible=False, height=350)

        print(f"Plot Callback: Successfully fetched and filtered {len(filtered_df)} data points for sensor {selected_id}.")

        # Create the line plot using plotly.express
        line_fig = px.line(
            filtered_df.sort_values(by='data'), # Ensure data is sorted for line plot
            x='data',
            y='valore', # Assuming 'valore' is the measurement value column
            title=f'Measurement Data for Station: {selected_station_name} (ID: {selected_id}) from {start_date} to {end_date}',
            labels={'data': 'Date', 'valore': 'Measurement Value'},
            line_shape='linear'
        )
        line_fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Measurement Value",
            hovermode="x unified", # Shows all y-values at a given x on hover
            height=350
        )
        return line_fig


# --- Part 3: Main application setup ---
# This is the entry point for your Dash app
if __name__ == '__main__':
    # Initialize Dash app
    app = dash.Dash(__name__, suppress_callback_exceptions=True) # suppress_callback_exceptions is useful for multi-page apps

    # Set the layout for the app
    app.layout = get_second_page_layout()

    # Register the callbacks for interactivity
    register_second_page_callbacks(app)

    # Run the Dash server
    print("🚀 Dash Dashboard running...")
    app.run_server(debug=True)