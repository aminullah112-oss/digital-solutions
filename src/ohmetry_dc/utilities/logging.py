"""Logging setup for the command-line interface."""
import logging


def setup_logging(verbose: bool = False) -> logging.Logger:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return logging.getLogger("ohmetry_dc")
