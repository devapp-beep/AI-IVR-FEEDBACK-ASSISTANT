import os
from dotenv import load_dotenv

load_dotenv()  # load .env once at startup

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    # Add shared settings here if needed

class Development(Config):
    ENV = "development"
    DEBUG = True

class Production(Config):
    ENV = "production"
    DEBUG = False

class Testing(Config):
    TESTING = True
    DEBUG = True

CONFIG_MAP = {
    "development": Development,
    "production": Production,
    "testing": Testing,
}

def get_config():
    name = os.getenv("FLASK_CONFIG", "development").lower()
    return CONFIG_MAP.get(name, Development)
