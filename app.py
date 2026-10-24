from flask import Flask, request
import os
import requests

app = Flask(__name__)

# Ces valeurs sont lues depuis les variables d'environnement de Render.
# Ne jamais les écrire en clair dans le code.
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")

MESSAGE_ACCUEIL = (
    "Bonjour et bienvenue ! 😊\n"
    "Je suis l'assistant automatique de la boutique."
)

MENU = (
    "Que souhaitez-vous faire ?\n"
    "1 - Passer une commande\n"
    "2 - Venir au magasin\n"
    "3 - Être livré(e)\n"
    "Répondez avec le numéro de votre choix."
)


def envoyer_message(numero, texte):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    corps = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texte},
    }
    reponse = requests.post(url, headers=headers, json=corps, timeout=10)
    print("Envoi :", reponse.status_code)


@app.route("/")
def home():
    return "Le bot WhatsApp est actif."


# Meta appelle cette route une seule fois pour vérifier ton serveur.
@app.route("/webhook", methods=["GET"])
def verifier():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN and VERIFY_TOKEN:
        return challenge, 200
    return "Accès refusé", 403


# Meta envoie ici chaque message reçu des clients.
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    try:
        valeur = data["entry"][0]["changes"][0]["value"]
        if "messages" in valeur:
            message = valeur["messages"][0]
            numero = message["from"]
            envoyer_message(numero, MESSAGE_ACCUEIL)
            envoyer_message(numero, MENU)
    except (KeyError, IndexError):
        pass
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
