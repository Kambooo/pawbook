import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "pawbook-local-secret")

# ── Database (PostgreSQL via DATABASE_URL env var) ────────────────────────
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "postgresql://pawbook:pawbook123@db:5432/pawbook"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ── Local file uploads (replaces S3 for local Docker run) ─────────────────
UPLOAD_FOLDER = "/app/uploads"
ALLOWED_EXT   = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "mov", "pdf"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB

db = SQLAlchemy(app)


# ── Models ────────────────────────────────────────────────────────────────
class Owner(db.Model):
    """One owner can have many pets."""
    __tablename__ = "owners"
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(180))
    phone      = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    pets = db.relationship(
        "Pet",
        backref="owner",
        cascade="all, delete-orphan",
        lazy=True,
    )


class Pet(db.Model):
    __tablename__ = "pets"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    species     = db.Column(db.String(50),  nullable=False)
    breed       = db.Column(db.String(100))
    age         = db.Column(db.Float)
    bio         = db.Column(db.Text)
    owner_id    = db.Column(db.Integer, db.ForeignKey("owners.id"), nullable=True)
    photo_file  = db.Column(db.String(300))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def photo_url(self):
        if self.photo_file:
            return url_for("uploaded_file", filename=self.photo_file)
        return None

    def species_emoji(self):
        return {"dog": "🐕", "cat": "🐈"}.get(self.species, "🐾")


# ── Helpers ───────────────────────────────────────────────────────────────
def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def save_file(f):
    ext  = f.filename.rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(UPLOAD_FOLDER, name))
    return name

def get_or_create_owner(name, email, phone):
    name  = (name  or "").strip()
    email = (email or "").strip()
    phone = (phone or "").strip()
    if not name:
        return None
    owner = Owner.query.filter_by(email=email).first() if email else None
    if owner:
        owner.name  = name
        owner.phone = phone or owner.phone
        return owner
    owner = Owner(name=name, email=email or None, phone=phone or None)
    db.session.add(owner)
    db.session.flush()
    return owner

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.context_processor
def inject_now():
    return {"now": datetime.utcnow()}


# ── Routes ────────────────────────────────────────────────────────────────

# PAGE 1 — Directory
@app.route("/")
def index():
    q       = request.args.get("q", "").strip()
    species = request.args.get("species", "")
    query   = Pet.query
    if q:
        query = query.filter(Pet.name.ilike(f"%{q}%"))
    if species:
        query = query.filter(Pet.species == species)
    pets = query.order_by(Pet.created_at.desc()).all()
    return render_template("index.html", pets=pets, q=q, species=species)


# PAGE 2 — Add Pet
@app.route("/add", methods=["GET", "POST"])
def add_pet():
    if request.method == "POST":
        f = request.files.get("photo")
        photo = save_file(f) if (f and f.filename and allowed(f.filename)) else None
        owner = get_or_create_owner(
            request.form.get("owner_name", ""),
            request.form.get("owner_email", ""),
            request.form.get("owner_phone", ""),
        )
        pet = Pet(
            name       = request.form["name"].strip(),
            species    = request.form["species"],
            breed      = request.form.get("breed", "").strip() or None,
            age        = float(request.form["age"]) if request.form.get("age") else None,
            bio        = request.form.get("bio", "").strip() or None,
            owner      = owner,
            photo_file = photo,
        )
        db.session.add(pet)
        db.session.commit()
        flash(f"{pet.name} has been added! 🎉", "success")
        return redirect(url_for("pet_detail", pet_id=pet.id))
    return render_template("add_pet.html")


# PAGE 3 — Pet Detail
@app.route("/pet/<int:pet_id>")
def pet_detail(pet_id):
    pet = Pet.query.get_or_404(pet_id)
    return render_template("pet_detail.html", pet=pet)


# PAGE 4 — Owners List
@app.route("/owners")
def owners_list():
    owners = Owner.query.order_by(Owner.name).all()
    return render_template("owners.html", owners=owners)


# Edit Pet
@app.route("/pet/<int:pet_id>/edit", methods=["GET", "POST"])
def edit_pet(pet_id):
    pet = Pet.query.get_or_404(pet_id)
    if request.method == "POST":
        f = request.files.get("photo")
        if f and f.filename and allowed(f.filename):
            pet.photo_file = save_file(f)
        pet.name    = request.form["name"].strip()
        pet.species = request.form["species"]
        pet.breed   = request.form.get("breed", "").strip() or None
        pet.age     = float(request.form["age"]) if request.form.get("age") else None
        pet.bio     = request.form.get("bio", "").strip() or None
        pet.owner   = get_or_create_owner(
            request.form.get("owner_name", ""),
            request.form.get("owner_email", ""),
            request.form.get("owner_phone", ""),
        )
        db.session.commit()
        flash("Profile updated! ✨", "success")
        return redirect(url_for("pet_detail", pet_id=pet.id))
    return render_template("edit_pet.html", pet=pet)


# Delete Pet
@app.route("/pet/<int:pet_id>/delete", methods=["POST"])
def delete_pet(pet_id):
    pet = Pet.query.get_or_404(pet_id)
    name = pet.name
    if pet.photo_file:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, pet.photo_file))
        except:
            pass
    db.session.delete(pet)
    db.session.commit()
    flash(f"{name} was removed from the directory.", "info")
    return redirect(url_for("index"))


# JSON API
@app.route("/api/pets")
def api_pets():
    pets = Pet.query.order_by(Pet.created_at.desc()).all()
    return jsonify([{
        "id": p.id, "name": p.name, "species": p.species,
        "breed": p.breed, "age": p.age,
        "owner": p.owner.name if p.owner else None,
    } for p in pets])


# ── Init DB & run ─────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
