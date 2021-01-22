# Download and format data from Comtrade API

import pandas as pd
import math
import os
import json
from urllib.request import urlopen
import time
import csv
import numpy as np

results_dir = "H:/Shared drives/APHIS  Projects/Pandemic/Data/Comtrade"
os.chdir(results_dir)  # set your current directory

# create a directory to save downloaded data
if not os.path.exists("csv"):
    os.makedirs("csv")


def nested_list(original_list, list_length):
    """Split long list into nested list of lists at specified length.
    Returns nested list.
    Ex: Create short lists of years or country codes for API calls."""
    nested_list = []
    start = 0
    for i in range(math.ceil(len(original_list) / list_length)):
        x = original_list[start : start + list_length]
        nested_list.append(x)
        start += list_length
    return nested_list


# Read UN codes to ISO3 codes crosswalk to use as country list
crosswalk = pd.read_csv("H:/Shared drives/APHIS  Projects/Pandemic/Data/un_to_iso.csv")
crosswalk["UN"] = crosswalk["UN"].astype(str)
crosswalk = crosswalk[crosswalk.ISO3.notnull()]

# Set years of trade data to download and use to subset crosswalk by years
start_year = 2000
end_year = 2019  # inclusive

# Change "Now" end date in crosswalk to a max year value so column can be converted
# to numeric and compared to simulation years
crosswalk.loc[crosswalk["End"] == "Now", "End"] = "9999"
crosswalk["End"] = pd.to_numeric(crosswalk["End"])
crosswalk = crosswalk[crosswalk["End"] >= start_year]

crosswalk_dict = pd.Series(crosswalk.ISO3.values, index=crosswalk.UN).to_dict()

# Error log file, track no data, but not very useful. Consider removing.
# if os.path.isfile("log.csv"):  # if file exists, open to append
#     csv_file = open("log.csv", "a", newline="")
#     error_log = csv.writer(csv_file, delimiter=",", quotechar='"')
# else:  # else if file does not exist, create it
#     csv_file = open("log.csv", "w", newline="")
#     error_log = csv.writer(csv_file, delimiter=",", quotechar='"')
#     error_log.writerow(
#         ["reporter_id", "reporter", "hs", "year", "status", "message", "time"]
#     )

# Premium subscription authorization code. Look this up in our
# Comtrade account info page. (https://comtrade.un.org/db/sysLoginAccess.aspx)
auth_code = "jXIKwJ2httdcPDHwwJCj7GzbDh8fva23HYV17lyN+BeKrxX3fSviSAT9vgH5zQ+XnKj75SBnqPn25kXrwD1viUgtdDMNhpjrw4ZPcpdznaYq1nH8F/wxSoUBSMUzwVVb3YsoqruN04qDiJU/NleTCA=="

# Set time step for trade data, options are A (annual) or M (monthly)
freq = "M"
years = np.arange(start_year, end_year + 1, 1)

if freq == "M":
    timesteps = []
    for year in years:
        months = [
            "01",
            "02",
            "03",
            "04",
            "05",
            "06",
            "07",
            "08",
            "09",
            "10",
            "11",
            "12",
        ]
        for month in months:
            timesteps.append(str(year) + month)
elif freq == "A":
    timesteps = years
else:
    raise RuntimeError("Unknown frequency: {freq}".format(**locals()))

# Get data availability from Comtrade and compare to desired data
data_availability_url = urlopen(
    "http://comtrade.un.org/api/refs/da/view?type=C&freq=all&ps=all&px=HS"
)
data_availability_raw = json.loads(data_availability_url.read().decode())
data_availability_url.close()
data_availability = pd.json_normalize(data_availability_raw)

data_summary = pd.DataFrame(
    columns=[
        "country",
        "year",
        "annual_avail",
        "all_monthly_avail",
        "partial_monthly_avail",
    ]
)
for country in crosswalk.UN.to_list():
    country_availability = data_availability[data_availability["r"] == country]
    for year in years:
        summary_data = {
            "country": [country],
            "year": [year],
            "annual_avail": [0],
            "all_monthly_avail": [0],
            "partial_monthly_avail": [0],
        }
        year_summary = pd.DataFrame(summary_data)
        if str(year) in list(country_availability["ps"]):
            year_summary["annual_avail"] = 1
        country_monthly = list(
            country_availability[country_availability["freq"] == "MONTHLY"]["ps"].str[
                :4
            ]
        )
        monthly_sum = sum(1 for i in country_monthly if i == str(year))
        if monthly_sum == 12:
            year_summary["all_monthly_avail"] = 1
        if 0 < monthly_sum < 12:
            year_summary["partial_monthly_avail"] = 1
        data_summary = data_summary.append(year_summary)

