MACHGUARD COMPLETE
===================
1. Open PowerShell in this folder.
2. Create/activate a virtual environment:
   python -m venv venv
   .\venv\Scripts\Activate.ps1
3. Install:
   pip install -r requirements.txt
4. Run:
   python app.py
5. Open:
   http://127.0.0.1:5000
6. Create an account and login.

Included:
- Public landing page
- Registration/login/logout
- SQLite database
- Machine CRUD (add/delete)
- Machine health/risk scoring
- Alerts
- Analytics chart
- Responsive dashboard
- API endpoint /api/health

This is a complete demo/prototype. For public production deployment, change SECRET_KEY,
use PostgreSQL, disable debug, and deploy behind a production WSGI server/HTTPS.
