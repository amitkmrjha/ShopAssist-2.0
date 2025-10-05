from flask import Flask, redirect, url_for, render_template, request
from functions import *

app = Flask(__name__)

conversation_bot = []
conversation = initialize_conversation()
introduction = get_chat_completions(conversation)
conversation_bot.append({'bot': introduction})
top_3_laptops = None


@app.route("/")
def default_func():
    global conversation_bot
    return render_template("index.html", name_xyz=conversation_bot)


@app.route("/end_conv", methods=['POST', 'GET'])
def end_conv():
    global conversation_bot, conversation, top_3_laptops
    conversation_bot = []
    conversation = initialize_conversation()
    introduction = get_chat_completions(conversation)
    conversation_bot.append({'bot': introduction})
    top_3_laptops = None
    return redirect(url_for('default_func'))


@app.route("/invite", methods=['POST'])
def invite():
    global conversation_bot, conversation, top_3_laptops, conversation_reco

    user_input = request.form["user_input_message"]
    prompt = (
        "Remember you are a laptop shopping assistant. "
        "Answer only laptop-related queries."
    )

    moderation = moderation_check(user_input)
    if moderation == 'Flagged':
        display("⚠️ Message flagged. Restart conversation.")
        return redirect(url_for('end_conv'))

    if top_3_laptops is None:
        conversation.append({"role": "user", "content": user_input + prompt})
        conversation_bot.append({'user': user_input})

        response_assistant = get_chat_completions(conversation)
        confirmation = intent_confirmation_layer(response_assistant)

        if "No" in confirmation.get('result'):
            conversation.append({"role": "assistant", "content": response_assistant})
            conversation_bot.append({'bot': response_assistant})
        else:
            response = dictionary_present(response_assistant)
            conversation_bot.append({'bot': "Thank you! Fetching laptop recommendations..."})

            top_3_laptops = compare_laptops_with_user(response)
            validated_reco = recommendation_validation(top_3_laptops)

            if not validated_reco:
                conversation_bot.append({'bot': "No laptops match your requirements."})
            else:
                conversation_reco = initialize_conv_reco(validated_reco)
                conversation_reco.append({
                    "role": "user",
                    "content": f"User profile {validated_reco}"
                })
                recommendation = get_chat_completions(conversation_reco)
                conversation_reco.append({"role": "assistant", "content": recommendation})
                conversation_bot.append({'bot': recommendation})
    else:
        conversation_reco.append({"role": "user", "content": user_input})
        conversation_bot.append({'user': user_input})

        response_asst_reco = get_chat_completions(conversation_reco)
        conversation_reco.append({"role": "assistant", "content": response_asst_reco})
        conversation_bot.append({'bot': response_asst_reco})

    return redirect(url_for('default_func'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
