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

@app.route("/download-log")
def download_log():
    return send_file("leads.csv", mimetype="text/csv", as_attachment=True)

@app.route("/logs")
def logs():
    if not os.path.exists("leads.csv"):
        return "Log file not found."
    df = pd.read_csv("leads.csv")
    campaign_filter = request.args.get("campaign")
    all_campaigns = sorted(df["Campaign_Name"].dropna().unique())
    if campaign_filter:
        df = df[df["Campaign_Name"] == campaign_filter]
    table_html = df.to_html(index=False, classes="table table-striped table-bordered")
    return render_template("logs.html", title="Lead Logs", table=table_html, campaigns=all_campaigns, selected=campaign_filter)

@app.route("/form", methods=["GET", "POST"])
def form():
    if request.method == "POST":
        data = {
            "Enquiry_Type": "Book_a_Test_Drive",
            "Firstname": request.form["firstname"],
            "Lastname": request.form["lastname"],
            "Mobile": request.form["mobile"],
            "Email": request.form["email"],
            "DealerCode": "PTC",
            "Shrm_SvCtr": "PETROMIN Jubail",
            "Make": "Jeep",
            "Line": "Wrangler",
            "Entry_Form": "EN",
            "Market": "Saudi Arabia",
            "Campaign_Source": request.form["source"],
            "Campaign_Name": request.form["campaign"],
            "Campaign_Medium": "Boopin",
            "TestDriveType": "In Showroom",
            "Extended_Privacy": "true",
            "Purchase_TimeFrame": "More than 3 months",
            "Source_Site": request.form["source"].lower() + " Ads",
            "Marketing_Communication_Consent": "1",
            "Fund": "DD",
            "FormCode": "PET_Q2_25",
            "Request_Origin": "https://www.jeep-saudi.com",
            "MasterKey": "Jeep_EN_GENERIC_RI:RP:TD_0_8_1_6_50_42"
        }
        try:
            token = get_salesforce_token()
            status, response = send_to_salesforce(token, data)
            log_to_csv(data, status, response)
            return redirect(url_for("logs"))
        except Exception as e:
            log_to_csv(data, 500, str(e))
            return f"Error: {str(e)}", 500

    return render_template("form.html", title="Submit a Test Lead")

@app.route("/dashboard")
def dashboard():
    if not os.path.exists("leads.csv"):
        return "Log file not found."
    df = pd.read_csv("leads.csv")
    if "Campaign_Source" not in df.columns:
        return "Campaign_Source column missing in logs."
    summary = df.groupby("Campaign_Source").size().to_dict()
    labels = list(summary.keys())
    values = list(summary.values())
    return render_template("dashboard.html", title="Dashboard: Leads by Source", labels=labels, values=values)

@app.route("/")
def index():
    return """
    <h2>🚀 Webhook is Live</h2>
    <ul>
        <li><a href="/form">📤 Submit Test Lead</a></li>
        <li><a href="/logs">📄 View Lead Log</a></li>
        <li><a href="/download-log">⬇️ Download CSV</a></li>
        <li><a href="/dashboard">📊 Dashboard</a></li>
    </ul>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
