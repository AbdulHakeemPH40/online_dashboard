# Django Deployment on DigitalOcean

## Server Information
| Item | Value |
|------|-------|
| OS | Ubuntu 24.04 LTS |
| Python | 3.12.3 |
| Web Server | Nginx 1.24.0 |
| WSGI | Gunicorn 21.2.0 |
| Database | SQLite (switched from MySQL for performance) |
| Project Path | /var/www/myproject |

---

## STEP 1: SSH to Server
```bash
```

---

## STEP 2: Create Project Directory
```bash
mkdir -p /var/www/myproject
cd /var/www/myproject

git pull



sudo systemctl restart gunicorn
sudo systemctl restart nginx

sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn

```


git pull
pip install -r requirements.txt
export DJANGO_ENV=digitalocean
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn

---

## STEP 3: Clone from GitHub
```bash
git clone https://github.com/AbdulHakeemPH40/online_dashboard.git .
```

Verify files:
```bash
ls
```
Expected: `manage.py`, `middleware_dashboard/`, `requirements.txt`

---

## STEP 4: Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

---

## STEP 5: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## STEP 6: Django Setup
```bash
export DJANGO_ENV=digitalocean
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

Test Django (optional):
```bash
python manage.py runserver 0.0.0.0:8000

---

## STEP 7: Gunicorn Systemd Service
```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Paste this content:
```ini
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/myproject
Environment="DJANGO_ENV=digitalocean"
Environment="OPENAI_API_KEY=your-api-key-here"
ExecStart=/var/www/myproject/venv/bin/gunicorn --workers 3 --threads 4 --timeout 600 --bind unix:/var/www/myproject/gunicorn.sock middleware_dashboard.wsgi:application

