import os

from robot_stream.api.web_app import run_server


if __name__ == "__main__":
    run_server(os.path.dirname(os.path.abspath(__file__)))
