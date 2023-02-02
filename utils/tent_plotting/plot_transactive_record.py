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
pandas.set_option('display.max_rows', None)


def transactive_record(db, building):
    try:
        df = None
        i = 0
        query = "SELECT ts, value_string FROM data " \
                "INNER JOIN topics ON data.topic_id = topics.topic_id " \
                "WHERE topics.topic_name = \"tns/{}/transactive_operation/Real-Time Auction\" order by ts asc"

        records = pd.read_sql_query(query.format(building), db)
        records = records.join(records['value_string'].apply(json.loads).apply(pd.Series)).dropna()
        price = records['prices']
        ts = [x[0] for item in price for x in item]
        p = [x[1] for item in price for x in item]
        pr = pd.DataFrame({'ts': ts, 'price': p})
        pr = pr.drop_duplicates(keep='last', subset='ts')
        demand_records = records['demand']
        for records in demand_records:
            try:
                _date = pr.iloc[i]['ts']
            except:
                break
            _max = records['actual']['assets']['ModelFrame'][-1]
            _min = records['actual']['assets']['ModelFrame'][-2]
            ts = _max[0]
            if ts != _date:
                values = records['actual']['assets']['ModelFrame']
                x = 0
                for vertices in values:
                    if vertices[0] == _date:
                        break
                    x += 1
                if x+1 > len(values):
                    continue
                _min = values[x]
                _max = values[x+1]
            avg_price = (_max[1]+_min[1])/2.0
            dct = {'ts': [ts], "MaxPrice": [_max[1]], 'MinPrice': [_min[1]], "AvgPrice": [avg_price]}
            if df is None:
                df = pd.DataFrame.from_dict(dct)
            else:
                temp = pd.DataFrame.from_dict(dct)
                df = pd.concat([df, temp])
            i += 1

        df['ts'] = pd.to_datetime(df['ts'])
        df = df.set_index('ts')
        df = df.drop_duplicates()
        # df.to_csv('prices.csv')
        # pr.to_csv('pr.csv')
        pr['ts'] = pd.to_datetime(pr['ts'])
        pr = pr.set_index('ts')
        fig = make_subplots(rows=1, cols=1, shared_xaxes=True, y_title='price', x_title='Date')
        _count = 1
        fig.add_trace(go.Scatter(x=df.index, y=df['MinPrice'], mode='lines',
                                 name="{} {}".format(building, 'MinPrice')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MaxPrice'], mode='lines',
                                 name="{} {}".format(building, 'MaxPrice')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['AvgPrice'], mode='lines',
                                 name="{} {}".format(building, 'AvgPrice')), row=1, col=1)
        fig.add_trace(go.Scatter(x=pr.index, y=pr['price'], mode='lines',
                                 name="{} {}".format(building, 'ClearedPrice')), row=1, col=1)
        fig.write_html('price.html', auto_open=True)
        return df
    except Exception as ex:
        print(ex)


# Change db name to db file one desires to use!
# Change building to building name in DB!
building_db_file = 'small_office.historian.sqlite'
db_building = sqlite3.connect(building_db_file)
building = 'SMALL_OFFICE_DR'
transactive_record(db_building, building)