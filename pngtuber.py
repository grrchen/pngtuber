# Standard library imports.
import time
import random
import socket
import select
import random
import os
import sys
import logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
#logger.setLevel(logging.DEBUG)
#formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

import traceback

from enum import Enum
import configparser

# Related third party imports.
import pygame as pg
try:
    import gif_pygame as gif_pg
    animated_images_supported: bool = True
except ModuleNotFoundError:
    logger.error("gif_pygame was not found! Without the gif_pygame library animated graphics are not supported. Please install the gif_pygame fork from https://github.com/grrchen/gif-pygame if you want to use animated graphics like gifs, or apngs.")
    animated_images_supported: bool = False

# Local application/library specific imports.


DEFAULT_CAPTION: str = "PNGTuber"
DEFAULT_HOST: str = "localhost"
DEFAULT_PORT: int = 8089
SCREEN_WIDTH: int = 800
SCREEN_HEIGHT: int = 600

framerate: int = 60


class Eyes(Enum):
    OPEN = 1
    CLOSED = 2


class Mouth(Enum):
    OPEN = 1
    CLOSED = 2


class StateGroup(pg.sprite.Group):
    def talk(self):
        logger.debug("Talking")
        for sprite in self.sprites():
            sprite.talk()

    def resize(self, w, h):
        for sprite in self.sprites():
            sprite.resize(w, h)


ANIMATED_FILE_EXT: tuple = (".apng", ".gif")
IGNORE_RESIZE_REQ_MSG: str = "Ignoring request, size did not change"


def scale(img, dimension):
    if isinstance(img, gif_pg.GIFPygame):
        scaled_image = img.copy()
        gif_pg.transform.scale(scaled_image, dimension)
    else:
        scaled_image = pg.transform.scale(img, dimension)
    return scaled_image


class Layer(pg.sprite.Sprite):

    rect = None
    _loops: int = -1
    _loop_pause: int | list = None
    _loop_end_time: float = None
    _loop_pause: int = None
    _random_loop_pause: bool = False
    _is_animated: bool = False

    def __init__(self, image_path, width, height, loops=-1, loop_pause=None):
        super().__init__()
        if loop_pause is not None:
            loops = 0
        self._loops = loops
        self.loop_pause = loop_pause
        self._last_resize_req = (width, height)
        self._image_path = image_path
        orig_image = self.load_image(image_path)
        self._orig_image = orig_image
        w, h = orig_image.get_size()
        ratio = self.get_ratio(w, h, width, height)
        width = int(w*ratio)
        height = int(h*ratio)
        self._image = image = scale(orig_image, (width, height))
        self.rect = image.get_rect()

    def load_image(self, image_path, loop_pause=None):
        if animated_images_supported:
            for file_ext in ANIMATED_FILE_EXT:
                if image_path.lower().endswith(file_ext):
                    image = gif_pg.load(image_path, self._loops).convert_alpha()
                    self._is_animated = True
                    break
            else:
                image = pg.image.load(image_path).convert_alpha()
        else:
            image = pg.image.load(image_path).convert_alpha()
        return image

    @property
    def image(self):
        if isinstance(self._image, gif_pg.GIFPygame):
            return self._image.blit_ready()
        return self._image

    def get_ratio(self, w, h, sw, sh):
        rw = sw / w
        rh = sh / h
        ratio = rw if rw < rh else rh
        return ratio

    def _resize(self, image, w, h):
        iw, ih = image.get_size()
        ratio = self.get_ratio(iw, ih, w, h)
        width = int(iw*ratio)
        height = int(ih*ratio)
        return scale(image, (width, height))

    def resize(self, w, h):
        resize_req = (w, h)
        if self._last_resize_req == resize_req:
            logger.debug(IGNORE_RESIZE_REQ_MSG)
            return
        self._last_resize_req = resize_req
        self._image = self._resize(self._orig_image, w, h)

    def talk(self):
        pass

    def update(self):
        if self._is_animated and self._image.ended:
            if self._loop_end_time is None:
                self._loop_end_time = time.time()
            if self._loop_pause is not None and time.time() - self._loop_end_time < self._current_loop_pause:
                return
            else:
                self._image.reset()
                self._loop_end_time = None
                if self._random_loop_pause:
                    self._current_loop_pause = random.randint(*self._loop_pause)
                    logger.debug(f"New loop pause for layer {self._image_path}")

    @property
    def loop_pause(self):
        return self._loop_pause

    @loop_pause.setter
    def loop_pause(self, value):
        self._loop_pause = value
        if isinstance(value, (list, tuple)):
            if len(value) == 2:
                self._loop_pause = value
                self._current_loop_pause = random.randint(*self._loop_pause)
                self._random_loop_pause = True
            else:
                logger.error(f"Invalid value: {value}")
        elif isinstance(value, int):
            self._loop_pause = self._current_loop_pause = value