[Install]
WantedBy=multi-user.target
```

Save: `Ctrl+X`, `Y`, `Enter`

Enable & start:
```bash
sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```


my sql 
USER:django_user
password:winDOws@10

---

## STEP 8: Configure Nginx

### Create Nginx Configuration
```bash
sudo nano /etc/nginx/sites-available/myproject
```

Paste this content:
```nginx
server {
    listen 800
    client_max_body_size 20M;  # Allow large CSV uploads

    # Static files (CSS, JavaScript, Images)
    location /static/ {
        alias /var/www/myproject/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files (User uploads)
    location /media/ {
        alias /var/www/myproject/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Proxy all other requests to Django/Gunicorn
    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/myproject/gunicorn.sock;
    }
}
```

**Configuration Explained:**
- `server_name`: Accepts requests from IP and domain
- `client_max_body_size 20M`: Allows CSV uploads up to 20MB
- `/static/`: Serves CSS, JS, images from `staticfiles/` folder
- `/media/`: Serves user-uploaded files from `media/` folder
- `expires` & `Cache-Control`: Browser caching for better performance
- `location /`: Proxies dynamic requests to Gunicorn

Save: `Ctrl+X`, `Y`, `Enter`

### Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/myproject /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

### Create Media Directory
```bash
mkdir -p /var/www/myproject/media
sudo chown -R root:www-data /var/www/myproject/media
sudo chmod -R 755 /var/www/myproject/media
```

---

## STEP 9: Firewall (Optional)
```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow 22
sudo ufw enable
```

---

## STEP 10: Enable HTTPS with SSL Certificate (Let's Encrypt)

### Install Certbot
```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
```

### Get SSL Certificate
**Important:** Before running this, make sure your domain DNS A record points to your server IP:
- Domain: `erp.pasons.group`
- Points to: `159.89.133.6`

```bash
sudo certbot --nginx -d erp.pasons.group
```

### Certbot Prompts
1. **Email address**: Enter your email (e.g., `abdulhakeemph@gmail.com`)
2. **Terms of Service**: Type `Y` to agree
3. **Share email with EFF**: Type `N` (optional)
4. **Redirect HTTP to HTTPS**: Type `2` (recommended)

### After SSL Installation

Certbot will automatically:
- ✅ Issue free SSL certificate (valid 90 days)
- ✅ Update Nginx configuration for HTTPS
- ✅ Set up auto-renewal (runs twice daily)
- ✅ Redirect HTTP to HTTPS

**Your site will be accessible at:**
- `https://erp.pasons.group` (Secure)
- `http://erp.pasons.group` (Redirects to HTTPS)
- `http://159.89.133.6` (Still works)

### Verify Auto-Renewal
```bash
sudo systemctl status certbot.timer
```

Should show: `Active: active (waiting)`

### 🧹 Data Cleaning Setup (Multi-File Support)
Since the system now supports merging multiple files in the **Promo** mode, you should ensure the server can handle larger uploads and has the temporary directory ready:

1. **Verify Media Permissions**:
```bash
mkdir -p /var/www/myproject/media/temp_cleaning
sudo chown -R root:www-data /var/www/myproject/media
sudo chmod -R 775 /var/www/myproject/media
```

2. **Increase Upload Limit** (Recommended for merging many files):
```bash
sudo nano /etc/nginx/sites-available/myproject
# Change client_max_body_size to 50M
# client_max_body_size 50M;

sudo nginx -t
sudo systemctl reload nginx
```
Manual Cleanup (Run now)
find /var/www/myproject/media/temp_cleaning/ -type f -mtime +0 -delete

3. **Auto-Cleanup (Every 24 Hours)**:
To prevent the server from filling up with temporary cleaned files, set up a "cron job" to delete files older than 24 hours:

```bash
# Open crontab editor
crontab -e

# Add this line at the bottom of the file:
0 0 * * * find /var/www/myproject/media/temp_cleaning/ -type f -mtime +0 -delete
```
*Note: This runs every night at 12:00 AM and deletes files that were created more than 24 hours ago.*

### Test Renewal (Optional)
```bash
sudo certbot renew --dry-run
```

### Manual Renewal (If Needed)
```bash
sudo certbot renew
sudo systemctl reload nginx
```

**Certificate Details:**
- Valid for: 90 days
- Auto-renews: 30 days before expiration
- Renewal notifications: Sent to your email
- Certificate path: `/etc/letsencrypt/live/erp.pasons.group/`

---

## FINAL RESULT
Open in browser: **http://159.89.133.6**

Your Django project is LIVE on DigitalOcean! 

---

## Useful Commands

### Restart Services
```bash
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

### View Logs
```bash
sudo journalctl -u gunicorn -f
sudo tail -f /var/log/nginx/error.log
```

### Update Code from GitHub
```bash
cd /var/www/myproject
source venv/bin/activate
git pull
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
```

### Check Service Status
```bash
sudo systemctl status gunicorn
sudo systemctl status nginx
```

---

## Optional (Later)
- Switch to PostgreSQL
- Create non-root user for security
- Set up monitoring and backups

---

## Environment Variables
Set in `/etc/systemd/system/gunicorn.service`:
```ini
Environment="DJANGO_ENV=digitalocean"
Environment="OPENAI_API_KEY=your-api-key"
```

After changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

---

## 🔄 How to Update Code (Step by Step)

When you make changes locally and push to GitHub, follow these steps on DigitalOcean:

### Step 1: SSH to Server
```bash
ssh root@159.89.133.6
```

### Step 2: Go to Project & Activate Venv
```bash
cd /var/www/myproject
source venv/bin/activate
```

### Step 3: Pull Latest Code
```bash
git pull
```

### Step 4: Install New Dependencies (if any)
```bash
pip install -r requirements.txt
```

### Step 5: Run Migrations (if model changes)
```bash
export DJANGO_ENV=digitalocean
python manage.py makemigrations
python manage.py migrate
```

### Step 6: Collect Static Files (if CSS/JS changes)
```bash
python manage.py collectstatic --noinput
```

### Step 7: Restart Gunicorn
```bash
sudo systemctl restart gunicorn
```

### Step 8: Verify
Open http://159.89.133.6 in browser to check changes.

---

## 📋 Quick Update (Copy-Paste)

For quick updates, copy and paste this entire block:
```bash
cd /var/www/myproject
source venv/bin/activate
git pull
pip install -r requirements.txt
export DJANGO_ENV=digitalocean
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
```

---

## 🚀 Push Changes FROM DigitalOcean TO GitHub

When you make changes on the server and want to push them to GitHub:

### Step 1: SSH to Server & Navigate
```bash
ssh root@159.89.133.6
cd /var/www/myproject
```

### Step 2: Check Git Status
```bash
git status
```

### Step 3: Add Changes
```bash
# Add specific files
git add docs/digita_ocean.md
git add templates/reports.html
git add integration/views.py

# Or add all changes
git add .
```

### Step 4: Commit Changes
```bash
git commit -m "Add comprehensive Reports system with export functionality"
```

### Step 5: Push to GitHub
```bash
git push origin main
```

### Step 6: Verify on GitHub
Visit: https://github.com/AbdulHakeemPH40/online_dashboard

---

## 📊 Recent Updates (December 2025)

### ✅ Reports & Data Export System
- **Added comprehensive reports page** with DataTables-like functionality
- **Platform-specific stats cards** (Pasons Items, Talabat Items, Outlets)
- **Three export types**: All Items, Platform Items, Outlet Items
- **Export formats**: CSV, Excel, Print (PDF removed)
- **Pagination system** (20 items per page) with navigation
- **Search functionality** across all data
- **Clean outlet dropdown** without colored indicators

### ✅ Database Migration (MySQL → SQLite)
- **Switched from MySQL to SQLite** for all environments due to performance issues
- **Updated settings.py** to use SQLite only (local, pythonanywhere, digitalocean)
- **MySQL service stopped** and disabled to free up 512MB RAM
- **Automated backup system** implemented with daily backups at 2 AM

### ✅ Export Filename Improvements
- **Updated ERP export filenames** to include outlet name and timestamp
- **Updated Talabat Feed export filenames** similarly
- **Fixed timezone issues** in CSV exports using `timezone.localtime()`
- **Changed underscores to hyphens** in all export filenames

### ✅ Bug Fixes
- **Fixed pencil icon lock** after editing selling prices
- **Fixed HTML encoding bug** in item descriptions (removed `escape()` calls)
- **Added database safety rules** in `docs/agent_instruction.md`

---

## ⚠️ Troubleshooting

### If site shows error after update:
```bash
sudo journalctl -u gunicorn -n 50
```

### If static files not loading:
```bash
python manage.py collectstatic --noinput
sudo systemctl restart nginx
```

### If database error:
```bash
python manage.py makemigrations
python manage.py migrate
sudo systemctl restart gunicorn
```

### Gunicorn Timeout
If you get **502 Bad Gateway** during CSV uploads:

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Change the `ExecStart=` line to add `--timeout 300`:
```ini
ExecStart=/var/www/myproject/venv/bin/gunicorn --workers 3 --threads 4 --timeout 600 --bind unix:/var/www/myproject/gunicorn.sock middleware_dashboard.wsgi:application
```

Save: `Ctrl+X`, `Y`, `Enter`

Apply changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

### Nginx Upload Size
If you get **"client intended to send too large body"** error:

```bash
sudo nano /etc/nginx/sites-available/myproject
```

Add `client_max_body_size 20M;` inside the `server` block:
```nginx
server {
    listen 80;
    server_name 159.89.133.6;

    client_max_body_size 20M;

    location /static/ {
        alias /var/www/myproject/staticfiles/;
    }

    location /media/ {
        alias /var/www/myproject/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/myproject/gunicorn.sock;
    }
}
```

Save: `Ctrl+X`, `Y`, `Enter`

Apply changes:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Update OpenAI API Key

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Update the `Environment="OPENAI_API_KEY=..."` line with new key.

Save: `Ctrl+X`, `Y`, `Enter`

Apply changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

---

### Performance Monitoring
```bash
# Check CPU and RAM usage
htop

# Check disk IO pressure (wait percentage)
iostat -xz 1

# View Gunicorn logs in real-time
sudo journalctl -u gunicorn -f
```

---

## 📝 Nano Editor Quick Reference

| Action | Command |
|--------|---------|
| Save file | `Ctrl+X`, then `Y`, then `Enter` |
| Exit without saving | `Ctrl+X`, then `N` |
| Move cursor | Arrow keys |
| Delete line | `Ctrl+K` |
| Search | `Ctrl+W` |
| Copy line | `Alt+6` |
| Paste | `Ctrl+U`
