import sqlite3

import json
import pandas as pd
import pytz

import plotly.express as px
import sys
local_tz = pytz.timezone('UTC')
query_template = "SELECT ts, value_string FROM data " \
                 "INNER JOIN topics ON data.topic_id = topics.topic_id " \
                 "WHERE topics.topic_name = \"{campus}/{bldg}/{device}/{point}\""


def gen_query(campus, bldg, device, point):
    return query_template \
        .replace("{campus}", campus) \
        .replace("{bldg}", bldg) \
        .replace("{device}", device) \
        .replace("{point}", point)


def get_power_data(db, campus, building_topic, device, point):
    query = gen_query(campus, building_topic, device, point)
    power = pd.read_sql_query(query, db)
    power.rename(columns={'value_string': point}, inplace=True)
    power[point] = pd.to_numeric(power[point], errors='coerce')
    power[point] = power[point] / 1000
    power['ts'] = pd.to_datetime(power['ts'])
    power.index = power['ts']
    # try:
    #     power['ts'] = power['ts'].dt.tz_localize(self.local_tz)
    # except TypeError:
    #     pass
    return power


def transactive_record(db, building):
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
        try:
            df.index = df.index.tz_localize(local_tz)
        except TypeError:
            pass
    except Exception as ex:
        print(ex)
        df = None
    return df

try:
    with open("tent.json") as f:
        config = json.load(f)
except:
    print("Problem parsing config.json file!")
    config = {}
building_topic_list = config.get("building_topic_list")
building_db_file = config.get("building_db")
baseline = config.get("baseline_building")
if not building_topic_list or building_db_file is None:
    print("Problem with configuration!")
    sys.exit()
# remove baseline for now
if baseline is not None and baseline in building_topic_list:
    building_topic_list.remove(baseline)

db_building = sqlite3.connect(building_db_file)
all_cost = pd.DataFrame()
for building in building_topic_list:
    price_df = transactive_record(db_building, building)
    price_df = price_df.resample('1T').ffill()
    power_df = get_power_data(db_building, "PNNL", building, "METERS", "WholeBuildingPower")
    combined_df = pd.merge(power_df, price_df, how='inner', left_index=True, right_index=True)
    combined_df[building] = combined_df['WholeBuildingPower']*combined_df["prices"]/60.0
    all_cost[building] = combined_df[building]


all_cost_hour = all_cost.groupby(all_cost.index.hour).sum()
all_cost_day = all_cost.groupby(all_cost.index.dayofweek).sum()
all_cost_month = all_cost.groupby(all_cost.index.month).sum()

fig = px.bar(all_cost_hour, barmode='group', text_auto='.2s',labels={"value": "Cost $", "index": "hour"})
fig.update_traces(textfont_size=14, textangle=0, textposition="outside", cliponaxis=False)
fig.write_html('cost_{}.html'.format("hourly"), auto_open=True)

fig1= px.bar(all_cost_day, barmode='group', text_auto='.2s', labels={"value": "Cost $", "index": "day"})
fig1.update_traces(textfont_size=14, textangle=0, textposition="outside", cliponaxis=False)
fig1.write_html('cost_{}.html'.format("day"), auto_open=True)

fig2 = px.bar(all_cost_month, barmode='group', text_auto='.2s', labels={"value": "Cost $", "index": "month"})
fig2.update_traces(textfont_size=14, textangle=0, textposition="outside", cliponaxis=False)
fig2.write_html('cost_{}.html'.format("monthly"), auto_open=True)
