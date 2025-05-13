from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for
import requests
import os
import csv
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import io
import json

app = Flask(__name__)
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
TOKEN_URL = os.getenv("TOKEN_URL")
LEAD_API_PATH = "/services/apexrest/lead/createlead"

def get_salesforce_token():
    """Obtain OAuth2 token from Salesforce"""
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
    """Send lead data to Salesforce API"""
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/json"
    }
    instance_url = token["instance_url"]
    response = requests.post(instance_url + LEAD_API_PATH, headers=headers, json=lead_data)
    return response.status_code, response.text

def log_lead(lead_data, status=200, error=""):
    """Log successful lead to CSV"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.exists("leads.csv")
    
    with open("leads.csv", "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            headers = ["Timestamp", "Status", "Error"] + list(lead_data.keys())
            writer.writerow(headers)
        
        row = [timestamp, status, error] + list(lead_data.values())
        writer.writerow(row)

def log_failed_lead(lead_data, status, response):
    """Log failed lead to CSV"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.exists("failed_leads.csv")
    
    with open("failed_leads.csv", "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Error", "Status", "Response", "Firstname", 
                             "Lastname", "Mobile", "Email", "Campaign_Source", "Campaign_Name"])
        
        writer.writerow([
            timestamp, 
            "API Error", 
            status, 
            response,
            lead_data.get("Firstname", ""),
            lead_data.get("Lastname", ""),
            lead_data.get("Mobile", ""),
            lead_data.get("Email", ""),
            lead_data.get("Campaign_Source", ""),
            lead_data.get("Campaign_Name", "")
        ])

