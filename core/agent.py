import math
import re

def _s(val, fallback=0):
    """Return fallback if val is None, NaN, or infinity."""
    if val is None:
        return fallback
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return fallback
    return val

def _s(val, fallback=0):
    """Return fallback if val is None, NaN, or infinity."""
    if val is None:
        return fallback
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return fallback
    return val

# Read the current agent.py
with open('core/agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# ================================================
# 1. Remove all external AI imports & clients
# ================================================
content = re.sub(r'from groq import Groq\n', '', content)
content = re.sub(r'import google\.generativeai as genai\n', '', content)
content = re.sub(r'from \.config import GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY\n', '', content)
content = re.sub(r'_groq_client = None\n_gemini_model = None\n', '', content)
content = re.sub(r'def _get_groq.*?return _groq_client\n', '', content, flags=re.DOTALL)
content = re.sub(r'def _get_gemini.*?return _gemini_model\n', '', content, flags=re.DOTALL)

# ================================================
# 2. Replace generate_trade_plan with a pure engine call
# ================================================
old_gen = re.search(r'def generate_trade_plan\(data: dict\) -> str:.*?return _rule_based\(data\)', content, re.DOTALL)
if old_gen:
    new_gen = '''def generate_trade_plan(data: dict) -> str:
    """
    Fully self-contained trading engine.
    No external APIs, no LLMs, no rate limits.
    """
    return _rule_based(data)'''
    content = content.replace(old_gen.group(0), new_gen)

# ================================================
# 3. Add NaN guard inside _rule_based output
# ================================================
# We'll wrap every numeric variable in a helper that returns 0 if NaN
helper = '''
def _s(val, fallback=0):
    """Return fallback if val is None, NaN, or infinity."""
    if val is None:
        return fallback
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return fallback
    return val
'''

# Insert helper after the imports (or at start)
insert_pos = content.find('\n', content.find('import re'))
content = content[:insert_pos+1] + helper + content[insert_pos+1:]

# Now fix the f-string in _rule_based: replace every occurrence of {var} with {_s(var, default)}
# We target the specific variables used in the output.
replace_map = {
    'vwap:.2f': 'price',     # VWAP fallback to current price
    'atr:.2f': 'price*0.02',
    'support:.2f': 'price*0.95',
    'resistance:.2f': 'price*1.05',
    'daily_high:.2f': 'price',
    'daily_low:.2f': 'price',
    'daily_range:.2f': 'price*0.02',
    'entry:.2f': '0',
    'stop:.2f': '0',
    'tp1:.2f': '0',
    'tp2:.2f': '0',
    'tp3:.2f': '0',
}

for var, fallback in replace_map.items():
    # Replace the formatted version {var:.2f} with {_s(var, fallback):.2f}
    old = '{' + var + '}'
    new = '{_s(' + var.split(':')[0] + ', ' + fallback + '):.2f}'
    content = content.replace(old, new)
    # Also replace unformatted occurrences if any (but they're usually formatted)

# Save the clean file
with open('core/agent.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('agent.py fixed – completely self-contained, NaN-safe.')