# WatchMetro: Metro Manila Accidents Dashboard

[![Live Dashboard](https://img.shields.io/badge/Live%20Dashboard-Click%20Here-blue?style=for-the-badge)](https://watchmetro-dashboard-production.up.railway.app/)

A comprehensive interactive dashboard for visualizing traffic accident data across Metro Manila from 2018-2020. Built with Plotly Dash and deployed on Railway.

## Dashboard Features

### Interactive Visualizations
- **Interactive Map**: Folium map showing accident locations with clustered markers
- **Vehicle Involved in Accidents**: Horizontal bar chart showing vehicles most involved in accidents
- **Total Accidents per Month**: Bar chart displaying accident patterns across months
- **Accidents by Hour of Day**: Line chart showing accident distribution throughout the day

### Filtering
- **Time Period**: Filter by Morning (6AM-12PM), Afternoon (12PM-6PM), Evening (6PM-6AM), or All Day
- **Month**: Filter by specific months or view all months
- **City**: Filter by specific Metro Manila cities or view all cities
- **Real-time Updates**: Apply filters instantly with loading indicators

## Dataset Information

- **Time Period**: 2018-2020
- **Coverage**: Metro Manila cities
- **Author**: Panji Brotoisworo
- **Source**: https://www.kaggle.com/datasets/esparko/mmda-traffic-incident-data/

## Usage Guide

### Basic Navigation
1. **Select Filters**: Choose time period, month, and city filters
2. **Apply Changes**: Click "Apply Filters" to update all visualizations
3. **Theme Toggle**: Use the toggle in the top-right to switch between dark mode and light mode
4. **Map Interaction**: Click on map markers to view detailed accident information

## Data Processing 

### Data Cleaning
- Automatic datetime parsing and formatting
- Vehicle name standardization (BU→BUS, MC→MOTORCYCLE, etc.)
- Time period classification (Morning/Afternoon/Evening)
- Missing data handling

### Data Preprocessing and Exploratory Data Analysis (EDA)
1. **Data Loading and Initial Exploration**: The dataset was loaded into a pandas DataFrame, and basic information like the head, info, and null counts were viewed. The earliest and latest dates in the dataset were also checked.
Handling Null Values: Rows with null values in 'City', 'Location', or 'Type' were dropped. The remaining null counts were checked.
2. **Filtering by Incident Type**: The dataset was filtered to include only rows where the 'Type' column contains "collision" or "accident", as these are considered more relevant to the dashboard's goal of visualizing risk. Incidents related to mechanical failures or road maintenance were excluded.
3. **Analyzing Involved Vehicles**: The 'Involved' column was cleaned and normalized to count the occurrences of different vehicle types. A pie chart was generated to visualize the distribution of involved vehicles, merging less frequent types into an 'OTHERS' category.
4. **Time-based Analysis**: The 'Date' column was converted to datetime objects to extract the month name and hour of the day. Bar charts were created to show the total accidents per month and a line plot to show incidents by the hour of the day.
5. **Geospatial Visualization**: A scatter map was generated using Plotly to visualize the locations of incidents based on Latitude and Longitude, with the size of the points representing the number of incidents at each location.
6. **City Name Cleaning**: The 'City' column was cleaned by correcting inconsistent spellings ("Kalookan City" to "Caloocan" and "ParaÃ±aque" to "Parañaque").
7. **Saving the Cleaned Data**: The processed DataFrame was saved to a new CSV file named "dataset_cleaned.csv".

## Authors

- **Jan Robee Feliciano** - [jan_feliciano@dlsu.edu.ph](mailto:jan_feliciano@dlsu.edu.ph)
- **Alphonse Juanito Sese** - [alphonse_sese@dlsu.edu.ph](mailto:alphonse_sese@dlsu.edu.ph)

## Data Disclaimer

- This dashboard presents information on traffic incidents in Metro Manila reported by the MMDA from 2018 to 2020. 

## Issues & Support

If you encounter any issues or have suggestions, reach out to Robee Feliciano at [robee.feliciano@gmail.com](mailto:robee.feliciano@gmail.com)

---

**Live Dashboard**: [https://watchmetro-dashboard-production.up.railway.app/](https://watchmetro-dashboard-production.up.railway.app/)

*Last Updated: August 2025*
