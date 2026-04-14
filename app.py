import io
import os
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, make_response, render_template, request, redirect, url_for, flash, session
from sqlalchemy.orm import joinedload
from sqlalchemy.engine import Engine
from sqlalchemy import event, cast, String, or_
from models import db, Product, Client, Employee, Sale, Config, initialize_database

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.sqlite")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "cambia_esta_clave")

db.init_app(app)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.close()


def get_tasa_hoy():
    config = Config.query.filter_by(fecha=date.today().isoformat()).first()
    return config.tasa_diaria if config else None


def prepare_database():
    if not os.path.exists(DB_PATH):
        initialize_database(app)
    else:
        with app.app_context():
            db.create_all()


prepare_database()

ROLE_PASSWORDS = {
    "vendedor": "vendedor123",
    "caja": "caja123",
    "admin": "admin123",
}

def require_role(required_role):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if session.get("role") != required_role:
                flash(f"Debe iniciar sesión como {required_role}.", "warning")
                return redirect(url_for("login", role=required_role))
            return f(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def inject_common_data():
    return {
        "tasa_actual": get_tasa_hoy(),
        "hoy": date.today().isoformat(),
    }


@app.before_request
def require_daily_rate():
    allowed = {"set_tasa", "static", "login", "logout"}
    if request.endpoint not in allowed and get_tasa_hoy() is None:
        return redirect(url_for("set_tasa"))


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    role = request.args.get("role", "vendedor")
    if request.method == "POST":
        role = request.form.get("role", "vendedor")
        password = request.form.get("password", "")
        if ROLE_PASSWORDS.get(role) == password:
            session["role"] = role
            flash(f"Acceso autorizado como {role}.", "success")
            if role == "vendedor":
                return redirect(url_for("device1"))
            if role == "caja":
                return redirect(url_for("device2"))
            if role == "admin":
                return redirect(url_for("device3"))
        flash("Contraseña incorrecta.", "danger")
    return render_template("login.html", role=role)


@app.route("/logout")
def logout():
    session.pop("role", None)
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))


@app.route("/device1")
def device1():
    employees = Employee.query.filter_by(active=True).order_by(Employee.name).all()
    return render_template("device4.html", employees=employees)


@app.route("/device4")
@require_role("vendedor")
def device4():
    return redirect(url_for("device1"))


@app.route("/tasa", methods=["GET", "POST"])
def set_tasa():
    tasa = None
    if request.method == "POST":
        try:
            tasa = float(request.form.get("tasa", "0").strip())
        except ValueError:
            flash("Ingrese una tasa válida.", "danger")
            return render_template("tasa.html", tasa=None)

        config = Config.query.filter_by(fecha=date.today().isoformat()).first()
        if not config:
            config = Config(fecha=date.today().isoformat(), tasa_diaria=tasa)
        else:
            config.tasa_diaria = tasa
        db.session.add(config)
        db.session.commit()
        flash("Tasa del día registrada con éxito.", "success")
        return redirect(url_for("device1"))

    config = Config.query.filter_by(fecha=date.today().isoformat()).first()
    if config:
        tasa = config.tasa_diaria
    return render_template("tasa.html", tasa=tasa)


@app.route("/search_products")
def search_products():
    query = request.args.get("q", "").strip()
    products = []
    if query:
        pattern = f"%{query}%"
        products = Product.query.filter(
            or_(
                Product.name.ilike(pattern),
                Product.brand.ilike(pattern),
                Product.model.ilike(pattern),
                cast(Product.id, String).ilike(pattern),
                cast(Product.price_usd, String).ilike(pattern),
            )
        ).order_by(Product.name).limit(50).all()
    return render_template("partials/product_list.html", products=products)


@app.route("/lookup_client")
def lookup_client():
    cedula = request.args.get("cedula", "").strip()
    client = None
    if cedula:
        client = Client.query.filter_by(cedula=cedula).first()
    return render_template("partials/client_result.html", client=client)


@app.route("/send_presale", methods=["POST"])
def send_presale():
    product_id = request.form.get("product_id")
    cedula = request.form.get("cedula", "").strip()
    quantity = request.form.get("quantity", "1")
    employee = request.form.get("employee", "").strip()
    device_source = request.form.get("device_source", "Dispositivo 1")

    if not product_id or not cedula:
        flash("Seleccione un producto y escriba la cédula del cliente.", "danger")
        return redirect(url_for("device1"))

    product = Product.query.get(product_id)
    if not product:
        flash("Producto no encontrado.", "danger")
        return redirect(url_for("device1"))

    try:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        flash("Cantidad inválida.", "danger")
        return redirect(url_for("device1"))

    # Verificar si ya existe una venta pendiente para este producto y cédula
    existing_sale = Sale.query.filter_by(
        product_id=product.id,
        client_cedula=cedula,
        status="pending"
    ).first()
    if existing_sale:
        flash("Ya existe una preventa pendiente para este producto y cliente.", "warning")
        return redirect(url_for("device1"))

    client = Client.query.filter_by(cedula=cedula).first()
    sale = Sale(
        product_id=product.id,
        client_id=client.id if client else None,
        client_cedula=cedula,
        client_name=client.name if client else None,
        client_address=client.address if client else None,
        client_phone=client.phone if client else None,
        client_email=client.email if client else None,
        quantity=quantity,
        price_usd=product.price_usd,
        status="pending",
        device_source=device_source,
        employee=employee,
    )
    db.session.add(sale)
    db.session.commit()
    flash("Venta enviada a Caja. El dispositivo 2 tendrá la solicitud pendiente.", "success")
    return redirect(url_for("device1"))


