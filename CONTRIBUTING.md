# Contributing

Run `python -m unittest discover -s tests -v` from the repository root. Use a synthetic reproducer for any changed classification and describe the connector conversion responsible. Report the probe ID and affected positions when opening an issue.

To verify distribution, build a wheel with `python -m pip wheel --no-deps --wheel-dir dist .` and run `python scripts/check_wheel.py dist`. The script installs into a fresh environment and runs the installed CLI from outside the checkout.
