from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user,
    login_required, current_user
)
import os
from werkzeug.utils import secure_filename  # <--- faltava isso

app = Flask(__name__)

app.config["SECRET_KEY"] = "dev-secret-pawly"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pawly.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --------- CONFIG UPLOAD DE FOTOS ----------
UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# -------------- MODELS -----------------

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)

    pets = db.relationship("Pet", backref="tutor", lazy=True)


class Pet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    especie = db.Column(db.String(50))
    raca = db.Column(db.String(100))
    idade = db.Column(db.Integer)
    peso = db.Column(db.Float)
    data_nascimento = db.Column(db.Date)
    foto = db.Column(db.String(200))

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    cuidados = db.relationship("PetCare", backref="pet", lazy=True)


class PetCare(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.String(200))
    data = db.Column(db.Date, nullable=False)
    observacoes = db.Column(db.Text)
    custo = db.Column(db.Float)

    pet_id = db.Column(db.Integer, db.ForeignKey("pet.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -------------- ROTAS BÁSICAS -----------------

@app.route("/")
def index():
    return render_template("index.html")


# -------- REGISTER --------

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")
        confirma = request.form.get("confirma")

        if senha != confirma:
            error = "As senhas não coincidem!"
        elif User.query.filter_by(email=email).first():
            error = "Email já cadastrado!"
        else:
            hashed = bcrypt.generate_password_hash(senha).decode("utf-8")
            user = User(nome=nome, email=email, senha=hashed)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("list_pets"))

    return render_template("register.html", error=error)


# -------- LOGIN --------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.senha, senha):
            login_user(user)
            return redirect(url_for("list_pets"))
        else:
            error = "Email ou senha incorretos!"

    return render_template("login.html", error=error)


# -------- LOGOUT --------

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# -------------- ROTAS DE PETS -----------------

@app.route("/pets")
@login_required
def list_pets():
    pets = Pet.query.filter_by(user_id=current_user.id).all()
    return render_template("pets.html", pets=pets)


@app.route("/pets/create", methods=["GET", "POST"])
@login_required
def create_pet():
    if request.method == "POST":
        nome = request.form.get("nome")
        especie = request.form.get("especie")
        raca = request.form.get("raca")
        idade_raw = request.form.get("idade")
        peso_raw = request.form.get("peso")
        data_nascimento_raw = request.form.get("data_nascimento")

        # campo opcional de URL
        foto_url = request.form.get("foto_url")

        # arquivo de upload
        file = request.files.get("foto_arquivo")

        # --- trata data
        if data_nascimento_raw:
            try:
                data_nascimento = datetime.strptime(
                    data_nascimento_raw, "%Y-%m-%d"
                ).date()
            except ValueError:
                data_nascimento = None
        else:
            data_nascimento = None

        # --- idade/peso
        idade = int(idade_raw) if idade_raw else None
        try:
            peso = float(peso_raw) if peso_raw else None
        except:
            peso = None

        # --- define caminho da foto
        foto = None

        # prioridade: upload real
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)

            # no banco salvamos relativo à pasta static
            foto = f"uploads/{filename}"
        elif foto_url:
            # fallback pra URL
            foto = foto_url

        new_pet = Pet(
            nome=nome,
            especie=especie,
            raca=raca,
            idade=idade,
            peso=peso,
            data_nascimento=data_nascimento,
            foto=foto,
            user_id=current_user.id
        )

        db.session.add(new_pet)
        db.session.commit()

        return redirect(url_for("list_pets"))

    return render_template("pet_create.html")


@app.route("/pets/<int:pet_id>/edit", methods=["GET", "POST"])
@login_required
def edit_pet(pet_id):
    pet = Pet.query.get_or_404(pet_id)

    # segurança: só dono pode editar
    if pet.user_id != current_user.id:
        return redirect(url_for("list_pets"))

    if request.method == "POST":
        pet.nome = request.form.get("nome")
        pet.especie = request.form.get("especie")
        pet.raca = request.form.get("raca")

        idade_raw = request.form.get("idade")
        peso_raw = request.form.get("peso")
        data_raw = request.form.get("data_nascimento")

        # campos de foto
        foto_url = request.form.get("foto_url")
        file = request.files.get("foto_arquivo")

        # idade/peso
        pet.idade = int(idade_raw) if idade_raw else None
        try:
            pet.peso = float(peso_raw) if peso_raw else None
        except:
            pet.peso = None

        # data
        if data_raw:
            try:
                pet.data_nascimento = datetime.strptime(
                    data_raw, "%Y-%m-%d"
                ).date()
            except:
                pet.data_nascimento = None

        # FOTO:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)
            pet.foto = f"uploads/{filename}"
        elif foto_url:
            pet.foto = foto_url
        # se nada for enviado, mantém a foto atual

        db.session.commit()

        return redirect(url_for("list_pets"))

    return render_template("pet_edit.html", pet=pet)


