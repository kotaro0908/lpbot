CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE fund_changes
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              change_type
                              TEXT
                              NOT
                              NULL,
                              amount_usd
                              REAL
                              NOT
                              NULL,
                              eth_balance
                              REAL,
                              weth_balance
                              REAL,
                              usdc_balance
                              REAL,
                              total_value_usd
                              REAL,
                              trigger_action
                              TEXT,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
CREATE TABLE swap_history
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              from_token
                              TEXT
                              NOT
                              NULL,
                              to_token
                              TEXT
                              NOT
                              NULL,
                              amount
                              REAL
                              NOT
                              NULL,
                              swap_direction
                              TEXT
                              NOT
                              NULL,
                              tx_hash
                              TEXT,
                              success
                              BOOLEAN
                              DEFAULT
                              1,
                              error_message
                              TEXT,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
CREATE TABLE gas_retry_history
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              function_name
                              TEXT
                              NOT
                              NULL,
                              attempt
                              INTEGER
                              NOT
                              NULL,
                              gas_limit
                              INTEGER
                              NOT
                              NULL,
                              gas_multiplier
                              REAL
                              NOT
                              NULL,
                              success
                              BOOLEAN
                              DEFAULT
                              0,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
CREATE TABLE lp_creation_history
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              tx_hash
                              TEXT,
                              gas_used
                              INTEGER,
                              events
                              INTEGER,
                              tick_lower
                              INTEGER,
                              tick_upper
                              INTEGER,
                              amount_weth
                              REAL,
                              amount_usdc
                              REAL,
                              success
                              BOOLEAN
                              DEFAULT
                              1,
                              error_message
                              TEXT,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
CREATE TABLE system_logs
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              log_level
                              TEXT
                              NOT
                              NULL,
                              function_name
                              TEXT,
                              message
                              TEXT
                              NOT
                              NULL,
                              execution_time_ms
                              INTEGER,
                              error_details
                              TEXT,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
CREATE TABLE monitoring_cycles
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              cycle
                              INTEGER
                              NOT
                              NULL,
                              tracked_nfts
                              TEXT,
                              status
                              TEXT
                              NOT
                              NULL,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
