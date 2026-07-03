import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-key-12345")
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:@localhost/time_tracker"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Karachi")
