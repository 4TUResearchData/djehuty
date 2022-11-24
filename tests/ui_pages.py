"""
This module tests browsing various UI pages.
"""

import unittest
import requests

BASE_URL = "http://127.0.0.1:8080"
TIMEOUT  = 15 # Stricter because it's the user interface

class TestUiPages(unittest.TestCase):
    """Class to test whether user interface points can be reached."""

    def __init__(self, *args, **kwargs):
        super(TestUiPages, self).__init__(*args, **kwargs)

    ## Access
    ## ------------------------------------------------------------------------
    def test_static_pages (self):
        """Tests whether the admin panel can be reached."""

        ## Info page
        ## ----------------------------------------------------------------
        response = requests.get(
            url  = f"{BASE_URL}/info/about-your-data/manage-share",
            headers = { "Accept": "text/html" },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 200)

        ## Portal page
        ## ----------------------------------------------------------------
        response = requests.get(
            url  = f"{BASE_URL}/portal",
            headers = { "Accept": "text/html" },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 200)

        ## Category overview page
        ## ----------------------------------------------------------------
        response = requests.get(
            url  = f"{BASE_URL}/category",
            headers = { "Accept": "text/html" },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 200)

        ## Category pages
        ## ----------------------------------------------------------------
        for category in [ 13431, 13603, 13594, 13551, 13410, 13578,
                          13376, 13611, 13630, 13652, 13474, 13362,
                          13647, 13566, 13500, 13464, 13453, 13427,
                          13559, 13517, 13448, 13588, 13360, 13401,
                          13440, 13421, 13620, 13524, 13509, 13661,
                          13544, 13457, 13667, 13415, 13571, 13369,
                          13493, 13385, 13438, 13539, 13462, 13498,
                          13561, 13530, 13459, 13496, 13590, 13497,
                          13372, 13436, 13373, 13404, 13422, 13526,
                          13432, 13494, 13467, 13672, 13532, 13425,
                          13592, 13484, 13673, 13361, 13540, 13535,
                          13670, 13623, 13423, 13593, 13458, 13515,
                          13510, 13564, 13658, 13471, 13516, 13669,
                          13537, 13668, 13538, 13575, 13389, 13409,
                          13466, 13479, 13430, 13460, 13520, 13563,
                          13543, 13549, 13506, 13523, 13629, 13449,
                          13574, 13567, 13513, 13451, 13548, 13653,
                          13519, 13511, 13542, 13572, 13485, 13426,
                          13521, 13374, 13383, 13504, 13499, 13375,
                          13508, 13621, 13591, 13437, 13470, 13398,
                          13525, 13402, 13443, 13514, 13397, 13622,
                          13488, 13656, 13501, 13419, 13482, 13386,
                          13627, 13577, 13444, 13495, 13666, 13649,
                          13371, 13487, 13655, 13476, 13648, 13428,
                          13545, 13380, 13502, 13644, 13473, 13595,
                          13478, 13468, 13573, 13446, 13439, 13465,
                          13663, 13589, 13624, 13570, 13505, 13403,
                          13671, 13518, 13651, 13550, 13569, 13616,
                          13384, 13418, 13547, 13420, 13392, 13365,
                          13598, 13638, 13461, 13481, 13665, 13615,
                          13435, 13576, 13399, 13396, 13664, 13512,
                          13650, 13393, 13654, 13379, 13408, 13417,
                          13626, 13602, 13483, 13486, 13441, 13596,
                          13489, 13604, 13597, 13445, 13382, 13442,
                          13472, 13605, 13584, 13490, 13381, 13628,
                          13546, 13640, 13400, 13475, 13434, 13657,
                          13447, 13364, 13378, 13492, 13491, 13456,
                          13507, 13618, 13586, 13581, 13368, 13610,
                          13587, 13366, 13568, 13599, 13469, 13601,
                          13585, 13660, 13477, 13646, 13606, 13390,
                          13395, 13641, 13433, 13659, 13480, 13411,
                          13413, 13582, 13613, 13363, 13553, 13377,
                          13619, 13600, 13625, 13391, 13416, 13454,
                          13608, 13662, 13583, 13614, 13632, 13455,
                          13414, 13503, 13634, 13642, 13637, 13636,
                          13633, 13579, 13394, 13645, 13556, 13607,
                          13609, 13367, 13580, 13412, 13558, 13555,
                          13612, 13631, 13617, 13554, 13643, 13635,
                          13557, 13387, 13639, 13388, 13552 ]:
            response = requests.get(
                url  = f"{BASE_URL}/categories/{category}",
                headers = { "Accept": "text/html" },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 200)

        ## Institution pages
        ## ----------------------------------------------------------------
        for institution in [ "Delft_University_of_Technology",
                             "University_of_Twente",
                             "Eindhoven_University_of_Technology",
                             "Wageningen_University_and_Research",
                             "Other_institutions" ]:
            response = requests.get(
                url  = f"{BASE_URL}/institutions/{institution}",
                headers = { "Accept": "text/html" },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 200)
