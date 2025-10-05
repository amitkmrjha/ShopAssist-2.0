from openai import OpenAI
import json
import pandas as pd

# --------------------------
# ✅ Gemini client setup
# --------------------------
client = OpenAI(
    api_key=open('GEMINI_API_KEY.txt', 'r').read().strip(),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# --------------------------
# 1. Initialize conversation (unchanged)
# --------------------------
def initialize_conversation():
    delimiter = "####"
    system_message = f"""
You are a highly experienced laptop advisor. Your goal is to help the user find the perfect laptop.
Follow these instructions carefully:

1. Ask detailed questions to understand:
   - Primary use case (gaming, content creation, coding, office, portability, battery life, etc.)
   - Priority for GPU intensity, display quality, portability, multitasking, processing speed, storage type, battery, and budget
   - Any preferred brands or additional requirements

2. Fill the following keys accurately in a dictionary:
   'GPU intensity', 'Display quality', 'Portability', 'Multitasking',
   'Processing speed', 'Storage type', 'Budget'

3. Values for all except Budget must be 'low', 'medium', or 'high'.
   Budget must be numeric (INR) and >= 25,000.
   If the user provides a currency symbol, convert it to INR using 1 USD = 83 INR.

4. If any key is missing or unclear, ask a polite, clarifying question.
5. Consider realistic laptop specs and market availability when suggesting ranges.
6. Provide concise, helpful, and friendly guidance, as if advising a knowledgeable client.
7. Use JSON format for output when required by function calling.

{delimiter}Thought Process:
- Thought 1: Understand user priorities and use case.
- Thought 2: Infer remaining keys logically if possible.
- Thought 3: Validate all keys; ask clarifying questions if unsure.
- Thought 4: Provide recommendations considering market trends and value for money.

Start with: "Hello! I’m here to help you find the perfect laptop. Can you tell me what you plan to use it for and which features matter most to you?"
"""
    return [{"role": "system", "content": system_message}]


# --------------------------
# 2. Gemini chat completion (enhanced with function calling)
# --------------------------
def get_chat_completions(messages, json_format=False, model="gemini-2.5-flash"):
    """
    Send messages to Gemini, optionally using JSON output.
    ⚙️ Now supports Gemini-compatible function calling.
    """
    # --- Define function schemas Gemini can call ---
    tools = [
        {
            "type": "function",
            "function": {
                "name": "dictionary_present",
                "description": "Extracts structured laptop preference dictionary from assistant or user text.",
                "parameters": {
                    "type": "object",
                    "properties": {"response": {"type": "string"}},
                    "required": ["response"]
                }
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compare_laptops_with_user",
                "description": "Compares user preferences with available laptops and returns top matches.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_req_string": {"type": "string"},
                        "laptop_csv": {"type": "string", "default": "updated_laptop.csv"}
                    },
                    "required": ["user_req_string"]
                }
            },
        }
    ]

    # --- Default user start ---
    if len(messages) == 1 and messages[0]["role"] == "system":
        messages.append({"role": "user", "content": "Hello!"})

    # --- Send request with tools ---
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools if not json_format else None,
        response_format={"type": "json_object"} if json_format else None
    )

    message = response.choices[0].message

    # --- Detect function calls ---
    if hasattr(message, "tool_calls") and message.tool_calls:
        tool_call = message.tool_calls[0]
        fn_name = tool_call.function.name
        fn_args = json.loads(tool_call.function.arguments or "{}")

        # Link available functions
        available_functions = {
            "dictionary_present": dictionary_present,
            "compare_laptops_with_user": compare_laptops_with_user,
        }

        if fn_name in available_functions:
            result = available_functions[fn_name](**fn_args)

            # --- Continue chat with function result ---
            messages.append(message)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": fn_name,
                "content": json.dumps(result)
            })

            follow_up = client.chat.completions.create(model=model, messages=messages)
            return follow_up.choices[0].message.content

    # --- No function call case ---
    msg = response.choices[0].message
    return json.loads(msg.content) if json_format else msg.content


# --------------------------
# 3–8. Your original methods remain unchanged
# --------------------------
def moderation_check(text):
    flagged_keywords = ["violence", "illegal", "hack"]
    for word in flagged_keywords:
        if word.lower() in text.lower():
            return "Flagged"
    return "Not Flagged"


def intent_confirmation_layer(response_assistant):
    prompt = """
Check if this dictionary includes all keys:
'GPU intensity','Display quality','Portability','Multitasking','Processing speed','Storage type','Budget'.
Values except Budget must be 'low','medium','high'. Budget must be numeric.
Return JSON: {"result": "Yes"} or {"result": "No"}.
"""
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Input: {response_assistant}"}
    ]
    return get_chat_completions(messages, json_format=True)


def dictionary_present(response):
    expected_keys = {
        'GPU intensity': 'high',
        'Display quality': 'high',
        'Portability': 'medium',
        'Multitasking': 'high',
        'Processing speed': 'high',
        'Storage type': 'SSD',
        'Budget': '200000'
    }
    prompt = f"""
Extract a JSON dictionary from text with keys:
{list(expected_keys.keys())}.
Ensure numeric Budget and lowercase values for other keys ('low','medium','high').
Output JSON only.
"""
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"User input: {response}"}
    ]
    return get_chat_completions(messages, json_format=True)


def compare_laptops_with_user(user_req_string, laptop_csv='updated_laptop.csv'):
    laptop_df = pd.read_csv(laptop_csv)
    user_requirements = dictionary_present(user_req_string)
    budget_str = str(user_requirements.get('Budget', 0)).replace(',', '').split()[0]
    try:
        budget = int(budget_str)
    except (ValueError, TypeError):
        budget = 25000
    filtered = laptop_df.copy()
    filtered['Price'] = filtered['Price'].astype(str).str.replace(',', '').fillna('0').astype(int)
    filtered = filtered[filtered['Price'] <= budget].copy()
    if filtered.empty:
        return json.dumps([{"message": "No laptops found within your budget."}])
    mappings = {'low': 0, 'medium': 1, 'high': 2}
    filtered['Score'] = 0
    for idx, row in filtered.iterrows():
        try:
            laptop_values = dictionary_present(row.get('laptop_feature', '')) or {}
        except Exception:
            laptop_values = {}
        score = 0
        for key, user_value in user_requirements.items():
            if key == 'Budget':
                continue
            laptop_value = str(laptop_values.get(key, 'low')).strip().lower()
            user_value_clean = str(user_value or 'low').strip().lower()
            if mappings.get(laptop_value, 0) >= mappings.get(user_value_clean, 0):
                score += 1
        filtered.at[idx, 'Score'] = score
    top_laptops = (
        filtered.drop(columns=['laptop_feature'], errors='ignore')
        .sort_values(by='Score', ascending=False)
        .head(3)
    )
    return top_laptops.to_json(orient='records')


def recommendation_validation(laptop_recommendation):
    data = json.loads(laptop_recommendation)
    return [d for d in data if d['Score'] > 2]


def initialize_conv_reco(products):
    system_message = """
You are a laptop expert. Summarize each laptop in descending order of price.
Include name, key specs, and price (INR). Make it clear and easy to read for the user.
"""
    user_message = f"These are the user's products: {products}"
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]
