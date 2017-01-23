"""
    EveExploHelper - a small program to help explorers of New Eden (Eve Online)
    Copyright 2017 apocolypse600

    This file is part of EveExploHelper.

    EveExploHelper is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License version 3 as published by
    the Free Software Foundation.

    EveExploHelper is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with EveExploHelper.  If not, see <http://www.gnu.org/licenses/>.
"""

# Requests is apache 2.0 licenced
import requests
# PyQt is GPL v3
from PyQt5.QtCore import QThread, pyqtSignal, QObject, QTimer, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap, QColor
# Python standard library is PSF licenced
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4
import base64
from enum import Enum
from time import sleep
import urllib.parse as urlparse
import webbrowser


class StoppableHTTPServer(HTTPServer):
    """
    The base HTTPServer class is not designed to be stop and start on demand. This subclass adds that functionality
    """
    stopped = False

    def __init__(self, *args):
        self.stopped = False
        super(StoppableHTTPServer, self).__init__(*args)

    def serve_forever(self):
        while not self.stopped:
            self.handle_request()

    def force_stop(self):
        self.server_close()
        self.stopped = True


class HttpServerThread(QThread):
    """
    Helper thread to run the http server
    """

    def __init__(self, port):
        super(HttpServerThread, self).__init__()
        self.port = port
        self.server = None

    def _emit_signal(self, code):
        self.auth_code_received.emit(code[0])

    def run(self):
        auth_handler_class = AuthHandler
        auth_handler_class.functionCallback = self._emit_signal
        self.server = StoppableHTTPServer(('', self.port), auth_handler_class)
        self.server.serve_forever()

    def exit(self, returnCode=0):
        self.server.force_stop()
        # We call server_forever again to insure it exits the event loop.
        # This can also be achieved by sending a dummy request to the server, but this is easier
        self.server.serve_forever()
        self.terminate()

    auth_code_received = pyqtSignal(str, name='auth_code_recieved')


class AuthHandler(BaseHTTPRequestHandler):
    """
    We need to hand the authentication code back to the eveCRESTHandler object, but the AuthHandler is passed as a
    class to the HTTP server. To do this, we set a function pointer here that we can set statically and then
    call to get the information out
    """
    functionCallback = None

    def do_GET(self):
        # We get a heap of these that we don't want to parse
        if self.path == "/favicon.ico":
            return
        # response_html is actually interpreted html. Here it is just plain text, but if you go to modify it, keep
        # that in mind.
        # TODO: A little CSS would make this look a heap better
        response_html = 'SSO login success. You can now close this page.'
        self.send_response(200)
        self.send_header("Connection", "Close")
        self.end_headers()
        self.wfile.write(bytes(response_html, 'utf-8'))
        returned_values = urlparse.parse_qs(urlparse.urlparse(self.path).query)
        try:
            return_code = returned_values['code']
            state = returned_values['state'][0]
            if EveCRESTHandler.state == state:
                self.functionCallback(return_code)
        except KeyError as e:
            print('HTTP response was lacking the correct information')
            print(e)

    # Stops printing all GETs to the terminal
    def log_message(self, format, *args):
        return


