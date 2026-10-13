import modal
import subprocess

# ১. একটি ডকার ইমেজ যেখানে Linux, GPU ও Ollama ইনস্টল থাকবে
image = (
    modal.Image.debian_slim()
    .apt_install("curl", "zstd")
    .run_commands(
        "curl -fsSL https://ollama.com/install.sh | sh",
        # মডেলটি ইমেজের ভেতরে আগে থেকেই ডাউনলোড করে নেওয়া
        "nohup ollama serve > /dev/null 2>&1 & sleep 5 && ollama pull qwen2.5:7b"
    )
    .env({"OLLAMA_HOST": "0.0.0.0:11434"})
)

app = modal.App("ollama-qwen-service")

# ২. সার্ভারলেস ফাংশন
@app.function(
    image=image,
    cpu=4,
    memory=8192,
    timeout=300,
    scaledown_window=60,
    env={"OLLAMA_HOST": "0.0.0.0:11434"}
)
@modal.web_server(port=11434, startup_timeout=120)
def serve():
    subprocess.Popen("ollama serve", shell=True)


