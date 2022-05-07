import io
import re
import base64
import pandas as pd
from datetime import datetime
import plotly.graph_objs as go


import dash_bootstrap_components as dbc
from dash import Dash, html, dcc, dash_table
from dash.dependencies import Input, Output, State

def create_dash_app(flask_app):
    external_stylesheets = [dbc.themes.BOOTSTRAP]
    dashapp = Dash(__name__,
                   server=flask_app,
                   url_base_pathname='/dashboard/',
                   external_stylesheets=external_stylesheets
                   )

    dashapp.layout = html.Div([
        dbc.NavbarSimple(
            children=[dbc.NavItem(dbc.NavLink("Page 1", href="#"))],
            brand="Racing x Data",
            brand_href="#",
            color="primary",
            dark=True
        ),
        dbc.Container([
        html.H4('Data Import'),
        dbc.Row([
            dbc.Col([html.H6("Upload data", style={"textAlign": "center"}),
                     dcc.Upload(id='upload-data',
                                children=html.Div(['Drag and Drop or ',
                                                  html.A('Select a File', style={'color': 'blue'})]),
                                style={'height': '60px',
                                      'lineHeight': '60px',
                                      'borderWidth': '1px',
                                      'borderStyle': 'dashed',
                                      'borderRadius': '5px',
                                      'textAlign': 'center',
                                      'float': 'center'},
                                multiple=False  # Disallow multiple files to be uploaded
                                )
                     ],
                    width=4),

            dbc.Col([html.H6("Column Separator"),
                     dbc.RadioItems(id='column-separator-id',
                                    options=[
                                        {'label': 'Comma (,)', 'value': ','},
                                        {'label': 'Semicolon (;)', 'value': ';'}],
                                    value=';')],
                    width=1),

            dbc.Col(html.Div(id='output-filename'))
            ], align="center"),
        html.Hr(),  # horizontal line

        html.H4('Data Preview'),
        html.Div(id='output-datatable'),
        html.Hr(),  # horizontal line

        html.H4('Lap Analysis'),
        html.Div(id='best-lap-table'),
        html.Hr(),  # horizontal line

        html.H4('Sequence Analysis'),
        html.Div(id='lap-slider-output'),
        dbc.Col(html.Div(id='output-sequence-analysis')),
        html.Hr(),  # horizontal line

        ], fluid=True, style={"height": "100vh"})
    ])

    @dashapp.callback(Output('output-filename', 'children'),
                      Input('upload-data', 'filename'))
    def parse_filename(filename):
        if filename is not None:
            if filename.endswith(".csv"):
                return dbc.Alert(f'Imported file: {filename}', color="success")
            else:
                return dbc.Alert('ERROR: Unknown file type. Please upload a .csv file!', color="danger")

    def parse_contents(contents, filename, column_separator):
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), sep=column_separator)
            elif filename.endswith('.xlsx'):
                df = pd.read_excel(io.BytesIO(decoded))
            else:
                return html.Div(['ERROR: Unknown file type. Please upload either a .csv or an .xlsx file!'])
        except Exception as e:
            print(e)
            return html.Div(['ERROR: Could not read the data...'])

        return html.Div([
            dash_table.DataTable(
                data=df.to_dict('records'),
                columns=[{'name': i, 'id': i} for i in df.columns],
                page_size=5,
                style_data={'whiteSpace': 'normal',
                            'height': 'auto'},
                style_table={'overflowX': 'scroll'}),
            dcc.Store(id='stored-data', data=df.to_dict('records'))
        ])

    def unify_timeformat(raw_time: str) -> str:
        raw_time = str(raw_time)
        correct_format = re.compile('\d{1,2}:\d{2}\.\d{1,5}')
        incorrect_format = re.compile('\d{1,2}\.\d{1,5}')
        if correct_format.match(raw_time) is not None:
            return raw_time
        elif incorrect_format.match(raw_time):
            return f"00:{raw_time}"


    @dashapp.callback(Output('output-datatable', 'children'),
                      Input('upload-data', 'contents'),
                      State('upload-data', 'filename'),
                      Input('column-separator-id', 'value'))
    def show_inital_table(list_of_contents, list_of_names, separator):
        if list_of_contents is not None:
            children = [parse_contents(list_of_contents, list_of_names, separator)]
            return children

    @dashapp.callback(Output('best-lap-table', 'children'),
                      Input('stored-data', 'data'))
    def best_lap(raw_data: dict):
        df = pd.DataFrame(raw_data)
        for time_column in ["LAP_TIME", "S1", "S2", "S3", "S1_LARGE", "S2_LARGE", "S3_LARGE"]:
            df[time_column] = df[time_column].apply(unify_timeformat)
            df[time_column] = pd.to_datetime(df[time_column], format='%M:%S.%f').dt.time

        # fastest lap per driver
        df_fastest_lap_per_driver = df.groupby(["NUMBER", "DRIVER_NAME"]).agg({"LAP_TIME": "min"}).reset_index()
        df_fastest_lap_per_driver.columns = ["NUMBER", "DRIVER_NAME", "LAP_TIME"]
        df_fastest_lap_per_driver["Fastest_lap_per_driver"] = df_fastest_lap_per_driver["LAP_TIME"]

        df_fastest_lap_full_data = pd.merge(df, df_fastest_lap_per_driver, how="inner",
                                            on=["NUMBER", "DRIVER_NAME", "LAP_TIME"])
        df_fastest_lap_relevant_data = df_fastest_lap_full_data[
            ["DRIVER_NAME", "S1", "S2", "S3", "LAP_TIME"]].sort_values(by="LAP_TIME", ascending=True)
        df_fastest_lap_relevant_data["P"] = [i for i in range(1, len(df_fastest_lap_relevant_data) + 1)]
        df_fastest_lap_relevant_data["GAP"] = pd.to_timedelta(
            df_fastest_lap_relevant_data["LAP_TIME"].astype(str)) - pd.to_timedelta(
            df_fastest_lap_relevant_data["LAP_TIME"].astype(str)).min()
        df_fastest_lap_relevant_data["GAP"] = df_fastest_lap_relevant_data["GAP"].astype(str).map(lambda x: x[7:])

        for column in ["S1", "S2", "S3", "LAP_TIME", "GAP"]:
            df_fastest_lap_relevant_data[column] = df_fastest_lap_relevant_data[column].astype(str).map(lambda x: x[3:-3])
        df_fastest_lap_relevant_data = df_fastest_lap_relevant_data[["P", "DRIVER_NAME", "S1", "S2", "S3", "LAP_TIME", "GAP"]]

        position_fastest_lap = df_fastest_lap_relevant_data[["DRIVER_NAME", "P"]]
        position_fastest_lap.columns = ["DRIVER_NAME", "P_fastest"]

        # ideal lap calculation
        df_ideal_lap_per_driver = df.groupby(["NUMBER", "DRIVER_NAME"]).agg(
            {"S1": "min", "S2": "min", "S3": "min"}).reset_index()
        df_ideal_lap_per_driver["IDEAL_LAP"] = (pd.to_timedelta(df_ideal_lap_per_driver["S1"].astype(str)) + \
                                                pd.to_timedelta(df_ideal_lap_per_driver["S2"].astype(str)) + \
                                                pd.to_timedelta(df_ideal_lap_per_driver["S3"].astype(str))).astype(str)

        df_ideal_lap_per_driver["IDEAL_LAP"] = df_ideal_lap_per_driver["IDEAL_LAP"].map(lambda x: x[7:])
        df_ideal_lap_per_driver = df_ideal_lap_per_driver.sort_values(by="IDEAL_LAP", ascending=True)
        df_ideal_lap_per_driver["P"] = [i for i in range(1, len(df_ideal_lap_per_driver) + 1)]

        df_ideal_lap_per_driver["GAP"] = pd.to_timedelta(
            df_ideal_lap_per_driver["IDEAL_LAP"].astype(str)) - pd.to_timedelta(
            df_ideal_lap_per_driver["IDEAL_LAP"].astype(str)).min()

        df_ideal_lap_per_driver["IDEAL_VS_FASTEST"] = pd.to_timedelta(
            df_fastest_lap_per_driver["Fastest_lap_per_driver"].astype(str)) - df_ideal_lap_per_driver["IDEAL_LAP"]
        df_ideal_lap_per_driver["IDEAL_VS_FASTEST"] = df_ideal_lap_per_driver["IDEAL_VS_FASTEST"].astype(str).map(
            lambda x: x[10:-3])

        df_ideal_lap_per_driver["GAP"] = df_ideal_lap_per_driver["GAP"].astype(str).map(lambda x: x[7:])

        for column in ["S1", "S2", "S3", "IDEAL_LAP", "GAP"]:
            df_ideal_lap_per_driver[column] = df_ideal_lap_per_driver[column].astype(str).map(lambda x: x[3:-3])
        df_ideal_lap_per_driver = df_ideal_lap_per_driver[["P", "DRIVER_NAME", "S1", "S2", "S3", "IDEAL_LAP", "GAP", "IDEAL_VS_FASTEST"]]


        # position change: all improve from fastest to ideal
        position_ideal_lap = df_ideal_lap_per_driver[["DRIVER_NAME", "P"]]
        position_ideal_lap.columns = ["DRIVER_NAME", "P_ideal"]
        position_fastest_vs_ideal = pd.merge(position_fastest_lap, position_ideal_lap, how="inner", on="DRIVER_NAME")

        # position change: only you improve from fastest to ideal
        ideal_position = {}
        for index, row in df_ideal_lap_per_driver.iterrows():
            df_base = df_fastest_lap_relevant_data.copy()
            ideal_driver_time = row["IDEAL_LAP"]
            driver = row["DRIVER_NAME"]

            df_base.loc[df_base.DRIVER_NAME == driver, "LAP_TIME"] = ideal_driver_time

            df_base = df_base.sort_values(by="LAP_TIME", ascending=True)
            df_base["P"] = [i for i in range(1, len(df_base) + 1)]
            ideal_position[driver] = df_base.loc[df_base.DRIVER_NAME == driver, "P"].values[0]

        position_fastest_vs_ideal["your_ideal_position"] = position_fastest_vs_ideal.DRIVER_NAME.map(ideal_position)

        return html.Div([dbc.Row(
                                [dbc.Col(
                                    [html.H5("Fastest Lap", style={"textAlign": "center"}), dash_table.DataTable(
                                        data=df_fastest_lap_relevant_data.to_dict('records'),
                                        columns=[{'name': i, 'id': i} for i in df_fastest_lap_relevant_data.columns],
                                        page_size=20)],
                                    width=6),

                                    dbc.Col(
                                        [html.H5("Ideal Lap", style={"textAlign": "center"}), dash_table.DataTable(
                                            data=df_ideal_lap_per_driver.to_dict('records'),
                                            columns=[{'name': i, 'id': i} for i in df_ideal_lap_per_driver.columns],
                                            page_size=20)],
                                        width=6)
                                ]),
            dbc.Row([
                dbc.Col([html.Br(),
                         html.H5("Fastest vs Ideal", style={"textAlign": "center"}),
                         dcc.Graph(id='fastest-vs-ideal-all',
                                   figure={'data': [go.Scatter(
                                                      x=position_fastest_vs_ideal["P_fastest"],
                                                      y=position_fastest_vs_ideal["P_ideal"],
                                                      mode="markers+text",
                                                      marker={'color': 'LightSeaGreen'},
                                                      text=position_fastest_vs_ideal["DRIVER_NAME"],
                                                      textposition='top center',
                                                      texttemplate="%{text}",
                                                      textfont={"size": 10},
                                                      name="drivers",
                                   ), go.Scatter(
                                                      x=position_fastest_vs_ideal["P_fastest"],
                                                      y=position_fastest_vs_ideal["P_fastest"],
                                                      mode="lines",
                                                      marker={'color': 'Aquamarine'},
                                                      name="45° line",
                                   )],

                                  'layout': go.Layout(
                                      xaxis=dict(title='Fastest Position'),
                                      yaxis=dict(title='Ideal Position'),
                                      title="Position Comparison",
                                      height=700)
                                   }
                                   )],
                        width=6),

                dbc.Col([html.Br(),
                         html.H5("Fastest vs Potential", style={"textAlign": "center"}),
                         dcc.Graph(id='fastest-vs-ideal-only_you',
                                   figure={'data': [go.Scatter(
                                       x=position_fastest_vs_ideal["P_fastest"],
                                       y=position_fastest_vs_ideal["your_ideal_position"],
                                       mode="markers+text",
                                       marker={'color': 'MidnightBlue'},
                                       name="drivers",
                                       text=position_fastest_vs_ideal["DRIVER_NAME"],
                                       textposition='top center',
                                       texttemplate="%{text}",
                                       textfont={"size": 10},
                                   ), go.Scatter(
                                       x=position_fastest_vs_ideal["P_fastest"],
                                       y=position_fastest_vs_ideal["P_fastest"],
                                       marker={'color': 'LightSkyBlue'},
                                       name="45° line"

                                   )],

                                       'layout': go.Layout(
                                           xaxis=dict(title='Fastest Position'),
                                           yaxis=dict(title='Potential Position'),
                                           title="Position Comparison",
                                           height=700)
                                   }
                                   )],
                        width=6)
            ]),
        # Difference in Positions
            dbc.Row([dbc.Col(dcc.Graph(id='difference-fastest-vs-ideal-all',
                                   figure={'data': [go.Bar(
                                       x=position_fastest_vs_ideal["DRIVER_NAME"].str[:10],
                                       y=position_fastest_vs_ideal["P_fastest"] - position_fastest_vs_ideal["P_ideal"],
                                       text=position_fastest_vs_ideal["P_fastest"] - position_fastest_vs_ideal["P_ideal"],
                                       textposition='outside',
                                       texttemplate="%{text}",
                                       textfont=dict(
                                           size=12,
                                           color="LightSeaGreen"),
                                       marker={'color': 'LightSeaGreen'},
                                   )],

                                       'layout': go.Layout(
                                           xaxis=dict(tickangle=-45, tickfont={'size': 10}),
                                           yaxis=dict(title='Difference Ideal to Fastest'),
                                           title="Position Difference",
                                       )
                                   }
                                   ),
                        width=6),

                dbc.Col([
                         dcc.Graph(id='difference-fastest-vs-ideal-only_you',
                                   figure={'data': [go.Bar(
                                       x=position_fastest_vs_ideal["DRIVER_NAME"].str[:10],
                                       y=position_fastest_vs_ideal["P_fastest"] - position_fastest_vs_ideal["your_ideal_position"],
                                       text=position_fastest_vs_ideal["P_fastest"] - position_fastest_vs_ideal["your_ideal_position"],
                                       textposition='outside',
                                       texttemplate="%{text}",
                                       textfont=dict(
                                           size=12,
                                           color="LightSkyBlue"),
                                       marker={'color': 'LightSkyBlue'}
                                   )],

                                       'layout': go.Layout(
                                           xaxis=dict(tickangle=-45, tickfont={'size': 10}),
                                           yaxis=dict(title='Difference Potential to Fastest'),
                                           title="Position Difference",
                                       )
                                   }
                                   )],
                        width=6)

            ], style={"height": "5%"})
        ])

    @dashapp.callback(Output('output-sequence-analysis', 'children'),
                      Input('stored-data', 'data'),
                      Input('my-slider', 'value'),
                      Input('team-filter', 'value'))
    def sequence_analysis(raw_data: dict, slider_value: int, relevant_teams: list):
        df = pd.DataFrame(raw_data)
        df.sort_values(by=["DRIVER_NAME", "LAP_NUMBER"], inplace=True)
        print("HEEEELLO")
        print(slider_value)
        df = df[(df.LAP_NUMBER >= slider_value[0]) & (df.LAP_NUMBER <= slider_value[1])]
        df = df[df.TEAM.isin(relevant_teams)]

        drivers = list(df["DRIVER_NAME"].unique())
        drivers_label = []
        laps = list(df["LAP_NUMBER"].unique())
        lap_times_per_driver = []
        text_lap_times_per_driver = []

        for driver in drivers:
            drivers_label.append(driver[:10])
            times_per_driver = []
            raw_times = []
            for lap in laps:
                lap_time = df[(df["DRIVER_NAME"] == driver) & (df["LAP_NUMBER"] == lap)]["LAP_TIME"].values
                if len(lap_time) == 0:
                    lap_time = None
                    raw_time = "-"
                else:
                    lap_time = lap_time[0]
                    raw_time = lap_time
                    lap_time = datetime.strptime(lap_time, '%M:%S.%f').time().microsecond

                times_per_driver.append(lap_time)
                raw_times.append(raw_time)
            lap_times_per_driver.append(times_per_driver)
            text_lap_times_per_driver.append(raw_times)

        return dcc.Graph( id='heatmap',
                          figure={'data': [go.Heatmap(z=lap_times_per_driver,
                                                      x=laps,
                                                      y=drivers_label,
                                                      text=text_lap_times_per_driver,
                                                      texttemplate="%{text}",
                                                      textfont={"size": 15},
                                                      colorscale='Aggrnyl',
                                                      showscale=False,
                                                      hoverongaps=False)],
                                  'layout': go.Layout(
                                      xaxis=dict(title='LAP NUMBER'),
                                      height=700
                                  )
                          }
                  )
    @dashapp.callback(Output('lap-slider-output', 'children'),
                      Input('stored-data', 'data'))
    def lap_slider(raw_data: dict):
        df = pd.DataFrame(raw_data)
        teams = list(df.TEAM.unique())

        minimum_slider_value = df.LAP_NUMBER.min()
        maximum_slider_value = df.LAP_NUMBER.max()

        return dbc.Row([dbc.Col([html.H6("Teams", style={"textAlign": "center"}),
                                 dcc.Dropdown(teams, teams,
                                              multi=True,
                                              id='team-filter')
                                 ]),
                        dbc.Col([html.H6("Laps", style={"textAlign": "center"}),
                                 dcc.RangeSlider(1, maximum_slider_value, 1,
                                                 value=[minimum_slider_value, maximum_slider_value],
                                                 id='my-slider')
                                 ])
                        ])
