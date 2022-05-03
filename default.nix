{ pkgs ? import <nixpkgs> { }, lib ? pkgs.lib, ... }: let

    pip3 = pkgs.python3Packages;
    mkPackage = name: version: sha256: deps: extra: pip3.buildPythonPackage ({
        pname = name; version = version; propagatedBuildInputs = deps;
        src = pip3.fetchPypi { pname = name; version = version; sha256 = sha256; };
    } // extra);

    smbus2    = mkPackage "smbus2"    "0.4.1" "YnbrWZt2xOdDcvJYLSKC8DtDmPDaFryZZgjk8hVXyps=" [ ] { };
    rpi-gpio  = mkPackage "RPi.GPIO"  "0.7.0" "dCS8bCBUZnZPMPZmwYGHoIJAd9ryCylcQvCK6iy4fT8=" [ ] { doCheck = false; };
    luma-core = mkPackage "luma.core" "2.3.1" "8pP1//iUbupirzpdXX2lXDfStkqsbJyQGAo4Xan30AM=" (with pip3; [ pillow smbus2 pyftdi cbor2 deprecated rpi-gpio spidev ]) { doCheck = false; };
    luma-oled = mkPackage "luma.oled" "3.8.1" "qbRF7MaG6UE92sZVVE2iHYAbvGuUYSc2z1koPmuSvLs=" (with pip3; [ luma-core pillow smbus2 pyftdi cbor2 deprecated rpi-gpio spidev ]) { doCheck = false; };

    python3 = pkgs.python3.withPackages (pip3: with pip3; [ pillow spotipy luma-oled luma-core smbus2 rpi-gpio ]);

    spotify-oled = pip3.buildPythonApplication rec {
        pname = "spotify-oled"; version = "1.0.0";
        src = pkgs.nix-gitignore.gitignoreSourcePure [ ./.gitignore ] ./.;
        propagatedBuildInputs = with pip3; [ spotipy luma-oled pillow luma-core ];
        doCheck = false;
        postPatch = ''
            # pretend that we're running in the source directory, to be able to find assets
            substituteInPlace spotify-oled.py \
                --replace "__file__" "'$src/spotify-oled.py'"
        '';
        meta = {
            homepage = "https://github.com/NiklasGollenstede/spotify-oled";
            description = "Service showing Spotify's currently playing song on an i²c or spi display";
            license = lib.licenses.gpl3;
        };
    };
in {
    spotify-oled = spotify-oled;
    spotify-oled-interpreter = python3;
}
