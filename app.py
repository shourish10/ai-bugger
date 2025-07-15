from flask import Flask, request, render_template_string, make_response, send_file
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
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Code Debugger</title>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Sans&family=Source+Code+Pro&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/codemirror.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/codemirror.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/python/python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.12/mode/clike/clike.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Fira Sans', sans-serif;
            background-color: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: auto;
            padding: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
        }
        .header h1 {
            font-size: 2.5rem;
            color: #61dafb;
        }
        .language-tabs {
            display: flex;
            gap: 10px;
            margin: 20px 0;
        }
        .language-tab {
            padding: 10px 20px;
            border: 1px solid #444;
            border-radius: 5px;
            cursor: pointer;
            background-color: #333;
            color: #d4d4d4;
            transition: all 0.3s;
        }
        .language-tab.active {
            background-color: #007acc;
            color: white;
        }
        .split-view { display: flex; gap: 20px; flex-wrap: wrap; }
        .code-editor, .output-panel { flex: 1; min-width: 500px; }
        #editor {
            height: 400px;
        }
        textarea, pre, input {
            width: 100%;
            background-color: #252526;
            color: #dcdcdc;
            font-family: 'Source Code Pro', monospace;
            font-size: 14px;
            border: none;
            border-radius: 5px;
            padding: 10px;
            margin-top: 10px;
        }
        .button-group { margin-top: 15px; display: flex; gap: 10px; }
        .button {
            padding: 10px 20px;
            background-color: #0e639c;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        .execution-output {
            background-color: #000;
            color: #0f0;
            padding: 15px;
            border-radius: 5px;
            box-shadow: inset 0 0 10px #0f0;
            white-space: pre-wrap;
        }
        .ai-float-chat {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 300px;
            background: #1e1e1e;
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.5);
        }
        .ai-float-chat textarea {
            height: 80px;
        }
        .ai-float-chat button {
            margin-top: 10px;
            width: 100%;
            background-color: #007acc;
            border: none;
            padding: 10px;
            color: white;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
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
            <input type="hidden" name="language" id="languageInput" value="{{ language }}">
            <input type="hidden" name="code" id="codeInput">
            <div class="split-view">
                <div class="code-editor">
                    <h3>Editor</h3>
                    <textarea id="editor">{{ code }}</textarea>
                    {% if language == 'java' %}
                    <input type="text" name="java_main_class" value="{{ java_main_class }}" placeholder="Main class name">
                    {% endif %}
                    {% if input_prompts %}
                    <div>
                        {% for prompt in input_prompts %}
                        <input type="text" name="test_input_{{ loop.index0 }}" value="{{ test_inputs[loop.index0] if test_inputs and loop.index0 < test_inputs|length else '' }}" placeholder="{{ prompt }}">
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
            "python": "python",
            "java": "text/x-java",
            "arduino": "text/x-c++src"
        };

        const editor = CodeMirror.fromTextArea(document.getElementById("editor"), {
            lineNumbers: true,
            mode: languageMode["{{ language }}"],
            theme: "default",
            matchBrackets: true,
            autoCloseBrackets: true
        });

        document.querySelector("form").addEventListener("submit", function () {
            document.getElementById("codeInput").value = editor.getValue();
        });

        function switchLanguage(lang) {
            document.querySelectorAll('.language-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelector(`.language-tab[onclick*="${lang}"]`).classList.add('active');
            document.getElementById('languageInput').value = lang;
            editor.setOption("mode", languageMode[lang]);
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