@app.route("/device2")
@require_role("caja")
def device2():
    pending_sales = Sale.query.options(joinedload(Sale.product)).filter_by(status="pending").order_by(Sale.created_at.desc()).all()
    products = Product.query.order_by(Product.name).all()
    return render_template("device2.html", pending_sales=pending_sales, products=products)


@app.route("/pending_alert")
def pending_alert():
    count = Sale.query.filter_by(status="pending").count()
    if count:
        return f"<div class=\"badge bg-warning ms-2\">{count} ventas pendientes</div>"
    return ""


@app.route("/presale/<int:sale_id>")
def presale_detail(sale_id):
    sale = Sale.query.options(joinedload(Sale.product)).get_or_404(sale_id)
    tasa_hoy = get_tasa_hoy()
    return render_template("partials/presale_detail.html", sale=sale, tasa_hoy=tasa_hoy)


@app.route("/process_sale/<int:sale_id>", methods=["POST"])
def process_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    payment_method = request.form.get("payment_method", "").strip()

    if not payment_method:
        flash("Seleccione un método de pago.", "danger")
        return redirect(url_for("device2"))

    if sale.product.stock < sale.quantity:
        flash("Stock insuficiente para procesar la venta.", "danger")
        return redirect(url_for("device2"))

    if not sale.client_id:
        name = request.form.get("client_name", "").strip()
        address = request.form.get("client_address", "").strip()
        phone = request.form.get("client_phone", "").strip()
        email = request.form.get("client_email", "").strip()

        if not name or not address:
            flash("Complete los datos del cliente para procesar la venta.", "danger")
            return redirect(url_for("device2"))

        client = Client.query.filter_by(cedula=sale.client_cedula).first()
        if not client:
            client = Client(
                cedula=sale.client_cedula,
                name=name,
                address=address,
                phone=phone,
                email=email,
            )
            db.session.add(client)
            db.session.flush()
        else:
            client.name = name
            client.address = address
            client.phone = phone
            client.email = email

        sale.client_id = client.id
        sale.client_name = name
        sale.client_address = address
        sale.client_phone = phone
        sale.client_email = email

    sale.payment_method = payment_method
    sale.status = "paid"
    sale.total_bs = sale.price_usd * get_tasa_hoy()
    sale.paid_at = datetime.utcnow()
    sale.product.stock = max(sale.product.stock - sale.quantity, 0)
    db.session.commit()
    flash("Venta procesada correctamente.", "success")
    return redirect(url_for("invoice", sale_id=sale.id))


