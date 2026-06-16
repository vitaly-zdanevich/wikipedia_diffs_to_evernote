"""Entry point: ``python -m wikisync``."""

from __future__ import annotations

import logging
import os
import sys

from .config import Config
from .sync import run


def main() -> None:
    config = Config.from_env(os.environ)
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    sys.exit(run(config, os.environ))


if __name__ == '__main__':
    main()
