# Boopin Salesforce Webhook

This lightweight Flask API receives lead data from TikTok and Snapchat via webhooks, and forwards it to Salesforce CRM in real-time.

---

## 🔧 How it works

- TikTok/Snapchat POST leads to `/webhook` endpoint
- The data is authenticated and immediately pushed to Salesforce using OAuth2
- All logic is handled securely server-side

---

## 🚀 Live Deployment Setup (via Render)

1. Connect this repo to [Render.com](https://render.com)
2. Deploy as a **Python Web Service**
3. Add these required environment variables in Render:

| Key           | Value                           |
|---------------|----------------------------------|
| `CLIENT_ID`   | Salesforce client ID            |
| `CLIENT_SECRET` | Salesforce client secret      |
| `USERNAME`    | Salesforce login email          |
| `PASSWORD`    | Password + security token       |
| `TOKEN_URL`   | e.g. `https://test.salesforce.com/services/oauth2/token` |

---

## 📦 Endpoints

| Method | Endpoint      | Purpose               |
|--------|---------------|-----------------------|
| `POST` | `/webhook`    | Accept lead payload from TikTok/Snapchat |
| `GET`  | `/`           | Health check          |

---

## ✅ Sample JSON Payload

```json
{
  "Firstname": "Test Omar",
  "Lastname": "Dummy Shaikh",
  "Mobile": "0512345681",
  "Email": "omar.test@example.com",
  "Campaign_Source": "Snapchat",
  "Campaign_Name": "PET-Q2-2025",
  ...
}
