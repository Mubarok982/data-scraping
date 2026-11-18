import os
import uvicorn
import gradio as gr

# Impor aplikasi FastAPI utama Anda dari dalam folder backend
from backend.app import app

# Hugging Face (Gradio SDK) secara bawaan mencari objek bernama 'demo' di file root.
# Kita buat blok Gradio dummy kecil agar mesin HF tenang dan tidak error (Invalid file descriptor).
demo = gr.Blocks()
with demo:
    gr.Markdown("# 🚀 DDC Scraper Portal Backend is Running!")
    gr.Markdown("Dashboard analitik menggunakan Tailwind kustom. API berjalan di backend.")

# Gabungkan aplikasi FastAPI Anda dengan Gradio dummy ke path tersembunyi
# Ini memastikan halaman depan ('/') tetap milik Dashboard HTML Anda, tapi HF tetap bahagia.
app = gr.mount_gradio_app(app, demo, path="/gradio-dummy")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