@app.route("/form", methods=["GET", "POST"])
def form():
    """Handle test lead submission form"""
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
            
            if 200 <= status < 300:
                log_lead(data, status)
                return redirect(url_for("index"))
            else:
                log_failed_lead(data, status, response)
                return redirect(url_for("index"))
                
        except Exception as e:
            log_failed_lead(data, 500, str(e))
            return redirect(url_for("index"))
            
    return render_template("form.html", title="Submit a Test Lead")

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming webhook from TikTok/Snapchat"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ["Firstname", "Lastname", "Mobile", "Email"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Add default fields
        lead_data = {
            "Enquiry_Type": "Book_a_Test_Drive",
            "DealerCode": "PTC",
            "Shrm_SvCtr": "PETROMIN Jubail",
            "Make": "Jeep",
            "Line": "Wrangler",
            "Entry_Form": "EN",
            "Market": "Saudi Arabia",
            "Campaign_Medium": "Boopin",
            "TestDriveType": "In Showroom",
            "Extended_Privacy": "true",
            "Purchase_TimeFrame": "More than 3 months",
            "Marketing_Communication_Consent": "1",
            "Fund": "DD",
            "FormCode": "PET_Q2_25",
            "Request_Origin": "https://www.jeep-saudi.com",
            "MasterKey": "Jeep_EN_GENERIC_RI:RP:TD_0_8_1_6_50_42"
        }
        
        # Update with incoming data
        lead_data.update(data)
        
        # Ensure Source_Site is set correctly
        if "Campaign_Source" in data:
            lead_data["Source_Site"] = data["Campaign_Source"].lower() + " Ads"
            
        # Send to Salesforce
        token = get_salesforce_token()
        status, response = send_to_salesforce(token, lead_data)
        
        if 200 <= status < 300:
            log_lead(lead_data, status)
            return jsonify({"success": True, "message": "Lead created successfully"}), 200
        else:
            log_failed_lead(lead_data, status, response)
            return jsonify({"success": False, "error": response}), status
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/webhook/google", methods=["POST"])
def google_webhook():
    """Handle incoming webhook from Google Ads"""
    try:
        data = request.json
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Ensure the file exists with headers
        if not os.path.exists("google_leads.csv"):
            with open("google_leads.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "FirstName", "LastName", "Email", "Phone", 
                                "CampaignID", "CampaignName", "AdGroupID", "AdGroupName"])
        
        # Write the lead data
        with open("google_leads.csv", "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                data.get("firstName", ""),
                data.get("lastName", ""),
                data.get("email", ""),
                data.get("phone", ""),
                data.get("campaignId", ""),
                data.get("campaignName", ""),
                data.get("adGroupId", ""),
                data.get("adGroupName", "")
            ])
            
        # Optionally forward to Salesforce
        lead_data = {
            "Enquiry_Type": "Book_a_Test_Drive",
            "Firstname": data.get("firstName", ""),
            "Lastname": data.get("lastName", ""),
            "Mobile": data.get("phone", ""),
            "Email": data.get("email", ""),
            "DealerCode": "PTC",
            "Shrm_SvCtr": "PETROMIN Jubail",
            "Make": "Jeep",
            "Line": "Wrangler",
            "Entry_Form": "EN",
            "Market": "Saudi Arabia",
            "Campaign_Source": "Google",
            "Campaign_Name": data.get("campaignName", "Google Ads"),
            "Campaign_Medium": "Boopin",
            "TestDriveType": "In Showroom",
            "Extended_Privacy": "true",
            "Purchase_TimeFrame": "More than 3 months",
            "Source_Site": "google ads",
            "Marketing_Communication_Consent": "1",
            "Fund": "DD",
            "FormCode": "PET_Q2_25",
            "Request_Origin": "https://www.jeep-saudi.com",
            "MasterKey": "Jeep_EN_GENERIC_RI:RP:TD_0_8_1_6_50_42"
        }
        
        token = get_salesforce_token()
        send_to_salesforce(token, lead_data)
            
        return jsonify({"success": True, "message": "Google lead saved successfully"}), 200
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/google-leads")
def google_leads():
    """Display Google Ads leads"""
    if not os.path.exists("google_leads.csv"):
        return render_template("google_leads.html", title="Google Ads Leads", no_data=True)
    
    df = pd.read_csv("google_leads.csv")
    
    # Apply filters if provided
    campaign_filter = request.args.get("campaign")
    date_filter = request.args.get("date")
    
    if campaign_filter:
        df = df[df["CampaignName"].str.contains(campaign_filter, na=False, case=False)]
        
    if date_filter:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df = df[df["Timestamp"].dt.date == pd.to_datetime(date_filter).date()]
    
    # Format timestamp
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df["Timestamp"] = df["Timestamp"].dt.strftime("%d-%m-%Y %H:%M")
    
    # Get unique campaign names for filter dropdown
    campaigns = df["CampaignName"].dropna().unique().tolist()
    
    # Convert to HTML table
    table_html = df.to_html(index=False, classes="table table-striped table-bordered table-hover")
    
    return render_template(
        "google_leads.html", 
        title="Google Ads Leads", 
        table=table_html,
        campaigns=campaigns,
        selected=campaign_filter,
        date=date_filter
    )

@app.route("/download-google-leads")
def download_google_leads():
    """Download Google leads as CSV"""
    if not os.path.exists("google_leads.csv"):
        return "No Google Ads leads found.", 404
        
    return send_file(
        "google_leads.csv",
        as_attachment=True,
        download_name=f"google_leads_{datetime.now().strftime('%Y%m%d')}.csv",
        mimetype="text/csv"
    )

@app.route("/export-google-excel")
def export_google_excel():
    """Export Google leads as Excel"""
    if not os.path.exists("google_leads.csv"):
        return "No Google Ads leads found.", 404
        
    # Apply filters if provided
    df = pd.read_csv("google_leads.csv")
    
    campaign_filter = request.args.get("campaign")
    date_filter = request.args.get("date")
    
    if campaign_filter:
        df = df[df["CampaignName"].str.contains(campaign_filter, na=False, case=False)]
        
    if date_filter:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df = df[df["Timestamp"].dt.date == pd.to_datetime(date_filter).date()]
    
    # Create Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Google Leads")
        
    output.seek(0)
    
    filename = f"google_leads_{datetime.now().strftime('%Y%m%d')}"
    if campaign_filter:
        filename += f"_{campaign_filter}"
    
    return send_file(
        output,
        as_attachment=True,
        download_name=f"{filename}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/logs")
