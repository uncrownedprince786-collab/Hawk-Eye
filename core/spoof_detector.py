import numpy as np
from collections import defaultdict
import time

class SpoofDetector:
    def __init__(self):
        self.snapshots = defaultdict(list)

    def update(self, symbol, bids, asks):
        self.snapshots[symbol].append((time.time(), bids, asks))
        if len(self.snapshots[symbol]) > 5:
            self.snapshots[symbol].pop(0)

    def get_spoof_alert(self, symbol):
        snaps = self.snapshots.get(symbol, [])
        if len(snaps) < 3:
            return "Insufficient order book history."
        latest_time, latest_bids, latest_asks = snaps[-1]
        prev_time, prev_bids, prev_asks = snaps[-2]
        alert = ""
        # Check bids
        for price, qty in prev_bids:
            if len(prev_bids) >= 10 and qty > 5 * np.mean([q for _, q in prev_bids[:10]]):
                if not any(abs(p - price) < price*0.001 and abs(q - qty) < qty*0.01 for p, q in latest_bids):
                    alert += f" Large bid {qty:.2f} @ {price:.2f} removed suddenly. "
        # Check asks
        for price, qty in prev_asks:
            if len(prev_asks) >= 10 and qty > 5 * np.mean([q for _, q in prev_asks[:10]]):
                if not any(abs(p - price) < price*0.001 and abs(q - qty) < qty*0.01 for p, q in latest_asks):
                    alert += f" Large ask {qty:.2f} @ {price:.2f} removed suddenly. "
        if alert:
            return "Spoofing detected: " + alert.strip()
        return "No spoofing detected."