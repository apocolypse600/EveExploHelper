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
# Keyboard is MIT licenced
import keyboard
# PyQt is GPL v3
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QPushButton
from PyQt5.QtCore import QSettings, pyqtSignal, pyqtSlot, Qt, QTimer
# Python standard library is PSF licenced
import os
import sys
import re
import wave
# Simple audio is MIT licenced
import simpleaudio as sa
# Other files from this project, GPL v3 licenced
from EveCRESTHandler import EveCRESTHandler
from ui.mainWindow import Ui_MainWindow
from ui.keyBindDialog import Ui_KeyBindDialog
from ui.featuresWindow import Ui_FeaturesWindow

MAX_FONT_SIZE = 256
PORT = 4173
VERSION = '1.0.0'
# TODO implement this
# The idea is to use the wormhole name we have to get a risk assessment from http://wh.pasta.gg/ or similar
feature_risk_assess_wormhole = True


# Called if the settings ini is not found, we write a new one with the default settings
def write_default_settings(settings):
    settings.setValue('main/shortcut', 'shift+0+9')

    settings.setValue('CREST/client_id', '')
    settings.setValue('CREST/secret', '')
    settings.setValue('CREST/saveRefreshToken', 0)
    settings.setValue('CREST/refreshToken', '')

    settings.setValue('features/reminderBookmarkWormhole', 1)
    settings.setValue('features/evePraisalClipboard', 1)
    settings.setValue('features/wormholeTypeKeycombo', 1)
    settings.setValue('features/reminderBookmarkWormholeSound', 1)
    settings.setValue('features/reminderBookmarkWormholeFlashText', 1)

    settings.setValue('sound/path', 'bookmarkTheHole.wav')

    settings.setValue('network/port', 4173)


# Get's a price estimate from evepraisal
def get_price_estimate(content):
    r = requests.post('http://evepraisal.com/estimate', data={'raw_paste': content,
                                                              'hide_buttons': "false",
                                                              'paste_autosubmit': "false",
                                                              'market': "30000142",  # Jita
                                                              'save': "false"})

    # What follows is a fairly hacky way of scraping the isk value from the returned webpage. This should probably
    # be made more robust
    return_string = r.content.decode()
    start_string = r'<td colspan="3" style="text-align: right"><span class="nowrap">Total Sell Value</span><br />'
    end_string = r'</th>'

    start = return_string.index(start_string)
    end = return_string.index(end_string, start)

    return_string = return_string[start:end].split('<span class="nowrap">')[4]
    return_string = return_string[0:return_string.index('<')]

    return return_string


# This isn't a very neat solution to the problem, but it was the only solution that I found that worked consistently
# Set the fontsize to a max size, then keep decreasing it until the bounding box of the text is within the bounding
# box of the label
def fit_text_in_label(label):
    font = label.font()
    contents_rect = label.contentsRect()
    binding_width = contents_rect.width()
    binding_height = contents_rect.height()

    font_size = 1
    font.setPointSize(font_size)
    while font_size < MAX_FONT_SIZE:
        font_metrics = QtGui.QFontMetrics(font)
        bounding_rect = font_metrics.boundingRect(label.text())

        if bounding_rect.width() <= binding_width and bounding_rect.height() <= binding_height and font_size:
            font_size += 1
            font.setPointSize(font_size)
        else:
            break

    label.setFont(font)


# Checks the system name against the known naming pattern from a
def is_wormhole(system_name):
    if system_name is None:
        return False
    # Start of string followed by J followed by any number of integers followed by end of string
    p = re.compile('^J[0-9]+$')
    return bool(p.match(system_name))


