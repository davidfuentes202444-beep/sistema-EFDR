# Sistema POS Venezuela

Sistema de Punto de Venta para Venezuela con soporte multi-dispositivo.

## Características

- ✅ Gestión de inventario
- ✅ Registro de clientes
- ✅ Ventas con conversión USD a BS
- ✅ Reportes diarios
- ✅ Interfaz multi-dispositivo (Vendedor, Caja, Admin)
- ✅ Impresión térmica para facturas

## Instalación Local

1. Clona el repositorio:
```bash
git clone https://github.com/tuusuario/sistema-pos-venezuela.git
cd sistema-pos-venezuela
```

2. Instala dependencias:
```bash
pip install -r requirements.txt
```

3. Ejecuta la aplicación:
```bash
python app.py
```

4. Accede en: http://127.0.0.1:5000

## Despliegue en Producción

### Railway (Recomendado)
1. Ve a [railway.app](https://railway.app)
2. Conecta tu GitHub
3. Crea proyecto desde este repo
4. Se despliega automáticamente

### Render
1. Ve a [render.com](https://render.com)
2. Conecta GitHub
3. Crea Web Service
4. Configura:
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`

## URLs de Acceso

- **Vendedor**: `/device1` (sin login)
- **Caja**: `/device2` (login: caja/caja123)
- **Admin**: `/device3` (login: admin/admin123)

## Tecnologías

- Flask 3.0
- SQLAlchemy
- Bootstrap 5
- HTMX
- SQLite (local) / PostgreSQL (producción)

## Licencia

MIT