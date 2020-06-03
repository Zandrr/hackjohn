import pathlib
import re

import requests
import pandas
from pkg_resources import parse_version

# Minimum number of available spaces
spaces = 2

# Comment out trailheads you'd like to start from
exclude = [
    #     'HI → LYV',
    #     'HI → Sunrise/Merced Lakes (Pass through)',
    #     "Glacier Point → LYV",
    #     "Sunrise Lakes",
    #     "Lyell Canyon",
]

# Dates you'd like to start on (inclusive of end date)
dates = pandas.date_range(start="2020-06-01", end="2020-10-05", freq="D")

# Write output to this file. If the generated output is identical to
# the existing output at this path, suppress notification. To disable
# writing any files, set output_path=None as shown below.
output_path = pathlib.Path("__file__").parent.joinpath("hackjohn-output.txt")
# output_path = None  # None disables writing to a file

# If the Report Date is before this day, suppress Telegram notification.
# You probably do not need to change this setting unless you have disabled
# output_path
min_report_date = "2020-01-01"


def get_trailhead_df():
    """
    Convert the current "Donohue Exit Quota and Trailhead Space Available" HTML table
    to a pandas.DataFrame.
    """
    pandas_version = parse_version(pandas.__version__)._version.release
    if pandas_version[:2] == (0, 23):
        # read_html malfunctions in pandas v0.23
        raise ImportError("pandas v0.23 is not supported due to https://git.io/fp9Zn")

    url = "https://www.nps.gov/yose/planyourvisit/fulltrailheads.htm"
    response = requests.get(url)
    response.raise_for_status()
    (wide_df,) = pandas.read_html(
        response.text,
        header=2,
        attrs={"id": "cs_idLayout2"},
        flavor="html5lib",
        parse_dates=["Date"],
    )
    wide_df = wide_df.iloc[:, :6]

    trailhead_df = (
        wide_df.melt(id_vars="Date", var_name="Trailhead", value_name="Spaces")
        .dropna()
        .sort_values(by=["Date"], kind="mergesort")
    )
    trailhead_df.Spaces = trailhead_df.Spaces.astype(int)
    assert len(trailhead_df) > 0

    return response, trailhead_df


yose_response, trailhead_df = get_trailhead_df()

# Extract report date
try:
    match = re.search(r"Report Date: ([0-9/]+)", yose_response.text)
    report_date = match.group(1)
    report_date = pandas.to_datetime(report_date, dayfirst=False)
    print("Report date is, ", report_date)
except Exception:
    report_date = yose_response.headers["Date"]
    report_date = pandas.to_datetime(report_date, utc=True)
report_date = report_date.date().isoformat()

space_df = trailhead_df.query(
    "Date in @dates and Spaces >= @spaces and Trailhead not in @exclude"
)
# space_df

space_str = "NO VACANCY" if space_df.empty else space_df.to_string(index=False)
text = f"{space_str}"

print(text)

#create csv so we can format in html
csv_space_df = space_df
csv_space_df.columns = ['Date', 'Trailhead', 'Spaces']
csv_data = "NO VACANCY" if space_df.empty else space_df.to_csv(r'hackcsv.csv', index=False)

html_file = pandas.read_csv('hackcsv.csv')
html_file = html_file.to_html()
phone_hours = f"""

According to https://www.nps.gov/yose/planyourvisit/fulltrailheads.htm

Yosemite Reservations: 209-372-0740 (Monday–Friday 9:00am–4:30pm)

Apply at https://yosemite.org/yosemite-wilderness-permit-request-form/
"""

# Detect if output_path has changed. If so, rewrite output. Also write previous text to previous_output_path so we can find the diff
output_has_changed = True
if output_path:
    output_path = pathlib.Path(output_path)
    if output_path.is_file():
        previous_text = output_path.read_text()
        output_has_changed = text != previous_text
    if output_has_changed:
        output_path.write_text(text)
print(f"output has changed: {output_has_changed}")

# determine whether to notify
notify = not space_df.empty and output_has_changed and min_report_date <= report_date


#Zapier
enable_zapier = True
zapier_url = "https://hooks.zapier.com/hooks/catch/7560244/oi4zve2"
if notify and enable_zapier:
    report = {
        "value1": html_file,
        "value_2": phone_hours
    }
    response = requests.post(zapier_url, data=report)
    print("SENDING EMAIL notify is ", notify)
    print("zapier status code", response.status_code)
    print(response.text)


