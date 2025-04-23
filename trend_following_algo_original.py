import requests
from time import sleep
import matplotlib.pyplot as plt
import pandas as pd

s = requests.Session()
s.headers.update({'X-API-key': 'competition-API-key'})

MAX_LONG_EXPOSURE = 72000  # Maximum total number of shares allowed to be held long across all stocks
MAX_SHORT_EXPOSURE = -72000  # Maximum total number of shares allowed to be held short across all stocks
ORDER_LIMIT = 1500  # maximum number of shares per order

WINDOW_SIZE_SHORT = 5    # Short-term moving average window (number of ticks)
WINDOW_SIZE_LONG = 20   # Long-term moving average window (number of ticks)
PRICE_HISTORY = {        # Dictionary to store price history for each ticker
    'OWL': [],
    'CROW': [],
    'DOVE': [],
    'DUCK': []
}

def get_tick(): #the simulation runs on ticks (one per second for 600s)
    resp = s.get('http://localhost:9999/v1/case')
    if resp.ok:
        case = resp.json()
        return case['tick'], case['status']

def get_bid_ask(ticker):
    payload = {'ticker': ticker}
    resp = s.get('http://localhost:9999/v1/securities/book', params=payload)
    if resp.ok:
        book = resp.json()
        bid_side_book = book['bids']
        ask_side_book = book['asks']
        
        bid_prices_book = [item["price"] for item in bid_side_book]
        ask_prices_book = [item['price'] for item in ask_side_book]
        
        if bid_prices_book and ask_prices_book:  # Modified: Added check to prevent index errors
            best_bid_price = bid_prices_book[0]
            best_ask_price = ask_prices_book[0]
            return best_bid_price, best_ask_price
    return None, None  # Added: Return None if data is unavailable

def get_time_sales(ticker):
    payload = {'ticker': ticker}
    resp = s.get('http://localhost:9999/v1/securities/tas', params=payload)
    if resp.ok:
        book = resp.json()
        time_sales_book = [item["quantity"] for item in book]
        return time_sales_book

def get_position(ticker):  # Modified: Changed to get position per ticker
    resp = s.get('http://localhost:9999/v1/securities', params={'ticker': ticker})
    if resp.ok:
        securities = resp.json()
        if securities:
            return securities[0]['position']
    return 0  # Added: Return 0 if position data is unavailable

def get_gross_position():
    resp = s.get ('http://localhost:9999/v1/securities')
    if resp.ok:
        book = resp.json()
        return abs(book[0]['position']) + abs(book[1]['position']) + abs(book[2]['position']) + abs(book[3]['position'])

def get_open_orders(ticker):
    payload = {'ticker': ticker}
    resp = s.get('http://localhost:9999/v1/orders', params=payload)
    if resp.ok:
        orders = resp.json()
        buy_orders = [item for item in orders if item["action"] == "BUY"]
        sell_orders = [item for item in orders if item["action"] == "SELL"]
        return buy_orders, sell_orders

def get_order_status(order_id):
    resp = s.get('http://localhost:9999/v1/orders' + '/' + str(order_id))
    if resp.ok:
        order = resp.json()
        return order['status']

def calculate_sma(prices, window_size):
    if len(prices) >= window_size:
        return sum(prices[-window_size:]) / window_size
    else:
        return None

# This is so that i can base limit order off of how large the SMA change is
def SMA_Differences_ranking(ticker):
    # This big if statement is just to make sure that the SMAs can actually be calculated for each stock
    if (len(PRICE_HISTORY['OWL']) < WINDOW_SIZE_LONG) or (len(PRICE_HISTORY['DOVE']) < WINDOW_SIZE_LONG) or (len(PRICE_HISTORY['CROW']) < WINDOW_SIZE_LONG) or (len(PRICE_HISTORY['DUCK']) < WINDOW_SIZE_LONG):
        return False
    OWL_diff = abs(calculate_sma(PRICE_HISTORY['OWL'], WINDOW_SIZE_LONG) - calculate_sma(PRICE_HISTORY['OWL'], WINDOW_SIZE_SHORT))
    DOVE_diff = abs(calculate_sma(PRICE_HISTORY['DOVE'], WINDOW_SIZE_LONG) - calculate_sma(PRICE_HISTORY['DOVE'], WINDOW_SIZE_SHORT))
    CROW_diff = abs(calculate_sma(PRICE_HISTORY['CROW'], WINDOW_SIZE_LONG) - calculate_sma(PRICE_HISTORY['CROW'], WINDOW_SIZE_SHORT))
    DUCK_diff = abs(calculate_sma(PRICE_HISTORY['DUCK'], WINDOW_SIZE_LONG) - calculate_sma(PRICE_HISTORY['DUCK'], WINDOW_SIZE_SHORT))
    SMA_Differences = { 'OWL': OWL_diff, 'CROW' : CROW_diff, 'DOVE' : DOVE_diff, 'DUCK' : DUCK_diff }
    SMA_Differences_values = sorted(list(SMA_Differences.values()))
    return (SMA_Differences[ticker] == SMA_Differences_values[-1]) or (SMA_Differences[ticker] == SMA_Differences_values[-2])

