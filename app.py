from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for
import requests
import os
import csv
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd

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

def log_google_lead(data, status, message):
    filename = "google_leads.csv"
    file_exists = os.path.isfile(filename)
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Status", "Message"] + list(data.keys()))
        writer.writerow([datetime.now().strftime("%d-%m-%Y %H:%M"), status, message] + list(data.values()))

@app.route("/google-webhook", methods=["POST"])
def google_webhook():
    data = request.json
    if not data:
        return jsonify({"error": "Missing JSON"}), 400

    mapped_data = {
        "Enquiry_Type": "Book_a_Test_Drive",
        "Firstname": data.get("First Name", ""),
        "Lastname": data.get("Last Name", ""),
        "Mobile": data.get("Phone Number", ""),
        "Email": data.get("Email", ""),
        "DealerCode": "PTC",
        "Shrm_SvCtr": "PETROMIN Jubail",
        "Make": "Jeep",
        "Line": "Grand Cherokee",
        "Entry_Form": "EN",
        "Market": "Saudi Arabia",
        "Campaign_Source": "Google Ads",
        "Campaign_Name": data.get("Campaign Name", ""),
        "Campaign_Medium": "Boopin",
        "TestDriveType": "In Showroom",
        "Extended_Privacy": "true",
        "Purchase_TimeFrame": data.get("Prefer to buy", "Not Specified"),
        "Source_Site": "google Ads",
        "Marketing_Communication_Consent": "1",
        "Fund": "DD",
        "FormCode": "PET_Q2_25",
        "Request_Origin": "https://www.jeep-saudi.com",
        "MasterKey": "Jeep_EN_GENERIC_RI:RP:TD_0_8_1_6_50_42"
    }

    try:
        token = get_salesforce_token()
        status, response = send_to_salesforce(token, mapped_data)
        log_google_lead(data, status, response)
        return jsonify({"status": status, "response": response}), status
    except Exception as e:
        log_google_lead(data, 500, str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/google-logs")
def google_logs():
    if not os.path.exists("google_leads.csv"):
        return "No Google Ads leads found."
    df = pd.read_csv("google_leads.csv")
    table_html = df.to_html(index=False, classes="table table-bordered table-striped")
    return render_template("google_logs.html", title="Google Ads Leads", table=table_html)

@app.route("/")
def index():
    lead_count = 0
    failed_count = 0
    last_time = None
    if os.path.exists("leads.csv"):
        df = pd.read_csv("leads.csv")
        lead_count = len(df)
        if "Timestamp" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
            if not df["Timestamp"].isnull().all():
                last_time = df["Timestamp"].max().strftime("%d-%m-%Y %H:%M")
    if os.path.exists("failed_leads.csv"):
        failed_df = pd.read_csv("failed_leads.csv")
        failed_count = len(failed_df)
    return render_template("index.html", title="Boopin Webhook", lead_count=lead_count,
                           last_time=last_time, failed_count=failed_count)

@app.route("/api/stats")
def api_stats():
    lead_count = 0
    last_time = None
    if os.path.exists("leads.csv"):
        df = pd.read_csv("leads.csv")
        lead_count = len(df)
        if "Timestamp" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
            if not df["Timestamp"].isnull().all():
                last_time = df["Timestamp"].max().strftime("%d-%m-%Y %H:%M")
    return jsonify({"lead_count": lead_count, "last_time": last_time})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
