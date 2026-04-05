import random
import time

from PIL import Image, ImageDraw

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
