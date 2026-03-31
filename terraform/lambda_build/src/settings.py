#from dotenv import load_dotenv
#import os

#load_dotenv()

#DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]
#S3_BUCKET = os.environ["S3_BUCKET"]
#OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
#OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
#TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
import os
import boto3

ssm = boto3.client("ssm")

def get_param(name):
    return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]

DYNAMODB_TABLE        = os.environ["DYNAMODB_TABLE"]
USER_PROFILES_TABLE   = os.environ["USER_PROFILES_TABLE"]
SESSIONS_TABLE        = os.environ["SESSIONS_TABLE"]
S3_BUCKET             = os.environ["S3_BUCKET"]
OPENAI_MODEL          = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

OPENAI_API_KEY        = get_param(os.environ["OPENAI_API_KEY_PARAM"])
TELEGRAM_BOT_TOKEN    = get_param(os.environ["TELEGRAM_TOKEN_PARAM"])
