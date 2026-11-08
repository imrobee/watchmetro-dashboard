# WatchMetro: Metro Manila Accidents Dashboard

WatchMetro shows where and when traffic accidents happen on Metro Manila's major roads. It maps 12,633 accidents that the MMDA (Metropolitan Manila Development Authority) reported on Twitter between August 2018 and December 2020. You can narrow them down by time of day, month and city.

I built it for people who drive or ride on these roads every day: commuters, new drivers, drivers on unfamiliar routes, and anyone with road anxiety. It's one thing to hear that EDSA is dangerous. It's another to see that EDSA Guadalupe alone had 214 reported accidents in this period, and that more accidents were reported at 7 AM than at any other hour. Knowing where and when accidents cluster can help you plan a route or pick a time to leave.

For example, a good use case for this dashboard would be planning the safest time to visit a relative in Makati based on the accident history along your route.

**Live dashboard:** [watchmetro-dashboard.vercel.app](https://watchmetro-dashboard.vercel.app/)

## Tech Stack

The app is written in Python with [Dash](https://dash.plotly.com/), Plotly's framework for building dashboards around Python callbacks. pandas does the filtering, Plotly draws the charts, and Folium (a Python wrapper around the Leaflet map library) builds the map. ⟦Why Dash: the preprocessing was already in pandas, so staying in Python kept everything in one language.⟧

![Python](https://img.shields.io/badge/python-%233670A0.svg?style=for-the-badge&logo=python&logoColor=ffdd54)
![Plotly](https://img.shields.io/badge/plotly-%237A76FF.svg?style=for-the-badge&logo=plotly&logoColor=white)
![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=for-the-badge&logo=pandas&logoColor=white)


## What's on the dashboard

**Accident locations.** A map with a pin for every accident. Nearby pins group into numbered clusters, and the clusters break apart as you zoom in. A darker cluster holds more accidents. Hover over a cluster to outline the area it covers. Select a pin to see what happened, for example:

> **Vehicular accident**
> Location: EDSA BUENDIA SPLIT, Makati City
> When: 22 Aug 2018, 10:37 AM
> Involved: CAR AND SUV

**Vehicles involved.** How often each kind of vehicle shows up in an accident. Cars make up 43% of all vehicles involved, motorcycles 15% and buses 9%. Any vehicle type under 2% of the total goes into "Others", and a footnote lists the largest ones in that group.

**Accidents by month.** Total accidents for each calendar month. This chart follows the time of day and city filters but ignores the month filter, since it already splits the data by month. When you pick a month, that month's bar stays fully colored and the rest fade.

**Accidents by hour of day.** Accidents for each hour, shown for the time range you selected. This is where the morning rush shows up: reports climb from 40 at 3 AM to 1,035 at 7 AM.

## Using the filters

- **Time of day:** All Day, Morning (6 AM to 11:59 AM), Afternoon (12 PM to 5:59 PM) or Evening (6 PM to 5:59 AM).
- **Month:** any calendar month, or all of them.
- **City:** any of the 14 cities in the data, or all of them.

Pick your filters, then select **Apply filters**. The map and charts update together, and a spinner shows on each card while it loads. The button with the funnel icon, next to Apply, resets everything to All Day, all months and all cities.

The dashboard starts in light or dark mode to match your browser. The sun and moon button in the top-right corner switches it.

## Where the data comes from

The data is the [MMDA Traffic Incident Data](https://www.kaggle.com/datasets/esparko/mmda-traffic-incident-data/) set on Kaggle, compiled by Panji Brotoisworo. The MMDA posts traffic alerts on its Twitter account, like this one:

> MMDA ALERT: Vehicular accident at EDSA Rockwell SB involving SUV and L300 as of 9:13 AM. 1 lane occupied MMDA on site. #mmda

He wrote a script that collected these tweets and split each one into columns: date, time, city, location, latitude and longitude, road direction, incident type, lanes blocked, vehicles involved, the original tweet and its link. The raw file has 17,312 rows.

## Preprocessing and EDA

All of this happens in [WatchMetro_Preprocessing.ipynb](WatchMetro_Preprocessing.ipynb), which writes `dataset_cleaned.csv`. The dashboard reads only that cleaned file.

**1. Dropping rows with no city, location or type.** 187 rows had no city, 23 had no location and 57 had no type. I dropped those rows instead of filling them in by hand: filling them would have been slow, and a report with no details is hard to check. That left 17,078 rows.

**2. Deciding what counts as an accident.** "Traffic incident" covers a lot. About 3,900 rows are stalled vehicles with mechanical problems, and others are DPWH roadwork like asphalt laying or lane marking. They all slow traffic, but none of them says anything about how risky a road is. I defined an accident as an incident caused by road users, and kept only rows whose type contains "collision" or "accident". That left 12,633 rows, the number on the map.

**3. Cleaning the vehicle names.** The "Involved" column is free text, like "TAXI AND MC" or "2- CAR'S". I split each entry on "and" and commas, removed counts and punctuation, and turned plurals into singulars: "BUSES" becomes Bus and "CARS" becomes Car, while a name like "UV EXPRESS" keeps its S. Then I mapped abbreviations to one name: MC becomes Motorcycle, PUJ becomes Jeep, BU becomes Bus. AUVs and SUVs are counted as cars, because the MMDA isn't consistent about how it labels them. "PICK UP" and "PICKUP" count as the same vehicle, and entries with no vehicle listed are skipped. That gives 22,224 vehicle mentions across the 12,633 accidents.

**4. Choosing the vehicle chart.** I started with a pie chart, and it was unreadable. Even after cleaning there are 455 different vehicle names, mostly rare spellings and one-offs. Grouping everything under 2% into "Others" fixed most of that. After feedback on the project, I switched to a horizontal bar chart, which is easier to read at the size of a dashboard card.

**5. Fixing city names.** The raw data spells some cities two ways. I changed "Kalookan City" to "Caloocan", and fixed "ParaÃ±aque", an encoding error, to "Parañaque".

**6. Keeping rows with no time.** 142 accidents have no usable time. I kept them, because their location is still useful. They appear on the map and in the charts only when the time filter is set to All Day.

**7. Checking the coordinates.** I spot-checked a random sample of coordinates against the map, and they matched the reported locations. 95.6% of the raw rows are also flagged as high accuracy in the dataset.

## What the data can't tell you

- **It only covers major roads.** The dataset covers a set of major roads its author selected, mostly EDSA, C5 and other main roads. Quezon City has 6,601 accidents, more than half the total. Navotas has 2. Las Piñas and Muntinlupa have none. That shows where the MMDA was watching, not where it's safe.
- **Months combine different years.** The data starts on August 20, 2018. It has no reports at all for July and August 2020, and only 7 for April 2020, likely because of the COVID-19 lockdown. So October has three years of data, while July has only one. Compare months with that in mind.
- **A report isn't always a separate accident.** 187 rows are exact copies of another report, with the same date, time, place and vehicles. They might be the same tweet collected twice, or two separate accidents that match exactly. I can't tell which, so I left them in.
- **The counts aren't rates.** EDSA has more accidents than a side street partly because it carries far more cars. The dashboard shows how many accidents were reported, not how likely you are to be in one.

## Design decisions

**An Apply button instead of instant updates.** Rebuilding the map with every accident takes a moment. If each filter change redrew everything, picking a time, a month and a city would mean three redraws. With Apply, you set all three and wait once.

**Every accident on the map.** An earlier version showed at most 5,000 pins to save memory on a small server. The first map you saw was simply the first 5,000 rows of the file, which only cover August 2018 to March 2019. Now the pins are built in your browser from a compact list of points, so the full map is about 1.7 MB and shows everything.

**One color for the data.** Every chart uses the same blue, and gray for "Others". Each chart measures one thing, so a different color per bar wouldn't add any meaning. The blue is checked for contrast against both the light and dark backgrounds.

**Clusters instead of colored roads.** My original plan was to color each road by how many accidents happened on it, like a traffic congestion map. I went with clustered pins instead. ⟦Reason to confirm: clusters work straight from the coordinates in the data, while coloring roads would need road shapes to match each report to.⟧

## Technical details

- **Map Visualization.** Folium writes the whole map as an HTML page, which the dashboard shows in an iframe. It uses `FastMarkerCluster`, which sends the points as a plain list and creates the pins in the browser. The older version created one marker object per accident on the server, which is what made it heavy. Each filter combination is built once and then kept in memory, so applying the same filters again is fast.
- **Base map.** The map tiles come from OpenStreetMap. An earlier version used CARTO's free tiles, but CARTO now requires an API key, so they stopped loading. Dark mode uses the same tiles, inverted with a CSS filter, so there's still no key to manage.
- **Accident types.** The 12,633 kept rows spell their type 58 different ways, from typos like "MLTIPLE COLLISION" to a few rows where the whole tweet landed in the type column. The pin popups group them into three labels: Vehicular accident (11,736), Multiple collision (635) and Self accident (262).


## Running it yourself

You need Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:8050. To run it the way a server would, use `gunicorn app:app`.

To deploy on Vercel, run `vercel` from the project folder. Vercel picks up `app.py` on its own. On Railway or Render, set the start command to `gunicorn app:app`.

## Background

WatchMetro started as my final project for DATANVI ⟦(data visualization)⟧ at De La Salle University, in the third term of academic year 2024 to 2025. The PDF report in this repo covers the original proposal, the prototypes and the first finished version.

## Planned features

- **Road Filter:** Filter the selection by road (e.g., C-5, EDSA) for better route planning.


