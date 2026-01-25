from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_mail import Mail, Message
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson import json_util
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import bcrypt, io, jwt, time, secrets, random
from urllib.parse import quote_plus
from flask import send_file, session
from captcha.image import ImageCaptcha
import random, string, io


from utils import load_model, transform_image, get_prediction

app = Flask(__name__)
CORS(app,supports_credentials=True,origins=["https://brain-tumour-61u1.vercel.app"])

# -------------------- Config --------------------
app.secret_key = 'your_secret_key_here'
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'pranshujena2511@gmail.com'        # Change this
app.config['MAIL_PASSWORD'] = 'gimxxcktgcchbdlf'                 # App password
app.config['MAIL_DEFAULT_SENDER'] = ('Team TumorDetect', 'pranshujena2511@gmail.com')


mail = Mail(app)

# -------------------- MongoDB --------------------
username = quote_plus("pranshujena2511")
password = quote_plus("Pranshu@91")
uri = f"mongodb+srv://{username}:{password}@cluster0.fk09csn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri)
db = client["brain_tumor_db"]
  # Twilio number (any verified one)



# -------------------- Collections --------------------
users_collection = db["registered_users"]
admin_collection = db["admin_users"]
history_collection = db["prediction_history"]
feedback_collection = db["feedback"]
contacts = db['contacts']

# -------------------- Temp Storage --------------------
otp_db = {}           # { email: {otp, expiry} }
pending_users = {}    # for registration only

# -------------------- Load Model --------------------
model = load_model("model/brain_tumor_resnet.pth")


# -------------------- Routes --------------------

@app.route('/')
def home():
    return "Brain Tumor Detection API"


@app.route("/generate-captcha")
def generate_captcha():
    from captcha.image import ImageCaptcha
    import random, string, io
    from flask import session, send_file

    # Use default font (no need to provide any font path)
    image_captcha = ImageCaptcha(width=200, height=80)

    # Generate random CAPTCHA text
    captcha_text = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    session['captcha'] = captcha_text.lower()

    # Render image to bytes buffer
    buf = io.BytesIO()
    image_captcha.write(captcha_text, buf)
    buf.seek(0)

    return send_file(buf, mimetype='image/png')


@app.route("/verify-captcha", methods=["POST"])
def verify_captcha():
    data = request.get_json()
    user_input = data.get("captcha", "").strip().lower()
    expected = session.get("captcha", "")

    if user_input == expected:
        return jsonify({"success": True})
    return jsonify({"success": False}), 400



# ========== PREDICTION ==========
@app.route('/predict', methods=['POST'])
def predict():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        email = request.form.get('email', 'unknown')
        image_bytes = io.BytesIO(file.read())
        image_tensor = transform_image(image_bytes)
        prediction = get_prediction(model, image_tensor)

        history_collection.insert_one({
            "email": email,
            "prediction": prediction,
            "timestamp": datetime.utcnow()
        })

        return jsonify({'prediction': prediction})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== PREDICTION HISTORY ==========
