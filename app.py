from flask import Flask, request, jsonify, render_template, redirect, session, send_file
from flask_cors import CORS
import csv
import os
import io
import json
import subprocess
import tempfile
import pdfkit
from datetime import date
import pandas as pd
from datetime import datetime
###############################################################################################
###############################################################################################
#Config a prendre en compte pour l'execution 
config = pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")

app = Flask(__name__)
app.secret_key = 'supersecretkey'
CORS(app)
###############################################################################################
###############################################################################################
# === CONFIG ===
os.makedirs('bdd', exist_ok=True)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CSV_FILE = os.path.join(BASE_DIR, 'bdd', 'Client.csv')
PRODUITS_FILE = os.path.join(BASE_DIR, 'bdd', 'produits.csv')
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
DOSSIER_DEVIS = os.path.join(BASE_DIR, 'devis_generes')
PRODUITS_FRS = os.path.join(BASE_DIR, 'Produits_FRS')  # On définit d'abord le chemin
os.makedirs(PRODUITS_FRS, exist_ok=True)               # Puis on crée le dossier
UPLOAD_FOLDER = 'uploads'
CSV_FILE1 = os.path.join(BASE_DIR, 'bdd', 'fournisseurs.csv')
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ALGO_PATH = os.path.join(PROJECT_DIR, 'backend', 'ton_algo.exe')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_dossier_client():
    nom = session.get("nom")
    prenom = session.get("prenom")

    if nom and prenom:
        nom_client = f"{prenom}_{nom}".strip().lower().replace(" ", "_")
    elif nom:
        nom_client = nom.strip().lower().replace(" ", "_")
    else:
        nom_client = "inconnu"

    dossier = os.path.join("devis_generes", nom_client)
    os.makedirs(dossier, exist_ok=True)  # ✅ crée le dossier s’il n’existe pas

    return dossier

###############################################################################################
##############################################################################################
#Page d'accueil du projet
#Test a enlever à la fin
#@app.route('/')
#def index():
#    return 'Serveur OK'
#Ouvrir la page de choix roles
@app.route('/')
def home():
    return redirect('/choix_roles')

@app.route('/choix_roles')
def choix_roles():
    return render_template('choix_roles.html')
###############################################################################################
###############################################################################################
#Client
#direction vers le html d'inscription
@app.route('/inscription')
def inscription():
    return render_template('client.html')
###############################################################################################
#inscription -enregistrement client
@app.route('/client', methods=['POST'])
def enregistrer_client():
    data = request.form
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            data.get('nom'),
            data.get('prenom'),
            data.get('email'),
            data.get('motdepasse'),
            data.get('adresse'),
            data.get('numero')
        ])
    return render_template('success.html')
