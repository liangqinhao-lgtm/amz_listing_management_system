"""日志配置"""
import logging
import os
import sys
from pathlib import Path

class ColoredFormatter(logging.Formatter):
    COLORS = {"DEBUG": "\033[36m", "INFO": "\033[32m", "WARNING": "\033[33m", "ERROR": "\033[31m"}
    RESET = "\033[0m"
    
    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)

def setup_logging(log_level: str = "INFO"):
    Path("logs").mkdir(exist_ok=True)
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"))
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def get_logger(name: str):
    return logging.getLogger(name)

setup_logging(os.getenv("LOG_LEVEL", "INFO"))
