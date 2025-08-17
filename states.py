import sys
import socket
import configparser
#import logging
#logger = logging.getLogger(__name__)
import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter.simpledialog import Dialog

# lbl -> label
# frm -> frame
# cbx -> combobox
# btn -> button
# cvs -> cvs_status

class States(Tk):

    stream = None
    connected: bool = False
    _last_state: bytes = None
    _last_entry: int = 0
    _host: str = "localhost"
    _port: int = 8089
  
    def connect(self):
        try:
            self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._s.connect((self._host, self._port))
            self.connected = True
            self.cvs_status.itemconfig(self.status, fill='green')
        except:
            self.connected = False
            self.cvs_status.itemconfig(self.status, fill='red')

    def load_pngtuber_config(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        c_sections = config.sections()
        states: list = []
        for state_name in c_sections:
            if state_name == "app":
                continue
            print(f"loading {state_name} ...")
            states.append(state_name)
            state = config[state_name]
        self.cbx_states['values'] = states

    def load_config(self):
        self._config = config = configparser.ConfigParser()
        config.read('states.ini')
        try:
            app_config = config["app"]
        except KeyError:
            app_config = config["app"] = {
                "hostname": "localhost",
                "port": 8089,
                "last_entry": 0,
            }
        self._host = app_config.get("host", "localhost")
        self._port = int(app_config.get("port", 8089))
        self._last_entry = int(app_config.get("last_state",0 ))
        self.cbx_states.current(self._last_entry)

    def __init__(self):
        super().__init__()

        self.title('States GUI')

        padding = 10

        frm_right = ttk.Frame()
        frm_state = ttk.Frame(frm_right)
        frm_connection = ttk.Frame(frm_right)
        frm_connection.pack(side=TOP, padx=padding, pady=padding, expand=True)
        frm_left = ttk.Frame()
        frm_state.pack(side=TOP, padx=padding, pady=padding, expand=True)

        # vvvv - connection informations
        self.cvs_status = Canvas(frm_connection, width=20, height=20)
        self.cvs_status.pack(side=LEFT)
        self.status = self.cvs_status.create_oval(1, 1, 19, 19, fill="red", tags="status")

        self.lbl_connection = ttk.Label(frm_connection)
        #self.lbl_connection['text'] = f"{self._host}:{self._port}"
        self.lbl_connection.pack(side=RIGHT, fill=X, expand=FALSE)
        # ^^^^
        
        self.cbx_states = ttk.Combobox(frm_state, state='readonly', width=50)
        self.cbx_states.pack(side=LEFT, padx=padding, pady=padding)
        self.load_pngtuber_config()
        self.load_config()
        self.lbl_connection['text'] = f"{self._host}:{self._port}"
        # vvvv - set state button
        self.set_state_button = ttk.Button(frm_state,
            text='set state', command=self.on_set_state)
        self.set_state_button.pack(side=RIGHT, padx=padding, pady=padding)
        # ^^^^
        
        # vvvvvv - buttons
        # vvvv - settings button
        self.btn_settings = ttk.Button(
            frm_right, text='settings', command=self.on_settings)
        self.btn_settings.pack(side=LEFT, padx=padding, pady=padding)
        # ^^^^
        # vvvv - reload button
        self.btn_reload = ttk.Button(
            frm_right, text='reload', command=self.on_reload)
        self.btn_reload.pack(side=LEFT, padx=padding, pady=padding)
        # ^^^^
        # vvvv - save button
        self.btn_save = ttk.Button(
            frm_right, text='save', command=self.on_save)
        self.btn_save.pack(side=LEFT, padx=padding, pady=padding)
        # ^^^^
        # vvvv - close button
        style = ttk.Style()
        style.configure('Custom.TButton', background='red')

        self.btn_close = ttk.Button(
            frm_right, text='close', style="Custom.TButton", command=self.destroy)
        self.btn_close.pack(side=LEFT, padx=padding, pady=padding)
        # ^^^^
        # ^^^^^

        frm_right.pack(side=RIGHT, expand=True, padx=padding, pady=padding)
        frm_left.pack(side=LEFT, expand=True)

        self.input_overflows = 0
        self.status_label = ttk.Label()
        self.status_label.pack(anchor='w')

        self.protocol('WM_DELETE_WINDOW', self.close_window)
        self.update_gui()

    def on_set_state(self, *args):
        state = self.cbx_states.current()
        try:
            last_state = self._last_state = f"state:{state}\r\n".encode()
            self._s.send(last_state)
        except (BrokenPipeError, ConnectionResetError):
            self.connected = False
    def on_settings(self, *args):
        w = SettingsWindow(self, 'Settings')
        if w.result is not None:
            self.create_stream(device=w.result)

    def on_save(self, *args):
        self._config["app"] = {
            "host": self._host,
            "port": self._port,
            "last_state": self.cbx_states.current(),
        }
        with open('states.ini', 'w') as configfile:
            self._config.write(configfile)

    def on_reload(self, *args):
        self._s.close()
        self.load_pngtuber_config()
        self.load_config()

    def update_gui(self):
        if not self.connected:
            self.connect()
            if self._last_state is not None:
                self._s.send(self._last_state)
                self._last_state = None
        self.after(100, self.update_gui)

    def close_window(self):
        self._s.close()
        self.destroy()


def main():
    app = States()
    app.mainloop()


if __name__ == '__main__':
    main()
