import io
import re
import base64
import pandas as pd

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
                               )],
                    width=4),

            dbc.Col([html.H6("Column Separator"),
                     dbc.RadioItems(id='column-separator-id',
                                    options=[
                                        {'label': 'Comma (,)', 'value': ','},
                                        {'label': 'Semicolon (;)', 'value': ';'},
                                        {'label': 'Hyphen (-)', 'value': '-'}],
                                    value=',')],
                    width=1),

            dbc.Col(html.Div(id='output-filename'), style={"height": "60px", "float": "center"})
            ], align="center"),

        html.Hr(),  # horizontal line
        html.H5('Data Preview'),
        dbc.Col(html.Div(id='output-datatable')),
        html.Hr(),  # horizontal line


        html.Div(id='best-lap-table')

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
                page_size=5),
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


        return dbc.Row(
            [dbc.Col(
                [html.H4("Fastest Lap", style={"textAlign": "center"}), dash_table.DataTable(
                    data=df_fastest_lap_relevant_data.to_dict('records'),
                    columns=[{'name': i, 'id': i} for i in df_fastest_lap_relevant_data.columns],
                    page_size=20)],
                width=6),

                dbc.Col(
                    [html.H4("Ideal Lap", style={"textAlign": "center"}), dash_table.DataTable(
                        data=df_ideal_lap_per_driver.to_dict('records'),
                        columns=[{'name': i, 'id': i} for i in df_ideal_lap_per_driver.columns],
                        page_size=20)],
                    width=6)
            ])
