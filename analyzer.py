# ============================================================
# analyzer.py
# CodeFix — core engine: error analysis + code repair
# with self-verification for Python fixes
# ============================================================

import os
import json

from groq import Groq

GROQ_KEY = os.environ.get("GROQ_KEY")

if not GROQ_KEY:
    from config import GROQ_KEY

MODEL = "openai/gpt-oss-20b"
MAX_FIX_ATTEMPTS = 3


ERROR_PROMPT = (
    "You are CodeFix, an expert programming debugger. A user will give you "
    "an error/traceback, optionally the relevant code, and possibly a "
    "programming language (which may be 'auto' if they want you to detect "
    "it yourself). Your job is to explain the problem clearly for a "
    "BEGINNER first, then give the fix. Never just dump a code block with "
    "no explanation. If the language is 'auto', figure it out from the "
    "error and code and report what you detected.\n\n"
    "Respond ONLY with valid JSON, no markdown fences, no extra text, in "
    "exactly this shape:\n"
    "{\n"
    '  "detected_language": "the programming language you identified, '
    'e.g. Python",\n'
    '  "error_type": "short name of the error, e.g. AttributeError",\n'
    '  "location": "file/function/line if identifiable from the input, '
    'else null",\n'
    '  "what_happened": "1-3 plain-English sentences describing what went '
    'wrong",\n'
    '  "why": "1-3 plain-English sentences explaining the root cause",\n'
    '  "simple_summary": "ONE short beginner-friendly sentence, the '
    '\'in simple terms\' explanation",\n'
    '  "fix_explanation": "what to change and why it works, in plain '
    'English",\n'
    '  "fixed_code": "the corrected code block as a plain string, or null '
    'if no code was given / no code change is needed"\n'
    "}"
)


CODE_FIX_PROMPT = (
    "You are CodeFix, an expert code repair tool. A user will paste code "
    "that is broken or messy, plus possibly a programming language (which "
    "may be 'auto' if they want you to detect it yourself). Fix everything "
    "that is wrong with it: indentation problems, syntax errors, missing "
    "brackets/quotes/colons, obvious typos, and clear bugs. Keep the "
    "original logic, names and style — only change what needs fixing. Do "
    "not add new features. Return the COMPLETE corrected code, never just "
    "snippets, so the user can copy and paste it directly. If the language "
    "is 'auto', figure it out from the code and report what you detected.\n\n"
    "Respond ONLY with valid JSON, no markdown fences, no extra text, in "
    "exactly this shape:\n"
    "{\n"
    '  "detected_language": "the programming language you identified, '
    'e.g. Python",\n'
    '  "summary": "one short sentence describing what was wrong overall",\n'
    '  "changes": ["one short line per fix, e.g. \'Fixed indentation '
    "inside the for loop'\"],\n"
    '  "fixed_code": "the full corrected code as a plain string"\n'
    "}\n"
    "If the code is already correct, say so in summary, set changes to an "
    "empty list, and return the code unchanged."
)


def _call_groq(system_prompt, user_message, max_tokens, temperature=0.2):
    client = Groq(api_key=GROQ_KEY)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        max_tokens=max_tokens,
        temperature=temperature
    )

    raw_text = response.choices[0].message.content.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:].strip()

    return json.loads(raw_text)


def _check_python_syntax(code_text):
    """Returns None if the code is syntactically valid Python, or a
    short error string describing what's wrong if it isn't. Does not
    execute the code — compile() only parses it."""

    try:
        compile(code_text, "<codefix_check>", "exec")
        return None
    except SyntaxError as error:
        return f"{error.msg} (line {error.lineno})"
    except Exception as error:
        return str(error)


def _verify_and_retry(code_text, language, ask_fix_again):
    """If the language is Python, checks the given code compiles. If it
    doesn't, calls ask_fix_again(previous_code, syntax_error) to get a
    corrected attempt, up to MAX_FIX_ATTEMPTS total. Returns
    (final_code, verified, attempts_used)."""

    if language.lower() != "python":
        # No built-in syntax checker for other languages yet — skip
        # verification rather than pretend to check it.
        return code_text, None, 1

    current_code = code_text

    for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
        syntax_error = _check_python_syntax(current_code)

        if syntax_error is None:
            return current_code, True, attempt

        if attempt == MAX_FIX_ATTEMPTS:
            break

        current_code = ask_fix_again(current_code, syntax_error)

    return current_code, False, MAX_FIX_ATTEMPTS


def analyze_error(error_text, code_text=None, language="Python"):
    """Explains an error and suggests a fix. Returns a dict."""

    parts = [f"Language: {language}", f"Error:\n{error_text}"]

    if code_text:
        parts.append(f"Relevant code:\n{code_text}")

    result = _call_groq(
        ERROR_PROMPT,
        "\n\n".join(parts),
        max_tokens=1500
    )

    if result.get("fixed_code"):
        effective_language = result.get("detected_language") or language

        def ask_fix_again(previous_code, syntax_error):
            retry_message = (
                f"Language: {effective_language}\n\n"
                f"Your previous fix still has a syntax error: "
                f"{syntax_error}\n\n"
                f"Previous attempt:\n{previous_code}\n\n"
                "Fix it properly this time. Respond with the same JSON "
                "shape as before."
            )
            retry_result = _call_groq(ERROR_PROMPT, retry_message, 1500)
            return retry_result.get("fixed_code", previous_code)

        final_code, verified, attempts = _verify_and_retry(
            result["fixed_code"], effective_language, ask_fix_again
        )
        result["fixed_code"] = final_code
        result["verified"] = verified

    return result


def fix_code(code_text, language="Python"):
    """Repairs broken/messy code and returns the full corrected version
    plus a short list of what changed. Returns a dict."""

    user_message = f"Language: {language}\n\nCode to fix:\n{code_text}"

    result = _call_groq(
        CODE_FIX_PROMPT,
        user_message,
        max_tokens=16000
    )

    def ask_fix_again(previous_code, syntax_error):
        retry_message = (
            f"Language: {language}\n\n"
            f"Your previous fix still has a syntax error: {syntax_error}\n\n"
            f"Previous attempt:\n{previous_code}\n\n"
            "Fix it properly this time. Respond with the same JSON shape "
            "as before."
        )
        retry_result = _call_groq(CODE_FIX_PROMPT, retry_message, 16000)
        return retry_result.get("fixed_code", previous_code)

    effective_language = result.get("detected_language") or language

    final_code, verified, attempts = _verify_and_retry(
        result["fixed_code"], effective_language, ask_fix_again
    )

    result["fixed_code"] = final_code
    result["verified"] = verified

    if verified is False:
        result["changes"] = result.get("changes", []) + [
            f"Note: could not fully verify this fix after {attempts} "
            "attempts — double-check before using it."
        ]

    return result