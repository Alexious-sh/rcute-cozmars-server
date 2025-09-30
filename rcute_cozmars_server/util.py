from os import path
from PIL import Image, ImageFont, ImageDraw, ImageColor
import gettext, locale, re
import asyncio
from concurrent import futures
import functools
import weakref

PKG = path.dirname(__file__)
STATIC = path.join(PKG, 'static')

def static(file_name):
    return path.join(STATIC, file_name)

def pkg(file_name):
    return path.join(PKG, file_name)

try:
    loc = gettext.translation('base', localedir=path.join(PKG, "locales"), languages=[locale.getdefaultlocale()[0]])
    loc.install()
    _ = loc.gettext
    _gettext = loc.gettext
except Exception as e:
    _ = gettext.gettext
    _gettext = gettext.gettext

def replace_gettext(match):
    match = match.group(2)
    return _gettext(match)

def parsed_template(name, **kwargs):
    with open(static("{}.html".format(name))) as file:
        content = file.read()
        content = re.sub(r'(\{_\("(.*?)"\)\})', replace_gettext, content)
        content = content.format(**kwargs)
        return content

CONF = '/home/pi/.cozmars/conf.json'
ENV = '/home/pi/.cozmars/env.json'

import socket
IP = socket.gethostbyname(f'{socket.gethostname()}.local')
HOSTNAME = socket.gethostname()

import uuid
MAC = hex(uuid.getnode())[2:]
SERIAL = MAC[-4:]
MAC = ':'.join([MAC[i:i+2] for i in range(0,12,2)])

def poweroff_screen():
    return Image.open(static('poweroff.png'))

def reboot_screen():
    return Image.open(static('reboot.png'))

def splash_screen():
    splash = static('splash.png')
    if not path.isfile(splash):
        font_color = '#00ffff'
        font_file = static('DejaVuSans.ttf')
        bfont = ImageFont.truetype(font_file, 30)
        sfont = ImageFont.truetype(font_file, 25)

        image = Image.new("RGB", (240,135))
        draw = ImageDraw.Draw(image)
        draw.text((55,27), 'Cozmars', fill=font_color, font=bfont)
        draw.text((85,72), SERIAL, fill=font_color, font=sfont)

        image.save(splash)

    return Image.open(splash)

def beep(server):
    with open(static('sine_800hz_16k_i8.raw'), 'rb') as f:
        d = f.read()
    q = asyncio.Queue()
    for _ in range(5):
        q.put_nowait(d)
    q.put_nowait(StopAsyncIteration())
    return server.speaker(16000, 'int8', 1600, request_stream=q)

# Following are copied from rcute-cozmars and needed for eye_animation

def bgr(color):
    if isinstance(color, str):
        return ImageColor.getrgb(color)[::-1]
    else:
        return color

class Component:
    def __init__(self, robot):
        self._robot = weakref.proxy(robot)

    @property
    def _mode(self):
        return self._robot._mode

    @property
    def _lo(self):
        return self._robot._lo

    @property
    def _rpc(self):
        return self._robot._rpc

    def _in_event_loop(self):
        return self._robot._in_event_loop()

def mode(force_sync=True, property_type=None):
    def func_deco(func):

        @functools.wraps(func)
        def new_func(*args, **kwargs):
            if not asyncio.iscoroutinefunction(func):
                raise ImportError('Cannot decorate connection.mode on non-coroutine function')

            self = args[0]
            if self._in_event_loop():
                return functools.partial(func, self) if property_type else func(*args, **kwargs)

            fut = asyncio.run_coroutine_threadsafe(func(*args, **kwargs), self._lo)

            if force_sync or property_type or self._mode == 'sync':
                try:
                    return fut.result(kwargs.pop('timeout', None))
                except futures.TimeoutError:
                    return None
            else: # mode == 'async'
                return fut

        if property_type == 'getter':
            return property(new_func)
        elif property_type == 'setter':
            return property(new_func).setter(new_func)
        else:
            return new_func

    return func_deco
