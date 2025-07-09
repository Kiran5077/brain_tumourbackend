from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pymongo import MongoClient
from flask_mail import Mail, Message
from datetime import datetime
from utils import load_model, transform_image, get_prediction
from bson import ObjectId, json_util
from urllib.parse import quote_plus
from werkzeug.security import generate_password_hash, check_password_hash
import io, bcrypt, jwt, smtplib,time,secrets, random
from flask import send_file,session
from captcha.image import ImageCaptcha
import re

app = Flask(__name__)
CORS(app)

# Secret key
app.config['SECRET_KEY'] = 'your_secret_key_here'

# Mail config
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



# Twilio credentials
#TWILIO_ACCOUNT_SID = 'AC30c97a32d6557cdefc56091c580714dd'
#TWILIO_AUTH_TOKEN = '36b3d5f80974aa9bab83ec726a82d0e6'
#TWILIO_PHONE_NUMBER = '+19342470593'
#SUPER_ADMIN_PHONE = '+91xxxxxxxxxx'  # verified number

#twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


# MongoDB connection

client = MongoClient(uri)
db = client["brain_tumor_db"]

# Collections
model = load_model("model/brain_tumor_resnet.pth")
history_collection = db["prediction_history"]
admin_collection = db["admin_users"]
users_collection = db["registered_users"]
feedback_collection = db["feedback"]
contacts = db['contacts']
admin_otp_collection = db["admin_otps"]
otp_db = {}
pending_users = {}


SUPER_ADMIN_EMAIL = "pranshujena2511@gmail.com"


@app.route('/')
def home():
    return "Brain Tumor Detection API"

@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "OK", "message": "Server is alive"}), 200


# -------------------- PREDICTION --------------------
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

