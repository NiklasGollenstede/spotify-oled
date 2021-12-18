{ description = (
    "Service showing Spotify's currently playing song on an i²c or spi display"
); inputs = {

    # To update »./flake.lock«: $ nix flake update
    nixpkgs = { url = "github:NixOS/nixpkgs/nixos-21.11"; };
    flake-utils = { url = "github:numtide/flake-utils/master"; };

}; outputs = inputs @ { self, ... }: let
    overlay = pkgs: prev: {
        inherit (import ./default.nix { inherit pkgs; }) spotify-oled spotify-oled-interpreter;
    };
    nixosModule = import ./module.nix;
in inputs.flake-utils.lib.eachDefaultSystem (system: let
    pkgs = import inputs.nixpkgs { inherit system; overlays = [ overlay ]; };

    devShell = pkgs.mkShell {
        buildInputs = with pkgs; [ spotify-oled spotify-oled-interpreter ];
    };
    defaultApp = { type = "app"; program = "${pkgs.spotify-oled}/bin/spotify-oled.py"; };
in {
    inherit devShell defaultApp;
    defaultPackage = pkgs.spotify-oled; packages = { inherit (pkgs) spotify-oled spotify-oled-interpreter; };
}) // {
    inherit overlay nixosModule; overlays = [ overlay ]; nixosModules = [ nixosModule ];
}; }