# Window opened to choose a new key in the keyBindingWindow
class ModifyKeyBindWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ModifyKeyBindWindow, self).__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        self.label = QtWidgets.QLabel("Press any key to add the keybind or ESC to unbind")
        layout.addWidget(self.label)
        self.keyName = None
        keyboard.hook(self.update_key)
        self.setWindowTitle('Modify keybind')
        # Need to handle the accept slot with a custom signal otherwise the program hangs
        self.finished.connect(self.accept)

    def update_key(self, key_event):
        self.keyName = key_event.name
        # There were some issues saving modifiers with which side of the keyboard they were on
        # For instance the keyboard event for 'left shift' won't work in the shortcut, we need it to just be 'shift'
        # So here we check the key against all modifiers, and just use the main modifier code if it's a match
        for modifier in keyboard.all_modifiers:
            if modifier in self.keyName:
                self.keyName = modifier

        keyboard.unhook(self.update_key)
        self.finished.emit()

    # Avoid closing the dialog on press of escape key. By default this is bound to reject, so can't check the key was pressed
    # This way, it get handles like the other keypresses, and we know esc was hit rather than just closing the dialog
    def keyPressEvent(self, event):
        if not event.key() == Qt.Key_Escape:
            super(ModifyKeyBindWindow, self).keyPressEvent(event)

    def get_key(self):
        return self.keyName

    finished = pyqtSignal()


class FeaturesWindow(QtWidgets.QDialog):
    def __init__(self, settings, parent=None):
        super(FeaturesWindow, self).__init__(parent)
        self.ui = Ui_FeaturesWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Features')
        self.settings = settings
        self.ui.checkBoxReminderBookmarkWormhole.stateChanged.connect(self.handle_reminder_bookmark_state)
        self.stopPlayingTimer = QTimer()
        self.stopPlayingTimer.setInterval(100)  # every 100 ms
        self.stopPlayingTimer.timeout.connect(self.handle_stop_playing_sound)
        self.ui.pushButtonTestSnd.pressed.connect(self.start_stop_playing_sound)
        self.play_object = None
        self.snd = None

        """
        Note QtCheckboxes have three states:    Unticked -> 0
                                                Halfticked -> 1
                                                Ticked -> 2
        We are only interested in the states 0 and 2, so we need to convert the state to a boolean to get the ticked
        / unticked we are interested in. When reading a string from the QSettings object, this means we cast to an int
        and then boolean. This is why int(bool(newState)) and bool(int(settings...)) are used so often.
        """
        # TODO: Wrap QSettings in a wrapper class to make this much nicer
        self._setup_checkbox(self.ui.checkBoxReminderBookmarkWormhole, 'features/reminderBookmarkWormhole')
        self._setup_checkbox(self.ui.checkBoxClipboardShortcut, 'features/evePraisalClipboard')
        self._setup_checkbox(self.ui.checkBoxWormholeTypeKeybind, 'features/wormholeTypeKeycombo')
        self._setup_checkbox(self.ui.checkBoxPlaySound, 'features/reminderBookmarkWormholeSound')
        self._setup_checkbox(self.ui.checkBoxFlashText, 'features/reminderBookmarkWormholeFlashText')

        self.ui.checkBoxSaveRefreshToken.setChecked(bool(int(self.settings.value('CREST/saveRefreshToken'))))
        self.ui.checkBoxSaveRefreshToken.stateChanged.connect(self.handle_save_refresh_token)

        self.ui.pushButtonBrowseSnd.clicked.connect(self.change_sound_path)
        self.ui.labelSndPath.setText(self.settings.value('sound/path'))

        # Need to manually call this, as if it wasn't checked the content that should be disabled won't be
        self.handle_reminder_bookmark_state(self.ui.checkBoxReminderBookmarkWormhole.checkState())

    # When we toggle off the reminder bookmark feature, all it's sub options no longer matter
    # As such, we disable their control to indicate this is the case. This means we also need to re-enable them if the
    # feature is turned back on. This function handles this disable / enable toggle
    def handle_reminder_bookmark_state(self, newState):
        self.ui.checkBoxPlaySound.setEnabled(bool(newState))
        self.ui.checkBoxFlashText.setEnabled(bool(newState))
        self.ui.pushButtonBrowseSnd.setEnabled(bool(newState))
        self.ui.pushButtonTestSnd.setEnabled(bool(newState))
        self.ui.labelSndPath.setEnabled(bool(newState))

    def handle_save_refresh_token(self, state):
        if state == Qt.Checked:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setText(
                "Saving the CREST refresh token with allow the application to login. However this token will be saved in PLAIN TEXT in the ini. Anyone who can access this ini " +
                "will be able to access your character location")
            save_button = QPushButton('I understand the risks, save the refresh token')
            msg_box.addButton(save_button, QMessageBox.YesRole)
            no_save_button = QPushButton("Don't save the token")
            msg_box.addButton(no_save_button, QMessageBox.NoRole)
            msg_box.addButton(QPushButton('Cancel'), QMessageBox.RejectRole)
            msg_box.exec()
            if msg_box.clickedButton() == save_button:
                self.settings.setValue('CREST/saveRefreshToken', '1')
            else:
                self.ui.checkBoxSaveRefreshToken.setCheckState(Qt.Unchecked)
                self.settings.setValue('CREST/saveRefreshToken', '0')
        else:
            self.settings.setValue('CREST/refreshToken', '')
            self.settings.setValue('CREST/saveRefreshToken', '0')

    # Start playing the sound, or stop it if one is playing
    def start_stop_playing_sound(self, sound_path=None):
        if self.play_object is not None:
            if self.play_object.is_playing():
                self.play_object.stop()
                return 0

        if sound_path is None:
            sound_path = self.settings.value('sound/path')

        # Play the sound
        try:
            self.play_object = sa.WaveObject.from_wave_file(sound_path).play()
            self.stopPlayingTimer.start()
            self.ui.pushButtonTestSnd.setText("Stop")
        except (wave.Error, FileNotFoundError) as e:
            msg_box = QMessageBox()
            msg_box.setText(str(e))
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.exec()
            return 1
        return 0

    def change_sound_path(self):
        if self.play_object is not None:
            if self.play_object.is_playing():
                self.play_object.stop()

        filename = QFileDialog.getOpenFileName(self, 'New sound file', '.', '*.wav')[0]
        if filename != '':
            if self.start_stop_playing_sound(filename) == 0:  # we played the sound successfully
                self.settings.setValue('sound/path', filename)
                self.ui.labelSndPath.setText(filename)

    def handle_stop_playing_sound(self):
        if self.play_object is not None:
            if not self.play_object.is_playing():
                self.ui.pushButtonTestSnd.setText("Play")

    def _setup_checkbox(self, checkbox, value):
        checkbox.setChecked(bool(int(self.settings.value(value))))
        checkbox.stateChanged.connect(lambda newState: self.settings.setValue(value, int(bool(newState))))


