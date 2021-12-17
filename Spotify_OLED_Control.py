#!/usr/bin/env python3

import os
import time
import re
import json

import multiprocessing as mp

import spotipy

from PIL import ImageFont

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled import device as devices

from RPi import GPIO

# Get associated values from config file
import configparser
configParser = configparser.ConfigParser()
configParser.read('config.ini')
config = { key: dict(configParser.items(key)) for key in configParser.sections() }
credentials = config['credentials']
screen = config['screen']
content = config['content']

if credentials['cache_path'] == '':
    cache_path = ".cache-{}".format(credentials['username'])
else:
    cache_path = credentials['cache_path']

# substitute spi(device=0, port=0) below if using that interface
if screen['type'] == 'spi':
    serial = spi(device=int(screen['device_num']), port=int(screen['port_num']))
else:
    serial = i2c(port=int(screen['port_num']), address=int(screen['address'], 0))
device = getattr(devices, screen['device'])(serial) # or `ssd1306`, `ssd1331`, ...
WIDTH   = int(screen['width'])
HEIGHT  = int(screen['height'])

SCROLL_SPEED       = int(content['scroll_speed'])
SCROLL_BACK_SPEED  = int(content['scroll_back_speed'])
SCROLL_REST_TIME   = int(content['scroll_rest_time'])
SONG_FONT_SIZE     = int(content['song_font_size'])
ARTIST_FONT_SIZE   = int(content['artist_font_size'])
SEEK_FONT_SIZE     = int(content['seek_font_size'])


font_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fonts", 'cour.ttf'))

