from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random

app = Flask(__name__)
app.config["SECRET_KEY"] = "machguard-production-change-this-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///machguard.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    def set_password(self, p):
        self.password_hash = generate_password_hash(p)
    def check_password(self, p):
        return check_password_hash(self.password_hash, p)

class Machine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    line = db.Column(db.String(120), default="Production Line A")
    status = db.Column(db.String(30), default="Online")
    temperature = db.Column(db.Float, default=65)
    vibration = db.Column(db.Float, default=1.8)
    pressure = db.Column(db.Float, default=5.5)
    rpm = db.Column(db.Integer, default=1500)
    health = db.Column(db.Integer, default=90)
    risk = db.Column(db.String(30), default="Low")
    last_check = db.Column(db.DateTime, default=datetime.utcnow)

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    machine = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    severity = db.Column(db.String(30), default="Warning")
    message = db.Column(db.String(300), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_counts():
    return {
        "alert_count": Alert.query.count() if db.session else 0,
        "machine_count": Machine.query.count() if db.session else 0
    }

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not name or not email or len(password) < 6:
            flash("Enter all details. Password must be at least 6 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered. Please login.", "warning")
        else:
            u = User(name=name, email=email)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            flash("Account created successfully. Please login.", "success")
            return redirect(url_for("login"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        u = User.query.filter_by(email=email).first()
        if u and u.check_password(password):
            login_user(u)
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("auth.html", mode="login")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    machines = Machine.query.order_by(Machine.id.desc()).all()
    alerts = Alert.query.order_by(Alert.created_at.desc()).limit(5).all()
    healthy = sum(1 for m in machines if m.health >= 75)
    highrisk = sum(1 for m in machines if m.health < 60)
    avg_health = round(sum(m.health for m in machines)/len(machines)) if machines else 0
    return render_template("dashboard.html", machines=machines, alerts=alerts,
                           healthy=healthy, highrisk=highrisk, avg_health=avg_health)

@app.route("/machines", methods=["GET","POST"])
@login_required
def machines():
    if request.method == "POST":
        m = Machine(
            name=request.form.get("name","New Machine"),
            line=request.form.get("line","Production Line A"),
            temperature=float(request.form.get("temperature",65)),
            vibration=float(request.form.get("vibration",1.8)),
            pressure=float(request.form.get("pressure",5.5)),
            rpm=int(request.form.get("rpm",1500)),
        )
        score = max(0, min(100, round(100 - max(0,m.temperature-70)*0.7 - max(0,m.vibration-2)*8)))
        m.health = score
        m.risk = "High" if score < 60 else ("Medium" if score < 75 else "Low")
        m.status = "Warning" if score < 75 else "Online"
        db.session.add(m)
        db.session.commit()
        if score < 75:
            db.session.add(Alert(machine=m.name, title="Machine health requires attention",
                                 severity="Danger" if score < 60 else "Warning",
                                 message=f"Predicted health score: {score}/100"))
            db.session.commit()
        flash("Machine added successfully.", "success")
        return redirect(url_for("machines"))
    return render_template("machines.html", machines=Machine.query.order_by(Machine.id.desc()).all())

@app.post("/machines/<int:machine_id>/delete")
@login_required
def delete_machine(machine_id):
    m = db.session.get(Machine, machine_id)
    if m:
        db.session.delete(m)
        db.session.commit()
        flash("Machine deleted.", "success")
    return redirect(url_for("machines"))

@app.route("/alerts")
@login_required
def alerts():
    return render_template("alerts.html", alerts=Alert.query.order_by(Alert.created_at.desc()).all())

@app.route("/analytics")
@login_required
def analytics():
    machines = Machine.query.all()
    return render_template("analytics.html", machines=machines)

@app.route("/api/health")
@login_required
def api_health():
    machines = Machine.query.all()
    return jsonify([{"name":m.name, "health":m.health, "temperature":m.temperature,
                     "vibration":m.vibration, "risk":m.risk} for m in machines])

def seed():
    db.create_all()
    if Machine.query.count() == 0:
        demo = [
            ("CNC Machine 01","Production Line A",64,1.8,5.6,1500,94),
            ("CNC Machine 04","Production Line B",91,3.8,6.2,1700,61),
            ("Lathe Machine 02","Production Line A",71,2.4,5.8,1450,86),
            ("Press Machine 01","Production Line C",59,1.2,5.2,1250,97),
        ]
        for name,line,temp,vib,press,rpm,health in demo:
            db.session.add(Machine(name=name,line=line,temperature=temp,vibration=vib,
                                   pressure=press,rpm=rpm,health=health,
                                   risk="High" if health < 60 else ("Medium" if health < 75 else "Low"),
                                   status="Warning" if health < 75 else "Online"))
        db.session.add(Alert(machine="CNC Machine 04", title="High Temperature",
                             severity="Danger", message="Temperature reached 91°C."))
        db.session.add(Alert(machine="Lathe Machine 02", title="Increased Vibration",
                             severity="Warning", message="Vibration is above normal range."))
        db.session.commit()

with app.app_context():
    seed()

if __name__ == "__main__":
    app.run(debug=True)