# Window to modify the key binding to analyse the clipboard
class KeyBindingDialog(QtWidgets.QDialog):
    def __init__(self, global_keyCombo, parent=None):
        super(KeyBindingDialog, self).__init__(parent)
        self.ui = Ui_KeyBindDialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Keybinding for evepraisal check')
        self.modify_key_dialog = None
        self.new_key_combo = None
        self.buttonArray = []
        self.ui.pushButtonAddAnother.pressed.connect(lambda: self.add_key("unbound", self.buttonArray, False))

        # Turn the current key combo into a string of buttons
        for key in global_keyCombo.split('+'):
            self.add_key(key, self.buttonArray)

        self.show()

    # Handle changing / removing a key in the current keybinding
    def modify_key(self, btn):
        btn_index = self.ui.horizontalLayoutButtons.indexOf(btn)
        self.modify_key_dialog = ModifyKeyBindWindow(self)
        if self.modify_key_dialog.exec():
            key_pressed = self.modify_key_dialog.get_key()
            if key_pressed == 'esc':
                self.buttonArray.remove(btn)
                btn.setParent(None)  # Easy way to remove + delete the widget
            else:
                self.ui.horizontalLayoutButtons.itemAt(btn_index).widget().setText(key_pressed)

    # Add a new key to the keybinding
    def add_key(self, key_text, button_array, place_at_start=True):
        new_button = QtWidgets.QPushButton(key_text, self)
        if place_at_start:
            self.ui.horizontalLayoutButtons.insertWidget(0, new_button)
        else:
            self.ui.horizontalLayoutButtons.insertWidget(self.ui.horizontalLayoutButtons.count() - 1, new_button)
        new_button.pressed.connect(lambda: self.modify_key(new_button))
        button_array.append(new_button)

    def accept(self):
        shortcut_str = ''
        for button in self.buttonArray:
            if button.text() != 'unbound':
                shortcut_str += button.text() + '+'
        shortcut_str = shortcut_str[:-1]  # remove the last +
        self.new_key_combo = shortcut_str
        super(KeyBindingDialog, self).accept()

    def get_new_key_combo(self):
        return self.new_key_combo


