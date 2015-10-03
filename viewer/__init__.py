import os

from flask import Flask, Response, jsonify, abort
from pymongo import MongoClient, DESCENDING
from bson.json_util import dumps

mongo_url = os.environ.get('MONGOLAB_URI')
arns = os.environ.get('AWS_DEVICE_FARM_ARNS').split(',')

app = Flask(__name__)

client = MongoClient(mongo_url, tz_aware=True)
db = client.get_default_database()

@app.route('/')
def list_arns():
    return jsonify(arns=arns)

@app.route('/arns/<arn>/logs')
def list_logs(arn):
    if arn not in arns:
        abort(404)

    cursor = db[arn].find(limit=20, sort=[('_id', DESCENDING)])
    return Response(dumps({'logs': cursor}), mimetype='application/json')

if __name__ == '__main__':
    app.run()
