__version__ = "0.3.0"

"""Thin launcher for the main EvalData application."""

from Source.shared.runtime_paths import configure_runtime_environment


if __name__ == "__main__":
    configure_runtime_environment()
    from Source.datapreparation_app.app import main

    main()