{
  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.05";
  inputs.poetry2nix = {
    url = "github:nix-community/poetry2nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        inherit (poetry2nix.legacyPackages.${system}) mkPoetryApplication;
        pkgs = nixpkgs.legacyPackages.${system};
        cli = mkPoetryApplication {
          projectDir = ./cli;
          preferWheels = true;
          python = pkgs.python311;
          checkGroups = [ ];
          meta.mainProgram = "trak";
        };
      in
      {
        packages = {
          default = cli;
        };
      }
    );
}
