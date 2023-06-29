{ description = (
    "Service showing Spotify's currently playing song on an i²c or spi display"
); inputs = {

    # To update »./flake.lock«: $ nix flake update
    nixpkgs = { url = "github:NixOS/nixpkgs/nixos-23.05"; };
    flake-utils = { url = "github:numtide/flake-utils"; };

}; outputs = inputs @ { self, ... }: let
    overlay = final: prev: {
        inherit (import ./default.nix { pkgs = final; }) spotify-oled spotify-oled-interpreter;
    };
    nixosModule = import ./module.nix;
in inputs.flake-utils.lib.eachDefaultSystem (system: let
    pkgs = import inputs.nixpkgs { inherit system; overlays = [ overlay ]; config.allowUnsupportedSystem = true; };
in {
    devShells.default = pkgs.mkShell {
        buildInputs = [ pkgs.spotify-oled pkgs.spotify-oled-interpreter ];
    };
    apps.default = { type = "app"; program = "${pkgs.spotify-oled}/bin/spotify-oled.py"; };
    packages = { inherit (pkgs) spotify-oled spotify-oled-interpreter; default = pkgs.spotify-oled; };
}) // {
    overlays = { spotify-oled = overlay; default = overlay; };
    nixosModules = { spotify-oled = nixosModule; default = nixosModule; };
}; }
