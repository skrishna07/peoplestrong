import sqlite3

conn = sqlite3.connect('Production_erp_sync_queue1.db')
c = conn.cursor()

for col_def in [
    ('lifecycle_status', "TEXT DEFAULT 'Processing'"),
    ('dropped_at', 'DATETIME'),
    ('drop_reason', 'TEXT')
]:
    try:
        c.execute(f'ALTER TABLE pending_sync ADD COLUMN {col_def[0]} {col_def[1]}')
        print(f'Added {col_def[0]}')
    except Exception as e:
        if 'already exists' in str(e):
            print(f'{col_def[0]} already exists')
        else:
            print(f'Error adding {col_def[0]}: {e}')

conn.commit()
conn.close()
print('Migration complete')
