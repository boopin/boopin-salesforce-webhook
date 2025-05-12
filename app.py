from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for
import requests
import os
import csv
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd

app = Flask(__name__)
load_dotenv()

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
        writer.writerow([datetime.now().strftime("%d-%m-%Y %H:%M"), status, message] + list(data.values()))

def log_failed_lead(data, error_msg, status_code, response_text):
    filename = "failed_leads.csv"
    file_exists = os.path.isfile(filename)
    with open(filename, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            headers = ["Timestamp", "Error", "Status", "Response", "Firstname", "Lastname", "Mobile", "Email", "Campaign_Source", "Campaign_Name"]
            writer.writerow(headers)
        writer.writerow([
            datetime.now().strftime("%d-%m-%Y %H:%M"),
            error_msg,
            status_code,
            response_text,
            data.get("Firstname", ""),
            data.get("Lastname", ""),
            data.get("Mobile", ""),
            data.get("Email", ""),
            data.get("Campaign_Source", ""),
            data.get("Campaign_Name", "")
        ])

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
        log_failed_lead(data, str(e), 500, "Webhook Error")
        return jsonify({"error": str(e)}), 500

@app.route("/retry-failed", methods=["POST"])
def retry_failed_leads():
    if not os.path.exists("failed_leads.csv"):
        return jsonify({"message": "No failed leads to retry."}), 404

    df = pd.read_csv("failed_leads.csv")
    if df.empty:
        return jsonify({"message": "No failed leads to retry."}), 200

    results = []
    for _, row in df.iterrows():
        data = {
            "Enquiry_Type": "Book_a_Test_Drive",
            "Firstname": row.get("Firstname", ""),
            "Lastname": row.get("Lastname", ""),
            "Mobile": row.get("Mobile", ""),
            "Email": row.get("Email", ""),
            "DealerCode": "PTC",
            "Shrm_SvCtr": "PETROMIN Jubail",
            "Make": "Jeep",
            "Line": "Wrangler",
            "Entry_Form": "EN",
            "Market": "Saudi Arabia",
            "Campaign_Source": row.get("Campaign_Source", ""),
            "Campaign_Name": row.get("Campaign_Name", ""),
            "Campaign_Medium": "Boopin",
            "TestDriveType": "In Showroom",
            "Extended_Privacy": "true",
            "Purchase_TimeFrame": "More than 3 months",
            "Source_Site": row.get("Campaign_Source", "").lower() + " Ads",
            "Marketing_Communication_Consent": "1",
            "Fund": "DD",
            "FormCode": "PET_Q2_25",
            "Request_Origin": "https://www.jeep-saudi.com",
            "MasterKey": "Jeep_EN_GENERIC_RI:RP:TD_0_8_1_6_50_42"
        }
        try:
            token = get_salesforce_token()
            status, response = send_to_salesforce(token, data)
            if status == 200:
                log_to_csv(data, status, response)
                results.append((data["Email"], "Success"))
            else:
                log_failed_lead(data, "Retry Failed", status, response)
                results.append((data["Email"], "Failed"))
        except Exception as e:
            log_failed_lead(data, str(e), 500, "Retry Exception")
            results.append((data["Email"], "Exception"))

    return jsonify({"results": results}), 200

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
