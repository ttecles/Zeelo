import unittest
from folium import Map
from zratrans import Zratrans


class TestZratrans(unittest.TestCase):
    _gmaps_api_key = 'AIzaSyCzBudv-TPRBmeTTzzapPmxS1go1dsgOjs'

    @classmethod
    def setUpClass(cls):
        cls.zratrans = Zratrans(gmaps_api_key=cls._gmaps_api_key)

    def setUp(self):
        self.z = Zratrans(self._gmaps_api_key)

    def tearDown(self):
        del self.z

    def test_Zratrans(self):
        self.assertIn('ES', self.z.countries)
        self.assertEqual(self.z.countries['ES'], 'Spain')
        self.assertEqual(Zratrans(self._gmaps_api_key).countries,
                         self.z.countries)

    def test_retrive_cities(self):

        with self.assertRaises(ValueError) as cm:
            self.z.retrive_cities('XX', 5)

        with self.assertRaises(ValueError) as cm:
            self.z.retrive_cities('ES', 101)

        with self.assertRaises(ValueError) as cm:
            self.z.retrive_cities('ES', -1)

        self.assertIsNone(self.z.cities)
        self.z.retrive_cities('GB', 5)
        self.assertIsNotNone(self.z.cities)

    def test_calculate_travel(self):
        self.z.retrive_cities('ES', 20)

        with self.assertRaises(ValueError) as cm:
            self.z.calculate_travel('qawsedqawsed')

        self.z.calculate_travel('Madrid')
        self.assertIn('ratio', self.z.cities.columns)

    def test_show_top_cities(self):
        self.z.retrive_cities('GB', 5)
        df = self.z.show_top_cities()
        self.assertEqual(5, df.shape[0])

        df = self.z.show_top_cities(10)
        self.assertEqual(10, df.shape[0])

    def test_get_map(self):
        self.z.retrive_cities('GB', 5)
        self.z.calculate_travel()

        m = self.z.get_map()
        self.assertIsInstance(m, Map)

if __name__ == "__main__":
    unittest.main()
