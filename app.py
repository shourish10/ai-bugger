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

load_dotenv()
app = Flask(__name__)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/javascript/javascript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/xml/xml.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/css/css.min.js"></script>
    <style>
        /* General Body and Container Styles */
        body {
            margin: 0;
            font-family: 'Fira Sans', sans-serif;
            background: #15151e;
            color: #fff;
            background-repeat: repeat;
        }

        /* ------------- WELCOME PAGE ------------ */
        .welcome-screen {
            display: {{ 'none' if code or result or explanation or output else 'flex' }};
            height: 100vh;
            width: 100vw;
            background: radial-gradient(circle at 20% 30%,#7fdfff77 0%, #a7a6ff66 60%, #23233a 100%);
            align-items: center;
            justify-content: center;
            flex-direction: column;
            position: relative;
            overflow: hidden;
            transition: all 0.9s cubic-bezier(.7,0,.3,1);
        }
        .hero-content {
            position: relative;
            z-index: 3;
            text-align: center;
        }
        .hero-content h1 {
            font-size: 5.9rem;
            font-weight: 900;
            color: #000000;
            letter-spacing: 0.02em;
            margin-bottom: 0.6em;
            text-shadow: 0 6px 32px #2637ff40, 0 1px 2px #16edd7, 0 8px 40px #3986fd20;
            font-family: 'Fira Sans', sans-serif;
            text-align: center;
            white-space: nowrap;
            overflow: hidden;
            border-right: .15em solid orange;
            animation: 
              typing 3.5s steps(40, end),
              blink-caret .75s step-end infinite;
        }

        /* Typing effect */
        @keyframes typing {
          from { width: 0 }
          to { width: 100% }
        }

        /* The typewriter cursor effect */
        @keyframes blink-caret {
          from, to { border-color: transparent }
          50% { border-color: orange; }
        }

        .hero-content p {
            color: #cbeefd;
            font-size: 1.3rem;
            max-width: 500px;
            margin: 0 auto 2.5em auto;
            font-weight: 400;
        }
        .hero-btn-group {
            margin-top: 1.7em;
            display: flex;
            justify-content: center;
            gap: 1.3em;
        }
        @keyframes blinkColors {
            0%   { background: linear-gradient(90deg,#6dc6fb 30%, #5affc3 100%); box-shadow: 0 0 18px #54dbff90; }
            20%  { background: linear-gradient(90deg,#f38eff 30%, #ffd96a 100%); box-shadow: 0 0 21px #fd8ecb70; }
            40%  { background: linear-gradient(90deg,#5ac8fa 30%,#54dede 100%); box-shadow: 0 0 18px #1be5c350; }
            60%  { background: linear-gradient(90deg,#a7a6ff 30%,#7fdfff 100%); box-shadow: 0 0 22px #94ffca50;}
            80%  { background: linear-gradient(90deg,#6dc6fb 30%, #5affc3 100%); box-shadow: 0 0 18px #54dbff90; }
            100% { background: linear-gradient(90deg,#6dc6fb 30%, #5affc3 100%); box-shadow: 0 0 18px #54dbff90; }
        }
        .hero-btn {
            font-family: inherit;
            font-size: 1.09rem;
            color: #183050;
            border: none;
            padding: 0.95em 2.3em;
            border-radius: 30px;
            font-weight: 700;
            cursor: pointer;
            outline: none;
            animation: blinkColors 1.35s infinite;
            transition: background 0.2s, color 0.2s, box-shadow 0.2s;
            box-shadow: 0 3px 24px #2cfbe260;
        }
        .hero-btn:hover {
            color: #0d3144;
            filter: brightness(1.1);
        }
        .hero-btn.login {
            background: transparent;
            color: #e2f4fc;
            border: 2px solid #00dfcc66;
            box-shadow: none;
        }
        .hero-btn.login:hover {
            background: #131b3144;
        }
        /* Floating animated icons */
        .floating-icons {
            position: absolute;
            left: 0; top: 0; width: 100%; height: 100%;
            z-index: 1;
            pointer-events: none;
        }
        .floating-icon {
            position: absolute;
            opacity: 0.2;
            font-size: 2.3rem;
            color: #fff;
            filter: blur(0.5px);
            animation: floatIcon 8s ease-in-out infinite;
        }
        .floating-icon.icon-1 { left: 10%;  top: 18%; font-size: 2.4rem; color: #49ffe0; animation-delay: 0s;}
        .floating-icon.icon-2 { left: 80%;  top: 12%; font-size: 3.0rem; color: #ffd96a; animation-delay: 1s;}
        .floating-icon.icon-3 { left: 25%;  top: 70%; font-size: 2.2rem; color: #f38eff; animation-delay: 2.2s;}
        .floating-icon.icon-4 { left: 70%;  top: 75%; font-size: 2rem; color: #b9ff8a; animation-delay: 4s;}
        .floating-icon.icon-5 { left: 50%;  top: 45%; font-size: 2.6rem; color: #a9caff; animation-delay: 1.6s;}
        @keyframes floatIcon {
            0% {transform: translateY(0);}
            50% { transform: translateY(-35px); }
            100% { transform: translateY(0);}
        }
        /* ------------- MODAL ------------ */
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(34,52,70,0.63);
            justify-content: center;
            align-items: center;
            z-index: 2000;
        }
        .modal-content {
            background: #2c2f41;
            padding: 36px 30px 24px 30px;
            border-radius: 13px;
            width: 90%;
            max-width: 430px;
            text-align: center;
            box-shadow: 0 2px 44px #272adc65;
        }
        .modal input {
            display: block;
            width: 100%;
            padding: 11px;
            margin: 15px 0;
            border-radius: 7px;
            border: none;
            background: #293360;
            color: white;
            font-size: 1.07rem;
        }
        .modal button {
            background: #1af0ff;
            color: #0e1935;
            padding: 10px 0;
            width: 100%;
            border: none;
            border-radius: 7px;
            font-weight: 700;
            font-size: 1.08rem;
            cursor: pointer;
            margin-top: 10px;
        }
        /* ------------- DEBUGGER PAGE ------------ */
        .container {
            display: {{ 'block' if code or result or explanation or output else 'none' }};
            max-width: 1400px;
            margin: 40px auto;
            padding: 30px 10px;
            border-radius: 35px;
            background: linear-gradient(110deg, #112230 82%, #292d54 100%);
            box-shadow: 0 8px 48px #0089ff37;
        }
        .header {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        .header h1 {
            font-size: 2.9rem;
            font-weight: 900;
            color: #FFFFFF;
            margin-bottom: 8px;
            text-shadow: 0 3px 15px #54dbff50, 0 1px 5px #0ffbe050;
            font-family: 'Fira Sans', sans-serif;
            letter-spacing: 0.03em;
            text-align: center;
            white-space: nowrap;
            overflow: hidden;
            border-right: .15em solid orange;
            animation: 
              typing 3.5s steps(40, end),
              blink-caret .75s step-end infinite;
        }
        .header p {
            color: #b7edff;
            margin-bottom: 30px;
            text-align: center;
        }
        .language-tabs {
            display: flex;
            gap: 18px;
            margin: 20px 0;
            justify-content: center;
            flex-wrap: wrap; /* Allow tabs to wrap on smaller screens */
        }
        .language-tab {
            padding: 8px 26px;
            border-radius: 10px;
            border: 1.5px solid #2fe6c9;
            background: #202745;
            color: #aaffff;
            font-size: 1.12rem;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.22s;
            display: flex; /* Make icons and text align */
            align-items: center;
            gap: 8px; /* Space between icon and text */
        }
        .language-tab.active {
            background: linear-gradient(90deg,#43effd 30%, #13e7c7 100%);
            color: #113366;
            border-color: #43effd;
            font-weight: 700;
        }
        .split-view {
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
        }
        .code-editor, .output-panel {
            flex: 1;
            min-width: 360px;
            background: #1a2240; /* Consistent background for editor/output panels */
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3); /* Enhanced shadow */
        }
        #editor {
            height: 400px;
            border: 1px solid #334466; /* Border for editor */
            border-radius: 8px; /* Rounded corners for editor */
        }

        /* Codemirror overrides for theme */
        .CodeMirror {
            border: 1px solid #334466;
            border-radius: 8px;
            background: #101329; /* Darker background for code editor */
            color: #bbfcff;
            font-family: 'Source Code Pro', monospace;
            font-size: 1rem;
        }
        .CodeMirror-gutters {
            background: #101329;
            border-right: 1px solid #334466;
        }
        .CodeMirror-linenumber {
            color: #6a7c99;
        }
        .CodeMirror-cursor {
            border-left: 1px solid #fff;
        }
        /* End Codemirror overrides */

        .button-group {
            margin-top: 22px;
            display: flex;
            gap: 12px;
            justify-content: flex-end; /* Align buttons to the right */
        }
        .button {
            padding: 11px 22px;
            background: linear-gradient(90deg,#16edd7 40%,#4874fe 100%);
            color: #fff;
            border: none;
            border-radius: 7px;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 600;
            transition: all 0.3s ease; /* Smooth transition for buttons */
            box-shadow: 0 4px 15px rgba(0,0,0,0.2); /* Button shadow */
        }
        .button:hover {
            background: linear-gradient(90deg,#58e1fe 30%,#1be5c3 100%);
            color: #133944;
            transform: translateY(-2px); /* Slight lift on hover */
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        .button.loading {
            background: linear-gradient(90deg, #666 40%, #999 100%); /* Grey out when loading */
            cursor: not-allowed;
        }
        .button.loading .spinner {
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top: 2px solid #fff;
            border-radius: 50%;
            width: 12px;
            height: 12px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-left: 8px;
            vertical-align: middle;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .execution-output {
            background-color: #101329;
            color: #0fcaca;
            padding: 15px;
            border-radius: 9px;
            box-shadow: 0 0 15px #4bffe367;
            margin-top: 12px;
            font-family: 'Source Code Pro', monospace;
            white-space: pre-wrap; /* Ensure wrapping here too */
            word-wrap: break-word;
            overflow-x: auto;
        }
        pre {
            font-family: 'Source Code Pro', monospace;
            border-radius: 6px;
            background: #101329; /* Darker background for pre tags */
            padding: 13px;
            color: #bbfcff;
            white-space: pre-wrap;   /* Fix: Allows wrapping of long lines */
            word-wrap: break-word;   /* Fix: Breaks words if necessary */
            overflow-x: auto;        /* Fix: Adds horizontal scroll if lines are still too long */
            box-shadow: inset 0 0 8px rgba(0,255,255,0.1); /* Subtle inner glow */
        }

        /* General Input Field Styling */
        input[type="text"] {
            display: block;
            width: calc(100% - 24px); /* Account for padding */
            padding: 10px 12px;
            margin-top: 10px;
            border-radius: 8px;
            border: 1px solid #334466;
            background: #1e253a;
            color: #e0f2f7;
            font-size: 0.95rem;
            font-family: 'Fira Sans', sans-serif;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }

        input[type="text"]::placeholder {
            color: #9bb7c7;
        }

        input[type="text"]:focus {
            border-color: #43effd;
            box-shadow: 0 0 0 2px rgba(67, 239, 253, 0.3);
        }

        /* Headings within panels */
        .code-editor h3, .output-panel h3 {
            color: #fff;
            margin-top: 0;
            margin-bottom: 15px;
            font-weight: 700;
            font-size: 1.4rem;
            border-bottom: 2px solid #334466; /* Underline effect */
            padding-bottom: 8px;
        }
        
        /* Responsive adjustments */
        @media (max-width: 900px) {
            .split-view { flex-direction: column; }
            .code-editor, .output-panel { min-width: unset; width: 100%; }
        }
        @media (max-width: 600px) {
            .welcome-content h1 { font-size: 2.2rem; }
            .welcome-content p { font-size: 1.01rem; }
            .container { margin: 13px 0; padding: 10px 4px; }
            .language-tabs { flex-direction: column; align-items: center; } /* Stack tabs vertically */
        }

        /* Custom scrollbar styles (Webkit browsers) */
        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }

        ::-webkit-scrollbar-track {
            background: #1a2240;
            border-radius: 10px;
        }

        ::-webkit-scrollbar-thumb {
            background: #43effd;
            border-radius: 10px;
            border: 2px solid #1a2240;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #13e7c7;
        }

        /* Chatbot Styles */
        .chatbot-container {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 350px;
            height: 450px;
            background: #202745;
            border-radius: 15px;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            z-index: 1000;
            transform: translateY(100%); /* Start off-screen */
            opacity: 0;
            transition: transform 0.3s ease-out, opacity 0.3s ease-out;
        }
        .chatbot-container.active {
            transform: translateY(0);
            opacity: 1;
        }
        .chatbot-header {
            background: linear-gradient(90deg, #43effd 30%, #13e7c7 100%);
            color: #113366;
            padding: 15px;
            font-size: 1.2rem;
            font-weight: 700;
            border-top-left-radius: 15px;
            border-top-right-radius: 15px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
        }
        .chatbot-header i {
            font-size: 1.5rem;
        }
        .chatbot-header .close-btn {
            background: none;
            border: none;
            color: #113366;
            font-size: 1.5rem;
            cursor: pointer;
            padding: 0 5px;
            transition: transform 0.2s;
        }
        .chatbot-header .close-btn:hover {
            transform: rotate(90deg);
        }
        .chatbot-messages {
            flex-grow: 1;
            padding: 15px;
            overflow-y: auto;
            background-color: #1a2240;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .message {
            max-width: 80%;
            padding: 10px 15px;
            border-radius: 15px;
            font-size: 0.95rem;
            line-height: 1.4;
            word-wrap: break-word;
        }
        .user-message {
            background-color: #007bff;
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 5px;
        }
        .bot-message {
            background-color: #334466;
            color: #e0f2f7;
            align-self: flex-start;
            border-bottom-left-radius: 5px;
        }
        .chatbot-input {
            display: flex;
            padding: 10px 15px;
            border-top: 1px solid #334466;
            background-color: #202745;
        }
        .chatbot-input input {
            flex-grow: 1;
            border: 1px solid #334466;
            border-radius: 20px;
            padding: 10px 15px;
            background-color: #1e253a;
            color: #e0f2f7;
            font-size: 0.95rem;
            margin-top: 0; /* Override default input margin */
            margin-right: 10px;
        }
        .chatbot-input input:focus {
            border-color: #43effd;
            box-shadow: 0 0 0 2px rgba(67, 239, 253, 0.3);
        }
        .chatbot-input button {
            background: linear-gradient(90deg,#16edd7 40%,#4874fe 100%);
            border: none;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: background 0.2s, transform 0.2s;
            box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
            color: white; /* Icon color */
            font-size: 1rem;
            padding: 0; /* Remove default button padding */
            margin-top: 0; /* Override default button margin */
        }
        .chatbot-input button:hover {
            background: linear-gradient(90deg,#58e1fe 30%,#1be5c3 100%);
            transform: translateY(-1px);
        }
        .chatbot-toggle-button {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: linear-gradient(90deg,#43effd 30%, #13e7c7 100%);
            color: #113366;
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
            z-index: 1001; /* Above the chatbot container when hidden */
            transition: transform 0.3s ease-out, opacity 0.3s ease-out;
        }
        .chatbot-toggle-button.hidden {
            opacity: 0;
            pointer-events: none; /* Make it unclickable when hidden */
        }
        .chatbot-toggle-button i {
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        .typing-indicator {
            display: flex;
            gap: 4px;
            padding: 10px 15px;
            border-radius: 15px;
            background-color: #334466;
            color: #e0f2f7;
            align-self: flex-start;
            border-bottom-left-radius: 5px;
            font-size: 0.95rem;
        }
        .typing-indicator span {
            animation: blink 1s infinite;
        }
        .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes blink {
            0%, 100% { opacity: 0.2; }
            50% { opacity: 1; }
        }
        /* Responsive Chatbot */
        @media (max-width: 400px) {
            .chatbot-container {
                width: 90%;
                right: 5%;
                left: 5%;
                height: 70vh; /* Adjust height for smaller screens */
                bottom: 10px;
            }
            .chatbot-toggle-button {
                bottom: 10px;
                right: 10px;
            }
        }
    </style>
</head>
<body>

<div class="welcome-screen" id="welcomeScreen">
    <div class="floating-icons">
        <i class="fas fa-bug floating-icon icon-1"></i>
        <i class="fas fa-code floating-icon icon-2"></i>
        <i class="fas fa-microchip floating-icon icon-3"></i>
        <i class="fab fa-python floating-icon icon-4"></i>
        <i class="fas fa-magic floating-icon icon-5"></i>
    </div>
    <div class="hero-content">
        <h1>AI Code Debugger !! </h1>
        <p>
            An AI-powered platform that writes, debugs, and executes code.
        </p>
        <div class="hero-btn-group">
            <button class="hero-btn" onclick="showDebugger()">Get Started for Free</button>
        </div>
    </div>
</div>

<div class="container" id="debuggerContainer">
    <div class="header">
        <h1>AI Code Debugger</h1>
        <p>Fix and run Python, Java, Arduino, Verilog, SystemVerilog, JS, TS, HTML, and CSS code with AI</p>
    </div>
    <div class="language-tabs">
        <div class="language-tab" onclick="switchLanguage('python')"><i class="fab fa-python"></i> Python</div>
        <div class="language-tab" onclick="switchLanguage('java')"><i class="fab fa-java"></i> Java</div>
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
                    <button class="button" type="submit" id="debugButton">Debug Code</button>
                    <a href="/download" class="button">Download</a>
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
    <div class="chatbot-input">
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
        javascript: "javascript",
        typescript: "javascript",
        html: "text/html",
        css: "text/css",
        django: "python", // Django uses Python
        react: "javascript", // React is JavaScript/JSX
        arduino: "text/x-c++src",
        verilog: "verilog",
        systemverilog: "verilog",
        uvm: "verilog",
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
            javaMainClassContainer.style.display = (lang === 'java') ? 'block' : 'none';
        }
        if (pythonInputPromptsContainer) { 
            // Only show for Python and Django (Python-based framework)
            const showPythonPrompts = ['python', 'django'].includes(lang);
            pythonInputPromptsContainer.style.display = showPythonPrompts ? 'block' : 'none';
        }

        // Make sure the chatbot button is visible when the debugger is active
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
            chatbotContainer.classList.toggle('active');
            chatbotToggleButton.classList.toggle('hidden');
            if (chatbotContainer.classList.contains('active')) {
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
        if (userMessage === '') return;

        const userMessageDiv = document.createElement('div');
        userMessageDiv.classList.add('message', 'user-message');
        userMessageDiv.textContent = userMessage;
        chatbotMessages.appendChild(userMessageDiv);
        chatInput.value = '';
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;

        const typingIndicatorDiv = document.createElement('div');
        typingIndicatorDiv.classList.add('typing-indicator', 'bot-message');
        typingIndicatorDiv.innerHTML = '<span>.</span><span>.</span><span>.</span>';
        chatbotMessages.appendChild(typingIndicatorDiv);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        sendChatBtn.disabled = true;

        try {
            const response = await fetch('/send_chat_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: userMessage }),
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
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        console.log("DOMContentLoaded fired.");
        
        initializeElements();

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

        if (debugButton) {
            debugButton.classList.remove('loading');
            debugButton.innerHTML = 'Debug Code';
            debugButton.disabled = false;
        }
        
        // This is the core fix: Ensure the chatbot button is visible
        // whenever the debugger container is shown.
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

# The Python code below is identical to our last conversation, but I'll include it for completeness.

# Global state
fixed_code_result = ""
explanation_text = ""

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
    # Update to handle new languages
    code = re.sub(r'```(python|java|arduino|verilog|systemverilog|uvm|javascript|typescript|html|css|django|react)\s*', '', code, flags=re.IGNORECASE)
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
        fixed_code_result = f"\u274c Error contacting AI: {str(e)}"
        explanation_text = "Could not generate explanation due to an error or repeated API failures."

def execute_java_code(code, main_class):
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, f"{main_class}.java")
    try:
        with open(file_path, 'w') as f:
            f.write(code)
        compile_command = ['javac', file_path]
        compile = subprocess.run(compile_command, cwd=temp_dir, capture_output=True, text=True, timeout=15)
        if compile.returncode != 0:
            return f"\u274c Compilation Error:\n{compile.stderr}"
        run_command = ['java', '-cp', temp_dir, main_class]
        run = subprocess.run(run_command, capture_output=True, text=True, timeout=10)
        if run.returncode != 0:
            return f"\u274c Runtime Error:\n{run.stderr}"
        return run.stdout or "\u2705 Ran successfully, no output."
    except subprocess.TimeoutExpired:
        return "\u274c Execution timed out."
    except Exception as e:
        return f"\u274c Execution error: {str(e)}"
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error during Java cleanup: {e}")

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
            return f"\u274c Compilation Error (Arduino CLI):\n{compile.stderr}"
        return "\u2705 Arduino code compiled successfully."
    except subprocess.TimeoutExpired:
        return "\u274c Arduino compilation timed out."
    except Exception as e:
        return f"\u274c Error during Arduino compilation: {str(e)}"
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
            return f"\u274c Compilation Error:\n{compile_result.stderr}"
        if "initial begin" in code or "always_ff" in code or "always_comb" in code or "program " in code:
            run_command = ['vvp', output_vvp]
            run_result = subprocess.run(run_command, cwd=temp_dir, capture_output=True, text=True, timeout=15)
            if run_result.returncode != 0:
                return f"\u274c Runtime Error (Simulation):\n{run_result.stderr}"
            return run_result.stdout or "\u2705 Verilog/SystemVerilog/UVM compiled and ran successfully (no output to display)."
        else:
            return "\u2705 Verilog/SystemVerilog/UVM compiled successfully (no testbench found for simulation)."
    except subprocess.TimeoutExpired:
        return "\u274c Execution timed out."
    except Exception as e:
        return f"\u274c Error: {str(e)}"
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
            return f"\u274c Runtime Error:\n{run_result.stderr}"
        return run_result.stdout or "\u2705 Ran successfully, no output."
    except FileNotFoundError:
        return "\u274c Error: Node.js is not installed or not in your system's PATH. Please install it to execute JavaScript code."
    except subprocess.TimeoutExpired:
        return "\u274c Execution timed out."
    except Exception as e:
        return f"\u274c Execution error: {str(e)}"
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
            return f"\u274c Compilation Error:\n{compile_result.stderr}"
        
        run_command = ['node', temp_js_file_path]
        run_result = subprocess.run(run_command, capture_output=True, text=True, timeout=10)
        
        if run_result.returncode != 0:
            return f"\u274c Runtime Error:\n{run_result.stderr}"
            
        return run_result.stdout or "\u2705 Ran successfully, no output."
        
    except FileNotFoundError as e:
        if 'tsc' in str(e):
            return "\u274c Error: TypeScript compiler ('tsc') is not installed. Please install it globally via `npm install -g typescript`."
        elif 'node' in str(e):
            return "\u274c Error: Node.js is not installed. Please install it to execute TypeScript code."
        else:
            return f"\u274c Execution Error: {str(e)}"
    except subprocess.TimeoutExpired:
        return "\u274c Execution timed out."
    except Exception as e:
        return f"\u274c Execution error: {str(e)}"
    finally:
        os.remove(temp_ts_file.name)
        if os.path.exists(temp_js_file_path):
            os.remove(temp_js_file_path)

def validate_and_execute_code(code, language, test_inputs=None, java_main_class=None):
    try:
        code = preprocess_code(code)
        if language == "python":
            inputs = re.findall(r'input\s*\(.*?\)', code)
            if test_inputs and len(test_inputs) < len(inputs):
                return f"\u274c Not enough test inputs (expected {len(inputs)})"
            for i, call in enumerate(inputs):
                if i < len(test_inputs):
                    code = code.replace(call, repr(test_inputs[i]), 1)
                else:
                    code = code.replace(call, "''", 1)
            old_stdout = sys.stdout
            sys.stdout = captured = io.StringIO()
            try:
                exec(code, {})
                return captured.getvalue().strip() or "\u2705 Ran successfully."
            finally:
                sys.stdout = old_stdout
        elif language == "java":
            return execute_java_code(code, java_main_class)
        elif language == "arduino":
            return execute_arduino_code(code)
        elif language in ["verilog", "systemverilog", "uvm"]:
            return execute_verilog_code(code, language)
        elif language == "javascript":
            return execute_javascript_code(code)
        elif language == "typescript":
            return execute_typescript_code(code)
        elif language in ["html", "css", "django", "react"]:
            # These are frameworks or markup/style languages that can't be "executed" as a single file.
            if language in ["django", "react"]:
                return f"\u2705 Code fixed successfully. Note: {language.capitalize()} requires a full project setup to run. The AI has provided the corrected snippet."
            else: # HTML/CSS
                return f"\u2705 Code fixed successfully. To see this {language.upper()} code in action, you need to open it in a web browser. The execution panel shows the raw, corrected code."
    except Exception as e:
        return f"\u274c Execution failed: {str(e)}"

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
    ext = ".txt" # Default extension
    if "void setup()" in fixed_code_result or "void loop()" in fixed_code_result:
        ext = ".ino"
    elif "public class" in fixed_code_result or "class " in fixed_code_result:
        ext = ".java"
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
    else:
        ext = ".py"

    response = make_response(fixed_code_result)
    response.headers["Content-Disposition"] = f"attachment; filename=debugged_code{ext}"
    response.mimetype = "text/plain"
    return response

@app.route("/send_chat_message", methods=["POST"])
def send_chat_message():
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"response": "Error: No message provided."}), 400
    try:
        model = genai.GenerativeModel("gemini-1.5-flash",
                                     safety_settings={
                                         HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                                         HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                                         HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                                         HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                                     })
        chat_session = model.start_chat(history=[])
        response = _gemini_api_call_with_retries(chat_session.send_message, user_message)
        ai_response = response.text
        return jsonify({"response": ai_response})
    except Exception as e:
        print(f"Error in AI chat response: {e}")
        return jsonify({"response": f"I'm sorry, I couldn't process that. Please try again. ({e})"}), 500

if __name__ == "__main__":
    print("Checking for external tools:")
    try:
        java_check = subprocess.run(['java', '-version'], capture_output=True, text=True, check=False)
        print("Java:", java_check.stderr.split('\n')[0].strip() if java_check.stderr else "Not found.")
    except Exception as e:
        print(f"\u26a0\ufe0f Java not found or not added to PATH. Java execution will not work. Error: {e}")
    try:
        arduino_check = subprocess.run(['arduino-cli', 'version'], capture_output=True, text=True, check=False)
        print("Arduino CLI:", arduino_check.stdout.strip().split('\n')[0].strip() if arduino_check.stdout else "Not found.")
    except Exception as e:
        print(f"\u26a0\ufe0f Arduino CLI not found or not added to PATH. Arduino compilation will not work. Error: {e}")
    try:
        iverilog_check = subprocess.run(['iverilog', '-v'], capture_output=True, text=True, check=False)
        print("Icarus Verilog:", iverilog_check.stdout.strip().split('\n')[0].strip() if iverilog_check.stdout else "Not found.")
    except Exception as e:
        print(f"\u26a0\ufe0f Icarus Verilog (iverilog) not found or not added to PATH. Verilog/SystemVerilog/UVM compilation will not work. Error: {e}")
    try:
        node_check = subprocess.run(['node', '-v'], capture_output=True, text=True, check=False)
        print("Node.js:", node_check.stdout.strip() if node_check.stdout else "Not found.")
    except Exception as e:
        print(f"\u26a0\ufe0f Node.js not found or not added to PATH. JavaScript and TypeScript execution will not work. Error: {e}")
    try:
        tsc_check = subprocess.run(['tsc', '-v'], capture_output=True, text=True, check=False)
        print("TypeScript Compiler (tsc):", tsc_check.stdout.strip() if tsc_check.stdout else "Not found.")
    except Exception as e:
        print(f"\u26a0\ufe0f TypeScript compiler ('tsc') not found. TypeScript compilation will not work. Error: {e}")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
