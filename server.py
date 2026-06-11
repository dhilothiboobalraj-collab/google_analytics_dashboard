import os
from flask import Flask, send_from_directory, Response

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def serve_dashboard():
    return send_from_directory('.', 'dashboard.html')

@app.route('/data')
def serve_data():
    csv_path = os.path.join('output', 'dashboard_combined.csv')
    if not os.path.exists(csv_path):
        return Response('CSV not found', status=404)
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        data = f.read()
    return Response(data, mimetype='text/csv')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=False)
