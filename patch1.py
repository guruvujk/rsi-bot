content = open("upstox_orders.py", "r", encoding="utf-8").read()

insert = """
    # Auto-save position to DB
    try:
        from db_state import get_conn as _gc
        _conn = _gc()
        _cur = _conn.cursor()
        _cur.execute(
            "INSERT INTO upstox_positions "
            "(symbol, itype, qty, buy_price, ltp, sl_price, tp_price, is_open, broker, source, paper_mode, synced_at) "
            "VALUES (%s,'STOCK',%s,%s,%s,%s,%s,TRUE,'Upstox','upstox',FALSE,NOW())",
            (symbol, qty, filled_price, filled_price, sl_price, target_price)
        )
        _conn.commit()
        _cur.close()
        print(f"  [DB] Position saved: {symbol} @ {filled_price}")
    except Exception as _e:
        print(f"  [DB] Save failed: {_e}")
"""

marker = '    return {\n        "success"     : True,'
content = content.replace(marker, insert + marker)
open("upstox_orders.py", "w", encoding="utf-8").write(content)
print("Done")
