from flask import Flask, render_template, request, render_template_string, make_response, send_file
import google.generativeai as genai
import os
from dotenv import load_dotenv
import io
import sys
import re
import subprocess
import tempfile

load_dotenv()
app = Flask(__name__)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# HTML template omitted for brevity (you already have it)
# HTML Template embedded
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
    <style>
        body {
            margin: 0;
            font-family: 'Fira Sans', sans-serif;
            background: #15151e;
            color: #fff;
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
            color: #000000; /* Changed to black as requested */
            letter-spacing: 0.02em;
            margin-bottom: 0.6em;
            text-shadow: 0 6px 32px #2637ff40, 0 1px 2px #16edd7, 0 8px 40px #3986fd20;
            font-family: 'Fira Sans', sans-serif;
            text-align: center;
            white-space: nowrap; /* Keep text on one line */
            overflow: hidden; /* Hide overflowing text */
            border-right: .15em solid orange; /* The typing cursor */
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
            /* --- MODIFIED TEXT SHADOW AND ADDED TYPING ANIMATION --- */
            text-shadow: 0 3px 15px #54dbff50, 0 1px 5px #0ffbe050; /* Reduced shadow */
            font-family: 'Fira Sans', sans-serif;
            letter-spacing: 0.03em;
            text-align: center;
            white-space: nowrap; /* Keep text on one line */
            overflow: hidden; /* Hide overflowing text */
            border-right: .15em solid orange; /* The typing cursor */
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
        }
        #editor {
            height: 400px;
        }
        .button-group {
            margin-top: 22px;
            display: flex;
            gap: 12px;
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
        }
        .button:hover {
            background: linear-gradient(90deg,#58e1fe 30%,#1be5c3 100%);
            color: #133944;
        }
        .execution-output {
            background-color: #101329;
            color: #0fcaca;
            padding: 15px;
            border-radius: 9px;
            box-shadow: 0 0 15px #4bffe367;
            margin-top: 12px;
        }
        pre {
            font-family: 'Source Code Pro', monospace;
            border-radius: 6px;
            background: #1a2240;
            padding: 13px;
            color: #bbfcff;
        }
        @media (max-width: 900px) {
            .split-view { flex-direction: column; }
        }
        @media (max-width: 600px) {
            .welcome-content h1 { font-size: 2.2rem; }
            .welcome-content p { font-size: 1.01rem; }
            .container { margin: 13px 0; padding: 10px 4px; }
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
        <p>Fix and run Python, Java & Arduino code with AI</p>
    </div>
    <div class="language-tabs">
        <div class="language-tab active" onclick="switchLanguage('python')"><i class="fab fa-python"></i> Python</div>
        <div class="language-tab" onclick="switchLanguage('java')"><i class="fab fa-java"></i> Java</div>
        <div class="language-tab" onclick="switchLanguage('arduino')"><i class="fas fa-microchip"></i> Arduino</div>
    </div>
    <form method="post">
        <input type="hidden" name="language" id="languageInput" value="{{ language }}" />
        <input type="hidden" name="code" id="codeInput" />
        <div class="split-view">
            <div class="code-editor">
                <h3>Editor</h3>
                <textarea id="editor">{{ code }}</textarea>
                {% if language == 'java' %}
                    <input type="text" name="java_main_class" value="{{ java_main_class }}" placeholder="Main class name" />
                {% endif %}
                {% if input_prompts %}
                    <div>
                        {% for prompt in input_prompts %}
                            <input
                                type="text"
                                name="test_input_{{ loop.index0 }}"
                                value="{{ test_inputs[loop.index0] if test_inputs and loop.index0 < test_inputs|length else '' }}"
                                placeholder="{{ prompt }}"
                            />
                        {% endfor %}
                    </div>
                {% endif %}
                <div class="button-group">
                    <button class="button" type="submit">Debug Code</button>
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

    {% if chat_response %}
    <div class="output-panel">
        <h3>AI Response</h3>
        <pre>{{ chat_response }}</pre>
    </div>
    {% endif %}
    <form class="ai-float-chat" method="post">
        <textarea name="chat_prompt" placeholder="Ask anything about code...">{{ chat_prompt }}</textarea>
        <button type="submit" name="chat_submit">Ask AI</button>
    </form>
</div>

<script>
    const languageMode = {
        python: "python",
        java: "text/x-java",
        arduino: "text/x-c++src",
    };

    const editor = CodeMirror.fromTextArea(document.getElementById("editor"), {
        lineNumbers: true,
        mode: languageMode["{{ language }}"],
        theme: "default",
        matchBrackets: true,
        autoCloseBrackets: true,
    });

    document.querySelector("form").addEventListener("submit", function () {
        document.getElementById("codeInput").value = editor.getValue();
    });

    function switchLanguage(lang) {
        document.querySelectorAll(".language-tab").forEach((tab) => tab.classList.remove("active"));
        document.querySelector(`.language-tab[onclick*="${lang}"]`).classList.add("active");
        document.getElementById("languageInput").value = lang;
        editor.setOption("mode", languageMode[lang]);
    }

    function showDebugger() {
        document.getElementById("welcomeScreen").style.display = "none";
        document.getElementById("debuggerContainer").style.display = "block";
    }

    window.onload = function () {
        switchLanguage("{{ language }}");
    };
</script>
</body>
</html>
"""



# Global state
fixed_code_result = ""
explanation_text = ""
chat_response = ""

def preprocess_code(code):
    code = code.replace("```python", "").replace("```java", "").replace("```arduino", "").replace("```", "")
    code = code.replace("\t", "    ")
    code = re.sub(r'[^\x00-\x7F]+', '', code)
    code = re.sub(r'^\s*\.\.\..*$', '', code, flags=re.MULTILINE)
    return code.strip()

def get_input_prompts(code):
    prompts = []
    matches = list(re.finditer(r'input\s*\((.*?)\)', code))
    for match in matches:
        try:
            prompt = match.group(1).strip('"\'') or "Enter value"
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
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        chat = model.start_chat()

        if language == "java":
            class_match = re.search(r'public\s+class\s+(\w+)', code)
            main_class = class_match.group(1) if class_match else "Main"
            prompt = f"""Fix this Java code:
{code}
Requirements:
1. Include main class '{main_class}'
2. Add imports and fix syntax
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""

        elif language == "arduino":
            prompt = f"""Fix this Arduino code:
{code}
Requirements:
1. Ensure setup() and loop() are present
2. Add comments and fix any syntax issues
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""

        else:
            prompt = f"""Fix this Python code:
{code}
Requirements:
1. Correct syntax or logical errors.
2. Do not convert string to int unless necessary.
3. Preserve operations like str * int.
Format:
<corrected_code>
---EXPLANATION---
<explanation>"""

        response = chat.send_message(prompt)
        full = response.text.strip()
        if '---EXPLANATION---' in full:
            fixed_code_result, explanation_text = map(str.strip, full.split('---EXPLANATION---', 1))
        else:
            fixed_code_result = full
            explanation_text = "Explanation not provided."
    except Exception as e:
        fixed_code_result = f"\u274c Error: {str(e)}"
        explanation_text = ""

def execute_java_code(code, main_class):
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, f"{main_class}.java")
    try:
        with open(file_path, 'w') as f:
            f.write(code)
        compile = subprocess.run(['javac', file_path], cwd=temp_dir, capture_output=True, text=True)
        if compile.returncode != 0:
            return f"\u274c Compilation Error:\n{compile.stderr}"
        run = subprocess.run(['java', '-cp', temp_dir, main_class], capture_output=True, text=True, timeout=10)
        if run.returncode != 0:
            return f"\u274c Runtime Error:\n{run.stderr}"
        return run.stdout or "\u2705 Ran successfully, no output."
    except subprocess.TimeoutExpired:
        return "\u274c Execution timed out."
    except Exception as e:
        return f"\u274c Execution error: {str(e)}"
    finally:
        try:
            for file in os.listdir(temp_dir):
                os.unlink(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)
        except: pass

def execute_arduino_code(code):
    temp_dir = tempfile.mkdtemp()
    sketch = os.path.join(temp_dir, "sketch.ino")
    try:
        with open(sketch, 'w') as f:
            f.write(code)
        compile = subprocess.run(['arduino-cli', 'compile', '--fqbn', 'arduino:avr:uno', temp_dir], capture_output=True, text=True)
        if compile.returncode != 0:
            return f"\u274c Compilation Error:\n{compile.stderr}"
        return "\u2705 Arduino code compiled successfully"
    except Exception as e:
        return f"\u274c Error: {str(e)}"
    finally:
        try:
            for file in os.listdir(temp_dir):
                os.unlink(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)
        except: pass

def validate_and_execute_code(code, language, test_inputs=None, java_main_class=None):
    try:
        code = preprocess_code(code)
        if language == "python":
            inputs = re.findall(r'input\s*\(.*?\)', code)
            if test_inputs and len(test_inputs) < len(inputs):
                return f"\u274c Not enough test inputs (expected {len(inputs)})"
            for i, call in enumerate(inputs):
                code = code.replace(call, repr(test_inputs[i]), 1)
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
    except Exception as e:
        return f"\u274c Execution failed: {str(e)}"

@app.route("/", methods=["GET", "POST"])
def index():
    global fixed_code_result, explanation_text, chat_response

    code = ""
    result = ""
    explanation = ""
    output = ""
    chat_prompt = ""
    chat_response = ""
    test_inputs = []
    input_prompts = []
    java_main_class = "Main"
    language = "python"

    if request.method == "POST":
        language = request.form.get("language", "python")
        if "chat_submit" in request.form:
            chat_prompt = request.form.get("chat_prompt", "")
            try:
                model = genai.GenerativeModel("models/gemini-1.5-flash")
                response = model.generate_content(chat_prompt)
                chat_response = response.text.strip()
            except Exception as e:
                chat_response = f"\u274c Error from AI: {str(e)}"
        else:
            code = request.form.get("code", "")
            java_main_class = request.form.get("java_main_class", "Main")

            if language == "python":
                input_prompts = get_input_prompts(code)
                if requires_test_input(code):
                    test_inputs = []
                    for i in range(len(input_prompts)):
                        input_value = request.form.get(f"test_input_{i}", "")
                        test_inputs.append(input_value)

            # ✅ Fix and execute
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
        chat_prompt=chat_prompt,
        chat_response=chat_response
    )

@app.route("/download")
def download():
    global fixed_code_result
    if "void setup()" in fixed_code_result or "void loop()" in fixed_code_result:
        ext = ".ino"
    elif "public class" in fixed_code_result or "class " in fixed_code_result:
        ext = ".java"
    else:
        ext = ".py"

    response = make_response(fixed_code_result)
    response.headers["Content-Disposition"] = f"attachment; filename=debugged_code{ext}"
    response.mimetype = "text/plain"
    return response

if __name__ == "__main__":
    try:
        java_check = subprocess.run(['java', '-version'], capture_output=True, text=True)
        print("Java:", java_check.stderr.split('\n')[0])
    except Exception as e:
        print("\u26a0\ufe0f Java not found or not added to PATH")

    try:
        arduino_check = subprocess.run(['arduino-cli', 'version'], capture_output=True, text=True)
        print("Arduino CLI:", arduino_check.stdout.strip())
    except Exception as e:
        print("\u26a0\ufe0f Arduino CLI not found or not added to PATH")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)





