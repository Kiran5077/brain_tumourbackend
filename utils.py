import torch
import os
import gdown
from PIL import Image
import torchvision.transforms as transforms

# ===== CONFIG =====
file_id = "1l2K9j-QSadeNP1GFixbajo7TQrlVpoNJ"

# FORCE CPU to reduce memory on Render
device = torch.device("cpu")

transform_test = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.Grayscale(num_output_channels=3),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])

class_names = ["Glioma", "Meningioma", "No_Tumor", "pituitary"]


# ===== LOAD MODEL =====
def load_model(model_path="model/best_resnet18_4class.pth"):

    if not os.path.exists(model_path):

        dir_path = os.path.dirname(model_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        url = f"https://drive.google.com/uc?id={file_id}"

        print(f"Downloading model from Google Drive to: {model_path}")

        gdown.download(url, model_path, quiet=False)

    # IMPORTANT FIX for PyTorch 2.6+
    model = torch.load(
        model_path,
        map_location="cpu",
        weights_only=False
    )

    model.eval()

    print(f"[DEBUG] Model eval mode: {not model.training}")

    return model


# ===== IMAGE TRANSFORM =====
def transform_image(image_input):

    if isinstance(image_input, str):
        image = Image.open(image_input).convert("RGB")

    elif isinstance(image_input, bytes):
        from io import BytesIO
        image = Image.open(BytesIO(image_input)).convert("RGB")

    elif hasattr(image_input, "read"):
        image = Image.open(image_input).convert("RGB")

    else:
        raise ValueError(f"Unexpected type: {type(image_input)}")

    image_tensor = transform_test(image).unsqueeze(0)

    return image_tensor


# ===== PREDICTION =====
def get_prediction(model, image_tensor):

    with torch.no_grad():
        outputs = model(image_tensor)
        _, predicted = torch.max(outputs, 1)

        return class_names[predicted.item()]
