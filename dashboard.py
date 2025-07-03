import dash
from dash import dcc, html, dash_table
from dash.dependencies import Output, Input, State
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import requests
import json
import geopandas # Import geopandas
import random # Import for random selection
from secondpage import get_second_page_layout
from secondpage import register_second_page_callbacks


# --- API Configuration ---
FLASK_API_URL = "http://127.0.0.1:5000"

def get_station_locations():
    """
    Fetches station location data from the Flask API's /sensors endpoint.
    """
    try:
        response = requests.get(f"{FLASK_API_URL}/sensors")
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        return df

    except requests.exceptions.RequestException as e:
        print(f"Error fetching station data from API: {e}")
        return pd.DataFrame()
    except json.JSONDecodeError:
        print("Error decoding JSON from API response. Is the API returning valid JSON?")
        return pd.DataFrame()

def get_random_stations_with_selected(num_stations_to_show=10, selected_station_name="Milano v.Marche"):
    """
    Fetches all station locations, includes a specific selected station if available,
    and then adds random stations to reach the desired number.
    """
    all_stations = get_station_locations()
    if all_stations.empty:
        return pd.DataFrame()

    selected_station_df = pd.DataFrame()
    other_stations_df = pd.DataFrame()

    # Try to find the selected station
    if selected_station_name:
        selected_station_df = all_stations[all_stations['nome_stazione'] == selected_station_name]
        
    if not selected_station_df.empty:
        # If selected station found, remove it from the pool for random selection
        other_stations_df = all_stations[all_stations['nome_stazione'] != selected_station_name]
        num_random = num_stations_to_show - 1 # Need one less random station
    else:
        # If selected station not found or not specified, select all randomly
        other_stations_df = all_stations.copy()
        num_random = num_stations_to_show

    # Ensure we don't try to sample more than available stations
    num_random = min(num_random, len(other_stations_df))

    # Get random stations
    if num_random > 0:
        random_stations = other_stations_df.sample(n=num_random, random_state=1) # Consistent random selection
        if not selected_station_df.empty:
            final_stations = pd.concat([selected_station_df, random_stations]).drop_duplicates(subset=['id_sensore'])
        else:
            final_stations = random_stations
    else:
        final_stations = selected_station_df

    # If, after all this, final_stations is still empty, and all_stations is not,
    # just pick the first 'num_stations_to_show' stations.
    if final_stations.empty and not all_stations.empty:
        final_stations = all_stations.head(num_stations_to_show)
        
    return final_stations


def get_station_air_quality_data(station_id=None, default_station_name="Milano v.Marche"):
    """
    Fetches air quality data for a specific station from the Flask API.
    If station_id is None, tries to get data for the default_station_name.
    If default_station_name not found, falls back to the first available station.
    """
    target_station_id = station_id

    if target_station_id is None:
        all_stations = get_station_locations()
        if not all_stations.empty:
            # Try to find the default station
            default_station = all_stations[all_stations['nome_stazione'] == default_station_name]
            if not default_station.empty:
                target_station_id = default_station.iloc[0]['id_sensore']
            else:
                # Fallback to the first available station if default not found
                print(f"'{default_station_name}' not found. Defaulting to the first available station.")
                target_station_id = all_stations.iloc[0]['id_sensore']
        else:
            return pd.DataFrame(), None # No stations available at all

    try:
        response = requests.get(f"{FLASK_API_URL}/air_quality/{target_station_id}")
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data'])
            df = df[df['data'].dt.year == 2019]
        
        return df, target_station_id

    except requests.exceptions.RequestException as e:
        print(f"Error fetching air quality data for station {target_station_id}: {e}")
        return pd.DataFrame(), target_station_id
    except json.JSONDecodeError:
        print("Error decoding JSON from API response.")
        return pd.DataFrame(), target_station_id

# Function to load shapefile data
def load_shapefile(filepath):
    try:
        gdf = geopandas.read_file(filepath)
        # Ensure the GeoDataFrame is in WGS84 (EPSG:4326) CRS, which Plotly uses
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        return gdf
    except Exception as e:
        print(f"Error loading shapefile: {e}")
        return None

