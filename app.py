from flask import Flask, request
import os
import requests
from datetime import datetime

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")

# Catalogue de départ : tu pourras le changer plus tard.
ARTICLES = {
    "1": "Robe",
    "2": "Pantalon",
    "3": "Chemise",
    "4": "Chaussures",
}
TAILLES = {"1": "S", "2": "M", "3": "L", "4": "XL"}
COULEURS = {"1": "Noir", "2": "Blanc", "3": "Bleu", "4": "Rouge"}

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

# Mémoire des conversations en cours (en attendant une vraie base de données).
# Attention : elle est vidée à chaque redémarrage du serveur.
CONVERSATIONS = {}
# Commandes terminées, en attente de validation par la commerçante.
COMMANDES = []


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


def liste_choix(dictionnaire):
    return "\n".join(f"{cle} - {valeur}" for cle, valeur in dictionnaire.items())


def traiter_message(numero, nom, texte):
    texte = texte.strip()
    conv = CONVERSATIONS.get(numero)

    # Nouvelle conversation : on salue, puis on montre le menu.
    if conv is None:
        CONVERSATIONS[numero] = {"etape": "menu", "nom": nom, "article": {}}
        envoyer_message(numero, MESSAGE_ACCUEIL)
        envoyer_message(numero, MENU)
        return

    etape = conv["etape"]

    if etape == "menu":
        if texte == "1":
            conv["etape"] = "article"
            envoyer_message(numero, "Quel article voulez-vous ?\n" + liste_choix(ARTICLES))
        elif texte == "2":
            conv["mode"] = "Retrait au magasin"
            envoyer_message(numero, "Très bien, nous vous attendons au magasin ! 🙂")
            CONVERSATIONS.pop(numero, None)
        elif texte == "3":
            conv["mode"] = "Livraison"
            envoyer_message(numero, "Pour la livraison, commencez par choisir votre article.\n" + liste_choix(ARTICLES))
            conv["etape"] = "article"
        else:
            envoyer_message(numero, MENU)

    elif etape == "article":
        if texte in ARTICLES:
            conv["article"]["nom"] = ARTICLES[texte]
            conv["etape"] = "taille"
            envoyer_message(numero, "Quelle taille ?\n" + liste_choix(TAILLES))
        else:
            envoyer_message(numero, "Choix non reconnu.\n" + liste_choix(ARTICLES))

    elif etape == "taille":
        if texte in TAILLES:
            conv["article"]["taille"] = TAILLES[texte]
            conv["etape"] = "couleur"
            envoyer_message(numero, "Quelle couleur ?\n" + liste_choix(COULEURS))
        else:
            envoyer_message(numero, "Choix non reconnu.\n" + liste_choix(TAILLES))

    elif etape == "couleur":
        if texte in COULEURS:
            conv["article"]["couleur"] = COULEURS[texte]
            conv["etape"] = "quantite"
            envoyer_message(numero, "Quelle quantité ? (écrivez un nombre)")
        else:
            envoyer_message(numero, "Choix non reconnu.\n" + liste_choix(COULEURS))

    elif etape == "quantite":
        if texte.isdigit() and int(texte) > 0:
            conv["article"]["quantite"] = int(texte)
            a = conv["article"]
            COMMANDES.append({
                "numero": numero,
                "nom": conv["nom"],
                "date": datetime.now().strftime("%d/%m/%Y"),
                "heure": datetime.now().strftime("%H:%M"),
                "mode": conv.get("mode", "À préciser"),
                "article": dict(a),
                "validee": False,
            })
            envoyer_message(
                numero,
                f"Merci ! Récapitulatif : {a['quantite']} x {a['nom']}, "
                f"taille {a['taille']}, couleur {a['couleur']}.\n"
                "La commerçante va valider votre commande.",
            )
            CONVERSATIONS.pop(numero, None)
        else:
            envoyer_message(numero, "Écrivez un nombre, par exemple 1 ou 2.")


@app.route("/")
def home():
    return "Le bot WhatsApp est actif."


@app.route("/webhook", methods=["GET"])
def verifier():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN and VERIFY_TOKEN:
        return challenge, 200
    return "Accès refusé", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    try:
        valeur = data["entry"][0]["changes"][0]["value"]
        if "messages" in valeur:
            message = valeur["messages"][0]
            numero = message["from"]
            nom = "Client"
            if "contacts" in valeur:
                nom = valeur["contacts"][0].get("profile", {}).get("name", "Client")
            if message.get("type") == "text":
                traiter_message(numero, nom, message["text"]["body"])
    except (KeyError, IndexError):
        pass
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
