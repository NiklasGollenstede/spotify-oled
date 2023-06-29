{ pkgs ? import <nixpkgs> { }, lib ? pkgs.lib, ... }: let

    pip3 = pkgs.python3Packages;
    mkPackage = name: version: sha256: deps: extra: pip3.buildPythonPackage ({
        pname = name; version = version; propagatedBuildInputs = deps;
        src = pip3.fetchPypi { pname = name; version = version; sha256 = sha256; };
    } // extra);

    smbus2    = mkPackage "smbus2"    "0.4.1" "YnbrWZt2xOdDcvJYLSKC8DtDmPDaFryZZgjk8hVXyps=" [ ] { };
    rpi-gpio  = mkPackage "RPi.GPIO"  "0.7.1" "zWHEsDw3tiu6SlrP6phidJwzxhjgKV5+kKpHE/s3O3A=" [ ] { doCheck = false; };
    luma-core = mkPackage "luma.core" "2.4.0" "z1/fNWPV7Fbi95LzovQyq66sUXoLBaEKdXpMWia7Ll0=" (with pip3; [ pillow smbus2 pyftdi cbor2 deprecated rpi-gpio spidev ]) { doCheck = false; };
    luma-oled = mkPackage "luma.oled" "3.12.0" "r5fXn6NIHSxIt7zPtt40khn22BT9yaPdB1x7LHEgZFA=" (with pip3; [ luma-core pillow smbus2 pyftdi cbor2 deprecated rpi-gpio spidev ]) { doCheck = false; };

    python3 = pkgs.python3.withPackages (pip3: with pip3; [ pillow spotipy luma-oled luma-core smbus2 rpi-gpio ]);

    spotify-oled = pip3.buildPythonApplication rec {
        pname = "spotify-oled"; version = "1.0.1";
        src = pkgs.nix-gitignore.gitignoreSourcePure [ ./.gitignore ] ./.;
        propagatedBuildInputs = with pip3; [ spotipy luma-oled pillow luma-core ];
        doCheck = false;
        postPatch = ''
            substituteInPlace spotify-oled.py \
                --replace "'./fonts/'" "'$out/share/fonts/'"
        '';
        postInstall = ''
            mkdir -p $out/share
            cp -aT ./fonts $out/share/fonts
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