# --- Dash App Initialization ---
app = dash.Dash(__name__, suppress_callback_exceptions=True)
register_second_page_callbacks(app)

# Define common styles
COLORS = {
    'background': '#f8f9fa',  # Light gray background
    'text': '#343a40',        # Dark gray text
    'primary': '#007bff',     # Blue for primary elements
    'secondary': '#6c757d',   # Gray for secondary elements
    'accent': '#28a745',      # Green for accents (e.g., success message)
    'danger': '#dc3545'       # Red for errors
}

HEADER_STYLE = {
    'textAlign': 'center',
    'color': 'white',
    'backgroundColor': COLORS['primary'],
    'padding': '20px',
    'marginBottom': '30px',
    'borderRadius': '8px',
    'boxShadow': '0 4px 8px rgba(0, 0, 0, 0.1)'
}

SECTION_HEADER_STYLE = {
    'textAlign': 'center',
    'color': COLORS['text'],
    'marginTop': '40px',
    'marginBottom': '20px',
    'fontSize': '2.2em',
    'fontWeight': 'bold',
    'borderBottom': f'2px solid {COLORS["primary"]}',
    'paddingBottom': '10px'
}

CONTAINER_STYLE = {
    'maxWidth': '1200px',
    'margin': 'auto',
    'padding': '20px',
    'backgroundColor': 'white',
    'borderRadius': '8px',
    'boxShadow': '0 4px 12px rgba(0, 0, 0, 0.1)',
    'fontFamily': 'Arial, sans-serif'
}

INPUT_STYLE = {
    'width': '100%',
    'padding': '12px',
    'margin': '8px 0',
    'display': 'inline-block',
    'border': f'1px solid {COLORS["secondary"]}',
    'borderRadius': '4px',
    'boxSizing': 'border-box',
    'fontSize': '16px'
}

BUTTON_STYLE = {
    'backgroundColor': COLORS['primary'],
    'color': 'white',
    'padding': '12px 25px',
    'border': 'none',
    'borderRadius': '4px',
    'cursor': 'pointer',
    'fontSize': '16px',
    'marginTop': '20px',
    'fontWeight': 'bold',
    'transition': 'background-color 0.3s ease'
}

# Define the layout of the main application
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
], style={'backgroundColor': COLORS['background']}) # Set overall background

