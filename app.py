from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for
import requests
import os
import csv
import math
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

def format_timestamp_for_display(timestamp):
    """Format timestamp into a user-friendly readable format"""
    try:
        if isinstance(timestamp, str):
            dt = pd.to_datetime(timestamp)
        else:
            dt = timestamp
            
        # Format as "May 10, 2025 at 5:33 PM"
        return dt.strftime("%b %d, %Y at %I:%M %p")
    except:
        return timestamp  # Return original if conversion fails

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
                                "CampaignID", "CampaignName", "AdGroupID", "AdGroupName",
                                "SentToSalesforce", "SalesforceStatus", "LastSentTimestamp"])
        
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
                data.get("adGroupName", ""),
                False,
                "",
                ""
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
    """Display Google Ads leads with enhanced features"""
    if not os.path.exists("google_leads.csv"):
        return render_template(
            "google_leads.html", 
            title="Google Ads Leads", 
            no_data=True,
            total_leads=0,
            today_leads=0,
            filtered_count=0
        )
    
    # Read the data
    df = pd.read_csv("google_leads.csv")
    
    # Calculate some stats first
    total_leads = len(df)
    
    # Convert timestamps 
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    
    # Calculate today's leads
    today = pd.Timestamp.now().date()
    today_leads = len(df[df["Timestamp"].dt.date == today])
    
    # Last lead time - use the user-friendly format
    if not df.empty:
        last_lead_time = format_timestamp_for_display(df["Timestamp"].max())
    else:
        last_lead_time = None
        
    # Top campaign
    if not df.empty and "CampaignName" in df.columns:
        campaign_counts = df["CampaignName"].value_counts()
        top_campaign = campaign_counts.index[0] if not campaign_counts.empty else None
    else:
        top_campaign = None
    
    # Apply filters if provided
    campaign_filter = request.args.get("campaign")
    date_filter = request.args.get("date")
    search_filter = request.args.get("search")
    date_range = request.args.get("date_range")
    sort_option = request.args.get("sort", "newest")
    
    # Start with full dataset
    filtered_df = df.copy()
    
    # Apply campaign filter
    if campaign_filter:
        filtered_df = filtered_df[filtered_df["CampaignName"].str.contains(campaign_filter, na=False, case=False)]
    
    # Apply date filter
    if date_filter:
        filtered_date = pd.to_datetime(date_filter).date()
        filtered_df = filtered_df[filtered_df["Timestamp"].dt.date == filtered_date]
    
    # Apply search filter
    if search_filter:
        search_condition = (
            filtered_df["FirstName"].str.contains(search_filter, na=False, case=False) | 
            filtered_df["LastName"].str.contains(search_filter, na=False, case=False) | 
            filtered_df["Email"].str.contains(search_filter, na=False, case=False)
        )
        filtered_df = filtered_df[search_condition]
    
    # Apply sorting
    if sort_option == "newest":
        filtered_df = filtered_df.sort_values(by="Timestamp", ascending=False)
    elif sort_option == "oldest":
        filtered_df = filtered_df.sort_values(by="Timestamp", ascending=True)
    elif sort_option == "campaign":
        filtered_df = filtered_df.sort_values(by="CampaignName")
    elif sort_option == "name":
        filtered_df = filtered_df.sort_values(by=["FirstName", "LastName"])
    
    # Count after filtering
    filtered_count = len(filtered_df)
    
    # Campaign performance data for chart
    if not df.empty and "CampaignName" in df.columns:
        campaign_counts = df["CampaignName"].value_counts().head(10)
        campaign_data = {
            "labels": campaign_counts.index.tolist(),
            "values": campaign_counts.values.tolist()
        }
    else:
        campaign_data = None
    
    # Pagination
    page = int(request.args.get("page", 1))
    per_page = 20
    total_pages = math.ceil(filtered_count / per_page)
    
    # Adjust page if out of bounds
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages
    
    # Apply pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_df = filtered_df.iloc[start_idx:end_idx] if not filtered_df.empty else filtered_df
    
    # Format timestamps for display in the table (more readable format)
    if not paginated_df.empty:
        paginated_df["Timestamp"] = paginated_df["Timestamp"].apply(format_timestamp_for_display)
        
        # Format LastSentTimestamp if it exists
        if "LastSentTimestamp" in paginated_df.columns:
            paginated_df["LastSentTimestamp"] = paginated_df["LastSentTimestamp"].apply(
                lambda x: format_timestamp_for_display(x) if pd.notna(x) else "-"
            )
    
    # Get unique campaign names for filter dropdown
    campaigns = df["CampaignName"].dropna().unique().tolist() if "CampaignName" in df.columns else []
    
    # Convert to HTML table
    table_html = paginated_df.to_html(
        index=False, 
        classes="table table-striped table-bordered table-hover",
        table_id="googleLeadsTable"
    ) if not paginated_df.empty else ""
    
    return render_template(
        "google_leads.html", 
        title="Google Ads Leads", 
        table=table_html,
        campaigns=campaigns,
        selected=campaign_filter,
        date=date_filter,
        search=search_filter,
        date_range=date_range,
        sort=sort_option,
        total_leads=total_leads,
        today_leads=today_leads,
        last_lead_time=last_lead_time,
        top_campaign=top_campaign,
        filtered_count=filtered_count,
        campaign_data=campaign_data if campaign_data else {"labels": [], "values": []},
        page=page,
        pages=total_pages
    )