def main():
    tick, status = get_tick()
    ticker_list = ['OWL', 'CROW', 'DOVE', 'DUCK']

    while status == 'ACTIVE':        

        for i in range(4):  # this is range 4 because there are 4 tickers
            ticker_symbol = ticker_list[i]
            position = get_position(ticker_symbol)
            best_bid_price, best_ask_price = get_bid_ask(ticker_symbol)

            if best_bid_price is None or best_ask_price is None:  # Added: Skip if prices are not available
                continue

            # Mid price
            current_price = (best_bid_price + best_ask_price) / 2

            # Update Price History
            PRICE_HISTORY[ticker_symbol].append(current_price)

            short_sma = calculate_sma(PRICE_HISTORY[ticker_symbol], WINDOW_SIZE_SHORT)
            long_sma = calculate_sma(PRICE_HISTORY[ticker_symbol], WINDOW_SIZE_LONG)

            if short_sma is None or long_sma is None:  # Check if SMAs can be calculated
                continue
            
            if short_sma > long_sma: # Buy Signal 
                            
                if position < MAX_LONG_EXPOSURE:
                    if position >= 0.66*MAX_LONG_EXPOSURE: # gets program to slow down as we reach individual long_exposure limit
                        quantity = min(750, MAX_LONG_EXPOSURE - position)
                    elif get_gross_position() >= 0.66*250000: # if we are getting near the limit and the position is positive, we take a larger sell order larger amount, otherwise we take a smaller amount than normal
                        if position > 0: 
                            quantity = 5000
                        else:
                            quantity = min(750, MAX_LONG_EXPOSURE - position)
                    
                    elif SMA_Differences_ranking(ticker_symbol) == True: # if there is a larger difference in the moving averages with this specific ticker (compared to the others) we take a larger position
                        quantity = min(5000, MAX_LONG_EXPOSURE - position)
                    else:
                        quantity = min(ORDER_LIMIT, MAX_LONG_EXPOSURE - position)
                    resp = s.post('http://localhost:9999/v1/orders', params={
                        'ticker': ticker_symbol,
                        'type': 'LIMIT',
                        'quantity': quantity,
                        'price': best_ask_price,
                        'action': 'BUY'
                    })
                    if resp.ok:
                        print(f"Placed BUY order for {quantity} shares of {ticker_symbol} at {best_ask_price}")
                    else:
                        print(quantity)
            elif short_sma < long_sma:
                # Sell Signal
                if position > MAX_SHORT_EXPOSURE:
                    if position <= 0.66*MAX_SHORT_EXPOSURE: # gets program to slow down as we reach individual short exposure limit
                        quantity = min(750, position - MAX_SHORT_EXPOSURE)
                    elif (get_gross_position() >= 0.66*250000): # if we are getting near limit and position is negative, we take a larger buy order, otherwise we take a smaller than usual one
                        if position < 0:
                            quantity = 5000
                        else:
                            quantity = min(750, position - MAX_SHORT_EXPOSURE)
                        
                        
                    elif SMA_Differences_ranking(ticker_symbol) == True: #if there is a larger difference in the moving averages with this specific ticker (compared to the others) we take a larger position
                        quantity = min(5000, position - MAX_SHORT_EXPOSURE)
                    else:
                        quantity = min(ORDER_LIMIT, position - MAX_SHORT_EXPOSURE)
                    #print(quantity)
                    resp = s.post('http://localhost:9999/v1/orders', params={
                        'ticker': ticker_symbol,
                        'type': 'LIMIT',
                        'quantity': quantity,
                        'price': best_bid_price,
                        'action': 'SELL'
                    })
                    if resp.ok:
                        print(f"Placed SELL order for {quantity} shares of {ticker_symbol} at {best_bid_price}")
                    else:
                        print(quantity)

            

            s.post('http://localhost:9999/v1/commands/cancel', params={'ticker': ticker_symbol})  # this cancels any open orders for the stock
        sleep(0.75) #so program only runs once per tick
        tick, status = get_tick()

    y_values1 = PRICE_HISTORY['OWL']  
    y_values2 = PRICE_HISTORY['CROW']
    y_values3 = PRICE_HISTORY['DOVE']
    y_values4 = PRICE_HISTORY['DUCK']

    # First Ticker graph
    plt.figure(1)
    plt.plot(y_values1, label="Graph 1", color="blue")
    plt.title("OWL")
    plt.xlabel("Time")
    plt.ylabel("Avg Price")
    plt.legend()

    # Second Ticker graph
    plt.figure(2)
    plt.plot(y_values2, label="Graph 2", color="green")
    plt.title("CROW")
    plt.xlabel("Time")
    plt.ylabel("Avg Price")
    plt.legend()

    # Third Ticker graph
    plt.figure(3)
    plt.plot(y_values3, label="Graph 3", color="red")
    plt.title("DOVE")
    plt.xlabel("Time")
    plt.ylabel("Avg Price")
    plt.legend()

    # Fourth Ticker graph
    plt.figure(4)
    plt.plot(y_values4, label="Graph 4", color="yellow")
    plt.title("DUCK")
    plt.xlabel("Time")
    plt.ylabel("Avg Price")
    plt.legend()

    # Show all graphs
    plt.show()

if __name__ == '__main__':
    main()
