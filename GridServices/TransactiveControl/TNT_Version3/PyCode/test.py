import os

marketSeriesName = 'testing'
filename = marketSeriesName + ".csv"
data_folder = os.getcwd()
data_folder = data_folder + "/Market_Data/"
if not os.path.exists(data_folder):
    os.makedirs(data_folder)