@app.route("/api/send-google-leads-to-salesforce", methods=["POST"])
def send_google_leads_to_salesforce():
    """API endpoint to send Google leads to Salesforce"""
    if not os.path.exists("google_leads.csv"):
        return jsonify({"error": "No Google leads found"}), 404
    
    data = request.json
    selection = data.get("selection", "all")
    mark_sent = data.get("markSent", True)
    log_results = data.get("logResults", True)
    filters = data.get("filters", {})
    
    # Read Google leads
    df = pd.read_csv("google_leads.csv")
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    
    # Ensure status columns exist
    if "SentToSalesforce" not in df.columns:
        df["SentToSalesforce"] = False
    if "SalesforceStatus" not in df.columns:
        df["SalesforceStatus"] = None
    if "LastSentTimestamp" not in df.columns:
        df["LastSentTimestamp"] = None
    
    # Apply the same filters as in the view
    if filters.get("campaign"):
        df = df[df["CampaignName"].str.contains(filters["campaign"], na=False, case=False)]
    
    if filters.get("date"):
        filter_date = pd.to_datetime(filters["date"]).date()
        df = df[df["Timestamp"].dt.date == filter_date]
    
    if filters.get("search"):
        search = filters["search"]
        search_condition = (
            df["FirstName"].str.contains(search, na=False, case=False) | 
            df["LastName"].str.contains(search, na=False, case=False) | 
            df["Email"].str.contains(search, na=False, case=False)
        )
        df = df[search_condition]
    
    # Further filter based on selection
    if selection == "unsent":
        df = df[~df["SentToSalesforce"].fillna(False)]
    elif selection == "failed":
        df = df[(df["SalesforceStatus"] != 200) & (df["SalesforceStatus"].notna())]
    
    # Process results
    results = {"success": 0, "failure": 0, "details": []}
    
    # Create a copy for updating status
    original_df = pd.read_csv("google_leads.csv")
    
    # Ensure status columns exist in original DF too
    if "SentToSalesforce" not in original_df.columns:
        original_df["SentToSalesforce"] = False
    if "SalesforceStatus" not in original_df.columns:
        original_df["SalesforceStatus"] = None
    if "LastSentTimestamp" not in original_df.columns:
        original_df["LastSentTimestamp"] = None
    
    # Process each lead
    for index, row in df.iterrows():
        try:
            lead_data = {
                "Enquiry_Type": "Book_a_Test_Drive",
                "Firstname": row.get("FirstName", ""),
                "Lastname": row.get("LastName", ""),
                "Mobile": row.get("Phone", ""),
                "Email": row.get("Email", ""),
                "DealerCode": "PTC",
                "Shrm_SvCtr": "PETROMIN Jubail",
                "Make": "Jeep",
                "Line": "Wrangler",
                "Entry_Form": "EN",
                "Market": "Saudi Arabia",
                "Campaign_Source": "Google",
                "Campaign_Name": row.get("CampaignName", "Google Ads"),
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
            status, response = send_to_salesforce(token, lead_data)
            
            if 200 <= status < 300:
                # Log successful lead
                log_lead(lead_data, status)
                results["success"] += 1
                
                # Update original dataframe if marking as sent
                if mark_sent:
                    original_df.loc[index, "SentToSalesforce"] = True
                    original_df.loc[index, "SalesforceStatus"] = status
                    original_df.loc[index, "LastSentTimestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                # Log failed lead
                log_failed_lead(lead_data, status, response)
                results["failure"] += 1
                
                # Update original dataframe
                if mark_sent:
                    original_df.loc[index, "SalesforceStatus"] = status
                    original_df.loc[index, "LastSentTimestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
        except Exception as e:
            results["failure"] += 1
            if log_results:
                print(f"Error sending lead {row.get('Email')}: {str(e)}")
    
    # Save updated status
    if mark_sent:
        original_df.to_csv("google_leads.csv", index=False)
    
    return jsonify(results)

@app.route("/download-google-leads")
def download_google_leads():
    """Download Google leads as CSV"""
    if not os.path.exists("google_leads.csv"):
        return "No Google Ads leads found.", 404
    
    # Apply filters if provided
    df = pd.read_csv("google_leads.csv")
    
    campaign_filter = request.args.get("campaign")
    date_filter = request.args.get("date")
    search_filter = request.args.get("search")
    
    # Convert timestamps 
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    
    # Apply campaign filter
    if campaign_filter:
        df = df[df["CampaignName"].str.contains(campaign_filter, na=False, case=False)]
    
    # Apply date filter
    if date_filter:
        filtered_date = pd.to_datetime(date_filter).date()
        df = df[df["Timestamp"].dt.date == filtered_date]
    
    # Apply search filter
    if search_filter:
        search_condition = (
            df["FirstName"].str.contains(search_filter, na=False, case=False) | 
            df["LastName"].str.contains(search_filter, na=False, case=False) | 
            df["Email"].str.contains(search_filter, na=False, case=False)
        )
        df = df[search_condition]
    
    # Convert back timestamp for CSV
    df["Timestamp"] = df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    
    # Create filtered CSV in memory
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    filename = f"google_leads_{datetime.now().strftime('%Y%m%d')}"
    if campaign_filter:
        filename += f"_{campaign_filter}"
    if date_filter:
        filename += f"_{date_filter}"
        
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        as_attachment=True,
        download_name=f"{filename}.csv",
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
    search_filter = request.args.get("search")
    
    # Convert timestamps 
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    
    # Apply campaign filter
    if campaign_filter:
        df = df[df["CampaignName"].str.contains(campaign_filter, na=False, case=False)]
    
    # Apply date filter
    if date_filter:
        filtered_date = pd.to_datetime(date_filter).date()
        df = df[df["Timestamp"].dt.date == filtered_date]
    
    # Apply search filter
    if search_filter:
        search_condition = (
            df["FirstName"].str.contains(search_filter, na=False, case=False) | 
            df["LastName"].str.contains(search_filter, na=False, case=False) | 
            df["Email"].str.contains(search_filter, na=False, case=False)
        )
        df = df[search_condition]
    
    # Format timestamps for Excel in user-friendly format
    df["Timestamp"] = df["Timestamp"].apply(format_timestamp_for_display)
    
    # Also format LastSentTimestamp if it exists
    if "LastSentTimestamp" in df.columns:
        df["LastSentTimestamp"] = df["LastSentTimestamp"].apply(
            lambda x: format_timestamp_for_display(x) if pd.notna(x) else "-"
        )
    
    # Create Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Google Leads")
        
    output.seek(0)
    
    filename = f"google_leads_{datetime.now().strftime('%Y%m%d')}"
    if campaign_filter:
        filename += f"_{campaign_filter}"
    if date_filter:
        filename += f"_{date_filter}"
    
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
        
        # Format timestamps in user-friendly way
        df["Timestamp"] = df["Timestamp"].apply(format_timestamp_for_display)
    
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

@app.route("/failed-logs", methods=["GET"])
def failed_logs():
    """Display failed lead logs with filtering and retry options"""
    if not os.path.exists("failed_leads.csv"):
        return render_template("failed_logs.html", title="Failed Leads Log", no_data=True)
        
    df = pd.read_csv("failed_leads.csv")
    
    # Format timestamps in user-friendly way
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df["Timestamp"] = df["Timestamp"].apply(format_timestamp_for_display)
    
    # Get unique error types and campaigns for filtering
    error_types = df["Error"].dropna().unique().tolist() if "Error" in df.columns else []
    campaigns = df["Campaign_Source"].dropna().unique().tolist() if "Campaign_Source" in df.columns else []
    
    # Apply filters
    selected_error = request.args.get("error_type")
    selected_campaign = request.args.get("campaign")
    
    if selected_error:
        df = df[df["Error"] == selected_error]
        
    if selected_campaign:
        df = df[df["Campaign_Source"] == selected_campaign]
    
    # Add row IDs for selective retry
    df = df.reset_index().rename(columns={"index": "ID"})
    
    # Group errors by type and count for chart
    error_counts = df["Error"].value_counts().to_dict()
    
    # Analyze common error patterns
    error_analysis = {}
    for error in error_types:
        if "INVALID" in error:
            error_analysis[error] = "Data validation error. Check the lead information for formatting issues."
        elif "AUTH" in error or "TOKEN" in error:
            error_analysis[error] = "Authentication failure. Verify Salesforce credentials."
        elif "RATE" in error:
            error_analysis[error] = "Rate limiting. The API has reached its call limit. Wait and retry."
        elif "TIMEOUT" in error:
            error_analysis[error] = "Connection timeout. Network or server performance issue."
        elif "API Error" in error:
            error_analysis[error] = "General API error. Check the status code for more information."
        else:
            error_analysis[error] = "Unknown error. Check the response for details."
    
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
        campaigns=campaigns,
        selected_error=selected_error,
        selected_campaign=selected_campaign,
        error_counts=json.dumps(error_counts),
        error_analysis=error_analysis
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
        
        # Format timestamps for better readability
        df["Timestamp"] = df["Timestamp"].apply(format_timestamp_for_display)
    
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
    selected_campaign = request.args.get("campaign")
    
    if selected_error:
        df = df[df["Error"] == selected_error]
        
    if selected_campaign:
        df = df[df["Campaign_Source"] == selected_campaign]
    
    # Format timestamps for better readability
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df["Timestamp"] = df["Timestamp"].apply(format_timestamp_for_display)
    
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
    
    # Check if specific IDs are provided for selective retry
    selected_ids = request.json.get("ids") if request.json else None
    
    df = pd.read_csv("failed_leads.csv")
    df = df.reset_index().rename(columns={"index": "ID"})
    
    # Filter by selected IDs if provided
    if selected_ids:
        df = df[df["ID"].isin(selected_ids)]
    
    results = {"success": 0, "failure": 0, "details": []}
    successful_indices = []
    
    for index, row in df.iterrows():
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
                successful_indices.append(index)
                results["details"].append({
                    "id": int(row.get("ID", 0)),
                    "name": f"{row.get('Firstname', '')} {row.get('Lastname', '')}",
                    "status": "Success",
                    "message": "Lead sent successfully"
                })
            else:
                results["failure"] += 1
                results["details"].append({
                    "id": int(row.get("ID", 0)),
                    "name": f"{row.get('Firstname', '')} {row.get('Lastname', '')}",
                    "status": "Failed",
                    "message": f"Status: {status}, Response: {response}"
                })
                
        except Exception as e:
            results["failure"] += 1
            results["details"].append({
                "id": int(row.get("ID", 0)),
                "name": f"{row.get('Firstname', '')} {row.get('Lastname', '')}",
                "status": "Error",
                "message": str(e)
            })
    
    # Remove successful leads from the failed_leads.csv if requested
    if request.json and request.json.get("removeSuccessful", True) and successful_indices:
        original_df = pd.read_csv("failed_leads.csv")
        original_df = original_df.reset_index().rename(columns={"index": "ID"})
        original_df = original_df[~original_df.index.isin(successful_indices)]
        original_df = original_df.drop(columns=["ID"])
        original_df.to_csv("failed_leads.csv", index=False)
    
    return jsonify({"results": results})

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
            timestamp = df["Timestamp"].iloc[-1]
            last_time = format_timestamp_for_display(timestamp)
    
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
            timestamp = df["Timestamp"].iloc[-1]
            last_time = format_timestamp_for_display(timestamp)
    
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