use_monthly = data_summary[data_summary["all_monthly_avail"] == 1]
use_monthly.append(
    data_summary[
        (data_summary["partial_monthly_avail"] == 1)
        & (data_summary["annual_avail"] == 0)
    ]
)
use_annual = data_summary[
    (data_summary["annual_avail"] == 1) & (data_summary["all_monthly_avail"] == 0)
]
no_data = data_summary[
    (data_summary["annual_avail"] == 0)
    & (data_summary["all_monthly_avail"] == 0)
    & (data_summary["partial_monthly_avail"] == 0)
]

# list HS commodity codes to query
hs_list = np.arange(6801, 6804 + 1, 1)

# loop over commodities, 1 at a time (could do more at once)
for hs in hs_list:
    nested_country_codes = nested_list(crosswalk.UN.to_list(), 5)
    nested_country_names = nested_list(crosswalk.Name.to_list(), 5)
    years_str = "%2C".join(map(str, years))
    data = pd.DataFrame()
    # loop over all countries (5 at a time, could do more at once) and call API
    for country_code_list in enumerate(nested_country_codes):
        country_code_str = "%2C".join(country_code_list[1])

        url = urlopen(
            "http://comtrade.un.org/api/get?max=250000&type=C&px=HS&cc="
            + str(hs)
            + "&r="
            + country_code_str
            + "&rg=1&p=all&freq="
            + freq
            + "&ps="
            + years_str
            + "&fmt=json&token="
            + str(auth_code)
        )
        raw = json.loads(url.read().decode())
        url.close()

        if len(raw["dataset"]) == 0:
            print(
                "No data downloaded for HS"
                + str(hs)
                + ", "
                + years_str
                + ": "
                + ", ".join(map(str, nested_country_names[country_code_list[0]]))
                + ". Message: "
                + str(raw["validation"]["message"])
            )
            continue

        data = data.append(raw["dataset"])
        data["ptCode"] = data["ptCode"].astype(str)

    # loop over timesteps (YYYY or YYYYMM) and save a country x country matrix
    # per timestep per HS code as csv
    for timestep in timesteps:
        timestep_data = data[data.period.eq(int(timestep))]
        HS_matrix = crosswalk[["UN"]]
        for reporter in crosswalk.UN.to_list():
            reporter_data = timestep_data[timestep_data.rtCode.eq(int(reporter))]
            reporter_data = reporter_data[["ptCode", "NetWeight"]]

            # if no data were downloaded for reporter/year, add column of zeros to
            # commodity/year df and move to next country
            if len(reporter_data) == 0:
                HS_matrix = HS_matrix.assign(x=0)
                HS_matrix.rename(columns={"x": reporter}, inplace=True)
                error_log.writerow(
                    [
                        crosswalk[crosswalk["UN"] == reporter]["Name"].tolist()[0],
                        reporter,
                        hs,
                        timestep,
                        "no data",
                        raw["validation"]["message"],
                        time.ctime(),
                    ]
                )
                print(
                    "HS"
                    + str(hs)
                    + " "
                    + str(timestep)
                    + " "
                    + str(crosswalk_dict[reporter])
                    + ": no data"
                )
                continue

            # Merge to commodity/year df
            HS_matrix = pd.merge(
                HS_matrix, reporter_data, how="left", left_on="UN", right_on="ptCode"
            )
            HS_matrix.drop("ptCode", axis=1, inplace=True)
            HS_matrix.rename(columns={"NetWeight": reporter}, inplace=True)
            print(
                "HS"
                + str(hs)
                + " "
                + str(timestep)
                + " "
                + str(crosswalk_dict[reporter])
                + ": finished"
            )

        # Use crosswalk to change UN country codes to ISO3
        HS_matrix.fillna(0, inplace=True)
        HS_matrix.rename(columns={"UN": "ISO"}, inplace=True)
        HS_matrix.set_index("ISO", inplace=True)
        HS_matrix.rename(mapper=crosswalk_dict, inplace=True, axis=0)
        HS_matrix.rename(mapper=crosswalk_dict, inplace=True, axis=1)

        # Check to see if there are any duplicate ISO codes in matrix
        # Should only occur for a few historical cases - Germany, Viet Nam, Yemen.
        # If so, group and sum any rows and columns with matching ISO codes.
        if len(HS_matrix.columns.to_list()) != len(set(HS_matrix.columns.to_list())):
            HS_matrix = HS_matrix.groupby("ISO", sort=False).sum()
            HS_matrix = HS_matrix.transpose()
            HS_matrix = HS_matrix.reset_index()
            HS_matrix = HS_matrix.groupby("index", sort=False).sum().transpose()
        assert len(HS_matrix.columns.to_list()) == len(set(HS_matrix.columns.to_list()))

        HS_matrix.to_csv("csv/" + str(hs) + "_" + str(timestep) + ".csv", index=True)

csv_file.close()
