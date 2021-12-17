# Spotify-OLED

Spotify now playing on an OLED screen, with a volume dial
![A preview of a song now playing on an OLED screen attached to a RaspberryPi Zero](./resources/Serving_Suggestion.jpg)
![A demo of the volume dial in action, showing Spotify with volume slider on display](./resources/Volume_Demo.gif)

Added controls to skip or go to previous track will be added in an upcoming version.


## Getting Started

### Parts List

1. Raspberry Pi (or similar) with an internet connection
2. I2C or SPI OLED display


### Prerequisites

All Spotify API requests are made through Spotipy, a lightweight Python library for the Spotify Web API, where all methods in this library require user authorisation.

So, you will need to register yourself and create an app on the Spotify [My Dashboard](https://developer.spotify.com/dashboard/applications) to get the credentials necessary to make calls (a *client id* and *client secret*).
Log into this dashboard with your Spotify account and note the credentials shown.


#### Required Packages

- python3 `sudo apt-get install python3`
- pip3 `sudo apt-get install python3-pip`
- libopenjp2-7 `sudo apt-get install libopenjp2-7-dev` (What is this needed for?)


### Setup

1. Connect OLED & configure rpi settings to enable it. External guide for this [here](http://codelectron.com/setup-oled-display-raspberry-pi-python/).
2. Use pip3 to install the following Python libraries
	- [Pillow](https://github.com/python-pillow/Pillow) `pip3 install pillow`
	- [luma.oled](https://github.com/rm-hull/luma.oled) `pip3 install luma-oled`
	- [Spotipy](https://spotipy.readthedocs.io/en/2.12.0/) `pip3 install git+https://github.com/plamere/spotipy.git --upgrade` (This is available in the pip3 repo too)
3. Copy `./resources/config.example.ini` and modify with your app credentials from the Spotify developer dashboard.
   Either copy to `./config.ini` to run locally, or for a system install, copy to `/etc/spotify-old.ini` and link with `ln -sT /etc/spotify-old.ini config.ini`.
4. Copy `./resources/spotify-oled.service` from the repo to `/etc/systemd/system/` and run `sudo systemctl enable spotify-oled.service` (You can also replace `enable` with `start` or `status` for manual starting/stopping of the service).
> Note: Without further steps, this runs user owned code as root, which is quite insecure. More on that to come ...


## Credit

Big Credit to Alex, my housemate, for getting the ball rolling for this project, creating the services file and collab'ing on this project.
* **Alex Hockly** - [@alhockly](https://github.com/alhockly)
