import os
import boto3

from math import floor
from pymongo import MongoClient, DESCENDING
from boto3.session import Session
from dateutil.tz import gettz
from datetime import datetime
from datadiff import diff
from urllib.request import urlopen
from json import dumps

accesskey = os.environ.get('AWS_ACCESS_KEY_ID')
secretkey = os.environ.get('AWS_SECRET_ACCESS_KEY')
region = os.environ.get('AWS_DEFAULT_REGION')
arns = os.environ.get('AWS_DEVICE_FARM_ARNS').split(',')
mongo_url = os.environ.get('MONGOLAB_URI')
slack_url = os.environ.get('SLACK_WEBHOOK_URL')

session = Session(aws_access_key_id=accesskey,
                  aws_secret_access_key=secretkey,
                  region_name=region)
devicefarm = boto3.client('devicefarm')

client = MongoClient(mongo_url, tz_aware=True)
db = client.get_default_database()

tz = gettz('UTC')

def main():
    for arn in arns:
        check_update(arn)

def check_update(arn):
    res = devicefarm.list_runs(arn=arn)
    if res['ResponseMetadata']['HTTPStatusCode'] != 200:
        return

    res['runs'] = [ensure_utc(run) for run in res['runs']]

    collection = db[arn]
    cursor = collection.find(limit=1, sort=[('_id', DESCENDING)])
    if cursor.count() == 0:
        res['created'] = datetime.now(tz)
        collection.insert_one(res)
        return

    data_runs = [ensure_utc(run) for run in cursor[0]['runs']]
    if not diff(res['runs'], data_runs):
        return

    res['created'] = datetime.now(tz)
    collection.insert_one(res)

    res['runs'].reverse()
    for i, run in enumerate(res['runs']):
        old_run = find_run_by_arn(data_runs, run['arn'])
        if old_run == None and i < 2 and run['status'] == 'COMPLETED':
            continue

        if run['status'] != 'COMPLETED':
            continue

        if old_run == None or run['status'] != old_run['status']:
            notify_to_slack(run)

def ensure_utc(run):
    created = run['created']
    if created.tzinfo != tz:
        created = created.astimezone(tz)

    microsecond = floor(created.microsecond / 1000) * 1000
    created = created.replace(microsecond=microsecond)
    run['created'] = created

    return run

def find_run_by_arn(runs, arn):
    matched = [run for run in runs if run['arn'] == arn]
    return None if len(matched) == 0 else matched[0]

def notify_to_slack(run):
    circle = ':white_circle: ' if run['result'] == 'PASSED' else ':red_circle: '
    text = circle + 'AWS Device Farm Test name: {0}, became: {1}, with result: {2}'.format(run['name'], run['status'], run['result'])
    data = {'text': text}
    urlopen(slack_url, data=dumps(data).encode('utf8'))

if __name__ == '__main__':
    main()