@app.route("/add_client", methods=["POST"])
def add_client():
    cedula = request.form.get("cedula", "").strip()
    name = request.form.get("name", "").strip()
    address = request.form.get("address", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    next_page = request.form.get("next_page", "device3")
    if not cedula or not name or not address:
        flash("Cédula, nombre y dirección son obligatorios.", "danger")
        return redirect(url_for(next_page if next_page in {"device1", "device2", "device3"} else "device3"))

    client = Client.query.filter_by(cedula=cedula).first()
    if not client:
        client = Client(cedula=cedula, name=name, address=address, phone=phone, email=email)
        db.session.add(client)
    else:
        client.name = name
        client.address = address
        client.phone = phone
        client.email = email

    db.session.commit()
    flash("Cliente guardado correctamente.", "success")
    return redirect(url_for(next_page if next_page in {"device1", "device2", "device3"} else "device3"))


@app.route("/invoice/<int:sale_id>")
def invoice(sale_id):
    sale = Sale.query.options(joinedload(Sale.product)).get_or_404(sale_id)
    return render_template("invoice.html", sale=sale, tasa=get_tasa_hoy())


@app.route("/device3")
@require_role("admin")
def device3():
    page = request.args.get("page", 1, type=int)
    per_page = 100
    products_pagination = Product.query.order_by(Product.name).paginate(page=page, per_page=per_page, error_out=False)
    clients_pagination = Client.query.order_by(Client.name).paginate(page=page, per_page=per_page, error_out=False)
    employees_pagination = Employee.query.order_by(Employee.name).paginate(page=page, per_page=per_page, error_out=False)
    report_date = request.args.get("date", date.today().isoformat())
    return render_template("device3.html", products=products_pagination.items, clients=clients_pagination.items, employees=employees_pagination.items, products_pagination=products_pagination, clients_pagination=clients_pagination, employees_pagination=employees_pagination, report_date=report_date)


@app.route("/add_employee", methods=["POST"])
@require_role("admin")
def add_employee():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Nombre del empleado es obligatorio.", "danger")
        return redirect(url_for("device3"))

    existing = Employee.query.filter_by(name=name).first()
    if existing:
        flash("Empleado ya existe.", "warning")
        return redirect(url_for("device3"))

    employee = Employee(name=name)
    db.session.add(employee)
    db.session.commit()
    flash("Empleado agregado.", "success")
    return redirect(url_for("device3"))


@app.route("/toggle_employee/<int:emp_id>", methods=["POST"])
@require_role("admin")
def toggle_employee(emp_id):
    employee = Employee.query.get_or_404(emp_id)
    employee.active = not employee.active
    db.session.commit()
    flash(f"Empleado {'activado' if employee.active else 'desactivado'}.", "success")
    return redirect(url_for("device3"))


@app.route("/add_product", methods=["POST"])
def add_product():
    name = request.form.get("name", "").strip()
    brand = request.form.get("brand", "").strip()
    model = request.form.get("model", "").strip()
    price_usd = request.form.get("price_usd", "0").strip()
    stock = request.form.get("stock", "0").strip()

    if not name or not price_usd:
        flash("Nombre y precio son obligatorios.", "danger")
        return redirect(url_for("device3"))

    try:
        price_usd = float(price_usd)
        stock = int(stock)
    except ValueError:
        flash("Precio o stock inválidos.", "danger")
        return redirect(url_for("device3"))

    product = Product(name=name, brand=brand, model=model, price_usd=price_usd, stock=stock)
    db.session.add(product)
    db.session.commit()
    if request.headers.get('HX-Request'):
        return "<div class='alert alert-success'>Producto agregado al inventario.</div>"
    flash("Producto agregado al inventario.", "success")
    next_page = request.form.get("next_page", "device3")
    if next_page not in {"device2", "device3"}:
        next_page = "device3"
    return redirect(url_for(next_page))


@app.route("/export_report")
def export_report():
    report_date = request.args.get("date", date.today().isoformat())
    try:
        selected = datetime.fromisoformat(report_date)
    except ValueError:
        selected = datetime.combine(date.today(), datetime.min.time())
    start = datetime(selected.year, selected.month, selected.day)
    end = start + timedelta(days=1)
    sales = Sale.query.options(joinedload(Sale.product)).filter(Sale.created_at >= start, Sale.created_at < end).order_by(Sale.created_at).all()
    output = io.StringIO()
    output.write("<html><head><meta charset='utf-8' /></head><body>")
    output.write("<table border='1'><tr><th>Fecha</th><th>Nombre</th><th>Cédula</th><th>Producto</th><th>Marca</th><th>Cantidad</th><th>Empleado</th><th>Método</th><th>Total Bs</th></tr>")
    for sale in sales:
        output.write("<tr>")
        output.write(f"<td>{sale.created_at.strftime('%Y-%m-%d %H:%M:%S')}</td>")
        output.write(f"<td>{sale.client_name or ''}</td>")
        output.write(f"<td>{sale.client_cedula}</td>")
        output.write(f"<td>{sale.product.name}</td>")
        output.write(f"<td>{sale.product.brand or ''}</td>")
        output.write(f"<td>{sale.quantity}</td>")
        output.write(f"<td>{sale.employee or ''}</td>")
        output.write(f"<td>{sale.payment_method or ''}</td>")
        output.write(f"<td>{'%.2f' % (sale.total_bs or 0)}</td>")
        output.write("</tr>")
    output.write("</table></body></html>")
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "application/vnd.ms-excel"
    response.headers["Content-Disposition"] = f"attachment; filename=ventas_{year}.xls"
    return response


@app.route("/sales_report_partial")
def sales_report_partial():
    report_date = request.args.get("date", date.today().isoformat())
    try:
        selected = datetime.fromisoformat(report_date)
    except ValueError:
        selected = datetime.combine(date.today(), datetime.min.time())
    start = datetime(selected.year, selected.month, selected.day)
    end = start + timedelta(days=1)
    sales = Sale.query.options(joinedload(Sale.product)).filter(Sale.created_at >= start, Sale.created_at < end).order_by(Sale.created_at.desc()).all()
    return render_template("partials/sales_report.html", sales=sales, report_date=report_date)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