# Define the layout for the index (login) page with the map
index_page = html.Div([
    html.Div(
        [
            html.H1("Welcome to the Air Quality Monitoring Dashboard", style={'marginBottom': '10px'}),
            html.P("Explore real-time air quality data and station locations."),
            # html.H5("🔍 This homepage provides a limited preview of our dataset and analysis tools. To access the complete dataset, advanced features, and full analytical results, please log in.", style={'textAlign': 'center', 'marginBottom': '20px'}),
        ],
        style=HEADER_STYLE
    ),
    html.Div(
        [

            html.H4("🔍 This homepage provides a limited preview of our dataset and analysis tools. To access the complete dataset, advanced features, and full analytical results, please log in.", style={'textAlign': 'center', 'marginBottom': '20px'}),
        ],
    ),

    html.Div([ # Login Card
        
        html.H3("Login to Access Full Features", style={'textAlign': 'center', 'color': COLORS['text'], 'marginBottom': '20px'}),
        html.Div(
            dcc.Input(
                id="user", 
                type="text", 
                placeholder="Enter Username", 
                style={**INPUT_STYLE, 'borderColor': COLORS['primary']}
            )
        ),
        html.Div(
            dcc.Input(
                id="passw", 
                type="password", 
                placeholder="Enter Password", 
                style={**INPUT_STYLE, 'borderColor': COLORS['primary']}
            )
        ),
        html.Div(
            html.Button('Verify', id='verify', n_clicks=0, 
                        style={**BUTTON_STYLE, 'width': 'auto', 'display': 'block', 'margin': '20px auto 0 auto'}),
            style={'textAlign': 'center'}
        ),
        html.Div(id='output1', style={'textAlign': 'center', 'marginTop': '15px'})
    ], style={
        'width': '400px', 'margin': '40px auto', 'padding': '30px', 
        'border': f'1px solid {COLORS["secondary"]}', 'borderRadius': '8px', 
        'boxShadow': '0 2px 5px rgba(0,0,0,0.05)', 'backgroundColor': 'white'
    }),

    html.Hr(style={'borderColor': COLORS['secondary'], 'marginTop': '50px', 'marginBottom': '50px'}),

    html.H2("Random Station Locations", style=SECTION_HEADER_STYLE), # Updated title
    dcc.Loading( # Add a loading indicator for the map
        id="loading-map-initial",
        type="default",
        children=dcc.Graph(id='initial-map', style={'height': '600px'})
    ),

    html.Hr(style={'borderColor': COLORS['secondary'], 'marginTop': '50px', 'marginBottom': '50px'}),

    html.H2("Station Preview - 2019 Data", style=SECTION_HEADER_STYLE),
    
    # Chart Section for One Station
    html.Div([
        html.H3(id="station-title", style={'textAlign': 'center', 'color': COLORS['text'], 'marginBottom': '20px'}),
        dcc.Loading(
            id="loading-station-chart",
            type="default",
            children=dcc.Graph(id='station-preview-chart', style={'height': '450px'})
        )
    ], style={'marginBottom': '30px', 'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.05)'}),

    # Table Section for One Station (Air Quality Data)
    html.Div([
        html.H3("Station Data Sample (2019)", style={'textAlign': 'center', 'color': COLORS['text'], 'marginBottom': '20px'}),
        dcc.Loading(
            id="loading-station-table",
            type="default",
            children=html.Div(id='station-preview-table')
        )
    ], style={'marginBottom': '30px', 'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.05)'}),

    html.Hr(style={'borderColor': COLORS['secondary'], 'marginTop': '50px', 'marginBottom': '50px'}),

    # Table Section for All Station Info (New Section)
    html.H2("Details of the Selected Station (Milano v.Marche)", style=SECTION_HEADER_STYLE), # Updated title
    html.Div([
        html.H3(id="chosen-station-info-title", style={'textAlign': 'center', 'color': COLORS['text'], 'marginBottom': '20px'}),
        dcc.Loading(
            id="loading-chosen-station-info",
            type="default",
            children=html.Div(id='chosen-station-info-table')
        )
    ], style={'marginBottom': '30px', 'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.05)'}),


], style=CONTAINER_STYLE)

# Define the layout for the next (main dashboard) page
next_page = html.Div([
    html.Div(dcc.Link('Log out', href='/', style={
        'color': COLORS['primary'], 'fontFamily': 'serif', 'fontWeight': 'bold', 
        "textDecoration": "none", 'fontSize': '20px', 'padding': '15px 20px', 
        'borderRadius': '5px', 'border': f'1px solid {COLORS["primary"]}', 
        'display': 'inline-block', 'transition': 'all 0.3s ease'
    }), style={'paddingLeft': '80%', 'paddingTop': '10px'}),
    html.H1(children="Welcome to Your Dashboard!", style={
        'color': COLORS['primary'], 'textAlign': 'center', 'justifyContent': 'center', 
        'paddingTop': '50px', 'fontWeight': 'bold', 'fontFamily': 'courier', 
        'paddingLeft': '1px'
    }),
    html.P("This is your secure dashboard content. You can add more interactive elements here.",
           style={'textAlign': 'center', 'marginTop': '20px', 'color': COLORS['text']})
], style={'padding': '20px', 'backgroundColor': COLORS['background'], 'minHeight': '100vh'})

