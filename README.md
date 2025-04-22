VoiceX: Voice-to-Haptic Feedback System
VoiceX is a wearable device that transforms speech and vocal sounds into customizable haptic feedback through vibration motors. The system uses an ESP32 microcontroller to process audio input in real-time and dynamically adjust vibration patterns based on sound characteristics.
System Overview
VoiceX consists of two main components:

ESP32 Microcontroller: Captures audio, processes sound data, and controls vibration motors
Raspberry Pi Interface: Provides a web dashboard for configuration, monitoring, and data visualization

Features

Real-time voice activity detection
Dynamic haptic feedback based on sound intensity and frequency
Adjustable sensitivity via potentiometer or web interface
Customizable vibration patterns and "phrases"
Usage statistics and data visualization
Web-based configuration interface

Hardware Requirements
ESP32 Component

ESP32 development board
Microphone module (connected to pin 36)
Two vibration motors (connected to pins 25 and 26)
Potentiometer (connected to pin 34)
Status LED (connected to pin 2)
Power supply

Raspberry Pi Component

Raspberry Pi (any model with USB port)
USB-to-Serial adapter
Power supply

Installation
ESP32 Setup

Install the Arduino IDE and ESP32 board support
Open voicex_esp32.ino in the Arduino IDE
Connect the ESP32 to your computer
Select the correct board and port in the Arduino IDE
Upload the sketch to the ESP32

Raspberry Pi Setup

Connect the ESP32 to the Raspberry Pi via USB
Ensure Python 3 is installed on your Raspberry Pi
Install required Python packages:

bashpip install pyserial flask matplotlib numpy

Copy voicex_raspi.py to your Raspberry Pi
Create required directories:

bashmkdir -p ~/voicex_data/phrases

Run the Python script:

bashpython3 voicex_raspi.py
Usage
Hardware Controls

Potentiometer: Adjust the sound detection threshold
Status LED: Indicates voice activity detection

Web Interface
Access the web interface by navigating to http://[Raspberry-Pi-IP]:8080 in your browser.
The interface provides:

Threshold and frequency settings adjustment
Real-time data visualization
Saved vibration pattern management
Usage statistics

Configuration
The system can be configured through the web interface or by editing the config.json file located in the ~/voicex_data directory.
Main configuration parameters:

threshold: Sound intensity threshold for detecting voice activity (default: 500)
base_frequency: Base frequency for the first vibration motor (default: 100 Hz)
mod_frequency: Modulation frequency for the second vibration motor (default: 200 Hz)
filter_alpha: Smoothing factor for audio filtering (default: 0.2)
min_activity_duration: Minimum duration to register activity (default: 200 ms)

Creating Custom Vibration Phrases
Custom vibration patterns (phrases) can be created through the web interface under the "Phrases" section. Each phrase can have:

A unique identifier
A descriptive name
Pattern parameters

Monitoring and Analytics
The system records usage data in ~/voicex_data/usage_log.csv. The web interface provides visualizations of:

Total usage sessions
Average session duration
Daily usage statistics

Troubleshooting
Common Issues

No serial connection: Ensure the USB port is correctly specified in the Python script (SERIAL_PORT variable)
No sound detection: Adjust the threshold value or check the microphone connection
Motors not vibrating: Verify the motor connections and power supply

Debug Mode
The ESP32 sends debug information every second, which can be viewed in the serial monitor or the web interface's visualization page.
