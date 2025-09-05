import os, json
import time
from requests_oauthlib import OAuth2Session
from datetime import datetime, timedelta

class FitbitClient:
    def __init__(self, client_id, client_secret, redirect_uri, token_path="fitbit_token.json"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_path = token_path
        self.auth_url = "https://www.fitbit.com/oauth2/authorize"
        self.token_url = "https://api.fitbit.com/oauth2/token"

        self.session = self._initialize_session()

    def _initialize_session(self):
        print("Initializing FitbitClient...")
        # Load or generate tokens
        if not os.path.exists(self.token_path):
            token = self.generate_tokens()
            self.save_token(token)
        else:
            with open(self.token_path, "r") as f:
                token = json.load(f)

        # Validate token
        if (not token or
            "access_token" not in token or
            "refresh_token" not in token or
            token.get("expires_at", 0) < time.time()):
            print("Token missing, expired, or invalid. Generating new token...")
            token = self.generate_tokens()
            self.save_token(token)

        session = OAuth2Session(
            client_id=self.client_id,
            token=token,
            auto_refresh_url=self.token_url,
            auto_refresh_kwargs={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            token_updater=self.save_token,
        ) 
        return session
    
    # Define how to save refreshed tokens
    def save_token(self, token):
            with open(self.token_path, "w") as f:
                json.dump(token, f, indent=2)

    def generate_tokens(self):
        scope = ["activity", "heartrate", "sleep", "nutrition",
            "weight", "temperature", "respiratory_rate", "oxygen_saturation"]
        
        fitbit = OAuth2Session(self.client_id, redirect_uri=self.redirect_uri, scope=scope)
        authorization_url, _ = fitbit.authorization_url(self.auth_url)

        print("Go here and authorize:", authorization_url)
        redirect_response = input("Paste the full redirect URL here: ")

        token = fitbit.fetch_token(self.token_url,
                                client_secret=self.client_secret,
                                authorization_response=redirect_response)
        return token

    def get(self, url):
        if not url.startswith("https://"):
            url = f"https://api.fitbit.com{url}"
                
        resp = self.session.get(url)

        if resp.ok:
            return resp.json()
        else:
            raise Exception(f"Error {resp.status_code}: {resp.text}")
    
        
    # --- Convenience methods ---
    def get_timeseries(self, resource, params):
        print(f"Fetching {resource} timeseries data...")
        detail = params["detail"]
        start_date = params["start_date"]
        end_date = params.get("end_date", start_date)

        day = datetime.fromisoformat(start_date) if start_date != "today" else datetime.today()
        end = datetime.fromisoformat(end_date) if end_date != "today" else datetime.today()

        dataset = []

        while day <= end:
            date_str = day.strftime("%Y-%m-%d")
            response = self.get(f"/1/user/-/activities/{resource}/date/{date_str}/1d/{detail}.json")[f"activities-{resource}-intraday"]

            if isinstance(response, dict):
                for entry in response["dataset"]:
                    dataset.append({
                            "date": date_str,
                            "time": entry["time"],
                            "value": entry["value"]})
            else:  
                for entry in response[0]["minutes"]:
                    dataset.append({
                            "date": date_str,
                            "time": entry["minute"].split("T")[1],
                            "value": entry["value"]})            
            day += timedelta(days=1)
        return dataset

    def get_sleep(self, params):
        print("Fetching sleep timeseries data...")
        start_date = params["start_date"]
        end_date = params.get("end_date", start_date)
        return self.get(f"/1.2/user/-/sleep/date/{start_date}/{end_date}.json")["sleep"]
    