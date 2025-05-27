import logging
import os
from datetime import datetime

def setup_logger():
    """Configura um sistema para gerar logs"""
    
    if not os.path.exists('logs'):
        os.mkdir('logs')
        
    logger = logging.getLogger('OpuspacApp')
    logger.setLevel(logging.INFO)
    
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    file_handler = logging.FileHandler(
        'logs/app.log',
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    return logger

def get_logger():
    return setup_logger()
