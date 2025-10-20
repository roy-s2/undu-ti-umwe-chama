from flask import Flask, request, jsonify, render_template
import requests
import base64
import json
import os
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'undu_ti_umwe_chama_secret_2023')

class MpesaDaraja:
    def __init__(self):
        # Use environment variables for security
        self.consumer_key = os.environ.get('DARAJA_CONSUMER_KEY', '2Qn44kLmyujxlRLoQyQO87WsAAbfkfcoAHXLtNxTSCleGI4d')
        self.consumer_secret = os.environ.get('DARAJA_CONSUMER_SECRET', 'QFGjKo0n5gdpX12AeXnyeArtrMhAhydG8ymNCovmfMidJH73INpQvdaYWteAh2se')
        self.business_shortcode = "174379"  # Keep sandbox for now
        self.passkey = os.environ.get('DARAJA_PASSKEY', 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919')
        self.callback_url = os.environ.get('DARAJA_CALLBACK_URL', '')  # Will set in Render
        self.base_url = "https://sandbox.safaricom.co.ke"  # Keep sandbox for now

    def format_phone_number(self, phone_number):
        """Convert any phone format to 2547XXXXXXXX format"""
        # Remove all non-digit characters
        cleaned = re.sub(r'\D', '', phone_number)
        
        # Handle different formats
        if cleaned.startswith('0') and len(cleaned) == 10:
            # Convert 07XXXXXXXX to 2547XXXXXXXX
            return '254' + cleaned[1:]
        elif cleaned.startswith('7') and len(cleaned) == 9:
            # Convert 7XXXXXXXX to 2547XXXXXXXX
            return '254' + cleaned
        elif cleaned.startswith('254') and len(cleaned) == 12:
            # Already in 2547XXXXXXXX format
            return cleaned
        elif cleaned.startswith('+254') and len(cleaned) == 13:
            # Convert +2547XXXXXXXX to 2547XXXXXXXX
            return cleaned[1:]
        else:
            # Return as is, let Daraja API handle validation
            return cleaned

    def get_access_token(self):
        """Get OAuth access token from Daraja API"""
        try:
            credentials = f"{self.consumer_key}:{self.consumer_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access_token')
                return self.access_token
            else:
                print(f"Token request failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error getting access token: {str(e)}")
            return None

    def stk_push(self, phone_number, amount, account_reference, transaction_desc="Chama Payment"):
        """Initiate STK Push"""
        try:
            # Format phone number to proper format
            formatted_phone = self.format_phone_number(phone_number)
            print(f"📱 Original phone: {phone_number} -> Formatted: {formatted_phone}")
            
            token = self.get_access_token()
            if not token:
                return {"error": "Failed to get access token"}

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            password = base64.b64encode(
                f"{self.business_shortcode}{self.passkey}{timestamp}".encode()
            ).decode()

            # Use Render URL for callback
            callback_url = os.environ.get('DARAJA_CALLBACK_URL', 'https://your-app.onrender.com/api/callback')
            
            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": amount,
                "PartyA": formatted_phone,
                "PartyB": self.business_shortcode,
                "PhoneNumber": formatted_phone,
                "CallBackURL": callback_url,
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "response": result,
                    "customer_message": result.get('CustomerMessage', 'Check your phone to complete payment'),
                    "checkout_request_id": result.get('CheckoutRequestID'),
                    "merchant_request_id": result.get('MerchantRequestID'),
                    "formatted_phone": formatted_phone
                }
            else:
                return {
                    "success": False,
                    "error": f"STK Push failed: {response.status_code} - {response.text}",
                    "formatted_phone": formatted_phone
                }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Exception: {str(e)}"
            }

mpesa = MpesaDaraja()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "chama_name": "Undu Ti Umwe",
        "deployed": True,
        "environment": "production",
        "phone_formatting": "flexible"
    })

@app.route('/api/initiate-payment', methods=['POST'])
def initiate_payment():
    try:
        data = request.get_json()
        
        phone = data['phone']
        amount = int(data['amount'])
        reference = data['reference']
        description = data.get('description', 'Chama Contribution')

        # Remove strict phone validation - accept any format
        # The format_phone_number method will handle conversion
        
        # Basic validation - just check if phone is provided
        if not phone or len(phone.strip()) == 0:
            return jsonify({
                "success": False,
                "error": "Phone number is required"
            }), 400

        if amount < 1 or amount > 100000:
            return jsonify({
                "success": False,
                "error": "Amount must be between 1 and 100,000"
            }), 400

        result = mpesa.stk_push(phone, amount, reference, description)
        return jsonify(result)

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

@app.route('/api/callback', methods=['POST'])
def payment_callback():
    try:
        callback_data = request.get_json()
        print("Payment callback received:", callback_data)
        return jsonify({"ResultCode": 0, "ResultDesc": "Success"}), 200
    except Exception as e:
        return jsonify({"ResultCode": 1, "ResultDesc": "Error"}), 500

@app.route('/api/format-phone', methods=['POST'])
def format_phone():
    """API endpoint to test phone formatting"""
    try:
        data = request.get_json()
        phone = data.get('phone', '')
        formatted = mpesa.format_phone_number(phone)
        
        return jsonify({
            "original": phone,
            "formatted": formatted,
            "valid": len(formatted) == 12 and formatted.startswith('2547')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 Undu Ti Umwe Chama - Flexible Phone Format")
    print("📱 Accepted formats: 07XXX, 7XXX, 2547XXX, +2547XXX")
    app.run(host='0.0.0.0', port=port, debug=False)