###############################################################################################
#connexion client
@app.route('/login', methods=['GET'])
def login_form():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    motdepasse = request.form.get('motdepasse')
    try:
        with open(CSV_FILE, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 4:
                    nom, prenom, email_enreg, mdp_enreg, *_ = row
                    if email == email_enreg and motdepasse == mdp_enreg:
                        session['nom'] = nom
                        session['prenom'] = prenom
                        session['email'] = email_enreg
                        return redirect('/dashboard')
    except Exception as e:
        return "Erreur serveur", 500
    return "Email ou mot de passe invalide", 401
###############################################################################################
###############################################################################################
#Interface client
#Chatbot
@app.route('/dashboard')
def dashboard():
    if 'email' in session:
        produits = []
        try:
            with open(PRODUITS_FILE, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['email'] == session['email']:
                        produits.append(row)
        except FileNotFoundError:
            pass

        return render_template(
            'dashboard.html',
            nom=session.get('nom'),
            prenom=session.get('prenom'),
            email=session.get('email'),
            produits=produits
        )
    return redirect('/login')

#Chatbot -Lecture & Ajout du fournisseur 
@app.route('/process_csv', methods=['POST'])
def process_csv():
    try:
        file = request.files['file']
        fournisseur_prefere = request.form.get('fournisseur', '').strip()

        if not file:
            return jsonify({'success': False, 'error': 'Aucun fichier reçu.'})
        # Sauver le fichier temporairement
        input_path = os.path.join(UPLOAD_FOLDER, 'input_user.csv')
        file.save(input_path)

        # Créer le fichier au bon format
        demandes_csv_path = os.path.join(BACKEND_DIR, 'demandes.csv')

        with open(input_path, 'r', encoding='utf-8') as infile, open(demandes_csv_path, 'w', newline='', encoding='utf-8') as outfile:
            reader = csv.reader(infile, delimiter=';')
            writer = csv.writer(outfile, delimiter=';')
            
            for row in reader:
                if len(row) >= 2:
                    produit = row[0].strip()
                    quantite = row[1].strip()
                    fournisseur = "" if fournisseur_prefere.upper() == "AUTO" else fournisseur_prefere
                    writer.writerow([produit, quantite, fournisseur])

        # Appeler ton algo avec le fichier backend/demandes.csv
        result = subprocess.run(
            [ALGO_PATH, "preanalyse", "demandes.csv"],
            capture_output=True,
            text=True,
            cwd=BACKEND_DIR  # on se place dans backend pour que produit.txt et tout soit visible
        )

        if result.returncode != 0:
            return jsonify({
                'success': False,
                'error': f"Erreur de ton algo.exe :\n{result.stderr or ''}\n{result.stdout or ''}"
            })

        # Vérifier si propositions.json a été généré dans backend/
        propositions_path = os.path.join(BACKEND_DIR, 'propositions.json')
        if not os.path.exists(propositions_path):
            return jsonify({'success': False, 'error': 'propositions.json non trouvé dans backend.'})

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})# === ROUTES CLIENT ZIP ===
#recuperer les noms des fournisseurs pour les afficher
@app.route('/get_fournisseurs')
def get_fournisseurs():
    fournisseurs = set()
    with open('backend/produit.txt', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 4:
                _, frs, _, _ = parts
                fournisseurs.add(frs.upper())
    return jsonify(sorted(fournisseurs))

#Chatbot -Génération du Proposition.json
@app.route('/algo_upload', methods=['POST'])
def algo_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier reçu'}), 400

    if 'nom' not in session:
        return jsonify({'error': 'Utilisateur non connecté'}), 401

    file = request.files['file']
    user_name = session['nom']

    # 📂 Créer un dossier personnel dans /upload/NOM_CLIENT/
    upload_dir = os.path.join(BASE_DIR, 'upload', user_name)
    os.makedirs(upload_dir, exist_ok=True)

    # 🕒 Nommer le fichier avec un horodatage
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"demandes_{timestamp}.csv"
    path_csv = os.path.join(upload_dir, file_name)
    file.save(path_csv)
    file.stream.seek(0)  # Réinitialise la lecture du fichier

    # Copie aussi dans backend/demandes.csv pour ton algo C
    backend_path = os.path.join(BACKEND_DIR, 'demandes.csv')
    file.save(backend_path)

    # ▶️ Exécuter ton algo
    exe_path = os.path.join(BACKEND_DIR, 'ton_algo.exe')
    if not os.path.exists(exe_path):
        return jsonify({'error': 'Fichier exécutable manquant'}), 500

    subprocess.run(
        [exe_path, 'preanalyse'],
        capture_output=True,
        text=True,
        cwd=BACKEND_DIR
    )

    # 📤 Lire les propositions générées
    prop_path = os.path.join(BACKEND_DIR, 'propositions.json')
    if not os.path.exists(prop_path):
        return jsonify({'error': 'Aucune proposition trouvée'}), 404

    with open(prop_path, 'r', encoding='utf-8') as f:
        propositions = json.load(f)

    return jsonify({'propositions': propositions})

#Chatbot -Récupération et affichage des propositions
@app.route('/get_propositions', methods=['GET'])
def get_propositions():
    try:
        propositions_path = os.path.join(BACKEND_DIR, 'propositions.json')
        
        if not os.path.exists(propositions_path):
            return jsonify({'success': False, 'error': 'Fichier propositions.json introuvable.'})
        
        with open(propositions_path, 'r', encoding='utf-8') as f:
            propositions = json.load(f)
        
        return jsonify({'success': True, 'data': propositions})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

#Chatbot -Enregistrement des choix du client et génération du .JSON
@app.route('/save_choix', methods=['POST'])
def save_choix():
    try:
        data = request.get_json()
        choix = data.get('choix', {})

        if not isinstance(choix, dict) or not choix:
            return jsonify({'success': False, 'error': 'Format invalide ou vide.'})

        choix_path = os.path.join(BACKEND_DIR, 'choix_utilisateur.json')
        with open(choix_path, 'w', encoding='utf-8') as f:
            json.dump(choix, f, indent=2)

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/choix', methods=['POST'])
def choix():
    data = request.get_json()
    choix_path = os.path.join(BACKEND_DIR, 'choix_utilisateur.json')
    with open(choix_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    return jsonify({"message": "Choix sauvegardés avec succès."})

@app.route('/save_choix_insuffisant', methods=['POST'])
def save_choix_insuffisant():
    try:
        data = request.get_json()
        path = os.path.join(BACKEND_DIR, 'choix_stock_insuffisant.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
#REPARTITION
@app.route('/calculer_repartition/<produit>/<int:qte>')
def calculer_repartition(produit, qte):
    produit = produit.strip().upper()
    resultats = []

    with open('backend/produit.txt', encoding='utf-8') as f:
        fournisseurs = []
        for line in f:
            parts = line.strip().split()
            if len(parts) == 4:
                nom, frs, stock, prix = parts
                if nom.strip().upper() == produit:
                    fournisseurs.append({
                        "nom": frs,
                        "stock": int(stock),
                        "prix": float(prix)
                    })

    fournisseurs.sort(key=lambda f: f["prix"])

    reste = qte
    for frs in fournisseurs:
        if reste <= 0:
            break
        prene = min(reste, frs["stock"])
        if prene > 0:
            resultats.append({ "nom": frs["nom"], "quantite": prene })
            reste -= prene

    return jsonify(resultats)

#recup des infos 
@app.route('/get_fournisseurs_disponibles/<produit>')
def get_fournisseurs_disponibles(produit):
    produit = produit.strip().upper()
    with open('backend/produit.txt', encoding='utf-8') as f:
        fournisseurs = {}
        for line in f:
            parts = line.strip().split()
            if len(parts) == 4:
                nom, frs, stock, prix = parts
                if nom.strip().upper() == produit:
                    fournisseurs[frs] = {"stock": int(stock), "prix": float(prix)}
    return jsonify(fournisseurs)

#Génération du devis
@app.route('/generer_devis_final', methods=['POST','GET'])
def generer_devis_final():
    with open('backend/choix_utilisateur.json', encoding='utf-8') as f:
        choix = json.load(f)

    with open('backend/propositions.json', encoding='utf-8') as f:
        propositions = json.load(f)
        
    try:
        with open('backend/choix_stock_insuffisant.json', encoding='utf-8') as f:
            choix_insuffisant = json.load(f)
    except FileNotFoundError:
        choix_insuffisant = {}

    produits_final = []
    total_ht = 0.0
    economie_totale = 0.0

    produit_data = {}
    with open('backend/produit.txt', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 4:
                nom, fournisseur, stock, prix = parts
                nom = nom.strip().upper()
                fournisseur = fournisseur.strip().upper()
                produit_data.setdefault(nom, {})[fournisseur] = (int(stock), float(prix))

    for produit, fournisseur_choisi in choix.items():
        produit = produit.strip().upper()

        # Répartition à traiter immédiatement (détail ligne par ligne)
        if produit in choix_insuffisant and choix_insuffisant[produit]["type"] == "repartition":
            fournisseurs = produit_data.get(produit, {})
            total_reparti = 0.0

            for f in choix_insuffisant[produit]["fournisseurs"]:
                frs = f["nom"].strip().upper()
                qte = f["quantite"]
                if frs in fournisseurs:
                    stock_frs, prix_frs = fournisseurs[frs]
                    if stock_frs >= qte:
                        total_ligne = prix_frs * qte
                        total_reparti += total_ligne

            # Ajouter une ligne d'en-tête visuelle
            produits_final.append({
                'nom': f"{produit} (🔁 Réparti automatiquement)",
                'fournisseur': "",
                'qte': "",
                'pu': "",
                'economie': "",
                'total': ""
            })

            for f in choix_insuffisant[produit]["fournisseurs"]:
                frs = f["nom"].strip().upper()
                qte = f["quantite"]
                if frs in fournisseurs:
                    stock_frs, prix_frs = fournisseurs[frs]
                    if stock_frs >= qte:
                        total_ligne = prix_frs * qte
                        total_ht += total_ligne
                        produits_final.append({
                            'nom': "",
                            'fournisseur': frs,
                            'qte': qte,
                            'pu': f"{prix_frs:.2f}€",
                            'economie': "—",
                            'total': f"{total_ligne:.2f}€"
                        })
            continue

        fournisseur_choisi = fournisseur_choisi.strip().upper()
        quantite_demandee = next((p['quantite_demande'] for p in propositions if p['nom'].strip().upper() == produit), 0)

        # Ajustement éventuel
        if produit in choix_insuffisant and choix_insuffisant[produit]["type"] == "ajustement":
            quantite_demandee = choix_insuffisant[produit]["quantite"]
            fournisseur_choisi = choix_insuffisant[produit]["fournisseur"].strip().upper()

        fournisseurs = produit_data.get(produit, {})

        if fournisseur_choisi in ["REFUS", "AUCUN", "—"] or fournisseur_choisi not in fournisseurs:
            produits_final.append({
                'nom': produit,
                'fournisseur': "—",
                'qte': "—",
                'pu': "—",
                'economie': "—",
                'total': "Indisponible"
            })
            continue

        stock_dispo, prix_choisi = fournisseurs[fournisseur_choisi]

        # Vérifier stock sauf si ajustement
        if (
            produit not in choix_insuffisant
            or choix_insuffisant[produit]["type"] != "ajustement"
        ):
            if stock_dispo < quantite_demandee:
                produits_final.append({
                    'nom': produit,
                    'fournisseur': fournisseur_choisi,
                    'qte': "—",
                    'pu': "—",
                    'economie': "—",
                    'total': "Indisponible"
                })
                continue

        proposition = next((p for p in propositions if p['nom'].strip().upper() == produit), None)

        if (
            proposition
            and proposition['fournisseur_optimise'].strip().upper() == fournisseur_choisi
            and proposition['economie'] > 0
        ):
            economie_totale_produit = proposition['economie']
            economie_affichee = f"{economie_totale_produit:.2f}€"
        else:
            economie_totale_produit = 0
            economie_affichee = "-"

        total_produit = prix_choisi * quantite_demandee

        produits_final.append({
            'nom': produit,
            'fournisseur': fournisseur_choisi,
            'qte': quantite_demandee,
            'pu': f"{prix_choisi:.2f}€",
            'economie': economie_affichee,
            'total': f"{total_produit:.2f}€"
        })

        total_ht += total_produit
        economie_totale += economie_totale_produit

    tva = round(total_ht * 0.20, 2)
    bia_fee = round(total_ht * 0.05, 2)
    total_ttc = round(total_ht + tva + bia_fee, 2)

    client_nom = session.get("nom", "Client")
    client_email = session.get("email", "email@example.com")
    client_ville = "Paris"

    dossier_client = get_dossier_client()

    numero_devis = 1
    while os.path.exists(os.path.join(dossier_client, f"BIA-{numero_devis:03}.pdf")):
        numero_devis += 1

    nom_fichier_pdf = f"BIA-{numero_devis:03}.pdf"
    chemin_pdf = os.path.join(dossier_client, nom_fichier_pdf)

    html = render_template('devis_visuel.html',
        numero_devis=f"BIA-{numero_devis:03}",
        client_nom=client_nom,
        client_email=client_email,
        client_ville=client_ville,
        emetteur_nom="BIA",
        emetteur_email="contact@bia.com",
        emetteur_ville="Paris",
        date_emission=str(date.today()),
        date_echeance=str(date.today().replace(day=28)),
        validite="2025-05-28",
        produits=produits_final,
        sous_total=f"{total_ht:.2f}€",
        tva=f"{tva:.2f}€",
        bia_fee=f"{bia_fee:.2f}€",
        total=f"{total_ttc:.2f}€",
        economie_totale=f"{economie_totale:.2f}€"
    )

    nom_client = f"{session.get('prenom')}_{session.get('nom')}".strip().lower().replace(" ", "_")
    # ✅ Génération réelle du fichier PDF
    try:
        pdfkit.from_string(html, chemin_pdf, configuration=config)
    except Exception as e:
        print("Erreur lors de la génération PDF :", e)
        return jsonify({'success': False, 'error': str(e)})
    # Enregistrer les infos du devis dans un fichier JSON
    infos_devis = {
        "numero": f"BIA-{numero_devis:03}",
        "montant": f"{total_ttc:.2f} €"
    }
    with open(os.path.join(dossier_client, f"{infos_devis['numero']}.json"), "w", encoding="utf-8") as f:
        json.dump(infos_devis, f, indent=2)
    return jsonify({
        'success': True,
        'fichier': nom_fichier_pdf,
        'numero_devis': f"BIA-{numero_devis:03}",
        'url': f"/devis_generes/{nom_client}/{nom_fichier_pdf}"
    })


from flask import send_from_directory

@app.route('/devis_generes/<client>/<filename>')
def get_devis_pdf(client, filename):
    return send_from_directory(os.path.join("devis_generes", client), filename)

#Chatbot -Déconnexion (à connecter)
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

#A voir ptt a supprimer
@app.route('/telecharger_devis', methods=['GET'])
def telecharger_devis():
    devis_path = os.path.join(BACKEND_DIR, 'devis.pdf')
    if not os.path.exists(devis_path):
        return jsonify({'success': False, 'error': 'Le fichier devis.pdf est introuvable.'})
###############################################################################################
@app.route('/accueil')
def accueil():
    dossier_fournisseurs = PRODUITS_FRS
    fournisseurs = []

    if os.path.exists(dossier_fournisseurs):
        fournisseurs = [
            nom for nom in os.listdir(dossier_fournisseurs)
            if os.path.isdir(os.path.join(dossier_fournisseurs, nom))
        ]

    commandes = []
    if "nom" in session and "prenom" in session:
        nom_client = "{}_{}".format(session.get("prenom"), session.get("nom")).strip().lower().replace(" ", "_")
        dossier_client = get_dossier_client()
        if os.path.exists(dossier_client):
            for fichier in os.listdir(dossier_client):
                if fichier.endswith(".pdf"):
                    numero = fichier.replace(".pdf", "")
                    chemin_json = os.path.join(dossier_client, f"{numero}.json")
                    montant = "—"
                    statut = "En attente"

                    if os.path.exists(chemin_json):
                        with open(chemin_json, encoding="utf-8") as f:
                            data = json.load(f)
                            montant = data.get("montant", montant)
                            statut = data.get("statut", statut)
                            
                    commandes.append({
                        "nom": numero,
                        "date": datetime.fromtimestamp(os.path.getmtime(os.path.join(dossier_client, fichier))).strftime("%d/%m/%Y"),
                        "montant": montant,
                        "statut": statut,
                        "fichier": fichier,
                        "url": "/devis_generes/{}/{}".format(nom_client, fichier)
                    })

    return render_template('accueil.html', fournisseurs=fournisseurs, commandes=commandes)

@app.route("/devis/<nom_fichier>")
def voir_devis(nom_fichier):
    nom_client = session.get("nom")
    if not nom_client:
        return redirect(url_for("login"))

    chemin_fichier = os.path.join(DOSSIER_DEVIS, nom_client.replace(" ", "_"), nom_fichier)
    if os.path.exists(chemin_fichier):
        return send_file(chemin_fichier)
    else:
        return "Fichier introuvable", 404

###############################################################################################
#Page de recherche
@app.route('/recherche')
def recherche():
    return render_template('recherche.html')

#traitement a faire avant affichage des produits
@app.route('/fusion_produits', methods=['GET'])
def fusion_produits():
    try:
        dossier_frs = PRODUITS_FRS
        fichier_sortie = os.path.join(BACKEND_DIR, 'produit.txt')

        os.makedirs(BACKEND_DIR, exist_ok=True)

        with open(fichier_sortie, 'w', encoding='utf-8') as f_out:
            for fournisseur in os.listdir(dossier_frs):
                dossier_fournisseur = os.path.join(dossier_frs, fournisseur)
                if os.path.isdir(dossier_fournisseur):
                    for fichier in os.listdir(dossier_fournisseur):
                        if fichier.endswith('.csv'):
                            chemin_fichier = os.path.join(dossier_fournisseur, fichier)
                            with open(chemin_fichier, newline='', encoding='utf-8') as f_in:
                                reader = csv.DictReader(f_in)
                                for row in reader:
                                    description_sans_espaces = row.get('description', '').replace(" ", "")
                                    # image = row.get('image', '').strip()  # ← optionnel, tu peux garder cette ligne si tu veux l'image plus tard
                                    ligne = f"{description_sans_espaces} {row.get('entreprise', fournisseur).strip()} {row.get('stock', '').strip()} {row.get('prix', '').strip()}"
                                    # ligne += f" {image}"  # ← désactivé temporairement
                                    f_out.write(ligne + '\n')

      #  return jsonify({"message": "Fusion terminée", "chemin": fichier_sortie})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

#Recherche -Récupération et affichage des produits
@app.route('/produits')
def produits():
    produit_txt = os.path.join(BACKEND_DIR, 'produit.txt')
    produits = {}

    try:
        with open(produit_txt, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 4:
                    nom = parts[0]
                    frs = parts[1]
                    qte = int(parts[2])
                    prix = float(parts[3])

                    if nom not in produits:
                        produits[nom] = []
                    produits[nom].append({
                        'fournisseur': frs,
                        'quantite': qte,
                        'prix': prix
                    })
    except FileNotFoundError:
        produits = {}

    return render_template('recherche.html', produits=produits)

#Recherche -Enregistrement et transcription vers panier
@app.route('/enregistrer_choix', methods=['POST'])
def enregistrer_choix():
    data = request.get_json()
    path = os.path.join(BACKEND_DIR, 'choix_et_quantites.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return jsonify({"message": "Choix avec quantités enregistrés."})
#validation commande
@app.route('/valider_commande', methods=['POST'])
def valider_commande():
    data = request.get_json()
    statut = data.get('statut', 'non défini')
    numero_devis = data.get('numero_devis', 'inconnu')
    montant = data.get('montant', '—')

    if not numero_devis or numero_devis == 'inconnu':
        return jsonify({'success': False, 'error': 'Numéro de devis manquant'}), 400

    dossier_client = get_dossier_client()
    chemin_json = os.path.join(dossier_client, f"{numero_devis}.json")

    try:
        # 🟢 Enregistre correctement les infos du devis
        with open(chemin_json, 'w', encoding='utf-8') as f:
            json.dump({
                "numero": numero_devis,
                "montant": montant,
                "statut": statut
            }, f, ensure_ascii=False, indent=2)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



###############################################################################################
#Page de panier
@app.route('/panier')
def panier():
    return render_template('panier.html')

#Panier -Gestion et génération du devis
@app.route('/generer_devis_panier', methods=['POST'])
def generer_devis_panier():
    path = os.path.join(BACKEND_DIR, 'choix_et_quantites.json')

    if not os.path.exists(path):
        return "Fichier choix_et_quantites.json introuvable", 404

    with open(path, encoding='utf-8') as f:
        choix = json.load(f)

    produits_final = []
    total_ht = 0.0
    economie_totale = 0.0

    produit_data = {}
    with open(os.path.join(BACKEND_DIR, 'produit.txt'), encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 4:
                nom, fournisseur, stock, prix = parts
                nom = nom.strip().upper()
                fournisseur = fournisseur.strip().upper()
                produit_data.setdefault(nom, {})[fournisseur] = (int(stock), float(prix))

    for produit, infos in choix.items():
        fournisseur_choisi = infos['fournisseur'].strip().upper()
        quantite_demandee = int(infos.get('quantite', 0))
        produit = produit.strip().upper()

        if fournisseur_choisi in ["REFUS", "AUCUN"]:
            produits_final.append({
                'nom': produit,
                'fournisseur': "—",
                'qte': "—",
                'pu': "—",
                'economie': "—",
                'total': "Indisponible"
            })
            continue

        fournisseurs = produit_data.get(produit, {})
        if fournisseur_choisi not in fournisseurs:
            produits_final.append({
                'nom': produit,
                'fournisseur': fournisseur_choisi,
                'qte': quantite_demandee,
                'pu': "—",
                'economie': "—",
                'total': "Indisponible"
            })
            continue

        stock_dispo, prix_choisi = fournisseurs[fournisseur_choisi]
        meilleur_prix = min(p for _, p in fournisseurs.values())

        if prix_choisi < meilleur_prix:
            economie_totale_produit = (meilleur_prix - prix_choisi) * quantite_demandee
            economie_affichee = f"{economie_totale_produit:.2f}€"
        else:
            economie_totale_produit = 0
            economie_affichee = "-"

        total_produit = prix_choisi * quantite_demandee

        produits_final.append({
            'nom': produit,
            'fournisseur': fournisseur_choisi,
            'qte': quantite_demandee,
            'pu': f"{prix_choisi:.2f}€",
            'economie': economie_affichee,
            'total': f"{total_produit:.2f}€"
        })

        total_ht += total_produit
        economie_totale += economie_totale_produit

    tva = round(total_ht * 0.20, 2)
    bia_fee = round(total_ht * 0.05, 2)
    total_ttc = round(total_ht + tva + bia_fee, 2)

    client_nom = session.get("nom", "Client")
    client_email = session.get("email", "email@example.com")
    client_ville = "Paris"

    dossier_client = os.path.join(DOSSIER_DEVIS, client_nom.replace(' ', '_'))
    os.makedirs(dossier_client, exist_ok=True)

    numero_devis = 1
    while os.path.exists(os.path.join(dossier_client, f"BIA-{numero_devis:03}.pdf")):
        numero_devis += 1

    nom_fichier_pdf = f"BIA-{numero_devis:03}.pdf"
    chemin_pdf = os.path.join(dossier_client, nom_fichier_pdf)

    html = render_template('devis_visuel.html',
        numero_devis=f"BIA-{numero_devis:03}",
        client_nom=client_nom,
        client_email=client_email,
        client_ville=client_ville,
        emetteur_nom="BIA",
        emetteur_email="contact@bia.com",
        emetteur_ville="Paris",
        date_emission=str(date.today()),
        date_echeance=str(date.today().replace(day=28)),
        validite="2025-05-28",
        produits=produits_final,
        sous_total=f"{total_ht:.2f}€",
        tva=f"{tva:.2f}€",
        bia_fee=f"{bia_fee:.2f}€",
        total=f"{total_ttc:.2f}€",
        economie_totale=f"{economie_totale:.2f}€"
    )

    try:
        pdfkit.from_string(html, chemin_pdf, configuration=config)
    except Exception as e:
        print("Erreur PDFKIT :", e)
        return jsonify({'success': False, 'error': str(e)})
    return send_file(chemin_pdf, download_name=nom_fichier_pdf, as_attachment=True)
###############################################################################################
#Page de profil
@app.route('/profil')
def profil():
    email = session.get("email")
    if not email:
        return redirect("/login")

    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 6 and row[2] == email:
                    return render_template('profil.html', 
                        nom=row[0], 
                        prenom=row[1], 
                        email=row[2], 
                        adresse=row[4], 
                        numero=row[5]
                    )
    except Exception as e:
        return f"Erreur lors de la lecture des données : {e}", 500

    return "Client non trouvé", 404
from flask import jsonify, session
import os
from datetime import datetime

@app.route('/get_factures_client')
def get_factures_client():
    if "nom" not in session or "prenom" not in session:
        return jsonify({"error": "Client non connecté"}), 401

    dossier = get_dossier_client()
    factures = []

    if os.path.exists(dossier):
        for fichier in os.listdir(dossier):
            if fichier.endswith(".pdf"):
                numero = fichier.replace(".pdf", "")
                chemin_pdf = os.path.join(dossier, fichier)
                chemin_json = os.path.join(dossier, f"{numero}.json")

                montant = "—"
                statut = "En attente"

                if os.path.exists(chemin_json):
                    with open(chemin_json, encoding="utf-8") as f:
                        data = json.load(f)
                        montant = data.get("montant", montant)
                        statut = data.get("statut", statut)

                date = datetime.fromtimestamp(os.path.getmtime(chemin_pdf)).strftime("%d %b %Y")

                factures.append({
                    "numero": numero,
                    "date": date,
                    "montant": montant,
                    "status": statut,
                    "url": f"/{chemin_pdf.replace(os.sep, '/')}"
                })

    return jsonify(factures)





#changement de mot de passe
@app.route('/changer_motdepasse', methods=['POST'])
def changer_motdepasse():
    ancien_mdp = request.form.get("ancien_mdp")
    nouveau_mdp = request.form.get("nouveau_mdp")
    email = session.get("email")

    if not email:
        return redirect("/login")

    lignes = []
    trouve = False
    client_infos = {}

    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 6:
                    if row[2] == email:
                        if row[3] == ancien_mdp:
                            row[3] = nouveau_mdp
                            trouve = True
                        client_infos = {
                            'nom': row[0],
                            'prenom': row[1],
                            'email': row[2],
                            'adresse': row[4],
                            'numero': row[5]
                        }
                    lignes.append(row)

        if not trouve:
            return "Ancien mot de passe incorrect", 403

        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(lignes)

        return render_template("profil.html", **client_infos)

    except Exception as e:
        return f"Erreur serveur : {str(e)}", 500

###############################################################################################
###############################################################################################




#FOURNISSEURS

@app.route('/fournisseur')
def fournisseur():
    return redirect('/fournisseur1')

@app.route('/fournisseur1')
def fournisseur1():
    return render_template('fournisseur.html')

@app.route('/logout1')
def logout1():
    session.clear()  # Supprime toutes les infos de session
    return redirect('/login1')  # Redirige vers la page de connexion

@app.route('/login1', methods=['POST'])
def login1():
    email = request.form.get('email')
    motdepasse = request.form.get('motdepasse')
    try:
        with open(CSV_FILE1, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 4:
                    nom, entreprise, email_enreg, mdp_enreg, *_ = row
                    if email == email_enreg and motdepasse == mdp_enreg:
                        # Enregistrer dans la session
                        session['nom'] = nom
                        session['entreprise'] = entreprise
                        session['email'] = email_enreg
                        return redirect('/dashboard1')
    except Exception as e:
        return "Erreur serveur", 500
    return "Email ou mot de passe invalide", 401

@app.route('/login1', methods=['GET'])
def login1_form():
    return render_template('login1.html')

@app.route('/dashboard1')
def dashboard1():
    if 'email' in session:
        produits = []
        try:
            with open('produits.csv', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['email'] == session['email']:
                        produits.append(row)
        except FileNotFoundError:
            pass

        return render_template(
            'dashboard1.html',
            nom=session['nom'],
            entreprise=session['entreprise'],
            email=session['email'],
            produits=produits
        )
    return redirect('/login1')

@app.route('/fournisseur1', methods=['POST'])
def enregistrer_fournisseur1():
    data = request.form
    with open(CSV_FILE1, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            data.get('nom'),
            data.get('entreprise'),
            data.get('email'),
            data.get('motdepasse'),
            data.get('entite'),
            data.get('adresse'),
            data.get('patente'),
            data.get('numero')
        ])
    return render_template('success1.html')

@app.route('/api/dernier_fournisseur1')
def dernier_fournisseur1():
    try:
        with open(CSV_FILE1, 'r', encoding='utf-8') as f:
            lignes = list(csv.reader(f))
            if not lignes:
                return jsonify({})
            dernier = lignes[-1]
            return jsonify({
                'nom': dernier[0],
                'entreprise': dernier[1],
                'email': dernier[2]
            })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/upload_csv1', methods=['POST'])
def upload_csv1():
    try:
        if 'file' not in request.files or 'email' not in session:
            return jsonify({'error': 'Fichier manquant ou utilisateur non connecté'}), 400

        file = request.files['file']
        email = session['email']
        entreprise = session.get('entreprise', 'Fournisseur')

        # Créer le dossier du fournisseur
        dossier_frs = os.path.join(PRODUITS_FRS, entreprise.replace(' ', '_'))
        os.makedirs(dossier_frs, exist_ok=True)

        # Générer un nom de fichier unique
        fichier_path = os.path.join(dossier_frs, f"produits_{date.today()}.csv")

        produits = []
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)

        with open(fichier_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['entreprise', 'image', 'code', 'description', 'famille', 'prix', 'stock'])  # Entêtes

            for row in reader:
                writer.writerow([
                    entreprise,
                    row['image'],
                    row['code'],
                    row['description'],
                    row['famille'],
                    row['prix'],
                    row['stock']
                ])
                produits.append(row)

        return jsonify(produits)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files or 'email' not in session:
        return jsonify({'error': 'Fichier manquant ou utilisateur non connecté'}), 400

    file = request.files['file']
    email = session['email']
    produits = []
    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    reader = csv.DictReader(stream)

    file_exists = os.path.isfile(PRODUITS_FILE)
    with open(PRODUITS_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['email', 'image', 'code', 'description', 'famille', 'prix', 'stock'])

        for row in reader:
            writer.writerow([
                email,
                row['image'],
                row['code'],
                row['description'],
                row['famille'],
                row['prix'],
                row['stock']
            ])
            produits.append(row)
    return jsonify(produits)






# === RUN ===
if __name__ == '__main__':
    app.run(debug=True)