# Callback for handling user login verification
@app.callback(
    Output('output1', 'children'),
    Input('verify', 'n_clicks'),
    State('user', 'value'),
    State('passw', 'value')
)
def update_output(n_clicks, uname, passw):
    if n_clicks is None or n_clicks == 0:
        return ''

    credentials = {'majid': '123456', 'ali':"1219"} # Set 'majid' as username and '123456' as password

    if not uname or not passw:
        return html.Div(children='Please enter both username and password.',
                        style={'color': COLORS['danger'], 'fontWeight': 'bold'})

    if uname not in credentials:
        return html.Div(children='Incorrect Username',
                        style={'color': COLORS['danger'], 'fontWeight': 'bold'})

    if credentials[uname] == passw:
        return html.Div(dcc.Link('Access Granted! Click to proceed', href='/next_page',
                                 style={'color':COLORS['accent'],'fontFamily': 'serif', 'fontWeight': 'bold', "textDecoration": "none",'fontSize':'20px'}),
                        style={'marginTop':'20px'})
    else:
        return html.Div(children='Incorrect Password',
                        style={'color': COLORS['danger'], 'fontWeight': 'bold'})

# Callback to generate the map on the initial (login) page
@app.callback(
    Output('initial-map', 'figure'),
    Input('url', 'pathname')
)
def update_initial_map(pathname):
    if pathname == '/':
        station_data_display = get_random_stations_with_selected(num_stations_to_show=10, selected_station_name="Milano v.Marche")
        shapefile_gdf = load_shapefile('geo_export_4aad674f-e9ac-4fd7-a917-0329635f0de9.shp')

        # Create an empty figure to start
        fig = go.Figure()

        if station_data_display.empty and shapefile_gdf is None:
            fig.update_layout(
                title="<span style='color: red;'>Error: Could not load station and shapefile data.</span><br>Is the Flask API running and shapefile correct?",
                height=500
            )
            return fig

        # Add station markers if data is available
        if not station_data_display.empty:
            
            colors = []
            sizes = []
            line_colors = []
            line_widths = []
            
            # Determine the station ID to highlight (Milano v.Marche, or the first in the list if not found)
            highlight_station_name = "Milano v.Marche"
            highlight_station_id = None
            
            milano_marche_station = station_data_display[station_data_display['nome_stazione'] == highlight_station_name]
            if not milano_marche_station.empty:
                highlight_station_id = milano_marche_station.iloc[0]['id_sensore']
            elif not station_data_display.empty: # Fallback to first station if Milano v.Marche not in the displayed list
                highlight_station_id = station_data_display.iloc[0]['id_sensore']


            for index, row in station_data_display.iterrows(): # Iterate over the selected random data
                status = row.get('status', 'Unknown')
                if status == 'Active':
                    color = 'green'
                elif status == 'Inactive':
                    color = 'red'
                elif status == 'Maintenance':
                    color = 'orange'
                else:
                    color = 'blue'
                
                size = 12
                marker_line_color = 'white'
                marker_line_width = 1

                if row['id_sensore'] == highlight_station_id:
                    size = 20  # Make larger
                    marker_line_color = 'purple' # Bold border
                    marker_line_width = 3 # Thicker border
                    color = 'cyan' # Distinct color for the chosen station

                colors.append(color)
                sizes.append(size)
                line_colors.append(marker_line_color) 
                line_widths.append(marker_line_width) 

            fig.add_trace(go.Scattermapbox(
                lat=station_data_display['latitude'], 
                lon=station_data_display['longitude'], 
                mode='markers',
                marker=go.scattermapbox.Marker(
                    size=sizes,
                    color=colors,
                    opacity=0.8,
                    # line=dict(width=line_widths, color=line_colors) 
                ),
                # text=[f"Station: {row['nome_stazione']}<br>ID: {row['id_sensore']}<br>Province: {row['provincia']}<br>Municipality: {row['comune']}{'<br>Status: ' + row['status'] if 'status' in station_data_display.columns else ''}"
                #       for index, row in station_data_display.iterrows()], 
                # hoverinfo='text',
                # name='Stations'
            ))

        # Add shapefile polygons if data is available
        if shapefile_gdf is not None:
            geojson_data = json.loads(shapefile_gdf.to_json())
            locations = list(shapefile_gdf.index)
            z_values = [i for i in range(len(shapefile_gdf))]

            fig.add_trace(go.Choroplethmapbox(
                geojson=geojson_data,
                locations=locations,
                z=z_values,
                colorscale="gray", 
                marker_opacity=0.5,
                marker_line_width=3,
                marker_line_color='red',
                # text=[f"Region: {row['NAME']}" for idx, row in shapefile_gdf.iterrows()] if 'NAME' in shapefile_gdf.columns else ['Region'] * len(shapefile_gdf),
                hoverinfo='text',
                name='Regions',
                colorbar=dict(tickvals=[],ticktext=[],thickness=0.2)  # <--- Add this line to hide the colorbar
            ))

        fig.update_layout(
            mapbox_style="open-street-map",
            mapbox_zoom=7,
            mapbox_center={"lat": 45.4642, "lon": 9.1900}, # Centered around Milan
            margin={"r":0,"t":0,"l":0,"b":0},
            height=500,
            title_text="Current Station Locations", # Updated map title
            showlegend = False,
        )
        return fig
    return go.Figure()

