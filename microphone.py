# Standard library imports.
import sys
import socket
import queue
import configparser
import threading
import contextlib
import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter.simpledialog import Dialog
import logging

logger = logging.getLogger(__name__)

handler = logging.StreamHandler(sys.stdout)
#logger.setLevel(logging.DEBUG)
#formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Related third party imports.
import sounddevice as sd
import numpy as np

# Local application/library specific imports.

# lbl -> label
# frm -> frame
# cbx -> combobox
# btn -> button
# cvs -> canvas
# scl -> scale
# pbr -> progressbar

RED: str = "red" 
YELLOW: str = "yellow"
GREEN: str = "green"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8089
DEFAULT_SENSITIVITY = 20


class SettingsWindow(Dialog):
    """Dialog window for choosing sound device."""

    def body(self, master):
        self.lbl_host_api = ttk.Label(master, text='Select host API:').pack(anchor='w')
        self.cbx_hostapi = ttk.Combobox(master, state='readonly', width=50)
        self.cbx_hostapi.pack()
        self.cbx_hostapi['values'] = [
            hostapi['name'] for hostapi in sd.query_hostapis()]

        self.lbl_sound_device = ttk.Label(master, text='Select sound device:').pack(anchor='w')
        self.device_ids = []
        self.cbx_devices = ttk.Combobox(master, state='readonly', width=50)
        self.cbx_devices.pack()

        self.cbx_hostapi.bind('<<ComboboxSelected>>', self.update_cbx_devices)
        with contextlib.suppress(sd.PortAudioError):
            self.cbx_hostapi.current(sd.default.hostapi)
            self.cbx_hostapi.event_generate('<<ComboboxSelected>>')

    def update_cbx_devices(self, *args):
        hostapi = sd.query_hostapis(self.cbx_hostapi.current())
        self.device_ids = [
            idx
            for idx in hostapi['devices']
            if sd.query_devices(idx)['max_input_channels'] > 0]
        self.cbx_devices['values'] = [
            sd.query_devices(idx)['name'] for idx in self.device_ids]
        default = hostapi['default_input_device']
        if default >= 0:
            self.cbx_devices.current(self.device_ids.index(default))

    def validate(self):
        self.result = self.device_ids[self.cbx_devices.current()]
        return True


