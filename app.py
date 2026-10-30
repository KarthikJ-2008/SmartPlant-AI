import base64
import datetime
import io
import os
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
import numpy as np
from PIL import Image
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash

# Universal TFLite interpreter loading (Works locally on Windows & in Render production)
try:
  from ai_edge_litert.interpreter import Interpreter
except ImportError:
  try:
    from tflite_runtime.interpreter import Interpreter
  except ImportError:
    from tensorflow.lite.python.interpreter import Interpreter

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret-key-plantcare")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
CONFIDENCE_THRESHOLD = 65.0  # Images below 60% confidence are rejected

# ----------------- MongoDB Atlas Setup -----------------
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI, connect=False)
db = client["plantcare_db"]
users_col = db["users"]
predictions_col = db["predictions"]

# ----------------- Model Loading (TFLite) -----------------
MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")

# Supports plant_disease.tflite or Plant_Disease_model.tflite
TFLITE_PATH = os.path.join(MODEL_DIR, "plant_disease.tflite")
if not os.path.exists(TFLITE_PATH):
  TFLITE_PATH = os.path.join(MODEL_DIR, "Plant_Disease_model.tflite")

interpreter = None
input_details = None
output_details = None
input_shape = (1, 180, 180, 3)


def load_tflite_model():
  global interpreter, input_details, output_details, input_shape
  try:
    if os.path.exists(TFLITE_PATH):
      interpreter = Interpreter(model_path=TFLITE_PATH)
      interpreter.allocate_tensors()

      input_details = interpreter.get_input_details()
      output_details = interpreter.get_output_details()
      input_shape = input_details[0]["shape"]

      print(
          f"[INFO] TFLite model loaded successfully from {TFLITE_PATH}. Input"
          f" shape: {input_shape}"
      )
    else:
      print(f"[WARN] TFLite model not found at {TFLITE_PATH}.")
  except Exception as e:
    print(f"[ERROR] Failed to load TFLite model: {e}")


load_tflite_model()

# ----------------- Exact 20 Class Names from Training Notebook -----------------
CLASS_NAMES = [
    "Apple - Apple Scab",
    "Apple - Black Rot",
    "Apple - Cedar Apple Rust",
    "Apple - Healthy",
    "Corn (Maize) - Cercospora Leaf Spot / Gray Leaf Spot",
    "Corn (Maize) - Common Rust",
    "Corn (Maize) - Northern Leaf Blight",
    "Corn (Maize) - Healthy",
    "Potato - Early Blight",
    "Potato - Late Blight",
    "Potato - Healthy",
    "Tomato - Bacterial Spot",
    "Tomato - Early Blight",
    "Tomato - Late Blight",
    "Tomato - Leaf Mold",
    "Tomato - Septoria Leaf Spot",
    "Tomato - Target Spot",
    "Tomato - Yellow Leaf Curl Virus",
    "Tomato - Mosaic Virus",
    "Tomato - Healthy",
]


def allowed_file(filename):
  return (
      "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
  )


def preprocess_image(image_bytes, target_size=(180, 180)):
  img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
  img = img.resize(target_size)
  img_array = np.array(img, dtype=np.float32)

  # Do NOT divide by 255.0: The model contains layers.Rescaling(1./255)
  img_array = np.expand_dims(img_array, axis=0)
  return img_array


# ----------------- Routes & Auth -----------------