class PNGTuberState(Layer):

    rect = None

    def __init__(self, pos, base_dir, eo_mc, ec_mc, eo_mo, ec_mo, width: int, height: int):
        pg.sprite.Sprite.__init__(self)
        self._talk: bool = False
        self._force_update: bool = False
        self._orig_images = []
        self._scaled_images = []
        self._current_frame = 0
        self._last_resize_req = (width, height)
        for state_image in (eo_mc, ec_mc, eo_mo, ec_mo):
            if state_image is None:
                self._orig_images.append(None)
                self._scaled_images.append(None)
                continue
            state_image_path = os.path.join(base_dir, state_image)
            orig_image = self.load_image(state_image_path)
            self._orig_images.append(orig_image)
            scaled_image = self._resize(orig_image, width, height)
            self._scaled_images.append(scaled_image)
        self._image = image = self.get_first_image()
        if image is not None:
            self.rect = image.get_rect()
        #self.rect.center = pos
        self.time = pg.time.get_ticks()
        self._next_blink: int = random.randint(4000, 6000)
        self._blink_duration: int = 250
        self._talk_cooldown: int = 250
        self._state = Eyes.OPEN

    def get_first_image(self):
        for image in self._scaled_images:
            if image is not None:
                return image

    def resize(self, w, h):
        resize_req = (w, h)
        if self._last_resize_req == resize_req:
            logger.debug(IGNORE_RESIZE_REQ_MSG)
            return
        self._last_resize_req = resize_req
        self._scaled_images = []
        for orig_image in self._orig_images:
            if orig_image is None:
                continue
            self._scaled_images.append(self._resize(orig_image, w, h))

    def talk(self):
        if not self._talk:
            self._force_update = True
        self._talk = True
        self.talk_time = pg.time.get_ticks()

    def update(self):
        if self._talk:
            eo_img = self._scaled_images[2]
            ec_img = self._scaled_images[3]
            if pg.time.get_ticks() - self.talk_time >= self._talk_cooldown:
                logger.debug("Stop talking")
                self._talk = False
                self._force_update = True
                eo_img = self._scaled_images[0]
                ec_img = self._scaled_images[1]
        else:
            eo_img = self._scaled_images[0]
            ec_img = self._scaled_images[1]
        if self._state == Eyes.OPEN:
            if self._force_update:
                if eo_img is None:
                    return
                # Set the image
                self._image = eo_img
                # Fetch the rectangle object that has the dimensions of the image
                # Update the position of this object by setting the values of rect.x and rect.y
                self.rect = eo_img.get_rect()
                self._force_update = False
            if pg.time.get_ticks() - self.time >= self._next_blink:
                if ec_img is None:
                    return
                # Set the image
                self._image = ec_img
                # Fetch the rectangle object that has the dimensions of the image
                # Update the position of this object by setting the values of rect.x and rect.y
                self.rect = ec_img.get_rect()
                self._next_blink = random.randint(4000, 6000)
                self.time = pg.time.get_ticks()
                self._state = Eyes.CLOSED
                logger.debug("Eyes closed")
        elif self._state == Eyes.CLOSED:
            if self._force_update:
                if ec_img is None:
                    return
                # Set the image
                self._image = ec_img
                # Fetch the rectangle object that has the dimensions of the image
                # Update the position of this object by setting the values of rect.x and rect.y
                self.rect = ec_img.get_rect()
                self._force_update = False
            if pg.time.get_ticks() - self.time >= self._blink_duration:
                if eo_img is None:
                    return
                logger.debug(f"next blink: {self._next_blink}")
                # Set the image
                self._image = eo_img
                # Fetch the rectangle object that has the dimensions of the image
                # Update the position of this object by setting the values of rect.x and rect.y
                self.rect = eo_img.get_rect()
                self.time = pg.time.get_ticks()
                self._state = Eyes.OPEN
                logger.debug("Eyes opend")