class RecGui(Tk):

    stream = None
    connected: bool = False

    def connect(self):
        try:
            self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._s.connect((self._host, self._port))
            self.connected = True
            self.cvs_status.itemconfig(self.status, fill='green')
        except:
            self.connected = False
            self.cvs_status.itemconfig(self.status, fill='red')

    def load_config(self):
        self._config = config = configparser.ConfigParser()
        config.read('microphone.ini')
        try:
            app_config = config["app"]
        except KeyError:
            app_config = config["app"] = {
                "hostname": DEFAULT_HOST,
                "port": DEFAULT_PORT,
                "scl_microphone_sensitivity": DEFAULT_SENSITIVITY,
            }
        self._host = app_config.get("host", DEFAULT_HOST)
        try:
            self._port = app_config.getint("port", DEFAULT_PORT)
        except ValueError:
            self._port = 8089
        try:
            self._sensitivity = app_config.getint("scl_microphone_sensitivity", DEFAULT_SENSITIVITY)
        except ValueError:
            self._sensitivity = DEFAULT_SENSITIVITY

    def __init__(self):
        super().__init__()
        self.load_config()

        self.title('Recording GUI')

        padding = 10

        frm_right = ttk.Frame()
        frm_connection = ttk.Frame(frm_right)
        frm_left = ttk.Frame()
        frm_connection.pack(side=TOP, padx=padding, pady=padding, expand=True)

        # vvvv - connection informations
        self.cvs_status = Canvas(frm_connection, width=20, height=20)
        self.cvs_status.pack(side=LEFT)
        self.status = self.cvs_status.create_oval(1, 1, 19, 19, fill="red", tags="status")

        self.lbl_connection = ttk.Label(frm_connection)
        self.lbl_connection['text'] = f"{self._host}:{self._port}"
        self.lbl_connection.pack(side=RIGHT, fill=X, expand=FALSE)
        # ^^^^
        
        # vvvvvv - buttons
        # vvvv - settings button
        self.btn_settings = ttk.Button(
            frm_right, text='settings', command=self.on_settings)
        self.btn_settings.pack(side=TOP, padx=padding, pady=padding)
        # ^^^^
        # vvvv - reload button
        self.btn_reload = ttk.Button(
            frm_right, text='reload', command=self.on_reload)
        self.btn_reload.pack(side=TOP, padx=padding, pady=padding)
        # ^^^^
        # vvvv - save button
        self.btn_save = ttk.Button(
            frm_right, text='save', command=self.on_save)
        self.btn_save.pack(side=TOP, padx=padding, pady=padding)
        # ^^^^
        # vvvv - close button
        style = ttk.Style()
        style.configure('Custom.TButton', background='red')

        self.btn_close = ttk.Button(
            frm_right, text='close', style="Custom.TButton", command=self.destroy)
        self.btn_close.pack(side=TOP, padx=padding, pady=padding)
        # ^^^^
        # ^^^^^

        frm_right.pack(side="right", expand=True, padx=padding, pady=padding)
        frm_left.pack(side="left", expand=True)

        # vvvv microphone sensitivity and pbr_meter
        self.sensitivity = DoubleVar()
        self.sensitivity.set(self._sensitivity)

        style.configure("red.Vertical.TProgressbar", background=RED, 
                bordercolor=RED)
        style.configure("yellow.Vertical.TProgressbar", background=YELLOW, 
                bordercolor=YELLOW)
        style.configure("green.Vertical.TProgressbar", background=GREEN, 
                bordercolor=GREEN)
        
        self.scl_microphone_sensitivity = ttk.Scale(frm_left, orient=VERTICAL, length=200, from_=100, to=0, variable=self.sensitivity)
        self.pbr_meter = ttk.Progressbar(frm_left, orient=VERTICAL, length=200, mode='determinate', style="green.Vertical.TProgressbar")

        self.scl_microphone_sensitivity.pack(side="left")
        self.pbr_meter.pack(side="left")
        # ^^^^

        self.metering_q = queue.Queue(maxsize=1)

        # We try to open a stream with default settings first, if that doesn't
        # work, the user can manually change the device(s)
        self.create_stream()

        self.protocol('WM_DELETE_WINDOW', self.close_window)
        self.update_gui()

    def create_stream(self, device=None):
        if self.stream is not None:
            self.stream.stop()
        self.stream = sd.InputStream(
            device=device, channels=1, callback=self.audio_callback)
        self.stream.start()

    def audio_callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        volume_norm = np.linalg.norm(indata)*10
        try:
            self.metering_q.put_nowait(volume_norm)
        except queue.Full:
            pass

    def on_settings(self, *args):
        w = SettingsWindow(self, 'Settings')
        if w.result is not None:
            self.create_stream(device=w.result)

    def on_save(self, *args):
        self._config["app"] = {
            "host": self._host,
            "port": self._port,
            "scl_microphone_sensitivity": int(self.sensitivity.get()),
        }
        with open('microphone.ini', 'w') as configfile:
            self._config.write(configfile)

    def on_reload(self, *args):
        self._s.close()
        self.load_config()
        self.lbl_connection['text'] = f"{self._host}:{self._port}"
        self.sensitivity.set(self._sensitivity)

    def update_gui(self):
        if not self.connected:
            self.connect()
        try:
            volume_norm = self.metering_q.get_nowait()
        except queue.Empty:
            pass
        else:
            self.pbr_meter['value'] = volume_norm
            self.pbr_meter.step(volume_norm)
            s = self.sensitivity.get()
            logger.debug(f"{volume_norm:.2f} > {self.sensitivity.get()}")
            if volume_norm > s:
                #logger.debug(f"Microphone Volume: {volume_norm:.2f}")
                logger.debug(f"♬ ♪ ٩(ˊᗜˋ*)و")
                if self.connected:
                    try:
                        self._s.send(b"talk")
                    except:
                        self.connected = False
            if volume_norm < (s + 5) and volume_norm > (s - 5):
                self.pbr_meter['style'] = "yellow.Vertical.TProgressbar"
            elif volume_norm > s:
                self.pbr_meter['style'] = "green.Vertical.TProgressbar"
            else:
                self.pbr_meter['style'] = "red.Vertical.TProgressbar"
        self.after(100, self.update_gui)

    def close_window(self):
        self._s.close()
        self.destroy()


def main():
    app = RecGui()
    app.mainloop()


if __name__ == '__main__':
    main()
