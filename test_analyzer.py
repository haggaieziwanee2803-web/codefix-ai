# ============================================================
# test_analyzer.py
# Quick terminal test for analyzer.py — no web stuff yet.
# ============================================================

from analyzer import analyze_error

PYTHON_ERROR = """Traceback (most recent call last):
  File "bot.py", line 42, in <module>
    result = h.play_command
AttributeError: module 'handlers_admin' has no attribute 'play_command'
"""

PYTHON_CODE = """
async def Play_command(update, context):
    pass
"""

JS_ERROR = """Uncaught TypeError: Cannot read properties of undefined (reading 'map')
    at renderList (app.js:15:23)
    at main (app.js:30:5)
"""

JS_CODE = """
function renderList(items) {
    return items.map(item => item.name);
}

function main() {
    const data = fetchData(); // returns undefined if API call hasn't resolved yet
    renderList(data);
}
"""


def run_test(label, error_text, code_text, language):
    print(f"===== {label} =====\n")

    result = analyze_error(
        error_text=error_text,
        code_text=code_text,
        language=language
    )

    print("Error type:", result["error_type"])
    print("Location:", result["location"])
    print()
    print("In simple terms:")
    print(result["simple_summary"])
    print()
    print("What happened:")
    print(result["what_happened"])
    print()
    print("Why:")
    print(result["why"])
    print()
    print("Fix explanation:")
    print(result["fix_explanation"])
    print()
    print("Fixed code:")
    print(result["fixed_code"])
    print("\n" + "=" * 50 + "\n")


if __name__ == "__main__":
    run_test("PYTHON TEST", PYTHON_ERROR, PYTHON_CODE, "Python")
    run_test("JAVASCRIPT TEST", JS_ERROR, JS_CODE, "JavaScript")