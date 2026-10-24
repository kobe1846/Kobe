from flask import Flask, request, Response
import os
import hmac
import requests
from datetime import datetime
from html import escape

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
NUMERO_COMMERCANTE = os.environ.get("NUMERO_COMMERCANTE", "")
MOT_DE_PASSE_ADMIN = os.environ.get("MOT_DE_PASSE_ADMIN", "")

ARTICLES = {"1": "Robe", "2": "Pantalon", "3": "Chemise", "4": "Chaussures"}
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

# Attention : ces données sont perdues à chaque redémarrage du serveur.
CONVERSATIONS = {}
COMMANDES = []


def envoyer_message(numero, texte):
    if not numero:
        return
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
    try:
        reponse = requests.post(url, headers=headers, json=corps, timeout=10)
        print("Envoi :", reponse.status_code)
    except requests.RequestException as erreur:
        print("Erreur d'envoi :", erreur)


def liste_choix(dictionnaire):
    return "\n".join(f"{cle} - {valeur}" for cle, valeur in dictionnaire.items())


def resume_commande(commande, numero_commande):
    a = commande["article"]
    return (
        f"🛍️ Nouvelle commande n°{numero_commande}\n"
        f"Client : {commande['nom']} (+{commande['numero']})\n"
        f"Date : {commande['date']} à {commande['heure']}\n"
        f"Article : {a['quantite']} x {a['nom']}, taille {a['taille']}, "
        f"couleur {a['couleur']}\n"
        f"Mode : {commande['mode']}"
    )


def traiter_message(numero, nom, texte):
    texte = texte.strip()
    conv = CONVERSATIONS.get(numero)

    if conv is None:
        CONVERSATIONS[numero] = {"etape": "menu", "nom": nom, "article": {}}
        envoyer_message(numero, MESSAGE_ACCUEIL)
        envoyer_message(numero, MENU)
        return

    etape = conv["etape"]

    if etape == "menu":
        if texte == "1":
            conv["mode"] = "À préciser"
            conv["etape"] = "article"
            envoyer_message(numero, "Quel article voulez-vous ?\n" + liste_choix(ARTICLES))
        elif texte == "2":
            conv["mode"] = "Retrait au magasin"
            conv["etape"] = "article"
            envoyer_message(numero, "Très bien, vous passerez au magasin. Choisissez votre article.\n" + liste_choix(ARTICLES))
        elif texte == "3":
            conv["mode"] = "Livraison"
            conv["etape"] = "article"
            envoyer_message(numero, "Pour la livraison, choisissez votre article.\n" + liste_choix(ARTICLES))
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
        if texte.isdigit() and 0 < int(texte) < 100:
            conv["article"]["quantite"] = int(texte)
            a = conv["article"]
            maintenant = datetime.now()
            commande = {
                "numero": numero,
                "nom": conv["nom"],
                "date": maintenant.strftime("%d/%m/%Y"),
                "heure": maintenant.strftime("%H:%M"),
                "mode": conv.get("mode", "À préciser"),
                "article": dict(a),
                "validee": False,
            }
            COMMANDES.append(commande)
            envoyer_message(
                numero,
                f"Merci ! Récapitulatif : {a['quantite']} x {a['nom']}, "
                f"taille {a['taille']}, couleur {a['couleur']}.\n"
                "La commerçante va valider votre commande.",
            )
            envoyer_message(NUMERO_COMMERCANTE, resume_commande(commande, len(COMMANDES)))
            CONVERSATIONS.pop(numero, None)
        else:
            envoyer_message(numero, "Écrivez un nombre entre 1 et 99.")


def mot_de_passe_ok():
    auth = request.authorization
    if not MOT_DE_PASSE_ADMIN or auth is None:
        return False
    return hmac.compare_digest(
        (auth.password or "").encode(), MOT_DE_PASSE_ADMIN.encode()
    )


def demander_connexion():
    return Response(
        "Connexion requise", 401,
        {"WWW-Authenticate": 'Basic realm="Espace commerçante"'},
    )


@app.route("/")
def home():
    return "Le bot WhatsApp est actif."


@app.route("/commandes")
def page_commandes():
    if not mot_de_passe_ok():
        return demander_connexion()
    lignes = ""
    for i, c in enumerate(COMMANDES, start=1):
        a = c["article"]
        if c["validee"]:
            statut = "✅ Validée"
        else:
            statut = f'<a href="/valider/{i}">Valider</a>'
        lignes += (
            "<tr>"
            f"<td>{i}</td>"
            f"<td>{escape(c['nom'])}</td>"
            f"<td>{c['date']} {c['heure']}</td>"
            f"<td>{a['quantite']} x {escape(a['nom'])} ({a['taille']}, {a['couleur']})</td>"
            f"<td>{escape(c['mode'])}</td>"
            f"<td>{statut}</td>"
            "</tr>"
        )
    if not lignes:
        lignes = '<tr><td colspan="6">Aucune commande pour le moment.</td></tr>'
    return (
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<h2>Commandes</h2>"
        '<table border="1" cellpadding="6">'
        "<tr><th>N°</th><th>Client</th><th>Date</th><th>Article</th>"
        "<th>Mode</th><th>Statut</th></tr>"
        + lignes +
        "</table>"
    )


@app.route("/valider/<int:numero_commande>")
def valider(numero_commande):
    if not mot_de_passe_ok():
        return demander_connexion()
    if 1 <= numero_commande <= len(COMMANDES):
        commande = COMMANDES[numero_commande - 1]
        if not commande["validee"]:
            commande["validee"] = True
            envoyer_message(
                commande["numero"],
                f"✅ Votre commande n°{numero_commande} est validée, merci !",
            )
    return '<meta http-equiv="refresh" content="0; url=/commandes">'


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
