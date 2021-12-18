{ config, lib, pkgs, ... }: {

    options.my = { services.spotify-oled = {
        enable = lib.mkOption { default = false; };
        client_id = lib.mkOption { default = ""; }; # required
        client_secret = lib.mkOption { default = ""; }; # required
        auth_cache_path = lib.mkOption { default = "/var/local/spotify-oled.auth"; };
        dev = lib.mkOption { default = false; };
        extraConfig = lib.mkOption { default = { }; type = lib.types.attrsOf (lib.types.attrsOf (lib.types.either lib.types.int lib.types.str)); };
        extraArgs = lib.mkOption { default = [ ]; type = lib.types.listOf lib.types.str; };
        package = lib.mkOption { default = pkgs.spotify-oled or (import ./default.nix { inherit pkgs lib; }).spotify-oled; type = lib.types.package; };
    }; };

    config = let
        cfg = config.my.services.spotify-oled;
        configFile = pkgs.writeText "spotify-oled.ini" (lib.generators.toINI { } (cfg.extraConfig // {
            credentials = {
                inherit (cfg) client_id client_secret; cache_path = cfg.auth_cache_path;
            } // (if cfg.extraConfig?credentials then cfg.extraConfig.credentials else { });
        }));
        spotify-oled = cfg.package;
    in lib.mkIf cfg.enable {

        environment.systemPackages = (lib.optionals cfg.dev [ spotify-oled ]);

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