class App:
    _host: str
    _port: int
    _s_width: int
    _s_height: int

    def __init__(self):
        self._command_buffer: dict = {}
        self.loop()

    def connect(self):
        self._server = server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.setblocking(False)
        server.bind((self._host, self._port))
        server.listen(5) # become a server socket, maximum 5 connections

    def load_config(self):
        self._config = config = configparser.ConfigParser()
        config.read('config.ini')

        self._layers_config = layers_config = configparser.ConfigParser()
        layers_config.read('layers.ini')

    def load_app_config(self):
        try:
            app_config = self._config["app"]
        except KeyError:
            app_config = self._config["app"] = {"background_color": "magenta", 
                "caption": DEFAULT_CAPTION, 
                "host": DEFAULT_HOST, "port": DEFAULT_PORT,
                "width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}
        self._background_color: str = app_config.get("background_color", "magenta")
        self._host: str = app_config.get("host", DEFAULT_HOST) 
        self._port: int = int(app_config.get("port", DEFAULT_PORT))
        self._s_width: int = int(app_config.get("width", SCREEN_WIDTH))
        self._s_height: int = int(app_config.get("height", SCREEN_HEIGHT))
        self._app_config = app_config

    def save_config(self):
        with open('config.ini', 'w') as config_fh:
            self._config.write(config_fh)

    def load_layers(self, layer_list):
        for layer_name in layer_list:
            layer_config = self._layers_config[layer_name]
            base_dir = layer_config["base_dir"]
            image = layer_config["image"]
            loop_pause = layer_config.get("loop_pause", None)
            if loop_pause is not None:
                tmp = loop_pause.split("-")
                if len(tmp) == 1:
                    loop_pause = int(loop_pause)
                else:
                    loop_pause = [int(value) for value in tmp]
            loops = int(layer_config.get("loops", -1))
            image_path = os.path.join(base_dir, image)
            layer = Layer(image_path, self._s_width, self._s_height, loops, loop_pause)
            logger.info(f"adding layer for image: {image_path}")
            self._state_group.add(layer)

    def _layers_str_to_list(self, layers_str: str) -> list:
        layer_list: list = []
        if layers_str is not None:
            for layer_name in layers_str.split(","):
                layer_list.append(layer_name.strip())
        return layer_list

    def load_states(self):
        config = self._config
        self._states = states = []
        c_sections = config.sections()
        for state_name in c_sections:
            if state_name == "app":
                continue
            logger.info(f"Loading {state_name} ...")
            state = config[state_name]
            base_dir = state.get("base_dir", "")
            if "image" in state:
                eo_mo = ec_mo = eo_mc = ec_mc = state.get("image", None)
            else:
                ec_mc = state.get("ec_mc", None)
                eo_mc = state.get("eo_mc", None)
                ec_mo = state.get("ec_mo", None)
                eo_mo = state.get("eo_mo", None)

            self._state_group = state_group = StateGroup()

            # vvvv - front layers
            layers: str = state.get("layers", None)
            layer_list: list = self._layers_str_to_list(layers)
            # ^^^^
            # vvvv - back layers
            layers_back: str = state.get("layers.back", None)
            layer_back_list: list = self._layers_str_to_list(layers_back)
            # ^^^^
            self.load_layers(layer_back_list)
            png_tuber_state = PNGTuberState((0, 0), base_dir, eo_mc, ec_mc, eo_mo, ec_mo, self._s_width, self._s_height)
            #png_tuber_state.resize(self._s_width, self._s_height)
            state_group.add(png_tuber_state)
            self.load_layers(layer_list)
            states.append(state_group)

    def get_next_command(self, s) -> bytes:
        command_buffer = self._command_buffer
        command: bytes = command_buffer.get(s, b"")
        new_data: bytes = s.recv(1024)
        if not new_data:
            del command_buffer[s]
            self._socket_list.remove(s)
            return None
        data: bytes = command + new_data
        if len(data) == 0:
            return None
        last_char: bytes = b""
        command = b""
        for i, char in enumerate(data):
            char = bytes([char])
            if last_char == b"\r" and char == b"\n":
                command_buffer[s] = data[i+1:]
                return command[:-1]
            command += char
            last_char = char
        if command:
            command_buffer[s] = command_buffer.get(s, b"") + command
        return None

    def loop(self):
        self.load_config()
        self.load_app_config()

        self.connect()
        server = self._server
        self._socket_list = socket_list = [server]
        command_buffer = self._command_buffer

        # Initialise pygame
        pg.init()
        pg.display.set_caption(self._app_config.get("caption", DEFAULT_CAPTION))

        screen = pg.display.set_mode([self._s_width, self._s_height], pg.RESIZABLE)
        background_color = self._background_color
        logger.debug(f"background_color: {background_color}")
        if background_color.startswith("#"):
            background_color = pg.Color(background_color)
        screen.fill(background_color)
        s_width, s_height = screen.get_width(), screen.get_height()
        self._s_width, self._s_height = s_width, s_height

        # Create sprites
        self.load_states()
        states: list = self._states
        png_tuber_state = states[0]

        clock = pg.time.Clock()

        # Main loop, run until window closed
        running = True
        while running:
            # Get the list sockets which are readable
            try:
                inputready, outputready, exceptready = select.select(socket_list, [], [], 0.01)
            except select.error:
                break
            except socket.error:
                break

            for s in inputready:
                if s == server:
                    # handle the server socket
                    client, address = server.accept()
                    logger.info(f"Got connection {client.fileno()} from {address}")
                    socket_list.append(client)
                elif s == sys.stdin:
                    # handle standard input
                    junk = sys.stdin.readline()
                    running = 0
                else:
                    # handle all other sockets
                    try:
                        # data = s.recv(BUFSIZ)
                        #data = s.recv(1024)
                        data = self.get_next_command(s)
                        if data is None:
                            continue
                        if data:
                            if data == b"talk":
                                png_tuber_state.talk()
                            else:
                                try:
                                    cmd, body = data.split(b":", 1)
                                    body = body.strip()
                                    if cmd == b"state":
                                        state_index = int(body)
                                        if state_index < len(states):
                                            png_tuber_state = states[state_index]
                                            png_tuber_state.resize(s_width, s_height)
                                        else:
                                            logger.error("State index out of range")
                                    else:
                                        logger.error("Unknown cmd")
                                except ValueError as err:
                                    logger.error(err)
                                    logger.error(f"data: {data}")
                        else:
                            logger.info(f"{s.fileno()} closed connection")
                            s.close()
                            del command_buffer[s]
                            socket_list.remove(s)
                    except (socket.error):
                        # Remove
                        del command_buffer[s]
                        socket_list.remove(s)

            # Check events
            for event in pg.event.get():
                logger.debug(f"Event type: {event.type}")
                if event.type == pg.QUIT:
                    running = False
                elif event.type == pg.VIDEORESIZE:
                    self._s_width, self._s_height = screen.get_width(), screen.get_height()
                    s_width, s_height = self._s_width, self._s_height
                    self._app_config["width"] = str(s_width)
                    self._app_config["height"] = str(s_height)
                    png_tuber_state.resize(s_width, s_height)
                    self.save_config()
                    pg.display.update()
                    #screen = pg.display.set_mode([s_width, s_height], pg.RESIZABLE)
                elif event.type == pg.VIDEOEXPOSE:
                    #png_tuber1.resize(s_width, s_height)
                    pg.display.update()
                elif event.type == pg.KEYUP:
                    key = event.key
                    if key in (pg.K_0, pg.K_1, pg.K_2, pg.K_2, pg.K_3, pg.K_4, pg.K_5, pg.K_6, pg.K_7, pg.K_8, pg.K_9):
                        logger.debug(f"Key pressed: {key}")
                        index = key - 48
                        logger.debug(f"index: {index}")
                        if index < len(states):
                            png_tuber_state = states[index]
                            png_tuber_state.resize(s_width, s_height)
            screen.fill(background_color)
            png_tuber_state.update()
            try:
                png_tuber_state.draw(screen)
            except TypeError as err:
                tb = traceback.format_exc()
                logger.error(tb)
            pg.display.flip()
            clock.tick(framerate)

        # close pygame
        pg.quit()


def main():
    app = App()


if __name__ == "__main__":
    main()
