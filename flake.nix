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
          # Add mypy type stubs
          typing-extensions
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
            nodePackages.markdownlint-cli
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

            # Start mypy daemon if not already running
            if ! dmypy status >/dev/null 2>&1; then
              dmypy start -- --strict --ignore-missing-imports \
                --python-version=3.10 \
                --cache-dir=.mypy_cache \
                --no-namespace-packages \
                --exclude='^(build|dist|\.git|\.mypy_cache|\.pytest_cache|\.venv)/'
            fi

            # Set PYTHONPATH
            export PYTHONPATH=$PYTHONPATH:$(pwd)

            # Ensure library path includes stdenv cc lib
            export LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH

            echo "Development environment for ndetect is ready."
            echo "Use 'dmypy check .' to run type checking"

            # Ensure markdownlint is available
            echo "Markdown linting is available via 'markdownlint'"
          '';
        };
      });
}
