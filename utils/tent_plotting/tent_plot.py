###  import necessary libraries  ####
import sqlite3

import pandas
import pandas as pd
import json
import pytz
import json
import sys
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.express as px
pd.set_option('display.max_colwidth', None)
pandas.set_option('display.max_rows', 1000)



query_template = "SELECT ts, value_string FROM data " \
                 "INNER JOIN topics ON data.topic_id = topics.topic_id " \
                 "WHERE topics.topic_name = \"{campus}/{bldg}/{device}/{point}\""


def gen_query(campus, bldg, device, point):
    return query_template \
        .replace("{campus}", campus) \
        .replace("{bldg}", bldg) \
        .replace("{device}", device) \
        .replace("{point}", point)


timestring = '%Y-%m-%dT%H:%M:%S'
timestring2 = '%Y%m%dT%H%M%S'


class TENT_data(object):
    def __init__(self, db_building, db_campus, db_city, building_list):

        self.local_tz = pytz.timezone('UTC')
        self.df_power = {}
        self.device_data = {}
        self.building_df = {}
        bldg_list = list(building_list)
        bldg_list.remove("SMALL_OFFICE_VANILLA")
        for building in bldg_list:
            df = self.transactive_record(db_building, building)
            if df is not None:
                self.building_df[building] = df

    def transactive_record(self, db, building):
        try:
            df = pd.DataFrame()
            query = "SELECT ts, value_string FROM data " \
                    "INNER JOIN topics ON data.topic_id = topics.topic_id " \
                    "WHERE topics.topic_name = \"tns/{}/market_balanced_prices\""

            records = pd.read_sql_query(query.format(building), db)

            records = records.join(records['value_string'].apply(json.loads).apply(pd.Series)).dropna()

            records = records[records.tnt_market_name.str.contains("Real-Time")]

            record = records['balanced_prices'].apply(pd.Series).T
            record = record.stack().groupby(level=0).last().reindex(record.index)
            df.index = record.index
            df['prices'] = record.values

            record = records['schedule_powers'].apply(pd.Series).T
            record = record.stack().groupby(level=0).last().reindex(record.index)
            df['campus_power'] = record.apply(lambda x: x.get('PNNL_Campus'))
            df['model'] = record.apply(lambda x: x.get('ModelFrame'))
            df.index = pd.to_datetime(df.index)
        except Exception as ex:
            print(ex)
            df = None
        return df


class TCC_data(object):

    def __init__(self, db, device_point_dict=None, csv=False):

        self.database = db
        self.start_time = None
        self.end_time = None
        self.local_tz = pytz.timezone('UTC')
        if device_point_dict is not None:
            self.device_point_dict = device_point_dict
        else:
            self.device_point_dict = {}
            self.device_point_dict["HP"] = [
                "ZoneCoolingTemperatureSetPoint",
                "ZoneTemperature",
                "FirstStageCooling"
            ]
        self.df_power = {}
        self.device_data = {}
        self.__get_topics()
        self.ilc_df = None
        self.get_ilc_target()

    def get_ilc_target(self):
        try:
            df = pd.DataFrame()
            query = "SELECT ts, value_string FROM data " \
                    "INNER JOIN topics ON data.topic_id = topics.topic_id " \
                    "WHERE topics.topic_name = \"record/target_agent\""

            target = pd.read_sql_query(query, self.database)
            target = target.join(target['value_string'].apply(json.loads).apply(pd.Series))
            df['target'] = target[0].apply(lambda x: x.get('value').get('target'))
            df['ts'] = target[0].apply(lambda x: x.get('value').get('start'))
            df['ts'] = pd.to_datetime(df['ts'])
            self.ilc_df = df
        except:
            self.ilc_df = None

    """ 

        This function generateS a list of all the control devices, such as RTU and VAV terminals.

        Note that this list doesn't include chillers and AHUs

        """

    def __get_topics(self):

        query_topic = "SELECT * FROM 'topics'"

        df_topics = pd.read_sql_query(query_topic, self.database)
        df_topics.to_csv("topics.csv")

    """ 

    This function generateS a Dataframe that contains system level operation info, including the whole building power consumption,

    demand limit threshold, and system loss.

    """
    def get_power_data(self, campus, building_topic, device, point):
        query = gen_query(campus, building_topic, device, point)
        power = pd.read_sql_query(query, self.database)
        power.rename(columns={'value_string': point}, inplace=True)
        power[point] = pd.to_numeric(power[point], errors='coerce')
        power[point] = power[point] / 1000
        power['ts'] = pd.to_datetime(power['ts'])
        try:
            power['ts'] = power['ts'].dt.tz_localize(self.local_tz)
        except TypeError:
            pass
        return power

    def get_zone_data(self, device_type, campus, building, device):
        device_data = None
        for point in self.device_point_dict[device_type]:
            control_query = gen_query(campus, building, device, point)
            df = pd.read_sql_query(control_query, self.database)
            df.rename(columns={'value_string': point}, inplace=True)
            df[point] = pd.to_numeric(df[point], errors='coerce')
            df[point] = df[point]
            df['ts'] = pd.to_datetime(df['ts'])
            if device_data is None:
                device_data = df.set_index('ts')
            else:
                device_data = device_data.join(df.set_index('ts'))
        return device_data

    def get_df(self, topic, point):
        query = "SELECT ts, value_string FROM data " \
               "INNER JOIN topics ON data.topic_id = topics.topic_id " \
               "WHERE topics.topic_name = \"{}/{}\""
        query = query.format(topic, point)
        df = pd.read_sql_query(query, self.database)
        df.rename(columns={'value_string': point}, inplace=True)
        df[point] = pd.to_numeric(df[point], errors='coerce')
        df[point] = df[point]
        df['ts'] = pd.to_datetime(df['ts'])
        return df


