import tensorflow as tf

# Load the trained Keras model
model = tf.keras.models.load_model("model/Plant_disease_model.keras")

# Convert the model to TensorFlow Lite
converter = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_model = converter.convert()

# Save the TFLite model
with open("Plant_Disease_model.tflite", "wb") as f:
    f.write(tflite_model)

print("Model converted successfully!")
print("Saved as my_model.tflite")