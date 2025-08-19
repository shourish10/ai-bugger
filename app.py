from flask import Flask, render_template_string, request, make_response, jsonify
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import os
from dotenv import load_dotenv
import io
import sys
import re
import subprocess
import tempfile
import time
import shutil
from PIL import Image
import sqlite3

load_dotenv()
app = Flask(__name__)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Global state to store the AI's response for download
fixed_code_result = ""
explanation_text = ""

def _js_string_filter(s):
    if s is None:
        return ''
    return s.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '')

app.jinja_env.filters['js_string'] = _js_string_filter

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>AI Code Debugger</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;900&family=Source+Code+Pro&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/codemirror.min.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/codemirror.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/python/python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/clike/clike.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/verilog/verilog.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/sql/sql.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/javascript/javascript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/xml/xml.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/css/css.min.js"></script>
    <style>
        :root {
            --bg-primary-dark: #121212;
            --bg-secondary-dark: #1e1e1e;
            --bg-card-dark: #282828;
            --bg-input-dark: #121212;
            --text-primary-dark: #E0E0E0;
            --text-secondary-dark: #B0B0B0;
            --accent-green: #92FE9D;
            --accent-blue: #00C9FF;
            --border-color-dark: #333;
            --shadow-color-dark: rgba(0, 0, 0, 0.5);
            --bg-primary-light: #f5f5f5;
            --bg-secondary-light: #ffffff;
            --bg-card-light: #e0e0e0;
            --bg-input-light: #ffffff;
            --text-primary-light: #333;
            --text-secondary-light: #666;
            --border-color-light: #ccc;
            --shadow-color-light: rgba(0, 0, 0, 0.1);
        }
        body.dark {
            --bg-primary: var(--bg-primary-dark);
            --bg-secondary: var(--bg-secondary-dark);
            --bg-card: var(--bg-card-dark);
            --bg-input: var(--bg-input-dark);
            --text-primary: var(--text-primary-dark);
            --text-secondary: var(--text-secondary-dark);
            --border-color: var(--border-color-dark);
            --shadow-color: var(--shadow-color-dark);
            --cursor-color: white;
        }
        body.light {
            --bg-primary: var(--bg-primary-light);
            --bg-secondary: var(--bg-secondary-light);
            --bg-card: var(--bg-card-light);
            --bg-input: var(--bg-input-light);
            --text-primary: var(--text-primary-light);
            --text-secondary: var(--text-secondary-light);
            --border-color: var(--border-color-light);
            --shadow-color: var(--shadow-color-light);
            --cursor-color: black;
        }
        body {
            font-family: 'Fira Sans', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            margin: 0;
            line-height: 1.6;
            transition: background-color 0.3s ease, color 0.3s ease;
        }
        .container {
            max-width: 1400px;
            margin: 40px auto;
            padding: 30px;
            background: var(--bg-secondary);
            border-radius: 15px;
            box-shadow: 0 10px 30px var(--shadow-color);
            transition: all 0.3s ease;
        }
        .header {
            text-align: center;
            margin-bottom: 2.5rem;
            position: relative;
        }
        .header h1 {
            font-size: 3.5rem;
            font-weight: 900;
            color: var(--text-primary);
            margin: 0 0 10px;
            text-shadow: 0 4px 15px rgba(0, 255, 255, 0.4);
            letter-spacing: 0.05em;
            animation: fadeIn 1s ease-in-out;
        }
        .header p {
            color: var(--text-secondary);
            font-size: 1.1rem;
            margin: 0;
            animation: fadeIn 1.5s ease-in-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .theme-toggle-button {
            position: absolute;
            top: 10px;
            right: 10px;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.2rem;
            transition: all 0.3s ease;
        }
        .theme-toggle-button:hover {
            transform: scale(1.1);
        }
        .theme-toggle-button i.fa-sun { color: #f39c12; }
        .theme-toggle-button i.fa-moon { color: #f1c40f; }
        .welcome-screen {
            display: {{ 'none' if code or result or explanation or output else 'flex' }};
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background: linear-gradient(135deg, #1f1c2c, #353457);
            color: #f0f0f0;
            text-align: center;
            animation: background-pan 10s infinite alternate linear;
            position: relative;
            overflow: hidden;
        }
        .wavy-grid-bg {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: radial-gradient(rgba(255, 255, 255, 0.1) 1px, transparent 1px);
            background-size: 30px 30px;
            z-index: 0;
            opacity: 0.3;
            animation: wavy-move 30s linear infinite;
        }
        @keyframes wavy-move {
            0% { background-position: 0 0; }
            100% { background-position: 100% 100%; }
        }
        .cubes-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            perspective: 800px;
            z-index: 1;
        }
        .cube {
            position: absolute;
            width: 50px;
            height: 50px;
            opacity: 0.1;
            transform-style: preserve-3d;
            animation: cube-rotate 20s linear infinite, cube-move 15s ease-in-out infinite alternate;
        }
        .cube-face {
            position: absolute;
            width: 100%;
            height: 100%;
            border: 1px solid rgba(0, 255, 255, 0.2);
            background: rgba(0, 255, 255, 0.1);
        }
        .cube-face:nth-child(1) { transform: rotateY(0deg) translateZ(25px); }
        .cube-face:nth-child(2) { transform: rotateX(90deg) translateZ(25px); }
        .cube-face:nth-child(3) { transform: rotateY(90deg) translateZ(25px); }
        .cube-face:nth-child(4) { transform: rotateY(180deg) translateZ(25px); }
        .cube-face:nth-child(5) { transform: rotateY(-90deg) translateZ(25px); }
        .cube-face:nth-child(6) { transform: rotateX(-90deg) translateZ(25px); }
        .cube:nth-child(1) { top: 20%; left: 15%; animation-delay: 0s; }
        .cube:nth-child(2) { top: 60%; left: 80%; animation-delay: 3s; }
        .cube:nth-child(3) { top: 80%; left: 30%; animation-delay: 6s; }
        .cube:nth-child(4) { top: 10%; left: 50%; animation-delay: 9s; }
        .cube:nth-child(5) { top: 40%; left: 60%; animation-delay: 12s; }
        @keyframes cube-rotate {
            from { transform: rotateX(0deg) rotateY(0deg); }
            to { transform: rotateX(360deg) rotateY(360deg); }
        }
        @keyframes cube-move {
            from { transform: translateY(0); }
            to { transform: translateY(50px); }
        }
        @keyframes background-pan {
            from { background-position: 0% 0%; }
            to { background-position: 100% 100%; }
        }
        .hero-content {
            z-index: 2;
        }
        .hero-content h1 {
            font-size: 5rem;
            font-weight: 900;
            text-shadow: 0 5px 20px rgba(0, 255, 255, 0.3);
            margin: 0;
            animation: text-glow 2s ease-in-out infinite alternate;
        }
        .hero-content p {
            font-size: 1.5rem;
            max-width: 600px;
            margin: 1rem auto 2.5rem;
            color: #C0C0C0;
        }
        .hero-btn {
            background: linear-gradient(45deg, #00C9FF, #92FE9D);
            border: none;
            padding: 15px 40px;
            font-size: 1.2rem;
            font-weight: 700;
            border-radius: 50px;
            color: #121212;
            cursor: pointer;
            box-shadow: 0 5px 20px rgba(0, 201, 255, 0.3);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .hero-btn:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 201, 255, 0.5);
        }
        @keyframes text-glow {
            from { text-shadow: 0 5px 20px rgba(0, 255, 255, 0.3); }
            to { text-shadow: 0 8px 25px rgba(146, 254, 157, 0.5); }
        }
        .language-tabs {
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 15px;
            margin-bottom: 2rem;
        }
        .language-tab {
            background: var(--bg-card);
            color: var(--accent-green);
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 10px;
            border: 1px solid var(--border-color);
        }
        .language-tab:hover {
            background: var(--border-color);
            transform: translateY(-2px);
        }
        .language-tab.active {
            background: linear-gradient(45deg, var(--accent-blue), var(--accent-green));
            color: var(--bg-primary-dark);
            border: 1px solid var(--accent-green);
            transform: translateY(-3px);
            box-shadow: 0 4px 15px rgba(146, 254, 157, 0.3);
        }
        .split-view {
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
        }
        .code-editor, .output-panel {
            flex: 1;
            min-width: 400px;
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: 12px;
            box-shadow: inset 0 0 10px rgba(0,0,0,0.2);
        }
        .output-panel {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        h3 {
            color: var(--accent-blue);
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 10px;
            margin-top: 0;
            font-size: 1.5rem;
            font-weight: 700;
        }
        pre, .execution-output {
            background: var(--bg-input);
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
            font-family: 'Source Code Pro', monospace;
            border: 1px solid var(--border-color);
            box-shadow: inset 0 0 5px rgba(0,0,0,0.3);
        }
        .execution-output {
            color: var(--accent-green);
        }
        .CodeMirror {
            height: 450px;
            font-size: 1rem;
            line-height: 1.5;
            background: var(--bg-input);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-primary);
            transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease;
        }
        .CodeMirror-gutters {
            background: var(--bg-input);
            border-right: 1px solid var(--border-color);
            transition: background-color 0.3s ease, border-color 0.3s ease;
        }
        .CodeMirror-cursor {
            border-left: 1px solid var(--cursor-color) !important;
            transition: border-color 0.3s ease;
        }
        .CodeMirror-linenumber {
            color: var(--text-secondary);
        }
        input[type="text"] {
            width: 100%;
            padding: 10px 15px;
            margin-top: 10px;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-primary);
            font-family: 'Fira Sans', sans-serif;
            transition: all 0.2s ease;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 2px rgba(0, 201, 255, 0.3);
        }
        .button-group {
            display: flex;
            justify-content: flex-end;
            gap: 15px;
            margin-top: 20px;
        }
        .button {
            padding: 12px 25px;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            border: none;
            text-decoration: none;
            text-align: center;
        }
        .button.debug {
            background: linear-gradient(45deg, var(--accent-blue), var(--accent-green));
            color: var(--bg-primary-dark);
        }
        .button.debug:hover {
            transform: translateY(-3px);
            box-shadow: 0 5px 20px rgba(0, 201, 255, 0.3);
        }
        .button.download {
            background: var(--bg-card);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }
        .button.download:hover {
            background: var(--border-color);
        }
        .button.loading {
            background: var(--text-secondary);
            cursor: not-allowed;
            color: var(--bg-secondary);
        }
        .button.loading .spinner {
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top: 2px solid #fff;
            border-radius: 50%;
            width: 16px;
            height: 16px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-left: 10px;
            vertical-align: middle;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .chatbot-toggle-button {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: linear-gradient(45deg, var(--accent-green), var(--accent-blue));
            color: var(--bg-primary-dark);
            border: none;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            font-size: 1.8rem;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            z-index: 1001;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .chatbot-toggle-button:hover {
            transform: scale(1.1);
            box-shadow: 0 6px 25px rgba(0, 255, 255, 0.5);
        }
        .chatbot-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 350px;
            height: 450px;
            background: var(--bg-card);
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            z-index: 1000;
            transform: scale(0.8) translateY(20px);
            opacity: 0;
            pointer-events: none;
            transition: all 0.3s cubic-bezier(0.68, -0.55, 0.27, 1.55);
        }
        .chatbot-container.active {
            transform: scale(1) translateY(0);
            opacity: 1;
            pointer-events: auto;
        }
        .chatbot-header {
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-green));
            color: var(--bg-primary-dark);
            padding: 15px;
            font-size: 1.2rem;
            font-weight: 700;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
        }
        .chatbot-header .close-btn {
            background: none;
            border: none;
            color: var(--bg-primary-dark);
            font-size: 1.5rem;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .chatbot-header .close-btn:hover {
            transform: rotate(90deg);
        }
        .chatbot-messages {
            flex-grow: 1;
            padding: 15px;
            overflow-y: auto;
            background-color: var(--bg-secondary);
            display: flex;
            flex-direction: column;
            gap: 10px;
            border-bottom: 1px solid var(--border-color);
        }
        .message {
            max-width: 80%;
            padding: 12px 18px;
            border-radius: 20px;
            font-size: 0.95rem;
            word-wrap: break-word;
            line-height: 1.4;
            animation: message-fade-in 0.3s ease-out;
        }
        @keyframes message-fade-in {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .user-message {
            background: #007BFF;
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 5px;
        }
        .bot-message {
            background: var(--bg-card);
            color: var(--text-primary);
            align-self: flex-start;
            border-bottom-left-radius: 5px;
        }
        .typing-indicator {
            display: flex;
            gap: 4px;
            padding: 12px 18px;
            border-radius: 20px;
            background: var(--bg-card);
            color: var(--text-primary);
            align-self: flex-start;
            border-bottom-left-radius: 5px;
        }
        .typing-indicator span {
            width: 8px;
            height: 8px;
            background: var(--text-primary);
            border-radius: 50%;
            animation: blink 1s infinite;
        }
        @keyframes blink {
            0%, 100% { opacity: 0.2; }
            50% { opacity: 1; }
        }
        .chatbot-input {
            display: flex;
            align-items: center;
            padding: 10px;
            background: var(--bg-card);
        }
        .chatbot-input input {
            flex-grow: 1;
            padding: 12px;
            border-radius: 25px;
            border: 1px solid var(--border-color);
            background: var(--bg-input);
            color: var(--text-primary);
            margin-right: 10px;
            transition: all 0.2s ease;
        }
        .chatbot-input input:focus {
            outline: none;
            border-color: var(--accent-blue);
        }
        .chatbot-input button {
            background: linear-gradient(45deg, var(--accent-blue), var(--accent-green));
            border: none;
            border-radius: 50%;
            width: 45px;
            height: 45px;
            color: var(--bg-primary-dark);
            cursor: pointer;
            font-size: 1.1rem;
            transition: transform 0.2s;
        }
        .chatbot-input button:hover {
            transform: scale(1.1);
        }
        .image-upload-label {
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 50%;
            width: 45px;
            height: 45px;
            display: flex;
            justify-content: center;
            align-items: center;
            margin-right: 10px;
            cursor: pointer;
            font-size: 1.2rem;
            color: var(--text-secondary);
            transition: all 0.2s ease;
        }
        .image-upload-label:hover {
            background: var(--border-color);
            color: var(--text-primary);
        }
        .image-preview-container {
            padding: 10px;
            background: var(--bg-card);
            border-top: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            position: relative;
            gap: 10px;
        }
        .image-preview {
            max-width: 80px;
            max-height: 80px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }
        .remove-image-btn {
            position: absolute;
            top: 5px;
            right: 5px;
            background: rgba(255, 0, 0, 0.7);
            color: white;
            border: none;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            font-size: 1rem;
            cursor: pointer;
            line-height: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            opacity: 0.8;
        }
        .remove-image-btn:hover {
            opacity: 1;
        }
        .message img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            margin-top: 10px;
        }
        @media (max-width: 900px) {
            .split-view {
                flex-direction: column;
            }
            .code-editor, .output-panel {
                min-width: unset;
            }
            .container {
                padding: 20px;
                margin: 20px;
            }
        }
        @media (max-width: 600px) {
            .header h1 {
                font-size: 2.5rem;
            }
            .hero-content h1 {
                font-size: 3rem;
            }
            .hero-content p {
                font-size: 1.1rem;
            }
            .language-tabs {
                flex-direction: column;
            }
            .language-tab {
                width: 100%;
                text-align: center;
                justify-content: center;
            }
            .chatbot-container, .chatbot-toggle-button {
                bottom: 15px;
                right: 15px;
            }
            .chatbot-container {
                width: 90%;
                height: 60vh;
                left: 5%;
                right: 5%;
            }
        }
    </style>
</head>
<body class="dark">
<div class="welcome-screen" id="welcomeScreen">
    <div class="wavy-grid-bg"></div>
    <div class="cubes-container">
        <div class="cube">
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
        </div>
        <div class="cube">
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
        </div>
        <div class="cube">
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
        </div>
        <div class="cube">
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
        </div>
        <div class="cube">
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
            <div class="cube-face"></div>
        </div>
    </div>
    <div class="floating-icons">
        <i class="fas fa-bug floating-icon icon-1"></i>
        <i class="fas fa-code floating-icon icon-2"></i>
        <i class="fas fa-microchip floating-icon icon-3"></i>
        <i class="fab fa-python floating-icon icon-4"></i>
        <i class="fas fa-magic floating-icon icon-5"></i>
    </div>
    <div class="hero-content">
        <h1>AI Code Debugger</h1>
        <p>
            An AI-powered platform that writes, debugs, and executes code.
        </p>
        <div class="hero-btn-group">
            <button class="hero-btn" onclick="showDebugger()">Get Started</button>
        </div>
    </div>
</div>
<div class="container" id="debuggerContainer" style="display: {{ 'block' if code or result or explanation or output else 'none' }};">
    <div class="header">
        <h1>AI Code Debugger</h1>
        <p>Fix and run Python, Java, Arduino, Verilog, SystemVerilog, JS, TS, HTML, and CSS code with AI</p>
        <button id="theme-toggle" class="theme-toggle-button">
            <i class="fas fa-sun"></i>
        </button>
    </div>
    <div class="language-tabs">
        <div class="language-tab" onclick="switchLanguage('python')"><i class="fab fa-python"></i> Python</div>
        <div class="language-tab" onclick="switchLanguage('java')"><i class="fab fa-java"></i> Java</div>
        <div class="language-tab" onclick="switchLanguage('cpp')"><i class="fas fa-cogs"></i> C++</div>
        <div class="language-tab" onclick="switchLanguage('go')"><i class="fab fa-go"></i> Go</div>
        <div class="language-tab" onclick="switchLanguage('rust')"><i class="fab fa-rust"></i> Rust</div>
        <div class="language-tab" onclick="switchLanguage('ruby')"><i class="fas fa-gem"></i> Ruby</div>
        <div class="language-tab" onclick="switchLanguage('kotlin')"><i class="fab fa-sketch"></i> Kotlin</div>
        <div class="language-tab" onclick="switchLanguage('javascript')"><i class="fab fa-js-square"></i> JS</div>
        <div class="language-tab" onclick="switchLanguage('typescript')"><i class="fas fa-microchip"></i> TS</div>
        <div class="language-tab" onclick="switchLanguage('html')"><i class="fab fa-html5"></i> HTML</div>
        <div class="language-tab" onclick="switchLanguage('css')"><i class="fab fa-css3-alt"></i> CSS</div>
        <div class="language-tab" onclick="switchLanguage('django')"><i class="fas fa-code"></i> Django</div>
        <div class="language-tab" onclick="switchLanguage('react')"><i class="fab fa-react"></i> React</div>
        <div class="language-tab" onclick="switchLanguage('arduino')"><i class="fas fa-microchip"></i> Arduino</div>
        <div class="language-tab" onclick="switchLanguage('verilog')"><i class="fas fa-microchip"></i> Verilog</div>
        <div class="language-tab" onclick="switchLanguage('systemverilog')"><i class="fas fa-microchip"></i> SystemVerilog</div>
        <div class="language-tab" onclick="switchLanguage('uvm')"><i class="fas fa-microchip"></i> UVM</div>
        <div class="language-tab" onclick="switchLanguage('sql')"><i class="fas fa-database"></i> SQL</div>
    </div>
    <form method="post">
        <input type="hidden" name="language" id="languageInput" value="{{ language }}" />
        <input type="hidden" name="code" id="codeInput" />
        <div class="split-view">
            <div class="code-editor">
                <h3>Editor</h3>
                <textarea id="editor">{{ code }}</textarea>
                <div id="javaMainClassContainer" style="display: none;">
                    <input type="text" name="java_main_class" id="javaMainClassInput" value="{{ java_main_class }}" placeholder="Main class name" />
                </div>
                <div id="pythonInputPrompts" style="display: none;">
                    {% for prompt in input_prompts %}
                        <input
                            type="text"
                            name="test_input_{{ loop.index0 }}"
                            value="{{ test_inputs[loop.index0] if test_inputs and loop.index0 < test_inputs|length else '' }}"
                            placeholder="{{ prompt }}"
                        />
                    {% endfor %}
                </div>
                <div class="button-group">
                    <button class="button debug" type="submit" id="debugButton">Debug Code</button>
                    <a href="/download" class="button download">Download</a>
                </div>
            </div>
            <div class="output-panel">
                {% if result %}
                    <h3>Fixed Code</h3>
                    <pre>{{ result }}</pre>
                {% endif %}
                {% if explanation %}
                    <h3>Explanation</h3>
                    <pre>{{ explanation }}</pre>
                {% endif %}
                {% if output %}
                    <h3>Execution Output</h3>
                    <div class="execution-output">{{ output }}</div>
                {% endif %}
            </div>
        </div>
    </form>
</div>
<div class="chatbot-container" id="chatbotContainer">
    <div class="chatbot-header" id="chatbotHeader">
        <i class="fas fa-robot"></i> AI Chatbot
        <button class="close-btn" onclick="toggleChatbot()">&#x2715;</button>
    </div>
    <div class="chatbot-messages" id="chatbotMessages">
        <div class="message bot-message">Hello! How can I assist you today?</div>
        <div class="message bot-message">Try asking: 'What is the sum of 5 and 3?' or 'Tell me a fun fact about space.'</div>
    </div>
    <div class="image-preview-container" id="imagePreviewContainer" style="display: none;">
        <img id="imagePreview" src="" alt="Image Preview" class="image-preview" />
        <button class="remove-image-btn" id="removeImageBtn">&times;</button>
    </div>
    <div class="chatbot-input">
        <label for="imageUpload" class="image-upload-label" id="imageUploadLabel">
            <i class="fas fa-image"></i>
        </label>
        <input type="file" id="imageUpload" accept="image/*" style="display: none;" />
        <input type="text" id="chatInput" placeholder="Type your message..." />
        <button id="sendChatBtn"><i class="fas fa-paper-plane"></i></button>
    </div>
</div>
<button class="chatbot-toggle-button {{ 'hidden' if not code and not result and not explanation and not output else '' }}" id="chatbotToggleButton" onclick="toggleChatbot()">
    <i class="fas fa-comment-dots"></i>
</button>
<script>
    const languageMode = {
        python: "python",
        java: "text/x-java",
        cpp: "text/x-c++src",
        go: "go",
        rust: "rust",
        ruby: "ruby",
        kotlin: "text/x-java",
        javascript: "javascript",
        typescript: "javascript",
        html: "text/html",
        css: "text/css",
        django: "python",
        react: "javascript",
        arduino: "text/x-c++src",
        verilog: "verilog",
        systemverilog: "verilog",
        uvm: "verilog",
        sql: "text/x-sql",
    };
    let editorInstance;
    let currentLanguage;
    let debugForm;
    let debugButton;
    let javaMainClassContainer;
    let pythonInputPromptsContainer;
    let chatbotContainer;
    let chatbotToggleButton;
    let chatInput;
    let sendChatBtn;
    let chatbotMessages;
    let debuggerContainer;
    let languageTabs;
    let themeToggleButton;
    let imageUpload;
    let imagePreviewContainer;
    let imagePreview;
    let removeImageBtn;
    let selectedImageFile = null;
    function initializeElements() {
        debugForm = document.querySelector("form");
        debugButton = document.getElementById("debugButton");
        javaMainClassContainer = document.getElementById('javaMainClassContainer');
        pythonInputPromptsContainer = document.getElementById('pythonInputPrompts');
        chatbotContainer = document.getElementById('chatbotContainer');
        chatbotToggleButton = document.getElementById('chatbotToggleButton');
        chatInput = document.getElementById('chatInput');
        sendChatBtn = document.getElementById('sendChatBtn');
        chatbotMessages = document.getElementById('chatbotMessages');
        debuggerContainer = document.getElementById('debuggerContainer');
        languageTabs = document.querySelectorAll(".language-tab");
        themeToggleButton = document.getElementById('theme-toggle');
        imageUpload = document.getElementById('imageUpload');
        imagePreviewContainer = document.getElementById('imagePreviewContainer');
        imagePreview = document.getElementById('imagePreview');
        removeImageBtn = document.getElementById('removeImageBtn');
    }
    function initializeCodeMirror(initialLanguage, initialCode) {
        console.log("Initializing CodeMirror with mode:", initialLanguage);
        const editorTextArea = document.getElementById("editor");
        if (editorTextArea) {
            editorInstance = CodeMirror.fromTextArea(editorTextArea, {
                lineNumbers: true,
                mode: languageMode[initialLanguage],
                theme: "default",
                matchBrackets: true,
                autoCloseBrackets: true,
                value: initialCode
            });
            editorInstance.refresh();
            console.log("CodeMirror instance created successfully.");
        } else {
            console.error("CRITICAL ERROR: CodeMirror textarea with ID 'editor' not found. Cannot initialize editor.");
        }
    }
    function switchLanguage(lang) {
        console.log("Attempting to switch language to:", lang);
        languageTabs.forEach((tab) => tab.classList.remove("active"));
        const targetTab = document.querySelector(`.language-tab[onclick*="${lang}"]`);
        if (targetTab) {
            targetTab.classList.add("active");
            console.log(`Active tab class added for '${lang}'.`);
        }
        document.getElementById("languageInput").value = lang;
        currentLanguage = lang;
        if (editorInstance) {
            editorInstance.setOption("mode", languageMode[lang]);
            editorInstance.refresh();
            console.log("CodeMirror mode successfully set to:", languageMode[lang]);
        } else {
            console.warn("CodeMirror instance is not available. Cannot set mode.");
        }
        if (javaMainClassContainer) {
            javaMainClassContainer.style.display = (lang === 'java' || lang === 'kotlin') ? 'block' : 'none';
        }
        if (pythonInputPromptsContainer) {
            const showPythonPrompts = ['python', 'django'].includes(lang);
            pythonInputPromptsContainer.style.display = showPythonPrompts ? 'block' : 'none';
        }
        updateChatbotVisibility(true);
    }
    function showDebugger() {
        console.log("showDebugger() called.");
        const welcomeScreen = document.getElementById("welcomeScreen");
        if (welcomeScreen) welcomeScreen.style.display = "none";
        if (debuggerContainer) debuggerContainer.style.display = "block";
        updateChatbotVisibility(true);
    }
    function updateChatbotVisibility(visible) {
        if (chatbotToggleButton) {
            if (visible) {
                chatbotToggleButton.classList.remove('hidden');
                chatbotToggleButton.style.display = 'flex';
            } else {
                chatbotToggleButton.classList.add('hidden');
                chatbotToggleButton.style.display = 'none';
            }
        }
    }
    function toggleChatbot() {
        console.log("toggleChatbot() called.");
        if (chatbotContainer && chatbotToggleButton) {
            const isActive = chatbotContainer.classList.toggle('active');
            chatbotToggleButton.style.display = isActive ? 'none' : 'flex';
            if (isActive) {
                if (chatbotMessages) {
                    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
                }
                if (chatInput) {
                    chatInput.focus();
                }
                console.log("Chatbot opened.");
            } else {
                console.log("Chatbot closed.");
            }
        } else {
            console.error("Chatbot elements not found.");
        }
    }
    async function sendMessage() {
        if (!chatInput || !chatbotMessages || !sendChatBtn) {
            console.error("Chatbot input elements not found.");
            return;
        }
        const userMessage = chatInput.value.trim();
        if (userMessage === '' && !selectedImageFile) return;
        const userMessageDiv = document.createElement('div');
        userMessageDiv.classList.add('message', 'user-message');
        if (userMessage) {
            userMessageDiv.textContent = userMessage;
        }
        if (selectedImageFile) {
            const imgElement = document.createElement('img');
            imgElement.src = URL.createObjectURL(selectedImageFile);
            imgElement.alt = "User provided image";
            userMessageDiv.appendChild(imgElement);
        }
        chatbotMessages.appendChild(userMessageDiv);
        chatInput.value = '';
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        const typingIndicatorDiv = document.createElement('div');
        typingIndicatorDiv.classList.add('typing-indicator', 'bot-message');
        typingIndicatorDiv.innerHTML = '<span></span><span></span><span></span>';
        chatbotMessages.appendChild(typingIndicatorDiv);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        sendChatBtn.disabled = true;
        const formData = new FormData();
        formData.append('message', userMessage);
        if (selectedImageFile) {
            formData.append('image', selectedImageFile);
        }
        try {
            const response = await fetch('/send_chat_message', {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) {
                if (response.status === 429) {
                    throw new Error('Quota exceeded. Please wait a moment and try again.');
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (chatbotMessages.contains(typingIndicatorDiv)) {
                chatbotMessages.removeChild(typingIndicatorDiv);
            }
            const botMessageDiv = document.createElement('div');
            botMessageDiv.classList.add('message', 'bot-message');
            botMessageDiv.textContent = data.response;
            chatbotMessages.appendChild(botMessageDiv);
            chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        } catch (error) {
            console.error('Error sending message:', error);
            if (chatbotMessages.contains(typingIndicatorDiv)) {
                 chatbotMessages.removeChild(typingIndicatorDiv);
            }
            const errorMessageDiv = document.createElement('div');
            errorMessageDiv.classList.add('message', 'bot-message');
            errorMessageDiv.textContent = `Error: ${error.message || 'Could not get a response. Please try again.'}`;
            chatbotMessages.appendChild(errorMessageDiv);
            chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        } finally {
            sendChatBtn.disabled = false;
            chatInput.focus();
            removeImage();
        }
    }
    function removeImage() {
        selectedImageFile = null;
        imageUpload.value = null;
        imagePreview.src = '';
        imagePreviewContainer.style.display = 'none';
    }
    function toggleTheme() {
        const body = document.body;
        const icon = themeToggleButton.querySelector('i');
        if (body.classList.contains('dark')) {
            body.classList.remove('dark');
            body.classList.add('light');
            icon.classList.remove('fa-sun');
            icon.classList.add('fa-moon');
            localStorage.setItem('theme', 'light');
        } else {
            body.classList.remove('light');
            body.classList.add('dark');
            icon.classList.remove('fa-moon');
            icon.classList.add('fa-sun');
            localStorage.setItem('theme', 'dark');
        }
    }
    function initializeTheme() {
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        const body = document.body;
        const icon = themeToggleButton.querySelector('i');
        if (savedTheme) {
            body.classList.add(savedTheme);
            if (savedTheme === 'light') {
                icon.classList.remove('fa-sun');
                icon.classList.add('fa-moon');
            }
        } else if (prefersDark) {
            body.classList.add('dark');
        } else {
            body.classList.add('light');
            icon.classList.remove('fa-sun');
            icon.classList.add('fa-moon');
        }
    }
    document.addEventListener('DOMContentLoaded', function () {
        console.log("DOMContentLoaded fired.");
        initializeElements();
        initializeTheme();
        const initialLanguage = "{{ language }}";
        const initialCode = `{{ code | js_string }}`;
        if (document.getElementById("editor")) {
            initializeCodeMirror(initialLanguage, initialCode);
            switchLanguage(initialLanguage);
        } else {
            console.warn("Editor element not found. Skipping CodeMirror initialization.");
        }
        if (debugForm) {
            debugForm.addEventListener("submit", function (event) {
                if (debugButton) {
                    debugButton.classList.add('loading');
                    debugButton.innerHTML = 'Processing... <span class="spinner"></span>';
                    debugButton.disabled = true;
                }
                if (editorInstance) {
                    document.getElementById("codeInput").value = editorInstance.getValue();
                }
            });
        }
        if (languageTabs) {
            languageTabs.forEach(tab => {
                const lang = tab.getAttribute('onclick').match(/'([^']+)'/)[1];
                tab.addEventListener('click', () => switchLanguage(lang));
            });
        }
        if (sendChatBtn && chatInput) {
            sendChatBtn.addEventListener('click', sendMessage);
            chatInput.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
        }
        if (themeToggleButton) {
            themeToggleButton.addEventListener('click', toggleTheme);
        }
        if (imageUpload) {
            imageUpload.addEventListener('change', function(e) {
                const file = e.target.files[0];
                if (file) {
                    selectedImageFile = file;
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        imagePreview.src = event.target.result;
                        imagePreviewContainer.style.display = 'flex';
                        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
                    };
                    reader.readAsDataURL(file);
                }
            });
        }
        if (removeImageBtn) {
            removeImageBtn.addEventListener('click', removeImage);
        }
        if (debugButton) {
            debugButton.classList.remove('loading');
            debugButton.innerHTML = 'Debug Code';
            debugButton.disabled = false;
        }
        if (document.getElementById('debuggerContainer').style.display !== 'none') {
            updateChatbotVisibility(true);
        } else {
            updateChatbotVisibility(false);
        }
    });
</script>
</body>
</html>
"""

def _gemini_api_call_with_retries(func, *args, max_retries=5, initial_delay=1, **kwargs):
    delay = initial_delay
    for i in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Attempt {i+1}/{max_retries} failed: {e}. Retrying in {delay:.2f} seconds...")
            time.sleep(delay)
            delay *= 2
    raise Exception(f"Failed after {max_retries} retries.")

def preprocess_code(code):
    code = re.sub(r'```(python|java|cpp|go|rust|ruby|kotlin|arduino|verilog|systemverilog|uvm|javascript|typescript|html|css|django|react|sql)\s*', '', code, flags=re.IGNORECASE)
    code = code.replace("```", "")
    code = code.replace("\t", "    ")
    code = re.sub(r'[^\x00-\x7F]+', '', code)
    code = re.sub(r'^\s*\.\.\..*$', '', code, flags=re.MULTILINE)
    return code.strip()

def get_input_prompts(code):
    prompts = []
    matches = list(re.finditer(r'input\s*\((.*?)\)', code))
    for match in matches:
        try:
            prompt = match.group(1).strip().strip('"\'') or "Enter value"
        except:
            prompt = "Enter value"
        prompts.append(prompt)
    return prompts

def requires_test_input(code):
    patterns = [r'input\s*\(', r'int\s*\(\s*input\s*\(', r'float\s*\(\s*input\s*\(']
    return any(re.search(p, code) for p in patterns)

def fix_code_with_gemini(code, language):
    global fixed_code_result, explanation_text
    try:
        model = genai.GenerativeModel("gemini-1.5-flash",
                                     safety_settings={
                                         HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                                         HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                                         HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                                         HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                                     })
        chat = model.start_chat()
        prompt = ""
        if language == "java":
            class_match = re.search(r'public\s+class\s+(\w+)', code)
            main_class = class_match.group(1) if class_match else "Main"
            prompt = f"""Fix this Java code:
{code}
Requirements:
1. Include main class '{main_class}'
2. Add necessary imports and fix syntax errors.
3. Ensure the code is runnable.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        elif language == "cpp":
            prompt = f"""Fix this C++ code:
{code}
Requirements:
1. Correct syntax and logical errors.
2. Add necessary includes (e.g., #include <iostream>).
3. Ensure the code is runnable.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        elif language == "go":
            prompt = f"""Fix this Go code:
{code}
Requirements:
1. Correct syntax and logical errors.
2. Add necessary imports and ensure proper package structure.
3. Ensure the code is runnable.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        elif language == "rust":
            prompt = f"""Fix this Rust code:
{code}
Requirements:
1. Correct syntax and ownership errors.
2. Add necessary use statements and ensure proper function signatures.
3. Ensure the code is runnable and passes the borrow checker.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        elif language == "ruby":
            prompt = f"""Fix this Ruby code:
{code}
Requirements:
1. Correct syntax and logical errors.
2. Ensure the code is runnable.
3. Provide clear and concise comments where necessary.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        elif language == "kotlin":
            class_match = re.search(r'fun\s+main', code)
            main_class = "MainKt" if class_match else "Main"
            prompt = f"""Fix this Kotlin code:
{code}
Requirements:
1. Correct syntax and logical errors.
2. Add necessary imports.
3. Ensure the code is runnable, typically with a main function.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        elif language == "arduino":
            prompt = f"""Fix this Arduino code:
{code}
Requirements:
1. Ensure setup() and loop() functions are correctly defined and present.
2. Fix any syntax errors, logical issues, and add necessary includes (e.g., #include <Arduino.h>).
3. Provide clear and concise comments where necessary.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        elif language in ["verilog", "systemverilog", "uvm"]:
            prompt = f"""Fix this {language} code:
{code}
Requirements:
1. Correct syntax errors and logical issues.
2. Ensure proper module/interface/class definition and port/variable declarations.
3. Provide clear and concise comments where necessary.
4. If it's a testbench, ensure it instantiates the DUT correctly and includes initial/always blocks for simulation.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        elif language in ["javascript", "typescript"]:
            prompt = f"""Fix this {language} code. 
{code}
Requirements:
1. Correct syntax or logical errors.
2. Ensure the code is runnable and produces expected output.
3. Provide clear and concise comments where necessary.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        elif language in ["html", "css", "react", "django"]:
            prompt = f"""Fix this {language} code.
{code}
Requirements:
1. Correct syntax or logical errors.
2. Ensure the code is well-structured and follows best practices.
3. For React and Django, provide a runnable code snippet, but mention that a full project setup is required for real-world use.
4. For HTML and CSS, provide a complete, well-formed code snippet.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        elif language == "sql":
            prompt = f"""Analyze and fix this SQL code.
{code}
Requirements:
1. Fix any syntax errors.
2. Suggest improvements for performance or clarity.
3. Provide the corrected, runnable query or schema.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        else: # Default to Python
            prompt = f"""Fix this Python code:
{code}
Requirements:
1. Correct syntax or logical errors.
2. Do not convert string to int unless explicitly necessary for the logic.
3. Preserve operations like string multiplication (e.g., 'a' * 3).
4. Ensure the code is runnable and produces expected output if inputs are provided.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""
        response = _gemini_api_call_with_retries(chat.send_message, prompt)
        full = response.text.strip()
        if '---EXPLANATION---' in full:
            fixed_code_result, explanation_text = map(str.strip, full.split('---EXPLANATION---', 1))
        else:
            fixed_code_result = full
            explanation_text = "Explanation not provided by AI."
    except Exception as e:
        fixed_code_result = f"❌ Error contacting AI: {str(e)}"
        explanation_text = "Could not generate explanation due to an error or repeated API failures."

def execute_python_code(code, test_inputs):
    inputs = re.findall(r'input\s*\(.*?\)', code)
    if test_inputs and len(test_inputs) < len(inputs):
        return f"❌ Not enough test inputs (expected {len(inputs)})"
    for i, call in enumerate(inputs):
        if i < len(test_inputs):
            code = code.replace(call, repr(test_inputs[i]), 1)
        else:
            code = code.replace(call, "''", 1)
    old_stdout = sys.stdout
    sys.stdout = captured = io.StringIO()
    try:
        exec(code, {})
        return captured.getvalue().strip() or "✅ Ran successfully."
    finally:
        sys.stdout = old_stdout

def execute_java_code(code, main_class):
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, f"{main_class}.java")
    try:
        with open(file_path, 'w') as f:
            f.write(code)
        compile_command = ['javac', file_path]
        compile = subprocess.run(compile_command, cwd=temp_dir, capture_output=True, text=True, timeout=15)
        if compile.returncode != 0:
            return f"❌ Compilation Error:\n{compile.stderr}"
        run_command = ['java', '-cp', temp_dir, main_class]
        run = subprocess.run(run_command, capture_output=True, text=True, timeout=10)
        if run.returncode != 0:
            return f"❌ Runtime Error:\n{run.stderr}"
        return run.stdout or "✅ Ran successfully, no output."
    except subprocess.TimeoutExpired:
        return "❌ Execution timed out."
    except Exception as e:
        return f"❌ Execution error: {str(e)}"
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error during Java cleanup: {e}")

def execute_cpp_code(code):
    temp_dir = tempfile.mkdtemp()
    source_path = os.path.join(temp_dir, "main.cpp")
    executable_path = os.path.join(temp_dir, "main")
    try:
        with open(source_path, 'w') as f:
            f.write(code)
        compile_command = ['g++', source_path, '-o', executable_path]
        compile_result = subprocess.run(compile_command, cwd=temp_dir, capture_output=True, text=True, timeout=15)
        if compile_result.returncode != 0:
            return f"❌ Compilation Error:\n{compile_result.stderr}"
        run_command = [executable_path]
        run_result = subprocess.run(run_command, cwd=temp_dir, capture_output=True, text=True, timeout=10)
        if run_result.returncode != 0:
            return f"❌ Runtime Error:\n{run_result.stderr}"
        return run_result.stdout or "✅ Ran successfully, no output."
    except subprocess.TimeoutExpired:
        return "❌ Execution timed out."
    except Exception as e:
        return f"❌ Execution error: {str(e)}"
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error during C++ cleanup: {e}")

def execute_go_code(code):
    temp_dir = tempfile.mkdtemp()
    source_path = os.path.join(temp_dir, "main.go")
    try:
        with open(source_path, 'w') as f:
            f.write(code)
        run_command = ['go', 'run', source_path]
        run_result = subprocess.run(run_command, cwd=temp_dir, capture_output=True, text=True, timeout=15)
        if run_result.returncode != 0:
            return f"❌ Runtime Error:\n{run_result.stderr}"
        return run_result.stdout or "✅ Ran successfully, no output."
    except subprocess.TimeoutExpired:
        return "❌ Execution timed out."
    except Exception as e:
        return f"❌ Execution error: {str(e)}"
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error during Go cleanup: {e}")

def execute_rust_code(code):
    temp_dir = tempfile.mkdtemp()
    source_path = os.path.join(temp_dir, "main.rs")
    executable_path = os.path.join(temp_dir, "main")
    try:
        with open(source_path, 'w') as f:
            f.write(code)
        compile_command = ['rustc', source_path, '-o', executable_path]
        compile_result = subprocess.run(compile_command, cwd=temp_dir, capture_output=True, text=True, timeout=15)
        if compile_result.returncode != 0:
            return f"❌ Compilation Error:\n{compile_result.stderr}"
        run_command = [executable_path]
        run_result = subprocess.run(run_command, cwd=temp_dir, capture_output=True, text=True, timeout=10)
        if run_result.returncode != 0:
            return f"❌ Runtime Error:\n{run_result.stderr}"
        return run_result.stdout or "✅ Ran successfully, no output."
    except subprocess.TimeoutExpired:
        return "❌ Execution timed out."
    except Exception as e:
        return f"❌ Execution error: {str(e)}"
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error during Rust cleanup: {e}")

def execute_ruby_code(code):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".rb", mode='w')
    temp_file.write(code)
    temp_file.close()
    try:
        run_command = ['ruby', temp_file.name]
        run_result = subprocess.run(run_command, capture_output=True, text=True, timeout=10)
        if run_result.returncode != 0:
            return f"❌ Runtime Error:\n{run_result.stderr}"
        return run_result.stdout or "✅ Ran successfully, no output."
    except FileNotFoundError:
        return "❌ Error: Ruby interpreter is not installed or not in your system's PATH."
    except subprocess.TimeoutExpired:
        return "❌ Execution timed out."
    except Exception as e:
        return f"❌ Execution error: {str(e)}"
    finally:
        os.remove(temp_file.name)

def execute_kotlin_code(code, main_class):
    temp_dir = tempfile.mkdtemp()
    source_path = os.path.join(temp_dir, f"{main_class}.kt")
    output_jar = os.path.join(temp_dir, f"{main_class}.jar")
    try:
        with open(source_path, 'w') as f:
            f.write(code)
        compile_command = ['kotlinc', source_path, '-include-runtime', '-d', output_jar]
        compile_result = subprocess.run(compile_command, cwd=temp_dir, capture_output=True, text=True, timeout=15)
        if compile_result.returncode != 0:
            return f"❌ Compilation Error:\n{compile_result.stderr}"
        run_command = ['java', '-jar', output_jar]
        run_result = subprocess.run(run_command, cwd=temp_dir, capture_output=True, text=True, timeout=10)
        if run_result.returncode != 0:
            return f"❌ Runtime Error:\n{run_result.stderr}"
        return run_result.stdout or "✅ Ran successfully, no output."
    except subprocess.TimeoutExpired:
        return "❌ Execution timed out."
    except Exception as e:
        return f"❌ Execution error: {str(e)}"
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error during Kotlin cleanup: {e}")

def execute_arduino_code(code):
    temp_dir = tempfile.mkdtemp()
    sketch_dir = os.path.join(temp_dir, "sketch")
    os.makedirs(sketch_dir)
    sketch_file = os.path.join(sketch_dir, "sketch.ino")
    try:
        with open(sketch_file, 'w') as f:
            f.write(code)
        compile_command = ['arduino-cli', 'compile', '--fqbn', 'arduino:avr:uno', sketch_dir]
        compile = subprocess.run(compile_command, capture_output=True, text=True, timeout=30)
        if compile.returncode != 0:
            return f"❌ Compilation Error (Arduino CLI):\n{compile.stderr}"
        return "✅ Arduino code compiled successfully."
    except subprocess.TimeoutExpired:
        return "❌ Arduino compilation timed out."
    except Exception as e:
        return f"❌ Error during Arduino compilation: {str(e)}"
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error during Arduino cleanup: {e}")

def execute_verilog_code(code, language):
    temp_dir = tempfile.mkdtemp()
    file_extension = ".v" if language in ["verilog"] else ".sv"
    file_path = os.path.join(temp_dir, f"design{file_extension}")
    output_vvp = os.path.join(temp_dir, "a.out")
    try:
        with open(file_path, 'w') as f:
            f.write(code)
        compile_command = ['iverilog', '-o', output_vvp, file_path]
        compile_result = subprocess.run(compile_command, cwd=temp_dir, capture_output=True, text=True, timeout=15)
        if compile_result.returncode != 0:
            return f"❌ Compilation Error:\n{compile_result.stderr}"
        if "initial begin" in code or "always_ff" in code or "always_comb" in code or "program " in code:
            run_command = ['vvp', output_vvp]
            run_result = subprocess.run(run_command, cwd=temp_dir, capture_output=True, text=True, timeout=15)
            if run_result.returncode != 0:
                return f"❌ Runtime Error (Simulation):\n{run_result.stderr}"
            return run_result.stdout or "✅ Verilog/SystemVerilog/UVM compiled and ran successfully (no output to display)."
        else:
            return "✅ Verilog/SystemVerilog/UVM compiled successfully (no testbench found for simulation)."
    except subprocess.TimeoutExpired:
        return "❌ Execution timed out."
    except Exception as e:
        return f"❌ Error: {str(e)}"
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error during Verilog cleanup: {e}")

def execute_javascript_code(code):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".js", mode='w')
    temp_file.write(code)
    temp_file.close()
    try:
        run_command = ['node', temp_file.name]
        run_result = subprocess.run(run_command, capture_output=True, text=True, timeout=10)
        if run_result.returncode != 0:
            return f"❌ Runtime Error:\n{run_result.stderr}"
        return run_result.stdout or "✅ Ran successfully, no output."
    except FileNotFoundError:
        return "❌ Error: Node.js is not installed or not in your system's PATH. Please install it to execute JavaScript code."
    except subprocess.TimeoutExpired:
        return "❌ Execution timed out."
    except Exception as e:
        return f"❌ Execution error: {str(e)}"
    finally:
        os.remove(temp_file.name)

def execute_typescript_code(code):
    temp_ts_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ts", mode='w')
    temp_ts_file.write(code)
    temp_ts_file.close()
    
    temp_js_file_path = temp_ts_file.name.replace(".ts", ".js")
    
    try:
        compile_command = ['tsc', '--outFile', temp_js_file_path, temp_ts_file.name]
        compile_result = subprocess.run(compile_command, capture_output=True, text=True, timeout=15)
        
        if compile_result.returncode != 0:
            return f"❌ Compilation Error:\n{compile_result.stderr}"
        
        run_command = ['node', temp_js_file_path]
        run_result = subprocess.run(run_command, capture_output=True, text=True, timeout=10)
        
        if run_result.returncode != 0:
            return f"❌ Runtime Error:\n{run_result.stderr}"
            
        return run_result.stdout or "✅ Ran successfully, no output."
        
    except FileNotFoundError as e:
        if 'tsc' in str(e):
            return "❌ Error: TypeScript compiler ('tsc') is not installed. Please install it globally via `npm install -g typescript`."
        elif 'node' in str(e):
            return "❌ Error: Node.js is not installed. Please install it to execute TypeScript code."
        else:
            return f"❌ Execution Error: {str(e)}"
    except subprocess.TimeoutExpired:
        return "❌ Execution timed out."
    except Exception as e:
        return f"❌ Execution error: {str(e)}"
    finally:
        os.remove(temp_ts_file.name)
        if os.path.exists(temp_js_file_path):
            os.remove(temp_js_file_path)

def execute_sql_code(code):
    output = []
    queries = [q.strip() for q in code.split(';') if q.strip()]
    if not queries:
        return "✅ Ran successfully, no output."
    conn = None
    try:
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        for query in queries:
            if not query.strip():
                continue
            output.append(f"Executing query: {query}")
            try:
                cursor.execute(query)
                conn.commit()
                if query.lower().startswith('select'):
                    rows = cursor.fetchall()
                    if rows:
                        headers = [desc[0] for desc in cursor.description]
                        output.append("--- Results ---")
                        output.append(" | ".join(headers))
                        output.append("-" * len(" | ".join(headers)))
                        for row in rows:
                            output.append(" | ".join(map(str, row)))
                        output.append("---------------")
                    else:
                        output.append("✅ Query executed successfully, no rows returned.")
                else:
                    output.append("✅ Statement executed successfully.")
            except sqlite3.Error as e:
                output.append(f"❌ SQL Error: {e}")
                break
    except Exception as e:
        return f"❌ An unexpected error occurred: {str(e)}"
    finally:
        if conn:
            conn.close()
    return "\n".join(output)

def validate_and_execute_code(code, language, test_inputs=None, java_main_class=None):
    try:
        code = preprocess_code(code)
        if language == "python":
            return execute_python_code(code, test_inputs)
        elif language == "java":
            return execute_java_code(code, java_main_class)
        elif language == "cpp":
            return execute_cpp_code(code)
        elif language == "go":
            return execute_go_code(code)
        elif language == "rust":
            return execute_rust_code(code)
        elif language == "ruby":
            return execute_ruby_code(code)
        elif language == "kotlin":
            class_match = re.search(r'fun\s+main', code)
            main_class = "MainKt" if class_match else "Main"
            return execute_kotlin_code(code, main_class)
        elif language == "arduino":
            return execute_arduino_code(code)
        elif language in ["verilog", "systemverilog", "uvm"]:
            return execute_verilog_code(code, language)
        elif language == "javascript":
            return execute_javascript_code(code)
        elif language == "typescript":
            return execute_typescript_code(code)
        elif language == "sql":
            return execute_sql_code(code)
        elif language in ["html", "css", "django", "react"]:
            if language in ["django", "react"]:
                return f"✅ Code fixed successfully. Note: {language.capitalize()} requires a full project setup to run. The AI has provided the corrected snippet."
            else:
                return f"✅ Code fixed successfully. To see this {language.upper()} code in action, you need to open it in a web browser. The execution panel shows the raw, corrected code."
    except Exception as e:
        return f"❌ Execution failed: {str(e)}"

@app.route("/", methods=["GET", "POST"])
def index():
    global fixed_code_result, explanation_text
    code = ""
    result = ""
    explanation = ""
    output = ""
    test_inputs = []
    input_prompts = []
    java_main_class = "Main"
    language = "python"
    if request.method == "POST":
        language = request.form.get("language", "python")
        code = request.form.get("code", "")
        java_main_class = request.form.get("java_main_class", "Main")
        if language == "python":
            input_prompts = get_input_prompts(code)
            if requires_test_input(code):
                for i in range(len(input_prompts)):
                    input_value = request.form.get(f"test_input_{i}", "")
                    test_inputs.append(input_value)
        fix_code_with_gemini(code, language)
        result = fixed_code_result
        explanation = explanation_text
        output = validate_and_execute_code(result, language, test_inputs, java_main_class)
    return render_template_string(
        HTML_TEMPLATE,
        code=code,
        result=result,
        explanation=explanation,
        output=output,
        language=language,
        input_prompts=input_prompts,
        test_inputs=test_inputs,
        java_main_class=java_main_class,
    )

@app.route("/download")
def download():
    global fixed_code_result
    ext = ".txt"
    if "void setup()" in fixed_code_result or "void loop()" in fixed_code_result:
        ext = ".ino"
    elif "public class" in fixed_code_result:
        ext = ".java"
    elif "func main()" in fixed_code_result:
        ext = ".go"
    elif "fn main()" in fixed_code_result:
        ext = ".rs"
    elif re.search(r'module\s+', fixed_code_result, re.IGNORECASE) or re.search(r'class\s+extends\s+uvm', fixed_code_result, re.IGNORECASE):
        if "logic" in fixed_code_result or "interface" in fixed_code_result or "class " in fixed_code_result:
            ext = ".sv"
        else:
            ext = ".v"
    elif fixed_code_result.strip().startswith('<!DOCTYPE html>'):
        ext = ".html"
    elif re.search(r'selector\s*\{', fixed_code_result):
        ext = ".css"
    elif "import React" in fixed_code_result:
        ext = ".jsx"
    elif "from django.db import models" in fixed_code_result:
        ext = ".py"
    elif fixed_code_result.strip().startswith('import React') or "function" in fixed_code_result or "const" in fixed_code_result:
        ext = ".js"
    elif "let" in fixed_code_result or "const" in fixed_code_result or "function" in fixed_code_result:
        ext = ".ts"
    elif re.search(r'(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP)\s+', fixed_code_result, re.IGNORECASE):
        ext = ".sql"
    else:
        ext = ".py"

    response = make_response(fixed_code_result)
    response.headers["Content-Disposition"] = f"attachment; filename=debugged_code{ext}"
    response.mimetype = "text/plain"
    return response

@app.route("/send_chat_message", methods=["POST"])
def send_chat_message():
    user_message = request.form.get("message")
    uploaded_image = request.files.get("image")
    
    if not user_message and not uploaded_image:
        return jsonify({"response": "Error: No message or image provided."}), 400

    try:
        model = genai.GenerativeModel("gemini-1.5-flash",
                                     safety_settings={
                                         HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                                         HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                                         HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                                         HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                                     })

        parts = []
        if user_message:
            parts.append(user_message)
        
        if uploaded_image:
            image_data = uploaded_image.read()
            img = Image.open(io.BytesIO(image_data))
            parts.append(img)

        response = _gemini_api_call_with_retries(model.generate_content, parts)
        ai_response = response.text

        return jsonify({"response": ai_response})
    except Exception as e:
        print(f"Error in AI chat response: {e}")
        return jsonify({"response": f"I'm sorry, I couldn't process that. Please try again. ({e})"}), 500

if __name__ == "__main__":
    print("Checking for external tools:")
    try:
        subprocess.run(['java', '-version'], capture_output=True, text=True, check=True)
        print("✅ Java is installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ Java not found. Java/Kotlin execution will not work.")
    try:
        subprocess.run(['kotlinc', '-version'], capture_output=True, text=True, check=True)
        print("✅ Kotlin is installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ Kotlin not found. Kotlin compilation will not work.")
    try:
        subprocess.run(['g++', '--version'], capture_output=True, text=True, check=True)
        print("✅ g++ is installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ g++ not found. C++ compilation will not work.")
    try:
        subprocess.run(['go', 'version'], capture_output=True, text=True, check=True)
        print("✅ Go is installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ Go not found. Go execution will not work.")
    try:
        subprocess.run(['rustc', '--version'], capture_output=True, text=True, check=True)
        print("✅ Rust is installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ Rust not found. Rust compilation will not work.")
    try:
        subprocess.run(['ruby', '-v'], capture_output=True, text=True, check=True)
        print("✅ Ruby is installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ Ruby not found. Ruby execution will not work.")
    try:
        subprocess.run(['arduino-cli', 'version'], capture_output=True, text=True, check=True)
        print("✅ Arduino CLI is installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ Arduino CLI not found. Arduino compilation will not work.")
    try:
        subprocess.run(['iverilog', '-v'], capture_output=True, text=True, check=True)
        print("✅ Icarus Verilog is installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ Icarus Verilog not found. Verilog/SystemVerilog/UVM compilation will not work.")
    try:
        subprocess.run(['node', '-v'], capture_output=True, text=True, check=True)
        print("✅ Node.js is installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ Node.js not found. JavaScript/TypeScript execution will not work.")
    try:
        subprocess.run(['tsc', '-v'], capture_output=True, text=True, check=True)
        print("✅ TypeScript compiler (tsc) is installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ TypeScript compiler (tsc) not found. TypeScript compilation will not work.")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