@app.route("/history", methods=["GET"])
def get_prediction_history():
    try:
        predictions = list(history_collection.find({}, {"email": 1, "prediction": 1, "timestamp": 1}))
        for prediction in predictions:
            prediction['_id'] = str(prediction['_id'])
            prediction['timestamp'] = prediction.get('timestamp').isoformat()
        return jsonify({"success": True, "predictions": predictions}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/delete-history/<id>", methods=["DELETE"])
def delete_prediction_by_id(id):
    try:
        result = history_collection.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 1:
            return jsonify({"success": True, "message": "Prediction deleted"}), 200
        return jsonify({"success": False, "message": "Prediction not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ========== ADMIN ==========
@app.route('/admin-login', methods=['POST'])
def admin_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    admin = admin_collection.find_one({"email": email})
    if not admin or admin['password'] != password:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

    return jsonify({'success': True, 'message': 'Login successful', 'email': email})


@app.route('/admin-dashboard', methods=['GET'])
def admin_dashboard():
    users = list(users_collection.find({}, {"_id": 0, "name": 1, "email": 1}))
    return jsonify({"users": users})


# ========== USER REGISTRATION ==========
@app.route('/user-register', methods=['POST'])
def register_user():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email', '').strip().lower()
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required'}), 400

    if users_collection.find_one({'email': email}):
        return jsonify({'success': False, 'message': 'Email already registered'}), 409

    otp = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    expiry = int(time.time()) + 60
    otp_db[email] = {'otp': otp, 'expiry': expiry}

    pending_users[email] = {
        'name': name,
        'email': email,
        'hashed_password': generate_password_hash(password)
    }

    try:
        msg = Message('Your OTP for Brain Tumor Detection App', recipients=[email])
        msg.html = f"""
        <div style="font-family: Arial; background-color: #1a1a1a; color: #fff; padding: 20px;">
            <h3>Hi {name},</h3>
            <p>Thank you for registering.</p>
            <p><strong>Your OTP is:</strong> 
               <span style="color:#ffd700; font-size:20px;">{otp}</span></p>
            <a href="https://brain-tumour-61u1.vercel.app"
               style="background:#ffd700; color:#000; padding:10px 20px; text-decoration:none; border-radius:5px;">
               Go to Home</a>
        </div>
        """
        mail.send(msg)
        return jsonify({'success': True, 'message': 'OTP sent to email'})
    except Exception as e:
        print("Mail error:", e)
        return jsonify({'success': False, 'message': 'Failed to send OTP'}), 500


@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({'success': False, 'message': 'Email and OTP required'}), 400

    record = otp_db.get(email)
    if not record or record['otp'] != otp:
        return jsonify({'success': False, 'message': 'Invalid OTP'}), 401

    if int(time.time()) > record['expiry']:
        return jsonify({'success': False, 'message': 'OTP expired'}), 403

    if email in pending_users:
        user_info = pending_users[email]
        users_collection.insert_one({
            'name': user_info['name'],
            'email': email,
            'hashed_password': user_info['hashed_password']
        })
        del pending_users[email]

    del otp_db[email]
    return jsonify({'success': True, 'message': 'OTP verified successfully'})


# ========== NEW: OTP FOR PREDICTION ==========
@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400

    user = users_collection.find_one({'email': email})
    if not user:
        return jsonify({'success': False, 'message': 'Email not registered'}), 404

    otp = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    expiry = int(time.time()) + 300
    otp_db[email] = {'otp': otp, 'expiry': expiry}

    try:
        msg = Message('Your OTP for Tumor Analysis Verification', recipients=[email])
        msg.body = f"Your OTP is: {otp}"
        mail.send(msg)
        return jsonify({'success': True, 'message': 'OTP sent successfully'})
    except Exception as e:
        print("OTP Send Error:", e)
        return jsonify({'success': False, 'message': 'Failed to send OTP'}), 500


# ========== LOGIN ==========
@app.route('/user-login', methods=['POST'])
def user_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password required'}), 400

    user = users_collection.find_one({'email': email})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    if not check_password_hash(user['hashed_password'], password):
        return jsonify({'success': False, 'message': 'Incorrect password'}), 401

    return jsonify({'success': True, 'email': email, 'message': 'Login successful'})


# ========== FEEDBACK ==========
@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data received"}), 400

    feedback_entry = {
        "fullName": data.get("fullName"),
        "email": data.get("email"),
        "feedbackTitle": data.get("feedbackTitle"),
        "category": data.get("category"),
        "rating": data.get("rating"),
        "detailedFeedback": data.get("detailedFeedback")
    }

    feedback_collection.insert_one(feedback_entry)
    return jsonify({"message": "Feedback received successfully"}), 200


@app.route("/get-feedback", methods=["GET"])
def get_feedback():
    try:
        feedback_list = list(feedback_collection.find({}, {
            "fullName": 1,
            "email": 1,
            "feedbackTitle": 1,
            "category": 1,
            "rating": 1,
            "detailedFeedback": 1
        }))
        for feedback in feedback_list:
            feedback['_id'] = str(feedback['_id'])
        return jsonify({"success": True, "feedback": feedback_list}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/delete_feedback/<feedback_id>', methods=['DELETE'])
def delete_feedback(feedback_id):
    try:
        result = feedback_collection.delete_one({"_id": ObjectId(feedback_id)})
        if result.deleted_count == 1:
            return jsonify({"message": "Feedback deleted successfully"}), 200
        return jsonify({"message": "Feedback not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== CONTACT ==========
@app.route('/contact', methods=['POST'])
def contact():
    data = request.get_json()
    full_name = data.get('fullName')
    email = data.get('email')
    subject = data.get('subject')
    message = data.get('message')

    if not full_name or not email or not message:
        return jsonify({'error': 'Missing required fields'}), 400

    contact_entry = {
        'fullName': full_name,
        'email': email,
        'subject': subject,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }

    contacts.insert_one(contact_entry)
    return jsonify({'message': 'Message received'}), 200


@app.route("/admin/contacts", methods=["GET"])
def get_contacts():
    try:
        contact_list = list(contacts.find())
        for contact in contact_list:
            contact['_id'] = str(contact['_id'])
        return jsonify(contact_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/contacts/<id>", methods=["DELETE"])
def delete_contact(id):
    try:
        result = contacts.delete_one({"_id": ObjectId(id)})
        if result.deleted_count:
            return jsonify({"message": "Deleted"}), 200
        return jsonify({"error": "Not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== Admin Seeder ==========
if __name__ == '__main__':
    if admin_collection.count_documents({"email": "pranshujena2511@gmail.com"}) == 0:
        admin_collection.insert_one({
            "email": "pranshujena2511@gmail.com",
            "password": "admin123"
        })
    app.run(debug=True)
