import os

from robot_stream.api.web_app import run_server


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.abspath(__file__))
    run_server(project_root)