CREATE TABLE daily_performance
                          (
                              date
                              DATE
                              PRIMARY
                              KEY,
                              total_value_usd
                              REAL,
                              fee_earned_usd
                              REAL,
                              impermanent_loss_usd
                              REAL,
                              gas_spent_usd
                              REAL,
                              net_profit_usd
                              REAL,
                              apr_percent
                              REAL,
                              rebalance_count
                              INTEGER
                              DEFAULT
                              0,
                              swap_count
                              INTEGER
                              DEFAULT
                              0,
                              error_count
                              INTEGER
                              DEFAULT
                              0,
                              success_rate
                              REAL,
                              in_range_percent
                              REAL,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP,
                              updated_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
CREATE TABLE metadata
                          (
                              key
                              TEXT
                              PRIMARY
                              KEY,
                              value
                              TEXT
                              NOT
                              NULL,
                              updated_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
CREATE INDEX idx_fund_changes_timestamp
                              ON fund_changes(timestamp DESC)
                          ;
CREATE INDEX idx_swap_timestamp
                              ON swap_history(timestamp DESC)
                          ;
CREATE INDEX idx_system_logs_timestamp
                              ON system_logs(timestamp DESC)
                          ;
CREATE INDEX idx_system_logs_level
                              ON system_logs(log_level)
                          ;
CREATE INDEX idx_monitoring_cycles_timestamp
                              ON monitoring_cycles(timestamp DESC)
                          ;
CREATE TABLE fee_collection_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    nft_id INTEGER,
    tx_hash TEXT,
    token0_symbol TEXT DEFAULT 'WETH',
    token1_symbol TEXT DEFAULT 'USDC',
    amount0 REAL,
    amount1 REAL,
    amount0_usd REAL,
    amount1_usd REAL,
    total_usd REAL,
    gas_used INTEGER,
    gas_cost_eth REAL,
    gas_cost_usd REAL,
    net_profit_usd REAL,
    success BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_fee_collection_timestamp ON fee_collection_history(timestamp DESC);
CREATE INDEX idx_fee_collection_tx_hash ON fee_collection_history(tx_hash);
CREATE TABLE investment_history
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     timestamp
                     DATETIME
                     NOT
                     NULL,
                     action
                     TEXT
                     NOT
                     NULL,
                     amount_usd
                     REAL
                     NOT
                     NULL,
                     cumulative_investment
                     REAL,
                     note
                     TEXT,
                     created_at
                     DATETIME
                     DEFAULT
                     CURRENT_TIMESTAMP
                 );
CREATE TABLE IF NOT EXISTS "rebalance_history" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    reason TEXT NOT NULL,
    old_nft_id INTEGER,
    new_nft_id INTEGER,
    old_tick_lower INTEGER,
    old_tick_upper INTEGER,
    new_tick_lower INTEGER,
    new_tick_upper INTEGER,
    price_at_rebalance REAL,
    estimated_amount REAL,
    actual_amount REAL,
    swap_executed BOOLEAN,
    tx_hash TEXT,
    gas_used INTEGER,
    gas_price REAL,
    gas_cost_usd REAL,
    success BOOLEAN,
    error_message TEXT,
    duration_seconds INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    gas_cost_eth REAL,
    UNIQUE(timestamp, reason, new_nft_id)
);
CREATE INDEX idx_rebalance_timestamp ON rebalance_history(timestamp DESC);
CREATE INDEX idx_rebalance_nft ON rebalance_history(old_nft_id, new_nft_id);
INSERT INTO metadata VALUES('schema_version','1.0.0','2025-07-30 03:48:33');
INSERT INTO metadata VALUES('initialized_at','2025-07-30T12:48:33.885022','2025-07-30 03:48:33');
INSERT INTO metadata VALUES('last_import_at','2025-08-02T10:50:02.702521','2025-08-02 01:50:02');
INSERT INTO metadata VALUES('total_imported','8414','2025-08-02 01:50:02');
INSERT INTO daily_performance VALUES('2025-07-30',NULL,NULL,NULL,NULL,NULL,NULL,3810,2610,222,94.17322834645669616,NULL,'2025-08-02 01:50:02','2025-08-02 01:50:02');
INSERT INTO daily_performance VALUES('2025-07-31',NULL,NULL,NULL,NULL,NULL,NULL,6383,3808,111,98.261005796647353351,NULL,'2025-08-02 01:50:02','2025-08-02 01:50:02');
INSERT INTO daily_performance VALUES('2025-08-01',NULL,NULL,NULL,NULL,NULL,NULL,9609,5760,444,95.379331876365895936,NULL,'2025-08-02 01:50:02','2025-08-02 01:50:02');
INSERT INTO daily_performance VALUES('2025-08-02',NULL,NULL,NULL,NULL,NULL,NULL,1461,738,0,100.0,NULL,'2025-08-02 01:50:02','2025-08-02 01:50:02');
INSERT INTO rebalance_history VALUES(36776,'2025-08-02T10:06:35.905486','range_out',4736493,4736646,-194850,-194650,-194760,-194560,3517.997241825707988,62.851236128505973965,62.856269361229053062,0,'0x549c32e99e70a420afd0a4d8e9975514c0bef90eaa838e479f5e6669007723f6',417505,0.010000000000000000208,0.014655248648176143894,1,NULL,NULL,'2025-08-02 01:10:02',4.1750499999999999469e-06);
INSERT INTO rebalance_history VALUES(31343,'2025-08-02T08:53:24.875253','range_out',4736214,4736493,-194940,-194740,-194850,-194650,3488.0833998183343282,62.611710945215229172,62.615548513369546413,0,'0x539388c1c118b49f39dcceb2eac3fc02382e8558b3ab2556e95aeba5e6765dfe',416665,0.010000000000000000208,0.01454208115535482286,1,NULL,NULL,'2025-08-01 23:55:02',4.166650000000000163e-06);
INSERT INTO rebalance_history VALUES(25596,'2025-08-02T07:32:06.209153','range_out',4736150,4736214,-194820,-194620,-194940,-194740,3459.0572635481494215,63.104321382360922141,63.103520358086214515,0,'0xee5a7a50deb23346e655c106c053391bd455090dd28efeec6669c5a344528f26',405770,0.65847699999999997899,0.9253718880394449231,1,NULL,NULL,'2025-08-01 22:35:01',0.00026719021229000002688);
INSERT INTO rebalance_history VALUES(24881,'2025-08-02T07:23:36.924972','range_out',4735932,4736150,-194720,-194520,-194820,-194620,3500.1558789743157831,64.105372886637070452,64.104427539646778198,0,'0xe5aa43b2d0bcb7c19aa8ea8cf4b0c01bc2c17e6446b7d27d081b422615a24286',416613,0.023179999999999999216,0.033833646097802386187,1,NULL,NULL,'2025-08-01 22:25:02',9.6570893400000001266e-06);
INSERT INTO rebalance_history VALUES(18524,'2025-08-02T05:50:09.199053','range_out',4735735,4735932,-194810,-194610,-194720,-194520,3534.8960398888748387,64.495980047309885208,64.498856571906202361,0,'0xf9fe4479116b1991026a100edae5fb8b5ccb9f1cd9bb8853f8ca971c73e1e463',411752,0.010000000000000000208,0.014534298292651990497,1,NULL,NULL,'2025-08-01 20:55:02',4.1175199999999996694e-06);
INSERT INTO fee_collection_history VALUES(106,'2025-08-02T10:06:15.880614',4736493,'0x269d50fe8c67378693acb92d0f0c91797b8e46a148d7f6e803ddb322f24923f7','WETH','USDC',1.1978512758615026886e-05,0.055973999999999080046,0.042045555907307637089,0.055973999999999080046,0.098019555907306710196,195206,1.9520600000000000771e-06,0.0068518896726465260485,0.091167666234660188484,1,'2025-08-02 01:10:09');
INSERT INTO fee_collection_history VALUES(105,'2025-08-02T08:53:05.847532',4736214,'0x2833b28e8c5dc0b5802aafce2e424e5d970b00f11d15c0a97f6753ad767be8d1','WETH','USDC',2.9239311300241033024e-05,0.10859299999999905139,0.10202620352499898459,0.10859299999999905139,0.21061920352499802211,201708,2.0170800000000000068e-06,0.0070382989699387518353,0.20358090455505928328,1,'2025-08-01 23:55:09');
INSERT INTO fee_collection_history VALUES(104,'2025-08-02T07:31:47.038693',4736150,'0x07484c01f187c998cfea4de8d1a1b84af27c66e0ba7973c831c8c1dcc469cacd','WETH','USDC',9.3573948612389601375e-06,0.016588999999999999579,0.032441654290548467554,0.016588999999999999579,0.049030654290548467133,189404,0.00012615253419999999831,0.4373649891964818126,-0.38833433490593333159,1,'2025-08-01 22:35:10');
INSERT INTO fee_collection_history VALUES(103,'2025-08-02T07:23:17.927418',4735932,'0x93c48b8b5408f5858f679c36b01124fd58971acc45802f1bd53a25f56344a493','WETH','USDC',2.0308065605888908633e-05,0.05647800000000002818,0.071168770837153685904,0.05647800000000002818,0.1276467708371537002,201607,4.8337294320000000237e-06,0.016939603648663478091,0.11070716718849021864,1,'2025-08-01 22:25:09');
INSERT INTO fee_collection_history VALUES(102,'2025-08-02T05:49:50.331683',4735735,'0xf679af999a92f21a8309f1e7b38e93f39b581157b182f18f91f0e5c3b0f63d79','WETH','USDC',1.1724344278236952833e-05,0.055213999999999430201,0.04143254871365655706,0.055213999999999430201,0.0966465487136559942,205255,2.05254999999999994e-06,0.0072534869195263855512,0.089393061794129605179,1,'2025-08-01 20:50:06');
