import time, os, requests, json

# ============================================================
# CONFIGURACIÓN (mejor usar variables de entorno en Render)
# ============================================================
API_KEY   = os.environ.get("CAPITAL_API_KEY", "JxByED4fKEQbXK3Z")
LOGIN     = os.environ.get("CAPITAL_LOGIN", "adriansg1428@gmail.com")
PASSWORD  = os.environ.get("CAPITAL_PASSWORD", "AdrianBot!25")
EPIC      = "SOLUSD"

LOT_SIZE       = 0.1
TRAILING_PIPS  = 20
OB_LEVEL       = 85
OS_LEVEL       = 15
STOCH_LENGTH   = 20
STOCH_SMOOTH_K = 3
STOCH_SMOOTH_D = 3

BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1/"

# ============================================================
# SESIÓN Y AUTENTICACIÓN
# ============================================================
session = requests.Session()
session.headers.update({
    "X-CAP-API-KEY": API_KEY,
    "Content-Type": "application/json"
})

def authenticate():
    resp = session.post(BASE_URL + "session", json={
        "identifier": LOGIN,
        "password": PASSWORD
    })
    if resp.status_code != 200:
        raise Exception(f"Error autenticación: {resp.json()}")
    data = resp.json()
    session.headers.update({
        "X-SECURITY-TOKEN": data["oauthToken"],
        "CST": resp.headers["CST"]
    })
    print("✔ Autenticado en Capital.com")

# ============================================================
# FUNCIONES DE MERCADO Y ÓRDENES
# ============================================================
def get_prices():
    resp = session.get(BASE_URL + f"markets/{EPIC}")
    data = resp.json()
    return data["snapshot"]["bid"], data["snapshot"]["offer"]

def open_position(direction):
    body = {
        "epic": EPIC,
        "expiry": "DFB",
        "direction": direction,
        "size": str(LOT_SIZE),
        "orderType": "MARKET",
        "guaranteedStop": False,
        "trailingStop": True,
        "trailingStopDistance": str(TRAILING_PIPS)
    }
    resp = session.post(BASE_URL + "positions", json=body)
    print(f"→ {direction} abierta:", resp.json())

def close_all_positions():
    resp = session.get(BASE_URL + "positions")
    if resp.status_code == 200:
        positions = resp.json().get("positions", [])
        for pos in positions:
            if pos["position"]["epic"] == EPIC:
                session.delete(BASE_URL + f"positions/{pos['position']['dealId']}")
                print("→ Posición cerrada")

def has_open_position():
    resp = session.get(BASE_URL + "positions")
    if resp.status_code == 200:
        positions = resp.json().get("positions", [])
        for pos in positions:
            if pos["position"]["epic"] == EPIC:
                return pos["position"]["direction"]
    return None

# ============================================================
# CÁLCULO DEL ESTOCÁSTICO
# ============================================================
class Stochastic:
    def __init__(self, length=20, smooth_k=3):
        self.length = length
        self.smooth_k = smooth_k
        self.prices = []
        self.rawk_hist = []

    def update(self, price):
        self.prices.append(price)
        if len(self.prices) > self.length + self.smooth_k:
            self.prices.pop(0)

    def compute(self):
        if len(self.prices) < self.length:
            return None
        closes = self.prices[-self.length:]
        low, high = min(closes), max(closes)
        if high == low:
            raw_k = 50.0
        else:
            raw_k = 100.0 * (closes[-1] - low) / (high - low)
        self.rawk_hist.append(raw_k)
        if len(self.rawk_hist) > self.smooth_k:
            self.rawk_hist.pop(0)
        if len(self.rawk_hist) < self.smooth_k:
            return None
        return sum(self.rawk_hist) / self.smooth_k

# ============================================================
# BUCLE PRINCIPAL
# ============================================================
def main():
    authenticate()
    stoch = Stochastic(STOCH_LENGTH, STOCH_SMOOTH_K)
    last_k = None
    print("▶ Bot iniciado. Esperando señales...")

    while True:
        try:
            bid, ask = get_prices()
            mid = (bid + ask) / 2.0
            stoch.update(mid)
            k = stoch.compute()
            if k is None:
                time.sleep(1)
                continue

            direction = has_open_position()
            print(f"SOL/USD: {mid:.5f} | Stoch %K: {k:.2f} | {'Posición: ' + direction if direction else 'Sin posición'}")

            if direction is None and last_k is not None:
                if last_k <= 50 and k > 50:
                    open_position("BUY")
                    time.sleep(5)
                    continue
                elif last_k >= 50 and k < 50:
                    open_position("SELL")
                    time.sleep(5)
                    continue

            if direction == "BUY" and k >= OB_LEVEL:
                close_all_positions()
                print("TP Long alcanzado")
            elif direction == "SELL" and k <= OS_LEVEL:
                close_all_positions()
                print("TP Short alcanzado")

            last_k = k
            time.sleep(3)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()