from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os
import pandas as pd
from io import BytesIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_segura_cambiar_en_produccion'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventario.db'
import os

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///inventario.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('reports', exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # nombre de la ruta de login

# ================== MODELO DE USUARIO ==================
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # En producción usa hash
    role = db.Column(db.String(20), default='usuario')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ================== MODELOS DE MATERIAL Y MOVIMIENTO ==================
class Material(db.Model):
    __tablename__ = 'materiales'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(100), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(50))
    tipo = db.Column(db.String(50))
    proveedor = db.Column(db.String(100))
    descripcion = db.Column(db.Text)
    unidad_medida = db.Column(db.String(20), default='metros')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    movimientos = db.relationship('Movimiento', backref='material', lazy=True, cascade='all, delete-orphan')

    def stock_actual(self):
        entradas = sum(m.cantidad for m in self.movimientos if m.tipo == 'entrada')
        salidas = sum(m.cantidad for m in self.movimientos if m.tipo == 'salida')
        return entradas - salidas

class Movimiento(db.Model):
    __tablename__ = 'movimientos'
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('materiales.id'), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
    cantidad = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    referencia = db.Column(db.String(100))
    descripcion = db.Column(db.Text)
    usuario = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Crear tablas y usuarios iniciales
with app.app_context():
    db.create_all()
    # Crear tres usuarios si no existen
    if User.query.count() == 0:
        users = [
            User(username='admin', password='admin123', role='admin'),
            User(username='usuario1', password='pass1', role='usuario'),
            User(username='usuario2', password='pass2', role='usuario'),
        ]
        db.session.add_all(users)
        db.session.commit()
        print("✅ Usuarios creados: admin, usuario1, usuario2")

# ================== FUNCIÓN AUXILIAR ==================
def stock_material(material_id):
    material = Material.query.get(material_id)
    return material.stock_actual() if material else 0

app.jinja_env.globals.update(stock_material=stock_material)

# ================== RUTAS DE AUTENTICACIÓN ==================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))

# Ruta temporal para crear usuarios manualmente (si no se crearon automáticamente)
@app.route('/crear_usuarios')
def crear_usuarios():
    with app.app_context():
        if User.query.count() == 0:
            users = [
                User(username='admin', password='admin123', role='admin'),
                User(username='usuario1', password='pass1', role='usuario'),
                User(username='usuario2', password='pass2', role='usuario'),
            ]
            db.session.add_all(users)
            db.session.commit()
            return "✅ Usuarios creados correctamente."
        else:
            return "⚠️ Ya existen usuarios."
    return "Error"

# ================== RUTAS PROTEGIDAS ==================
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    materiales = Material.query.all()
    labels = [m.nombre for m in materiales]
    stocks = [m.stock_actual() for m in materiales]
    movimientos = Movimiento.query.order_by(Movimiento.fecha.desc()).limit(5).all()
    return render_template('dashboard.html',
                         materiales=materiales,
                         movimientos=movimientos,
                         labels=labels,
                         stocks=stocks)

@app.route('/materiales')
@login_required
def listar_materiales():
    materiales = Material.query.order_by(Material.nombre).all()
    return render_template('materiales.html', materiales=materiales)

