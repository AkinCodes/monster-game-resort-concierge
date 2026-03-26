import os
from dotenv import load_dotenv
load_dotenv()
import gradio as gr
import requests

monster_theme = gr.themes.Soft(
    primary_hue="stone",
    secondary_hue="stone",
    neutral_hue="stone",
    font=[gr.themes.GoogleFont("DM Sans"), "system-ui", "sans-serif"],
).set(
    body_background_fill="#faf9f7",
    block_background_fill="#ffffff",
    block_border_width="0px",
    block_shadow="0 1px 3px rgba(0,0,0,0.06)",
    button_primary_background_fill="#1a1a1a",
    button_primary_background_fill_hover="#333333",
    button_primary_text_color="white",
    input_background_fill="#ffffff",
    input_border_color="#e5e5e5",
    input_border_width="1px",
)

custom_css = """
footer {visibility: hidden}
.gradio-container {max-width: 860px !important; margin: auto; padding: 0 20px;}

/* Header */
.header-wrap {
    text-align: center;
    padding: 32px 0 20px 0;
}
.header-wrap h1 {
    font-size: 1.6rem !important;
    font-weight: 600 !important;
    color: #1a1a1a !important;
    margin: 0 !important;
    letter-spacing: -0.5px;
}
.header-wrap p {
    color: #888 !important;
    font-size: 0.9rem;
    margin-top: 4px !important;
}

/* Chat area — clean white card */
#chatbot {
    border: 1px solid #eee !important;
    border-radius: 16px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
}
.bubble-wrap {
    height: 480px !important;
    max-height: 480px !important;
    padding: 16px !important;
}

/* Message styling */
.message-wrap .message {
    border-radius: 14px !important;
    padding: 12px 16px !important;
    font-size: 0.92rem !important;
    line-height: 1.55 !important;
}

/* Input row */
.input-row {
    margin-top: 12px !important;
}
.input-row textarea {
    border-radius: 12px !important;
    padding: 14px 16px !important;
    font-size: 0.92rem !important;
    border: 1px solid #e0e0e0 !important;
    transition: border-color 0.2s;
}
.input-row textarea:focus {
    border-color: #999 !important;
    box-shadow: 0 0 0 2px rgba(0,0,0,0.05) !important;
}

/* Send button */
.send-btn {
    min-height: 48px !important;
    max-height: 48px !important;
    border-radius: 12px !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.3px;
}

/* Example buttons */
.examples-row {
    margin-top: 10px !important;
}
button.gallery-item {
    background: #f5f5f3 !important;
    border: 1px solid #e8e8e5 !important;
    color: #555 !important;
    border-radius: 10px !important;
    font-size: 0.82rem !important;
    padding: 8px 14px !important;
    transition: all 0.15s;
}
button.gallery-item:hover {
    background: #eee !important;
    border-color: #ccc !important;
    color: #1a1a1a !important;
}
"""

WELCOME_MESSAGE = {
    "role": "assistant",
    "content": (
        "Good evening. I am the Grand Chamberlain of Monster Resort Lodgings "
        "-- serving the supernatural community since 1348.\n\n"
        "I can help you with:\n"
        "- **Booking rooms** across our six haunted properties\n"
        "- **Amenities & dining** -- spa treatments, restaurants, activities\n"
        "- **Events & packages** -- Full Moon Festival, Halloween Ball, and more\n\n"
        "What can I arrange for you tonight?"
    ),
}


def predict(message, history, session_id):
    history.append({"role": "user", "content": message})
    history.append(
        {"role": "assistant", "content": "Consulting the ancient ledger..."}
    )
    yield history, "", session_id

    url = "http://127.0.0.1:8000/chat"
    headers = {
        "Authorization": f"Bearer {os.environ.get('MRC_API_KEY', 'your-api-key-here')}",
        "Content-Type": "application/json",
    }
    payload = {"message": message, "session_id": session_id}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        data = response.json()

        reply = data.get("reply", "The concierge is silent...")
        new_session_id = data.get("session_id", session_id)

        history = history[:-1]
        history.append({"role": "assistant", "content": reply})
        yield history, "", new_session_id

    except requests.exceptions.Timeout:
        history = history[:-1]
        history.append(
            {"role": "assistant", "content": "The concierge took too long to respond. Please try again."}
        )
        yield history, "", session_id

    except requests.exceptions.ConnectionError:
        history = history[:-1]
        history.append(
            {"role": "assistant", "content": "Cannot reach the concierge service. Is the server running on port 8000?"}
        )
        yield history, "", session_id

    except Exception as e:
        history = history[:-1]
        history.append(
            {"role": "assistant", "content": f"Something went wrong: {str(e)}"}
        )
        yield history, "", session_id


with gr.Blocks(theme=monster_theme, css=custom_css) as demo:
    with gr.Column(elem_classes="header-wrap"):
        gr.Markdown("# Monster Resort Concierge")
        gr.Markdown("Your guide to the spookiest stays and eeriest experiences")

    chatbot = gr.Chatbot(
        value=[WELCOME_MESSAGE],
        elem_id="chatbot",
        type="messages",
        height=480,
        show_copy_button=True,
        show_label=False,
    )

    with gr.Row(elem_classes="input-row"):
        msg = gr.Textbox(
            placeholder="Ask about rooms, amenities, or make a booking...",
            show_label=False,
            lines=1,
            max_lines=3,
            scale=5,
            container=False,
        )
        submit_btn = gr.Button("Send", variant="primary", scale=1, elem_classes="send-btn")

    with gr.Row(elem_classes="examples-row"):
        examples = gr.Examples(
            examples=[
                "What rooms does Vampire Manor have?",
                "Book a Coffin Suite for Count Dracula",
                "Tell me about the Mummy Resort spa",
                "What happens during the Full Moon Festival?",
            ],
            inputs=msg,
            label="",
        )

    session_id_state = gr.State(None)

    msg.submit(
        fn=predict,
        inputs=[msg, chatbot, session_id_state],
        outputs=[chatbot, msg, session_id_state],
    )
    submit_btn.click(
        fn=predict,
        inputs=[msg, chatbot, session_id_state],
        outputs=[chatbot, msg, session_id_state],
    )

if __name__ == "__main__":
    print("Starting Monster Resort Concierge UI...")
    print("Access the interface at: http://localhost:7861")
    print("Make sure your FastAPI server is running on http://localhost:8000")
    demo.launch(server_port=7861, share=True, show_error=True, server_name="127.0.0.1")
