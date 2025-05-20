FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

RUN apt-get update && \
    apt-get install -y libgl1-mesa-glx libglib2.0-0 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


COPY ./requirements.txt .

RUN pip install -r requirements.txt

RUN mkdir -p /models/stable-diffusion-v1-4 && \
    python - <<'PY'
from diffusers import DiffusionPipeline
model_id = "CompVis/stable-diffusion-v1-4"
DiffusionPipeline.from_pretrained(
    model_id,
    variant="fp16",
    use_safetensors=True
).save_pretrained("/models/stable-diffusion-v1-4")
PY

COPY . .

ENV SD_MODEL=/models/stable-diffusion-v1-4

ENTRYPOINT ["python", "app.py"]