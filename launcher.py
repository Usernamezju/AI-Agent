"""Entry point for packaged .exe — launches the Streamlit web UI."""
import os
import sys
import subprocess


def main():
    # Set up paths relative to the bundled app
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    os.chdir(base_dir)

    # Ensure .env exists
    env_path = os.path.join(base_dir, ".env")
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("DEEPSEEK_API_KEY=sk-your-key-here\n")
            f.write("SANDBOX_ROOT=./sandbox\n")
        print("Created .env template — please edit it with your API key.")
        print(f"Location: {env_path}")
        print()

    # Find streamlit executable
    streamlit_exe = os.path.join(os.path.dirname(sys.executable), "streamlit.exe")
    if not os.path.exists(streamlit_exe):
        streamlit_exe = "streamlit"

    app_path = os.path.join(base_dir, "ui", "app.py")
    print(f"Starting AI Agent at http://localhost:8501")
    print("Press Ctrl+C to stop.")
    print()

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", app_path,
         "--server.headless", "true",
         "--browser.serverAddress", "localhost"],
        cwd=base_dir,
    )


if __name__ == "__main__":
    main()