# Window to handle CREST SSO and show status
class CRESTWindow(QtWidgets.QDialog):
    def __init__(self, CREST_handler, parent=None):
        super(CRESTWindow, self).__init__(parent)

        self.CREST_handler = CREST_handler
        self.setWindowTitle('CREST Information')
        self.begin_sso_auth.connect(self.CREST_handler.sso_auth)
        self.CREST_handler.charactor_information_updated.connect(self.update_UI)
        self.CREST_handler.new_char_location.connect(self.update_location)
        self.btn = QtWidgets.QPushButton()
        if self.CREST_handler.status == self.CREST_handler.Statuses.obtaining_public_endpoints or self.CREST_handler.status == self.CREST_handler.Statuses.waiting_for_credentials:
            self.btn.setText("Start SSO")
            self.btn.pressed.connect(self.begin_sso_auth.emit)
        else:
            self.btn.setText("Logout")
            self.btn.pressed.connect(self.CREST_handler.logout)

        self.charImage = QtWidgets.QLabel()
        self.charImage.setPixmap(self.CREST_handler.get_character_portrait())

        self.charNameLabel = QtWidgets.QLabel(self.CREST_handler.get_character_name())
        self.charNameLabel.setAlignment(Qt.AlignCenter)
        self.charLocationLabel = QtWidgets.QLabel(self.CREST_handler.get_character_position())
        self.charLocationLabel.setAlignment(Qt.AlignCenter)

        self.labelStatus = QtWidgets.QLabel()
        status = self.CREST_handler.get_status()
        if status is not None:
            self.labelStatus.setText(status.value)
        self.CREST_handler.status_updated.connect(lambda status: self.labelStatus.setText(status.value))

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.charImage, alignment=Qt.AlignCenter)
        layout.addWidget(self.charNameLabel, alignment=Qt.AlignCenter)
        layout.addWidget(self.charLocationLabel, alignment=Qt.AlignCenter)
        layout.addWidget(self.btn, alignment=Qt.AlignCenter)
        layout.addWidget(self.labelStatus, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.show()

    def update_location(self, new_position):
        self.charLocationLabel.setText(new_position)

    @pyqtSlot(str, object)
    def update_UI(self, name, portrait):
        self.charImage.setPixmap(portrait)
        self.charNameLabel.setText(name)

        if self.CREST_handler.get_status() == self.CREST_handler.Statuses.connected:
            self.btn.setText("Logout")
            self.btn.disconnect()
            self.btn.pressed.connect(self.CREST_handler.logout)
        else:
            self.btn.setText("Start SSO")
            self.charLocationLabel.setText("No position")
            self.charNameLabel.setText("No character")
            self.btn.disconnect()
            self.btn.pressed.connect(self.begin_sso_auth.emit)

    send_credentials = pyqtSignal(str, str, str)
    begin_sso_auth = pyqtSignal()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('EveExploHelper ' + VERSION)
        self.ui.actionKey_Binding.triggered.connect(self.open_key_bind_window)
        self.ui.actionFeatures.triggered.connect(self.open_features_window)
        self.label_status_corner = QtWidgets.QLabel()
        # 300 pixels just seems like a good width that always fits the text
        self.label_status_corner.setFixedWidth(300)
        self.label_status_corner.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ui.menuBar.setCornerWidget(self.label_status_corner)
        self.key_bind_window = None
        self.features_window = None
        self.CREST_window = None
        self.old_location = None
        self.refreshToken = None

        self.blink_text_timer = QTimer()
        self.blink_text_timer.timeout.connect(self.blink_main_text)
        self.blink_text_timer.setInterval(250)
        self.blink_text_number = 20  # 20 flashes at 250 ms spacing = 5 seconds of flashing
        self.blink_text_flashes_left = 0

        # Read the settings from the settings.ini file
        system_location = os.path.dirname(os.path.abspath(sys.argv[0]))
        QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, system_location)
        self.settings = QSettings("settings.ini", QSettings.IniFormat)
        if os.path.exists(system_location + "/settings.ini"):
            print("Loading settings from " + system_location + "/settings.ini")
        else:
            print("Unable to read settings.ini, creating new default settings.ini ...")
            write_default_settings(self.settings)
        self.global_keyCombo = self.settings.value('main/shortcut')
        CREST_client_id = self.settings.value('CREST/client_id')
        CREST_secret = self.settings.value('CREST/secret')
        refresh_token = self.settings.value('CREST/refreshToken')

        keyboard.add_hotkey(self.global_keyCombo, self.analyse_clipboard_text)
        # Turn the wormhole name into a hotkey deceleration (commas between each letter) and then attach it to
        # the update_label_text function
        if bool(int(self.settings.value('features/wormholeTypeKeycombo'))):
            self.handle_keybinds('wormholes.csv')

        try:
            self.port = int(self.settings.value('network/port'))
        except TypeError:
            self.port = 4173

        if CREST_client_id != '' and CREST_secret != '':
            self.CREST_handler = EveCRESTHandler(port=self.port)
            self.CREST_handler.status_updated.connect(self.handle_CREST_handler_status_update)
            self.CREST_handler.new_char_location.connect(self.handle_new_position)
            self.CREST_handler.new_refresh_token.connect(self.received_new_refresh_token)
            self.send_credentials.connect(self.CREST_handler.setup)
            self.send_credentials.emit(CREST_client_id, CREST_secret, refresh_token)
            self.ui.actionCREST.triggered.connect(self.open_CREST_window)
        else:
            self.ui.actionCREST.setEnabled(False)
        self.show()

    # TODO: Stop the border blinking along with the text. Honestly I'd rather get rid of the border,
    # but it makes the text fit inside the bounds better, so that would need to be looked at
    def blink_main_text(self):
        if self.ui.labelMain.isHidden():
            self.ui.labelMain.show()
        else:
            self.ui.labelMain.hide()
        self.blink_text_flashes_left -= 1
        if self.blink_text_flashes_left < 0:
            self.blink_text_timer.stop()
            self.ui.labelMain.show()  # Make sure it's visible now that the blinking has stopped

    # Yes I know there are many python libraries that read csv's better than this, and csv's are complicated to read
    # However this is a very simple csv, so there is no point dragging in extra dependencies for this
    def handle_keybinds(self, filepath, unbind=False):
        with open(filepath) as f:
            for line in f:
                if line != '':
                    wh_name = line.split(',')[0]
                    wh_type = line.split(',')[1]
                    if unbind:
                        keyboard.remove_hotkey(",".join(wh_name))
                    else:
                        keyboard.add_hotkey(",".join(wh_name), self.update_label_text, args=[wh_type])

    def analyse_clipboard_text(self):
        if bool(int(self.settings.value('features/evePraisalClipboard'))):
            clipboard = QtGui.QGuiApplication.clipboard()
            clipboard_text = clipboard.text().strip()
            print(clipboard_text)
            estimate = get_price_estimate(clipboard_text)
            GUI.ui.labelMain.setText(estimate + " isk")

        fit_text_in_label(GUI.ui.labelMain)

    def reminder_to_bookmark_wormhole(self):
        if bool(int(self.settings.value('features/reminderBookmarkWormholeFlashText'))):
            self.blink_text_flashes_left = self.blink_text_number
            GUI.ui.labelMain.setText('BOOKMARK THE HOLE')
            self.blink_text_timer.start()
            fit_text_in_label(GUI.ui.labelMain)
        if bool(int(self.settings.value('features/reminderBookmarkWormholeSound'))):
            try:
                wave_obj = sa.WaveObject.from_wave_file(self.settings.value('sound/path'))
                wave_obj.play()
            except (wave.Error, FileNotFoundError):
                # We won't crash on an error, but errors are more rigorously handled and reported to the user if they test
                # in the options menu. I don't really want to pop a dialog up here as the user has just jumped into a
                # wormhole, so it's a bad time to have to deal with other dialog menus, maybe even minimising Eve.
                pass

    def handle_new_position(self, new_pos):
        if (is_wormhole(self.old_location) and new_pos != "Offline") \
                or (is_wormhole(new_pos) and self.old_location != "No position" and self.old_location != "Offline") and \
                        bool(int(self.settings.value('features/reminderBookmarkWormhole'))):
            self.reminder_to_bookmark_wormhole()
        self.old_location = new_pos

    def open_key_bind_window(self):
        self.key_bind_window = KeyBindingDialog(self.global_keyCombo, parent=self)
        if self.key_bind_window.exec():
            new_key_combo = self.key_bind_window.get_new_key_combo()
            keyboard.remove_hotkey(self.global_keyCombo)
            keyboard.add_hotkey(new_key_combo, self.analyse_clipboard_text)
            self.settings.setValue('main/shortcut', new_key_combo)
            self.global_keyCombo = new_key_combo

    def open_CREST_window(self):
        self.CREST_window = CRESTWindow(self.CREST_handler, parent=self)

    def open_features_window(self):
        old_keybind_setting = bool(int(self.settings.value('features/wormholeTypeKeycombo')))
        self.features_window = FeaturesWindow(settings=self.settings, parent=self)
        if self.features_window.exec():
            # We need to set / unset the keybinds if the setting was changed
            new_keybind_setting = bool(int(self.settings.value('features/wormholeTypeKeycombo')))
            if old_keybind_setting != new_keybind_setting:
                self.handle_keybinds('wormholes.csv', unbind=old_keybind_setting)
            if bool(int(self.settings.value('CREST/saveRefreshToken'))):
                if self.refreshToken is not None:
                    self.settings.setValue('CREST/refreshToken', self.refreshToken)
            else:
                self.settings.setValue('CREST/refreshToken', '')

    def received_new_refresh_token(self, token):
        self.refreshToken = token
        if bool(int(self.settings.value('CREST/saveRefreshToken'))):
            self.settings.setValue('CREST/refreshToken', self.refreshToken)

    def update_label_text(self, text):
        self.ui.labelMain.setText(text)
        fit_text_in_label(self.ui.labelMain)

    def handle_CREST_handler_status_update(self, status):
        if status == self.CREST_handler.Statuses.connected.error:
            self.label_status_corner.setStyleSheet("QLabel {color : red; }")
        else:
            self.label_status_corner.setStyleSheet("QLabel {color : green; }")
        self.label_status_corner.setText('CREST status: ' + status.value)
        self.repaint()

    # Note: before using this technique, make sure the size policy for the label is set to ignored
    # If you don't, very bad things will happen
    def resizeEvent(self, evt):
        fit_text_in_label(self.ui.labelMain)
        QtWidgets.QMainWindow.resizeEvent(self, evt)

    send_credentials = pyqtSignal(str, str, str)


app = QtWidgets.QApplication(sys.argv)
GUI = MainWindow()
GUI.resize(700, 100)  # Trigger the resize to set the right font size
sys.exit(app.exec())
