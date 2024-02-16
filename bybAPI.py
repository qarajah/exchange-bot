from settings import API_KEY, API_SECRET, LOCAL, ASSETS
import json
from pybit.unified_trading import HTTP

session = HTTP(
    testnet=False,
    api_key=API_KEY,
    api_secret=API_SECRET,
)


def getCat(_sym):
    _cat = 'inverse'
    if 'USDT' in _sym:
        _cat = 'linear'
    return _cat

def getFunds():
    response = session.get_wallet_balance(
        accountType="UNIFIED",
        coin="USDT",
    )
    totalEquity = response['result']['list'][0]['totalEquity']
    print(totalEquity)
    return totalEquity

def cancelAPI(_sym, _id):
    resp = session.cancel_order(
        category="linear",
        symbol=_sym,
        orderId=_id,
    )
    return json.dumps(resp)

def checkTrades():
    tradeDict={}
    for _sym in ASSETS.keys():
        print(_sym)
        resp = session.get_positions(
            category="linear",
            symbol=_sym
        )

        trade = resp['result']['list'][0]
        _size = trade['positionBalance']
        if _size != '' and _size != '0':
            tradeDict[_sym] = {
                'lev' : trade['leverage'],
                'size' : _size,
                'entry' : trade['avgPrice'],
                'side' : trade['side'],
                'profit' : trade['takeProfit'],
                'stop' : trade['stopLoss'],
                'time' : trade['updatedTime'],
                'gains' : trade['unrealisedPnl']
            }
            print(resp)
    print(tradeDict)
    return tradeDict

def getLast(_sym):
    data = session.get_tickers(
        category="linear",
        symbol=_sym,
        )
    last_price = float(data['result']['list'][0]['lastPrice'])

    return last_price



def checkOrders():
    orderDict={}
    print(ASSETS.keys())
    for _sym in ASSETS.keys():
        resp = session.get_open_orders(
            category="linear",
            symbol=_sym
        )

        last_price = getLast(_sym)


        orders = resp['result']['list']

        if len(orders) > 0:
            for order in orders:
                print(order)
                if _sym not in orderDict:
                    orderDict[_sym] = []

                if order['price'] != '' and order['price'] != '0':
                    orderDict[_sym].append({
                        'last_price' : last_price,
                        'entry' : float(order['price']),
                        'profit' : order['takeProfit'],
                        'stop' : order['stopLoss'],
                        'time' : order['updatedTime'],
                        'side' : order['side'],
                        'qty' : order['qty'],
                        'id' : order['orderId'],
                        'reduce' : order['reduceOnly']
                    })

    return orderDict

def setSLTP(_sym, _profit, _stop):
    _cat = getCat(_sym)
    resp =session.set_trading_stop(
            category=_cat,
            symbol=_sym,
            takeProfit=str(_profit),
            stopLoss=str(_stop),
            # tpTriggerBy="MarkPrice",
            # slTriggerB="IndexPrice",
            # tpslMode="Partial",
            # tpOrderType="Limit",
            # slOrderType="Limit",
            # tpSize="50",
            # slSize="50",
            # tpLimitPrice="0.57",
            # slLimitPrice="0.21",
            positionIdx=0
        )
    return resp

def autoAdjust(_sym, _stop, _profit, _entry, _side):
    last_price = getLast(_sym)
    action = False
    if _side == 'Buy':
        _diff = _profit - _entry
        if last_price > _entry + _diff*0.7:
            newStop = _entry + _diff*0.4
            if _stop != newStop:
                _stop = newStop
                action = True
        elif last_price > _entry + _diff*0.4 and _stop < _entry:
            _stop = _entry
            action = True
    else:
        _diff = _entry - _profit
        if last_price < _entry - _diff*0.7:
            newStop = _entry - _diff*0.4
            if _stop != newStop:
                _stop = newStop
                action = True

        elif last_price < _entry - _diff*0.4 and _stop > _entry:
            _stop = _entry
            action = True

    if action:
        resp = setSLTP(_sym, _profit, _stop)
        placeReduce(_sym)
        return resp
    else:
        return False

