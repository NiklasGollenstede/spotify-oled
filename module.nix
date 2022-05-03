{ config, lib, pkgs, ... }: {

    options = { services.spotify-oled = {
        enable = lib.mkEnableOption "the Spotify-OLED service";
        client_id = lib.mkOption { description = ''
            The id of your personal Spotify "app" created at <https://developer.spotify.com/dashboard/applications>.
            Must be provided.
        ''; default = ""; };
        client_secret = lib.mkOption { description = ''
            The "secret" to the personal Spotify app's id.
            Since using the app requires signing in with the account that created it, this does not actually need to be secret at all.
            Must be provided.
        ''; default = ""; };
        auth_cache_path = lib.mkOption { description = ''
            File path to a persistent location where the Spotify login authentication will be stored. Instructions on creating and populating this file will be printed during NixOS activation if the file doesn't exist.
        ''; default = "/var/local/spotify-oled.auth"; };
        extraConfig = lib.mkOption { description = ''
            Additional config file content to be serialized and provided as »--config« to the service.
            Needs to set at least »screen.type« and »screen.device«; see the example.
        ''; example = {
            screen = { type = "i2c"; address = "0x3C"; device = "sh1106"; };
        }; default = { }; type = lib.types.attrsOf (lib.types.attrsOf (lib.types.either lib.types.int lib.types.str)); };
        extraArgs = lib.mkOption { description = ''
            Additional CLI arguments provided to the service.
            Should't need any.
        ''; default = [ ]; type = lib.types.listOf lib.types.str; };
        package = lib.mkOption { description = ''
            The »spotify-oled« package to use. Defaults to »pkgs.spotify-oled« or if missing the package that this config module came with.
        ''; default = pkgs.spotify-oled or (import ./default.nix { inherit pkgs lib; }).spotify-oled; type = lib.types.package; };
    }; };

    config = let
        cfg = config.services.spotify-oled;
        configFile = pkgs.writeText "spotify-oled.ini" (lib.generators.toINI { } (cfg.extraConfig // {
            credentials = {
                inherit (cfg) client_id client_secret; cache_path = cfg.auth_cache_path;
            } // (cfg.extraConfig.credentials or { });
        }));
        spotify-oled = cfg.package;
    in lib.mkIf cfg.enable {

        systemd.services.spotify-oled = {
            serviceConfig.ExecStart = "${spotify-oled}/bin/spotify-oled.py --config=${configFile} ${lib.concatStringsSep " " (map lib.escapeShellArgs cfg.extraArgs)}";
            wantedBy = [ "multi-user.target" ]; wants = [ "network-online.target" ]; after = [ "network-online.target" ];
            serviceConfig.Restart = "always"; serviceConfig.RestartSec = 10; unitConfig.StartLimitIntervalSec = 0;
            serviceConfig.DynamicUser = "yes"; serviceConfig.Group = "i2c"; serviceConfig.ReadWritePaths = cfg.auth_cache_path;
        };

        system.activationScripts = { "ensure spotify-oled login" = ''
            if [ ! -e ${lib.escapeShellArgs [ cfg.auth_cache_path ]} ] ; then
                echo ${lib.escapeShellArgs [ "!! spotify-oled's authentication cache is missing. Non-interactive authentication will fail." ]}
                echo ${lib.escapeShellArgs [ "Run »${spotify-oled}/bin/spotify-oled.py --config=${configFile} --auth && chown :i2c ${cfg.auth_cache_path} && chmod 660 ${cfg.auth_cache_path}« to prepare authentication." ]}
                false # emphasize that there is a problem
            fi
        ''; };

    };

}
