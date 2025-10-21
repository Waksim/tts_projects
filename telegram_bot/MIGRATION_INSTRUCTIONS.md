# Database Migration: Add max_audio_duration_minutes Column

## Problem
The production database is missing the `max_audio_duration_minutes` column in the `user_settings` table, causing errors when users click the "Длительность аудио" button.

## Solution
Run the migration script to add the missing column.

## Steps to Run Migration on Production Server

### 1. Connect to the server
```bash
ssh root@v2533030.hosted-by-vdsina.ru
```

### 2. Navigate to the project directory
```bash
cd /root/tts_projects
```

### 3. Stop the bot service
```bash
sudo systemctl stop tts-bot
```

### 4. Run the migration script
```bash
cd telegram_bot
python3 migrate_add_duration_column.py
```

Expected output:
```
📊 Connecting to database: /root/tts_projects/telegram_bot/bot_history.db
🔧 Adding column 'max_audio_duration_minutes' to 'user_settings' table...
✅ Migration completed successfully!
   Column 'max_audio_duration_minutes' has been added to 'user_settings' table.
✅ Verification: Column exists and is ready to use.
```

If the column already exists:
```
📊 Connecting to database: /root/tts_projects/telegram_bot/bot_history.db
✅ Column 'max_audio_duration_minutes' already exists in 'user_settings' table.
   No migration needed.
```

### 5. Start the bot service
```bash
sudo systemctl start tts-bot
```

### 6. Verify the bot is running
```bash
sudo systemctl status tts-bot
```

### 7. Check logs for any errors
```bash
sudo journalctl -u tts-bot -f
```

Press `Ctrl+C` to stop following logs.

### 8. Test the feature
Open Telegram and test the "Длительность аудио" button. It should now work without errors.

## Rollback (if needed)
If something goes wrong, you can remove the column (though this is not recommended):

```bash
# This requires recreating the table, so backup first
sqlite3 /root/tts_projects/telegram_bot/bot_history.db ".backup /root/tts_projects/telegram_bot/bot_history_backup.db"
```

## Technical Details

The migration script:
- Adds `max_audio_duration_minutes INTEGER DEFAULT NULL` column
- Is idempotent (safe to run multiple times)
- Uses SQLite's `ALTER TABLE` command
- Checks if the column exists before attempting to add it

## What This Fixes

After running the migration, users will be able to:
- Click the "Длительность аудио" button in settings
- Select their preferred maximum audio duration (15 min, 30 min, 1 hour, etc.)
- Set "Без лимита" (no limit) option

The default value is `NULL` which means "no limit" - matching the bot's default behavior.