def adjustAPI(_sym, _mode, _stop, _profit, _entry, _side, _vwap):
    print('ADJUST 1', _mode, _sym, _entry, _profit, _stop)
    _stop = float(_stop)
    _entry = float(_entry)
    if _profit != '':
        _profit = float(_profit)

    _adjust = _mode.split('-')[0]
    _action = _mode.split('-')[1]
    last_price = getLast(_sym)

    if _adjust == 'profit' and _action == 'cancel':
        _profit == last_price
    elif _adjust == 'profit' and _action == 'reduce' and _profit != '':
        if _side == 'Buy':
            _profit = _entry + (_profit - _entry)/2
        else:
            _profit = _entry - (_entry - _profit)/2
    elif _adjust == 'profit' and _action == 'prop':
        if _side == 'Buy':
            _profit = _entry + (_entry - _stop)*2
        else:
            _profit = _entry - (_stop - _entry)*2
    elif _adjust == 'profit' and _action == 'vwap':
        print('VWAP ', _vwap)
        if _side == 'Buy' and _vwap != 0 and _vwap > float(_entry):
            _profit = _vwap
        elif _vwap != 0 and _vwap < float(_entry):
            _profit = _vwap

        if _vwap != 0:
            _profit = _vwap

    elif _adjust == 'stop' and _action == 'reduce':
        if _side == 'Buy':
            _stop = _entry - (_entry - _stop)/2
        else:
            _stop = _entry + (_stop -_entry)/2
    elif _adjust == 'stop' and _action == 'profit':
        if _side == 'Buy':
            _stop = _entry + (last_price - _entry)/2
        else:
            _stop = _entry - (_entry - last_price)/2
    elif _adjust == 'stop' and _action == 'break':
        _stop = _entry

    print('ADJUST 2', _mode, _sym, _entry, _profit, _stop)


    resp = setSLTP(_sym, _profit, _stop)

    return resp


def getOrders(_sym, dataReq):
    _cat = getCat(_sym)

    response = (session.get_open_orders(
        category=_cat,
        symbol=_sym,
    ))

    ok = response['retMsg']
    print(f'getOrders {ok}')
    # print(response['result'])

    data = response['result']['list']

    if dataReq:
        return data
    else:
        if len(data) == 0:
            print(f'No orders on {_sym}')
            return False
        else:
            return True


def getPosition(_sym):
    _cat = getCat(_sym)

    response = (session.get_positions(
        category=_cat,
        symbol=_sym,
    ))
    ok = response['retMsg']
    print(f'getPosition {ok}')
    #print(f'getPosition {str(response['retMsg'])}')

    data = response['result']['list'][0]

    dataDict = {
        'side' : data['side'],
        'size' : data['size'],
        'value' : data['positionValue'],
        'price' : data['avgPrice'],
        'lev' : data['leverage'],
        'stop' : data['stopLoss'],
        'profit' : data['takeProfit'],
        'time' : data['updatedTime']
        }

    # print(dataDict)

    if dataDict['value'] == '' or float(dataDict['value']) == 0:
        print(f'No positions on {_sym}')
        return False

    for d in dataDict:
        print(d, dataDict[d])

    #print(response)
    return dataDict

def checkValid(_sym):
    _cat = getCat(_sym)

    if getPosition(_sym):
        print(f'No Trade Action: Positions on {_sym}')
        return True
    elif getOrders(_sym, False):
        print(f'No Trade Action: Orders on {_sym}')
        return True
    else:
        return False

def getHL(side, current, stop, mode):

    now = datetime.now()
    minutes = 5
    timestamp = int(datetime.timestamp(now)) - int(minutes)*60
    data = session.query_kline(symbol="BTCUSD", interval="1", from_time=str(timestamp))['result']

    hAry = []
    lAry = []

    for i in range(0, len(data)):
        hAry.append(int(data[i]['high'].split('.')[0]))
        lAry.append(int(data[i]['low'].split('.')[0]))

    mHi = max(hAry)
    mLow = min(lAry)

    if side == 'Buy':
        distance = abs(current - mLow)
        if distance > stop:
            stop_loss = current - stop
        else:
            stop_loss = mLow - 45

    if side == 'Sell':
        distance = abs(current - mHi)
        if distance > stop:
            stop_loss = current + stop
        else:
            stop_loss = mHi + 45


    return stop_loss


def setLeverage(_sym, _entry, _stop, _risk):
    _cat = getCat(_sym)

    diff = abs(_entry - _stop)
    per = (diff/_entry)*100

    _lev = round(_risk/per, 1)
    if _lev > 30:
        print(f'set lev on {_sym} at {_lev} : Lev too high')
        return False

    try:
        response = session.set_leverage(
            category=_cat,
            symbol=_sym,
            buyLeverage=str(_lev),
            sellLeverage=str(_lev),
        )
        ok = response['retMsg']
        print(f'set lev on {_sym} at {_lev} : {ok}')

        if ok == 'OK':
            return _lev
        else:
            return False

    except:
        print(f'set lev on {_sym} at {_lev} : Not modified')
        return _lev



    else:
        return False