def logs():
    """Display lead logs with filtering"""
    if not os.path.exists("leads.csv"):
        return render_template("logs.html", title="Lead Logs", no_data=True)
        
    df = pd.read_csv("leads.csv")
    
    # Get unique campaigns and sources for filtering
    campaigns = df["Campaign_Name"].dropna().unique().tolist() if "Campaign_Name" in df.columns else []
    sources = df["Campaign_Source"].dropna().unique().tolist() if "Campaign_Source" in df.columns else []
    
    # Apply filters
    selected = request.args.get("campaign")
    selected_source = request.args.get("source")
    from_date = request.args.get("from_date")
    
    if selected and "Campaign_Name" in df.columns:
        df = df[df["Campaign_Name"] == selected]
        
    if selected_source and "Campaign_Source" in df.columns:
        df = df[df["Campaign_Source"] == selected_source]
        
    if from_date and "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df = df[df["Timestamp"].dt.date >= pd.to_datetime(from_date).date()]
    
    # Convert to HTML
    table_html = df.to_html(index=False, classes="table table-striped table-bordered table-hover")
    
    return render_template(
        "logs.html", 
        title="Lead Logs", 
        table=table_html,
        campaigns=campaigns,
        sources=sources,
        selected=selected,
        selected_source=selected_source,
        from_date=from_date
    )

@app.route("/failed-logs")
def failed_logs():
    """Display failed lead logs with filtering"""
    if not os.path.exists("failed_leads.csv"):
        return render_template("failed_logs.html", title="Failed Leads Log", no_data=True)
        
    df = pd.read_csv("failed_leads.csv")
    
    # Get unique error types for filtering
    error_types = df["Error"].dropna().unique().tolist() if "Error" in df.columns else []
    
    # Apply filter
    selected_error = request.args.get("error_type")
    if selected_error:
        df = df[df["Error"] == selected_error]
    
    # Convert to template format
    headers = df.columns.tolist()
    rows = df.values.tolist()
    
    return render_template(
        "failed_logs.html",
        title="Failed Leads Log",
        table=True,
        headers=headers,
        rows=rows,
        error_types=error_types,
        selected_error=selected_error
    )

@app.route("/dashboard")
def dashboard():
    """Display dashboard with charts"""
    if not os.path.exists("leads.csv"):
        return render_template("dashboard.html", title="Dashboard", 
                              labels=json.dumps([]), values=json.dumps([]))
    
    df = pd.read_csv("leads.csv")
    
    # Count leads by source
    if "Campaign_Source" in df.columns:
        source_counts = df["Campaign_Source"].value_counts()
        labels = source_counts.index.tolist()
        values = source_counts.values.tolist()
    else:
        labels, values = [], []
    
    return render_template(
        "dashboard.html",
        title="Dashboard", 
        labels=json.dumps(labels),
        values=json.dumps(values)
    )

@app.route("/download-log")
def download_log():
    """Download leads CSV"""
    if not os.path.exists("leads.csv"):
        return "No leads found.", 404
        
    return send_file(
        "leads.csv",
        as_attachment=True,
        download_name=f"leads_{datetime.now().strftime('%Y%m%d')}.csv",
        mimetype="text/csv"
    )

@app.route("/download-failed-log")
def download_failed_log():
    """Download failed leads CSV"""
    if not os.path.exists("failed_leads.csv"):
        return "No failed leads found.", 404
        
    return send_file(
        "failed_leads.csv",
        as_attachment=True,
        download_name=f"failed_leads_{datetime.now().strftime('%Y%m%d')}.csv",
        mimetype="text/csv"
    )

