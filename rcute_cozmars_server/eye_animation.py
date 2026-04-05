import asyncio
import random

from PIL import ImageColor

from . import util
from .roboeyes import (
    ANGRY,
    CURIOUS,
    DEFAULT,
    HAPPY,
    N,
    NE,
    NW,
    RoboEyes,
    S,
    SE,
    SW,
    TIRED,
    W,
    E,
)


class EyeAnimation:
    """Wrapper/controller for RoboEyes animation."""

    _exp_list = ["auto", "happy", "sad", "surprised", "angry", "neutral", "focused", "sleepy"]

    def __init__(self, robot):
        self._robot = robot
        self._exp_before = None
        self._expression = None
        self._ev = None
        self._exp_q = None
        self._color = util.bgr("orange")
        self._auto_expression = "neutral"
        self._auto_next_switch = 0

    @classmethod
    def get_expression_list(cls):
        return list(cls._exp_list)

    @staticmethod
    def _bgr_to_rgb(color):
        return color[2], color[1], color[0]

    @staticmethod
    def _norm_color(color):
        if isinstance(color, str):
            rgb = ImageColor.getrgb(color)
            return rgb[2], rgb[1], rgb[0]
        return tuple(color)

    @staticmethod
    def _ticks_ms():
        import time

        return int(time.monotonic() * 1000)

    async def color(self, color=None):
        if color is None:
            return self._color
        color = self._norm_color(color)
        if color != self._color:
            self._color = color
            await self._set_exp(self._expression or "auto")

    async def expression(self, exp=None):
        if exp is None:
            return (self._expression or "auto").split(".")[0]

        exp, color = exp if isinstance(exp, tuple) else (exp, None)
        if exp not in self._exp_list:
            raise TypeError(f"Unknown expression not in {self._exp_list}")

        if color is not None:
            color = self._norm_color(color)
            if color != self._color:
                self._color = color
        await self._set_exp(exp)

    async def hide(self):
        if self._expression != "hidden":
            if self._expression != "stopped":
                self._exp_before = self._expression
            await self._set_exp("hidden", True)

    async def stop(self):
        if self._expression not in ["stopped", "hidden"]:
            self._exp_before = self._expression
            await self._set_exp("stopped", True)

    async def resume(self):
        if self._expression == "stopped":
            await self._set_exp(self._exp_before or "auto")
            self._exp_before = None

    async def show(self, exp=None):
        await self._set_exp(exp or self._exp_before or "auto")
        self._exp_before = None

    async def _set_exp(self, exp, wait=False):
        if self._expression == exp:
            return
        if self._exp_q:
            if self._exp_q.full():
                self._exp_q.get_nowait()
            self._exp_q.put_nowait(exp)
        else:
            self._expression = exp

        if wait and self._ev:
            await self._ev.wait()
            self._ev.clear()

    def _apply_expression(self, robo, exp):
        robo.fgcolor = self._bgr_to_rgb(self._color)
        robo.bgcolor = (0, 0, 0)
        robo.eyes_width(80, 80)
        robo.eyes_height(80, 80)
        robo.eyes_radius(20, 20)
        robo.eyes_spacing(20)
        robo.horiz_flicker(False)
        robo.vert_flicker(False)
        robo.curious = False

        if exp == "neutral":
            robo.mood = DEFAULT
            robo.set_idle_mode(True, 1, 3)
            robo.set_auto_blinker(True, 1, 4)
        elif exp == "happy":
            robo.mood = HAPPY
            robo.set_idle_mode(True, 1, 2)
            robo.set_auto_blinker(True, 1, 3)
            robo.position = random.choice((N, NE, NW, DEFAULT))
        elif exp == "sad":
            robo.mood = TIRED
            robo.set_idle_mode(True, 2, 2)
            robo.set_auto_blinker(True, 2, 2)
            robo.position = random.choice((S, SE, SW))
        elif exp == "sleepy":
            robo.mood = TIRED
            #robo.eyes_height(28, 28)
            robo.set_idle_mode(True, 3, 2)
            robo.set_auto_blinker(True, 2, 3)
            robo.position = S
        elif exp == "angry":
            robo.mood = ANGRY
            robo.set_idle_mode(True, 1, 2)
            robo.set_auto_blinker(True, 2, 2)
            robo.position = random.choice((E, W, NE, NW))
        elif exp == "focused":
            robo.mood = CURIOUS
            #robo.eyes_height(24, 24)
            #robo.eyes_spacing(6)
            robo.set_idle_mode(True, 1, 1)
            robo.set_auto_blinker(True, 2, 1)
            robo.position = random.choice((E, W, DEFAULT))
        elif exp == "surprised":
            robo.mood = DEFAULT
            #robo.eyes_width(40, 40)
            #robo.eyes_height(42, 42)
            robo.set_idle_mode(True, 1, 2)
            robo.set_auto_blinker(True, 1, 2)
            robo.position = random.choice((N, NE, NW, DEFAULT))
        else:
            robo.mood = DEFAULT
            robo.set_idle_mode(True, 1, 3)
            robo.set_auto_blinker(True, 1, 4)

    def _advance_auto_expression(self):
        now = self._ticks_ms()
        if now < self._auto_next_switch:
            return self._auto_expression
        self._auto_expression = random.choice(self._exp_list[1:])  # exclude "auto"
        self._auto_next_switch = now + random.randint(1200, 4200)
        return self._auto_expression

    async def animate(self, robot, start_exp=None):
        self._ev = asyncio.Event()
        self._exp_q = asyncio.Queue(1)
        self._expression = start_exp or self._expression or "auto"
        self._exp_q.put_nowait(self._expression)

        robo = RoboEyes(
            width=240,
            height=135,
            frame_rate=20,
            bgcolor=(0, 0, 0),
            fgcolor=self._bgr_to_rgb(self._color),
            on_show=lambda r: robot.screen.image(r.fb),
        )

        active_expression = "neutral"

        while True:
            try:
                self._expression = await asyncio.wait_for(self._exp_q.get(), timeout=max(0.01, robo.frameInterval / 1000.0))
            except asyncio.TimeoutError:
                self._expression = self._expression or "auto"

            if self._expression == "hidden":
                robot.screen.fill(0)
                self._ev.set()
                while True:
                    self._expression = await self._exp_q.get()
                    if self._expression != "hidden":
                        break

            if self._expression == "stopped":
                self._ev.set()
                while True:
                    self._expression = await self._exp_q.get()
                    if self._expression != "stopped":
                        break

            if self._expression == "auto":
                active_expression = self._advance_auto_expression()
            else:
                active_expression = self._expression

            self._apply_expression(robo, active_expression)
            robo.update()