@app.route("/pets/<int:pet_id>/delete", methods=["POST"])
@login_required
def delete_pet(pet_id):
    pet = Pet.query.get_or_404(pet_id)

    # 🔒 NÃO deixa excluir pet de outro user
    if pet.user_id != current_user.id:
        return redirect(url_for("list_pets"))

    db.session.delete(pet)
    db.session.commit()
    return redirect(url_for("list_pets"))


# -------------- DASHBOARD -----------------

@app.route("/dashboard")
@login_required
def dashboard():
    pets = Pet.query.filter_by(user_id=current_user.id).all()
    total_pets = len(pets)

    total_cuidados = (
        PetCare.query
        .join(Pet)
        .filter(Pet.user_id == current_user.id)
        .count()
    )

    ultimos_cuidados = (
        PetCare.query
        .join(Pet)
        .filter(Pet.user_id == current_user.id)
        .order_by(PetCare.data.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard.html",
        pets=pets,
        total_pets=total_pets,
        total_cuidados=total_cuidados,
        ultimos_cuidados=ultimos_cuidados
    )


@app.route("/pets/<int:pet_id>/dashboard")
@login_required
def pet_dashboard(pet_id):
    pet = Pet.query.get_or_404(pet_id)

    if pet.user_id != current_user.id:
        return redirect(url_for("list_pets"))

    cuidados = (
        PetCare.query
        .filter_by(pet_id=pet.id)
        .order_by(PetCare.data.desc())
        .all()
    )

    total_cuidados = len(cuidados)
    proximos = [c for c in cuidados if c.data and c.data >= datetime.today().date()]

    return render_template(
        "pet_dashboard.html",
        pet=pet,
        cuidados=cuidados,
        total_cuidados=total_cuidados,
        proximos=proximos
    )


# -------------- ROTAS DE CUIDADOS -----------------

@app.route("/pets/<int:pet_id>/care", methods=["GET", "POST"])
@login_required
def pet_care(pet_id):
    pet = Pet.query.get_or_404(pet_id)

    # 🔒 protege cuidados de pet alheio
    if pet.user_id != current_user.id:
        return redirect(url_for("list_pets"))

    if request.method == "POST":
        tipo = request.form.get("tipo")
        descricao = request.form.get("descricao")
        data_raw = request.form.get("data")
        observacoes = request.form.get("observacoes")
        custo_raw = request.form.get("custo")

        data = datetime.strptime(data_raw, "%Y-%m-%d").date() if data_raw else None
        custo = float(custo_raw) if custo_raw else None

        cuidado = PetCare(
            tipo=tipo,
            descricao=descricao,
            data=data,
            observacoes=observacoes,
            custo=custo,
            pet_id=pet.id
        )

        db.session.add(cuidado)
        db.session.commit()

        return redirect(url_for("pet_care", pet_id=pet.id))

    cuidados = PetCare.query.filter_by(pet_id=pet.id).order_by(PetCare.data.desc()).all()

    return render_template("pet_care.html", pet=pet, cuidados=cuidados)


@app.route("/care/<int:care_id>/delete", methods=["POST"])
@login_required
def delete_care(care_id):
    cuidado = PetCare.query.get_or_404(care_id)

    # segurança: só pode excluir cuidado de pet do usuário logado
    if cuidado.pet.tutor.id != current_user.id:
        return "Acesso negado", 403

    pet_id = cuidado.pet_id

    db.session.delete(cuidado)
    db.session.commit()

    return redirect(url_for("pet_care", pet_id=pet_id))


# -------------- INICIALIZAÇÃO -----------------

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    with app.app_context():
        db.create_all()

    app.run(debug=True)