@app.route("/export-excel")
def export_excel():
    """Export leads as Excel"""
    if not os.path.exists("leads.csv"):
        return "No leads found.", 404
        
    df = pd.read_csv("leads.csv")
    
    # Apply filters if provided
    selected = request.args.get("campaign")
    selected_source = request.args.get("source")
    from_date = request.args.get("from_date")
    
    if selected and "Campaign_Name" in df.columns:
        df = df[df["Campaign_Name"] == selected]
        
    if selected_source and "Campaign_Source" in df.columns:
        df = df[df["Campaign_Source"] == selected_source]
        
    if from_date and "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df = df[df["Timestamp"].dt.date >= pd.to_datetime(from_date).date()]
    
    # Create Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Leads")
        
    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name=f"leads_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/export-failed-log")
def export_failed_log():
    """Export failed leads as Excel"""
    if not os.path.exists("failed_leads.csv"):
        return "No failed leads found.", 404
        
    df = pd.read_csv("failed_leads.csv")
    
    # Apply filters if provided
    selected_error = request.args.get("error_type")
    if selected_error:
        df = df[df["Error"] == selected_error]
    
    # Create Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Failed Leads")
        
    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name=f"failed_leads_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/retry-failed", methods=["POST"])
def retry_failed():
    """Retry failed leads"""
    if not os.path.exists("failed_leads.csv"):
        return jsonify({"message": "No failed leads to retry"}), 404
        
    df = pd.read_csv("failed_leads.csv")
    results = {"success": 0, "failure": 0}
    
    for _, row in df.iterrows():
        try:
            lead_data = {
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
                "Source_Site": row.get("Campaign_Source", "").lower() + " Ads" if row.get("Campaign_Source") else "",
                "Marketing_Communication_Consent": "1",
                "Fund": "DD",
                "FormCode": "PET_Q2_25",
                "Request_Origin": "https://www.jeep-saudi.com",
                "MasterKey": "Jeep_EN_GENERIC_RI:RP:TD_0_8_1_6_50_42"
            }
            
            token = get_salesforce_token()
            status, response = send_to_salesforce(token, lead_data)
            
            if 200 <= status < 300:
                log_lead(lead_data, status)
                results["success"] += 1
            else:
                results["failure"] += 1
                
        except Exception:
            results["failure"] += 1
    
    # Optionally clear the failed_leads.csv if all succeeded
    if results["failure"] == 0 and results["success"] > 0:
        headers = df.columns.tolist()
        with open("failed_leads.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
    
    return jsonify({"results": results})

@app.route("/api/stats")
def api_stats():
    """API endpoint for dashboard stats"""
    lead_count = 0
    failed_count = 0
    last_time = "-"
    
    if os.path.exists("leads.csv"):
        df = pd.read_csv("leads.csv")
        lead_count = len(df)
        if lead_count > 0 and "Timestamp" in df.columns:
            last_time = df["Timestamp"].iloc[-1]
    
    if os.path.exists("failed_leads.csv"):
        failed_df = pd.read_csv("failed_leads.csv")
        failed_count = len(failed_df)
    
    return jsonify({
        "lead_count": lead_count,
        "failed_count": failed_count,
        "last_time": last_time
    })

@app.route("/")
def index():
    """Render homepage with statistics"""
    lead_count = 0
    failed_count = 0
    last_time = "-"
    
    if os.path.exists("leads.csv"):
        df = pd.read_csv("leads.csv")
        lead_count = len(df)
        if lead_count > 0 and "Timestamp" in df.columns:
            last_time = df["Timestamp"].iloc[-1]
    
    if os.path.exists("failed_leads.csv"):
        failed_df = pd.read_csv("failed_leads.csv")
        failed_count = len(failed_df)
        
    return render_template(
        "index.html", 
        title="Boopin Webhook", 
        lead_count=lead_count,
        failed_count=failed_count,
        last_time=last_time
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
