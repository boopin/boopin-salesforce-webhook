
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

def log_failed_lead(data, error_msg, status_code, response_text):
    filename = "failed_leads.csv"
    file_exists = os.path.isfile(filename)
    with open(filename, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            headers = ["Timestamp", "Error", "Status", "Response", "Firstname", "Lastname", "Mobile", "Email", "Campaign_Source", "Campaign_Name"]
            writer.writerow(headers)
        writer.writerow([
            datetime.now().isoformat(),
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

@app.route("/download-log")
def download_log():
    return send_file("leads.csv", mimetype="text/csv", as_attachment=True)

@app.route("/export-excel")
def export_excel():
    if not os.path.exists("leads.csv"):
        return "Log file not found.", 404
    df = pd.read_csv("leads.csv")
    output_path = "leads.xlsx"
    df.to_excel(output_path, index=False)
    return send_file(output_path, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="leads.xlsx")

@app.route("/download-failed-log")
def download_failed_log():
    if not os.path.exists("failed_leads.csv"):
        return "No failed leads found."
    return send_file("failed_leads.csv", mimetype="text/csv", as_attachment=True)

@app.route("/failed-logs")
def failed_logs():
    if not os.path.exists("failed_leads.csv"):
        return "No failed leads found."

    df = pd.read_csv("failed_leads.csv")
    error_types = sorted(df["Error"].dropna().unique()) if "Error" in df else []
    selected_error = request.args.get("error_type")
    if selected_error:
        df = df[df["Error"] == selected_error]

    headers = df.columns.tolist()
    rows = df.values.tolist()

    return render_template("failed_logs.html", title="Failed Leads Log",
                           headers=headers, rows=rows,
                           error_types=error_types,
                           selected_error=selected_error,
                           table=True)

@app.route("/logs")
def logs():
    if not os.path.exists("leads.csv"):
        return "Log file not found."
    df = pd.read_csv("leads.csv")

    campaign_filter = request.args.get("campaign")
    source_filter = request.args.get("source")
    from_date = request.args.get("from_date")

    all_campaigns = sorted(df["Campaign_Name"].dropna().unique()) if "Campaign_Name" in df else []
    all_sources = sorted(df["Campaign_Source"].dropna().unique()) if "Campaign_Source" in df else []

    if campaign_filter:
        df = df[df["Campaign_Name"] == campaign_filter]
    if source_filter:
        df = df[df["Campaign_Source"] == source_filter]
    if from_date:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df = df[df["Timestamp"] >= pd.to_datetime(from_date)]

    table_html = df.to_html(index=False, classes="table table-striped table-bordered")
    return render_template("logs.html", title="Lead Logs", table=table_html,
                           campaigns=all_campaigns, selected=campaign_filter,
                           sources=all_sources, selected_source=source_filter,
                           from_date=from_date or "")

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
            log_failed_lead(data, str(e), 500, "Form Submission Error")
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
    lead_count = 0
    last_time = None
    if os.path.exists("leads.csv"):
        df = pd.read_csv("leads.csv")
        lead_count = len(df)
        if "Timestamp" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
            if not df["Timestamp"].isnull().all():
                last_time = df["Timestamp"].max().strftime("%Y-%m-%d %H:%M")
    return render_template("index.html", title="Boopin Webhook", lead_count=lead_count, last_time=last_time)

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
                last_time = df["Timestamp"].max().strftime("%Y-%m-%d %H:%M")
    return jsonify({"lead_count": lead_count, "last_time": last_time})

@app.route("/export-failed-log")
def export_filtered_failed_log():
    if not os.path.exists("failed_leads.csv"):
        return "No failed leads found."

    df = pd.read_csv("failed_leads.csv")
    error_type = request.args.get("error_type")

    if error_type:
        df = df[df["Error"] == error_type]

    export_path = "filtered_failed_leads.xlsx"
    df.to_excel(export_path, index=False)

    return send_file(export_path, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="filtered_failed_leads.xlsx")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
