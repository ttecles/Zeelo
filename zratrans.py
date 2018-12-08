"""
Core functionality, common across all API requests (including performing HTTP requests).
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import folium
import branca.colormap as cm
from io import StringIO

_DEFAULT_GOOGLEMAPS_BASE_URL = 'https://maps.googleapis.com'
_GOOGLEMAPS_DIRECTION_API = '/maps/api/directions/json'
_GOOGLEMAPS_GEOCODING_API = '/maps/api/geocode/json'

_DEFAULT_OPENDATASOFT_BASE_URL = 'https://public.opendatasoft.com'
_OPENDATASOFT_API_DOWNLOAD = '/api/records/1.0/download'


class Zratrans(object):
    """Generates a report that shows the ratio between the public transport network and the road network using
        Google Maps API
    """
    countries = {}

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls)

        # Get countries only first time a object is instantiated
        if not cls.countries:
            parameters = {"dataset": "geonames-country", "fields": "iso,country", "q": "population>0"}
            cls.countries = cls._get_csv_data(parameters=parameters, header=0, index_col=0, sep=';', na_filter=False,
                                        squeeze=True).to_dict()
        obj.countries = cls.countries
        return obj

    def __init__(self, gmaps_api_key):
        """Constructor

        :param gmaps_api_key: Maps API key
        :type gmaps_api_key: str
        """
        self.__gmaps_api_key = gmaps_api_key
        self.cities = None  # Dataframe to save top nth percentil sorted by population
        self.country = None  # Country of interest to evaluate ratio
        self.origin = None
        self.origin_geopoint = None

    def retrive_cities(self, country, percentile):
        """Get cities information from opendatasoft->worldcitypop dataset

        :param country: country cities in iso2 format.
            Check https://public.opendatasoft.com/explore/dataset/geonames-country/table/ for more information.
        :type country: str

        :param percentile: the cities in the top nth percentil, sorted by population. Value must be between 0 and 100
        :type percentile: float

        :return: None
        """
        # Input validations
        if percentile < 0 or percentile > 100:
            raise ValueError("percentile must be between 0 and 100")

        if country.upper() not in self.countries:
            raise ValueError("'%s' is not a valid country. Check available countries in "
                             + _DEFAULT_OPENDATASOFT_BASE_URL + '/explore/dataset/geonames-country/table/')

        # Core function
        self.country = country.upper()

        parameters = {'dataset': 'worldcitiespop', 'refine.country': self.country.lower(), 'q': 'population>0',
                      'fields': "city,population,geopoint"}
        data = self._get_csv_data(parameters = parameters, header=0, sep=";")
        p = data['population'].quantile(1 - percentile / 100)

        self.cities = data.loc[data['population'] > p].sort_values(by=['population'], ascending=False).drop_duplicates(subset='city')

        self.cities.reset_index(drop=True, inplace=True)

        print("Found {:d} cities".format(self.cities.shape[0]))

    def calculate_travel(self, origin='Victoria Station, London'):
        """
        calculates the ratio between the origin and all the cities listed in the cities attribute

        :param origin: origin from where to calculate time duration
        :type origin: str

        :return: None
        """
        self.origin = origin

        # Geocode the origin address to check if its a valid address, otherwise a ValueError will raise
        self.origin_geopoint = self._geocode(self.origin)
        if not self.origin_geopoint:
            raise ValueError('Not a valid origin \'{}\''.format(origin))

        distance_d = []
        duration_d = []
        distance_t = []
        duration_t = []
        ratio = []

        for i, row in self.cities.iterrows():
            # we use dest as string and not the geopoint because Directions API does not retrive results for transit
            # mode on some cities if using geopoint
            dest = row['city'] + ', ' + self.countries[self.country]

            # retrive directions in driving mode for the selected destination
            dist_d, dur_d = self._directions(self.origin,
                                             dest,
                                             mode="driving")

            # retrive directions in transit mode for the selected destination
            dist_t, dur_t = self._directions(self.origin,
                                             dest,
                                             mode="transit")

            # add collected information into lists
            distance_d.append(dist_d)
            duration_d.append(dur_d)
            distance_t.append(dist_t)
            duration_t.append(dur_t)
            try:
                ratio.append(dur_t / dur_d)
            except:
                ratio.append(None)

        # Generate DataFrame with Google Maps information
        maps = {'distance_driving': distance_d,
                'duration_driving': duration_d,
                'distance_transit': distance_t,
                'duration_transit': duration_t,
                'ratio': ratio}
        df_maps = pd.DataFrame.from_dict(maps)

        # Join new information into cities dataframe
        self.cities = self.cities.join(df_maps)

        print('Done. Average distance: {:.2f} km'.format(
            (self.cities['distance_driving'].mean() + self.cities['distance_transit'].mean()) / 2000))

    def show_top_cities(self, number=5):
        """ shows top cities from full dataframe

        :param number: Number of cities to show
        :type number: int

        :return: DataFrame with the top number cities
        """

        rows = self.cities.shape[0]
        return self.cities.loc[:min(number, rows)-1]

    def get_map(self):
        """ Print information graphicaly into a folium Map

        :return: folium.Map object
        """
        # Get geopoint from country
        try:
            center_geopoint = self._geocode(self.countries[self.country])
        except:
            center_geopoint = self.origin_geopoint

        s = pd.Series(1 / self.cities['ratio'])

        self.cities['ratio_n'] = (s - s.min()) / (s.max() - s.min())

        scala = cm.LinearColormap(['green', 'yellow', 'red'], vmin=0.5, vmax=1.5)

        origin_icon = folium.Icon(prefix="fa",
                                   icon="flag-checkered",
                                   icon_color="white",
                                   color="black")

        marker = folium.Marker([float(i) for i in self.origin_geopoint.split(',')], popup=self.origin,
                               icon=origin_icon)

        m = folium.Map(location=[float(i) for i in center_geopoint.split(',')], zoom_start=5)

        marker.add_to(m)

        for i, row in self.cities.dropna().iterrows():
            row['city'] = row['city'].title()
            row['duration_driving'] = str(timedelta(seconds=row['duration_driving']))
            row['duration_transit'] = str(timedelta(seconds=row['duration_transit']))
            detail = row[["city", "ratio", "duration_driving", "duration_transit"]].to_frame(name="info")
            color = scala(row['ratio'])
            folium.CircleMarker(
                location=[float(n) for n in row['geopoint'].split(',')],
                radius=round(25 * row['ratio_n'] + 5),
                popup=detail.to_html(),
                color=color + '30',
                fill=True,
                fill_opacity=0.75,
                fill_color=color
            ).add_to(m)
        return m

    @classmethod
    def _get_csv_data(self, parameters, *args, **kwargs):
        """
        Function to retrive data from opendatasoft download API

        :param parameters: request parameters
        :type parameters: dict
        :param args: additional parameters passed to pd.DataFrame.read_csv
        :param kwargs: additional parameters passed to pd.DataFrame.read_csv
        :return: pd.DataFrame
        """
        response = requests.get(_DEFAULT_OPENDATASOFT_BASE_URL + _OPENDATASOFT_API_DOWNLOAD, params=parameters)

        if response.status_code != 200:
            raise HTTPError(response.status_code)

        raw_data = StringIO(response.content.decode())
        return pd.read_csv(raw_data, *args, **kwargs)


    def _geocode(self, address):
        """Performs requests to the Google Maps Geocode API.

        NOTE: this function is implemented in github https://github.com/googlemaps/google-maps-services-python
        but we implement an easy solution for the Zeelo Test

        :param address: The address to geocode
        :type address: str

        :return: str in format '53.151524,-1.018151'
        """
        # Geocode the origin adress
        parameters = {'key': self.__gmaps_api_key, 'address': address}
        response = requests.get(_DEFAULT_GOOGLEMAPS_BASE_URL + _GOOGLEMAPS_GEOCODING_API, params=parameters)

        if response.status_code != 200:
            raise HTTPError(response.status_code)

        try:
            d_geopoint = response.json()['results'][0]['geometry']['location']
        except:
            return None

        return '{0},{1}'.format(d_geopoint['lat'], d_geopoint['lng'])

    def _directions(self, origin, destination, mode=None):
        """Performs requests to the Google Maps Directions API.

        NOTE: this function is implemented in github https://github.com/googlemaps/google-maps-services-python
        but some cities did not get the expected result becase it converts every string destination into lat/lng
        coordinate and Directions API does not return result with transit mode for some coordinates but it does if we
        send the destination as a name 'Bristol, United Kingdom'. Thus, we implement an easy solution for the Zeelo Test

        :param origin: The address or latitude/longitude value from which you wish to calculate directions.
        :type origin: str

        :param destination: The address or latitude/longitude value from which you wish to calculate directions
        :type destination: str

        :param mode: Specifies the mode of transport to use when calculating directions.
            One of "driving", "walking", "bicycling" or "transit"
        :type destination: str

        :return: tuple with distance and time duration
        """
        params = {'key': self.__gmaps_api_key, 'origin': origin, 'destination': destination}

        if mode:
            # NOTE(broady): the mode parameter is not validated by the Maps API
            # server. Check here to prevent silent failures.
            if mode not in ["driving", "walking", "bicycling", "transit"]:
                raise ValueError("Invalid travel mode.")
            params["mode"] = mode

        response = requests.get(_DEFAULT_GOOGLEMAPS_BASE_URL + _GOOGLEMAPS_DIRECTION_API, params=params)

        if response.status_code != 200:
            raise HTTPError(response.status_code)

        try:
            dist_d = response.json()['routes'][0]['legs'][0]['distance']['value']
            dur_d = response.json()['routes'][0]['legs'][0]['duration']['value']
        except:
            dist_d = None
            dur_d = None

        return dist_d, dur_d

class HTTPError(Exception):
    """An unexpected HTTP error occurred."""

    def __init__(self, status_code):
        self.status_code = status_code

    def __str__(self):
        return "HTTP Error: %d" % self.status_code
