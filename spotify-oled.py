#!/usr/bin/env python3

import argparse ; import configparser
import os ; import time
import re ; import json
from threading import Thread

from PIL.ImageDraw import ImageDraw
from PIL import Image, ImageFont
from luma.core.device import dummy

import spotipy

from luma.core.interface.serial import i2c, spi
from luma.core.render import canvas as Canvas
from luma.oled import device as devices


def _():
    try:
        # TODO: What does this do, and (when) is it required / specific to the display/interface?
        from RPi import GPIO
        clk = 17 ; dt = 18 ; btn = 27
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(clk, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(dt, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(btn, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.input(clk)
    except Exception as error:
        print("Applying GPIO settings failed, but that may be fine: " + str(error.args[0]))
_() ; del _


class AuthConfig:
    def __init__(self, credentials: 'dict[str, str]'):
        self.client_id = credentials['client_id']
        self.client_secret = credentials['client_secret']
        self.redirect_uri = credentials.get('redirect_uri', 'https://no-domain.invalid/')
        self.cache_path = credentials['cache_path'] if credentials.get('cache_path', None) else '.cache-{}'.format(credentials['username'])

class ContentConfig:
    def __init__(self, content: 'dict[str, str]'):
        self.scroll_speed       = int(content.get('scroll_speed',        3))
        self.scroll_back_speed  = int(content.get('scroll_back_speed',   6))
        self.scroll_rest_time   = int(content.get('scroll_rest_time',   15))
        self.song_font_size     = int(content.get('song_font_size',     22))
        self.artist_font_size   = int(content.get('artist_font_size',   18))
        self.seek_font_size     = int(content.get('seek_font_size',     10))
        self.min_frame_time     = int(content.get('min_frame_time',    200))
        self.data_poll_sleep    = int(content.get('data_poll_sleep',  2000))

        font_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fonts", 'cour.ttf'))
        self.title_font = ImageFont.truetype(font_path, self.song_font_size)
        self.content_font = ImageFont.truetype(font_path, self.artist_font_size)
        self.seekbar_font = ImageFont.truetype(font_path, self.seek_font_size)


# Playback state (passive data structure)
class PlaybackInfo:
    def __init__(self):

        # track info
        self.track: str = '' # track title
        self.artists: list[str] = [ ] # list of track's artist names
        self.duration: int = 0 # track duration in ms
        self.started: int = 0 # if not `paused`, wall clock time in ms at which the track would have stared at normal speed to reach its current playback position now (which will not change over time without an actual playback change)
        self.progress: int = 0 # if `paused`, playback position when this info was captured

        # playback state
        self.shuffling: bool = False
        self.paused: bool = False # true iff playback is active but paused (otherwise it's either outputting audio, stalled, or there is no playback)
        self.volume: int = 0 # volume in percent

    def __eq__(self, other):
        if not isinstance(other, PlaybackInfo): return NotImplemented

        # cheap comparisons first
        if self.duration != other.duration or self.paused != other.paused or self.volume != other.volume or self.shuffling != other.shuffling or self.progress != other.progress: return False

        # consider `.started` only to an accuracy of +-150ms
        if self.started < other.started - 150 or self.started > other.started + 150: return False

        # expensive string/list comp. last
        return self.track == other.track and self.artists == other.artists

    def __str__(self):
        return ("MUTED - " if self.volume == 0 else '') + ("Paused " if self.paused else "Playing ") + ("»" + self.track + "« by »" + '«, »'.join(self.artists) + "« ") + ("at " + str(self.progress) if self.paused else "since " + str(self.started))


class PlaybackError:
    def __init__(self, title: str, message: str):
        self.title = title ; self.message = message
    def __str__(self):
        return "PlaybackError {}: {}".format(self.title, self.message)
    def __eq__(self, other):
        if not isinstance(other, PlaybackError): return NotImplemented
        return self.title == other.title and self.message == other.message


class ScrollingText:
    def __init__(self, text: str, start: int, font: ImageFont.FreeTypeFont):
        self.text = text ; self.start = start ; self.now = 0 ; self.font = font
        self.width, _ = dummy_screen.textsize(text, font=font)

    def update(self, now: int):
        self.now = now

    def draw(self, draw: ImageDraw, top: int):
        offset = 0 # TODO: actually make this scroll again
        draw.text((-offset, top), self.text, font=self.font, fill="white")

dummy_screen = ImageDraw(Image.new('1', (1, 1))) # screen type shouldn't matter here


class ProgressBar:

    def __init__(self, cfg: ContentConfig, pb: PlaybackInfo):
        self.cfg = cfg ; self.pb = pb ; self.now = 0
        self.duration = format_mm_ss(pb.duration)
        self.height = cfg.seek_font_size + 2
        self.padding = int(cfg.seek_font_size * 3.3) + 2

    def update(self, now: int):
        self.now = now

    def draw(self, draw: ImageDraw, width: int, top: int):

        #draw.rectangle(((0), (top), (width - 1), (top + self.height - 1)), "black", "white", 1) # outline

        progress = self.pb.progress if self.pb.paused else self.now - self.pb.started
        if progress > self.pb.duration: progress = self.pb.duration

        if self.pb.paused:
            draw_paused(draw, self.height, width / 2, top)
        elif self.pb.volume == 0:
            draw_muted(draw, width / 2, top)
        else: # progress bar
            draw.rectangle(((self.padding + 0), (top + 3), (width - self.padding), (top + self.height - 4)), "black", "white", 1) # outline
            length = width - 2 * (self.padding + 1)
            fill = round(progress / self.pb.duration * length)
            draw.rectangle(((self.padding + 1), (top + 3), (self.padding + 1 + fill), (top + self.height - 4)), "white", "white", 1)

        # (here?) text with a `1` in it is rendered one pixel too high ...
        txt = format_mm_ss(progress) ; draw.text((0, top + (1 if '1' in txt else 0)), txt, font=self.cfg.seekbar_font, fill="white")
        draw.text((width - self.padding + 5, top + (1 if '1' in self.duration else 0)), self.duration, font=self.cfg.seekbar_font, fill="white")


def format_mm_ss(ms: int):
    mm, ss = divmod(round(ms / 1000), 60)
    hh, mm = divmod(mm, 60)
    return '{:02d}:{:02d}'.format(mm, ss)

# Draws a pause icon.
def draw_paused(draw: ImageDraw, height: int, center: int, top: int):
    stroke = int(height / 4)
    draw.rectangle((center - 2*stroke, top, center - 1*stroke, top + height), "white", "white", 1) # left bar
    draw.rectangle((center + 1*stroke, top, center + 2*stroke, top + height), "white", "white", 1) # right bar

# Draws a muted speaker icon (currently fixed to 12 pixels high, which assumes SEEK_FONT_SIZE == 10).
def draw_muted(draw: ImageDraw, center: int, top: int):
    draw.line((center - 9, top +  3, center - 8, top +  3), "white", 1)  # -
    draw.line((center - 9, top +  3, center - 9, top +  8), "white", 1)  # |
    draw.line((center - 9, top +  8, center - 8, top +  8), "white", 1)  # -
    draw.line((center - 8, top +  3, center - 2, top +  0), "white", 1)  # /
    draw.line((center - 2, top +  0, center - 2, top + 11), "white", 1)  # |
    draw.line((center - 8, top +  8, center - 2, top + 11), "white", 1)  # \
    draw.line((center + 1, top +  3, center + 6, top +  8), "white", 1)  # \
    draw.line((center + 1, top +  8, center + 6, top +  3), "white", 1)  # /


class MainUI:
    def __init__(self, device: devices.device, cfg: ContentConfig):
        self.device = device ; self.cfg = cfg
        self.set(None, None)
        self.thread: 'Thread|None' = None ; self.error: 'Exception|None' = None

    def set(self, pb: PlaybackInfo, error: PlaybackError):
        title = error.title if error else pb.track if pb else ''
        content = error.message if error else ', '.join(pb.artists) if pb else ''
        now = round(time.time() * 1000)
        if not hasattr(self, 'title') or self.title.text != title:
            self.title = ScrollingText(title, now, self.cfg.title_font)
        if not hasattr(self, 'content') or self.content.text != content:
            self.content = ScrollingText(content, now, self.cfg.content_font)
        #print(self.title.text, '|', self.content.text)
        self.seekbar = ProgressBar(self.cfg, pb) if pb else None

    def run(self):
        try:
            while self.thread != None:

                now = round(time.time() * 1000)
                self.title.update(now)
                self.content.update(now)
                if self.seekbar: self.seekbar.update(now)

                with Canvas(self.device) as draw: self.draw(draw)

                then = now ; now = round(time.time() * 1000)
                time.sleep((self.cfg.min_frame_time - (now - then)) / 1000)

        except Exception as error:
            self.error = error

    def draw(self, draw: ImageDraw):
        self.title.draw(draw, 0)
        self.content.draw(draw, self.device.height - 40)
        if self.seekbar: self.seekbar.draw(draw, self.device.width, self.device.height - self.seekbar.height)

    def __enter__(self): self.start() ; return self
    def start(self):
        self.thread = Thread(target=self.run) ; self.thread.start()

    def __exit__(self, type, error, trace): self.finish() ; self.test() # (is it ok to just ignore the errors?)
    def finish(self):
        thread = self.thread ; self.thread = None ; thread.join()

    def test(self):
        if self.error: error = self.error ; self.error = None ; raise error


class SpotifyDataProvider:
    def __init__(self, auth: AuthConfig):
        self.sp = spotipy.Spotify(
            requests_timeout=10,
            auth_manager=spotipy.SpotifyOAuth(
                client_id=auth.client_id, client_secret=auth.client_secret,
                redirect_uri=auth.redirect_uri, open_browser=False,
                cache_path=auth.cache_path, # could/should use `cache_handler` instead
                scope='user-read-playback-state, user-modify-playback-state',
            ),
        )

    def poll(self):
        playback = self.sp.current_playback()
        if playback == None: return None
        pb = PlaybackInfo()
        pb.artists = [ artist['name'] for artist in playback['item']['artists'] ]
        pb.track = strip_artists_from_track(playback['item']['name'], pb.artists)
        pb.duration = playback['item']['duration_ms']
        if playback['is_playing']:
            pb.started = round(time.time() * 1000) - playback['progress_ms']
        else:
            pb.progress = playback['progress_ms']
        pb.shuffling = playback['shuffle_state']
        pb.paused = not playback['is_playing']
        pb.volume = playback['device']['volume_percent']
        return pb

    def poll_safe(self) -> 'tuple[PlaybackInfo, None] | tuple[None, PlaybackError]':
        try:
            pb = self.poll()
            if pb != None: return (pb, None)
            return (None, PlaybackError("Stopped", ""))
        except EOFError: # tries to ask for user input without stdin
            return (None, PlaybackError("No Auth", "Interactive login required"))
        except Exception as raw:
            try: message = str(raw.args[0])
            except: message = '<no description>'
            return (None, PlaybackError("Unhandled Exception", message))

def strip_artists_from_track(track: str, artists: 'list[str]'):
    """
    Cleans up a track's title by removing any pair of prentices that contains any of the artist names:
    `strip_artists_from_track('a (x b) c (d x) e (f)', ['a','b','c','d','e','f',])` => 'a c e'
    """
    # make sure there are none of the (unprintable) placeholders used already
    track = re.sub(r'[\0-\x1f]', '', track)
    # supstitute artist names with matchable placeholders
    for i in range(min(len(artists), 0x1f)):
        track = track.replace(artists[i], chr(i))
    # remove placeholders in and including prentices
    track = re.sub(r' ?[(][^()\0-\x1f]*[\0-\x1f][^())]*[)]', '', track)
    # put back any leftover artist names
    return re.sub(r'[\0-\x1f]', lambda i: artists[ord(i.group())] if False else '[' + str(ord(i.group()) + 1) + ']', track).strip()


def main():

    parser = argparse.ArgumentParser(description="Service that displays the authenticated user's current Spotify playback on an i2c/spi OLED display.", allow_abbrev=False)
    parser.add_argument('--config', type=str, help="path to config file, defaults to ./config.ini", default='./config.ini')
    parser.add_argument('--auth', action='store_true', help="do user authentication (which is interactive if not already cached), then exit instead of continuing to drive the display")
    args = parser.parse_args()

    configParser = configparser.ConfigParser() ; configParser.read(args.config)
    config = { key: dict(configParser.items(key)) for key in configParser.sections() }

    if args.auth:
        cfg = AuthConfig(config['credentials'])
        print("Ensuring authentication (cache path: {}):".format(cfg.cache_path))
        SpotifyDataProvider(cfg).poll()
        print("Authentication successfull")
        return

    screen_cfg = config['screen']
    if screen_cfg['type'] == 'spi':
        serial = spi(device=int(screen_cfg.get('device_num', 0)), port=int(screen_cfg.get('port_num', 1)))
    else:
        serial = i2c(port=int(screen_cfg.get('port_num', 1)), address=int(screen_cfg.get('address', 0x3C), 0))
    device: devices.device = getattr(devices, screen_cfg['device'])(serial)

    cfg = ContentConfig(config.get('content', { }))

    spotify = SpotifyDataProvider(AuthConfig(config['credentials']))
    prev_data: 'PlaybackInfo|None' = None
    prev_error: 'PlaybackError|None' = None

    with MainUI(device, cfg) as ui:
        while True:
            next_data, next_error = spotify.poll_safe()

            if next_data != prev_data or next_error != prev_error:
                print('\n' + str(next_data if next_data != None else next_error))
                ui.set(next_data, next_error)
                prev_data = next_data ; prev_error = next_error

            time.sleep(cfg.data_poll_sleep / 1000)
            ui.test()

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("Exiting")
