# robot-ong-do
AI-powered Vietnamese calligraphy robot demo using Fairino FR3 Cobot

# AI Calligraphy Robot FR3

This project is a recruitment/open-day demo using a Fairino FR5 cobot to write Vietnamese calligraphy based on user selection.

## Concept

Users select a Vietnamese calligraphy word from a web interface. The system loads a pre-designed SVG file, converts the SVG path into robot trajectory points, maps the points into the robot workspace, performs safety checks, and sends commands to the robot.

## Demo Words

- Tâm
- Tri thức
- Sáng tạo
- Tương lai
- Công nghệ
- Khát vọng

## System Pipeline

User selection  
→ Load SVG  
→ Parse SVG path  
→ Sample Bezier curves  
→ Scale to paper size  
→ Map to robot coordinates  
→ Safety check  
→ Send trajectory to Fairino FR5  

## Tech Stack

- Python
- svgpathtools
- NumPy
- OpenCV
- Streamlit
- Fairino SDK/API

## Project Structure

```text
assets/             SVG files and preview images
config/             Robot and paper configuration
src/                Main source code
outputs/            Generated trajectories and logs
tests/              Unit tests
docs/               Project documentation