import torch
import os
import gdown
from PIL import Image
import torchvision.transforms as transforms

# ====== CONFIGURATION ======
file_id = "1l2K9j-QSadeNP1GFixbajo7TQrlVpoNJ"
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ====== Image Transformation (Same as Training) ======
transform_test = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.Grayscale(num_output_channels=3),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])

# ====== Class Labels ======
class_names = ["Glioma", "Meningioma",  "No_Tumor","pituitary"]

# ====== Load Model ======
def load_model(model_path="model/best_resnet18_4class.pth"):
    if not os.path.exists(model_path):
        dir_path = os.path.dirname(model_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        url = f"https://drive.google.com/uc?id={file_id}"
        print(f"Downloading model from Google Drive to: {model_path}")
        gdown.download(url, model_path, quiet=False)

    # Load full model object
    model = torch.load(model_path, map_location=device,weights_only=False)
    
    # Set to evaluation mode
    model.eval()

    # DEBUG: Confirm eval mode
    print(f"[DEBUG] Model eval mode: {not model.training}")  # Should print: True

    return model

# ====== Transform Image ======
def transform_image(image_input):
    if isinstance(image_input, str):  # It's a file path
        image = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, bytes):
        from io import BytesIO
        image = Image.open(BytesIO(image_input)).convert("RGB")
    elif hasattr(image_input, "read"):  # It's a BytesIO or file-like object
        image = Image.open(image_input).convert("RGB")
    else:
        raise ValueError(f"Unexpected type: {type(image_input)}")

    image_tensor = transform_test(image).unsqueeze(0).to(device)
    return image_tensor


# ====== Get Prediction ======
def get_prediction(model, image_tensor):
    with torch.no_grad():
        outputs = model(image_tensor)
        _, predicted = torch.max(outputs, 1)
        return class_names[predicted.item()]
