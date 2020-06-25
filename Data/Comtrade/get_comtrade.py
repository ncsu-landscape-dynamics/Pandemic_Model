# ************************************************************************
# Downloading data from Comtrade API, keeping a log of successful downloads and errors.
# Example: ice cream imports and exports
# https://github.com/evpu
# ************************************************************************

import pandas as pd
import numpy as np
import math
import os
import json
from urllib.request import urlopen
import time
import csv

# print(os.getcwd())
# os.chdir('.')  # set your current directory

# create a directory where to save downloaded data
if not os.path.exists('data'):
    os.makedirs('data')

# ************************************************************************
# Obtain Comtrade country codes
# ************************************************************************
url = urlopen('http://comtrade.un.org/data/cache/partnerAreas.json')

country_code = json.loads(url.read().decode())
url.close()
country_code = pd.DataFrame(country_code['results'])
country_code['id']=country_code['id'].astype(str)

# Clean up country codes a bit
# drop 'all' and 'world'
country_code = country_code.drop([0, 1])
# drop areas that are "nes" or "Fmr"
#country_code = country_code[~country_code['text'].str.contains(', nes|Fmr')]

# ************************************************************************
# Error log file
# ************************************************************************
if os.path.isfile('log.csv'):  # if file exists, open to append
    csv_file = open('log.csv', 'a', newline='')
    error_log = csv.writer(csv_file, delimiter=',', quotechar='"')
else:  # else if file does not exist, create it
    csv_file = open('log.csv', 'w', newline='')
    error_log = csv.writer(csv_file, delimiter=',', quotechar='"')
    error_log.writerow(['reporter_id', 'reporter', 'hs', 'year', 'status', 'message', 'time'])


# ************************************************************************
# Imports
# ************************************************************************
def nested_list(original_list, list_length):
    '''Split long list into nested list of lists at specified length. Returns nested list.
    Ex: Create short lists of years or country codes for API calls.'''
    nested_list = []
    start = 0
    for i in range(math.ceil(len(original_list) / list_length)):
        x = original_list[start:start + list_length]
        nested_list.append(x)
        start += list_length
    return nested_list

auth_code = "jXIKwJ2httdcPDHwwJCj7GzbDh8fva23HYV17lyN+BeKrxX3fSviSAT9vgH5zQ+XnKj75SBnqPn25kXrwD1viUgtdDMNhpjrw4ZPcpdznaYq1nH8F/wxSoUBSMUzwVVb3YsoqruN04qDiJU/NleTCA=="

# add lines to import HS list and loop through codes of interest at 4 digits
hs_69 = np.arange(6902, 6903 + 1, 1)
for hs in hs_69:
    start_year = 1994
    end_year = 2018
    years = np.arange(start_year, end_year + 1, 1)
    nested_years = nested_list(years, 5)
    nested_country_codes = nested_list(list(country_code['id']), 5)
    for year_list in nested_years:
        years_str = "%2C".join(map(str, year_list))
        data = pd.DataFrame()
        for country_code_list in nested_country_codes:  # loop over all countries
            # time.sleep(45)  # prob not needed
            country_code_str = "%2C".join(country_code_list)
            try:
                url = urlopen('http://comtrade.un.org/api/get/plus?max=250000&type=C&px=HS&cc=' + str(hs) + '&r=' + country_code_str + '&rg=1&p=all&freq=A&ps=' + years_str + '&fmt=json') #'&fmt=json&token=' + str(auth_code))
                raw = json.loads(url.read().decode())
                url.close()
            except:  # if did not load, try again
                try:
                    url = urlopen('http://comtrade.un.org/api/get/plus?max=250000&type=C&px=HS&cc=' + str(hs) + '&r=' + country_code_str + '&rg=1&p=all&freq=A&ps=' + years_str + '&fmt=json') #'&fmt=json&token=' + str(auth_code))
                    raw = json.loads(url.read().decode())
                    url.close()
                except:  # if did not load again, move on to the next country in the loop
                    #error_log.writerow([country_code[country_code['id'] == str(i)]['text'].tolist()[0], i, hs, year, 'Fail', raw['validation']['message'], time.ctime()])
                    print('Fail: country ' + country_code_str + ', ' + years_str + ", " + str(hs))
                    continue

            if len(raw['dataset']) == 0:
                print('No data downloaded for:' + years_str + ' ' + country_code_str + '. Message: ' + str(raw['validation']['message']))
                continue

            data = data.append(raw['dataset'])          
            data['ptCode']=data['ptCode'].astype(str)


        for year in year_list:
            yr_data = data[data.yr.eq(year)]
            HS_matrix = country_code[['id']]
            for reporter in list(country_code['id']):
                reporter_data = yr_data[yr_data.rtCode.eq(int(reporter))]
                reporter_data = reporter_data[['ptCode', 'NetWeight']]

                # if no data was downloaded for reporter/year, add column of zeros to commodity/year df and move to next country
                if len(reporter_data) == 0:
                    HS_matrix = HS_matrix.assign(x = 0)
                    HS_matrix.rename(columns={"x": reporter}, inplace=True)
                    error_log.writerow([country_code[country_code['id'] == reporter]['text'].tolist()[0], reporter, hs, year, 'no data', raw['validation']['message'], time.ctime()])
                    print('No data: country ' + reporter + ' ' + str(year))
                    continue

                # Merge to commodity/year df

                HS_matrix = pd.merge(HS_matrix, reporter_data, how = 'left', left_on='id', right_on='ptCode')
                HS_matrix.drop("ptCode", axis=1, inplace=True)
                HS_matrix.rename(columns={"NetWeight": reporter}, inplace=True)
                print(reporter + " " + str(year) + ": finished")

            HS_matrix.fillna(0, inplace=True)
            HS_matrix.to_csv('data/' + str(hs) + '_' + str(year) + '.csv', index=False)

csv_file.close()
