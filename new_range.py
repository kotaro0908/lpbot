    # 現在のレンジ情報
    current_range = None
    if current_nft:
        # まずDBから取得を試みる
        range_info = conn.execute("""
                                  SELECT new_tick_lower, new_tick_upper
                                  FROM rebalance_history
                                  WHERE new_nft_id = ?
                                  ORDER BY timestamp DESC
                                      LIMIT 1
                                  """, (current_nft,)).fetchone()
        if range_info and range_info['new_tick_lower'] is not None:
            print(f"DEBUG: range_info = {range_info}")
            price_range = ticks_to_price_range(range_info['new_tick_lower'], range_info['new_tick_upper'])
            current_range = {
                'lower': range_info['new_tick_lower'],
                'upper': range_info['new_tick_upper'],
                'lower_price': price_range['lower_price'],
                'upper_price': price_range['upper_price'],
                'range_width_percent': price_range['range_width_percent']
            }
        else:
            # DBになければrange_config.jsonから取得
            try:
                with open('/root/lpbot/range_config.json', 'r') as f:
                    range_config = json.load(f)
                    price_range = ticks_to_price_range(range_config['lower_tick'], range_config['upper_tick'])
                    current_range = {
                        'lower': range_config['lower_tick'],
                        'upper': range_config['upper_tick'],
                        'lower_price': price_range['lower_price'],
                        'upper_price': price_range['upper_price'],
                        'range_width_percent': price_range['range_width_percent']
                    }
                    print(f"DEBUG: range_config.jsonから取得 - {current_range}")
            except Exception as e:
                print(f"レンジ情報取得エラー: {e}")