def getQty(_sym, _amt, _lev, _entry):
    _cat = getCat(_sym)

    info = session.get_instruments_info(
        category=_cat,
        symbol=_sym,
    )
    qtyStep = info['result']['list'][0]['lotSizeFilter']['qtyStep']

    last_entry = getLast(_sym)
    print(last_entry)

    if _entry == 0:
        _entry = last_entry

    qty = (_amt / _entry) * _lev

    checkQty = round(qty * 10000)/10000

    excess = checkQty%float(qtyStep)

    rQty = qty - excess

    print(f'QTY: {_amt} / {_entry} / {_lev} / {qtyStep} / {rQty}')

    return rQty

def placeOrder(_sym, _type, _side, _entry, _amt, _stop, _profit, _risk, _reduce):
    _cat = getCat(_sym)

    print('CHECK VALID')

    if checkValid(_sym):
        return 'Check Valid Fail'

    print('SET LEV')

    _lev = setLeverage(_sym, _entry, _stop, _risk)

    if _lev:
        _qty = getQty(_sym, _amt, _lev, _entry)
    else:
        return 'Set Lev Fail'

    _pidx = 0
    # if _side == 'Sell':
    #     _pidx = 2

    try:
        print('TRY ORDER', _lev, _qty)

        response = session.place_order(
                category=_cat,
                symbol=_sym,
                side=_side,
                orderType=_type,
                qty=str(round(_qty, 3)),
                price=str(_entry),
                stopLoss=str(_stop),
                takeProfit=str(_profit),
                positionIdx=_pidx,
                reduceOnly=False
            )

        placeReduce(_sym)

        return response

    except Exception as e:
        return str(e)


def placeReduce(_sym):
    _cat = getCat(_sym)
    _type = 'Limit'

    position = getPosition(_sym)
    orders = getOrders(_sym, True)

    currentPrice = 0
    currentId = 0

    print('ORDERS REDUCE', orders)

    for o in orders:
        print(orders[0])
        if o['orderType'] == 'Limit':
            currentPrice = o['price']
            currentId = o['orderId']

    if not position:
        print(f'No Positions on {_sym}')
        return False

    _side = position['side']
    _stop = position['stop']
    _profit = position['profit']
    _lev = position['lev']
    _value = position['value']
    _size = position['size']


    info = session.get_instruments_info(
        category=_cat,
        symbol=_sym,
    )

    tickSize = info['result']['list'][0]['priceFilter']['tickSize']
    print('TICK REDUCE', tickSize)

    if currentPrice != 0 and abs(float(currentPrice) - float(_profit)) <= float(tickSize)*2:
        print('NO REDUCE ADJUST')
        return False


    _oppSide = 'Sell'

    if _side == 'Sell':
        _oppSide = 'Buy'

    if _side == 'Buy':
        _entry = float(_profit) - float(tickSize)*2
    else:
        _entry = float(_profit) + float(tickSize)*2

    _pidx = 0
    # if _side == 'Sell':
    #     _pidx = 2
    #print('PDX', _pidx)
    try:
        print('TRY REDUCE: ' + _sym)
        if currentPrice != 0:
            response = session.amend_order(
                    category=_cat,
                    symbol=_sym,
                    orderId=currentId,
                    price=str(_entry)
                )
        else:
            response = session.place_order(
                    category=_cat,
                    symbol=_sym,
                    side=_oppSide,
                    orderType=_type,
                    qty=str(_size),
                    price=str(_entry),
                    positionIdx=_pidx,
                    reduceOnly=True
                )

        return True

    except Exception as e:
        print('REDUCE EXCEPTON: ' + _sym, str(e))
        return False



# getPosition('ALGOUSDT')

# getOrders('ALGOUSDT')

# print(getQty('ALGOUSDT', 100, 5))

info = session.get_instruments_info(
        category='linear',
        symbol='NEARUSDT',
    )

tickSize = info['result']['list'][0]['priceFilter']['tickSize']
print('TICK', tickSize)

symx = 5
_sym = 'USDT'
_side = 'Sell'
_type = 'Limit'
_entry = 2393
_stop = 2403
_profit = 2381
_amt = 100
_risk = 4


data = {"code":"324","side":"Sell","entry":"0.001734","stop":"0.001791","profit":"0.001677","risk":"10","amt":"100","type":"Limit","asset":"REEFUSDT"}

_sym = data['asset']
_side = data['side']
_type = data['type']
_entry = float(data['entry'])
_stop = float(data['stop'])
_profit = float(data['profit'])
_amt = int(data['amt'])
_risk = int(data['risk'])



# if LOCAL:
#     #placeOrder(_sym,_type, _side, _entry, _amt, _stop, _profit, _risk)
#     placeReduce('ALGOUSDT')


# getQty(_sym, _amt, 3.6, 0)

## setLeverage('MATICUSDT', 'linear')