class Main(object):
    def __init__(self, config):
        self.colors = config.get("color_scheme", px.colors.qualitative.Plotly)
        self.combined_colors = [self.colors[0], self.colors[1], self.colors[5], self.colors[9]]
        self.x1 = {}
        self.x2 = {}
        self.campus = config.get("campus", "PNNL")
        self.building_topic_list = config.get("building_topic_list",
                                              ["SMALL_OFFICE_VANILLA", "SMALL_OFFICE_ILC", "SMALL_OFFICE_DR"])
        self.power_meter = config.get("power_meter", "METERS")
        self.power_point = config.get("power_point", "WholeBuildingPower")
        self.avg_power_point = self.power_point + "Average"
        self.device_data_dict = {}
        self.device_list = {}
        building_db_file = config.get("building_db", 'small_office.historian.sqlite')
        db_building = sqlite3.connect(building_db_file)
        campus_db_file = config.get("campus_db", None)
        if campus_db_file is not None:
            db_campus = sqlite3.connect(campus_db_file)
        else:
            db_campus = None
        city_db_file = config.get("city_db", None)
        if city_db_file is not None:
            db_city = sqlite3.connect(city_db_file)
        else:
            db_city = None
        self.tent_data = TENT_data(db_building, db_campus, db_city, self.building_topic_list)
        devices = config.get("devices", {})
        for device_type, device_config in devices.items():
            self.device_list[device_type] = device_config.get("device_list", [])
            self.device_data_dict[device_type] = device_config.get("device_data", {})
            self.x1[device_type] = ""
            self.x2[device_type] = ""
            self.create_device_units(device_type)
        self.tcc_data = TCC_data(db_building, device_point_dict=self.device_data_dict)
        self.power = {}
        self.build_power_df()
        self.additional_topic = self.tcc_data.get_df("PNNL/SMALL_OFFICE_VANILLA/HP1", "OutdoorAirTemperature")
        # how to create specs parameter automagically
        self.specs = [[{"secondary_y": True}], [{"secondary_y": True}], [{"secondary_y": True}], [{"secondary_y": False}]]
        self.nplots = len(list(self.power.keys()))

    def create_device_units(self, device_type):
        x1 = set()
        x2 = set()
        for point, info in self.device_data_dict.items():
            secondary = info.get("secondary_axis", False)
            units = info.get("units", "")
            if secondary:
                x2.add(units)
            else:
                x1.add(units)
        self.x1[device_type] = "/".join(x1)
        self.x2[device_type] = "/".join(x2)

    def build_power_df(self):
        for bldg in self.building_topic_list:
            self.power[bldg] = self.tcc_data.get_power_data(self.campus, bldg, self.power_meter, self.power_point)
            self.power[bldg][self.avg_power_point] = self.power[bldg][self.power_point].rolling(30).mean()

    def make_power_plot(self):
        specs = [[{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": True}]]
        fig = make_subplots(specs=specs, rows=self.nplots, cols=1, shared_xaxes=True, y_title='Power (kW)', x_title='Date')
        _count = 1
        for bldg, df in self.power.items():
            tag = bldg.split("_")[-1]
            fig.add_trace(go.Scatter(x=df['ts'], y=df[self.avg_power_point], mode='lines',
                                     name="{} {}".format(tag, self.avg_power_point)), row=_count, col=1)
            if self.tcc_data.ilc_df is not None and "ILC" in bldg:
                fig.add_trace(
                    go.Scatter(x=self.tcc_data.ilc_df['ts'], y=self.tcc_data.ilc_df['target'], mode='lines', name="{} target".format(tag)),
                    row=_count, col=1)
            if self.tent_data.building_df is not None and bldg in self.tent_data.building_df:
                fig.update_yaxes(title_text="Price ($)", secondary_y=True)
                fig.add_trace(
                    go.Scatter(x=self.tent_data.building_df[bldg].index, y=-self.tent_data.building_df[bldg]['model'], mode='lines',
                               name="{} schedule_power".format(tag)),
                    row=_count, col=1)
                fig.add_trace(
                    go.Scatter(x=self.tent_data.building_df[bldg].index, y=self.tent_data.building_df[bldg]['prices'],
                               mode='lines',
                               name="{} price".format(tag)),
                    row=_count, col=1, secondary_y=True)

            _count += 1
        fig.write_html('power.html', auto_open=True)
        fig = make_subplots(specs=[[{"secondary_y": True}]], rows=1, cols=1, shared_xaxes=True, x_title='Date')
        col = 0
        for name, df in self.power.items():
            fig.add_trace(go.Scatter(x=df['ts'], y=df[self.avg_power_point], mode='lines',
                                     line={"color": self.combined_colors[col]}, name="{} {}".format(name, self.avg_power_point)),
                          row=1, col=1)
            col += 1
        fig.add_trace(go.Scatter(x=self.additional_topic['ts'], y=self.additional_topic['OutdoorAirTemperature'], mode='lines',
                                 line={"color": self.combined_colors[col]}, name="OutdoorAirTemperature"),
                      row=1, col=1, secondary_y=True)
        fig.update_yaxes(title_text='Power (kW)', secondary_y=False)
        fig.update_yaxes(title_text='Temperature (\u00B0F)', secondary_y=True)
        fig.write_html('power_combined.html', auto_open=True)

    def make_device_plots(self):
        for device_type in self.device_list:
            for device_id in self.device_list[device_type]:
                print("Creating device plot: {}".format(device_id))
                zones = {}
                _count = 1
                fig = make_subplots(specs=self.specs, rows=self.nplots + 1, cols=1, shared_xaxes=True, x_title='Date')
                fig.update_yaxes(title_text=self.x2[device_type], secondary_y=True)
                fig.update_yaxes(title_text=self.x1[device_type], secondary_y=False)
                for building in self.building_topic_list:
                    tag = building.split("_")[-1]
                    df = self.tcc_data.get_zone_data(device_type, self.campus, building, device_id)
                    combine_list = []
                    for point, info in self.device_data_dict[device_type].items():
                        secondary_x = info.get("secondary_axis", False)
                        combine_status = info.get("combine", False)
                        fig.add_trace(go.Scatter(x=df.index, y=df[point], mode='lines', name="{} {}".format(tag, point)),
                                      row=_count, col=1, secondary_y=secondary_x)
                        if combine_status:
                            combine_list.append(point)
                    _count += 1
                    zones[building] = df
                col = 0
                for name, df in zones.items():
                    tag = name.split("_")[-1]
                    for point in combine_list:
                        fig.add_trace(go.Scatter(x=df.index, y=df[point], mode='lines',
                                                 line={"color": self.colors[col]}, name="{} {}".format(tag, point)),
                                      row=_count, col=1)
                    col += self.nplots
                    device_tag = device_id.replace("/", "_")
                fig.write_html('zone_{}.html'.format(device_tag), auto_open=True)


try:
    with open("tent.json") as f:
        config = json.load(f)
except:
    print("Problem parsing config.json file!")
    config = {}

main = Main(config)
main.build_power_df()
main.make_power_plot()
main.make_device_plots()
