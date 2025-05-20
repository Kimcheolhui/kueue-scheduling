if __name__ == "__main__":
    from model import gen_image
    import sys
    import os
    from datetime import datetime

    prompt = sys.argv[1] if len(sys.argv) > 1 else "a cat riding a bike"
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    print(f"[INFO] Prompt: {prompt} | Step: {step}")

    img = gen_image(prompt, step)

    os.makedirs("/output", exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    filename = f"/output/{timestamp}.png"

    with open(filename, "wb") as f:
        f.write(img)

    print(f"[INFO] Image generation complete. Saved to {filename}")