@app.route("/history", methods=["GET"])
def get_prediction_history():
    try:
        predictions = list(history_collection.find({}, {"email": 1, "prediction": 1, "timestamp": 1}))
        for p in predictions:
            p['_id'] = str(p['_id'])
            p['timestamp'] = p['timestamp'].isoformat() if p.get("timestamp") else None
        return jsonify({"success": True, "predictions": predictions}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/delete-history/<id>", methods=["DELETE"])
def delete_prediction_by_id(id):
    try:
        result = history_collection.delete_one({"_id": ObjectId(id)})
        if result.deleted_count:
            return jsonify({"success": True, "message": "Prediction deleted"}), 200
        return jsonify({"success": False, "message": "Prediction not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# -------------------- ADMIN REGISTRATION --------------------
# Optional: simple email format checker
def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email)

@app.route("/admin-register", methods=["POST"])
def admin_register():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    # phone = data.get("phone")  # ⛔️ Commented
    password = data.get("password")

    if not all([name, email, password]):
        return jsonify({"success": False, "message": "All fields required"}), 400

    if not is_valid_email(email):
        return jsonify({"success": False, "message": "Invalid email format."}), 400

    if admin_collection.find_one({"email": email}):
        return jsonify({"success": False, "message": "Admin already exists"}), 400

    try:
        confirm_msg = Message(
            "Thank you for registering as Admin",
            recipients=[email]
        )
        confirm_msg.body = (
            f"Hi {name},\n\n"
            f"Thank you for registering as an admin. Please wait while we verify and approve your request."
        )
        mail.send(confirm_msg)
    except Exception as e:
        return jsonify({"success": False, "message": "Invalid email. Could not send confirmation."}), 400

    # Optional: Send SMS removed for simplicity
    # if phone:
    #     try:
    #         twilio_client.messages.create(
    #             body=f"Hi {name}, thank you for registering as an admin. Await approval.",
    #             from_=TWILIO_PHONE_NUMBER,
    #             to=phone
    #         )
    #     except Exception as e:
    #         print("Failed to send SMS to admin:", str(e))

    otp = str(random.randint(100000, 999999))
    admin_otp_collection.delete_many({"email": email, "verified": False})
    admin_otp_collection.insert_one({
        "email": email,
        "name": name,
        "password": password,
        "otp": otp,
        "verified": False,
        "created_at": datetime.utcnow()
    })

    try:
        otp_msg = Message("Admin Approval OTP", recipients=[SUPER_ADMIN_EMAIL])
        otp_msg.body = (
            f"A new admin '{name}' requested access.\n\n"
            f"Email: {email}\nOTP: {otp}"
        )
        mail.send(otp_msg)
    except Exception as e:
        return jsonify({"success": False, "message": "Failed to email OTP to super admin."}), 500

    #try:
        #twilio_client.messages.create(
            ##body=f"Admin access OTP for '{name}' ({email}): {otp}",
            #from_=TWILIO_PHONE_NUMBER,
            #to=SUPER_ADMIN_PHONE
        #)
    #except Exception as e:
        #return jsonify({"success": False, "message": "Failed to SMS OTP to super admin."}), 500

    return jsonify({
        "success": True,
        "message": "Confirmation email sent to admin and OTP sent to Super Admin via email and SMS."
    }), 200

@app.route("/verify-admin-otp", methods=["POST"])
def verify_admin_otp():
    data = request.get_json()
    email, otp_input = data.get("email"), data.get("otp")

    # Find OTP entry
    otp_record = admin_otp_collection.find_one({
        "email": email,
        "otp": otp_input,
        "verified": False
    })

    if not otp_record:
        return jsonify({"success": False, "message": "Invalid OTP"}), 400

    try:
        # Send "Thank you" message to admin email
        msg = Message("Thank you for registering", recipients=[email])
        msg.body = f"Hi {otp_record['name']},\nYour admin registration is successful. Welcome!"
        mail.send(msg)
    except Exception as e:
        return jsonify({"success": False, "message": "Invalid email. Could not send confirmation."}), 400

    # Create admin record only after successful email
    admin_collection.insert_one({
        "name": otp_record["name"],
        "email": otp_record["email"],
        "password": otp_record["password"],
        "status": "approved"
    })

    # Mark OTP as used
    admin_otp_collection.update_one({"_id": otp_record["_id"]}, {"$set": {"verified": True}})

    return jsonify({"success": True, "message": "Admin registered successfully."}), 200


@app.route('/admin-login', methods=['POST'])
def admin_login():
    data = request.get_json()
    email, password = data.get('email'), data.get('password')
    admin = admin_collection.find_one({"email": email})
    if not admin:
        return jsonify({'success': False, 'message': 'Admin not found'}), 404
    if admin['password'] != password:
        return jsonify({'success': False, 'message': 'Incorrect password'}), 401
    if admin['status'] != "approved":
        return jsonify({'success': False, 'message': 'Access not yet approved'}), 403
    return jsonify({'success': True, 'message': 'Login successful', 'email': email}), 200

@app.route('/admin-dashboard', methods=['GET'])
def admin_dashboard():
    users = list(users_collection.find({}, {"_id": 0, "name": 1, "email": 1}))
    return jsonify({"users": users})


# -------------------- USER REGISTRATION + OTP --------------------
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
            <a href="https://brain-frontend3.vercel.app/"
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

# -------------------- FEEDBACK + CONTACT --------------------
@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.get_json()
    feedback_collection.insert_one(data)
    return jsonify({"message": "Feedback received successfully"}), 200

@app.route("/get-feedback", methods=["GET"])
def get_feedback():
    feedback_list = list(feedback_collection.find())
    for f in feedback_list:
        f['_id'] = str(f['_id'])
    return jsonify({"success": True, "feedback": feedback_list})

@app.route("/api/delete_feedback/<feedback_id>", methods=["DELETE"])
def delete_feedback(feedback_id):
    result = feedback_collection.delete_one({"_id": ObjectId(feedback_id)})
    if result.deleted_count:
        return jsonify({"message": "Deleted"}), 200
    return jsonify({"message": "Not found"}), 404

@app.route('/contact', methods=['POST'])
def contact():
    data = request.get_json()
    data['timestamp'] = datetime.utcnow().isoformat()
    contacts.insert_one(data)
    return jsonify({'message': 'Message received'}), 200

@app.route("/admin/contacts", methods=["GET"])
def get_contacts():
    contact_list = list(contacts.find())
    for contact in contact_list:
        contact['_id'] = str(contact['_id'])
    return jsonify(contact_list), 200

@app.route("/admin/contacts/<id>", methods=["DELETE"])
def delete_contact(id):
    result = contacts.delete_one({"_id": ObjectId(id)})
    if result.deleted_count:
        return jsonify({"message": "Deleted"}), 200
    return jsonify({"error": "Not found"}), 404

@app.route('/change-password', methods=['POST'])
def change_password():
    data = request.get_json()
    email = data.get('email')
    current_password = data.get('currentPassword')
    new_password = data.get('newPassword')
    is_admin = data.get('isAdmin', False)

    collection = admin_collection if is_admin else users_collection
    user = collection.find_one({'email': email})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    if is_admin:
        if user['password'] != current_password:
            return jsonify({'success': False, 'message': 'Incorrect current password'}), 401
        collection.update_one({'email': email}, {'$set': {'password': new_password}})
    else:
        if not check_password_hash(user['password'], current_password):
            return jsonify({'success': False, 'message': 'Incorrect current password'}), 401
        new_hashed = generate_password_hash(new_password)
        collection.update_one({'email': email}, {'$set': {'password': new_hashed}})

    return jsonify({'success': True, 'message': 'Password changed successfully'}), 200

if __name__ == '__main__':
    if admin_collection.count_documents({"email": SUPER_ADMIN_EMAIL}) == 0:
        admin_collection.insert_one({
            "name": "Super Admin",
            "email": SUPER_ADMIN_EMAIL,
            "password": "admin123",
            "status": "approved"
        })
    app.run(debug=True)
