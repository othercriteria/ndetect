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
          flake8
          isort
        ]);
      in
      {
        devShell = pkgs.mkShell {
          name = "ndetect-dev-shell";
          
          buildInputs = with pkgs; [
            pythonEnv
            stdenv.cc.cc.lib
            zlib
            glib
            pre-commit
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
            pip install -e ".[dev]"
            
            # Initialize pre-commit hooks
            pre-commit install
            
            # Set PYTHONPATH
            export PYTHONPATH=$PYTHONPATH:$(pwd)
            
            # Ensure library path includes stdenv cc lib
            export LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH
            
            echo "Development environment for ndetect is ready."
          '';
        };
      });
}
