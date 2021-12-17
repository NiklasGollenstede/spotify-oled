from setuptools import setup, find_packages

setup(
    name = 'Spotify-OLED-Control',
    version = '0.0.0',
    url = 'https://github.com/conorhennessy/Spotify-OLED-Control',
    author = 'conorhennessy',
    #author_email = '',
    description = 'Spotify current playback OLED display',
    packages = find_packages(),
    install_requires = [
        'spotipy>=2.12.0',
        'luma.oled>=3.4.0',
        'Pillow>=8.2.0'
    ],
    scripts=['Spotify_OLED_Control.py']
)
