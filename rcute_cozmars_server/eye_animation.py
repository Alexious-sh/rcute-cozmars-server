import asyncio
import random
import time

from PIL import Image, ImageColor, ImageDraw

from . import util


# RoboEyes moods
DEFAULT = 0
TIRED = 1
ANGRY = 2
HAPPY = 3
FROZEN = 4
SCARY = 5
CURIOUS = 6

# RoboEyes predefined positions
N = 1
NE = 2
E = 3
SE = 4
S = 5
SW = 6
W = 7
NW = 8


def _ticks_ms():
    return int(time.monotonic() * 1000)


class RoboEyes:
    """CPython-friendly port of MicroPython RoboEyes using Pillow drawing primitives."""

    def __init__(self, width, height, frame_rate=20, on_show=None, bgcolor=(0, 0, 0), fgcolor=(255, 165, 0)):
        assert on_show is not None, "on_show callback is required"
        self.on_show = on_show
        self.screenWidth = width
        self.screenHeight = height
        self.bgcolor = bgcolor
        self.fgcolor = fgcolor
        self.fb = Image.new("RGB", (width, height), bgcolor)
        self.draw = ImageDraw.Draw(self.fb)

        self.fpsTimer = 0
        self._position = 0
        self._mood = DEFAULT

        self.tired = False
        self.angry = False
        self.happy = False
        self._curious = False
        self._cyclops = False
        self.eyeL_open = False
        self.eyeR_open = False

        self.spaceBetweenDefault = 10

        self.eyeLwidthDefault = 36
        self.eyeLheightDefault = 36
        self.eyeLwidthCurrent = self.eyeLwidthDefault
        self.eyeLheightCurrent = 1
        self.eyeLwidthNext = self.eyeLwidthDefault
        self.eyeLheightNext = self.eyeLheightDefault
        self.eyeLheightOffset = 0
        self.eyeLborderRadiusDefault = 8
        self.eyeLborderRadiusCurrent = self.eyeLborderRadiusDefault
        self.eyeLborderRadiusNext = self.eyeLborderRadiusDefault

        self.eyeRwidthDefault = self.eyeLwidthDefault
        self.eyeRheightDefault = self.eyeLheightDefault
        self.eyeRwidthCurrent = self.eyeRwidthDefault
        self.eyeRheightCurrent = 1
        self.eyeRwidthNext = self.eyeRwidthDefault
        self.eyeRheightNext = self.eyeRheightDefault
        self.eyeRheightOffset = 0
        self.eyeRborderRadiusDefault = 8
        self.eyeRborderRadiusCurrent = self.eyeRborderRadiusDefault
        self.eyeRborderRadiusNext = self.eyeRborderRadiusDefault

        self.eyeLxDefault = int((self.screenWidth - (self.eyeLwidthDefault + self.spaceBetweenDefault + self.eyeRwidthDefault)) / 2)
        self.eyeLyDefault = int((self.screenHeight - self.eyeLheightDefault) / 2)
        self.eyeLx = self.eyeLxDefault
        self.eyeLy = self.eyeLyDefault
        self.eyeLxNext = self.eyeLx
        self.eyeLyNext = self.eyeLy

        self.eyeRxDefault = self.eyeLx + self.eyeLwidthCurrent + self.spaceBetweenDefault
        self.eyeRyDefault = self.eyeLy
        self.eyeRx = self.eyeRxDefault
        self.eyeRy = self.eyeRyDefault
        self.eyeRxNext = self.eyeRx
        self.eyeRyNext = self.eyeRy

        self.eyelidsTiredHeight = 0
        self.eyelidsTiredHeightNext = 0
        self.eyelidsAngryHeight = 0
        self.eyelidsAngryHeightNext = 0
        self.eyelidsHappyBottomOffset = 0
        self.eyelidsHappyBottomOffsetNext = 0

        self.spaceBetweenCurrent = self.spaceBetweenDefault
        self.spaceBetweenNext = self.spaceBetweenDefault

        self.hFlicker = False
        self.hFlickerAlternate = False
        self.hFlickerAmplitude = 2
        self.vFlicker = False
        self.vFlickerAlternate = False
        self.vFlickerAmplitude = 10

        self.autoblinker = False
        self.blinkInterval = 1
        self.blinkIntervalVariation = 4
        self.blinktimer = 0

        self.idle = False
        self.idleInterval = 1
        self.idleIntervalVariation = 3
        self.idleAnimationTimer = 0

        self._confused = False
        self.confusedAnimationTimer = 0
        self.confusedAnimationDuration = 500
        self.confusedToggle = True

        self._laugh = False
        self.laughAnimationTimer = 0
        self.laughAnimationDuration = 500
        self.laughToggle = True

        self.clear_display()
        self.on_show(self)
        self.set_framerate(frame_rate)

    def clear_display(self):
        self.draw.rectangle((0, 0, self.screenWidth, self.screenHeight), fill=self.bgcolor)

    def set_framerate(self, fps):
        self.frameInterval = max(1, 1000 // max(1, fps))

    def update(self):
        now = _ticks_ms()
        if now - self.fpsTimer >= self.frameInterval:
            self.draw_eyes()
            self.fpsTimer = now

    def eyes_width(self, leftEye=None, rightEye=None):
        if leftEye is not None:
            self.eyeLwidthNext = leftEye
            self.eyeLwidthDefault = leftEye
        if rightEye is not None:
            self.eyeRwidthNext = rightEye
            self.eyeRwidthDefault = rightEye

    def eyes_height(self, leftEye=None, rightEye=None):
        if leftEye is not None:
            self.eyeLheightNext = leftEye
            self.eyeLheightDefault = leftEye
        if rightEye is not None:
            self.eyeRheightNext = rightEye
            self.eyeRheightDefault = rightEye

    def eyes_radius(self, leftEye=None, rightEye=None):
        if leftEye is not None:
            self.eyeLborderRadiusNext = leftEye
            self.eyeLborderRadiusDefault = leftEye
        if rightEye is not None:
            self.eyeRborderRadiusNext = rightEye
            self.eyeRborderRadiusDefault = rightEye

    def eyes_spacing(self, space):
        self.spaceBetweenNext = space
        self.spaceBetweenDefault = space

    @property
    def mood(self):
        return self._mood

    @mood.setter
    def mood(self, mood):
        if (self._mood in (SCARY, FROZEN)) and mood not in (SCARY, FROZEN):
            self.horiz_flicker(False)
            self.vert_flicker(False)

        if self._curious and mood != CURIOUS:
            self._curious = False

        if mood == TIRED:
            self.tired, self.angry, self.happy = True, False, False
        elif mood == ANGRY:
            self.tired, self.angry, self.happy = False, True, False
        elif mood == HAPPY:
            self.tired, self.angry, self.happy = False, False, True
        elif mood == FROZEN:
            self.tired, self.angry, self.happy = False, False, False
            self.horiz_flicker(True, 2)
            self.vert_flicker(False)
        elif mood == SCARY:
            self.tired, self.angry, self.happy = True, False, False
            self.horiz_flicker(False)
            self.vert_flicker(True, 2)
        elif mood == CURIOUS:
            self.tired, self.angry, self.happy = False, False, False
            self._curious = True
        else:
            self.tired, self.angry, self.happy = False, False, False
        self._mood = mood

    def set_mood(self, value):
        self.mood = value

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, direction):
        if direction == N:
            self.eyeLxNext = self.get_screen_constraint_X() // 2
            self.eyeLyNext = 0
        elif direction == NE:
            self.eyeLxNext = self.get_screen_constraint_X()
            self.eyeLyNext = 0
        elif direction == E:
            self.eyeLxNext = self.get_screen_constraint_X()
            self.eyeLyNext = self.get_screen_constraint_Y() // 2
        elif direction == SE:
            self.eyeLxNext = self.get_screen_constraint_X()
            self.eyeLyNext = self.get_screen_constraint_Y()
        elif direction == S:
            self.eyeLxNext = self.get_screen_constraint_X() // 2
            self.eyeLyNext = self.get_screen_constraint_Y()
        elif direction == SW:
            self.eyeLxNext = 0
            self.eyeLyNext = self.get_screen_constraint_Y()
        elif direction == W:
            self.eyeLxNext = 0
            self.eyeLyNext = self.get_screen_constraint_Y() // 2
        elif direction == NW:
            self.eyeLxNext = 0
            self.eyeLyNext = 0
        else:
            self.eyeLxNext = self.get_screen_constraint_X() // 2
            self.eyeLyNext = self.get_screen_constraint_Y() // 2
        self._position = direction

    def set_position(self, value):
        self.position = value

    def set_auto_blinker(self, active, interval=None, variation=None):
        self.autoblinker = bool(active)
        if interval is not None:
            self.blinkInterval = interval
        if variation is not None:
            self.blinkIntervalVariation = variation
        if active:
            self.blinktimer = 0

    def set_idle_mode(self, active, interval=None, variation=None):
        self.idle = bool(active)
        if interval is not None:
            self.idleInterval = interval
        if variation is not None:
            self.idleIntervalVariation = variation
        if active:
            self.idleAnimationTimer = 0

    @property
    def curious(self):
        return self._curious

    @curious.setter
    def curious(self, enable):
        self._curious = bool(enable)

    @property
    def cyclops(self):
        return self._cyclops

    @cyclops.setter
    def cyclops(self, enabled):
        self._cyclops = bool(enabled)

    def horiz_flicker(self, enable, amplitude=None):
        self.hFlicker = bool(enable)
        if amplitude is not None:
            self.hFlickerAmplitude = amplitude

    def vert_flicker(self, enable, amplitude=None):
        self.vFlicker = bool(enable)
        if amplitude is not None:
            self.vFlickerAmplitude = amplitude

    def get_screen_constraint_X(self):
        return self.screenWidth - self.eyeLwidthCurrent - self.spaceBetweenCurrent - self.eyeRwidthCurrent

    def get_screen_constraint_Y(self):
        return self.screenHeight - self.eyeLheightDefault

    def close(self, left=None, right=None):
        if left is None and right is None:
            self.eyeLheightNext = 1
            self.eyeRheightNext = 1
            self.eyeL_open = False
            self.eyeR_open = False
            return
        if left is not None:
            self.eyeLheightNext = 1
            self.eyeL_open = False
        if right is not None:
            self.eyeRheightNext = 1
            self.eyeR_open = False

    def open(self, left=None, right=None):
        if left is None and right is None:
            self.eyeL_open = True
            self.eyeR_open = True
            return
        if left is not None:
            self.eyeL_open = True
        if right is not None:
            self.eyeR_open = True

    def blink(self, left=None, right=None):
        self.close(left=left, right=right)
        self.open(left=left, right=right)

    def confuse(self):
        self._confused = True

    def laugh(self):
        self._laugh = True

    def _fill_rrect(self, x, y, w, h, radius, color):
        if w <= 0 or h <= 0:
            return
        x0 = int(x)
        y0 = int(y)
        x1 = int(x + w - 1)
        y1 = int(y + h - 1)
        if x1 < 0 or y1 < 0 or x0 >= self.screenWidth or y0 >= self.screenHeight:
            return
        radius = max(0, min(int(radius), int(min(w, h) // 2)))
        self.draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=color)

    def _fill_triangle(self, x1, y1, x2, y2, x3, y3, color):
        self.draw.polygon(((int(x1), int(y1)), (int(x2), int(y2)), (int(x3), int(y3))), fill=color)

    def draw_eyes(self):
        if self._curious:
            if self.eyeLxNext <= 10:
                self.eyeLheightOffset = 8
            elif self.eyeLxNext >= self.get_screen_constraint_X() - 10 and self._cyclops:
                self.eyeLheightOffset = 8
            else:
                self.eyeLheightOffset = 0
            if self.eyeRxNext >= (self.screenWidth - self.eyeRwidthCurrent - 10):
                self.eyeRheightOffset = 8
            else:
                self.eyeRheightOffset = 0
        else:
            self.eyeLheightOffset = 0
            self.eyeRheightOffset = 0

        self.eyeLheightCurrent = (self.eyeLheightCurrent + self.eyeLheightNext + self.eyeLheightOffset) // 2
        self.eyeLy += (self.eyeLheightDefault - self.eyeLheightCurrent) // 2
        self.eyeLy -= self.eyeLheightOffset // 2

        self.eyeRheightCurrent = (self.eyeRheightCurrent + self.eyeRheightNext + self.eyeRheightOffset) // 2
        self.eyeRy += (self.eyeRheightDefault - self.eyeRheightCurrent) // 2
        self.eyeRy -= self.eyeRheightOffset // 2

        if self.eyeL_open and self.eyeLheightCurrent <= (1 + self.eyeLheightOffset):
            self.eyeLheightNext = self.eyeLheightDefault
        if self.eyeR_open and self.eyeRheightCurrent <= (1 + self.eyeRheightOffset):
            self.eyeRheightNext = self.eyeRheightDefault

        self.eyeLwidthCurrent = (self.eyeLwidthCurrent + self.eyeLwidthNext) // 2
        self.eyeRwidthCurrent = (self.eyeRwidthCurrent + self.eyeRwidthNext) // 2
        self.spaceBetweenCurrent = (self.spaceBetweenCurrent + self.spaceBetweenNext) // 2

        self.eyeLx = (self.eyeLx + self.eyeLxNext) // 2
        self.eyeLy = (self.eyeLy + self.eyeLyNext) // 2

        self.eyeRxNext = self.eyeLxNext + self.eyeLwidthCurrent + self.spaceBetweenCurrent
        self.eyeRyNext = self.eyeLyNext
        self.eyeRx = (self.eyeRx + self.eyeRxNext) // 2
        self.eyeRy = (self.eyeRy + self.eyeRyNext) // 2

        self.eyeLborderRadiusCurrent = (self.eyeLborderRadiusCurrent + self.eyeLborderRadiusNext) // 2
        self.eyeRborderRadiusCurrent = (self.eyeRborderRadiusCurrent + self.eyeRborderRadiusNext) // 2

        now = _ticks_ms()
        if self.autoblinker and now >= self.blinktimer:
            self.blink()
            self.blinktimer = now + (self.blinkInterval * 1000) + (random.randint(0, self.blinkIntervalVariation) * 1000)

        if self._laugh:
            if self.laughToggle:
                self.vert_flicker(True, 5)
                self.laughAnimationTimer = now
                self.laughToggle = False
            elif now - self.laughAnimationTimer >= self.laughAnimationDuration:
                self.vert_flicker(False, 0)
                self.laughToggle = True
                self._laugh = False

        if self._confused:
            if self.confusedToggle:
                self.horiz_flicker(True, 20)
                self.confusedAnimationTimer = now
                self.confusedToggle = False
            elif now - self.confusedAnimationTimer >= self.confusedAnimationDuration:
                self.horiz_flicker(False, 0)
                self.confusedToggle = True
                self._confused = False

        if self.idle and now >= self.idleAnimationTimer:
            self.eyeLxNext = random.randint(0, max(0, self.get_screen_constraint_X()))
            self.eyeLyNext = random.randint(0, max(0, self.get_screen_constraint_Y()))
            self.idleAnimationTimer = now + (self.idleInterval * 1000) + (random.randint(0, self.idleIntervalVariation) * 1000)

        if self.hFlicker:
            if self.hFlickerAlternate:
                self.eyeLx += self.hFlickerAmplitude
                self.eyeRx += self.hFlickerAmplitude
            else:
                self.eyeLx -= self.hFlickerAmplitude
                self.eyeRx -= self.hFlickerAmplitude
            self.hFlickerAlternate = not self.hFlickerAlternate

        if self.vFlicker:
            if self.vFlickerAlternate:
                self.eyeLy += self.vFlickerAmplitude
                self.eyeRy += self.vFlickerAmplitude
            else:
                self.eyeLy -= self.vFlickerAmplitude
                self.eyeRy -= self.vFlickerAmplitude
            self.vFlickerAlternate = not self.vFlickerAlternate

        if self._cyclops:
            self.eyeRwidthCurrent = 0
            self.eyeRheightCurrent = 0
            self.spaceBetweenCurrent = 0

        self.clear_display()

        self._fill_rrect(
            self.eyeLx,
            self.eyeLy,
            self.eyeLwidthCurrent,
            self.eyeLheightCurrent,
            self.eyeLborderRadiusCurrent,
            self.fgcolor,
        )

        if not self._cyclops:
            self._fill_rrect(
                self.eyeRx,
                self.eyeRy,
                self.eyeRwidthCurrent,
                self.eyeRheightCurrent,
                self.eyeRborderRadiusCurrent,
                self.fgcolor,
            )

        if self.tired:
            self.eyelidsTiredHeightNext = self.eyeLheightCurrent // 2
            self.eyelidsAngryHeightNext = 0
        else:
            self.eyelidsTiredHeightNext = 0

        if self.angry:
            self.eyelidsAngryHeightNext = self.eyeLheightCurrent // 2
            self.eyelidsTiredHeightNext = 0
        else:
            self.eyelidsAngryHeightNext = 0

        self.eyelidsHappyBottomOffsetNext = self.eyeLheightCurrent // 2 if self.happy else 0

        self.eyelidsTiredHeight = (self.eyelidsTiredHeight + self.eyelidsTiredHeightNext) // 2
        if not self._cyclops:
            self._fill_triangle(
                self.eyeLx,
                self.eyeLy - 1,
                self.eyeLx + self.eyeLwidthCurrent,
                self.eyeLy - 1,
                self.eyeLx,
                self.eyeLy + self.eyelidsTiredHeight - 1,
                self.bgcolor,
            )
            self._fill_triangle(
                self.eyeRx,
                self.eyeRy - 1,
                self.eyeRx + self.eyeRwidthCurrent,
                self.eyeRy - 1,
                self.eyeRx + self.eyeRwidthCurrent,
                self.eyeRy + self.eyelidsTiredHeight - 1,
                self.bgcolor,
            )
        else:
            half = self.eyeLwidthCurrent // 2
            self._fill_triangle(
                self.eyeLx,
                self.eyeLy - 1,
                self.eyeLx + half,
                self.eyeLy - 1,
                self.eyeLx,
                self.eyeLy + self.eyelidsTiredHeight - 1,
                self.bgcolor,
            )
            self._fill_triangle(
                self.eyeLx + half,
                self.eyeLy - 1,
                self.eyeLx + self.eyeLwidthCurrent,
                self.eyeLy - 1,
                self.eyeLx + self.eyeLwidthCurrent,
                self.eyeLy + self.eyelidsTiredHeight - 1,
                self.bgcolor,
            )

        self.eyelidsAngryHeight = (self.eyelidsAngryHeight + self.eyelidsAngryHeightNext) // 2
        if not self._cyclops:
            self._fill_triangle(
                self.eyeLx,
                self.eyeLy - 1,
                self.eyeLx + self.eyeLwidthCurrent,
                self.eyeLy - 1,
                self.eyeLx + self.eyeLwidthCurrent,
                self.eyeLy + self.eyelidsAngryHeight - 1,
                self.bgcolor,
            )
            self._fill_triangle(
                self.eyeRx,
                self.eyeRy - 1,
                self.eyeRx + self.eyeRwidthCurrent,
                self.eyeRy - 1,
                self.eyeRx,
                self.eyeRy + self.eyelidsAngryHeight - 1,
                self.bgcolor,
            )
        else:
            half = self.eyeLwidthCurrent // 2
            self._fill_triangle(
                self.eyeLx,
                self.eyeLy - 1,
                self.eyeLx + half,
                self.eyeLy - 1,
                self.eyeLx + half,
                self.eyeLy + self.eyelidsAngryHeight - 1,
                self.bgcolor,
            )
            self._fill_triangle(
                self.eyeLx + half,
                self.eyeLy - 1,
                self.eyeLx + self.eyeLwidthCurrent,
                self.eyeLy - 1,
                self.eyeLx + half,
                self.eyeLy + self.eyelidsAngryHeight - 1,
                self.bgcolor,
            )

        self.eyelidsHappyBottomOffset = (self.eyelidsHappyBottomOffset + self.eyelidsHappyBottomOffsetNext) // 2
        self._fill_rrect(
            self.eyeLx - 1,
            (self.eyeLy + self.eyeLheightCurrent) - self.eyelidsHappyBottomOffset + 1,
            self.eyeLwidthCurrent + 2,
            self.eyeLheightDefault,
            self.eyeLborderRadiusCurrent,
            self.bgcolor,
        )
        if not self._cyclops:
            self._fill_rrect(
                self.eyeRx - 1,
                (self.eyeRy + self.eyeRheightCurrent) - self.eyelidsHappyBottomOffset + 1,
                self.eyeRwidthCurrent + 2,
                self.eyeRheightDefault,
                self.eyeRborderRadiusCurrent,
                self.bgcolor,
            )

        self.on_show(self)


class EyeAnimation:
    """Eye animation controller using a CPython port of RoboEyes."""

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

    async def color(self, color=None):
        """Eyes' color in BGR mode."""
        if color is None:
            return self._color
        color = self._norm_color(color)
        if color != self._color:
            self._color = color
            await self._set_exp(self._expression or "auto")

    async def expression(self, exp=None):
        """Set expression. If omitted, returns current expression name."""
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
        robo.eyes_width(36, 36)
        robo.eyes_height(36, 36)
        robo.eyes_radius(8, 8)
        robo.eyes_spacing(10)
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
            robo.eyes_height(28, 28)
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
            robo.eyes_height(24, 24)
            robo.eyes_spacing(6)
            robo.set_idle_mode(True, 1, 1)
            robo.set_auto_blinker(True, 2, 1)
            robo.position = random.choice((E, W, DEFAULT))
        elif exp == "surprised":
            robo.mood = DEFAULT
            robo.eyes_width(40, 40)
            robo.eyes_height(42, 42)
            robo.set_idle_mode(True, 1, 2)
            robo.set_auto_blinker(True, 1, 2)
            robo.position = random.choice((N, NE, NW, DEFAULT))
        else:
            robo.mood = DEFAULT
            robo.set_idle_mode(True, 1, 3)
            robo.set_auto_blinker(True, 1, 4)

    def _advance_auto_expression(self):
        now = _ticks_ms()
        if now < self._auto_next_switch:
            return self._auto_expression
        self._auto_expression = random.choice(["neutral", "happy", "sad", "surprised", "angry", "focused", "sleepy"])
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
            await asyncio.sleep(0.01)
