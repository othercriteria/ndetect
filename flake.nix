{
  description = "Development environment for ndetect (near-duplicate detection tool)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config = { allowUnfree = true; };
        };
        
        pythonEnv = pkgs.python312.withPackages (ps: with ps; [
          pip
          setuptools
          wheel
          build
          twine
          # Development dependencies
          pytest
          ruff
          mypy
          types-setuptools
          black
        ]);
      in
      {
        devShell = pkgs.mkShell {
          name = "ndetect-dev-shell";
          
          buildInputs = [
            pythonEnv
          ];

          nativeBuildInputs = with pkgs; [
          ];

          shellHook = ''
            # Create venv if it doesn't exist
            if [ ! -d .venv ]; then
              ${pythonEnv}/bin/python -m venv .venv
            fi
            
            # Activate venv
            source .venv/bin/activate
            
            # Install package in development mode
            pip install -e .
            
            # Set PYTHONPATH
            export PYTHONPATH=$PYTHONPATH:$(pwd)
            
            echo "Development environment for ndetect is ready."
          '';
        };
      });
}
