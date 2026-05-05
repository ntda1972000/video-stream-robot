import os

from robot_stream.streaming.publisher_app import run_publisher


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.abspath(__file__))
    run_publisher(project_root)
