from flask import Flask, request, render_template, jsonify, abort
import json
import time
import redis
import requests
from datetime import datetime
from settings import SECRET_KEY, CODE, DEBUG, auth_required, TG_TOKEN, TG_CHAT, r
# from exchangeAPI import apiFunds, apiTicker, apiOrder
from bybAPI import *

import logging
# from logger.handlers import SysLogHandler

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = DEBUG


##logging.basicConfig(level=logging.warning, filename="log.log", filemode="w", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logger.warning('Test Logger App')

@app.route('/')
@auth_required
def home():

    context = {}

    return render_template('trading.html', **context)


def addAlert(instrument, msg):
    errors = json.loads(r.get('errors'))

    now = datetime.now()
    date_time = now.strftime("%m/%d/%Y, %H:%M:%S")


    if instrument not in errors:
        errors['misc'].insert(0, msg + '//' + date_time)
        instrument = 'misc'

    errorList = errors[instrument]
    errorList.insert(0, msg + '//' + date_time)


    r.set('errors', json.dumps(errors))
    return True


def sendMessage(m):
    url_string = 'https://api.telegram.org/bot' + TG_TOKEN + '/sendMessage?chat_id=' + str(TG_CHAT)
    base_url = url_string + '&text="{}"'.format(m)
    print(base_url)
    requests.get(base_url)
    return True

@app.route("/auto", methods=['POST'])
def checkAuto():
    _sym = None
    try:
        _sym = request.form ['sym']
        print('autoSwitch', _sym)
    except:
        print('autoCheck No _sym')

    autoDict = {}
    if not r.get('auto'):
        r.set('auto', json.dumps(autoDict))
    else:
        autoDict = json.loads(r.get('auto'))

    orderDict = checkOrders()
    for a in orderDict:
        if a not in autoDict:
            autoDict[a] = True

    if _sym and _sym in autoDict:
        autoDict[_sym] = not autoDict[_sym]
        r.set('auto', json.dumps(autoDict))

    return autoDict



@app.route("/ping", methods=['POST'])
def ping_webhook():
    try:
        print(request.data)
        bDec = request.data.decode("utf-8")
        print(bDec)
        data = json.loads(bDec)
        r.set('vwaps', json.dumps(data))
    except Exception as e:
        print('PING EXCEPTION', e)


    trades = checkTrades()
    rTrades = {}

    if r.get('trades'):
        rTrades = json.loads(r.get('trades'))

    autoDict = checkAuto()

    for t in trades:
        try:

            if autoDict[t]:
                _sym = t
                _side = trades[t]['side']
                _profit = float(trades[t]['profit'])
                _entry = float(trades[t]['entry'])
                _stop = float(trades[t]['stop'])
                print('AUTO TRY ', t, _stop, _profit, _entry, _side)
                resp = autoAdjust(_sym, _stop, _profit, _entry, _side)
                print('AUTO RESULT', resp)
                if resp != False:
                    sendMessage('AUTO ACTION ON ' + _sym + json.dumps(resp) )
            else:
                sendMessage('NO AUTO ACTION ON ' + t )
        except Exception as e:
            print('AUTO EXCEPTION ' + _sym, e)

        if t not in rTrades:
            sendMessage('TRADE OPEN ON ' + t)
    for t in rTrades:
        if t not in trades:
            sendMessage('TRADE CLOSED ON ' + t)

    r.set('trades', json.dumps(trades))


    return 'PING'

@app.route("/webhook", methods=['POST'])
def tradingview_webhook():

    data = None

    try:
        data = json.loads(request.data)
    except Exception as e:
        logger.warning('DATA LOAD EXCEPTION ' + str(e))
        addAlert('tradingview', 'Invalid json data')
        return 'ERROR'
    logger.warning('TV DATA' +  json.dumps(data))

    try:
        ##logger.warning(data['TVCODE'])
        if not data['code']:
            addAlert('tradingview', 'No TVCODE found in webhook alert')
            return 'ERROR'
        elif int(data['code']) != int(CODE):
            addAlert('tradingview', 'TVCODE in webhook alert is incorrect')
            return 'ERROR'
        else:
            logger.warning('CODE SUCCESS')

    except Exception as e:
        logger.warning('TV CODE EXCEPTION ' + str(e))

    _sym = data['asset']
    _side = data['side']
    _type = data['type']
    _entry = float(data['entry'])
    _stop = float(data['stop'])
    _profit = float(data['profit'])
    _amt = int(data['amt'])
    _risk = int(data['risk'])

    try:
        _reduce = False
        resp = placeOrder(_sym,_type, _side, _entry, _amt, _stop, _profit, _risk, _reduce)
        tag = resp
        if type(resp) == dict:
            tag = resp['retMsg']
        m = 'TRADE RESULT ' + _sym + ' ' + _side + ' ' + tag
        logger.warning(m)
        sendMessage(m)
    except Exception as e:
        m = 'TRADE ERROR ' + _sym + ' ' + _side + ' ' + str(e)
        logger.warning(m)
        sendMessage(m)

    return 'TV WEBHOOK COMPLETE'


@app.route('/getData', methods=['POST'])
def getData():
    pw = request.form ['pw']
    if int(pw) != int(CODE):
        return {'error' : 'authentication code input required'}

    # errors = json.loads(r.get('errors'))

    # if 'misc' not in errors:
    #     errors['misc'] = []
    #     r.set('errors', json.dumps(errors))

    dataOBJ = {
        'funds' : getFunds(),
        'misc' : None,
        'assets' : checkTrades(),
        'orders' : checkOrders(),
        'auto' : checkAuto()
    }

    return json.dumps(dataOBJ)

def getVWAP(tickerusdt):
    vwapsGet = r.get('vwaps')

    ticker = tickerusdt.split('USDT')[0]

    if not vwapsGet:
        r.set(vwapsGet, json.dumps({ticker:"0/0"}))
        print('NO VWAPS', ticker)
        return 0
    else:
        vwaps = json.loads(vwapsGet)
        print(vwaps)
        print(ticker, ticker in vwaps)
        if ticker in vwaps:
            vwap_D = vwaps[ticker].split('/')[0]
            vwap_W = vwaps[ticker].split('/')[1]
            return float(vwap_D)
        else:
            return 0

@app.route('/adjustOrder', methods=['POST'])
def adjustOrder():
    pw = request.form ['pw']
    _sym = request.form ['_sym']
    _mode = request.form ['_mode']
    _stop = request.form ['_stop']
    _profit = request.form ['_profit']
    _entry = request.form ['_entry']
    _side = request.form ['_side']
    if int(pw) != int(CODE):
        return {'error' : 'authentication code input required'}

    _vwap = getVWAP(_sym)

    result = adjustAPI(_sym, _mode, _stop, _profit, _entry, _side, _vwap)

    dataOBJ = {
        'response' : result
    }

    return json.dumps(dataOBJ)


@app.route('/cancelOrder', methods=['POST'])
def cancelOrder():
    _sym = request.form['sym']
    _id = request.form['id']
    print(_sym, _id)
    cancel = cancelAPI(_sym, _id)
    return cancel


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)