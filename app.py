import os
import zipfile
import xml.etree.ElementTree as ET
from flask import Flask, request, render_template, redirect, url_for

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def parse_3mf(file_path):
    with zipfile.ZipFile(file_path, 'r') as z:
        with z.open('3D/3dmodel.model') as model_file:
            tree = ET.parse(model_file)
            root = tree.getroot()
            ns = {'ns': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

            vertices = []
            for mesh in root.findall(".//ns:mesh", ns):
                for vertex in mesh.findall(".//ns:vertex", ns):
                    x = float(vertex.attrib['x'])
                    y = float(vertex.attrib['y'])
                    z = float(vertex.attrib['z'])
                    vertices.append((x, y, z))
            return vertices

def calculate_cost(vertices):
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]

    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    dz = max(zs) - min(zs)

    volume_mm3 = dx * dy * dz
    volume_cm3 = volume_mm3 / 1000.0
    cost = volume_cm3 * 7

    return round(volume_cm3, 2), round(cost, 2)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename.endswith('.3mf'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            try:
                vertices = parse_3mf(filepath)
                volume, cost = calculate_cost(vertices)
                return render_template('index.html', volume=volume, cost=cost, filename=file.filename)
            except Exception as e:
                return f"Ошибка при обработке файла: {e}"
        else:
            return "Пожалуйста, загрузите файл с расширением .3mf"
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