# TODO: What does this do, and is it required / specific to the display/interface?
clk = 17
dt = 18
btn = 27
GPIO.setmode(GPIO.BCM)
GPIO.setup(clk, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(dt, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(btn, GPIO.IN, pull_up_down=GPIO.PUD_UP)

clkLastState = GPIO.input(clk)


global spotify_data

class ScrollDataClass:
    def __init__(self, text_width, string):
        self.x = 0
        self.text_width = text_width
        self.string = string
        self.scrolling = text_width > WIDTH
        self.end = not self.scrolling  # scroll has reached the end of its movement
        self.movingLeft = True  # scrolling direction
        self.restCounter = 0

        # TODO modify scroll speed based on text length

    def calc_if_scroll_ended(self):
        if not self.end:
            if self.movingLeft:
                if self.x < 0 - self.text_width + WIDTH:
                    self.end = True
            else:
                if self.x >= 0:
                    self.end = True


class SeekbarDataClass:

    def __init__(self, current_pos, song_len):
        self.currentPos = current_pos
        self.lastTime = int(time.time())
        self.songLen = song_len
        self.totalTimeString = self.calc_time_string(song_len)
        self.currentPosString = self.calc_time_string(self.currentPos)
        self.x_pos = 0
        self.padding = 35
        self.end = False

    def calc_time_string(self, song_len):
        m, s = divmod(song_len, 60)
        h, m = divmod(m, 60)
        c_song_len = '{:02d}:{:02d}'.format(m, s)
        return c_song_len


class UIThread:
    def __init__(self, spotify_data):
        self.dataAvailable = False
        if spotify_data.track is not None and spotify_data.artists is not None:
            self.track = spotify_data.track
            self.artist = ', '.join(spotify_data.artists)
            self.track_font = ImageFont.truetype(font_path, SONG_FONT_SIZE)
            self.artist_font = ImageFont.truetype(font_path, ARTIST_FONT_SIZE)
            self.dataAvailable = True

        self.seekbar_font = ImageFont.truetype(font_path, SEEK_FONT_SIZE)

    def run(self):  # scroll
        if self.dataAvailable:
            with canvas(device) as draw:
                track_w, self.h = draw.textsize(self.track, font=self.track_font)
                artist_w, self.h = draw.textsize(self.artist, font=self.artist_font)

            track_scroll_info = ScrollDataClass(track_w, self.track)
            artist_scroll_info = ScrollDataClass(artist_w, self.artist)
            scroll_infos = [track_scroll_info, artist_scroll_info]

        seekbar_info = SeekbarDataClass(int(spotify_data.progressMs / 1000), int(spotify_data.durationMs / 1000))

        while True:
            if self.dataAvailable:
                scroll_infos = self.next_scroll_frame(scroll_infos)

            seekbar_info = self.next_seek_frame(seekbar_info, spotify_data.isPlaying)

            with canvas(device) as draw:
                if self.dataAvailable:
                    # track name scroller
                    draw.text((scroll_infos[0].x, 0), track_scroll_info.string, font=self.track_font, fill="white")
                    # artist name scroller
                    draw.text((scroll_infos[1].x, HEIGHT - 40), artist_scroll_info.string, font=self.artist_font, fill="white")

                if not spotify_data.isPlaying:
                    # draw pause symbol
                    draw.rectangle((55, (HEIGHT - 12), 58, HEIGHT), "white", "white", 1)  # Left bar
                    draw.rectangle((67, (HEIGHT - 12), 70, HEIGHT), "white", "white", 1)  # Right bar
                else:
                    if spotify_data.isMuted:
                        # draw muted speaker icon
                        draw.line((55, (HEIGHT -  9), 58, (HEIGHT -  9)), "white", 1)  # -
                        draw.line((55, (HEIGHT -  9), 55, (HEIGHT -  4)), "white", 1)  # |
                        draw.line((55, (HEIGHT -  4), 58, (HEIGHT -  4)), "white", 1)  # -
                        draw.line((58, (HEIGHT -  9), 62, (HEIGHT - 12)), "white", 1)  # /
                        draw.line((62, (HEIGHT - 12), 62,  HEIGHT      ), "white", 1)  # |
                        draw.line((58, (HEIGHT -  4), 62,  HEIGHT      ), "white", 1)  # \
                        draw.line((65, (HEIGHT -  9), 70, (HEIGHT -  4)), "white", 1)  # \
                        draw.line((65, (HEIGHT -  4), 70, (HEIGHT -  9)), "white", 1)  # /
                    else:
                        # draw seek bar outline
                        draw.rectangle((seekbar_info.padding, (HEIGHT - 7), (WIDTH - seekbar_info.padding), (HEIGHT - 4)),
                                       "black", "white", 1)
                        # draw seek bar within
                        draw.rectangle((seekbar_info.padding, (HEIGHT - 6), (seekbar_info.x_pos + 2), (HEIGHT - 5)),
                                       "black", "white", 2)

                # draw current time
                draw.text((0, (HEIGHT - 12)), seekbar_info.currentPosString, font=self.seekbar_font, fill="white")
                # end time
                draw.text((WIDTH - seekbar_info.padding + 5, (HEIGHT - 12)), seekbar_info.totalTimeString,
                          font=self.seekbar_font, fill="white")

    def next_scroll_frame(self, scroll_infos):
        scrolling_count = 0
        for scroll in scroll_infos:
            scroll.calc_if_scroll_ended()
            if scroll.scrolling:
                scrolling_count += 1

        # true if both scroll bars are finished scrolling at the starting position
        all_ended = scroll_infos[0].end and scroll_infos[0].movingLeft == \
                    False and scroll_infos[1].end and scroll_infos[1].movingLeft == False

        for scroll in scroll_infos:
            if scroll.scrolling:
                if scroll.end:  # if end of scrolling movement, on either side
                    if scroll.movingLeft:
                        scroll.end = False
                        scroll.movingLeft = not scroll.movingLeft
                    else:
                        if all_ended or scrolling_count == 1:  # if both scrolls back at beginning or only one scrolling
                            if scroll.restCounter > SCROLL_REST_TIME:
                                scroll.end = False
                                scroll.movingLeft = not scroll.movingLeft
                                scroll.restCounter = 0
                            else:
                                scroll.restCounter += 1
                else:
                    if scroll.movingLeft:
                        scroll.x -= SCROLL_SPEED
                    else:
                        scroll.x += SCROLL_BACK_SPEED
        return scroll_infos

    def next_seek_frame(self, seekbar_info, is_playing):
        diff = time.time() - seekbar_info.lastTime
        seekbar_info.lastTime = time.time()
        if is_playing:
            seekbar_info.currentPos += diff
        percent = seekbar_info.currentPos / seekbar_info.songLen
        seekbar_info.x_pos = seekbar_info.padding + int(percent * (WIDTH - seekbar_info.padding * 2))
        if percent >= 1:
            seekbar_info.end = True
        else:
            seekbar_info.end = False

        seekbar_info.currentPosString = seekbar_info.calc_time_string(int(seekbar_info.currentPos))
        return seekbar_info

    def finish(self):
        self.proc.terminate()


class SpotifyDataClass:
    def __init__(self):

        # track info
        self.track: str = None # ("title"?)
        self.artists: list[str] = None
        self.durationMs: int = None

        # playback state
        self.progressMs = None
        self.shuffleState = None
        self.isPlaying = None  # playing => true ; paused => false
        self.nothingPlaying = True  # a track is playing / no playback ("isStopped"?)
        self.volume = self.get_vol()
        if self.volume == 0: # (isn't this redundant?)
            self.isMuted = True
        else:
            self.isMuted = False

        # login data
        self.username = credentials['username']
        self.scope = 'user-read-playback-state, user-modify-playback-state'
        self.cache_path = cache_path
        self.sp = spotipy.Spotify(
            requests_timeout=10,
            auth_manager=spotipy.SpotifyOAuth(
                client_id=credentials['client_id'],
                client_secret=credentials['client_secret'],
                redirect_uri=credentials['redirect_uri'],
                scope=self.scope,
                cache_path=self.cache_path,
                open_browser=False,
            ),
        )

    def get_playback(self):
        try:
            playback = self.sp.current_playback()
            self.isPlaying = playback['is_playing']
            try:
                if self.isPlaying: # chainging tracks implicitly stats playback
                    self.artists = [ artist['name'] for artist in playback['item']['artists'] ]
                    self.track = strip_artists_from_track(playback['item']['name'], self.artists)
                    self.durationMs = playback['item']['duration_ms']
                    self.nothingPlaying = False

                self.volume = self.get_vol()
                self.progressMs = playback['progress_ms']

                # shuffle doesn't change
                self.shuffleState = playback['shuffle_state']
            except TypeError:
                self.nothingPlaying = True
                print("Type error getting data")

        except:
            # TODO do something if this hits lots
            self.nothingPlaying = True
            self.isPlaying = None
            self.track = None
            self.artists = None
            self.durationMs = None
            self.progressMs = None

    def get_vol(self):
        if self.isPlaying:
            playback = self.sp.current_playback()
            self.volume = playback['device']['volume_percent']
            if self.volume == 0:
                self.isMuted = True
            else:
                self.isMuted = False
            return self.volume

    def __str__(self):
        string = ""
        if self.isMuted:
            string += "MUTED - "
        if self.nothingPlaying:
            string += "Stopped"
        elif self.isPlaying:
            string += "Playing »" + self.track + "« by »" + '«, »'.join(self.artists) + "«"
        else:
            string += "Paused"
        return string


def update_all_UIs(UI, spotify_data):
    print(spotify_data)
    if UI != None:
        UI.finish()
    UI = start_UI_thread(spotify_data)
    return UI


def start_UI_thread(spotify_data):
    # TODO spotify data should not have None fields! where possible cache previous value
    UI_obj = UIThread(spotify_data)
    p = mp.Process(target=UI_obj.run)
    UI_obj.proc = p
    p.start()
    mp.active_children()
    return UI_obj


# basically removes any pair of prentices that contains any of the artist names:
# `strip_artists_from_track('a (x b) c (d x) e (f)', ['a','b','c','d','e','f',])` => 'a c e'
def strip_artists_from_track(track, artists):
    # make sure there are none of the (unprintable) placeholders used already
    track = re.sub(r'[\0-\x1f]', '', track)
    # supstitute artist names with matchable placeholders
    for i in range(min(len(artists), 0x1f)):
        track = track.replace(artists[i], chr(i))
    # remove placeholders in and including prentices
    track = re.sub(r' ?[(][^()\0-\x1f]*[\0-\x1f][^())]*[)]', '', track)
    # put back any leftover artist names
    return re.sub(r'[\0-\x1f]', lambda i: artists[ord(i.group())] if False else '[' + str(ord(i.group()) + 1) + ']', track).strip()


if __name__ == "__main__":
    spotify_data = SpotifyDataClass()
    last_song = ""
    last_song_is_playing = False
    last_song_pos = 0
    ui = None
    spotify_data.get_playback()
    print(spotify_data)
    if spotify_data.isPlaying:
        ui = start_UI_thread(spotify_data)

    while True:
        try:
            last_song = spotify_data.track + spotify_data.artists[0]
        except TypeError:
            last_song = None  # This means that nothing is playing

        if spotify_data.progressMs is not None:
            last_song_pos = int(spotify_data.progressMs / 1000)
        last_song_is_playing = spotify_data.isPlaying
        last_song_is_muted = spotify_data.isMuted
        spotify_data.get_playback()

        if spotify_data.nothingPlaying:
            print("Nothing playing")
            time.sleep(2)
            continue

        ## Update the UI if there was a change (other than the expected progression of time)

        # TODO: what is the polling rate on this? The last test implies it's less than 5s ...

        # if spotify_data.track is None and last_song is not None:  # paused
        if not spotify_data.isPlaying and last_song_is_playing:
            print("Paused")
            ui = update_all_UIs(ui, spotify_data)
            continue

        # if last_song is None and spotify_data.track is not None:  # un-paused
        if spotify_data.isPlaying and not last_song_is_playing:
            print("Un-paused")
            ui = update_all_UIs(ui, spotify_data)
            continue

        if spotify_data.isMuted and not last_song_is_muted:
            print("Muted")
            ui = update_all_UIs(ui, spotify_data)
            continue

        if not spotify_data.isMuted and last_song_is_muted:
            print("Un-muted")
            ui = update_all_UIs(ui, spotify_data)
            continue

        if spotify_data.isPlaying:
            if spotify_data.track + spotify_data.artists[0] != last_song:
                print("Song changed")
                ui = update_all_UIs(ui, spotify_data)
                continue

            if abs(last_song_pos - int(spotify_data.progressMs / 1000)) > 5:
                print("woah! Time skipped")
                ui = update_all_UIs(ui, spotify_data)
                continue
