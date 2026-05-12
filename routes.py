# routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from database import db
from models import Material, Movimiento
from datetime import datetime
import pandas as pd
from io import BytesIO

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/dashboard')
def dashboard():
    from app import stock_material  # importamos la función desde app
    materiales = Material.query.all()
    labels = [m.nombre for m in materiales]
    stocks = [stock_material(m.id) for m in materiales]
    movimientos = Movimiento.query.order_by(Movimiento.fecha.desc()).limit(5).all()
    return render_template('dashboard.html',
                         materiales=materiales,
                         movimientos=movimientos,
                         labels=labels,
                         stocks=stocks)

@main_bp.route('/materiales')
def listar_materiales():
    materiales = Material.query.order_by(Material.nombre).all()
    return render_template('materiales.html', materiales=materiales)

@main_bp.route('/material/nuevo', methods=['GET', 'POST'])
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
            flash('✅ Material creado exitosamente', 'success')
            return redirect(url_for('main.listar_materiales'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error: {str(e)}', 'danger')
    return render_template('nuevo_material.html')

@main_bp.route('/material/<int:id>')
def detalle_material(id):
    from app import stock_material
    material = Material.query.get_or_404(id)
    movimientos = Movimiento.query.filter_by(material_id=id).order_by(Movimiento.fecha.desc()).all()
    stock = stock_material(id)
    return render_template('detalle_material.html',
                         material=material,
                         movimientos=movimientos,
                         stock_actual=stock)

@main_bp.route('/movimiento/nuevo', methods=['GET', 'POST'])
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
                usuario=request.form.get('usuario', 'Sistema')
            )
            db.session.add(movimiento)
            db.session.commit()
            flash('✅ Movimiento registrado exitosamente', 'success')
            return redirect(url_for('main.detalle_material', id=movimiento.material_id))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error: {str(e)}', 'danger')
    
    materiales = Material.query.order_by(Material.nombre).all()
    return render_template('movimientos.html', 
                         materiales=materiales,
                         now=datetime.now())

@main_bp.route('/reportes')
def reportes():
    return render_template('reportes.html')

@main_bp.route('/exportar/excel')
def exportar_excel():
    from app import stock_material
    try:
        materiales = Material.query.all()
        data = []
        for m in materiales:
            stock = stock_material(m.id)
            data.append({
                'Código': m.codigo,
                'Nombre': m.nombre,
                'Color': m.color,
                'Tipo': m.tipo,
                'Proveedor': m.proveedor or '',
                'Stock (m)': stock,
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
        return redirect(url_for('main.reportes'))