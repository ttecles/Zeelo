# Zeelo technical assignment

## Description

This module is intented for retrieving public transport information from a country and compare it with driving transport using Google Maps Directions API

## Requirements

- Python 3.x (tested only on 3.7)
- A Google Maps API key with permission to the following API's:
  - Directions API
  - Geocoding API
- The following modules must be installed: `pip install requests pandas folium branca`

## Usage
````python
from zratrans import Zratrans

#help(zratrans.Zratrans) for more information

z = Zratrans('YourAPIkey')

# retrive information from a country and select the top 5th percentil, sorted by population
z.retrive_cities('ES', 5)

# Calculate travel from Atocha (Madrid) to the cities
z.calculate_travel('Atocha, Madrid')

# returns a DataFrame with all the information
z.show_top_cities()

# returns a folium.Map object to show all the information
z.get_map()

```