@app.route('/material/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_material():
    if request.method == 'POST':
        try:
            material = Material(
                codigo=request.form['codigo'],
                nombre=request.form['nombre'],
                color=request.form['color'],
                tipo=request.form['tipo'],
                proveedor=request.form.get('proveedor', ''),
                descripcion=request.form.get('descripcion', ''),
                unidad_medida=request.form.get('unidad_medida', 'metros')
            )
            db.session.add(material)
            db.session.commit()
            flash('✅ Material creado', 'success')
            return redirect(url_for('listar_materiales'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error: {str(e)}', 'danger')
    return render_template('nuevo_material.html')

@app.route('/material/<int:id>')
@login_required
def detalle_material(id):
    material = Material.query.get_or_404(id)
    movimientos = Movimiento.query.filter_by(material_id=id).order_by(Movimiento.fecha.desc()).all()
    return render_template('detalle_material.html',
                         material=material,
                         movimientos=movimientos,
                         stock_actual=material.stock_actual())

@app.route('/movimiento/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_movimiento():
    if request.method == 'POST':
        try:
            movimiento = Movimiento(
                material_id=int(request.form['material_id']),
                tipo=request.form['tipo'],
                cantidad=float(request.form['cantidad']),
                fecha=datetime.strptime(request.form['fecha'], '%Y-%m-%d'),
                referencia=request.form.get('referencia', ''),
                descripcion=request.form.get('descripcion', ''),
                usuario=current_user.username
            )
            db.session.add(movimiento)
            db.session.commit()
            flash('✅ Movimiento registrado', 'success')
            return redirect(url_for('detalle_material', id=movimiento.material_id))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error: {str(e)}', 'danger')
    materiales = Material.query.order_by(Material.nombre).all()
    return render_template('movimientos.html', materiales=materiales, now=datetime.now())

@app.route('/reportes')
@login_required
def reportes():
    return render_template('reportes.html')

@app.route('/exportar/excel')
@login_required
def exportar_excel():
    try:
        materiales = Material.query.all()
        data = []
        for m in materiales:
            data.append({
                'Código': m.codigo,
                'Nombre': m.nombre,
                'Color': m.color,
                'Tipo': m.tipo,
                'Proveedor': m.proveedor or '',
                'Stock (m)': m.stock_actual(),
                'Unidad': m.unidad_medida
            })
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Inventario', index=False)
        output.seek(0)
        filename = f'inventario_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error al exportar: {str(e)}', 'danger')
        return redirect(url_for('reportes'))

# ================== RUTA DE IMPORTACIÓN COMPLETA ==================
@app.route('/importar_excel', methods=['GET', 'POST'])
@login_required
def importar_excel():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No se seleccionó ningún archivo', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Archivo vacío', 'danger')
            return redirect(request.url)
        if file and file.filename.endswith('.xlsx'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            try:
                # Leer el Excel con header=0 (primera fila de datos es el encabezado)
                df = pd.read_excel(filepath, sheet_name='BASE MAESTRO', header=0)
                # Tomar columnas A a I (0 a 8)
                df = df.iloc[:, :9]
                # Asignar nombres según la cabecera real
                df.columns = ['tipo', 'nombre', 'color', 'proveedor',
                              'cant_entrada', 'fecha_entrada', 'cant_salida', 'fecha_salida', 'total']

                print("\n=== INICIANDO IMPORTACIÓN ===")
                print(f"Total de filas: {len(df)}")

                ultimo_tipo = None
                contador_materiales = 0
                contador_movimientos = 0

                for idx, row in df.iterrows():
                    if pd.isna(row['nombre']):
                        continue

                    # Tipo (columna 'tipo') - se hereda si está vacío
                    if pd.notna(row['tipo']):
                        ultimo_tipo = str(row['tipo']).strip()
                    tipo_actual = ultimo_tipo if ultimo_tipo else 'GENERAL'

                    nombre_completo = str(row['nombre']).strip()
                    codigo = nombre_completo
                    color = str(row['color']).strip() if pd.notna(row['color']) else ''
                    proveedor = str(row['proveedor']).strip() if pd.notna(row['proveedor']) else 'KOPEEL'

                    print(f"\nProcesando fila {idx+1}: {codigo}")

                    # Crear material si no existe
                    material = Material.query.filter_by(codigo=codigo).first()
                    if not material:
                        material = Material(
                            codigo=codigo,
                            nombre=nombre_completo,
                            color=color,
                            tipo=tipo_actual,
                            proveedor=proveedor,
                            unidad_medida='metros'
                        )
                        db.session.add(material)
                        db.session.flush()
                        contador_materiales += 1
                        print(f"  ✅ Material creado (ID: {material.id})")
                    else:
                        print(f"  ⚠️ Material ya existente (ID: {material.id})")

                    # --- Movimiento de entrada (cantidad en 'cant_entrada', fecha en 'fecha_entrada') ---
                    cant_ent = row['cant_entrada']
                    if pd.notna(cant_ent):
                        try:
                            cant_ent = float(cant_ent)
                            if cant_ent > 0:
                                fecha_ent = None
                                if pd.notna(row['fecha_entrada']):
                                    try:
                                        fecha_ent = pd.to_datetime(row['fecha_entrada']).to_pydatetime()
                                    except:
                                        pass
                                if fecha_ent is None:
                                    print(f"    ⚠️ Entrada sin fecha, se omite")
                                else:
                                    # Evitar duplicados
                                    existe = Movimiento.query.filter_by(
                                        material_id=material.id,
                                        tipo='entrada',
                                        cantidad=cant_ent,
                                        fecha=fecha_ent
                                    ).first()
                                    if not existe:
                                        mov = Movimiento(
                                            material_id=material.id,
                                            tipo='entrada',
                                            cantidad=cant_ent,
                                            fecha=fecha_ent,
                                            referencia='ENTRADA',
                                            usuario='Sistema'
                                        )
                                        db.session.add(mov)
                                        contador_movimientos += 1
                                        print(f"    + Entrada: {cant_ent} m el {fecha_ent.strftime('%Y-%m-%d')}")
                        except (ValueError, TypeError):
                            print(f"    ⚠️ Cantidad de entrada no numérica: {cant_ent}")

                    # --- Movimiento de salida (cantidad en 'cant_salida', fecha en 'fecha_salida') ---
                    cant_sal = row['cant_salida']
                    if pd.notna(cant_sal):
                        try:
                            cant_sal = float(cant_sal)
                            if cant_sal > 0:
                                fecha_sal = None
                                if pd.notna(row['fecha_salida']):
                                    try:
                                        fecha_sal = pd.to_datetime(row['fecha_salida']).to_pydatetime()
                                    except:
                                        pass
                                if fecha_sal is None:
                                    print(f"    ⚠️ Salida sin fecha, se omite")
                                else:
                                    existe = Movimiento.query.filter_by(
                                        material_id=material.id,
                                        tipo='salida',
                                        cantidad=cant_sal,
                                        fecha=fecha_sal
                                    ).first()
                                    if not existe:
                                        mov = Movimiento(
                                            material_id=material.id,
                                            tipo='salida',
                                            cantidad=cant_sal,
                                            fecha=fecha_sal,
                                            referencia='SALIDA',
                                            usuario='Sistema'
                                        )
                                        db.session.add(mov)
                                        contador_movimientos += 1
                                        print(f"    - Salida: {cant_sal} m el {fecha_sal.strftime('%Y-%m-%d')}")
                        except (ValueError, TypeError):
                            print(f"    ⚠️ Cantidad de salida no numérica: {cant_sal}")

                db.session.commit()
                print("\n=== RESUMEN ===")
                print(f"✅ Materiales creados: {contador_materiales}")
                print(f"✅ Movimientos registrados: {contador_movimientos}")
                flash(f'✅ Datos importados correctamente. {contador_materiales} materiales nuevos, {contador_movimientos} movimientos.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Error al importar: {str(e)}', 'danger')
                print(f"\n❌ ERROR: {str(e)}")
            finally:
                os.remove(filepath)
            return redirect(url_for('listar_materiales'))
        else:
            flash('Formato de archivo no válido. Debe ser .xlsx', 'danger')
            return redirect(request.url)

    # GET: formulario
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Importar Excel</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-5">
            <h2>Importar datos desde Excel</h2>
            <p>Selecciona el archivo Excel con la hoja "BASE MAESTRO".</p>
            <form method="post" enctype="multipart/form-data">
                <div class="mb-3">
                    <label for="file" class="form-label">Archivo Excel (.xlsx)</label>
                    <input class="form-control" type="file" name="file" accept=".xlsx" required>
                </div>
                <button type="submit" class="btn btn-primary">Importar</button>
                <a href="/" class="btn btn-secondary">Cancelar</a>
            </form>
        </div>
    </body>
    </html>
    '''
if __name__ == '__main__':
    import os
    # Esto permite que Render le asigne el puerto que necesite
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

@app.before_request
def cargar_maestro_materiales():
    db.create_all()
    
    materiales_iniciales = [
        {"codigo": "COMUS", "nombre": "COMUS BLANCO", "color": "BLANCO", "tipo": "KOPEEL", "stock": 538.9},
        {"codigo": "COMUS", "nombre": "COMUS BLANCO BRILLANTE", "color": "BLANCO BRILLANTE", "tipo": "KOPEEL", "stock": 4.0},
        {"codigo": "COMUS", "nombre": "COMUS AMARILLO", "color": "AMARILLO", "tipo": "KOPEEL", "stock": 8.0},
        {"codigo": "COMUS", "nombre": "COMUS AZUL", "color": "AZUL", "tipo": "KOPEEL", "stock": 59.1},
        {"codigo": "COMUS", "nombre": "COMUS AMARILLO VERDE", "color": "AMARILLO VERDE", "tipo": "KOPEEL", "stock": 325.0},
        {"codigo": "COMUS", "nombre": "COMUS ROJO", "color": "ROJO", "tipo": "KOPEEL", "stock": 5.0},
        {"codigo": "COMUS", "nombre": "COMUS NARANJA", "color": "NARANJA", "tipo": "KOPEEL", "stock": 28.0},
        {"codigo": "COMUS", "nombre": "COMUS NEGRO", "color": "NEGRO", "tipo": "KOPEEL", "stock": 95.5},
        {"codigo": "GERMANO", "nombre": "GER ROJO", "color": "ROJO", "tipo": "KOPEEL", "stock": 129.8},
        {"codigo": "GERMANO", "nombre": "GER VERDE", "color": "VERDE", "tipo": "KOPEEL", "stock": 10.0},
        {"codigo": "GERMANO", "nombre": "GER NEGRO", "color": "NEGRO", "tipo": "KOPEEL", "stock": 5.0},
        {"codigo": "GERMANO", "nombre": "GER AZUL REY", "color": "AZUL REY", "tipo": "KOPEEL", "stock": 8.0},
        {"codigo": "GERMANO", "nombre": "GER GRIS", "color": "GRIS", "tipo": "KOPEEL", "stock": 3.0},
        {"codigo": "GERMANO", "nombre": "GER AZUL OSCURO", "color": "AZUL OSCURO", "tipo": "KOPEEL", "stock": 4.0},
        {"codigo": "GERMANO", "nombre": "GER BLANCO", "color": "BLANCO", "tipo": "KOPEEL", "stock": 70.0},
        {"codigo": "GERMANO", "nombre": "GER FUCSIA", "color": "FUCSIA", "tipo": "KOPEEL", "stock": 2.0},
        {"codigo": "GERMANO", "nombre": "GER MORADO", "color": "MORADO", "tipo": "KOPEEL", "stock": 1.0},
        {"codigo": "GERMANO", "nombre": "GER CELESTE", "color": "CELESTE", "tipo": "KOPEEL", "stock": 1.0},
        {"codigo": "GERMANO", "nombre": "GER ROSADO", "color": "ROSADO", "tipo": "KOPEEL", "stock": 1.0},
        {"codigo": "GOLTY", "nombre": "GOL AZUL REY", "color": "AZUL REY", "tipo": "KOPEEL", "stock": 2.0},
        {"codigo": "GOLTY", "nombre": "GOL AMARILLO", "color": "AMARILLO", "tipo": "KOPEEL", "stock": 2.0},
        {"codigo": "GOLTY", "nombre": "GOL NEGRO", "color": "NEGRO", "tipo": "KOPEEL", "stock": 110.0},
        {"codigo": "GOLTY", "nombre": "GOL ROJO", "color": "ROJO", "tipo": "KOPEEL", "stock": 5.0},
        {"codigo": "GOLTY", "nombre": "GOL ROJO MATE", "color": "ROJO MATE", "tipo": "KOPEEL", "stock": 1.0},
        {"codigo": "GOLTY", "nombre": "GOL VERDE OSCURO", "color": "VERDE OSCURO", "tipo": "KOPEEL", "stock": 1.0},
        {"codigo": "MEET", "nombre": "KOPEEL", "color": "COLOR", "tipo": "KOPEEL", "stock": 18.0},
        {"codigo": "MEET", "nombre": "MEETNEGRO", "color": "NEGRO", "tipo": "KOPEEL", "stock": 27.0},
        {"codigo": "MEET", "nombre": "MEETROJO", "color": "ROJO", "tipo": "KOPEEL", "stock": 25.0},
        {"codigo": "VOLEYBOL", "nombre": "VOL BLANCO", "color": "BLANCO", "tipo": "KOPEEL", "stock": 69.0},
        {"codigo": "VOLEYBOL", "nombre": "VOL ROJO", "color": "ROJO", "tipo": "KOPEEL", "stock": 25.0},
        {"codigo": "VOLEYBOL", "nombre": "VOL VERDE", "color": "VERDE", "tipo": "KOPEEL", "stock": 0.0},
        {"codigo": "VOLEYBOL", "nombre": "VOL AMARILLO", "color": "AMARILLO", "tipo": "KOPEEL", "stock": 7.0},
        {"codigo": "VOLEYBOL", "nombre": "VOL AZUL", "color": "AZUL", "tipo": "KOPEEL", "stock": 12.0},
        {"codigo": "COSTA", "nombre": "COS OROJO", "color": "ROJO", "tipo": "KOPEEL", "stock": 35.0},
        {"codigo": "COSTA", "nombre": "COS OVERDE", "color": "VERDE", "tipo": "KOPEEL", "stock": 71.0},
        {"codigo": "COSTA", "nombre": "COS OBLANCO", "color": "BLANCO", "tipo": "KOPEEL", "stock": 25.0},
        {"codigo": "MEXICANO", "nombre": "MEX OASISI VERDE", "color": "OASISI VERDE", "tipo": "KOPEEL", "stock": 30.0},
        {"codigo": "PU_PVC", "nombre": "PU 1.4 BLANCO MATE", "color": "BLANCO MATE", "tipo": "PU PVC", "stock": 124.0},
        {"codigo": "PU_PVC", "nombre": "PU 1.4 BLANCO BRILLANTE", "color": "BLANCO BRILLANTE", "tipo": "PU PVC", "stock": 47.0},
        {"codigo": "PU_PVC", "nombre": "PU 1.4 AMARILLO NEON BRILLANTE", "color": "AMARILLO NEON BRILLANTE", "tipo": "PU PVC", "stock": 80.0},
        {"codigo": "PU_PVC", "nombre": "PU 1.4 NARANJA NEON", "color": "NARANJA NEON", "tipo": "PU PVC", "stock": 24.0},
        {"codigo": "PU_PVC", "nombre": "PU 1.4 AZUL REY BRILLANTE", "color": "AZUL REY BRILLANTE", "tipo": "PU PVC", "stock": 12.0},
        {"codigo": "PU_PVC", "nombre": "PU 1.2 BLANCO MATE TEXTURADO", "color": "BLANCO MATE TEXTURADO", "tipo": "PU PVC", "stock": 35.0},
        {"codigo": "PU_PVC", "nombre": "PU 1.2 AMARILLO MATE TEXTURADO", "color": "AMARILLO MATE TEXTURADO", "tipo": "PU PVC", "stock": 46.0},
        {"codigo": "PU_PVC", "nombre": "PU GRIS PLATA TEXTURADO", "color": "GRIS PLATA TEXTURADO", "tipo": "PU PVC", "stock": 140.0},
        {"codigo": "PU_PVC", "nombre": "PVC 1.2 BLANCO FOAM", "color": "BLANCO FOAM", "tipo": "PU PVC", "stock": 29.0},
        {"codigo": "PU_PVC", "nombre": "PVC 1.2 AMARILLO FOAM", "color": "AMARILLO FOAM", "tipo": "PU PVC", "stock": 40.0},
        {"codigo": "PU_PVC", "nombre": "PVC 1.2 NARANJA FOAM", "color": "NARANJA FOAM", "tipo": "PU PVC", "stock": 23.0},
        {"codigo": "TPU", "nombre": "TPU 0.15 BLANCO", "color": "BLANCO", "tipo": "TPU", "stock": 16.0},
        {"codigo": "TPU", "nombre": "TPU 0.20 BLANCO", "color": "BLANCO", "tipo": "TPU", "stock": 50.0},
        {"codigo": "TPU", "nombre": "TPU 0.20 AMARILLO NEON", "color": "AMARILLO NEON", "tipo": "TPU", "stock": 30.0},
        {"codigo": "TPU", "nombre": "TPU 0.20 NARANJA NEON", "color": "NARANJA NEON", "tipo": "TPU", "stock": 31.0},
        {"codigo": "NEUMATICOS", "nombre": "MICROPOROSA N° 4", "color": "NEGRO", "tipo": "NEUMATICOS", "stock": 12.0},
        {"codigo": "NEUMATICOS", "nombre": "MICROPOROSA N° 5", "color": "NEGRO", "tipo": "NEUMATICOS", "stock": 53.0},
        {"codigo": "NEUMATICOS", "nombre": "VALVULAS", "color": "NEGRO", "tipo": "NEUMATICOS", "stock": 400.0},
        {"codigo": "NEUMATICOS", "nombre": "BLADER GOLTY ORIGINAL N° 5", "color": "NEGRO", "tipo": "NEUMATICOS", "stock": 12.0},
        {"codigo": "NEUMATICOS", "nombre": "BLADER BOUTE N° 5", "color": "NEGRO", "tipo": "NEUMATICOS", "stock": 61.0},
        {"codigo": "NEUMATICOS", "nombre": "BLADER BOUTE N° 4", "color": "NEGRO", "tipo": "NEUMATICOS", "stock": 50.0},
        {"codigo": "NEUMATICOS", "nombre": "BLADER COSTA N° 5", "color": "NEGRO", "tipo": "NEUMATICOS", "stock": 20.0}
    ]
    
    try:
        from app_unificada import Material
        if Material.query.count() < 30:
            # Limpiamos remanentes previos para que entre el lote completo impecable
            Material.query.delete()
            db.session.commit()
            
            codigos_vistos = {}
            for mat in materiales_iniciales:
                nuevo = Material()
                
                # Generamos un identificador único para la columna código base
                base_code = mat["codigo"].strip().replace(" ", "_")
                if base_code not in codigos_vistos:
                    codigos_vistos[base_code] = 1
                    nuevo.codigo = base_code
                else:
                    codigos_vistos[base_code] += 1
                    nuevo.codigo = f"{base_code}_{codigos_vistos[base_code]}"
                
                nuevo.nombre = mat["nombre"]
                nuevo.color = mat["color"]
                nuevo.tipo = mat["tipo"]
                
                if hasattr(nuevo, 'cantidad'):
                    nuevo.cantidad = mat["stock"]
                elif hasattr(nuevo, 'metraje'):
                    nuevo.metraje = mat["stock"]
                elif hasattr(nuevo, 'stock_inicial'):
                    nuevo.stock_inicial = mat["stock"]
                else:
                    nuevo.stock = mat["stock"]
                    
                db.session.add(nuevo)
            db.session.commit()
            print("¡Carga completa y exitosa de las 59 referencias con códigos únicos!")
    except Exception as e:
        print(f"Error durante la carga masiva: {e}")
