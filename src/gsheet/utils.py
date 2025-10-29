import gspread
import pandas
from src.config import settings

def create_credentials():
    """
    Create GSheet credentials from an environment variable

    Production use only, normally you could have the credentials file in your project
    Deploying with Heroku requires the credentials be placed somewhere else. Make sure
    the below env vars are set before use

    """
    credentials = {
        "type": "service_account",
        "project_id": settings.gs_project_id,
        "private_key_id": settings.gs_private_key_id,
        "private_key": settings.gs_private_key,
        "client_email": settings.gs_client_email,
        "client_id": settings.gs_client_id,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": settings.gs_509_cert_url,
        "universe_domain": "googleapis.com"
    }
    gc = gspread.service_account_from_dict(credentials)
    return gc


def write_to_gsheet(data: pandas.DataFrame, worksheet_name: str,
                    gc: gspread.client.Client, sh: str):
    """
    Write a pandas dataframe to a Google Sheet
    
    @param data: The pandas Dataframe. Headers are written as the first row
    @param worksheet_name: The name of the worksheet in the Google Sheet
    @param gc: The Gspread client, uses credentials set-up prior
    @param sh: The Google Sheet ID (Retrieved from the URL)
    """
    # Important: Enable both Google Drive and Google Sheet API for the key
    sh = gc.open_by_key(settings.roster_sheet_key)
    worksheet = sh.worksheet(worksheet_name)
    worksheet.update([data.columns.values.tolist()] + data.values.tolist())
    return {
        "success": True,
        "worksheet_updated": worksheet_name,
        "rows_updated": len(data)
    }