#!/usr/bin/env python3
"""
Simple script to test an RTSP stream using OpenCV.
Usage:
    python dev_scripts/test_rtsp.py

Press 'q' to quit the video window.
"""
import cv2

# RTSP URL provided
RTSP_URL = 'rtsp://admin:R0148636@anr.microlumin.com:554/Streaming/Channels/102'

# Open the RTSP stream
cap = cv2.VideoCapture(RTSP_URL)
if not cap.isOpened():
    print(f"❌ Cannot open stream: {RTSP_URL}")
    exit(1)

# Read and display frames
while True:
    ret, frame = cap.read()
    if not ret:
        print("⚠️  Failed to grab frame; stream may have ended.")
        break

    cv2.imshow('RTSP Stream', frame)
    # Exit on 'q' key press
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
