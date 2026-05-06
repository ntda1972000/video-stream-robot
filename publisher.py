#!/usr/bin/env python3

import os

from robot_stream.streaming.publisher_app import run_publisher


if __name__ == "__main__":
    run_publisher(os.path.dirname(os.path.abspath(__file__)))
