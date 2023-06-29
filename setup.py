from setuptools import setup

setup(
    name = 'Spotify-OLED',
    version = '1.0.0',
    url = '/spotify-oled',
    author = 'Niklas Gollenstede',
    author_email = 'n.gollenstede@web.de',
    license = 'GPL-3.0',
    description = "Service showing Spotify's currently playing song on an i²c or spi display",
    packages = '.',
    #package_data = {'':[ 'fonts/*.*', ],}, include_package_data = True, # (this doesn't work ...)
    install_requires = [
        'spotipy>=2.23.0',
        'luma.oled>=3.12.0',
        'Pillow>=9.4.0'
    ],
    scripts = [ 'spotify-oled.py' ],
)