class EveCRESTHandler(QObject):
    """
    Wrapper class to handle the connection, authentication and receiving of CREST data. I know PyCrest exists that
    probably does this much better than this implementation, but I wanted to use this opportunity to understand
    OAuth 2 at a lower level.
    """

    # Random value used for the state param of OAuth 2
    state = str(uuid4())

    def __init__(self, parent=None, user_agent='eveExploHelper', port=4173):
        super(self.__class__, self).__init__(parent)

        self.worker_thread = QThread()
        self.moveToThread(self.worker_thread)
        self.worker_thread.start()

        self.port = port
        self.endPoints = None
        self.clientID = None
        self.secret = None
        self.refreshToken = None
        self.accessToken = None
        self.server_thread = None
        self.headers = {'User-Agent': user_agent}
        self.authheaders = None
        self.character_name = "No character"
        self.status = self.Statuses.blank
        self.character_position = "No position"
        self.http_timeout = 10  # seconds before assuming http connection has timed out
        self.delay_before_retry = 5  # seconds before retrying the http connection

        tmp_char_image = QPixmap(128, 128)
        tmp_char_image.fill(QColor(0, 0, 0))
        self.character_portrait = tmp_char_image

        # Important note : These timers need to be initialised outside of the __init__ function or they won't fire
        # We create them in the separate setup function instead
        self.reauth_timer = None
        self.update_location_timer = None
        self.idle_http_server_shutdown_timer = None

    # Public slot that we use to initialise the timers on the correct thread so they fire correctly
    @pyqtSlot(str, str, str)
    def setup(self, client_ID=None, secret=None, refresh_token=''):

        # Timer that handles reauthenticating when the credentials expire
        self.reauth_timer = QTimer()
        self.reauth_timer.timeout.connect(self.auth_via_refresh_token)
        # Timer that handles polling for character location updates
        self.update_location_timer = QTimer()
        self.update_location_timer.timeout.connect(self._handle_position_update)
        # Timer that handles shutting down the http server if no response is given within 60 seconds
        self.idle_http_server_shutdown_timer = QTimer()
        self.idle_http_server_shutdown_timer.timeout.connect(self._http_server_timeout)
        self.idle_http_server_shutdown_timer.setInterval(60000)

        try:
            self._setup_public_endpoints()
        except requests.exceptions.RequestException as e:
            # Unable to setup public endpoint. We'll try again later, so not a huge deal at the moment
            print(e)

        self.clientID = client_ID
        self.secret = secret
        if refresh_token != '':
            self.refreshToken = refresh_token
            self.auth_via_refresh_token()
        else:
            self._update_status(self.Statuses.waiting_for_credentials)

    class Statuses(Enum):
        # The string here is used as a human readable / displayable form of the status
        blank = 'Waiting for instruction'
        connected = 'Authenticated and connected'
        error = 'Error'
        waiting_for_http_response = "Waiting for SSO web login"
        obtaining_public_endpoints = "Collecting URLs for public endpoints"
        obtaining_authenticated_endpoints = "Collecting URLs for authenticated endpoints"
        authenticating_via_refresh_token = "Authenticating via refresh token"
        waiting_for_credentials = "Waiting for login credentials"
        getting_character_name = "Getting character name"
        getting_character_portrait = "Getting character portrait"
        getting_character_position = "Getting character position"

    def get_status(self):
        return self.status

    def auth_via_refresh_token(self):
        self._update_status(self.Statuses.authenticating_via_refresh_token)
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(bytes(self.clientID + ':' + self.secret, 'utf-8')).decode(
                'utf-8'),
            'User-Agent': 'eveExploHelper'}
        query = {'grant_type': 'refresh_token', 'refresh_token': self.refreshToken}
        while True:
            try:
                response = requests.post('https://login.eveonline.com/oauth/token', params=query, headers=headers,
                                         timeout=self.http_timeout).json()
                self.accessToken = response['access_token']
                self.reauth_timer.start(
                    (response['expires_in'] - 30) * 1000)  # Refresh the token 30 seconds before expiry
                self._setup_auth_headers()
                self._setup_authed_endpoints()
                self.set_basic_char_data()
                break
            except requests.exceptions.RequestException as e:
                print(e)
                print('Network error while attempting to communicate with the eve servers, trying again in 5 seconds')
                self._update_status(self.Statuses.error)
                sleep(5)

        self._setup_auth_headers()

    @pyqtSlot(name='sso_auth')
    def sso_auth(self):
        self._start_http_server()
        webbrowser.open_new(
            'https://login.eveonline.com/oauth/authorize?response_type=code&redirect_uri='
            'http://localhost:' + str(
                self.port) + '/&client_id=' + self.clientID + '&scope=characterLocationRead&state=' + self.state)
        self._update_status(self.Statuses.waiting_for_http_response)
        self.idle_http_server_shutdown_timer.start()

    @pyqtSlot()
    def logout(self):
        tmp_char_image = QPixmap(128, 128)
        tmp_char_image.fill(QColor(0, 0, 0))
        self.character_portrait = tmp_char_image
        self.authheaders = None
        self.reauth_timer.stop()
        self.update_location_timer.stop()
        self.character_name = "No character"

        self._update_status(self.Statuses.waiting_for_credentials)

        self.character_information_updated.emit(self.character_name, self.character_portrait)

    def set_basic_char_data(self):
        while True:
            try:
                self.character_name = self._retrieve_character_name()
                break
            except requests.exceptions.RequestException:
                self._update_status(self.Statuses.error)
                sleep(5)

        while True:
            try:
                character_portrait_bytes = self._retrieve_character_portrait_bytes()
                image = QImage()
                image.loadFromData(character_portrait_bytes)
                self.character_portrait = QPixmap(image)
                break
            except requests.exceptions.RequestException:
                self._update_status(self.Statuses.error)
                sleep(5)

        if self.character_name is not None and self.character_portrait is not None:
            self._update_status(self.Statuses.connected)
            self.character_information_updated.emit(self.character_name, self.character_portrait)
        else:
            self._update_status(self.Statuses.error)

    @pyqtSlot(str)
    def auth_via_code(self, code):
        self._stop_http_server()
        self.idle_http_server_shutdown_timer.stop()
        headers = self.headers
        headers['Authorization'] = 'Basic ' + base64.b64encode(
            bytes(self.clientID + ':' + self.secret, 'utf-8')).decode('utf-8')
        query = {'grant_type': 'authorization_code', 'code': code}
        # Try to get a response every 5 seconds
        while True:
            try:
                response = requests.post(self.endPoints['authEndpoint']['href'], params=query, headers=headers).json()
                access_token = response['access_token']
                self.accessToken = access_token
                self.refreshToken = response['refresh_token']
                self.new_refresh_token.emit(self.refreshToken)
                self.reauth_timer.start(
                    (response['expires_in'] - 30) * 1000)  # Refresh the token 30 seconds before expiry
                self._setup_auth_headers()
                self._setup_authed_endpoints()
                self.set_basic_char_data()
                break
            except requests.exceptions.RequestException as e:
                print(e)
                print('Network error while attempting to authenticate with the eve servers, trying again in 5 seconds')
                self._update_status(self.Statuses.error)
                sleep(5)

    def get_character_position(self):
        return self.character_position

    def get_character_portrait(self):
        return self.character_portrait

    def get_character_name(self):
        return self.character_name

    def _update_status(self, new_status):
        self.status = new_status
        self.status_updated.emit(new_status)

    def _http_server_timeout(self):
        self._stop_http_server()
        self._update_status(self.Statuses.waiting_for_credentials)

    def _handle_position_update(self):
        new_pos = self._retrieve_character_position()

        if new_pos != self.character_position:
            # We have a new location
            self.new_char_location.emit(new_pos)
            self.character_position = new_pos

        # We poll slower if the character is offline. Even though polling every 5 seconds is within the rate limits, it's not needed
        # The location is cached server side for a duration of 5 seconds, so no point in polling faster
        if self.character_position == "Offline":
            self.update_location_timer.setInterval(60 * 1000)  # 60 seconds
        else:
            self.update_location_timer.setInterval(5 * 1000)  # 5 seconds

    def _setup_auth_headers(self):
        self.authheaders = self.headers
        self.authheaders['Authorization'] = 'Bearer ' + self.accessToken

    def _setup_authed_endpoints(self):
        self._update_status(self.Statuses.obtaining_authenticated_endpoints)

        # We need the public decode endpoint here. We try and initialise it on creation,
        # but if it's not set at the moment (eg the network was down when the program was launched), we need to set it now
        if 'href' not in self.endPoints.get('decode', {}):
            while True:
                # Need to set the public endpoint
                try:
                    self._setup_public_endpoints()
                    break
                except requests.exceptions.RequestException as e:
                    # Network error
                    print(e)
                    print(
                        'Network error while attempting to communicate with the eve servers, trying again in 5 seconds')
                    self._update_status(self.Statuses.error)
                    sleep(self.delay_before_retry)

        root_node = self.endPoints['decode']['href']

        while True:
            try:
                self.endPoints['char'] = \
                    requests.get(root_node, headers=self.authheaders, timeout=self.http_timeout).json()['character'][
                        'href']
                self.endPoints['location'] = \
                    requests.get(self.endPoints['char'], headers=self.authheaders, timeout=self.http_timeout).json()[
                        'location']['href']
                break
            except requests.exceptions.RequestException as e:
                print(e)
                print('Network error while attempting to communicate with the eve servers, trying again in 5 seconds')
                self._update_status(self.Statuses.error)
                sleep(5)

        self.update_location_timer.setInterval(5000)
        self.update_location_timer.start()

    def _retrieve_character_position(self):
        self._update_status(self.Statuses.getting_character_position)
        if 'location' in self.endPoints:
            try:
                response = requests.get(self.endPoints['location'], headers=self.authheaders,
                                        timeout=self.http_timeout).json()
                if 'solarSystem' in response:
                    new_pos = response['solarSystem']['name']
                else:
                    new_pos = 'Offline'
                self._update_status(self.Statuses.connected)
                return new_pos
            except requests.exceptions.RequestException as e:
                print(e)
                print("Network error retrieving character location")
                self._update_status(self.Statuses.error)
                raise
        else:
            print('Location endpoint not set')

    def _retrieve_character_portrait_bytes(self, size='128x128'):
        self._update_status(self.Statuses.getting_character_portrait)
        if 'char' in self.endPoints:
            try:
                avatar_url = \
                    requests.get(self.endPoints['char'], headers=self.authheaders, timeout=self.http_timeout).json()[
                        'portrait'][size]['href']
                data = requests.get(avatar_url).content
                self._update_status(self.Statuses.connected)
                return data
            except requests.exceptions.RequestException as e:
                print(e)
                print("Network error retrieving character portrait")
                self._update_status(self.Statuses.error)
                raise
        else:
            print('Character endpoint not set')

    def _retrieve_character_name(self):
        self._update_status(self.Statuses.getting_character_name)
        if 'char' in self.endPoints:
            try:
                response = requests.get(self.endPoints['char'], headers=self.authheaders,
                                        timeout=self.http_timeout).json()
                self._update_status(self.Statuses.connected)
                return response['name']
            except requests.exceptions.RequestException as e:
                print(e)
                print("Network error retrieving character name")
                self._update_status(self.Statuses.error)
                raise
        else:
            print('Character endpoint not set')

    def _start_http_server(self):
        self.server_thread = HttpServerThread(port=self.port)
        self.server_thread.auth_code_received.connect(self.auth_via_code)
        self.server_thread.start()

    def _stop_http_server(self):
        if self.server_thread is not None:
            if self.server_thread.isRunning():
                self.server_thread.exit()
                self.server_thread = None

    def _setup_public_endpoints(self):
        self._update_status(self.Statuses.obtaining_public_endpoints)
        try:
            self.endPoints = requests.get('https://crest-tq.eveonline.com', headers=self.headers,
                                          timeout=self.http_timeout).json()
        # TODO: Perhaps try and handle the different exceptions differently. For now, a catch all will do
        except requests.exceptions.RequestException:
            raise

    new_char_location = pyqtSignal(str, name='new_char_location')
    new_refresh_token = pyqtSignal(str, name='new_refresh_token')
    character_information_updated = pyqtSignal(str, object, name='charactor_information_updated')
    status_updated = pyqtSignal(object, name='status_updated')