@app.route("/register", methods=["GET", "POST"])
def register():
  if "user_id" in session:
    return redirect(url_for("home"))

  if request.method == "POST":
    full_name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not full_name or not email or not password:
      flash("All fields are required.", "danger")
      return redirect(url_for("register"))

    if users_col.find_one({"email": email}):
      flash("An account with this email already exists.", "danger")
      return redirect(url_for("register"))

    hashed_password = generate_password_hash(password)
    user_record = {
        "name": full_name,
        "email": email,
        "password": hashed_password,
        "created_at": datetime.datetime.utcnow(),
    }
    res = users_col.insert_one(user_record)

    session["user_id"] = str(res.inserted_id)
    session["user_name"] = full_name
    session["user_email"] = email

    flash("Registration successful! Welcome to PlantCare AI.", "success")
    return redirect(url_for("home"))

  return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
  if "user_id" in session:
    return redirect(url_for("home"))

  if request.method == "POST":
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = users_col.find_one({"email": email})
    if user and check_password_hash(user["password"], password):
      session["user_id"] = str(user["_id"])
      session["user_name"] = user["name"]
      session["user_email"] = user["email"]
      flash("Logged in successfully.", "success")
      return redirect(url_for("home"))
    else:
      flash("Invalid email or password. Please try again.", "danger")
      return redirect(url_for("login"))

  return render_template("login.html")


@app.route("/logout")
def logout():
  session.clear()
  flash("You have been signed out.", "info")
  return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
def home():
  if "user_id" not in session:
    return redirect(url_for("login"))

  user_id = session["user_id"]
  prediction_result = None
  confidence_score = None
  uploaded_image_url = None
  error_message = None

  if request.method == "POST":
    if "image" not in request.files:
      error_message = "No file chosen. Please upload an image."
    else:
      file = request.files["image"]
      if file.filename == "":
        error_message = "No image selected."
      elif file and allowed_file(file.filename):
        try:
          file.seek(0)
          file_bytes = file.read()

          if not file_bytes:
            raise ValueError("Uploaded file is empty.")

          # Format correct MIME type for browser preview
          raw_ext = file.filename.rsplit(".", 1)[1].lower()
          mime_type = "jpeg" if raw_ext in ["jpg", "jpeg"] else raw_ext

          # Base64 Data URL for UI
          encoded_b64 = base64.b64encode(file_bytes).decode("utf-8")
          uploaded_image_url = f"data:image/{mime_type};base64,{encoded_b64}"

          if interpreter is not None:
            target_h, target_w = int(input_shape[1]), int(input_shape[2])
            processed_img = preprocess_image(
                file_bytes, target_size=(target_h, target_w)
            )
            processed_img = processed_img.astype(input_details[0]["dtype"])

            # Inference
            interpreter.set_tensor(input_details[0]["index"], processed_img)
            interpreter.invoke()

            preds = interpreter.get_tensor(output_details[0]["index"])[0]

            top_idx = int(np.argmax(preds))
            confidence_val = float(preds[top_idx]) * 100

            # --- 60% Confidence Threshold Check ---
            if confidence_val < CONFIDENCE_THRESHOLD:
              prediction_result = (
                  "Unable to identify / Not a valid plant leaf"
              )
              confidence_score = f"{confidence_val:.2f}% (Low Confidence)"
            else:
              confidence_score = f"{confidence_val:.2f}%"
              prediction_result = (
                  CLASS_NAMES[top_idx]
                  if top_idx < len(CLASS_NAMES)
                  else f"Class #{top_idx}"
              )

            # Save prediction record in MongoDB Atlas
            predictions_col.insert_one({
                "user_id": user_id,
                "image_data": uploaded_image_url,
                "prediction": prediction_result,
                "confidence": confidence_score,
                "created_at": datetime.datetime.utcnow(),
            })
          else:
            error_message = "Deep learning model is not loaded. Please verify plant_disease.tflite."
        except Exception as e:
          error_message = f"Error during inference: {str(e)}"
      else:
        error_message = "Unsupported file type. Use JPG, PNG, or WEBP."

  # Fetch recent analysis history
  history = list(
      predictions_col.find({"user_id": user_id})
      .sort("created_at", -1)
      .limit(10)
  )

  return render_template(
      "index.html",
      user_name=session.get("user_name"),
      user_email=session.get("user_email"),
      prediction=prediction_result,
      confidence=confidence_score,
      uploaded_image=uploaded_image_url,
      error=error_message,
      history=history,
  )


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port, debug=False)