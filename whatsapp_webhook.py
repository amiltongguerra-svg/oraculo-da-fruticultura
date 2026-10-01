import os
import requests
from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
@app.route("/privacy", methods=["GET"])
def privacy():
    return """
    <h1>Política de Privacidade - Oráculo da Fruticultura</h1>
    <p>O Oráculo da Fruticultura utiliza informações enviadas pelo usuário
    exclusivamente para responder às solicitações realizadas pelo WhatsApp.</p>
    <p>Os dados não são vendidos nem compartilhados para fins comerciais.</p>
    <p>Para solicitar exclusão de dados, entre em contato com o responsável
    pelo Oráculo da Fruticultura.</p>
    """

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Falha na verificação", 403

@app.route("/webhook", methods=["POST"])
def receive_webhook():
    data = request.get_json()

    print("Mensagem recebida do WhatsApp:")
    print(data)

    try:
        value = data["entry"][0]["changes"][0]["value"]
        messages = value.get("messages", [])

        if messages:
            message = messages[0]
            from_number = message["from"]
            text = message.get("text", {}).get("body", "")

            if text:
                url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"

                headers = {
                    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                    "Content-Type": "application/json",
                }

                payload = {
                    "messaging_product": "whatsapp",
                    "to": from_number,
                    "type": "text",
                    "text": {
                        "body": "Olá! Sou o Oráculo da Fruticultura. Recebi sua mensagem."
                    },
                }

                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=30
                )

                print("Resposta enviada ao WhatsApp:")
                print(response.status_code)
                print(response.text)

    except Exception as e:
        print("Erro ao processar mensagem:", str(e))

    return "EVENT_RECEIVED", 200
