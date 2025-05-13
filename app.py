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
            return redirect(url_for("index"))
        except Exception as e:
            return f"Error: {str(e)}", 500
    return render_template("form.html", title="Submit a Test Lead")

@app.route("/")
def index():
    return render_template("index.html", title="Boopin Webhook")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
