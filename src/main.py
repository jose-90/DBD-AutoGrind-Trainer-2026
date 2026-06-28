import asyncio
import logging
from rich.logging import RichHandler
from src.gui import launch_gui

logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)

log = logging.getLogger("DBD-Trainer")

def main():
    log.info("Starting DBD AutoGrind Trainer 2026")
    # GUI will handle the asyncio event loop internally via customtkinter
    launch_gui()

if __name__ == "__main__":
    main()
