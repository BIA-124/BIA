from flask import Flask, request, jsonify
import pandas as pd
import io
import requests

app = Flask(__name__)

@app.route('/parse_csv', methods=['POST'])
def parse_csv():
    if 'file' in request.files:
        file = request.files['file']
        df = pd.read_csv(file)
    else:
        url = request.json.get('url')
        r = requests.get(url)
        df = pd.read_csv(io.StringIO(r.text))
    produits = df['nom_produit'].dropna().unique().tolist()
    return jsonify(produits=produits)

if __name__ == '__main__':
    app.run(debug=True)
