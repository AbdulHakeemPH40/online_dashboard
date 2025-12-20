# Agent Instructions for Database Management

## ⚠️ CRITICAL DATABASE RULES

### NEVER DELETE PRODUCTION DATABASE
- **STRICTLY PROHIBITED**: `rm db.sqlite3` on production server
- **STRICTLY PROHIBITED**: `DROP DATABASE` commands on production
- Production data loss is unacceptable and causes major business disruption

### Git Conflict Resolution with Database Schema Changes

When git conflicts occur involving database schema changes:

#### ❌ WRONG APPROACH (NEVER DO THIS)
```bash
# NEVER run these commands on production:
rm db.sqlite3
rm -rf integration/migrations/
```

#### ✅ CORRECT APPROACH

1. **Backup Database First**
```bash
cp db.sqlite3 db.sqlite3.backup.$(date +%Y%m%d_%H%M%S)
```

2. **Handle Migration Conflicts**
```bash
# Reset migrations to clean state
python manage.py migrate integration zero
python manage.py showmigrations
```

3. **Apply Schema Changes via ALTER TABLE**
```bash
# Open SQLite database
sqlite3 db.sqlite3

# Example: Add new column safely
ALTER TABLE integration_item ADD COLUMN new_field VARCHAR(255) DEFAULT '';

# Example: Rename column safely  
ALTER TABLE integration_item RENAME COLUMN old_name TO new_name;

# Exit SQLite
.exit
```

4. **Create Fresh Migration**
```bash
python manage.py makemigrations --empty integration
# Edit the migration file to match the manual ALTER TABLE changes
python manage.py migrate
```

### Database Schema Change Workflow

1. **Local Development**
   - Make model changes
   - Run `python manage.py makemigrations`
   - Test migrations locally

2. **Production Deployment**
   - Backup database: `cp db.sqlite3 db.sqlite3.backup`
   - Pull code: `git pull`
   - Run migrations: `python manage.py migrate`
   - If conflicts occur, use ALTER TABLE approach above

### Emergency Recovery

If database is accidentally deleted:
1. Check for recent backups in `/var/www/myproject/`
2. Restore from backup: `cp db.sqlite3.backup.YYYYMMDD_HHMMSS db.sqlite3`
3. If no backup exists, recreate from scratch and re-import data

### Backup Strategy

**Automated Daily Backup** (add to crontab):
```bash
# Add this to crontab: crontab -e
0 2 * * * cp /var/www/myproject/db.sqlite3 /var/www/myproject/db.sqlite3.backup.$(date +\%Y\%m\%d)
```

**Manual Backup Before Changes**:
```bash
cp db.sqlite3 db.sqlite3.backup.$(date +%Y%m%d_%H%M%S)
```

## Summary

- **NEVER** delete `db.sqlite3` on production
- **ALWAYS** backup before schema changes
- **USE** ALTER TABLE for production schema changes
- **AVOID** migration conflicts by proper planning
- **DOCUMENT** all manual database changes