# Callback to generate the station preview chart
@app.callback(
    [Output('station-preview-chart', 'figure'),
      Output('station-title', 'children')],
    Input('url', 'pathname')
)
def update_station_chart(pathname):
    if pathname == '/':
        aq_data, station_id_used = get_station_air_quality_data(station_id=None, default_station_name="Milano v.Marche") # Pass None to use default logic
        
        station_name = "Station Preview"
        if station_id_used:
            all_stations = get_station_locations()
            station_info = all_stations[all_stations['id_sensore'] == station_id_used]
            if not station_info.empty:
                station_name = f"Station: {station_info.iloc[0]['nome_stazione']} (ID: {station_id_used})"
        
        if aq_data.empty:
            fig = go.Figure()
            fig.update_layout(
                title="<span style='color: red;'>No 2019 data available for this station</span>",
                height=400
            )
            return fig, station_name

        # Create a time series chart for the station
        fig = go.Figure()
        
        if 'data' in aq_data.columns and 'valore' in aq_data.columns:
            # Sort by date
            aq_data_sorted = aq_data.sort_values('data')
            
            fig.add_trace(go.Scatter(
                x=aq_data_sorted['data'],
                y=aq_data_sorted['valore'],
                mode='lines+markers',
                name=f'Air Quality Values',
                line=dict(width=2, color=COLORS['primary']),
                marker=dict(size=3, color=COLORS['danger'])
            ))
        
        fig.update_layout(
            title="Air Quality Measurements (2019)",
            xaxis_title="Date",
            yaxis_title="Air Quality Value",
            height=400,
            margin={"r":0,"t":50,"l":0,"b":0},
            showlegend=False,
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        return fig, station_name
    return go.Figure(), "Station Preview"

# Callback to generate the station preview table (Air Quality Data)
@app.callback(
    Output('station-preview-table', 'children'),
    Input('url', 'pathname')
)
def update_station_table(pathname):
    if pathname == '/':
        aq_data, station_id_used = get_station_air_quality_data(station_id=None, default_station_name="Milano v.Marche") # Pass None to use default logic
        
        if aq_data.empty:
            return html.Div([
                html.P("No 2019 data available for this station.",
                        style={'color': COLORS['danger'], 'textAlign': 'center', 'padding': '20px'})
            ])

        # Prepare data for the table - show recent records
        table_data = aq_data.copy()
        
        # Sort by date and take a sample
        table_data = table_data.sort_values('data', ascending=False).head(20)
        
        # Format the datetime for better display
        if 'data' in table_data.columns:
            table_data['data'] = table_data['data'].dt.strftime('%Y-%m-%d %H:%M:%S')

        # Create columns for the table
        columns = []
        for col in table_data.columns:
            columns.append({
                'name': col.replace('_', ' ').title(),
                'id': col,
                'type': 'numeric' if col in ['valore', 'idsensore'] else 'text'
            })

        return dash_table.DataTable(
            data=table_data.to_dict('records'),
            columns=columns,
            style_cell={
                'textAlign': 'left',
                'padding': '10px',
                'fontFamily': 'Arial, sans-serif',
                'fontSize': '14px',
                'borderBottom': f'1px solid {COLORS["secondary"]}'
            },
            style_header={
                'backgroundColor': COLORS['primary'],
                'color': 'white',
                'fontWeight': 'bold',
                'textAlign': 'center',
                'fontSize': '16px'
            },
            style_data={
                'backgroundColor': 'white',
                'color': COLORS['text']
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': '#f2f2f2' # Light grey for odd rows
                }
            ],
            page_size=10,
            sort_action="native",
            filter_action="native",
            style_table={'overflowX': 'auto', 'border': f'1px solid {COLORS["secondary"]}', 'borderRadius': '8px'}
        )
    
    return html.Div()

