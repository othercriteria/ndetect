{
  description = "Python development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShell = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Core Python
            python3
            python3Packages.pip
            python3Packages.virtualenv

            # Development tools
            python3Packages.mypy
            python3Packages.black
            python3Packages.ruff
            python3Packages.pytest

            # System dependencies
            git
          ];

          shellHook = ''
            # Create and activate venv if it doesn't exist
            if [ ! -d .venv ]; then
              python -m venv .venv
            fi
            source .venv/bin/activate

            # Install project dependencies
            pip install -e ".[dev]"

            # Setup git hooks if not already done
            if [ -d .git ] && [ ! -f .git/hooks/pre-commit ]; then
              pre-commit install
            fi

            # Start mypy daemon if not already running
            if ! dmypy status >/dev/null 2>&1; then
              dmypy start -- --strict --ignore-missing-imports \
                --python-version=3.10 \
                --cache-dir=.mypy_cache \
                --no-namespace-packages \
                --exclude='^(build|dist|\.git|\.mypy_cache|\.pytest_cache|\.venv)/'
            fi

            # Ensure virtualenv bin directory takes precedence
            export PATH="$(pwd)/.venv/bin:$PATH"

            # Set PYTHONPATH
            export PYTHONPATH=$PYTHONPATH:$(pwd)

            # Print versions for key tools
            echo "Python: $(python --version)"
            echo "MyPy: $(mypy --version)"
            echo "Black: $(black --version)"
            echo "Ruff: $(ruff --version)"
          '';
        };
      });
}
