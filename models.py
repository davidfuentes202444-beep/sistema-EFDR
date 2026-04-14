from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# ORM ligero para SQLite
# La estructura incluye inventario, clientes, ventas y configuración de tasa diaria.

db = SQLAlchemy()

class Config(db.Model):
    __tablename__ = "configuracion"
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.String(10), nullable=False, unique=True)
    tasa_diaria = db.Column(db.Float, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Product(db.Model):
    __tablename__ = "inventario"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    brand = db.Column(db.String(80), nullable=True, index=True)
    model = db.Column(db.String(80), nullable=True, index=True)
    price_usd = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Client(db.Model):
    __tablename__ = "clientes"
    id = db.Column(db.Integer, primary_key=True)
    cedula = db.Column(db.String(32), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    address = db.Column(db.String(240), nullable=True)
    phone = db.Column(db.String(60), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Employee(db.Model):
    __tablename__ = "empleados"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Sale(db.Model):
    __tablename__ = "ventas"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("inventario.id"), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True, index=True)
    client_cedula = db.Column(db.String(32), nullable=False, index=True)
    client_name = db.Column(db.String(120), nullable=True)
    client_address = db.Column(db.String(240), nullable=True)
    client_phone = db.Column(db.String(60), nullable=True)
    client_email = db.Column(db.String(120), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    payment_method = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    price_usd = db.Column(db.Float, nullable=False)
    total_bs = db.Column(db.Float, nullable=True)
    device_source = db.Column(db.String(60), nullable=True)
    employee = db.Column(db.String(120), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    paid_at = db.Column(db.DateTime, nullable=True)

    product = db.relationship("Product")
    client = db.relationship("Client")


def initialize_database(app):
    with app.app_context():
        db.create_all()
        # Agregar empleados por defecto si no existen
        if not Employee.query.first():
            default_employees = [
                "Juan Pérez",
                "María García",
                "Carlos López",
                "Ana Rodríguez"
            ]
            for name in default_employees:
                emp = Employee(name=name)
                db.session.add(emp)
            db.session.commit()