# NEW CALLBACK: Display detailed info for the chosen station
@app.callback(
    [Output('chosen-station-info-table', 'children'),
     Output('chosen-station-info-title', 'children')],
    Input('url', 'pathname')
)
def update_chosen_station_info_table(pathname):
    if pathname == '/':
        all_stations = get_station_locations()
        
        if all_stations.empty:
            return html.Div([
                html.P("No station location data available.",
                        style={'color': COLORS['danger'], 'textAlign': 'center', 'padding': '20px'})
            ]), "Details of the Chosen Station"

        chosen_station_info_df = pd.DataFrame()
        chosen_station_name_for_title = "Chosen Station"

        # Try to find "Milano v.Marche"
        milano_marche_station = all_stations[all_stations['nome_stazione'] == "Milano v.Marche"]
        
        if not milano_marche_station.empty:
            chosen_station_info_df = milano_marche_station.iloc[[0]]
            chosen_station_name_for_title = milano_marche_station.iloc[0].get('nome_stazione', 'N/A')
        else:
            # If "Milano v.Marche" not found, default to the first random station picked for the map
            # This requires calling the same random selection logic
            random_stations_display = get_random_stations_with_selected(num_stations_to_show=10, selected_station_name="Milano v.Marche")
            if not random_stations_display.empty:
                chosen_station_info_df = random_stations_display.iloc[[0]]
                chosen_station_name_for_title = random_stations_display.iloc[0].get('nome_stazione', 'N/A')
            else:
                return html.Div([
                    html.P("No station location data available to display details.",
                            style={'color': COLORS['danger'], 'textAlign': 'center', 'padding': '20px'})
                ]), "Details of the Chosen Station"

        # Prepare columns for the table
        columns = []
        for col in chosen_station_info_df.columns:
            columns.append({
                'name': col.replace('_', ' ').title(),
                'id': col,
                'type': 'text' # All are text for this info table
            })

        return dash_table.DataTable(
            data=chosen_station_info_df.to_dict('records'),
            columns=columns,
            style_cell={
                'textAlign': 'left',
                'padding': '10px',
                'fontFamily': 'Arial, sans-serif',
                'fontSize': '14px',
                'borderBottom': f'1px solid {COLORS["secondary"]}'
            },
            style_header={
                'backgroundColor': COLORS['primary'],
                'color': 'white',
                'fontWeight': 'bold',
                'textAlign': 'center',
                'fontSize': '16px'
            },
            style_data={
                'backgroundColor': 'white',
                'color': COLORS['text']
            },
            style_table={'overflowX': 'auto', 'border': f'1px solid {COLORS["secondary"]}', 'borderRadius': '8px'}
        ), f"Details for Station: {chosen_station_name_for_title}"
    
    return html.Div(), "Details of the Chosen Station"

# Callback for navigating between pages based on URL
@app.callback(Output('page-content', 'children'),
              Input('url', 'pathname'))
def display_page(pathname):
    if pathname == '/next_page':
        return get_second_page_layout()  # Use your second page layout function
    else:
        return index_page

if __name__ == '__main__':
    app.run(port=4070, debug=True)