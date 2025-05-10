from flask import Flask, request, jsonify, send_file
import requests
import os
import csv
from datetime import datetime
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# Salesforce credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
TOKEN_URL = os.getenv("TOKEN_URL")
LEAD_API_PATH = "/services/apexrest/lead/createlead"

def get_salesforce_token():
    payload = {
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(TOKEN_URL, data=payload)
    response.raise_for_status()
    return response.json()

def send_to_salesforce(token, lead_data):
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/json"
    }
    instance_url = token["instance_url"]
    response = requests.post(instance_url + LEAD_API_PATH, headers=headers, json=lead_data)
    return response.status_code, response.text

def log_to_csv(data, status, message):
    filename = "leads.csv"
    file_exists = os.path.isfile(filename)
    with open(filename, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            headers = ["Timestamp", "Status", "Error"] + list(data.keys())
            writer.writerow(headers)
        writer.writerow([datetime.now().isoformat(), status, message] + list(data.values()))

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid or missing JSON"}), 400

    try:
        token = get_salesforce_token()
        status, response = send_to_salesforce(token, data)
        log_to_csv(data, status, response)
        return jsonify({"status": status, "response": response}), status
    except Exception as e:
        log_to_csv(data, 500, str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/download-log", methods=["GET"])
def download_log():
    log_path = "leads.csv"
    if os.path.exists(log_path):
        return send_file(log_path, mimetype="text/csv", as_attachment=True)
    else:
        return "Log file not found.", 404

@app.route("/", methods=["GET"])
def index():
    return "Webhook is live."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
